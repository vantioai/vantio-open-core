"""Nine-step stranger-host grade.

A passing grade is still Roadmap. host_proof stays false here. verify()
is the only place that can report a signed bundle ready for outside review.
"""

from __future__ import annotations

import hashlib
from typing import Mapping

from constants import (
    ALLOW_CASES,
    CEILING_PATH,
    COMPARISON_SEAL,
    DENY_CASES,
    ENROLLED_UID,
    HEX64_RE,
    LABEL,
    MAX_BYTES,
    PLUMBING_ONLY_SEAL,
    PUBLIC_PIN,
    TIER,
    TRACKING_SEAL,
    WORKING_SEAL,
)
from facts import bpf_in_cmdline, bpf_in_lsm_list, boot_id_ok, exact_int, image_is_exact, lsm_word, parse_lockdown, positive_int


def _dedupe(reasons: list[str]) -> list[str]:
    ordered: list[str] = []
    for reason in reasons:
        if reason not in ordered:
            ordered.append(reason)
    return ordered


def _step(number: int, name: str, reasons: list[str], notes: list[str] | None = None, **extra: object) -> dict[str, object]:
    clean = _dedupe(reasons)
    body: dict[str, object] = {
        "name": name,
        "notes": list(notes or []),
        "reasons": clean,
        "result": "FAIL" if clean else "PASS",
        "step": number,
    }
    body.update(extra)
    return body


def _mapping(value: object) -> Mapping[str, object] | None:
    if isinstance(value, Mapping):
        return value
    return None


def grade_preflight(host: object) -> dict[str, object]:
    reasons: list[str] = []
    body = _mapping(host)
    if body is None:
        return _step(1, "preflight", ["bpf_lsm_inactive"])
    enabled = body.get("enabled_lsm")
    if not isinstance(enabled, str) or not bpf_in_lsm_list(enabled):
        reasons.append("bpf_lsm_inactive")
    btf = body.get("btf_bytes")
    if type(btf) is not int or btf <= 0:
        reasons.append("btf_missing")
    if body.get("cgroup_fstype") != "cgroup2fs":
        reasons.append("cgroup_v2_missing")
    raw = body.get("lockdown_raw")
    mode = body.get("lockdown_mode")
    try:
        parsed = parse_lockdown(raw) if isinstance(raw, str) else None
    except ValueError:
        parsed = None
    if parsed is None or parsed != mode:
        reasons.append("lockdown_unreadable")
    elif mode == "confidentiality":
        reasons.append("lockdown_confidentiality")
    if body.get("bpffs") is not True:
        reasons.append("bpffs_missing")
    image = _mapping(body.get("image")) or {}
    if not image_is_exact(image.get("exact"), source=image.get("source")):
        reasons.append("image_exact_missing")
    return _step(1, "preflight", reasons)


def grade_seal(seal: object) -> dict[str, object]:
    body = _mapping(seal)
    if body is None or body.get("present") is not True:
        return _step(2, "seal", ["seal_file_missing"])
    reasons: list[str] = []
    digest = body.get("digest")
    if not isinstance(digest, str) or HEX64_RE.fullmatch(digest) is None:
        reasons.append("seal_digest_malformed")
    elif digest == PUBLIC_PIN:
        reasons.append("seal_is_public_pin")
    elif digest == PLUMBING_ONLY_SEAL:
        reasons.append("seal_is_plumbing_only")
    elif digest == TRACKING_SEAL:
        reasons.append("seal_is_tracking")
    elif body.get("file_sha256") != digest:
        reasons.append("seal_bytes_mismatch")
    return _step(
        2,
        "seal",
        reasons,
        working_seal=digest == WORKING_SEAL,
        comparison_seal=digest == COMPARISON_SEAL,
    )


def _unchanged_open_ok(unchanged: Mapping[str, object]) -> bool:
    probe = unchanged.get("probe")
    if probe == "open_ok":
        return True
    nested = _mapping(probe)
    if nested is not None and nested.get("result") == "open_ok":
        return True
    return unchanged.get("result") == "open_ok"


