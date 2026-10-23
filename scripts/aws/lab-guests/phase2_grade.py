#!/usr/bin/env python3
"""Score one clean-host phase observation. No AWS and no loader.

A fixture result is not a host pass. These functions only classify numbers
the guest already measured. lab_pass stays false. The ceiling stays
INTERNAL_CLEAN_HOST_PROOF.
"""

from __future__ import annotations

import importlib.util
import ipaddress
import sys
from pathlib import Path
from typing import Any


def _load_seal():
    origin = Path(__file__).resolve().parent
    for parent in (origin, *origin.parents):
        for candidate in (parent / "pe_canonical_seal.py", parent / "scripts" / "release" / "pe_canonical_seal.py"):
            if not candidate.is_file():
                continue
            cached = sys.modules.get("pe_canonical_seal")
            if cached is not None:
                return cached
            spec = importlib.util.spec_from_file_location("pe_canonical_seal", candidate)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules["pe_canonical_seal"] = module
            spec.loader.exec_module(module)
            return module
    raise FileNotFoundError("pe_canonical_seal.py")


_SEAL = _load_seal()
# Zachary, 2026-10-16: the comparison digest is the working seal.
# The previous working seal prefix is bbb1025d. The full digest is in release/pe-seal-history.json.
WORKING_SEAL = _SEAL.lane_seal()
PREVIOUS_WORKING_SEAL = _SEAL.previous_working_seal()
PUBLIC_INSTALLER_PIN = _SEAL.public_pin()
CLAIM_CEILING = "INTERNAL_CLEAN_HOST_PROOF"
PHASES = (
    "r15-container-exit",
    "2c-upgrade-rollback",
    "2d-crash-recovery",
    "2e-performance",
    "2f-tamper",
    "2g-distro",
    "lsm-guard",
)
MAX_PERF_SECONDS = 900
CGROUP_SKB_PROGRAM = "cgroup_skb_egress_enforce"
# bpftool prog show prints at most 15 characters of the kernel name.
CGROUP_SKB_BPFTOOL_PREFIX = "cgroup_skb_egre"
# Lab listener on the host's own address. Not a privileged port.
DEFAULT_EGRESS_PORT = 4879
# RFC 5737. These are not routed on AWS or GCP, so a battery must not use them.
_DOCUMENTATION_V4 = (
    ipaddress.IPv4Network("192.0.2.0/24"),
    ipaddress.IPv4Network("198.51.100.0/24"),
    ipaddress.IPv4Network("203.0.113.0/24"),
)


def restart_keeps_the_same_anchor(
    *,
    pid: int | None,
    before_errno: int | None,
    before_anchor: int | None,
    after_errno: int | None,
    after_anchor: int | None,
    before_count: int | None,
    after_count: int | None,
) -> dict[str, Any]:
    """The same process stays denied with the same anchor after the loader restarts.

    A second errno 13 with no new deny row is a stand-in. A different anchor
    means the restart did not keep the enrollment.
    """
    same_pid = isinstance(pid, int) and not isinstance(pid, bool) and pid > 0
    same_anchor = (
        isinstance(before_anchor, int)
        and not isinstance(before_anchor, bool)
        and before_anchor > 0
        and after_anchor == before_anchor
    )
    new_row = (
        isinstance(before_count, int)
        and not isinstance(before_count, bool)
        and isinstance(after_count, int)
        and not isinstance(after_count, bool)
        and after_count > before_count
    )
    held = same_pid and before_errno == 13 and after_errno == 13 and same_anchor and new_row
    reason = None
    if not held:
        if after_errno == 0:
            reason = "enrollment_dropped"
        elif not new_row:
            reason = "no_new_deny_after_restart"
        else:
            reason = "anchor_not_carried"
    return {"held": held, "reason": reason}


# GCP 2D only (phase2_host with VANTIO_LAB_CLOUD=gcp; AWS keeps DENY_ROW_WAIT_S).
# On an e2-micro the same-process deny row took 4.2 s after the restart in run 4
# and more than 5 s in run 5. The GCP wait is 15 s. A row seen after 5 s still
# counts, and its seconds are kept as late_s.
RESTART_ROW_CAP_S = 15.0
RESTART_ROW_LATE_S = 5.0
# Where a 2D restart row's time came from. PE ledger rows carry no time field,
# so the guest falls back to its own wall clock when it first saw the row.
LEDGER_TS_FROM_ROW = "ledger_row"
LEDGER_TS_HOST_SEEN = "host_seen_at"
# DenyAttr.path_key is 32 bytes. Rows drained from the deny-attr map carry the
# ceiling path cut to this length, so they never equal the full path.
DENY_PATH_KEY_LEN = 32
# Why one side of the restart check failed. not_blocked is a fail-open (the
# open succeeded). row_absent_errno13 means the open was blocked but no row
# was written; row_past_cap means the row came only after RESTART_ROW_CAP_S;
# row_not_new means the row did not raise the count. All are fails.
RESTART_ROW_CAUSES = frozenset(
    {
        "anchor_not_carried",
        "errno_invalid",
        "errno_not_13",
        "guest_flag_mismatch",
        "not_blocked",
        "pid_mismatch",
        "row_absent_errno13",
        "row_not_new",
        "row_past_cap",
    }
)


def _positive_int(value: object) -> bool:
    return type(value) is int and value > 0


def _count(value: object) -> bool:
    return type(value) is int and value >= 0


