"""Userspace model of t5_egress.bpf.c.

The model does not import the Shannon helper. A long left-hand name sets
entropy_deferred and is still allowed when every other kernel check passes.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from t5_egress.address import address_class, listed_address, parse_address

from t5_kernel.reasons import (
    CLASSIFIED,
    EVAL,
    MAX_HOPS,
    MAX_LABELS,
    MAX_PARSE_STEPS,
    PASS,
    SCOPE,
)


@dataclass(frozen=True)
class KernelDecision:
    reason: str
    kind: str
    transmit: bool
    entropy_deferred: bool
    action: str
    label: str = "Lab-only"

    def as_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "reason": self.reason,
            "kind": self.kind,
            "transmit": self.transmit,
            "entropy_deferred": self.entropy_deferred,
            "label": self.label,
        }


@dataclass
class FixedWindow:
    """Per-cgroup fixed window. Not the userspace sliding list."""

    start_ns: int = 0
    count: int = 0

    def hit(self, now_ns: int, window_ns: int, cap: int) -> str:
        if self.start_ns != 0 and now_ns < self.start_ns:
            return "failure"
        if self.start_ns == 0 or now_ns - self.start_ns >= window_ns:
            self.start_ns = now_ns
            self.count = 0
        if self.count >= cap:
            return "over"
        self.count += 1
        return "ok"


@dataclass(frozen=True)
class KernelMaps:
    enforce: bool
    max_label: int
    max_queries: int
    entropy_min_length: int
    entropy_userspace: int
    window_ns: int
    names: tuple[str, ...]
    resolvers: tuple[str, ...]
    icmp_destinations: tuple[str, ...]
    ports: tuple[int, ...]


def _finish(reason: str, kind: str, mode: str, entropy_deferred: bool = False) -> KernelDecision:
    if kind == PASS:
        action = "ALLOW"
        transmit = True
    elif kind == CLASSIFIED and mode == "observe":
        action = "OBSERVE_WOULD_DENY"
        transmit = True
    elif kind == CLASSIFIED:
        action = "DENY"
        transmit = False
    elif kind == SCOPE:
        action = "NOT_IN_SCOPE"
        transmit = False
    elif kind == EVAL:
        action = "DENY"
        transmit = False
    else:
        action = "DENY"
        transmit = False
        kind = EVAL
        reason = "policy_malformed"
    return KernelDecision(reason, kind, transmit, entropy_deferred, action)


def _cfg_ok(maps: KernelMaps) -> bool:
    if maps.entropy_userspace != 1:
        return False
    if not 1 <= maps.max_label <= 63:
        return False
    if not 1 <= maps.max_queries <= 64:
        return False
    if maps.window_ns <= 0:
        return False
    if len(maps.names) > 4 or len(maps.resolvers) > 4 or len(maps.icmp_destinations) > 4 or len(maps.ports) > 8:
        return False
    return True


def _as_addrs(entries: tuple[str, ...]) -> tuple[object, ...]:
    parsed = []
    for entry in entries:
        item = parse_address(entry)
        if item is not None:
            parsed.append(item)
    return tuple(parsed)


def _on_list(candidate: object, entries: tuple[str, ...]) -> bool:
    return listed_address(candidate, _as_addrs(entries))


def _fold_name(name: str) -> str:
    return "".join(ch.lower() if "A" <= ch <= "Z" else ch for ch in name)


def _ldh(ch: str) -> bool:
    return ("a" <= ch <= "z") or ("A" <= ch <= "Z") or ("0" <= ch <= "9") or ch in "-_"


def _parse_name(packet: bytes, offset: int, max_label: int) -> tuple[str, str] | str:
    """Return (folded_name, '') or a reason token."""
    cursor = offset
    hops = 0
    steps = 0
    labels: list[str] = []
    while steps < MAX_PARSE_STEPS:
        steps += 1
        if cursor < 0 or cursor >= len(packet):
            return "dns_unparsable"
        length = packet[cursor]
        if length == 0:
            return (".".join(labels), "")
        if length & 0xC0 == 0xC0:
            if hops >= MAX_HOPS:
                return "dns_parse_budget"
            if cursor + 1 >= len(packet):
                return "dns_unparsable"
            pointer = ((length & 0x3F) << 8) | packet[cursor + 1]
            if pointer >= cursor:
                return "dns_unparsable"
            cursor = pointer
            hops += 1
            continue
        if length & 0xC0 or length > 63:
            return "dns_unparsable"
        if len(labels) >= MAX_LABELS:
            return "dns_parse_budget"
        if length > max_label:
            return "dns_label_too_long"
        start = cursor + 1
        stop = start + length
        if stop > len(packet):
            return "dns_unparsable"
        raw = packet[start:stop]
        text = []
        for byte in raw:
            ch = chr(byte)
            if not _ldh(ch):
                return "dns_label_not_ldh"
            text.append(ch.lower() if "A" <= ch <= "Z" else ch)
        labels.append("".join(text))
        cursor = stop
    return "dns_parse_budget"


def _name_verdict(name: str, maps: KernelMaps) -> tuple[str, bool]:
    best = 0
    matched = False
    folded_slots = tuple(_fold_name(item) for item in maps.names)
    for slot in folded_slots:
        if not slot or len(slot) > 63 or len(slot) > len(name):
            continue
        if slot == name:
            matched = True
            best = len(slot)
            continue
        if not name.endswith("." + slot):
            continue
        if "." not in slot:
            continue
        if len(slot) >= best:
            matched = True
            best = len(slot)
    if not matched:
        return "dns_name_not_allowed", False
    entropy = False
    if len(name) > best:
        left = name[: len(name) - best - 1].replace(".", "")
        if len(left) > maps.max_label:
            return "dns_label_too_long", False
        if maps.entropy_min_length > 0 and len(left) >= maps.entropy_min_length:
            entropy = True
    return "policy_permits", entropy


def _kind_for(reason: str) -> str:
    if reason == "policy_permits":
        return PASS
    if reason in {"dns_name_not_allowed", "dns_label_too_long", "resolver_not_allowed", "dns_query_volume", "link_local_not_allowed", "icmp_destination_not_allowed", "icmp_type_not_allowed", "loopback_port_not_allowed"}:
        return CLASSIFIED
    if reason == "case_not_applicable":
        return SCOPE
    return EVAL


def _read_ipv4(packet: bytes) -> tuple[int, int, str, int] | str:
    """Return (protocol, ihl, dest, dest_port_or_-1) or a reason."""
    if len(packet) < 20:
        return "icmp_header_unreadable"
    version = packet[0] >> 4
    if version == 6:
        if len(packet) < 40:
            return "icmp_header_unreadable"
        next_header = packet[6]
        if next_header == 58:
            return "icmp_v6"
        return "icmp_header_unreadable"
    if version != 4:
        return "address_not_canonical"
    ihl = packet[0] & 0x0F
    if ihl != 5:
        return "icmp_header_unreadable"
    protocol = packet[9]
    dest = ".".join(str(byte) for byte in packet[16:20])
    dport = -1
    if protocol in (6, 17):
        if len(packet) < 24:
            return "loopback_header_unreadable"
        dport = struct.unpack_from(">H", packet, 22)[0]
    return protocol, ihl, dest, dport


def kernel_packet(packet: bytes, maps: KernelMaps, mode: str, window: FixedWindow | None, now_ns: int) -> KernelDecision:
    if mode not in ("observe", "enforce"):
        return _finish("policy_malformed", EVAL, "enforce")
    if not _cfg_ok(maps):
        return _finish("policy_malformed", EVAL, mode)
    parsed = _read_ipv4(packet)
    if parsed == "icmp_v6":
        return _finish("icmp_type_not_allowed", CLASSIFIED, mode)
    if isinstance(parsed, str):
        return _finish(parsed, _kind_for(parsed), mode)
    protocol, _ihl, dest, dport = parsed
    if protocol == 1:
        return _icmp(packet, dest, maps, mode)
    if protocol not in (6, 17):
        return _finish("case_not_applicable", SCOPE, mode)
    if dport < 0:
        return _finish("loopback_header_unreadable", EVAL, mode)
    if protocol == 6 and dport == 53:
        return _finish("dns_transport_not_visible", EVAL, mode)
    if protocol == 17 and dport == 53:
        return _dns(packet, dest, maps, mode, window, now_ns)
    if protocol == 6 and dport == 80:
        return _finish("get_method_not_visible", EVAL, mode)
    return _loopback_packet(dest, dport, maps, mode)


def _dns(packet: bytes, dest: str, maps: KernelMaps, mode: str, window: FixedWindow | None, now_ns: int) -> KernelDecision:
    if len(packet) < 28 + 12:
        return _finish("dns_unparsable", EVAL, mode)
    qdcount = struct.unpack_from(">H", packet, 28 + 4)[0]
    if qdcount != 1:
        return _finish("dns_qdcount", EVAL, mode)
    parsed = _parse_name(packet, 28 + 12, maps.max_label)
    if isinstance(parsed, str):
        return _finish(parsed, _kind_for(parsed), mode)
    name, _empty = parsed
    if window is None:
        return _finish("dns_query_volume", EVAL, mode)
    status = window.hit(now_ns, maps.window_ns, maps.max_queries)
    if status == "failure":
        return _finish("dns_query_volume", EVAL, mode)
    dest_addr = parse_address(dest)
    if dest_addr is None:
        return _finish("address_not_canonical", EVAL, mode)
    if address_class(dest_addr) == "link_local":
        return _finish("link_local_not_allowed", CLASSIFIED, mode)
    if not _on_list(dest_addr, maps.resolvers):
        return _finish("resolver_not_allowed", CLASSIFIED, mode)
    reason, entropy = _name_verdict(name, maps)
    if reason != "policy_permits":
        return _finish(reason, _kind_for(reason), mode)
    if status == "over":
        return _finish("dns_query_volume", CLASSIFIED, mode, entropy)
    return _finish("policy_permits", PASS, mode, entropy)


def _icmp(packet: bytes, dest: str, maps: KernelMaps, mode: str) -> KernelDecision:
    if len(packet) < 21:
        return _finish("icmp_header_unreadable", EVAL, mode)
    kind = packet[20]
    dest_addr = parse_address(dest)
    if dest_addr is None:
        return _finish("address_not_canonical", EVAL, mode)
    if address_class(dest_addr) == "link_local":
        return _finish("link_local_not_allowed", CLASSIFIED, mode)
    if kind not in (0, 8):
        return _finish("icmp_type_not_allowed", CLASSIFIED, mode)
    if not _on_list(dest_addr, maps.icmp_destinations):
        return _finish("icmp_destination_not_allowed", CLASSIFIED, mode)
    return _finish("policy_permits", PASS, mode)


def _loopback_packet(dest: str, dport: int, maps: KernelMaps, mode: str) -> KernelDecision:
    dest_addr = parse_address(dest)
    if dest_addr is None:
        return _finish("address_not_canonical", EVAL, mode)
    kind = address_class(dest_addr)
    if kind == "link_local":
        return _finish("link_local_not_allowed", CLASSIFIED, mode)
    if kind != "loopback":
        return _finish("case_not_applicable", SCOPE, mode)
    if dport in maps.ports:
        return _finish("policy_permits", PASS, mode)
    return _finish("loopback_port_not_allowed", CLASSIFIED, mode)


def kernel_connect(destination: str, port: int, protocol: str, maps: KernelMaps, mode: str) -> KernelDecision:
    if mode not in ("observe", "enforce"):
        return _finish("policy_malformed", EVAL, "enforce")
    if not _cfg_ok(maps):
        return _finish("policy_malformed", EVAL, mode)
    if protocol not in ("tcp", "udp"):
        return _finish("loopback_header_unreadable", EVAL, mode)
    if isinstance(port, bool) or not isinstance(port, int) or port < 0 or port > 65535:
        return _finish("loopback_header_unreadable", EVAL, mode)
    parsed = parse_address(destination)
    if parsed is None:
        return _finish("address_not_canonical", EVAL, mode)
    kind = address_class(parsed)
    if port == 53 and _on_list(parsed, maps.resolvers):
        return _finish("policy_permits", PASS, mode)
    if kind == "link_local":
        return _finish("link_local_not_allowed", CLASSIFIED, mode)
    if kind == "loopback":
        if port in maps.ports:
            return _finish("policy_permits", PASS, mode)
        return _finish("loopback_port_not_allowed", CLASSIFIED, mode)
    if port == 53:
        return _finish("resolver_not_allowed", CLASSIFIED, mode)
    return _finish("case_not_applicable", SCOPE, mode)
