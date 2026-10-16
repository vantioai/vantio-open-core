"""Bounded DNS walk. The step and pointer caps match the skb budget."""

from __future__ import annotations

import struct
from dataclasses import dataclass

MAX_STEPS = 128
MAX_HOPS = 4
MAX_NAME = 255
_LABEL_OK = set(b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")


class WireFail(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason


@dataclass
class Budget:
    steps: int = 0

    def take(self) -> None:
        self.steps += 1
        if self.steps > MAX_STEPS:
            raise WireFail("dns_parse_budget")


@dataclass(frozen=True)
class Name:
    labels: tuple[bytes, ...]
    end: int


@dataclass(frozen=True)
class Question:
    labels: tuple[bytes, ...]
    end: int


@dataclass(frozen=True)
class Record:
    owner: tuple[bytes, ...]
    rtype: int
    rdata_name: tuple[bytes, ...] | None
    rdata_addr: str | None


@dataclass(frozen=True)
class ResponseView:
    authority: tuple[Record, ...]
    additional: tuple[Record, ...]


def _read_name(packet: bytes, offset: int, budget: Budget) -> Name:
    labels: list[bytes] = []
    hops = 0
    jumped = False
    end = offset
    cursor = offset
    octets = 0
    while True:
        budget.take()
        if cursor < 0 or cursor >= len(packet):
            raise WireFail("dns_unparsable")
        length = packet[cursor]
        if length == 0:
            if not jumped:
                end = cursor + 1
            if octets + 1 > MAX_NAME:
                raise WireFail("dns_unparsable")
            return Name(tuple(labels), end)
        if length & 0xC0 == 0xC0:
            if hops >= MAX_HOPS:
                raise WireFail("dns_parse_budget")
            if cursor + 1 >= len(packet):
                raise WireFail("dns_unparsable")
            pointer = ((length & 0x3F) << 8) | packet[cursor + 1]
            if pointer >= cursor or pointer >= len(packet):
                raise WireFail("dns_unparsable")
            if not jumped:
                end = cursor + 2
            jumped = True
            cursor = pointer
            hops += 1
            continue
        if length & 0xC0 or length > 63:
            raise WireFail("dns_unparsable")
        start = cursor + 1
        stop = start + length
        if stop > len(packet):
            raise WireFail("dns_unparsable")
        label = packet[start:stop]
        octets += length + 1
        if octets + 1 > MAX_NAME:
            raise WireFail("dns_unparsable")
        labels.append(label)
        cursor = stop


def parse_question(packet: bytes) -> Question:
    if len(packet) < 12:
        raise WireFail("dns_unparsable")
    qd, _an, _ns, _ar = struct.unpack_from(">HHHH", packet, 4)
    if qd != 1:
        raise WireFail("dns_qdcount")
    budget = Budget()
    name = _read_name(packet, 12, budget)
    if name.end + 4 > len(packet):
        raise WireFail("dns_unparsable")
    return Question(name.labels, name.end + 4)


def _addr_text(rtype: int, data: bytes) -> str | None:
    if rtype == 1 and len(data) == 4:
        return ".".join(str(byte) for byte in data)
    if rtype == 28 and len(data) == 16:
        words = struct.unpack(">8H", data)
        return ":".join(f"{word:x}" for word in words)
    return None


def _read_records(packet: bytes, cursor: int, count: int, budget: Budget) -> tuple[list[Record], int]:
    found: list[Record] = []
    for _ in range(count):
        owner = _read_name(packet, cursor, budget)
        if owner.end + 10 > len(packet):
            raise WireFail("dns_unparsable")
        rtype, _rclass, _ttl, rdlength = struct.unpack_from(">HHIH", packet, owner.end)
        start = owner.end + 10
        stop = start + rdlength
        if stop > len(packet):
            raise WireFail("dns_unparsable")
        rdata_name = None
        if rtype == 2:
            rdata_name = _read_name(packet, start, budget).labels
        found.append(Record(owner.labels, rtype, rdata_name, _addr_text(rtype, packet[start:stop])))
        cursor = stop
    return found, cursor


def parse_response(packet: bytes) -> ResponseView:
    if len(packet) < 12:
        raise WireFail("dns_unparsable")
    qd, an, ns, ar = struct.unpack_from(">HHHH", packet, 4)
    budget = Budget()
    cursor = 12
    for _ in range(qd):
        name = _read_name(packet, cursor, budget)
        if name.end + 4 > len(packet):
            raise WireFail("dns_unparsable")
        cursor = name.end + 4
    _answers, cursor = _read_records(packet, cursor, an, budget)
    authority, cursor = _read_records(packet, cursor, ns, budget)
    additional, _cursor = _read_records(packet, cursor, ar, budget)
    return ResponseView(tuple(authority), tuple(additional))