def grade_enterprise(rows: object) -> dict[str, object]:
    body = _mapping(rows)
    if body is None:
        return _step(3, "enforcement", ["enterprise_rows_missing"])
    reasons: list[str] = []
    grant = _mapping(body.get("grant_loader"))
    if grant is None or grant.get("rc") != 0 or isinstance(grant.get("rc"), bool):
        reasons.append("grant_loader")
    if grant is None or grant.get("audit") is not True:
        reasons.append("grant_audit")
    if grant is None or grant.get("path_observe") is not True:
        reasons.append("grant_observe")
    grant_probe = _mapping(body.get("grant_probe"))
    if grant_probe is None or not exact_int(grant_probe.get("nobody_errno"), 0):
        reasons.append("grant_errno")
    unchanged = _mapping(body.get("unchanged"))
    if unchanged is None or not _unchanged_open_ok(unchanged):
        reasons.append("unchanged_probe")
    if unchanged is None or unchanged.get("conflict_reason") != "VERSION_CONFLICT":
        reasons.append("conflict_reason")
    if unchanged is None or "generation" not in unchanged or "generation_before" not in unchanged:
        reasons.append("generation_moved")
    elif unchanged.get("generation") != unchanged.get("generation_before") or isinstance(unchanged.get("generation"), bool):
        reasons.append("generation_moved")
    freeze = _mapping(body.get("freeze"))
    if freeze is None or freeze.get("widen_reason") != "FROZEN":
        reasons.append("freeze_reason")
    unreachable = _mapping(body.get("unreachable"))
    if unreachable is None or unreachable.get("reason") != "ENTERPRISE_UNREACHABLE":
        reasons.append("unreachable_reason")
    revoke = _mapping(body.get("revoke")) or {}
    probe = _mapping(revoke.get("probe")) or {}
    if not exact_int(probe.get("nobody_errno"), 13):
        reasons.append("revoke_errno")
    path = probe.get("path") if isinstance(probe.get("path"), str) else body.get("path")
    if path != CEILING_PATH:
        reasons.append("deny_path")
    uid = probe.get("uid") if "uid" in probe else body.get("uid")
    if not exact_int(uid, ENROLLED_UID):
        reasons.append("deny_uid")
    event = _mapping(revoke.get("block_event")) or {}
    if event.get("ActionTaken") != "DENIED" or not positive_int(event.get("Pid")) or not positive_int(event.get("lineage_anchor")):
        reasons.append("deny_not_held")
    raw_reasons = body.get("fail_reasons", [])
    notes: list[str] = []
    if not isinstance(raw_reasons, list) or any(not isinstance(item, str) for item in raw_reasons):
        reasons.append("fail_reasons")
    else:
        extra = [item for item in raw_reasons if item != "programs_not_removed"]
        if extra:
            reasons.append("fail_reasons")
        elif "programs_not_removed" in raw_reasons:
            notes.append("harness_fault_candidate")
    return _step(3, "enforcement", reasons, notes)


def _pick(body: Mapping[str, object], key: str) -> object:
    if key in body:
        return body.get(key)
    loader = _mapping(body.get("loader"))
    if loader is None:
        return None
    return loader.get(key)


def grade_loader(rows: object) -> dict[str, object]:
    body = _mapping(rows)
    if body is None:
        return _step(4, "loader", ["loader_kill", "loader_restart", "deny_attr_post_kill"])
    reasons: list[str] = []
    if _pick(body, "loader_kill") != "held":
        reasons.append("loader_kill")
    if _pick(body, "loader_restart") != "held":
        reasons.append("loader_restart")
    if _pick(body, "deny_attr_post_kill") is not True:
        reasons.append("deny_attr_post_kill")
    return _step(4, "loader", reasons)