def restart_row_cause(side: Any) -> str | None:
    """None when one side of the GCP 2D restart check held, else why it failed.

    The probe needs errno int 13: bool, str, float and None are rejected.
    errno 0 is always not_blocked, whatever the ledger shows. With errno 13,
    a new DENIED row for the same pid has to be seen within RESTART_ROW_CAP_S
    and carry the expected anchor. pid, anchor and newness come from the
    integers; a boolean that disagrees is guest_flag_mismatch. The host
    (offline_deliver_2.restart_row_cause) grades the same way.
    """
    if not isinstance(side, dict):
        return "errno_invalid"
    errno = side.get("errno")
    if type(errno) is not int:
        return "errno_invalid"
    if errno == 0:
        return "not_blocked"
    if errno != 13:
        return "errno_not_13"
    wait = side.get("wait_s")
    if side.get("row_seen") is not True or type(wait) not in (int, float) or not 0 <= wait < float("inf"):
        return "row_absent_errno13"
    if wait > RESTART_ROW_CAP_S:
        return "row_past_cap"
    count, before = side.get("row_count"), side.get("rows_before")
    if not (_count(count) and _count(before) and count > before):
        return "row_not_new"
    pid = side.get("pid")
    if not (_positive_int(pid) and side.get("row_pid") == pid):
        return "pid_mismatch"
    anchor, expected = side.get("anchor"), side.get("expected_anchor")
    if not _positive_int(anchor) or (expected is not None and expected != anchor):
        return "anchor_not_carried"
    for key in ("new_row", "pid_match", "anchor_match"):
        if key in side and side[key] is not True:
            return "guest_flag_mismatch"
    return None


def restart_row_side(
    *,
    pid: Any,
    errno: Any,
    row: Any,
    wait_s: Any,
    row_count: Any,
    rows_before: Any,
    expected_anchor: Any,
    probe_at: Any = None,
    seen_at: Any = None,
    ledger_ts: Any = None,
    map_rows: Any = None,
    map_rows_before: Any = None,
) -> dict[str, Any]:
    """Evidence for one side of the GCP 2D restart check, plus its grade.

    expected_anchor None (before the restart) accepts any positive anchor.
    After the restart it is the anchor on the first row. The fields are the
    same on both sides.

    ledger_ts_source says where a time for the row came from. PE ledger rows
    (engine da961aa) carry no time field, so it is usually host_seen_at: the
    guest's wall clock when the poll first saw the row, an upper bound on when
    the row was written. map_rows counts this pid's rows from the deny-attr
    map, whose path is cut to 32 bytes; they are evidence only, never graded.

    map_rows is cumulative for the pid, so on the after side it includes the
    before side's rows. The after side also gets map_rows_before (the before
    side's map_rows) and map_rows_after_new = map_rows - map_rows_before, never
    below 0: the cut rows written since the before side was recorded.
    """
    row = row if isinstance(row, dict) else None
    anchor = row.get("lineage_anchor") if row else 0
    row_pid = row.get("pid") if row else 0
    if expected_anchor is None:
        anchor_match = row is not None and _positive_int(anchor)
    else:
        anchor_match = row is not None and _positive_int(anchor) and anchor == expected_anchor
    side: dict[str, Any] = {
        "anchor": anchor if _positive_int(anchor) else 0,
        "anchor_match": anchor_match,
        "errno": errno,
        "expected_anchor": expected_anchor,
        "ledger_ts": ledger_ts if row is not None else None,
        "new_row": _count(row_count) and _count(rows_before) and row_count > rows_before,
        "pid": pid,
        "pid_match": row is not None and _positive_int(pid) and row_pid == pid,
        "probe_at": probe_at,
        "row_count": row_count,
        "row_pid": row_pid if _positive_int(row_pid) else 0,
        "row_seen": row is not None,
        "rows_before": rows_before,
        "seen_at": seen_at if row is not None else None,
        "wait_s": wait_s,
    }
    if row is not None:
        side["ledger_ts_source"] = LEDGER_TS_FROM_ROW if ledger_ts else LEDGER_TS_HOST_SEEN
    if _count(map_rows):
        side["map_rows"] = map_rows
        if _count(map_rows_before):
            side["map_rows_before"] = map_rows_before
            side["map_rows_after_new"] = max(0, map_rows - map_rows_before)
    cause = restart_row_cause(side)
    side["cause"] = cause
    side["pass"] = cause is None
    if cause is None and wait_s > RESTART_ROW_LATE_S:
        side["late_s"] = wait_s
    return side


def anchor_before_open_ok(anchor: object) -> bool:
    """The 2D baseline may open only after the lab cgroup has a non-zero anchor.

    Errno 13 with anchor 0 is not an enrolled deny. It is DAC, a stand-in, or
    a missing enrollment write.
    """
    return isinstance(anchor, int) and not isinstance(anchor, bool) and anchor > 0


def _base(battery: str) -> dict[str, Any]:
    return {
        "battery": battery,
        "claim_ceiling": CLAIM_CEILING,
        "customer_claim": False,
        "descendant_pass": False,
        "docker_child_pass": False,
        "lab_pass": False,
        "published": False,
        "seal": WORKING_SEAL,
    }


DENY_KIND_FILE = 1
DENY_KIND_EGRESS_CGROUP = 2
DENY_KIND_EGRESS_TC = 3
DENY_KIND_SELF = 4
# DenyAttr on engine a86c7af: pid, uid, kind, path_len, anchor, timestamp, syscall, inodes, 32-byte path.
DENY_ATTR_SIZE = 88


