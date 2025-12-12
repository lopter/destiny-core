import click
import functools
import ipaddress
import json
import logging
import prometheus_client
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.request

__all__ = ["exporter"]

logger = logging.getLogger(__name__)

gauge_latency_avg = prometheus_client.Gauge(
    "mtr_hop_latency_avg_ms",
    "Average latency for a hop in milliseconds",
    ["target", "hop", "ip", "asn", "source"],
)
gauge_latency_best = prometheus_client.Gauge(
    "mtr_hop_latency_best_ms",
    "Best latency for a hop in milliseconds",
    ["target", "hop", "ip", "asn", "source"],
)
gauge_latency_worst = prometheus_client.Gauge(
    "mtr_hop_latency_worst_ms",
    "Worst latency for a hop in milliseconds",
    ["target", "hop", "ip", "asn", "source"],
)
gauge_latency_stdev = prometheus_client.Gauge(
    "mtr_hop_latency_stdev_ms",
    "Standard deviation of latency for a hop in milliseconds",
    ["target", "hop", "ip", "asn", "source"],
)
gauge_loss_ratio = prometheus_client.Gauge(
    "mtr_hop_loss_ratio",
    "Packet loss ratio for a hop",
    ["target", "hop", "ip", "asn", "source"],
)
counter_mtr_runs = prometheus_client.Counter(
    "mtr_runs_total",
    "Total number of mtr command executions",
    ["target", "exit_code", "source"],
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
@click.option(
    "-i",
    "--interval",
    type=click.FloatRange(min=0.0, min_open=True),
    default=60.0,
    show_default=True,
    help=(
        "Interval between mtr runs in seconds "
        "(mtr execution time is subtracted from this)"
    ),
)
@click.pass_context
def exporter(
    ctx: click.Context,
    port: int,
    listen_addr: str,
    endpoint: list[ipaddress.IPv4Address | ipaddress.IPv6Address],
    source: list[ipaddress.IPv4Address | ipaddress.IPv6Address],
    interval: float,
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
    monitor_threads: list[threading.Thread] = []
    for dest_ip in endpoint:
        source_ip = ipv4_source if is_ipv4(dest_ip) else ipv6_source
        args = (dest_ip, source_ip, stop_event, interval)
        thread = threading.Thread(target=monitor, args=args, daemon=False)
        thread.start()
        monitor_threads.append(thread)

    shutdown_signals = (signal.SIGINT, signal.SIGTERM, signal.SIGQUIT)
    signal_received = threading.Event()

    def signal_handler(signum: int, frame: object) -> None:
        signal_name = signal.Signals(signum).name
        logger.info(f"Received {signal_name}, shutting down…")
        signal_received.set()

    for sig in shutdown_signals:
        _ = signal.signal(sig, signal_handler)

    _ = signal_received.wait()
    wsgi_server.shutdown()
    stop_event.set()
    server_thread.join()
    for thread in monitor_threads:
        thread.join()


# Could use functools.Placeholder in Python ≥ 3.14
def is_ipv4(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return isinstance(addr, ipaddress.IPv4Address)


def is_ipv6(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return isinstance(addr, ipaddress.IPv6Address)


def monitor(
    endpoint: ipaddress.IPv4Address | ipaddress.IPv6Address,
    source: ipaddress.IPv4Address | ipaddress.IPv6Address,
    stop_event: threading.Event,
    interval: float,
) -> None:
    """Monitor an endpoint and export metrics."""
    ip_version_flag = "-4" if is_ipv4(endpoint) else "-6"

    target = str(endpoint)
    source_ip = str(source)

    while not stop_event.is_set():
        start_time = time.monotonic()

        cmd = [
            "mtr",
            "--no-dns",
            "--json",
            "--report-cycles",
            "5",
            ip_version_flag,
            target,
        ]
        logger.info(f"Running mtr for {target}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            exit_code = result.returncode
            counter_mtr_runs.labels(
                target=target, exit_code=str(exit_code), source=source_ip
            ).inc()
            logger.info(f"mtr finished for {target} with exit code {exit_code}")
            if exit_code != 0:
                logger.warning(
                    f"mtr command failed for {target} with exit code {exit_code}"
                )
                elapsed = time.monotonic() - start_time
                sleep_time = max(0, interval - elapsed)
                if sleep_time > 0 and stop_event.wait(timeout=sleep_time):
                    break
                continue

            mtr_data = json.loads(result.stdout)
            hubs = mtr_data.get("report", {}).get("hubs", [])
            for hub in hubs:
                host_ip = hub.get("host", "")
                if host_ip == "???":
                    continue
                hop_num = str(hub.get("count", "na"))
                asn = "na"
                try:
                    ip_obj = ipaddress.ip_address(host_ip)
                    if ip_obj.is_global:
                        asn = lookup_asn(host_ip)
                except ValueError:
                    logger.warning(f"could not parse ip from mtr: {host_ip}")

                labels = {
                    "target": target,
                    "hop": hop_num,
                    "ip": host_ip,
                    "asn": asn,
                    "source": source_ip,
                }
                gauge_latency_avg.labels(**labels).set(hub.get("Avg", 0.0))
                gauge_latency_best.labels(**labels).set(hub.get("Best", 0.0))
                gauge_latency_worst.labels(**labels).set(hub.get("Wrst", 0.0))
                gauge_latency_stdev.labels(**labels).set(hub.get("StDev", 0.0))
                gauge_loss_ratio.labels(**labels).set(hub.get("Loss%", 0.0) / 100)

        except subprocess.TimeoutExpired:
            logger.warning(f"mtr command timed out for {target}")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse mtr output for {target}: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error monitoring {target}: {e}")

        elapsed = time.monotonic() - start_time
        sleep_time = max(0, interval - elapsed)

        if sleep_time > 0:
            stop_event.wait(timeout=sleep_time)


@functools.lru_cache
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
