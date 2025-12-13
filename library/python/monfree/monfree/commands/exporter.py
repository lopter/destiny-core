import asyncio
import click
import ipaddress
import json
import logging
import prometheus_client
import signal
import threading
import time
import urllib.error
import urllib.request

from monfree import mtrpacket

__all__ = ["exporter"]

logger = logging.getLogger(__name__)

PING_INTERVAL = 10.0  # seconds
PING_TTL = 64
TRACEROUTE_INTERVAL = 30.0  # seconds
TRACEROUTE_MAX_TTL = 28
TRACEROUTE_PROBE_DELAY = 0.075  # 75ms between probes

LATENCY_BUCKETS = (
    0.001,  # 1ms   - local network, same rack
    0.002,  # 2ms   - same datacenter
    0.005,  # 5ms   - same datacenter / nearby
    0.010,  # 10ms  - same metro/region
    0.020,  # 20ms  - regional
    0.050,  # 50ms  - same continent
    0.100,  # 100ms - continental
    0.200,  # 200ms - intercontinental
    0.500,  # 500ms - high latency / satellite
    1.0,    # 1s    - problematic
    2.0,    # 2s    - severe issues
)

packet_counter = prometheus_client.Counter(
    "mtr_packets_total",
    "Count of packets sent and whether they came back",
    ["asn", "endpoint", "responder", "result", "source", "task", "ttl"],
)

packet_latency = prometheus_client.Histogram(
    "mtr_ping_latency_seconds",
    "Latency in seconds for a hop",
    ["asn", "endpoint", "responder", "source", "task", "ttl"],
    buckets=LATENCY_BUCKETS,
)


