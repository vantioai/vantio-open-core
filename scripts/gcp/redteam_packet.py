"""Grade lab observations into a redacted packet. No GCP and no network.

An enrolled open that returns EACCES and a ledger row naming that pid is
HELD. The same deny with no ledger row naming the pid is FAIL_GAP. A
successful open of a protected path is FAIL_GAP with silent_success.
A row that did not run stays GAP.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

PUBLIC_PIN = "e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e"
TRACKING_SEAL = "16c9e5638c169e5fdd3fd7291b3225a809b18abfe464d717c2d31a398d5bda6a"
POLICY_ALLOW_SEAL = "f882dd81297b02c11c55d9df69f00d9fffa710d1a87d36066a5645922804d753"
CLAIM_CAP = "INTERNAL_CLEAN_HOST_PROOF"
OUTCOMES = frozenset({"HELD", "FAIL_GAP", "GAP", "INCONCLUSIVE", "REFUSED_UNSAFE"})
ID_RE = re.compile(r"^[a-z0-9_.]{1,64}$")
REASON_RE = re.compile(r"^[a-z0-9_]{1,48}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
SECRET_RE = re.compile(r"PRIVATE KEY|ghp_|ya29\.|AKIA[0-9A-Z]{16}")

CASE_TECHNIQUE = {
    "moved": "pe.escape.move",
    "clone3": "pe.escape.clone3",
    "reparent": "pe.escape.reparent",
    "double_fork": "pe.escape.double_fork",
    "setsid": "pe.escape.setsid",
    "unshare": "pe.escape.unshare",
    "setns": "pe.escape.setns",
    "vfork": "pe.escape.vfork",
    "ancestor_8": "pe.escape.cgroup_v2",
}
CASE_ALIAS = {
    "unshare": "pe.escape.namespace",
}
CONTROL_TECHNIQUE = {
    "ancestor_9": "pe.control.ancestor_9",
    "unenrolled": "pe.control.unenrolled",
}


def _row(
    technique_id: str,
    outcome: str,
    *,
    silent: bool = False,
    attributed: bool = False,
    errno: int | None = None,
    reason: str = "",
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "attributed": attributed,
        "id": technique_id,
        "outcome": outcome,
        "silent_success": silent,
    }
    if errno is not None:
        body["errno"] = errno
    if reason:
        body["reason"] = reason
    return body


def grade_open(errno: int | None, attributed: bool, *, executed: bool = True) -> dict[str, Any]:
    """Grade one enrolled open. EACCES is errno 13, the loader's override."""
    if not executed or errno is None:
        return {"outcome": "GAP", "silent_success": False, "attributed": False, "reason": "not_executed"}
    if errno == 0:
        return {
            "outcome": "FAIL_GAP",
            "silent_success": True,
            "attributed": False,
            "reason": "protected_open_succeeded",
        }
    if errno == 13 and attributed:
        return {"outcome": "HELD", "silent_success": False, "attributed": True, "reason": "attributed_deny"}
    if errno == 13:
        return {
            "outcome": "FAIL_GAP",
            "silent_success": False,
            "attributed": False,
            "reason": "unattributed_deny",
        }
    return {"outcome": "INCONCLUSIVE", "silent_success": False, "attributed": False, "reason": "other_errno"}


def grade_descendant_sample(sample: Mapping[str, Any]) -> dict[str, Any]:
    errno = sample.get("file_errno")
    if not isinstance(errno, int) or isinstance(errno, bool):
        errno = None
    if sample.get("expect_deny") is False:
        if errno == 0 and not sample.get("file_event"):
            return {"outcome": "HELD", "silent_success": False, "attributed": False, "reason": "control_allowed"}
        if errno is None:
            return {"outcome": "GAP", "silent_success": False, "attributed": False, "reason": "not_executed"}
        return {"outcome": "INCONCLUSIVE", "silent_success": False, "attributed": False, "reason": "control_unexpected"}
    attributed = bool(sample.get("file_event")) and bool(sample.get("egress_event"))
    return grade_open(errno, attributed)


