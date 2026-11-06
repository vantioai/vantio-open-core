#!/usr/bin/env python3
"""Fail-closed grades for one enforcement-proof transcript.

The loader ndjson is not an independent drop counter.
This module does not call a cloud API and does not set live_enforcement.
"""

from __future__ import annotations

import json
import re
import socket
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

# Pinned to Phantom Engine 48c95504. A cgroup_skb drop and a TC drop both
# write NETWORK_BLOCK. DropPath names which hook. A CGROUP_BLOCK row does not pass.
EXPECTED_DROP_EVENT = "NETWORK_BLOCK"
EXPECTED_DROP_PATH = "cgroup_skb"
IPV4_HEADER_LEN = 20
TCP_HEADER_LEN = 40
UDP_HEADER_LEN = 8
# A connect that fails immediately is EPERM. Any other errno is not a block.
EXPECTED_BLOCK_ERRNO = 1
# EACCES. The file-deny canary is this errno inside the enrolled cgroup.
FILE_DENY_ERRNO = 13

CONNECT_RE = re.compile(
    r"^connect where=(?P<where>[a-z0-9_]+) "
    r"result=(?P<result>connected|timeout|error|cgroup_join_failed|setuid_failed) "
    r"errno=(?P<errno>[0-9]+)(?: elapsed_ms=[0-9.]+)?$"
)
OPEN_RE = re.compile(
    r"^result=(?P<result>ok|error|cgroup_join_failed|setuid_failed) errno=(?P<errno>[0-9]+)$"
)
BOOT_RE = re.compile(r"^[0-9a-f-]{1,80}$")
DROP_COUNT_RE = re.compile(
    r"^drop_count=packets=(?P<packets>[0-9]+) cgroup_skb=(?P<cgroup_skb>[0-9]+) tc=(?P<tc>[0-9]+)$"
)
LEDGER_TLS_RE = re.compile(r"^ledger_tls=rows=(?P<rows>[0-9]+)$")
DROP_COUNTER_RE = re.compile(
    r"^drop_counter=source=(?P<source>nft|iptables|tcpdump|afpacket|ndjson|loader|missing)"
    r"(?: delta=(?P<delta>-?[0-9]+))?"
    r"(?: inside=(?P<inside>-?[0-9]+|missing))?"
    r"(?: outside=(?P<outside>-?[0-9]+|missing))?$"
)
LEDGER_DROP_RE = re.compile(
    r"^ledger_drop=type=(?P<type>[A-Z0-9_]+) bytes=(?P<bytes>-?[0-9]+) "
    r"sent=(?P<sent>-?[0-9]+) drop_path=(?P<drop_path>[a-z0-9_]+)$"
)
SENT_PACKET_RE = re.compile(
    r"^sent_packet=transport=(?P<transport>tcp|udp) payload=(?P<payload>[0-9]+)"
    r"(?: ip_header=(?P<ip_header>[0-9]+))?"
    r"(?: transport_header=(?P<transport_header>[0-9]+))?"
    r" bytes=(?P<bytes>[0-9]+)$"
)
TCPDUMP_IP_RE = re.compile(r"proto TCP \(6\), length (?P<length>[0-9]+)")
TCPDUMP_PAYLOAD_RE = re.compile(r"Flags \[S\].*\blength (?P<length>[0-9]+)")
FORK_TRACE_RE = re.compile(
    r"^parent=(?P<parent>[0-9a-fA-F]+) child=(?P<child>[0-9a-fA-F]+) "
    r"grandchild=(?P<grandchild>[0-9a-fA-F]+)$"
)
FORK_ANCHOR_RE = re.compile(
    r"^parent=(?P<parent>[0-9]+) child=(?P<child>[0-9]+) grandchild=(?P<grandchild>[0-9]+)$"
)
FORK_ROWS_RE = re.compile(
    r"^fork_rows=blocks=(?P<blocks>[0-9]+) anchor=(?P<anchor>[0-9]+) "
    r"trace_zero=(?P<trace_zero>yes|no) drop_path=(?P<drop_path>[a-z0-9_]+)$"
)
ROOT_ATTEMPT_RE = re.compile(
    r"^root_detach_attempt=(?P<kind>prog_detach|link_detach|map_update|unlink|rename) "
    r"target=(?P<target>\S+) result=(?P<result>refused|ok|other|skipped) "
    r"errno=(?P<errno>[0-9]+)$"
)
ROOT_LEDGER_RE = re.compile(
    r"^root_detach_ledger=type=(?P<type>[A-Z0-9_]+) bytes=(?P<bytes>-?[0-9]+) "
    r"sent=(?P<sent>-?[0-9]+) drop_path=(?P<drop_path>[a-z0-9_]+)$"
)
ROOT_KINDS = frozenset({"prog_detach", "link_detach", "map_update", "unlink", "rename"})
SIGNAL_NAMES = ("SIGINT", "SIGTERM", "SIGHUP")
SIGNAL_RE = re.compile(
    r"^signal=(?P<name>SIGINT|SIGTERM|SIGHUP) result=(?P<result>refused|detached) "
    r"pins=(?P<pins>remain|gone) connect=(?P<connect>blocked|restored)$"
)
_REFUSED_ERRNO = 1
_INDEPENDENT_SOURCES = frozenset({"nft", "iptables", "tcpdump", "afpacket"})


