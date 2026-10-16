"""Synthetic packets for drills and tests. Not customer traffic."""

from __future__ import annotations

import socket
import struct


def encode_name(name: str) -> bytes:
    body = b""
    for label in name.rstrip(".").split("."):
        raw = label.encode("ascii")
        body += bytes([len(raw)]) + raw
    return body + b"\x00"


def dns_query(name: str, qid: int = 0x1505) -> bytes:
    header = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0)
    return header + encode_name(name) + struct.pack(">HH", 1, 1)


def dns_ns_response(owner: str, ns_host: str, glue: str | None, qid: int = 0x1505) -> bytes:
    question = encode_name(owner) + struct.pack(">HH", 1, 1)
    rdata = encode_name(ns_host)
    authority = encode_name(owner) + struct.pack(">HHIH", 2, 1, 60, len(rdata)) + rdata
    additional = b""
    extra = 0
    if glue is not None:
        glue_bytes = socket.inet_aton(glue)
        additional = encode_name(ns_host) + struct.pack(">HHIH", 1, 1, 60, 4) + glue_bytes
        extra = 1
    header = struct.pack(">HHHHHH", qid, 0x8400, 1, 0, 1, extra)
    return header + question + authority + additional


def checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\x00"
    total = 0
    for index in range(0, len(data), 2):
        total += (data[index] << 8) + data[index + 1]
        total = (total & 0xFFFF) + (total >> 16)
    return (~total) & 0xFFFF


def icmp_message(kind: int, ident: int = 1, seq: int = 1) -> bytes:
    payload = b"t5"
    bare = struct.pack(">BBHHH", kind, 0, 0, ident, seq) + payload
    return struct.pack(">BBHHH", kind, 0, checksum(bare), ident, seq) + payload


def ipv4_icmp(src: str, dst: str, message: bytes) -> bytes:
    total = 20 + len(message)
    base = struct.pack(
        ">BBHHHBBH4s4s",
        0x45,
        0,
        total,
        0,
        0,
        64,
        1,
        0,
        socket.inet_aton(src),
        socket.inet_aton(dst),
    )
    summed = struct.pack(
        ">BBHHHBBH4s4s",
        0x45,
        0,
        total,
        0,
        0,
        64,
        1,
        checksum(base),
        socket.inet_aton(src),
        socket.inet_aton(dst),
    )
    return summed + message


def ipv6_icmp(dst_words: tuple[int, ...], kind: int = 128) -> bytes:
    header = bytearray(40)
    header[0] = 0x60
    header[4:6] = struct.pack(">H", 8)
    header[6] = 58
    header[7] = 64
    struct.pack_into(">8H", header, 24, *dst_words)
    message = struct.pack(">BBHHH", kind, 0, 0, 1, 1) + b"t5"
    return bytes(header) + message