def deny_record_anchor(record: bytes, pid: int) -> int:
    """Lineage anchor from a pinned DenyAttr, or 0 when the row does not name both.

    pid is at 0, kind at 8, anchor_cgroup at 16, timestamp_ns at 24. A pid
    with anchor 0 is not a post-kill hold.
    """
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return 0
    if len(record) < DENY_ATTR_SIZE:
        return 0
    got = int.from_bytes(record[0:4], "little")
    kind = int.from_bytes(record[8:12], "little")
    anchor = int.from_bytes(record[16:24], "little")
    timestamp = int.from_bytes(record[24:32], "little")
    if got != pid or anchor == 0 or timestamp == 0 or kind not in (DENY_KIND_FILE, DENY_KIND_SELF):
        return 0
    return anchor


def deny_record_names(record: bytes, pid: int) -> bool:
    """True when the pinned row names this pid and a non-zero lineage anchor."""
    return deny_record_anchor(record, pid) > 0


def egress_record_anchor(record: bytes, pid: int) -> int:
    """Lineage anchor from an egress deny-attr row, or 0.

    A dropped SYN makes connect time out. That timeout is a block only when
    this row names the pid, an egress kind, a non-zero anchor, and a timestamp.
    A file row does not count.
    """
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return 0
    if len(record) < DENY_ATTR_SIZE:
        return 0
    got = int.from_bytes(record[0:4], "little")
    kind = int.from_bytes(record[8:12], "little")
    anchor = int.from_bytes(record[16:24], "little")
    timestamp = int.from_bytes(record[24:32], "little")
    if got != pid or anchor == 0 or timestamp == 0:
        return 0
    if kind not in (DENY_KIND_EGRESS_CGROUP, DENY_KIND_EGRESS_TC):
        return 0
    return anchor


def usable_lab_ipv4(host: str) -> bool:
    """An address the battery may connect to.

    The lab host's own private address qualifies. A paired instance's private
    address qualifies. Loopback, link-local, and RFC 5737 documentation
    ranges do not: those documentation ranges are not routed on AWS or GCP.
    """
    try:
        ip = ipaddress.IPv4Address(host)
    except ipaddress.AddressValueError:
        return False
    if (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
        or not ip.is_private
    ):
        return False
    return not any(ip in network for network in _DOCUMENTATION_V4)


def choose_egress_target(
    configured_host: str | None,
    configured_port: int | None,
    local_addrs: list[str],
) -> tuple[str, int] | None:
    """Listener address for one battery run.

    An explicit host is the arm's choice: this machine's private address, or
    a paired lab instance's private address. When the arm does not set one,
    the first usable address on this host is the target. A documentation
    address is refused, and the case is not graded. The local netns unit
    test is the only path that still dials the documentation listener.
    """
    if configured_port is None:
        port = DEFAULT_EGRESS_PORT
    elif isinstance(configured_port, bool) or not isinstance(configured_port, int):
        return None
    elif configured_port < 1 or configured_port > 65535:
        return None
    else:
        port = configured_port
    host = (configured_host or "").strip()
    if host:
        if not usable_lab_ipv4(host):
            return None
        return host, port
    for addr in local_addrs:
        if usable_lab_ipv4(addr):
            return addr, port
    return None


def egress_word(errno: int | None) -> str:
    """Blocked is EPERM, EACCES, or connection refused. A timeout is not a result."""
    if errno in (1, 13, 111):
        return "denied"
    if errno == 0:
        return "allowed"
    return "no_response"


def egress_grade_block(control_errno: int | None, enrolled_errno: int | None) -> str | None:
    """Why this egress pair must not be graded.

    The unenrolled control has to finish the handshake before the enrolled
    connect counts. A timeout, a refusal, or any other incomplete control is
    the lab network (security group, firewall, or listener), so the case is
    not a result. An enrolled timeout after a completed control is not a
    result either. Errno 0, 1, 13, or 111 on the enrolled connect is definite.
    """
    if isinstance(control_errno, bool) or control_errno != 0:
        return "lab_network"
    if isinstance(enrolled_errno, bool) or enrolled_errno not in (0, 1, 13, 111):
        return "enrolled_egress_timeout"
    return None


def apply_allowlisted_private(body: dict[str, Any], errno: int | None) -> dict[str, Any]:
    """An allowlisted private destination has to finish the handshake.

    Scoped mode denies other private addresses. A block of the allowlisted
    one is over-blocking, so a pass becomes a fail. A missing measurement
    does the same. A battery that is already not a pass keeps its result.
    """
    if isinstance(errno, bool) or not isinstance(errno, int):
        body["allowlisted_private"] = "missing"
        if body.get("host_result") == "PASS":
            body["classification"] = "overblock"
            body["expectation_met"] = False
            body["host_result"] = "FAIL"
        return body
    body["allowlisted_private_errno"] = errno
    body["allowlisted_private"] = egress_word(errno)
    if body.get("host_result") == "PASS" and errno != 0:
        body["classification"] = "overblock"
        body["expectation_met"] = False
        body["host_result"] = "FAIL"
    return body