def _last(lines: Sequence[str], prefix: str) -> str:
    found = ""
    for line in lines:
        if line.startswith(prefix):
            found = line[len(prefix) :]
    return found


def _connect(item: str) -> re.Match[str] | None:
    return CONNECT_RE.fullmatch(item)


def _connected_ok(item: str) -> bool:
    match = _connect(item)
    return match is not None and match.group("result") == "connected" and int(match.group("errno")) == 0


def _block_kind(item: str) -> str:
    """OPEN, BLOCK, or OTHER. BLOCK is a timeout or the pinned errno."""
    match = _connect(item)
    if match is None:
        return "OTHER"
    result = match.group("result")
    errno = int(match.group("errno"))
    if result == "connected":
        return "OPEN"
    if result == "timeout":
        return "BLOCK"
    if result == "error" and errno == EXPECTED_BLOCK_ERRNO:
        return "BLOCK"
    return "OTHER"


def counter_confirms_drop(line: str) -> bool:
    """True for an nft, iptables, or tcpdump observation of a drop.

    A delta is a drop counter that increased. inside=0 and outside>=1 is a
    wire count: the enrolled packets did not arrive and the outside ones did.
    The loader ndjson is not a counter.
    """
    match = DROP_COUNTER_RE.fullmatch(line.strip())
    if match is None or match.group("source") not in _INDEPENDENT_SOURCES:
        return False
    if match.group("delta") is not None and match.group("inside") is None:
        return int(match.group("delta")) >= 1
    inside = match.group("inside")
    outside = match.group("outside")
    if inside is None or outside is None or inside == "missing" or outside == "missing":
        return False
    return int(inside) == 0 and int(outside) >= 1


def _counter_ok(lines: Sequence[str]) -> bool:
    line = _last(lines, "drop_counter=")
    if not line:
        return False
    return counter_confirms_drop("drop_counter=" + line)


TCP_SYN_BYTES = IPV4_HEADER_LEN + TCP_HEADER_LEN


