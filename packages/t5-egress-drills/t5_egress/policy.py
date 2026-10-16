"""Closed policy schema. A bad file is malformed and fail-closed."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from t5_egress.address import Addr, parse_address
from t5_egress.names import NameRejected, prepare_listed_name


class PolicyMalformed(Exception):
    pass


@dataclass(frozen=True)
class DnsPolicy:
    allowed_names: tuple[tuple[str, ...], ...]
    allowed_resolvers: tuple[Addr, ...]
    max_label_length: int
    entropy_min_length: int
    entropy_bits_max: float
    max_queries: int
    window_seconds: int


@dataclass(frozen=True)
class IcmpPolicy:
    allowed_destinations: tuple[Addr, ...]
    allowed_types: tuple[int, ...]


@dataclass(frozen=True)
class HttpPolicy:
    allowed_hosts: tuple[tuple[str, ...], ...]
    allowed_host_addrs: tuple[Addr, ...]
    max_query_length: int
    max_path_length: int
    max_header_bytes: int
    write_query_keys: tuple[str, ...]
    write_path_prefixes: tuple[str, ...]


@dataclass(frozen=True)
class LoopPolicy:
    allowed_ports: tuple[int, ...]
    privileged_ports: tuple[int, ...]


@dataclass(frozen=True)
class Policy:
    dns: DnsPolicy
    icmp: IcmpPolicy
    http_get: HttpPolicy
    loopback: LoopPolicy
    malformed: bool = False


_TOP = {"dns", "icmp", "http_get", "loopback"}
_DNS = {
    "allowed_names",
    "allowed_resolvers",
    "max_label_length",
    "entropy_min_length",
    "entropy_bits_max",
    "max_queries",
    "window_seconds",
}
_ICMP = {"allowed_destinations", "allowed_types"}
_HTTP = {
    "allowed_hosts",
    "max_query_length",
    "max_path_length",
    "max_header_bytes",
    "write_query_keys",
    "write_path_prefixes",
}
_LOOP = {"allowed_ports", "privileged_ports"}


def _int(value: object, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PolicyMalformed()
    if value < low or value > high:
        raise PolicyMalformed()
    return value


def _float(value: object, low: float, high: float) -> float:
    if isinstance(value, bool):
        raise PolicyMalformed()
    if isinstance(value, int):
        value = float(value)
    if not isinstance(value, float):
        raise PolicyMalformed()
    if not (low < value <= high):
        raise PolicyMalformed()
    return value


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        raise PolicyMalformed()
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise PolicyMalformed()
        if item == "":
            raise PolicyMalformed()
        out.append(item)
    return out


def _addrs(value: object) -> tuple[Addr, ...]:
    found: list[Addr] = []
    for item in _strings(value):
        if "/" in item:
            raise PolicyMalformed()
        parsed = parse_address(item)
        if parsed is None:
            raise PolicyMalformed()
        found.append(parsed)
    return tuple(found)


def _names(value: object) -> tuple[tuple[str, ...], ...]:
    found: list[tuple[str, ...]] = []
    for item in _strings(value):
        try:
            found.append(prepare_listed_name(item))
        except NameRejected as exc:
            raise PolicyMalformed() from exc
    return tuple(found)


def _require_list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise PolicyMalformed()
    return list(value)


def _ports(value: object) -> tuple[int, ...]:
    if not isinstance(value, list):
        raise PolicyMalformed()
    found: list[int] = []
    for item in value:
        found.append(_int(item, 0, 65535))
    return tuple(found)


def _section(data: object, keys: set[str]) -> dict[str, object]:
    if not isinstance(data, dict) or set(data) != keys:
        raise PolicyMalformed()
    return data


def _http(data: dict[str, object]) -> HttpPolicy:
    hosts = _strings(data["allowed_hosts"])
    names: list[tuple[str, ...]] = []
    addrs: list[Addr] = []
    for host in hosts:
        parsed = parse_address(host)
        if parsed is not None and ":" not in host and host.count(".") == 3:
            addrs.append(parsed)
            continue
        if parsed is not None and ":" in host:
            addrs.append(parsed)
            continue
        try:
            names.append(prepare_listed_name(host))
        except NameRejected as exc:
            raise PolicyMalformed() from exc
    keys = tuple(item.strip(" \t").lower() for item in _strings(data["write_query_keys"]))
    for key in keys:
        if not key or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for ch in key):
            raise PolicyMalformed()
    prefixes: list[str] = []
    for prefix in _strings(data["write_path_prefixes"]):
        folded = "".join(ch.lower() if "A" <= ch <= "Z" else ch for ch in prefix)
        if not folded.startswith("/") or any(ord(ch) > 127 for ch in folded):
            raise PolicyMalformed()
        if "%" in folded or ".." in folded or "//" in folded or "\\" in folded or ";" in folded:
            raise PolicyMalformed()
        prefixes.append(folded)
    return HttpPolicy(
        allowed_hosts=tuple(names),
        allowed_host_addrs=tuple(addrs),
        max_query_length=_int(data["max_query_length"], 1, 128),
        max_path_length=_int(data["max_path_length"], 1, 256),
        max_header_bytes=_int(data["max_header_bytes"], 0, 1024),
        write_query_keys=keys,
        write_path_prefixes=tuple(prefixes),
    )


def load_policy(data: object) -> Policy:
    try:
        if not isinstance(data, dict) or set(data) != _TOP:
            raise PolicyMalformed()
        dns = _section(data["dns"], _DNS)
        icmp = _section(data["icmp"], _ICMP)
        http = _section(data["http_get"], _HTTP)
        loop = _section(data["loopback"], _LOOP)
        return Policy(
            dns=DnsPolicy(
                allowed_names=_names(dns["allowed_names"]),
                allowed_resolvers=_addrs(dns["allowed_resolvers"]),
                max_label_length=_int(dns["max_label_length"], 1, 63),
                entropy_min_length=_int(dns["entropy_min_length"], 1, 63),
                entropy_bits_max=_float(dns["entropy_bits_max"], 0.0, 8.0),
                max_queries=_int(dns["max_queries"], 1, 64),
                window_seconds=_int(dns["window_seconds"], 1, 3600),
            ),
            icmp=IcmpPolicy(
                allowed_destinations=_addrs(icmp["allowed_destinations"]),
                allowed_types=tuple(_int(item, 0, 255) for item in _require_list(icmp["allowed_types"])),
            ),
            http_get=_http(http),
            loopback=LoopPolicy(
                allowed_ports=_ports(loop["allowed_ports"]),
                privileged_ports=_ports(loop["privileged_ports"]),
            ),
            malformed=False,
        )
    except (PolicyMalformed, TypeError, ValueError):
        return Policy(
            dns=DnsPolicy((), (), 1, 1, 1.0, 1, 1),
            icmp=IcmpPolicy((), ()),
            http_get=HttpPolicy((), (), 1, 1, 0, (), ()),
            loopback=LoopPolicy((), ()),
            malformed=True,
        )


def load_policy_file(path: Path) -> Policy:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return load_policy(None)
    return load_policy(raw)
