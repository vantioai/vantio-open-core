"""One command that plans, applies, rolls back, uninstalls, or verifies removal.

Apply, rollback, and uninstall still require both live gates. The command
does not replace those gates. Observe-only stays the default. HEALTHY with
enforcement off is protection_state OBSERVE. PROTECTED is refused and is
not entered. The public pin constant is not written by this module.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from vantio_install import constants
from vantio_install.artifact_verify import (
    active_artifact_trust,
    fetch_to_file,
    load_signature_file,
    verify_archive_file,
)
from vantio_install.engine import apply, plan, rollback, uninstall, verify_removal
from vantio_install.errors import InstallError
from vantio_install.signed_policy import verify_signed_policy

_ENV_GATE = "VANTIO_INSTALL_ALLOW_LIVE"


def _with_saved_plan(ctx: dict, tx_id: object | None = None) -> dict:
    """Bind apply to the plan file this command already wrote.

    Live apply checks that hash. The caller does not supply a different plan.
    """
    state_dir = ctx.get("state_dir")
    chosen = tx_id if isinstance(tx_id, str) and tx_id else ctx.get("transaction_id")
    if not isinstance(chosen, str) or not chosen or state_dir is None:
        return ctx
    plan_path = Path(state_dir) / "transactions" / chosen / "PLAN.json"
    if not plan_path.is_file():
        return ctx
    copied = dict(ctx)
    copied["plan_path"] = plan_path
    copied["plan_sha256"] = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    return copied


def run_one_command(ctx: dict) -> tuple[int, dict]:
    phase = str(ctx.get("phase") or "install")
    if phase == "verify-removal":
        code, payload = verify_removal(_with_command(ctx, "verify-removal", live_flag=False))
        return code, _annotate(payload)
    if phase in {"rollback", "uninstall"}:
        if not _gates(ctx):
            return _refused(ctx, "LIVE_GATES_REQUIRED", "NOT_RUN")
        command = rollback if phase == "rollback" else uninstall
        code, payload = command(_with_saved_plan(_with_command(ctx, phase)))
        return code, _annotate(payload)
    if phase != "install":
        return _refused(ctx, "MALFORMED", "NOT_RUN")
    if ctx.get("requested_protection") == "PROTECTED":
        return _refused(ctx, "ENFORCEMENT_HELD", "NOT_RUN")
    policy_decision = _require_signed_policy(ctx.get("policy_file"))
    if policy_decision is not None:
        return policy_decision
    if ctx.get("artifact_trust") is not None:
        return _refused(ctx, "CALLER_TRUST_REFUSED", "NOT_RUN")
    signature_path = ctx.get("signature_file")
    if signature_path is None:
        return _refused(ctx, "SIGNATURE_REQUIRED", "NOT_RUN")
    trust_keys = active_artifact_trust()
    if not trust_keys:
        return _refused(ctx, "UNTRUSTED_KEY", "NOT_RUN")
    try:
        record = load_signature_file(Path(signature_path))
    except (OSError, ValueError, json.JSONDecodeError):
        return _refused(ctx, "MALFORMED", "NOT_RUN")
    archive = _archive_path(ctx)
    fetched = False
    url = ctx.get("artifact_url")
    if url:
        if archive is None:
            return _refused(ctx, "BYTES_ABSENT", "NOT_RUN")
        download = fetch_to_file(str(url), archive.with_name(archive.name + ".download"))
        if download["reason"] != "FETCHED":
            payload = _refused(ctx, str(download["reason"]), "FAILED_SAFE")[1]
            payload["fetched"] = False
            return constants.EXIT_FAILED_SAFE, payload
        fetched = True
        downloaded = Path(str(download["path"]))
        payload_bytes = downloaded.read_bytes()
        checked = verify_archive_file(downloaded, record, trust_keys=trust_keys)
        downloaded.unlink(missing_ok=True)
        if checked["disposition"] != "VERIFIED":
            code, payload = _refused(ctx, str(checked["reason"]), "FAILED_SAFE")
            payload["bytes_hashed_here"] = checked["bytes_hashed_here"]
            payload["fetched"] = True
            return code, payload
        if archive.is_file():
            local_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
            if local_hash != checked["sha256"]:
                return _refused(ctx, "PIN_MISMATCH", "NOT_RUN")
        elif not _gates(ctx):
            return _refused(ctx, "LIVE_GATES_REQUIRED", "NOT_RUN")
        else:
            archive.parent.mkdir(parents=True, exist_ok=True)
            archive.write_bytes(payload_bytes)
    if archive is None or not archive.is_file():
        return _refused(ctx, "BYTES_ABSENT", "NOT_RUN")
    verified = verify_archive_file(archive, record, trust_keys=trust_keys)
    if verified["disposition"] != "VERIFIED":
        code, payload = _refused(ctx, str(verified["reason"]), "FAILED_SAFE")
        payload["bytes_hashed_here"] = verified["bytes_hashed_here"]
        payload["fetched"] = fetched
        return code, payload
    code, payload = plan(_with_command(ctx, "plan", live_flag=False))
    payload = _annotate(payload)
    payload["bytes_hashed_here"] = True
    payload["fetched"] = fetched
    if payload.get("state") != "PLANNED":
        return code, payload
    if not _gates(ctx):
        payload["state"] = "FAILED_SAFE"
        payload["reason"] = "LIVE_GATES_REQUIRED"
        payload["message"] = (
            "Live mutations need VANTIO_INSTALL_ALLOW_LIVE=1 and --i-accept-live-mutations together."
        )
        payload["protection_state"] = "NOT_PROTECTED"
        return constants.EXIT_FAILED_SAFE, payload
    apply_ctx = _with_saved_plan(_with_command(ctx, "apply"), payload.get("transaction_id"))
    apply_ctx["yes"] = True
    try:
        code, applied = apply(apply_ctx)
    except InstallError as exc:
        return exc.exit_code, _annotate(
            {
                "command": "install",
                "state": exc.state,
                "message": str(exc),
                "proof_state": constants.PROOF_STATE,
                "proof_ceiling": constants.PROOF_CEILING,
            }
        )
    applied = _annotate(applied)
    applied["bytes_hashed_here"] = True
    applied["fetched"] = fetched
    if applied.get("state") in {"HEALTHY", "DEGRADED"} and applied.get("enforcement", "NOT_ENABLED") == "NOT_ENABLED":
        applied["protection_state"] = "OBSERVE"
    return code, applied


def _require_signed_policy(path: object):
    if path is None:
        return _refused({}, "POLICY_REQUIRED", "NOT_RUN")
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return _refused({}, "UNSIGNED_POLICY", "NOT_RUN")
    verified = verify_signed_policy(document)
    if not verified.ok or not isinstance(verified.policy, dict):
        return _refused({}, verified.reason, "NOT_RUN")
    policy = verified.policy
    if policy.get("enforcement") != "NOT_ENABLED" or policy.get("install_mode") != "observe-only":
        return _refused({}, "ENFORCEMENT_HELD", "NOT_RUN")
    if set(policy) != {"enforcement", "install_mode"}:
        return _refused({}, "MALFORMED", "NOT_RUN")
    return None


def _with_command(ctx: dict, command: str, *, live_flag: bool | None = None) -> dict:
    copied = dict(ctx)
    copied["command"] = command
    if live_flag is not None:
        copied["accept_live_mutations"] = live_flag
    return copied


def _gates(ctx: dict) -> bool:
    env = os.environ.get(_ENV_GATE) == "1"
    return env and bool(ctx.get("accept_live_mutations"))


def _archive_path(ctx: dict) -> Path | None:
    bundle = ctx.get("bundle")
    if bundle is None:
        return None
    name = constants.FROZEN_PINS["pe_archive_name"]
    return Path(bundle) / "artifacts" / "phantom-engine" / name


def _annotate(payload: dict) -> dict:
    payload = dict(payload)
    payload["live_gates_replaced"] = False
    payload["protected_entered"] = False
    payload["public_pin_moved"] = False
    payload.setdefault("protection_state", "NOT_PROTECTED")
    payload.setdefault("proof_state", constants.PROOF_STATE)
    payload.setdefault("fetched", False)
    return payload


def _refused(ctx: dict, reason: str, state: str) -> tuple[int, dict]:
    del ctx
    return constants.EXIT_FAILED_SAFE, _annotate(
        {
            "command": "install",
            "state": state,
            "reason": reason,
            "message": reason,
            "proof_state": constants.PROOF_STATE,
            "proof_ceiling": constants.PROOF_CEILING,
            "installer_version": constants.INSTALLER_VERSION,
        }
    )
