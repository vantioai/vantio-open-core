"""Decision functions for the red-team lab phases.

These functions do not start the loader. The shell phase passes the transcript
and the ledger. A unit test can feed the same shapes.
"""

from __future__ import annotations

import json


def _rows(text: str) -> list[dict]:
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _field(lines: list[str], prefix: str) -> str:
    for line in reversed(lines):
        if line.startswith(prefix):
            return line.split("=", 1)[1]
    return ""


def _blocked(item: str) -> bool:
    return "result=timeout" in item or "result=error" in item


def _connected(item: str) -> bool:
    return "result=connected" in item


def fork_inherit_verdict(transcript: str, ledger: str) -> str:
    """Parent, fork child, clone3 child, and grandchild are dropped.

    Each drop row carries one non-zero trace id and a non-zero lineage anchor.
    A process that was never in the family still connects.
    """
    lines = transcript.splitlines()
    parent = _field(lines, "fork_parent=connect where=parent ")
    child = _field(lines, "fork_child=connect where=child ")
    grand = _field(lines, "fork_grandchild=connect where=grandchild ")
    clone3 = _field(lines, "fork_clone3=connect where=clone3 ")
    outsider = _field(lines, "fork_outsider=connect where=outsider ")
    if not all(_blocked(item) for item in (parent, child, grand, clone3)):
        if any(_connected(item) for item in (parent, child, grand, clone3)):
            return "FAIL_OPEN"
        return "INCONCLUSIVE"
    if not _connected(outsider):
        return "FAIL_UNSCOPED"
    trace_ids = set()
    for row in _rows(ledger):
        if row.get("EventType") != "NETWORK_BLOCK" or row.get("ActionTaken") != "BLOCKED":
            continue
        try:
            anchor = int(row.get("lineage_anchor") or 0)
            severed = int(row.get("BytesSevered") or 0)
        except (TypeError, ValueError):
            return "FAIL_UNATTRIBUTED"
        if anchor <= 0 or severed <= 0:
            return "FAIL_UNATTRIBUTED"
        trace = str(row.get("TraceId") or "")
        if trace in ("", "0000000000000000"):
            return "FAIL_UNATTRIBUTED"
        trace_ids.add(trace)
    if len(trace_ids) != 1:
        return "FAIL_UNATTRIBUTED"
    return "PASS"


def same_boundary_verdict(transcript: str, ledger: str) -> str:
    lines = transcript.splitlines()
    first = _field(lines, "boundary_a=connect where=a ")
    second = _field(lines, "boundary_b=connect where=b ")
    exempt = _field(lines, "boundary_exempt=connect where=exempt ")
    later = _field(lines, "boundary_later=connect where=later ")
    if not all(_blocked(item) for item in (first, second, later)):
        if any(_connected(item) for item in (first, second, later)):
            return "FAIL_OPEN"
        return "INCONCLUSIVE"
    if not _connected(exempt):
        return "FAIL_EXCEPTION"
    blocked_cgroups = set()
    exempt_blocked = False
    for row in _rows(ledger):
        if row.get("EventType") != "NETWORK_BLOCK":
            continue
        cgroup = str(row.get("cgroup_path") or row.get("lineage_anchor") or "")
        if "exempt" in cgroup:
            exempt_blocked = True
        if cgroup:
            blocked_cgroups.add(cgroup)
    if exempt_blocked:
        return "FAIL_EXCEPTION"
    if len(blocked_cgroups) < 2 and not any(
        row.get("EventType") == "NETWORK_BLOCK" and int(row.get("BytesSevered") or 0) > 0
        for row in _rows(ledger)
    ):
        return "FAIL_UNATTRIBUTED"
    return "PASS"


def observed_open_verdict(transcript: str, ledger: str) -> str:
    """A successful open is not BLOCKED. A denied open may be BLOCKED or DENIED."""
    lines = transcript.splitlines()
    opened = _field(lines, "open_observe=")
    denied = _field(lines, "open_inside=")
    if "errno=0" not in opened:
        return "INCONCLUSIVE"
    if "errno=13" not in denied:
        return "INCONCLUSIVE"
    for row in _rows(ledger):
        payload = str(row.get("Payload") or row.get("PathAttempted") or "")
        action = row.get("ActionTaken")
        if payload.endswith("/etc/passwd") and action in {"BLOCKED", "DENIED"}:
            return "FAIL_MISLABEL"
        if "marker" in payload and action not in {"BLOCKED", "DENIED", None}:
            continue
    return "PASS"