# The three deny-attr pins a starting loader pins beside the canonical name
# (<pin>_incoming_<pid>) and promotes only after the previous generation stops.
DENY_SWAP_STEMS = ("vantio_deny_attr", "vantio_deny_attr_drops", "vantio_deny_overflow")
MAP_SWAP_TIMEOUT = "map_swap_timeout"
MAP_SWAP_BASELINE_MISSING = "map_swap_baseline_missing"
# The previous generation still had a live side pin, or a canonical map was
# missing, when the baseline was due. Nothing is killed.
MAP_SWAP_BASELINE_UNSETTLED = "map_swap_baseline_unsettled"
# The ids changed, but the side pin seen during the wait was not the
# running enforce loader's <pin>_incoming_<pid> (or that pid was not known).
MAP_SWAP_SIDE_PIN_UNMATCHED = "map_swap_side_pin_unmatched"
# Every 2F body says when the loader was killed. A graded 2F body also says
# what that timing does and does not cover.
KILL_TIMING_AFTER_MAP_SWAP = "after_map_swap"
CLAIM_SCOPE_2F = "kill after deny-attr map swap; ready-to-swap gap not covered (VAN-45)"
# A 2F body refused before kill_loader ran says so.
KILL_TIMING_NOT_KILLED = "not_killed"
# A 2F PASS without both claim fields is not a pass.
CLAIM_FIELDS_MISSING = "claim_fields_missing"


def tamper_claim_complete(body: Any) -> bool:
    """The body says the kill came after the map swap and names the claim it supports."""
    if not isinstance(body, dict):
        return False
    scope = body.get("claim_scope")
    return body.get("kill_timing") == KILL_TIMING_AFTER_MAP_SWAP and isinstance(scope, str) and bool(scope.strip())


def require_tamper_claim(body: dict[str, Any]) -> dict[str, Any]:
    """Leave a 2F PASS not graded when it lacks kill_timing or claim_scope.

    FAIL and HOLD stand as they are: the claim fields only bound what a pass
    may claim. The withheld result is kept for the record.
    """
    if body.get("host_result") != "PASS" or tamper_claim_complete(body):
        return body
    body["withheld_host_result"] = "PASS"
    body["setup_invalid"] = True
    body["reason"] = CLAIM_FIELDS_MISSING
    body["host_result"] = "NOT_GRADED"
    body["expectation_met"] = False
    body["classification"] = "not_graded"
    return body


def side_pin_pid(path: str) -> int | None:
    """The pid in <stem>_incoming_<pid>, or None. A pid of 0 is never a process."""
    if not isinstance(path, str) or "_incoming_" not in path:
        return None
    tail = path.rsplit("_incoming_", 1)[1]
    if not tail.isdigit():
        return None
    pid = int(tail)
    return pid if pid > 0 else None


def swap_owner_matches(seen: list[str], loaders: list[dict[str, Any]]) -> bool:
    """The side pins seen during the wait belong to the one running enforce loader.

    loaders lists the running vantio-loader processes as {"host": pid, "ns":
    pid in its own namespace}. The pid is known only when exactly one loader
    runs. At least one new side pin must have been seen, and every one must
    name that loader's host or namespace pid.
    """
    if not isinstance(seen, list) or not isinstance(loaders, list) or len(loaders) != 1:
        return False
    owner = loaders[0]
    if not isinstance(owner, dict):
        return False
    pids = {pid for pid in (owner.get("host"), owner.get("ns")) if type(pid) is int and pid > 0}
    if not pids or not seen:
        return False
    return all(side_pin_pid(path) in pids for path in seen)


def deny_map_swapped(
    before_ids: dict[str, Any],
    before_incoming: list[str],
    ids: dict[str, Any],
    incoming: list[str],
) -> bool:
    """The enforce loader's deny-attr maps are on the canonical pins.

    Both must hold: no side pin exists that was not already there before the
    enforce loader started, and every canonical pin names a map whose id is
    set and differs from the id it had before (when it had one). The ready
    banner prints before this handoff, so the banner alone is not enough.
    """
    if not isinstance(before_ids, dict) or not isinstance(ids, dict):
        return False
    if not isinstance(before_incoming, list) or not isinstance(incoming, list):
        return False
    if any(path not in before_incoming for path in incoming):
        return False
    for stem in DENY_SWAP_STEMS:
        now = ids.get(stem)
        was = before_ids.get(stem)
        if type(now) is not int or now <= 0:
            return False
        if type(was) is int and was > 0 and now == was:
            return False
    return True


def ungraded_egress(battery: str, reason: str) -> dict[str, Any]:
    """A timeout or a dead control. This is not a pass, a fail, or a hold."""
    body = _base(battery)
    body["setup_invalid"] = True
    body["reason"] = reason
    body["host_result"] = "NOT_GRADED"
    body["expectation_met"] = False
    body["classification"] = "not_graded"
    return body


def stderr_has_cgroup_pin(text: str) -> bool:
    """The pin succeeded. A load or pin failure mentions the same name in a longer line."""
    return any(line.strip() == CGROUP_SKB_PROGRAM for line in text.splitlines())


def enforce_banner_ready(text: str) -> bool:
    """SCOPED has been printed and the cgroup program pin line is on stderr.

    Open and openat pin lines are printed before that program is loaded.
    Those lines alone are not a start.
    """
    return "SCOPED (drop enrolled)" in text and stderr_has_cgroup_pin(text)


def cgroup_skb_listed(names: object) -> bool:
    """True when a bpftool name is this program, including the 15-character prefix."""
    if not isinstance(names, list):
        return False
    for name in names:
        if isinstance(name, str) and (name == CGROUP_SKB_PROGRAM or name.startswith(CGROUP_SKB_BPFTOOL_PREFIX)):
            return True
    return False


