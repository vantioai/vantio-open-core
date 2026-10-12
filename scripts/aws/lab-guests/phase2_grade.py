#!/usr/bin/env python3
"""Score one clean-host phase observation. No AWS and no loader.

A fixture result is not a host pass. These functions only classify numbers
the guest already measured. lab_pass stays false. The ceiling stays
INTERNAL_CLEAN_HOST_PROOF.
"""

from __future__ import annotations

import ipaddress
from typing import Any

WORKING_SEAL = "8d2fc4acb61606681ae474c399364c7b1e185d0c693b8dfe40bb5846b42723e9"
CLAIM_CEILING = "INTERNAL_CLEAN_HOST_PROOF"
PHASES = (
    "2c-upgrade-rollback",
    "2d-crash-recovery",
    "2e-performance",
    "2f-tamper",
    "2g-distro",
)
MAX_PERF_SECONDS = 900
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


def ungraded_egress(battery: str, reason: str) -> dict[str, Any]:
    """A timeout or a dead control. This is not a pass, a fail, or a hold."""
    body = _base(battery)
    body["setup_invalid"] = True
    body["reason"] = reason
    body["host_result"] = "NOT_GRADED"
    body["expectation_met"] = False
    body["classification"] = "not_graded"
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


def grade_crash(
    *,
    enrolled_errno: int | None,
    unenrolled_errno: int | None,
    file_errno: int | None = None,
    file_attributed: bool | None = None,
) -> dict[str, Any]:
    """After the loader is dead. Enrolled traffic that completes is a fail."""
    body = _base("2d-crash-recovery")
    enrolled = egress_word(enrolled_errno)
    unenrolled = egress_word(unenrolled_errno)
    body["enrolled_egress"] = enrolled
    body["unenrolled_egress"] = unenrolled
    file_row = _file_open_failed(file_errno, file_attributed)
    if file_row is not None and file_row.get("file_open") != "attributed_deny":
        body.update(file_row)
        return body
    block = egress_grade_block(unenrolled_errno, enrolled_errno)
    if block is not None:
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
) -> dict[str, Any]:
    body = _base("2f-tamper")
    enrolled = egress_word(enrolled_errno)
    unenrolled = egress_word(unenrolled_errno)
    body["enrolled_egress"] = enrolled
    body["unenrolled_egress"] = unenrolled
    file_row = _file_open_failed(file_errno, file_attributed)
    if file_row is not None and file_row.get("file_open") != "attributed_deny":
        body.update(file_row)
        return body
    block = egress_grade_block(unenrolled_errno, enrolled_errno)
    if block is not None:
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