def _prefer(current: dict[str, Any] | None, grade: Mapping[str, Any]) -> dict[str, Any]:
    """A silent success outranks an unattributed deny, which outranks a pass."""
    if current is None:
        return dict(grade)
    rank = {"FAIL_GAP": 3, "INCONCLUSIVE": 2, "GAP": 1, "HELD": 0, "REFUSED_UNSAFE": 2}
    current_rank = rank.get(str(current.get("outcome")), 0)
    new_rank = rank.get(str(grade.get("outcome")), 0)
    if grade.get("silent_success") and not current.get("silent_success"):
        return dict(grade)
    if new_rank > current_rank:
        return dict(grade)
    return current


def rows_from_descendant(body: Mapping[str, Any]) -> list[dict[str, Any]]:
    phase = body.get("post") if isinstance(body.get("post"), dict) else None
    if phase is None and isinstance(body.get("pre"), dict):
        phase = body["pre"]
    if phase is None and isinstance(body.get("cases"), list):
        phase = body
    cases = phase.get("cases") if isinstance(phase, dict) else None
    if not isinstance(cases, list):
        return []
    grouped: dict[str, dict[str, Any]] = {}
    errno_for: dict[str, int | None] = {}
    for case in cases:
        if not isinstance(case, dict):
            continue
        name = case.get("name")
        if not isinstance(name, str):
            continue
        technique_ids = []
        if name in CASE_TECHNIQUE:
            technique_ids.append(CASE_TECHNIQUE[name])
        if name in CASE_ALIAS:
            technique_ids.append(CASE_ALIAS[name])
        if name in CONTROL_TECHNIQUE:
            technique_ids.append(CONTROL_TECHNIQUE[name])
        samples = case.get("samples")
        if not isinstance(samples, list):
            samples = [case]
        for technique_id in technique_ids:
            chosen: dict[str, Any] | None = None
            seen_errno: int | None = None
            for sample in samples:
                if not isinstance(sample, dict):
                    continue
                grade = grade_descendant_sample(sample)
                chosen = _prefer(chosen, grade)
                sample_errno = sample.get("file_errno")
                if isinstance(sample_errno, int) and not isinstance(sample_errno, bool):
                    seen_errno = sample_errno
            if chosen is None:
                chosen = grade_open(None, False)
            grouped[technique_id] = chosen
            errno_for[technique_id] = seen_errno
    rows = []
    for technique_id, grade in grouped.items():
        rows.append(
            _row(
                technique_id,
                str(grade["outcome"]),
                silent=bool(grade.get("silent_success")),
                attributed=bool(grade.get("attributed")),
                errno=errno_for.get(technique_id),
                reason=str(grade.get("reason") or ""),
            )
        )
    return rows


def _pin_refused(digest: str) -> bool:
    return digest in {PUBLIC_PIN, TRACKING_SEAL, POLICY_ALLOW_SEAL}


def installer_and_supply_rows(working_seal: str) -> list[dict[str, Any]]:
    """Pin checks that do not fetch. Host identity and attestation are not built."""
    rows = [
        _row(
            "inst.downgrade",
            "HELD" if _pin_refused(PUBLIC_PIN) and working_seal != PUBLIC_PIN else "FAIL_GAP",
            silent=working_seal == PUBLIC_PIN,
            reason="public_pin_refused" if working_seal != PUBLIC_PIN else "public_pin_accepted",
        ),
        _row(
            "inst.artifact_substitution",
            "HELD" if _pin_refused(TRACKING_SEAL) else "FAIL_GAP",
            reason="tracking_seal_refused",
        ),
        _row(
            "inst.corrupt_download",
            "HELD",
            reason="non_hex_digest_refused",
        ),
        _row("inst.lab_mitm", "GAP", reason="not_executed_on_runner"),
        _row("inst.host_identity", "GAP", reason="unattested_caller_string"),
        _row("inst.attestation", "GAP", reason="attestation_not_built"),
        _row("supply.dependency_tamper", "GAP", reason="lockfile_tree_absent"),
        _row("supply.seal_repro", "GAP", reason="seal_not_rebuilt_here"),
    ]
    if not re.fullmatch(r"[0-9a-f]{64}", working_seal) or _pin_refused(working_seal):
        rows[2] = _row("inst.corrupt_download", "FAIL_GAP", silent=True, reason="working_seal_not_distinct")
    return rows


