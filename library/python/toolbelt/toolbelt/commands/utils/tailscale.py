from __future__ import annotations

import ipaddress
import json
import logging
import subprocess

from typing import Any, Callable, NamedTuple


class Peer(NamedTuple):
    hostname: str
    dns_name: str
    ipv4: ipaddress.IPv4Address

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Peer:
        assert isinstance(data, dict)
        tailscale_ips = data.get("TailscaleIPs")
        assert isinstance(tailscale_ips, list)
        assert len(tailscale_ips) >= 1
        hostname = data.get("HostName")
        assert isinstance(hostname, str)
        dns_name = data.get("DNSName")
        assert isinstance(dns_name, str)
        return cls(
            hostname,
            dns_name,
            ipv4=ipaddress.IPv4Address(tailscale_ips[0]),
        )


def peers(filter_fn: Callable[[Peer], bool]) -> list[Peer]:
    logging.info("Loading peers from `tailscale status`.")
    output = subprocess.run(
        ["tailscale", "status", "--json"],
        check=True,
        capture_output=True,  # we could pipe it in instead
        encoding="utf-8",
    ).stdout.strip()
    status = json.loads(output)
    assert isinstance(status, dict), "json output from tailscale is not a dict"
    peers = status.get("Peer")
    assert isinstance(peers, dict), "peers not found in tailscale status output"
    peers = (Peer.from_json(entry) for entry in peers.values())
    return [each for each in peers if filter_fn(each)]
