"""Strict address parse and loopback / link-local class tests.

Allow-list equality collapses IPv4-mapped IPv6 only.
Class tests also collapse IPv4-compatible IPv6, except the all-zero address.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Addr:
    kind: str
    v4: int | None
    words: tuple[int, ...] | None
    compatible: bool


def parse_ipv4(text: str) -> int | None:
    parts = text.split(".")
    if len(parts) != 4:
        return None
    value = 0
    for part in parts:
        if not part.isdigit() or (len(part) > 1 and part.startswith("0")):
            return None
        octet = int(part)
        if octet > 255:
            return None
        value = (value << 8) | octet
    return value


def _hex_group(text: str) -> int | None:
    if not text or len(text) > 4 or any(ch not in "0123456789abcdef" for ch in text):
        return None
    return int(text, 16)


def parse_ipv6(text: str) -> tuple[int, ...] | None:
    raw = text.lower()
    if "%" in raw or not raw:
        return None
    if raw.count("::") > 1:
        return None
    v4_tail: int | None = None
    if "." in raw:
        head, _, tail = raw.rpartition(":")
        if head == raw:
            return None
        v4_tail = parse_ipv4(tail)
        if v4_tail is None:
            return None
        raw = head + ":v4"
    left, sep, right = raw.partition("::")
    if sep and right.count("::"):
        return None

    def side(piece: str) -> list[int] | None:
        if piece == "":
            return []
        groups = piece.split(":")
        out: list[int] = []
        for index, group in enumerate(groups):
            if group == "v4":
                if index != len(groups) - 1 or v4_tail is None:
                    return None
                out.append((v4_tail >> 16) & 0xFFFF)
                out.append(v4_tail & 0xFFFF)
                continue
            parsed = _hex_group(group)
            if parsed is None:
                return None
            out.append(parsed)
        return out

    if not sep:
        groups = side(left)
        if groups is None or len(groups) != 8:
            return None
        return tuple(groups)
    lgroups = side(left)
    rgroups = side(right)
    if lgroups is None or rgroups is None:
        return None
    if len(lgroups) + len(rgroups) > 7:
        return None
    zeros = [0] * (8 - len(lgroups) - len(rgroups))
    return tuple(lgroups + zeros + rgroups)


def parse_address(value: object) -> Addr | None:
    if not isinstance(value, str):
        return None
    text = value.strip(" \t\r\n\f\v")
    if text != value or any(ord(ch) > 127 for ch in text):
        return None
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    v4 = parse_ipv4(text)
    if v4 is not None:
        return Addr("v4", v4, None, False)
    words = parse_ipv6(text)
    if words is None:
        return None
    mapped = words[0] == 0 and words[1] == 0 and words[2] == 0 and words[3] == 0 and words[4] == 0 and words[5] == 0xFFFF
    if mapped:
        embedded = ((words[6] << 16) | words[7]) & 0xFFFFFFFF
        return Addr("v4", embedded, None, False)
    compatible = (
        words[0] == 0
        and words[1] == 0
        and words[2] == 0
        and words[3] == 0
        and words[4] == 0
        and words[5] == 0
        and not (words[6] == 0 and words[7] == 0)
    )
    return Addr("v6", None, words, compatible)


def _v4_class(v4: int) -> str:
    first = (v4 >> 24) & 0xFF
    if first in (0, 127):
        return "loopback"
    if (v4 >> 16) == 0xA9FE:
        return "link_local"
    return "external"


def address_class(addr: Addr) -> str:
    if addr.kind == "v4" and addr.v4 is not None:
        return _v4_class(addr.v4)
    words = addr.words or ()
    if len(words) != 8:
        return "external"
    if all(word == 0 for word in words):
        return "loopback"
    if addr.compatible and addr.words is not None:
        embedded = ((words[6] << 16) | words[7]) & 0xFFFFFFFF
        return _v4_class(embedded)
    if words == (0, 0, 0, 0, 0, 0, 0, 1):
        return "loopback"
    if (words[0] & 0xFFC0) == 0xFE80:
        return "link_local"
    return "external"


def same_allow_address(left: Addr, right: Addr) -> bool:
    if left.kind != right.kind:
        return False
    if left.kind == "v4":
        return left.v4 == right.v4
    return left.words == right.words


def listed_address(candidate: Addr, entries: tuple[Addr, ...]) -> bool:
    return any(same_allow_address(candidate, entry) for entry in entries)