def full_packet_bytes(
    payload: int,
    transport: str,
    ip_header: int = IPV4_HEADER_LEN,
    transport_header: int | None = None,
) -> int:
    """Kernel length of the packet that was sent, headers included.

    The userspace payload length is not BytesSevered. A TCP SYN on Linux
    is the IPv4 header plus the TCP header (options included). A UDP
    datagram adds the UDP header. Passing the payload length as the packet
    length does not match.
    """
    if payload < 0 or ip_header < IPV4_HEADER_LEN:
        raise ValueError("header")
    if transport == "tcp":
        header = TCP_HEADER_LEN if transport_header is None else transport_header
        if header < 20:
            raise ValueError("header")
    elif transport == "udp":
        header = UDP_HEADER_LEN if transport_header is None else transport_header
        if header < UDP_HEADER_LEN:
            raise ValueError("header")
    else:
        raise ValueError("transport")
    total = payload + ip_header + header
    if total <= payload:
        raise ValueError("payload")
    return total


def sent_packet_ok(line: str) -> tuple[int, str] | None:
    match = SENT_PACKET_RE.fullmatch(line.strip())
    if match is None:
        return None
    payload = int(match.group("payload"))
    transport = match.group("transport")
    ip_header = int(match.group("ip_header") or IPV4_HEADER_LEN)
    raw_transport = match.group("transport_header")
    transport_header = None if raw_transport is None else int(raw_transport)
    try:
        expected = full_packet_bytes(payload, transport, ip_header, transport_header)
    except ValueError:
        return None
    if int(match.group("bytes")) != expected:
        return None
    return expected, transport


def sniff_syn(ip: str, port: int, seconds: float = 2.0) -> tuple[int, str, str]:
    """Count TCP packets to ip:port on lo and record one SYN.

    Returns (count, sent_packet line, status). status is ok or unavailable.
    A cgroup drop that happens before loopback delivery is a count of zero.
    """
    blank = "sent_packet=transport=tcp payload=0 bytes=0"
    try:
        sock = socket.socket(socket.AF_PACKET, socket.SOCK_DGRAM, socket.htons(0x0800))
        sock.bind(("lo", 0))
    except OSError:
        return 0, blank, "unavailable"
    sock.settimeout(0.2)
    count = 0
    line = blank
    deadline = time.time() + seconds
    try:
        while time.time() < deadline:
            try:
                data, _addr = sock.recvfrom(256)
            except socket.timeout:
                continue
            if len(data) < 40 or data[9] != 6:
                continue
            ihl = (data[0] & 0x0F) * 4
            total = int.from_bytes(data[2:4], "big")
            dst = ".".join(str(b) for b in data[16:20])
            if dst != ip or ihl < 20 or total < ihl + 20 or total > len(data) + 64:
                continue
            data_off = (data[ihl + 12] >> 4) * 4
            if data_off < 20 or ihl + data_off > total:
                continue
            dst_port = int.from_bytes(data[ihl + 2 : ihl + 4], "big")
            if dst_port != port:
                continue
            count += 1
            flags = data[ihl + 13]
            if flags & 0x02 and not flags & 0x10:
                payload = total - ihl - data_off
                line = (
                    f"sent_packet=transport=tcp payload={payload} ip_header={ihl} "
                    f"transport_header={data_off} bytes={total}"
                )
    finally:
        sock.close()
    return count, line, "ok"


def sent_packet_from_text(text: str) -> str:
    for line in reversed(text.splitlines()):
        if sent_packet_ok(line.strip()):
            return line.strip()
    return sent_packet_from_tcpdump(text)


def sent_packet_from_tcpdump(text: str) -> str:
    """One sent_packet line from a tcpdump -v decode of the SYN that was sent."""
    ip_match = TCPDUMP_IP_RE.search(text)
    payload_match = TCPDUMP_PAYLOAD_RE.search(text)
    if ip_match is None or payload_match is None:
        return "sent_packet=transport=tcp payload=0 bytes=0"
    ip_len = int(ip_match.group("length"))
    payload = int(payload_match.group("length"))
    transport_header = ip_len - IPV4_HEADER_LEN - payload
    return (
        f"sent_packet=transport=tcp payload={payload} ip_header={IPV4_HEADER_LEN} "
        f"transport_header={transport_header} bytes={ip_len}"
    )


