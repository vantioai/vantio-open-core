#!/usr/bin/env python3
"""Fail-closed grades for one enforcement-proof transcript.

The loader ndjson is not an independent drop counter.
This module does not call a cloud API and does not set live_enforcement.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

# Pinned to Phantom Engine 864289cb. cgroup_skb drops are written as
# CGROUP_BLOCK. When that loader writes every drop as NETWORK_BLOCK, change
# this constant to NETWORK_BLOCK. A row of the other type does not pass.
EXPECTED_DROP_EVENT = "CGROUP_BLOCK"
# Linux IPv4 TCP SYN with the usual options is 60 bytes on the wire.
# The ledger BytesSevered value has to equal that sent length.
SENT_PACKET_LENGTH = 60
# A connect that fails immediately is EPERM. Any other errno is not a block.
EXPECTED_BLOCK_ERRNO = 1
# EACCES. The file-deny canary is this errno inside the enrolled cgroup.
FILE_DENY_ERRNO = 13

CONNECT_RE = re.compile(
    r"^connect where=(?P<where>inside|outside) "
    r"result=(?P<result>connected|timeout|error|cgroup_join_failed|setuid_failed) "
    r"errno=(?P<errno>[0-9]+)(?: elapsed_ms=[0-9.]+)?$"
)
OPEN_RE = re.compile(
    r"^result=(?P<result>ok|error|cgroup_join_failed|setuid_failed) errno=(?P<errno>[0-9]+)$"
)
BOOT_RE = re.compile(r"^[0-9a-f-]{1,80}$")
DROP_COUNTER_RE = re.compile(
    r"^drop_counter=source=(?P<source>nft|iptables|tcpdump|ndjson|loader|missing)"
    r"(?: delta=(?P<delta>-?[0-9]+))?"
    r"(?: inside=(?P<inside>-?[0-9]+|missing))?"
    r"(?: outside=(?P<outside>-?[0-9]+|missing))?$"
)
LEDGER_DROP_RE = re.compile(
    r"^ledger_drop=type=(?P<type>[A-Z0-9_]+) bytes=(?P<bytes>-?[0-9]+) sent=(?P<sent>-?[0-9]+)$"
)
FORK_TRACE_RE = re.compile(
    r"^parent=(?P<parent>[0-9a-fA-F]+) child=(?P<child>[0-9a-fA-F]+) "
    r"grandchild=(?P<grandchild>[0-9a-fA-F]+)$"
)
FORK_ANCHOR_RE = re.compile(
    r"^parent=(?P<parent>[0-9]+) child=(?P<child>[0-9]+) grandchild=(?P<grandchild>[0-9]+)$"
)
ROOT_ATTEMPT_RE = re.compile(
    r"^root_detach_attempt=(?P<kind>prog_detach|link_detach|unlink) "
    r"target=(?P<target>\S+) result=(?P<result>refused|ok|other|skipped) "
    r"errno=(?P<errno>[0-9]+)$"
)
ROOT_LEDGER_RE = re.compile(
    r"^root_detach_ledger=type=(?P<type>[A-Z0-9_]+) bytes=(?P<bytes>-?[0-9]+) sent=(?P<sent>-?[0-9]+)$"
)
ROOT_KINDS = frozenset({"prog_detach", "link_detach", "unlink"})
_REFUSED_ERRNOS = frozenset({1, 13})
_INDEPENDENT_SOURCES = frozenset({"nft", "iptables", "tcpdump"})


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


def ledger_rows_ok(rows: Sequence[Mapping[str, Any]], sent_len: int = SENT_PACKET_LENGTH) -> bool:
    """True when one BLOCKED row has the pinned type and BytesSevered == sent_len.

    A file whose only blocked rows use a different EventType is not ok,
    including a NETWORK_BLOCK row while the pin is CGROUP_BLOCK.
    """
    if sent_len != SENT_PACKET_LENGTH:
        return False
    for row in rows:
        if row.get("ActionTaken") != "BLOCKED":
            continue
        if row.get("EventType") != EXPECTED_DROP_EVENT:
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


def ledger_line(text: str) -> str:
    """One ledger_drop line. MISMATCH when the only blocked rows are the wrong type."""
    sent = SENT_PACKET_LENGTH
    rows = _load_rows(text)
    if ledger_rows_ok(rows, sent):
        return f"ledger_drop=type={EXPECTED_DROP_EVENT} bytes={sent} sent={sent}"
    mismatched = False
    for row in rows:
        if row.get("ActionTaken") != "BLOCKED":
            continue
        event = row.get("EventType")
        if isinstance(event, str) and event and event != EXPECTED_DROP_EVENT:
            mismatched = True
    kind = "MISMATCH" if mismatched else "ABSENT"
    return f"ledger_drop=type={kind} bytes=0 sent={sent}"


def _ledger_line_ok(lines: Sequence[str]) -> bool:
    text = "ledger_drop=" + _last(lines, "ledger_drop=")
    match = LEDGER_DROP_RE.fullmatch(text)
    if match is None:
        return False
    return (
        match.group("type") == EXPECTED_DROP_EVENT
        and int(match.group("bytes")) == int(match.group("sent"))
        and int(match.group("sent")) == SENT_PACKET_LENGTH
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
    """PASS when parent, child, and grandchild are blocked with one non-zero trace id."""
    parent = _block_kind(_last(lines, "fork_parent="))
    child = _block_kind(_last(lines, "fork_child="))
    grandchild = _block_kind(_last(lines, "fork_grandchild="))
    if parent == "OTHER" and not _last(lines, "fork_parent="):
        return "INCONCLUSIVE"
    if "OPEN" in {parent, child, grandchild}:
        return "FAIL_OPEN"
    if parent != "BLOCK" or child != "BLOCK" or grandchild != "BLOCK":
        return "INCONCLUSIVE"
    if not _connected_ok(_last(lines, "fork_stranger=")):
        return "FAIL_UNSCOPED"
    trace = FORK_TRACE_RE.fullmatch(_last(lines, "fork_trace="))
    anchor = FORK_ANCHOR_RE.fullmatch(_last(lines, "fork_anchor="))
    if trace is None or anchor is None:
        return "FAIL_UNATTRIBUTED"
    if trace.group("parent") != trace.group("child") or trace.group("parent") != trace.group("grandchild"):
        return "FAIL_UNATTRIBUTED"
    if int(trace.group("parent"), 16) == 0:
        return "FAIL_UNATTRIBUTED"
    if min(int(anchor.group("parent")), int(anchor.group("child")), int(anchor.group("grandchild"))) <= 0:
        return "FAIL_UNATTRIBUTED"
    return "PASS"


def root_detach_verdict(lines: Sequence[str]) -> str:
    """PASS only when root, outside the loader, is refused on every detach.

    prog detach, link detach, and bpffs unlink must each be attempted and
    each must return EPERM or EACCES. The programs and pins must still be
    there. The enrolled connect must still be blocked, with a CGROUP_BLOCK
    row whose BytesSevered equals the sent length. A successful detach, a
    skipped attempt, and an inactive BPF LSM are FAIL. Tip 864289cb lets
    uid 0 detach, so this verdict is FAIL for that loader. The commit is
    not special-cased.
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
        if item.group("result") != "refused" or int(item.group("errno")) not in _REFUSED_ERRNOS:
            return "FAIL"
    if _last(lines, "root_detach_programs_remain=") != "yes":
        return "FAIL"
    if _last(lines, "root_detach_pins_remain=") != "yes":
        return "FAIL"
    inside = _last(lines, "root_detach_inside=")
    parsed_connect = _connect(inside)
    if parsed_connect is None or parsed_connect.group("where") != "inside" or _block_kind(inside) != "BLOCK":
        return "FAIL"
    ledger = ROOT_LEDGER_RE.fullmatch("root_detach_ledger=" + _last(lines, "root_detach_ledger="))
    if ledger is None or ledger.group("type") != EXPECTED_DROP_EVENT:
        return "FAIL"
    if int(ledger.group("bytes")) != int(ledger.group("sent")) or int(ledger.group("sent")) != SENT_PACKET_LENGTH:
        return "FAIL"
    return "PASS"


def reboot_post_ok(lines: Sequence[str], observed: Mapping[str, str] | None = None) -> bool:
    """True when the guest recorded a new boot id. An unchanged id fails."""
    if "reboot_wiped=PASS" not in lines or "reboot_restored=NOT_RUN" not in lines:
        return False
    pre = _last(lines, "reboot_pre_boot_id=")
    post = _last(lines, "reboot_post_boot_id=")
    if not BOOT_RE.fullmatch(pre) or not BOOT_RE.fullmatch(post) or pre == post:
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


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: proof_grade.py ledger-line|compare-verdict|gate", file=sys.stderr)
        return 2
    command = args[0]
    if command == "ledger-line" and len(args) == 2:
        path = Path(args[1])
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        print(ledger_line(text))
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