def _cases(body: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    found: dict[str, Mapping[str, object]] = {}
    raw = body.get("cases")
    if not isinstance(raw, list):
        return found
    for item in raw:
        mapped = _mapping(item)
        if mapped is None:
            continue
        name = mapped.get("name")
        if isinstance(name, str):
            found[name] = mapped
    return found


def _grade_measure(body: Mapping[str, object] | None, *, expected_boot: str | None) -> list[str]:
    if body is None:
        return ["descendant_rows_missing"]
    reasons: list[str] = []
    if body.get("failed_cases") != []:
        reasons.append("failed_cases")
    found = _cases(body)
    if not isinstance(body.get("cases"), list):
        reasons.append("case_missing")
    for name in DENY_CASES:
        item = found.get(name)
        if item is None:
            reasons.append("case_missing")
            continue
        if item.get("skipped") is True:
            reasons.append("case_skipped")
        if item.get("pass") is not True:
            reasons.append("case_not_passed")
        if not exact_int(item.get("file_errno"), 13):
            reasons.append("file_errno")
        if not exact_int(item.get("net_errno"), 1):
            reasons.append("net_errno")
    for name in ALLOW_CASES:
        item = found.get(name)
        if item is None:
            reasons.append("case_missing")
            continue
        if item.get("skipped") is True:
            reasons.append("case_skipped")
        if item.get("pass") is not True:
            reasons.append("case_not_passed")
        if not exact_int(item.get("file_errno"), 0):
            reasons.append("file_errno")
    if expected_boot is not None and body.get("boot_id") != expected_boot:
        reasons.append("boot_id")
    return reasons


def grade_descendants_pre(rows: object, pre_boot: object) -> dict[str, object]:
    body = _mapping(rows)
    pre = _mapping(body.get("pre")) if body is not None else None
    if pre is None and body is not None and isinstance(body.get("cases"), list):
        pre = body
    expected = pre_boot if isinstance(pre_boot, str) else ""
    return _step(5, "descendants-pre", _grade_measure(pre, expected_boot=expected))


def grade_reboot(boot: object, pre_boot: object, serial_text: str | None = None) -> dict[str, object]:
    body = _mapping(boot)
    if body is None:
        return _step(6, "reboot", ["boot_id"])
    reasons: list[str] = []
    boot_id = body.get("boot_id")
    if not boot_id_ok(boot_id):
        reasons.append("boot_id")
    elif boot_id == pre_boot:
        reasons.append("boot_id_unchanged")
    cmdline = body.get("cmdline") if isinstance(body.get("cmdline"), str) else ""
    if not bpf_in_cmdline(cmdline):
        reasons.append("cmdline_bpf_missing")
    enabled = body.get("enabled_lsm") if isinstance(body.get("enabled_lsm"), str) else ""
    if not bpf_in_lsm_list(enabled):
        reasons.append("lsm_bpf_missing")
    serial = serial_text if serial_text is not None else body.get("serial_log")
    if not isinstance(serial, str) or not serial.strip():
        reasons.append("serial_missing")
    else:
        encoded = serial.encode("utf-8")
        if len(encoded) > MAX_BYTES:
            reasons.append("serial_too_large")
        recorded = body.get("serial_sha256")
        if isinstance(recorded, str) and recorded != hashlib.sha256(encoded).hexdigest():
            reasons.append("serial_boot_mismatch")
        word = lsm_word(cmdline)
        if word is None or word not in serial:
            reasons.append("serial_lsm_missing")
    if body.get("serial_boot_id") != boot_id:
        reasons.append("serial_boot_mismatch")
    return _step(6, "reboot", reasons)


def grade_descendants_post(rows: object, boot: object) -> dict[str, object]:
    body = _mapping(rows)
    if body is None:
        return _step(7, "descendants-post", ["descendant_rows_missing"])
    reasons: list[str] = []
    if body.get("reboot_observed") is not True:
        reasons.append("reboot_not_observed")
    pre = _mapping(body.get("pre"))
    post = _mapping(body.get("post"))
    live = _mapping(boot).get("boot_id") if _mapping(boot) is not None else None
    post_boot = post.get("boot_id") if post is not None else None
    pre_boot = pre.get("boot_id") if pre is not None else None
    if post is None or pre is None or post_boot == pre_boot or not boot_id_ok(post_boot):
        reasons.append("reboot_not_observed")
    if not isinstance(live, str) or post_boot != live:
        reasons.append("stale_rows")
    reasons.extend(_grade_measure(post, expected_boot=None))
    return _step(7, "descendants-post", reasons)


def grade_uninstall(record: object) -> dict[str, object]:
    body = _mapping(record)
    if body is None:
        return _step(8, "uninstall", ["uninstall_output_missing"], removal="NOT_REMOVED")
    reasons: list[str] = []
    if body.get("uninstall_verified_line") is not True:
        reasons.append("uninstall_not_verified")
    lines = body.get("bpftool_vantio_lines")
    if not isinstance(lines, list):
        reasons.append("bpftool_missing")
    elif lines:
        reasons.append("bpftool_vantio_present")
    pins = body.get("bpffs_vantio_names")
    if not isinstance(pins, list):
        reasons.append("bpffs_pins_missing")
    elif pins:
        reasons.append("bpffs_vantio_present")
    status = "VERIFIED_REMOVED" if not reasons else "NOT_REMOVED"
    notes: list[str] = []
    raw = body.get("fail_reasons") or []
    if status == "VERIFIED_REMOVED" and isinstance(raw, list) and "programs_not_removed" in raw:
        notes.append("harness_fault_candidate")
    return _step(8, "uninstall", reasons, notes, removal=status)


def grade_teardown(record: object) -> dict[str, object]:
    body = _mapping(record)
    if body is None:
        return _step(9, "teardown", ["teardown_missing"])
    reasons: list[str] = []
    if body.get("actor") != "outside_operator":
        reasons.append("teardown_actor")
    if body.get("project_touched_by_vantio") is not False or body.get("vantio_ran_teardown") is not False:
        reasons.append("teardown_ran_by_vantio")
    deleted = body.get("vm_deleted") is True
    restored = (
        body.get("apt_sources_restored") is True
        and body.get("offline_conf_removed") is True
        and body.get("swapfile_removed") is True
    )
    if not deleted and not restored:
        reasons.append("teardown_incomplete")
    return _step(9, "teardown", reasons)


def grade_evidence(
    *,
    host: object,
    seal: object,
    enterprise: object,
    descendant_pre: object,
    boot: object,
    descendant_post: object,
    uninstall: object,
    teardown: object,
    serial_text: str | None = None,
) -> dict[str, object]:
    pre_boot = _mapping(host).get("boot_id") if _mapping(host) is not None else None
    steps = [
        grade_preflight(host),
        grade_seal(seal),
        grade_enterprise(enterprise),
        grade_loader(enterprise),
        grade_descendants_pre(descendant_pre, pre_boot),
        grade_reboot(boot, pre_boot, serial_text),
        grade_descendants_post(descendant_post, boot),
        grade_uninstall(uninstall),
        grade_teardown(teardown),
    ]
    result = "PASS" if all(step["result"] == "PASS" for step in steps) else "FAIL"
    return {
        "host_proof": False,
        "label": LABEL,
        "result": result,
        "steps": steps,
        "tier": TIER,
    }