def ledger_rows_ok(rows: Sequence[Mapping[str, Any]], sent_len: int, drop_path: str = EXPECTED_DROP_PATH) -> bool:
    """True when one BLOCKED NETWORK_BLOCK row has DropPath and BytesSevered == sent_len.

    sent_len is the full packet, headers included. A CGROUP_BLOCK row does not pass.
    A row whose BytesSevered is only the payload does not pass.
    """
    if sent_len <= IPV4_HEADER_LEN:
        return False
    for row in rows:
        if row.get("ActionTaken") != "BLOCKED":
            continue
        if row.get("EventType") != EXPECTED_DROP_EVENT:
            continue
        if row.get("DropPath") != drop_path:
            continue
        try:
            severed = int(row.get("BytesSevered"))
        except (TypeError, ValueError):
            continue
        if severed == sent_len:
            return True
    return False


def _load_rows(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def ledger_line(text: str, payload: int = 0, transport: str = "tcp", sent_line: str = "") -> str:
    """One ledger_drop line. The sent length is the full packet, not the payload."""
    if sent_line:
        parsed = sent_packet_ok(sent_line)
        if parsed is None:
            return "ledger_drop=type=ABSENT bytes=0 sent=0 drop_path=absent"
        sent = parsed[0]
    else:
        sent = full_packet_bytes(payload, transport)
    rows = _load_rows(text)
    if ledger_rows_ok(rows, sent):
        return (
            f"ledger_drop=type={EXPECTED_DROP_EVENT} bytes={sent} sent={sent} "
            f"drop_path={EXPECTED_DROP_PATH}"
        )
    mismatched = False
    for row in rows:
        if row.get("ActionTaken") != "BLOCKED":
            continue
        event = row.get("EventType")
        if isinstance(event, str) and event and event != EXPECTED_DROP_EVENT:
            mismatched = True
        if row.get("DropPath") not in (None, EXPECTED_DROP_PATH):
            mismatched = True
    kind = "MISMATCH" if mismatched else "ABSENT"
    return f"ledger_drop=type={kind} bytes=0 sent={sent} drop_path=absent"


def _sent_length(lines: Sequence[str]) -> int | None:
    parsed = sent_packet_ok("sent_packet=" + _last(lines, "sent_packet="))
    if parsed is None:
        return None
    return parsed[0]


def _ledger_line_ok(lines: Sequence[str]) -> bool:
    sent = _sent_length(lines)
    text = "ledger_drop=" + _last(lines, "ledger_drop=")
    match = LEDGER_DROP_RE.fullmatch(text)
    if sent is None or match is None:
        return False
    return (
        match.group("type") == EXPECTED_DROP_EVENT
        and match.group("drop_path") == EXPECTED_DROP_PATH
        and int(match.group("bytes")) == int(match.group("sent"))
        and int(match.group("sent")) == sent
    )


def compare_verdict(lines: Sequence[str]) -> str:
    """PASS only with the pinned block, an outside success, a counter, and the ledger row."""
    if "enforce_banner=ENFORCING" not in lines:
        return "INCONCLUSIVE"
    if not _connected_ok(_last(lines, "audit_outside=")) or not _connected_ok(_last(lines, "audit_inside=")):
        return "INCONCLUSIVE"
    inside = _block_kind(_last(lines, "enforce_inside="))
    if inside == "OPEN":
        return "FAIL_OPEN"
    if inside != "BLOCK":
        return "FAIL_UNEXPECTED_ERRNO" if _connect(_last(lines, "enforce_inside=")) else "INCONCLUSIVE"
    if not _counter_ok(lines) or not _ledger_line_ok(lines):
        return "FAIL_UNATTRIBUTED"
    if _last(lines, "ledger_chain=") != "ok":
        return "FAIL_UNATTRIBUTED"
    if LEDGER_TLS_RE.fullmatch("ledger_tls=" + _last(lines, "ledger_tls=")) is None:
        return "FAIL_UNATTRIBUTED"
    counted = DROP_COUNT_RE.fullmatch("drop_count=" + _last(lines, "drop_count="))
    if counted is None or int(counted.group("packets")) < 1:
        return "FAIL_UNATTRIBUTED"
    if not _connected_ok(_last(lines, "enforce_outside=")):
        return "FAIL_UNSCOPED"
    return "PASS"


def file_deny_verdict(lines: Sequence[str]) -> str:
    """PASS only for errno 13 inside the cgroup and errno 0 outside, with a deny row."""
    inside = OPEN_RE.fullmatch(_last(lines, "open_inside="))
    outside = OPEN_RE.fullmatch(_last(lines, "open_outside="))
    if inside is None or outside is None:
        return "INCONCLUSIVE"
    if inside.group("result") == "ok":
        return "FAIL_OPEN"
    if not (inside.group("result") == "error" and int(inside.group("errno")) == FILE_DENY_ERRNO):
        return "INCONCLUSIVE"
    if not (outside.group("result") == "ok" and int(outside.group("errno")) == 0):
        return "FAIL_UNSCOPED"
    if "file_deny_row=yes" not in lines:
        return "FAIL_UNATTRIBUTED"
    return "PASS"


def fork_inherit_verdict(lines: Sequence[str]) -> str:
    """PASS when every descendant is blocked and the drops share one enrolled anchor.

    A cgroup drop writes TraceId as 0xA110000000000000 plus the sender TGID when
    that TGID was not already in the trace map. Parent, child, and grandchild
    therefore emit different TraceId values. The shared field is lineage_anchor.
    A zero TraceId, a zero anchor, or more than one anchor is not attribution.
    """
    parent = _block_kind(_last(lines, "fork_parent="))
    child = _block_kind(_last(lines, "fork_child="))
    grandchild = _block_kind(_last(lines, "fork_grandchild="))
    clone3 = _last(lines, "fork_clone3=")
    if parent == "OTHER" and not _last(lines, "fork_parent="):
        return "INCONCLUSIVE"
    family = {parent, child, grandchild}
    if clone3:
        family.add(_block_kind(clone3))
    if "OPEN" in family:
        return "FAIL_OPEN"
    if parent != "BLOCK" or child != "BLOCK" or grandchild != "BLOCK":
        return "INCONCLUSIVE"
    if not clone3 or _block_kind(clone3) != "BLOCK":
        return "INCONCLUSIVE"
    outsider = _last(lines, "fork_outsider=") or _last(lines, "fork_stranger=")
    if not _connected_ok(outsider):
        return "FAIL_UNSCOPED"
    rows = FORK_ROWS_RE.fullmatch("fork_rows=" + _last(lines, "fork_rows="))
    anchor = FORK_ANCHOR_RE.fullmatch(_last(lines, "fork_anchor="))
    if rows is None or anchor is None:
        return "FAIL_UNATTRIBUTED"
    if rows.group("trace_zero") != "no" or rows.group("drop_path") != EXPECTED_DROP_PATH:
        return "FAIL_UNATTRIBUTED"
    if int(rows.group("blocks")) < 1 or int(rows.group("anchor")) <= 0:
        return "FAIL_UNATTRIBUTED"
    recorded = int(rows.group("anchor"))
    if any(int(anchor.group(name)) != recorded for name in ("parent", "child", "grandchild")):
        return "FAIL_UNATTRIBUTED"
    return "PASS"


def root_detach_verdict(lines: Sequence[str]) -> str:
    """PASS only when root, outside the loader, is refused on every canary.

    prog detach, link detach, map update, pin unlink, and pin rename must
    each be attempted and each must return errno 1. The programs and pins
    must still be there. The enrolled connect must still be blocked, with a
    NETWORK_BLOCK row, DropPath cgroup_skb, and BytesSevered equal to the
    full packet length. A successful detach, errno 13, a skipped attempt,
    and an inactive BPF LSM are FAIL.
    """
    if _last(lines, "root_detach_lsm=") != "present":
        return "FAIL"
    if _last(lines, "root_detach_uid=") != "0":
        return "FAIL"
    if _last(lines, "root_detach_actor=") != "outside_loader":
        return "FAIL"
    attempts = [ROOT_ATTEMPT_RE.fullmatch(line) for line in lines]
    parsed = [item for item in attempts if item is not None]
    if {item.group("kind") for item in parsed} != ROOT_KINDS:
        return "FAIL"
    for item in parsed:
        if item.group("result") != "refused" or int(item.group("errno")) != _REFUSED_ERRNO:
            return "FAIL"
    if _last(lines, "root_detach_programs_remain=") != "yes":
        return "FAIL"
    if _last(lines, "root_detach_pins_remain=") != "yes":
        return "FAIL"
    inside = _last(lines, "root_detach_inside=")
    parsed_connect = _connect(inside)
    if parsed_connect is None or parsed_connect.group("where") != "inside" or _block_kind(inside) != "BLOCK":
        return "FAIL"
    sent = _sent_length(lines)
    ledger = ROOT_LEDGER_RE.fullmatch("root_detach_ledger=" + _last(lines, "root_detach_ledger="))
    if sent is None or ledger is None or ledger.group("type") != EXPECTED_DROP_EVENT:
        return "FAIL"
    if ledger.group("drop_path") != EXPECTED_DROP_PATH:
        return "FAIL"
    if int(ledger.group("bytes")) != int(ledger.group("sent")) or int(ledger.group("sent")) != sent:
        return "FAIL"
    return "PASS"


def signal_verdict(lines: Sequence[str]) -> str:
    """PASS when SIGINT, SIGTERM, and SIGHUP each leave enforcement up."""
    found: dict[str, re.Match[str]] = {}
    for line in lines:
        match = SIGNAL_RE.fullmatch(line)
        if match is not None:
            found[match.group("name")] = match
    if set(found) != set(SIGNAL_NAMES):
        return "FAIL"
    for match in found.values():
        if match.group("result") != "refused" or match.group("pins") != "remain" or match.group("connect") != "blocked":
            return "FAIL"
    if _last(lines, "signal_process=") != "up":
        return "FAIL"
    return "PASS"


def same_boundary_verdict(lines: Sequence[str]) -> str:
    """PASS when unlisted, expired, and unsigned stay blocked and a signed stop restores."""
    need = {
        "boundary_unlisted": "blocked",
        "boundary_exception": "connected",
        "boundary_expired": "blocked",
        "boundary_unsigned": "blocked",
        "boundary_stop": "restored",
    }
    for key, value in need.items():
        if _last(lines, key + "=") != value:
            return "FAIL"
    return "PASS"


def oom_verdict(lines: Sequence[str]) -> str:
    """PASS when the loader is killed and the programs still block connect."""
    if _last(lines, "oom_killed=") != "yes":
        return "FAIL"
    if _last(lines, "oom_programs=") != "remain":
        return "FAIL"
    if _block_kind(_last(lines, "oom_inside=")) != "BLOCK":
        return "FAIL"
    return "PASS"


ESCAPE_KINDS = ("file", "exec", "memfd", "interpreter", "static", "userns")


def escapes_verdict(lines: Sequence[str]) -> str:
    """PASS when each named escape is denied."""
    for kind in ESCAPE_KINDS:
        if not _last(lines, f"escape_{kind}=").startswith("denied"):
            return "FAIL"
    return "PASS"


def clock_verdict(lines: Sequence[str]) -> str:
    """PASS when the clock moves past exp and enforcement fails closed."""
    if _last(lines, "clock_moved=") != "yes":
        return "FAIL"
    if _last(lines, "clock_exp_passed=") != "yes":
        return "FAIL"
    if _last(lines, "clock_enforcement=") != "fail_closed":
        return "FAIL"
    return "PASS"


def reboot_post_ok(lines: Sequence[str], observed: Mapping[str, str] | None = None) -> bool:
    """True when a new boot id re-applied the block. NOT_RUN is not a pass."""
    if "reboot_wiped=PASS" not in lines or "reboot_restored=PASS" not in lines:
        return False
    if "reboot_restored=NOT_RUN" in lines:
        return False
    pre = _last(lines, "reboot_pre_boot_id=")
    post = _last(lines, "reboot_post_boot_id=")
    if not BOOT_RE.fullmatch(pre) or not BOOT_RE.fullmatch(post) or pre == post:
        return False
    if _block_kind(_last(lines, "reboot_post_inside=")) != "BLOCK":
        return False
    if observed and observed.get("before") and observed.get("after"):
        before = observed["before"]
        after = observed["after"]
        if before == after or pre != before or post != after:
            return False
    return True


def expired_key_accepted(lines: Sequence[str], returncode: int) -> bool:
    """NOT_PROVEN is a failure. REFUSED is the observation that the loader refused exp."""
    if returncode != 0:
        return False
    if any(line.startswith("expired_key=FAIL") for line in lines):
        return False
    if "license_exp_claim=NOT_PROVEN" in lines:
        return False
    return "license_exp_claim=REFUSED" in lines and "license_exp_observation=REFUSED" in lines


def _status(lines: Sequence[str], key: str) -> str:
    return _last(lines, key + "=")


def _needs(lines: Sequence[str], need: Mapping[str, str]) -> bool:
    return all(_status(lines, key) == value for key, value in need.items())


_PHASE_MARK = {
    "unix-socket": "unix_socket",
    "ptrace-deny": "ptrace_deny",
    "inbound": "inbound",
    "bpffs-overmount": "bpffs_overmount",
    "af-packet": "af_packet",
    "stop-token": "stop_token",
    "pin-absent": "pin_absent",
    "missing-path": "missing_path",
    "k8s": "k8s",
    "vlan": "vlan",
    "host-enroll": "host_enroll",
    "clock": "clock",
    "reboot-post": "reboot_post",
}


def phase_decision(
    phase: str,
    lines: Sequence[str],
    returncode: int,
    observed_boots: Mapping[str, str] | None = None,
) -> bool:
    """True when this phase's evidence is accepted. Unknown phases fail closed."""
    if returncode == 255:
        return False
    if phase == "compare":
        return returncode == 0 and compare_verdict(lines) == "PASS"
    if phase == "file-deny":
        return returncode == 0 and file_deny_verdict(lines) == "PASS"
    if phase == "reboot-pre":
        return returncode == 0 and "reboot_pre=RECORDED" in lines
    if phase == "reboot-post":
        return returncode == 0 and reboot_post_ok(lines, observed_boots)
    if phase == "expired-key":
        return expired_key_accepted(lines, returncode)
    if phase == "fork-inherit":
        return returncode == 0 and fork_inherit_verdict(lines) == "PASS"
    if phase == "root-detach":
        return returncode == 0 and root_detach_verdict(lines) == "PASS"
    if phase == "signals":
        return returncode == 0 and signal_verdict(lines) == "PASS"
    if phase == "same-boundary":
        return returncode == 0 and same_boundary_verdict(lines) == "PASS"
    if phase == "oom":
        return returncode == 0 and oom_verdict(lines) == "PASS"
    if phase == "escapes":
        return returncode == 0 and escapes_verdict(lines) == "PASS"
    if phase == "clock":
        return returncode == 0 and clock_verdict(lines) == "PASS"
    if phase == "unix-socket":
        return returncode == 0 and _needs(lines, {"unix_enrolled": "denied", "unix_outside": "connected"})
    if phase == "ptrace-deny":
        return returncode == 0 and all(
            _status(lines, key) in {"1", "13"}
            for key in ("ptrace_errno", "process_vm_errno", "proc_mem_errno", "pidfd_getfd_errno")
        )
    if phase == "inbound":
        return returncode == 0 and _needs(lines, {"inbound_enrolled": "blocked", "inbound_outside": "connected"})
    if phase == "bpffs-overmount":
        return returncode == 0 and _needs(lines, {"bpffs_overmount": "refused", "bpffs_errno": "1", "bpffs_pins": "remain"})
    if phase == "af-packet":
        return returncode == 0 and _needs(lines, {"af_packet_enrolled": "denied", "af_packet_outside": "ok"})
    if phase == "stop-token":
        return returncode == 0 and _needs(
            lines,
            {
                "stop_expired": "refused",
                "stop_bare": "refused",
                "stop_replay": "refused",
                "stop_fresh": "accepted",
            },
        )
    if phase == "pin-absent":
        return returncode == 0 and _needs(lines, {"pin_absent": "REFUSED", "pin_present": "ENFORCING"})
    if phase == "missing-path":
        return returncode == 0 and _needs(lines, {"missing_create": "denied", "missing_created": "no"})
    if phase == "k8s":
        return returncode == 0 and _needs(lines, {"k8s_enrolled": "blocked", "k8s_outsider": "connected"})
    if phase == "vlan":
        return returncode == 0 and _needs(lines, {"vlan_attached": "yes", "vlan_enrolled": "denied", "vlan_outside": "allowed"})
    if phase == "host-enroll":
        return returncode == 0 and same_boundary_verdict(lines) == "PASS"
    if phase == "uninstall":
        return any(
            line in lines
            for line in (
                "uninstall=VERIFIED",
                "uninstall=NOT_RUN_NO_APPROVAL",
                "uninstall=REFUSED_NOT_ENROLLED",
            )
        )
    return False


def phase_outcome(
    phase: str,
    lines: Sequence[str],
    returncode: int,
    observed_boots: Mapping[str, str] | None = None,
) -> str:
    """PASS, FAIL, or NOT_RUN. NOT_RUN is not a pass."""
    mark = _PHASE_MARK.get(phase)
    if mark is not None and _status(lines, mark) == "NOT_RUN":
        return "NOT_RUN"
    if phase_decision(phase, lines, returncode, observed_boots):
        return "PASS"
    return "FAIL"


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: proof_grade.py ledger-line|compare-verdict|gate", file=sys.stderr)
        return 2
    command = args[0]
    if command == "sent-packet" and len(args) == 2:
        path = Path(args[1])
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        print(sent_packet_from_text(text))
        return 0
    if command == "sniff-syn" and len(args) == 4:
        count, line, status = sniff_syn(args[1], int(args[2]), float(args[3]))
        print(f"{count}\t{line}\t{status}")
        return 0
    if command == "ledger-line" and len(args) >= 2:
        path = Path(args[1])
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        sent_line = ""
        if "--sent-line" in args:
            sent_line = args[args.index("--sent-line") + 1]
        print(ledger_line(text, sent_line=sent_line))
        return 0
    if command == "fork-inherit-verdict" and len(args) == 2:
        path = Path(args[1])
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        print(fork_inherit_verdict(text.splitlines()))
        return 0
    if command == "compare-verdict" and len(args) == 2:
        path = Path(args[1])
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        print(compare_verdict(text.splitlines()))
        return 0
    if command == "root-detach-verdict" and len(args) == 2:
        path = Path(args[1])
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        print(root_detach_verdict(text.splitlines()))
        return 0
    if command == "gate" and len(args) == 4:
        phase, path, raw_rc = args[1], Path(args[2]), args[3]
        try:
            returncode = int(raw_rc)
        except ValueError:
            return 2
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines() if path.is_file() else []
        accepted = phase_decision(phase, lines, returncode)
        print("harness_accept=yes" if accepted else "harness_accept=no")
        return 0 if accepted else 1
    print("usage: proof_grade.py ledger-line|compare-verdict|gate", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