def validate_ip_address(
    ctx: click.Context,
    param: click.Parameter,
    value: tuple[str, ...],
) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Validate and parse IP addresses."""
    result: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for addr in value:
        try:
            result.append(ipaddress.ip_address(addr))
        except ValueError:
            raise click.BadParameter(f"'{addr}' is not a valid IP address")
    return result


@click.command()
@click.option(
    "-p",
    "--port",
    type=click.IntRange(1, 65535),
    default=9091,
    show_default=True,
)
@click.option(
    "-l",
    "--listen-addr",
    default="0.0.0.0",
    show_default=True,
)
@click.option(
    "-e",
    "--endpoint",
    multiple=True,
    required=True,
    callback=validate_ip_address,
    help="Endpoint IP address (can be specified multiple times)",
)
@click.option(
    "-s",
    "--source",
    multiple=True,
    required=True,
    callback=validate_ip_address,
    help="Source IP address used for monitoring (can be specified multiple times)",
)
@click.pass_context
def exporter(
    ctx: click.Context,
    port: int,
    listen_addr: str,
    endpoint: list[ipaddress.IPv4Address | ipaddress.IPv6Address],
    source: list[ipaddress.IPv4Address | ipaddress.IPv6Address],
) -> None:
    ipv4_source = next((src for src in source if is_ipv4(src)), None)
    ipv6_source = next((src for src in source if is_ipv6(src)), None)

    has_ipv4_endpoint = any(is_ipv4(ep) for ep in endpoint)
    has_ipv6_endpoint = any(is_ipv6(ep) for ep in endpoint)
    if has_ipv4_endpoint and not ipv4_source:
        msg = "IPv4 endpoint(s) specified but no IPv4 source address provided"
        ctx.fail(msg)
    if has_ipv6_endpoint and not ipv6_source:
        msg = "IPv6 endpoint(s) specified but no IPv6 source address provided"
        ctx.fail(msg)

    wsgi_server, server_thread = prometheus_client.start_http_server(port, listen_addr)

    stop_event = threading.Event()
    monitor_thread = threading.Thread(
        target=monitor,
        args=(endpoint, ipv4_source, ipv6_source, stop_event),
        daemon=False,
    )
    monitor_thread.start()

    shutdown_signals = (signal.SIGINT, signal.SIGTERM, signal.SIGQUIT)

    def signal_handler(signum: int, frame: object) -> None:
        signal_name = signal.Signals(signum).name
        logger.info(f"Received {signal_name}, shutting down…")
        stop_event.set()

    for sig in shutdown_signals:
        _ = signal.signal(sig, signal_handler)

    _ = stop_event.wait()
    wsgi_server.shutdown()
    server_thread.join()
    monitor_thread.join()


def is_ipv4(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return isinstance(addr, ipaddress.IPv4Address)


def is_ipv6(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return isinstance(addr, ipaddress.IPv6Address)


def monitor(
    endpoints: list[ipaddress.IPv4Address | ipaddress.IPv6Address],
    ipv4_source: ipaddress.IPv4Address | None,
    ipv6_source: ipaddress.IPv6Address | None,
    stop_event: threading.Event,
) -> None:
    """Monitor endpoints and export metrics using asyncio."""
    try:
        asyncio.run(async_monitor(endpoints, ipv4_source, ipv6_source, stop_event))
    except Exception as e:
        logger.error(f"Monitor failed: {e}")
        stop_event.set()
        raise


async def async_monitor(
    endpoints: list[ipaddress.IPv4Address | ipaddress.IPv6Address],
    ipv4_source: ipaddress.IPv4Address | None,
    ipv6_source: ipaddress.IPv6Address | None,
    stop_event: threading.Event,
) -> None:
    """Async implementation of the monitor."""
    async with mtrpacket.MtrPacket() as mtr:
        loop = asyncio.get_running_loop()

        tasks: list[asyncio.Task] = []
        for ep in endpoints:
            source = ipv4_source if is_ipv4(ep) else ipv6_source
            assert source is not None
            tasks.append(asyncio.create_task(ping(mtr, ep, source)))
            tasks.append(asyncio.create_task(traceroute(mtr, ep, source)))

        stop_future = loop.run_in_executor(None, stop_event.wait)

        done, pending = await asyncio.wait(
            [stop_future, *tasks],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for p in pending:
            p.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

        for d in done:
            if d is not stop_future and (exc := d.exception()) is not None:
                raise exc


async def ping(
    mtr: mtrpacket.MtrPacket,
    endpoint: ipaddress.IPv4Address | ipaddress.IPv6Address,
    source: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> None:
    """Continuously ping an endpoint every PING_INTERVAL seconds."""

    endpoint_str = str(endpoint)
    source_str = str(source)
    base_labels = {
        "endpoint": endpoint_str,
        "source": source_str,
        "task": "ping",
        "ttl": str(PING_TTL),
    }

    try:
        while True:
            start_time = time.monotonic()

            logger.info(f"ping: sending probe to {endpoint_str}")
            result = await mtr.probe(
                endpoint_str,
                ttl=PING_TTL,
                protocol="icmp",
            )
            logger.info(
                f"ping: got {result.result} from {endpoint_str} "
                f"in {result.time_ms}ms"
            )

            responder = result.responder or ""
            asn = await get_asn(responder)

            labels = base_labels | {
                "asn": asn,
                "responder": responder,
                "result": result.result,
            }
            packet_counter.labels(**labels).inc()

            if result.time_ms is not None:
                del labels["result"]
                packet_latency.labels(**labels).observe(result.time_ms / 1000.0)

            elapsed = time.monotonic() - start_time
            sleep_time = max(0, PING_INTERVAL - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
    except asyncio.CancelledError:
        pass


async def traceroute(
    mtr: mtrpacket.MtrPacket,
    endpoint: ipaddress.IPv4Address | ipaddress.IPv6Address,
    source: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> None:
    """Continuously traceroute to an endpoint every TRACEROUTE_INTERVAL seconds."""

    endpoint_str = str(endpoint)
    source_str = str(source)
    base_labels = {
        "endpoint": endpoint_str,
        "source": source_str,
        "task": "traceroute",
    }

    try:
        while True:
            start_time = time.monotonic()

            for ttl in range(1, TRACEROUTE_MAX_TTL + 1):
                logger.info(
                    f"traceroute: sending probe to "
                    f"{endpoint_str} with ttl={ttl}"
                )
                result = await mtr.probe(
                    endpoint_str,
                    ttl=ttl,
                    protocol="icmp",
                )
                logger.info(
                    f"traceroute: got {result.result} from "
                    f"{result.responder or "???"} at ttl={ttl} for "
                    f"{endpoint_str} in {result.time_ms or "???"}ms"
                )

                responder = result.responder or ""
                asn = await get_asn(responder)

                labels = base_labels | {
                    "asn": asn,
                    "responder": responder,
                    "result": result.result,
                    "ttl": str(ttl),
                }
                packet_counter.labels(**labels).inc()

                if result.time_ms is not None:
                    del labels["result"]
                    time_s = result.time_ms / 1000.0
                    packet_latency.labels(**labels).observe(time_s)

                if result.result == "reply":
                    break

            elapsed = time.monotonic() - start_time
            sleep_time = max(0, TRACEROUTE_INTERVAL - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
    except asyncio.CancelledError:
        pass


_asn_cache: dict[str, str] = {}


async def get_asn(responder: str) -> str:
    """Get ASN for a responder IP, returns 'na' for non-global or on failure."""

    if not responder:
        return "na"
    try:
        ip_obj = ipaddress.ip_address(responder)
    except ValueError:
        return "na"
    if not ip_obj.is_global:
        return "na"
    asn = _asn_cache.get(responder)
    if asn is None:
        asn = await asyncio.to_thread(lookup_asn, responder)
        _asn_cache[responder] = asn
    return asn


def lookup_asn(ip: str) -> str:
    """Lookup ASN for an IP address using RIPE API. Returns 'na' on failure."""

    url = f"https://stat.ripe.net/data/network-info/data.json?resource={ip}"
    max_retries = 3
    retry_delay = 0.5

    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read())
                asns = data.get("data", {}).get("asns", [])
                if asns and len(asns) > 0:
                    asn = asns[0]
                    if asn.startswith("AS"):
                        return asn[2:]
                    return asn
                return "na"
        except urllib.error.HTTPError as e:
            if 500 <= e.code < 600 and attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            logger.debug(f"ASN lookup failed for {ip}: HTTP {e.code}")
            return "na"
        except Exception as e:
            logger.debug(f"ASN lookup failed for {ip}: {e}")
            return "na"
    return "na"
