"""Bring up loopback inside a drill network namespace. No iproute2."""

from __future__ import annotations

import fcntl
import os
import socket
import struct

SIOCGIFFLAGS = 0x8913
SIOCSIFFLAGS = 0x8914
SIOCSIFADDR = 0x8916
SIOCSIFNETMASK = 0x891C
IFF_UP = 0x1


def netns_inode() -> int:
    return os.stat("/proc/self/ns/net").st_ino


def _ifreq_flags(name: bytes, flags: int) -> bytes:
    return struct.pack("16sH14x", name, flags)


def bring_up_lo() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        current = fcntl.ioctl(sock, SIOCGIFFLAGS, _ifreq_flags(b"lo", 0))
        flags = struct.unpack("16sH14x", current)[1]
        fcntl.ioctl(sock, SIOCSIFFLAGS, _ifreq_flags(b"lo", flags | IFF_UP))
    finally:
        sock.close()


_alias = 1


def add_ipv4(ip: str, mask: str = "255.255.255.255") -> None:
    """Add an address on an lo alias. Setting lo itself would replace 127.0.0.1."""
    global _alias
    if ip == "127.0.0.1":
        return
    label = f"lo:{_alias}".encode("ascii")
    _alias += 1
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        addr = struct.pack("HH4s8s", socket.AF_INET, 0, socket.inet_aton(ip), b"\0" * 8)
        fcntl.ioctl(sock, SIOCSIFADDR, struct.pack("16s", label) + addr)
        mask_bytes = struct.pack("HH4s8s", socket.AF_INET, 0, socket.inet_aton(mask), b"\0" * 8)
        fcntl.ioctl(sock, SIOCSIFNETMASK, struct.pack("16s", label) + mask_bytes)
    finally:
        sock.close()