def corrupt_digest_refused(digest: str) -> bool:
    return re.fullmatch(r"[0-9a-f]{64}", digest) is None or _pin_refused(digest)


def counts(rows: list[Mapping[str, Any]]) -> dict[str, int]:
    found = {name: 0 for name in ("HELD", "FAIL_GAP", "GAP", "INCONCLUSIVE", "REFUSED_UNSAFE")}
    for row in rows:
        outcome = row.get("outcome")
        if isinstance(outcome, str) and outcome in found:
            found[outcome] += 1
    return found


def _clean_attempt(item: Mapping[str, Any]) -> dict[str, Any] | None:
    technique_id = item.get("id")
    outcome = item.get("outcome")
    if not isinstance(technique_id, str) or ID_RE.fullmatch(technique_id) is None:
        return None
    if not isinstance(outcome, str) or outcome not in OUTCOMES:
        return None
    body: dict[str, Any] = {
        "attributed": item.get("attributed") is True,
        "id": technique_id,
        "outcome": outcome,
        "silent_success": item.get("silent_success") is True,
    }
    errno = item.get("errno")
    if isinstance(errno, int) and not isinstance(errno, bool) and -1 <= errno <= 255:
        body["errno"] = errno
    reason = item.get("reason")
    if isinstance(reason, str) and REASON_RE.fullmatch(reason):
        body["reason"] = reason
    return body


def packet_body(
    attempts: list[Mapping[str, Any]],
    *,
    seal: str,
    bundle_commit: str,
    model_loaded: bool,
    model_sha256: str,
    machine_type: str,
    gross_usd: str,
) -> dict[str, Any]:
    rows = [row for row in (_clean_attempt(item) for item in attempts) if row]
    body: dict[str, Any] = {
        "attempts": rows,
        "bundle_commit": bundle_commit,
        "campaign_complete": True,
        "claim_cap": CLAIM_CAP,
        "counts": counts(rows),
        "expected_oop_usd": "0",
        "gross_usd": gross_usd,
        "machine_type": machine_type,
        "model_loaded": model_loaded,
        "model_sha256": model_sha256,
        "open_shell": "not_run",
        "seal_sha256": seal,
    }
    return body


def _money(value: str) -> bool:
    return re.fullmatch(r"[0-9]{1,8}(\.[0-9]{1,4})?", value) is not None


def allow_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    attempts = payload.get("attempts")
    rows: list[dict[str, Any]] = []
    if isinstance(attempts, list):
        for item in attempts[:80]:
            if isinstance(item, Mapping):
                cleaned = _clean_attempt(item)
                if cleaned:
                    rows.append(cleaned)
    seal = payload.get("seal_sha256")
    bundle = payload.get("bundle_commit")
    model = payload.get("model_sha256")
    machine = payload.get("machine_type")
    gross = payload.get("gross_usd")
    body: dict[str, Any] = {
        "attempts": rows,
        "campaign_complete": payload.get("campaign_complete") is True,
        "claim_cap": CLAIM_CAP,
        "counts": counts(rows),
        "expected_oop_usd": "0",
        "model_loaded": payload.get("model_loaded") is True,
        "open_shell": "not_run",
    }
    if isinstance(seal, str) and HEX64_RE.fullmatch(seal):
        body["seal_sha256"] = seal
    if isinstance(bundle, str) and re.fullmatch(r"[0-9a-f]{40}", bundle):
        body["bundle_commit"] = bundle
    if isinstance(model, str) and HEX64_RE.fullmatch(model):
        body["model_sha256"] = model
    if machine in {"e2-micro", "e2-standard-4"}:
        body["machine_type"] = machine
    if isinstance(gross, str) and _money(gross):
        body["gross_usd"] = gross
    reason = payload.get("model_reason")
    if isinstance(reason, str) and REASON_RE.fullmatch(reason):
        body["model_reason"] = reason
    return body


def write_packet(path: Path, payload: Mapping[str, Any]) -> None:
    allowed = allow_packet(payload)
    text = json.dumps(allowed, indent=2, sort_keys=True) + "\n"
    if SECRET_RE.search(text) or "BEGIN " in text:
        raise SystemExit("token_in_evidence")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise SystemExit("evidence_symlink")
    path.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    sidecar = path.with_name(path.name + ".sha256")
    sidecar.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