def grade_container_exit(
    *,
    file_errno: int | None,
    egress_errno: int | None,
    program_listed: bool | None,
    egress_anchor: int = 0,
    while_up_file_errno: int | None = None,
) -> dict[str, Any]:
    """After the loader container exits, before uninstall.

    fail_open is only the case where the secret was denied while the loader
    was up and the same open is allowed after the container exits. An open
    that was already allowed while the container was up is not that result.
    A listing that does not show cgroup_skb_egress_enforce after the stop is
    not that result either. The program is pinned and should still be listed.
    """
    body = _base("r15-container-exit")
    body["file_errno"] = file_errno
    body["egress_errno"] = egress_errno
    body["program_listed"] = program_listed
    body["cgroup_program_held"] = program_listed if isinstance(program_listed, bool) else None
    body["while_up_file_errno"] = while_up_file_errno
    body["measured_before_uninstall"] = True
    if while_up_file_errno != 13:
        body["classification"] = "deny_not_engaged"
        body["reason"] = "deny_not_engaged_while_up"
        body["host_result"] = "NOT_GRADED"
        body["expectation_met"] = False
        body["file_open"] = "not_denied_while_up"
        body["egress"] = "not_graded"
        return body
    if program_listed is False:
        body["classification"] = "program_not_listed"
        body["reason"] = "cgroup_program_absent_after_stop"
        body["host_result"] = "RECORDED"
        body["expectation_met"] = False
        body["file_open"] = "denied" if file_errno == 13 else "allowed" if file_errno == 0 else "other"
        body["egress"] = "not_graded"
        return body
    file_denied = file_errno == 13
    file_allowed = file_errno == 0
    egress_denied = egress_errno in (1, 13, 111) or _recorded_egress_block(egress_errno, egress_anchor)
    egress_allowed = egress_errno == 0
    if file_errno is None or egress_errno is None:
        classification = "unmeasured"
    elif (file_denied or egress_denied) and (file_allowed or egress_allowed):
        classification = "mixed"
    elif file_denied or egress_denied:
        classification = "fail_closed"
    elif file_allowed and egress_allowed:
        classification = "fail_open"
    else:
        classification = "unmeasured"
    body["classification"] = classification
    body["file_open"] = "denied" if file_denied else "allowed" if file_allowed else "other"
    body["egress"] = "denied" if egress_denied else "allowed" if egress_allowed else "other"
    body["host_result"] = "RECORDED"
    body["expectation_met"] = False
    return body


def grade_rollback_gap(*, from_pin: str, to_seal: str, rollback_image_present: bool) -> dict[str, Any]:
    """e0b19d55 to the working seal and back needs a second image on the guest.

    The public installer pin is not a seal tar. Reloading the one seal tar
    the runner copied is not that upgrade.
    """
    body = _base("2c-upgrade-rollback")
    body["from_pin"] = from_pin
    body["to_seal"] = to_seal
    body["public_pin_unchanged"] = from_pin == PUBLIC_INSTALLER_PIN
    body["host_rollback"] = "NOT_RUN"
    body["upgrade_pass"] = False
    if from_pin != PUBLIC_INSTALLER_PIN:
        body["action"] = "HOLD"
        body["reason"] = "public_pin_mismatch"
        body["host_result"] = "FAIL"
        return body
    if to_seal != WORKING_SEAL:
        body["action"] = "HOLD"
        body["reason"] = "seal"
        body["host_result"] = "FAIL"
        return body
    if not rollback_image_present:
        body["action"] = "HOLD"
        body["reason"] = "rollback_image_absent"
        body["host_result"] = "HOLD"
        return body
    body["action"] = "HOLD"
    body["reason"] = "rollback_image_not_graded"
    body["host_result"] = "HOLD"
    return body


CYCLE_STEPS = ("baseline", "upgrade", "rollback", "reupgrade")
PIN_STEPS = ("baseline", "rollback")
# The public pin (e0b19d55, PE 06696d5) predates `vantio-loader --uninstall`
# and the stderr pin line. Its own banner is these stdout lines. Its own
# removal is SIGINT on the container, which ends with PUBLIC_PIN_DETACHED and
# says the pinned maps remain. The bpftool and bpffs census is still required.
PUBLIC_PIN_SCOPED_LINE = "tc enforce : SCOPED (drop enrolled)"
PUBLIC_PIN_CGROUP_SKB_LINE = "cgroup_skb : egress enforce ON"
PUBLIC_PIN_ACTIVE_LINE = "Phantom Engine active"
PUBLIC_PIN_DETACHED = "Detached cleanly."
PUBLIC_PIN_UNINSTALL = "public_pin_sigint"
SEAL_UNINSTALL = "product_uninstall"
SEAL_UNINSTALL_ATTESTATION = "UNINSTALL_VERIFIED"
# The pin's SIGINT removal says its pinned maps remain, so programs or pins it
# leaves behind are a named finding, not a 2C fail. 2C passes only when the
# seal's own product uninstall after it leaves the census fully clean,
# including whatever the pin left. That is the customer upgrade path.
PUBLIC_PIN_RESIDUE_FINDING = "public_pin_leaves_bpf_residue"
# The pin (PE 06696d5) enforces, but its denies were not attributed in
# CHAIN8 2C 39864267674. On a pin step only, an enforced open (errno 13)
# after the pin's own banner that is not attributed is this named finding,
# not a 2C fail. A seal step still needs an
# attributed deny.
PUBLIC_PIN_UNATTRIBUTED_FINDING = "public_pin_unattributed_deny"
# Every named finding grade_image_cycle can emit. GCP pins its allowlist to this.
CYCLE_FINDINGS = frozenset({PUBLIC_PIN_RESIDUE_FINDING, PUBLIC_PIN_UNATTRIBUTED_FINDING})


