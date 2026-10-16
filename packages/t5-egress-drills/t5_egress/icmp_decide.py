"""ICMP allow-list. ICMPv6 is denied in this track."""

from __future__ import annotations

import struct

from t5_egress.address import address_class, listed_address, parse_address
from t5_egress.decision import Decision, allow, deny_classified, deny_eval, gate_call, not_in_scope
from t5_egress.policy import Policy

_EXT = {0, 43, 44, 51, 60}
_MAX_EXT = 4


def _parse(packet: bytes) -> Decision | tuple[str, int, str]:
    if len(packet) < 1:
        return deny_eval("icmp_header_unreadable")
    version = packet[0] >> 4
    if version == 4:
        if len(packet) < 20:
            return deny_eval("icmp_header_unreadable")
        ihl = packet[0] & 0x0F
        if ihl < 5:
            return deny_eval("icmp_header_unreadable")
        header_len = ihl * 4
        if len(packet) < header_len + 1 or packet[9] != 1:
            if len(packet) >= 20 and packet[9] != 1:
                return not_in_scope("case_not_applicable")
            return deny_eval("icmp_header_unreadable")
        dest = ".".join(str(byte) for byte in packet[16:20])
        return ("v4", packet[header_len], dest)
    if version == 6:
        if len(packet) < 40:
            return deny_eval("icmp_header_unreadable")
        next_header = packet[6]
        offset = 40
        seen = 0
        while next_header in _EXT:
            if seen >= _MAX_EXT:
                return deny_eval("icmp_header_unreadable")
            if next_header == 44:
                if offset + 8 > len(packet):
                    return deny_eval("icmp_header_unreadable")
                next_header = packet[offset]
                offset += 8
            else:
                if offset + 2 > len(packet):
                    return deny_eval("icmp_header_unreadable")
                hdrlen = packet[offset + 1]
                size = (hdrlen + 2) * 4 if next_header == 51 else (hdrlen + 1) * 8
                if offset + size > len(packet):
                    return deny_eval("icmp_header_unreadable")
                next_header = packet[offset]
                offset += size
            seen += 1
        if next_header != 58 or offset >= len(packet):
            if next_header != 58:
                return not_in_scope("case_not_applicable")
            return deny_eval("icmp_header_unreadable")
        dest = ":".join(f"{word:x}" for word in struct.unpack_from(">8H", packet, 24))
        return ("v6", packet[offset], dest)
    return deny_eval("icmp_header_unreadable")


def decide_icmp(packet: bytes, policy: Policy, mode: object, enrolled: object) -> Decision:
    early = gate_call(enrolled, mode)
    if early is not None:
        return early
    assert isinstance(mode, str)
    if policy.malformed:
        return deny_eval("policy_malformed")
    parsed = _parse(packet)
    if isinstance(parsed, Decision):
        return parsed
    family, icmp_type, dest = parsed
    if family == "v6":
        return deny_classified("icmp_type_not_allowed", mode)
    addr = parse_address(dest)
    if addr is None:
        return deny_eval("address_not_canonical")
    if address_class(addr) == "link_local":
        return deny_classified("link_local_not_allowed", mode)
    if not listed_address(addr, policy.icmp.allowed_destinations):
        return deny_classified("icmp_destination_not_allowed", mode)
    if icmp_type not in policy.icmp.allowed_types:
        return deny_classified("icmp_type_not_allowed", mode)
    return allow()
