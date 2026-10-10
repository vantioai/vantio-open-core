#!/usr/bin/env python3
"""Score one clean-host phase observation. No AWS and no loader.

A fixture result is not a host pass. These functions only classify numbers
the guest already measured. lab_pass stays false. The ceiling stays
INTERNAL_CLEAN_HOST_PROOF.
"""

from __future__ import annotations

from typing import Any

WORKING_SEAL = "ec22e75c4eea423676a20752c7f33b9f5608ba67f3a9d5b32e3ff973eb1990ca"
CLAIM_CEILING = "INTERNAL_CLEAN_HOST_PROOF"
PHASES = (
    "2c-upgrade-rollback",
    "2d-crash-recovery",
    "2e-performance",
    "2f-tamper",
    "2g-distro",
)
MAX_PERF_SECONDS = 900


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
DENY_ATTR_SIZE = 40


def deny_record_names(record: bytes, pid: int) -> bool:
    """Pinned DenyAttr: pid at 0, timestamp_ns at 16, kind at 32."""
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return False
    if len(record) < DENY_ATTR_SIZE:
        return False
    got = int.from_bytes(record[0:4], "little")
    timestamp = int.from_bytes(record[16:24], "little")
    kind = int.from_bytes(record[32:36], "little")
    return got == pid and timestamp != 0 and kind in (DENY_KIND_FILE, DENY_KIND_SELF)


def egress_word(errno: int | None) -> str:
    if errno in (1, 13):
        return "denied"
    if errno == 0:
        return "allowed"
    return "no_response"


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
    """A protected open after the loader is gone. Errno 0 is silent. EACCES needs a pid."""
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
    if file_row is not None:
        if file_row.get("file_open") == "attributed_deny":
            body["file_open"] = "attributed_deny"
        else:
            body.update(file_row)
            return body
    if enrolled == "allowed":
        body["classification"] = "silent_weakening"
        body["expectation_met"] = False
        body["host_result"] = "FAIL"
        return body
    if enrolled == "no_response" or unenrolled != "allowed":
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
    if file_row is not None:
        if file_row.get("file_open") == "attributed_deny":
            body["file_open"] = "attributed_deny"
        else:
            body.update(file_row)
            return body
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
    if loader_up or enrolled == "no_response" or unenrolled != "allowed":
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