def public_pin_banner_ready(text: str) -> bool:
    """The public pin printed its own SCOPED start with the cgroup_skb program loaded.

    That pin prints these lines on stdout after the cgroup program loaded and
    the root attach ran. It never prints the newer stderr pin line.
    """
    return (
        PUBLIC_PIN_ACTIVE_LINE in text
        and PUBLIC_PIN_SCOPED_LINE in text
        and PUBLIC_PIN_CGROUP_SKB_LINE in text
    )


def uninstall_attestation(name: str, uninstall: dict[str, Any]) -> str:
    """The line this step's own uninstall must print.

    Only a pin step may use the pin's SIGINT contract. A seal step always
    needs UNINSTALL_VERIFIED. Either way the census must be clean.
    """
    if name in PIN_STEPS and uninstall.get("contract") == PUBLIC_PIN_UNINSTALL:
        return PUBLIC_PIN_DETACHED
    return SEAL_UNINSTALL_ATTESTATION


def census_fully_clean(uninstall: dict[str, Any]) -> bool:
    """Every removal_census field read back clean: bpftool ran, nothing listed.

    Missing fields are not clean. This is the bar for the seal's uninstall.
    """
    rc = uninstall.get("bpftool_rc")
    return (
        uninstall.get("verified_removed") is True
        and uninstall.get("docker_ps_failed") is not True
        and type(rc) is int
        and rc == 0
        and uninstall.get("loader_programs") == []
        and uninstall.get("bpffs_vantio") == []
        and uninstall.get("docker_containers") == ""
    )


def public_pin_residue(uninstall: dict[str, Any]) -> dict[str, Any] | None:
    """Census detail when the pin's own removal left only bpf programs or pins.

    The pin must have printed its own shutdown line, bpftool must have run,
    bpffs must have been listed, and no container may remain. Anything else
    is not residue; it is an unreadable or unfinished removal and still fails.
    None means there is no residue to record (or it is not recordable).
    """
    if uninstall.get("contract") != PUBLIC_PIN_UNINSTALL:
        return None
    if PUBLIC_PIN_DETACHED not in str(uninstall.get("tail") or ""):
        return None
    programs = uninstall.get("loader_programs")
    paths = uninstall.get("bpffs_vantio")
    if not isinstance(programs, list) or not isinstance(paths, list):
        return None
    if not all(isinstance(item, str) and item for item in programs + paths):
        return None
    if "find_failed" in paths:
        return None
    rc = uninstall.get("bpftool_rc")
    if type(rc) is not int or rc != 0 or uninstall.get("docker_containers") != "":
        return None
    if uninstall.get("docker_ps_failed") is True:
        return None
    if not programs and not paths:
        return None
    return {
        "bpffs_vantio": list(paths),
        "bpftool_rc": 0,
        "docker_containers": "",
        "loader_programs": list(programs),
    }


def public_pin_unattributed(name: str, step: dict[str, Any]) -> bool:
    """A pin step that enforced on its own banner but whose deny names no pid.

    Only baseline or rollback on the public pin archive. The open must have
    returned errno 13, the pin's own banner must have been seen (setup_error
    is exactly ""), and attributed must be exactly False. Anything else,
    including a missing measurement, is not this finding.
    """
    errno = step.get("file_errno")
    return (
        name in PIN_STEPS
        and step.get("archive_sha256") == PUBLIC_INSTALLER_PIN
        and type(errno) is int
        and errno == 13
        and step.get("setup_error") == ""
        and step.get("attributed") is False
    )


