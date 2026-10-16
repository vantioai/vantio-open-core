"""Observed destinations from sockets, argv tokens, and an operator map.

Raw command lines, userinfo, paths, and query strings are not retained.
"""

from __future__ import annotations

import errno
import ipaddress
import json
import os
import socket
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from optics_agent_inventory.catalog import catalog_in_scope, guess_provider

MAX_MAP_BYTES = 65536
SOCKET_STATES = {"01": "established", "0A": "listen"}


@dataclass(frozen=True)
class Observed:
    host: str
    port: int | None
    provider: str
    source: str


@dataclass(frozen=True)
class EndpointMap:
    by_ip: dict[str, tuple[str, int | None] | None]
    reason: str | None


def empty_map() -> EndpointMap:
    return EndpointMap({}, None)


def load_endpoint_map(path: Path | None, extra: tuple[str, ...]) -> EndpointMap:
    if path is None:
        return empty_map()
    try:
        fd = os.open(os.fspath(path), os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return EndpointMap({}, "endpoint_map_unreadable")
    except OSError as err:
        if err.errno == errno.ELOOP:
            return EndpointMap({}, "endpoint_map_unreadable")
        return EndpointMap({}, "endpoint_map_unreadable")
    try:
        blob = os.read(fd, MAX_MAP_BYTES + 1)
    except OSError:
        return EndpointMap({}, "endpoint_map_unreadable")
    finally:
        os.close(fd)
    if len(blob) > MAX_MAP_BYTES:
        return EndpointMap({}, "endpoint_map_unreadable")
    try:
        parsed = json.loads(blob.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return EndpointMap({}, "endpoint_map_unreadable")
    if not isinstance(parsed, dict) or parsed.get("schema") != "vantio.optics.endpoint_map.v1":
        return EndpointMap({}, "endpoint_map_unreadable")
    rows = parsed.get("map")
    if not isinstance(rows, list) or set(parsed) - {"schema", "map"}:
        return EndpointMap({}, "endpoint_map_unreadable")
    found: dict[str, tuple[str, int | None] | None] = {}
    for row in rows:
        if not isinstance(row, dict):
            return EndpointMap({}, "endpoint_map_unreadable")
        ip = normalize_ip(str(row.get("ip", "")))
        host = str(row.get("host", "")).lower()
        port = row.get("port")
        if ip is None or not catalog_in_scope(host, None, extra):
            return EndpointMap({}, "endpoint_map_unreadable")
        if port is not None and (not isinstance(port, int) or port < 0 or port > 65535):
            return EndpointMap({}, "endpoint_map_unreadable")
        if ip in found:
            found[ip] = None
            continue
        found[ip] = (host, port if isinstance(port, int) else None)
    return EndpointMap(found, None)


def argv_endpoints(tokens: list[str], extra: tuple[str, ...]) -> list[Observed]:
    found: list[Observed] = []
    for token in tokens:
        host, port = _token_host(token, extra)
        if host is None:
            continue
        provider = guess_provider(host, port)
        found.append(Observed(host, port, provider, "argv"))
    return found


def _token_host(token: str, extra: tuple[str, ...]) -> tuple[str | None, int | None]:
    if token.startswith("http://") or token.startswith("https://"):
        parsed = urlparse(token)
        host = (parsed.hostname or "").lower()
        if not host or not catalog_in_scope(host, parsed.port, extra):
            return None, None
        if parsed.port is not None:
            return host, parsed.port
        return host, 443 if token.startswith("https://") else 80
    host = token.lower().rstrip(".")
    if catalog_in_scope(host, None, extra) and " " not in host and "/" not in host:
        return host, None
    return None, None


def parse_proc_net(blob: str) -> list[tuple[str, str, int, str]]:
    """Return (state, ip, port, inode) for ipv4 or ipv6 tables."""
    rows: list[tuple[str, str, int, str]] = []
    for line in blob.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 10:
            continue
        local = _decode_endpoint(parts[1])
        remote = _decode_endpoint(parts[2])
        state = parts[3].upper()
        inode = parts[9]
        if local is None or remote is None or state not in SOCKET_STATES:
            continue
        if state == "0A":
            rows.append((state, local[0], local[1], inode))
        else:
            rows.append((state, remote[0], remote[1], inode))
    return rows


def _decode_endpoint(raw: str) -> tuple[str, int] | None:
    if ":" not in raw:
        return None
    ip_hex, port_hex = raw.split(":", 1)
    try:
        port = int(port_hex, 16)
    except ValueError:
        return None
    try:
        if len(ip_hex) == 8:
            packed = bytes.fromhex(ip_hex)[::-1]
            ip = socket.inet_ntop(socket.AF_INET, packed)
        elif len(ip_hex) == 32:
            words = []
            for index in range(0, 32, 8):
                word = bytes.fromhex(ip_hex[index : index + 8])[::-1]
                words.append(word)
            ip = socket.inet_ntop(socket.AF_INET6, b"".join(words))
        else:
            return None
    except (ValueError, OSError):
        return None
    normalized = normalize_ip(ip)
    if normalized is None:
        return None
    return normalized, port


def normalize_ip(value: str) -> str | None:
    try:
        return str(ipaddress.ip_address(value.strip("[]")))
    except ValueError:
        return None


def hosts_catalog_names(text: str, extra: tuple[str, ...]) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for line in text.splitlines():
        body = line.split("#", 1)[0].strip()
        if not body:
            continue
        parts = body.split()
        ip = normalize_ip(parts[0])
        if ip is None:
            continue
        for name in parts[1:]:
            if catalog_in_scope(name, None, extra):
                found.setdefault(ip, set()).add(name.lower().rstrip("."))
    return found


def resolve_socket(
    ip: str,
    port: int,
    state: str,
    hosts: dict[str, set[str]],
    endpoint_map: EndpointMap,
    extra: tuple[str, ...],
) -> Observed | None:
    if port == 11434 and _unspecified_or_loopback(ip):
        host = "127.0.0.1" if ip in {"0.0.0.0", "::"} else ip
        return Observed(host, 11434, "ollama", "socket")
    if state == "0A":
        return None
    mapped = endpoint_map.by_ip.get(ip, "absent")
    if mapped is None:
        return None
    host_names = hosts.get(ip, set())
    if len(host_names) > 1:
        return None
    map_host = None
    map_port = None
    if mapped != "absent":
        map_host, map_port = mapped
        if map_port is not None and map_port != port:
            map_host = None
    if len(host_names) == 1 and map_host and map_host != next(iter(host_names)):
        return None
    chosen = next(iter(host_names)) if len(host_names) == 1 else map_host
    if chosen is None or not catalog_in_scope(chosen, port, extra):
        return None
    return Observed(chosen, port, guess_provider(chosen, port), "socket")


def _unspecified_or_loopback(ip: str) -> bool:
    try:
        parsed = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return parsed.is_loopback or parsed.is_unspecified