def grade_image_cycle(steps: list[dict[str, Any]]) -> dict[str, Any]:
    """Upgrade, roll back, and upgrade again on two different archives.

    Each step has already been measured. Every step must start and enforce
    on its own image. A pin step's own removal may leave bpf programs or pins
    (the pin says its pinned maps remain); that is recorded as the named
    finding public_pin_leaves_bpf_residue with the census detail. A pin
    step that enforced (errno 13) on its own banner without attribution is
    the named finding public_pin_unattributed_deny. A seal step must deny
    with attribution, and its product uninstall must leave the census fully
    clean, which includes anything the pin left. lab_pass stays false.
    """
    body = _base("2c-upgrade-rollback")
    body["from_pin"] = PUBLIC_INSTALLER_PIN
    body["to_seal"] = WORKING_SEAL
    body["public_pin_unchanged"] = True
    body["host_rollback"] = "NOT_RUN"
    body["upgrade_pass"] = False
    body["steps"] = steps
    body["findings"] = []
    names = [step.get("name") for step in steps] if isinstance(steps, list) else []
    if names != list(CYCLE_STEPS):
        body["action"] = "FAIL"
        body["host_result"] = "FAIL"
        body["reason"] = "cycle_incomplete"
        return body
    expected = {
        "baseline": PUBLIC_INSTALLER_PIN,
        "upgrade": WORKING_SEAL,
        "rollback": PUBLIC_INSTALLER_PIN,
        "reupgrade": WORKING_SEAL,
    }
    pin_ids: list[str] = []
    seal_ids: list[str] = []
    reasons: list[str] = []
    for step in steps:
        name = str(step.get("name"))
        if step.get("archive_sha256") != expected[name]:
            reasons.append(f"{name}_digest")
        image_id = step.get("image_id")
        if not isinstance(image_id, str) or not image_id.startswith("sha256:") or len(image_id) < 16:
            reasons.append(f"{name}_image")
        elif name in {"baseline", "rollback"}:
            pin_ids.append(image_id)
        else:
            seal_ids.append(image_id)
        if step.get("file_errno") != 13 or step.get("attributed") is not True:
            if public_pin_unattributed(name, step):
                body["findings"].append({"finding": PUBLIC_PIN_UNATTRIBUTED_FINDING, "step": name, "file_errno": 13})
            else:
                reasons.append(f"{name}_enforcement")
        uninstall = step.get("uninstall") if isinstance(step.get("uninstall"), dict) else {}
        tail = str(uninstall.get("tail") or "")
        attested = uninstall_attestation(name, uninstall) in tail
        if name in PIN_STEPS and uninstall.get("contract") == PUBLIC_PIN_UNINSTALL:
            residue = public_pin_residue(uninstall)
            if residue is not None and attested:
                body["findings"].append({"finding": PUBLIC_PIN_RESIDUE_FINDING, "step": name, **residue})
            elif not attested or not census_fully_clean(uninstall):
                reasons.append(f"{name}_uninstall")
        elif not attested or not census_fully_clean(uninstall):
            reasons.append(f"{name}_uninstall")
    if (
        len(pin_ids) != 2
        or len(seal_ids) != 2
        or len(set(pin_ids)) != 1
        or len(set(seal_ids)) != 1
        or pin_ids[0] == seal_ids[0]
    ):
        reasons.append("image_identity")
    body["host_rollback"] = "RAN"
    if reasons:
        body["action"] = "FAIL"
        body["host_result"] = "FAIL"
        body["reason"] = reasons[0]
        body["reasons"] = reasons
        return body
    body["action"] = "RECORDED"
    body["host_result"] = "RECORDED"
    body["reason"] = "upgrade_rollback_reupgrade"
    body["upgrade_pass"] = True
    return body


def grade_upgrade(
    *,
    seal_sha256: str,
    image_before: str,
    image_after: str,
    deny_before: int | None,
    deny_after: int | None,
    attributed_before: bool | None = None,
    attributed_after: bool | None = None,
) -> dict[str, Any]:
    """Same seal loaded twice is not an upgrade. A process restart is separate."""
    body = _base("2c-upgrade-rollback")
    same_bytes = seal_sha256 == WORKING_SEAL
    same_image = bool(image_before) and image_before == image_after
    restart_held = deny_before == 13 and deny_after == 13
    if attributed_before is False or attributed_after is False:
        restart_held = False
    body["process_restart_held"] = restart_held
    body["restart_attributed"] = (
        restart_held and attributed_before is True and attributed_after is True
    )
    body["host_rollback"] = "NOT_RUN"
    body["upgrade_pass"] = False
    if same_bytes and same_image:
        body["action"] = "HOLD"
        body["reason"] = "same_seal_is_not_an_upgrade"
        body["host_result"] = "HOLD"
        return body
    body["action"] = "HOLD"
    body["reason"] = "seal_or_image_mismatch"
    body["host_result"] = "FAIL"
    return body


def _file_open_failed(file_errno: int | None, file_attributed: bool | None) -> dict[str, Any] | None:
    """A protected open after the loader is gone. Errno 0 is silent.

    file_attributed is true only when a ledger DENIED row, or a deny-attr row,
    names this pid and a non-zero lineage anchor. A pid alone is not that.
    """
    if file_errno is None:
        return None
    if file_errno == 0:
        return {
            "classification": "silent_weakening",
            "expectation_met": False,
            "file_open": "allowed",
            "host_result": "FAIL",
        }
    if file_errno == 13 and file_attributed is False:
        return {
            "classification": "unattributed_deny",
            "expectation_met": False,
            "file_open": "unattributed",
            "host_result": "FAIL",
        }
    if file_errno == 13 and file_attributed is True:
        return {"file_open": "attributed_deny"}
    return None


def _recorded_egress_block(errno: int | None, anchor: int) -> bool:
    """A connect timeout with an egress deny-attr row is a block, not a missing result."""
    return (
        errno == 110
        and isinstance(anchor, int)
        and not isinstance(anchor, bool)
        and anchor > 0
    )


def grade_crash(
    *,
    enrolled_errno: int | None,
    unenrolled_errno: int | None,
    file_errno: int | None = None,
    file_attributed: bool | None = None,
    enrolled_block_anchor: int = 0,
) -> dict[str, Any]:
    """After the loader is dead. Enrolled traffic that completes is a fail."""
    body = _base("2d-crash-recovery")
    enrolled = egress_word(enrolled_errno)
    if _recorded_egress_block(enrolled_errno, enrolled_block_anchor):
        enrolled = "denied"
        body["net_block_anchor"] = enrolled_block_anchor
    unenrolled = egress_word(unenrolled_errno)
    body["enrolled_egress"] = enrolled
    body["unenrolled_egress"] = unenrolled
    file_row = _file_open_failed(file_errno, file_attributed)
    if file_row is not None and file_row.get("file_open") != "attributed_deny":
        body.update(file_row)
        return body
    block = egress_grade_block(unenrolled_errno, enrolled_errno)
    if block is not None and not (block == "enrolled_egress_timeout" and enrolled == "denied"):
        refused = ungraded_egress("2d-crash-recovery", block)
        refused["enrolled_egress"] = enrolled
        refused["unenrolled_egress"] = unenrolled
        if file_row is not None:
            refused["file_open"] = file_row.get("file_open")
        return refused
    if file_row is not None:
        body["file_open"] = "attributed_deny"
    if enrolled == "allowed":
        body["classification"] = "silent_weakening"
        body["expectation_met"] = False
        body["host_result"] = "FAIL"
        return body
    if unenrolled != "allowed":
        body["classification"] = "inconclusive"
        body["expectation_met"] = False
        body["host_result"] = "HOLD"
        return body
    body["classification"] = "fail_closed"
    body["expectation_met"] = True
    body["host_result"] = "PASS"
    return body


def grade_performance(*, runtime_seconds: float, host_count: int, sample_count: int) -> dict[str, Any]:
    body = _base("2e-performance")
    body["host_count"] = host_count
    body["max_runtime_seconds"] = MAX_PERF_SECONDS
    body["sample_count"] = sample_count
    body["source"] = "host_measured"
    if host_count != 1 or sample_count < 1:
        body["result"] = "REJECTED"
        body["reason"] = "host_count"
        body["host_result"] = "FAIL"
        return body
    if runtime_seconds < 0 or runtime_seconds > MAX_PERF_SECONDS:
        body["result"] = "REJECTED"
        body["reason"] = "runtime_bound"
        body["host_result"] = "FAIL"
        return body
    body["result"] = "RECORDED"
    body["reason"] = "within_bound"
    body["runtime_seconds"] = round(runtime_seconds, 3)
    body["host_result"] = "PASS"
    return body


def grade_tamper(
    *,
    enrolled_errno: int | None,
    unenrolled_errno: int | None,
    loader_up: bool,
    policy_malformed: bool = False,
    file_errno: int | None = None,
    file_attributed: bool | None = None,
    enrolled_block_anchor: int = 0,
) -> dict[str, Any]:
    body = _base("2f-tamper")
    enrolled = egress_word(enrolled_errno)
    if _recorded_egress_block(enrolled_errno, enrolled_block_anchor):
        enrolled = "denied"
        body["net_block_anchor"] = enrolled_block_anchor
    unenrolled = egress_word(unenrolled_errno)
    body["enrolled_egress"] = enrolled
    body["unenrolled_egress"] = unenrolled
    file_row = _file_open_failed(file_errno, file_attributed)
    if file_row is not None and file_row.get("file_open") != "attributed_deny":
        body.update(file_row)
        return body
    block = egress_grade_block(unenrolled_errno, enrolled_errno)
    if block is not None and not (block == "enrolled_egress_timeout" and enrolled == "denied"):
        refused = ungraded_egress("2f-tamper", block)
        refused["enrolled_egress"] = enrolled
        refused["unenrolled_egress"] = unenrolled
        if file_row is not None:
            refused["file_open"] = file_row.get("file_open")
        return refused
    if file_row is not None:
        body["file_open"] = "attributed_deny"
    if enrolled == "allowed":
        body["classification"] = "silent_weakening"
        body["expectation_met"] = False
        body["host_result"] = "FAIL"
        return body
    if policy_malformed and enrolled == "denied":
        body["classification"] = "detected_rejected"
        body["expectation_met"] = True
        body["host_result"] = "PASS"
        return body
    if loader_up or unenrolled != "allowed":
        body["classification"] = "inconclusive"
        body["expectation_met"] = False
        body["host_result"] = "HOLD"
        return body
    body["classification"] = "fail_closed"
    body["expectation_met"] = True
    body["host_result"] = "PASS"
    return body


def grade_distro(facts: dict[str, Any]) -> dict[str, Any]:
    body = _base("2g-distro")
    body["distro"] = facts.get("distro")
    body["kernel"] = facts.get("kernel")
    body["live_probe"] = facts.get("live_probe") is True
    required = ("distro", "kernel", "btf", "lsm", "seal")
    missing = [key for key in required if not facts.get(key)]
    if facts.get("live_probe") is not True or missing:
        body["result"] = "NOT_PROVED"
        body["reason"] = "live_probe_required" if facts.get("live_probe") is not True else "missing_fields"
        body["missing"] = missing
        body["host_result"] = "HOLD"
        return body
    if facts.get("seal") != WORKING_SEAL:
        body["result"] = "NOT_PROVED"
        body["reason"] = "seal"
        body["host_result"] = "FAIL"
        return body
    if facts.get("descendant_pass") or facts.get("docker_child_pass"):
        body["result"] = "REJECTED"
        body["reason"] = "descendant_or_docker_child"
        body["host_result"] = "FAIL"
        return body
    held = (
        facts.get("enrolled_errno") == 13
        and facts.get("unenrolled_errno") == 0
        and facts.get("removed") is True
        and facts.get("btf") is True
    )
    body["result"] = "RECORDED" if held else "NOT_PROVED"
    body["reason"] = "live_probe_present" if held else "enforcement_or_removal"
    body["host_result"] = "PASS" if held else "FAIL"
    body["ami"] = facts.get("ami")
    return body
