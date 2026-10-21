"""apply --enforce-enrolled. Observe-only apply is unchanged.

The flag is off unless the command passes it. Both live gates are required.
A valid license, a signed policy that allows enforcement, and a post-boot
LSM list that contains bpf are required before the loader starts. The
transaction becomes PROTECTED only when the loader output contains
``SCOPED (drop enrolled)`` and the program list contains
``cgroup_skb_egress_enforce``. Anything else is DEGRADED with a reason.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from vantio_install import constants
from vantio_install.commands import enforce_container_argv
from vantio_install.engine import (
    Lock,
    _clock,
    _exit_for,
    _move,
    _payload,
    _require_yes,
    _save_tx,
    _sync,
    _tx_dir,
)
from vantio_install.gates import command_payload, require_live_gates
from vantio_install.health import bpf_lsm_active, derive
from vantio_install.host_prep import read_lsm
from vantio_install.license_token import read_stored_license, verify_token
from vantio_install.self_serve import load_policy_file, manifest_has_exec_deny
from vantio_install.server_root import server_root
from vantio_install.signed_policy import verify_signed_policy
from vantio_install.util import read_json, redact_text, sha256_file, write_json

_LOG_CAP = 256 * 1024


def apply_enforce_enrolled(ctx: dict) -> tuple[int, dict]:
    _require_yes(bool(ctx.get("yes")), "apply")
    require_live_gates(ctx)
    preset = ctx.get("exec_preset")
    if preset is not None and preset != "web-server":
        return _refuse(ctx, "EXEC_PRESET_REFUSED", "The only exec preset is web-server.")
    tx_id = ctx.get("transaction_id")
    if not tx_id:
        return _refuse(ctx, "TRANSACTION_REQUIRED", "apply --enforce-enrolled needs --transaction-id.")
    state_dir = Path(ctx["state_dir"])
    with Lock(state_dir):
        tx_dir = _tx_dir(state_dir, str(tx_id))
        tx_path = tx_dir / "TRANSACTION.json"
        if not tx_path.is_file():
            return _refuse(ctx, "TRANSACTION_MISSING", "The transaction was not found.")
        tx = read_json(tx_path)
        if tx.get("state") not in {"HEALTHY", "DEGRADED"}:
            return _refuse(
                ctx,
                "OBSERVE_INSTALL_REQUIRED",
                "Run observe apply before apply --enforce-enrolled.",
                transaction_id=tx_id,
                state=str(tx.get("state") or "FAILED_SAFE"),
            )
        plan_reason = _plan_reason(ctx, tx_dir)
        if plan_reason is not None:
            return _refuse(ctx, plan_reason, "The plan hash does not match this transaction.", transaction_id=tx_id)
        root = server_root(ctx, create=True)
        license_reason, license_fields = _license_reason(root)
        if license_reason is not None:
            message = "license canceled or expired" if license_reason == "EXPIRED" else license_reason
            return _refuse(ctx, license_reason, message, transaction_id=tx_id)
        policy_reason = _policy_reason(ctx)
        if policy_reason is not None:
            return _refuse(ctx, policy_reason, policy_reason, transaction_id=tx_id)
        lsm = read_lsm(root)
        if lsm is None:
            return _refuse(ctx, "LSM_UNREADABLE", "Could not read /sys/kernel/security/lsm.", transaction_id=tx_id)
        if not bpf_lsm_active(lsm):
            return _refuse(
                ctx,
                "LSM_BPF_MISSING",
                "The post-boot LSM list does not contain bpf. Run host-prep and reboot.",
                transaction_id=tx_id,
            )
        bundle = Path(ctx["bundle"]) if ctx.get("bundle") else Path(str(tx.get("bundle_dir") or ""))
        if preset == "web-server" and not _manifest_allows(bundle):
            return _refuse(
                ctx,
                "EXEC_DENY_NOT_IN_SEAL",
                "The sealed manifest does not advertise exec_deny.",
                transaction_id=tx_id,
            )
        stamp = _clock(ctx.get("as_of"))
        snapshot_path = tx_dir / "HOST-SNAPSHOT.json"
        snapshot = read_json(snapshot_path) if snapshot_path.is_file() else {}
        config_path = tx_dir / "CONFIG.json"
        if ctx.get("config_path") and Path(ctx["config_path"]).is_file():
            config = read_json(Path(ctx["config_path"]))
        elif config_path.is_file():
            config = read_json(config_path)
        else:
            config = {}
        _start_loader(ctx, snapshot, root, str(tx_id), str(config.get("iface") or "ens5"), preset if preset == "web-server" else None)
        snapshot["active_lsm"] = lsm
        snapshot["enforce_flag"] = True
        health = derive(snapshot, config, limitations=tx.get("limitations") or [])
        if isinstance(license_fields, dict):
            health["license"] = license_fields
            tx["license"] = license_fields
        health.update(
            {
                "transaction_id": tx_id,
                "as_of_et": stamp,
                "evidence_paths": [str(tx.get("evidence_dir") or "")],
            }
        )
        write_json(tx_dir / "HEALTH.json", health)
        write_json(snapshot_path, snapshot)
        tx["install_mode"] = "enforce-enrolled"
        tx["enforcement"] = "ENROLLED"
        tx["updated_at"] = stamp
        tx["health_overall"] = health["overall"]
        tx["protection_state"] = health.get("protection_state")
        tx["phase"] = "apply"
        if health.get("protection_state") == "PROTECTED" and health["overall"] == "PASS":
            if tx["state"] != "HEALTHY":
                _move(tx, "HEALTHY", stamp)
        elif tx["state"] == "HEALTHY":
            _move(tx, "DEGRADED", stamp)
        tx["last_error"] = None if health.get("protection_state") == "PROTECTED" else health.get("degraded_reason")
        _save_tx(tx_dir, tx)
        evidence = tx.get("evidence_dir")
        if evidence:
            _sync(tx_dir, Path(str(evidence)))
        return _exit_for(tx["state"]), _payload(
            "apply",
            tx,
            health_overall=health.get("overall"),
            components=health.get("components", {}),
            protection_state=health.get("protection_state"),
            degraded_reason=health.get("degraded_reason", ""),
            license=license_fields,
            limitations=tx.get("limitations") or [],
        )


def _start_loader(ctx: dict, snapshot: dict, root: Path, tx_id: str, iface: str, preset: str | None) -> None:
    tag = constants.FROZEN_PINS["pe_local_tag"]
    name = f"vantio-pe-{tx_id[-12:]}"
    argv = enforce_container_argv(tag=tag, iface=iface, name=name, exec_preset=preset)
    snapshot.setdefault("recorded_argv", []).append(argv)
    if ctx.get("fixture_host"):
        loader_output, programs = _fixture_proof(root)
    else:
        subprocess.run(["docker", "rm", "-f", name], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(argv, check=False)
        logs = subprocess.run(["docker", "logs", name], check=False, capture_output=True, text=True)
        bpf = subprocess.run(["bpftool", "prog", "list"], check=False, capture_output=True, text=True)
        loader_output = redact_text(((logs.stdout or "") + (logs.stderr or ""))[:_LOG_CAP])
        programs = redact_text(((bpf.stdout or "") + (bpf.stderr or ""))[:_LOG_CAP])
    tag_at = argv.index(tag)
    loader_cmd = argv[tag_at + 1 :]
    containers = [
        row
        for row in snapshot.get("containers") or []
        if row.get("name") != name
    ]
    containers.append(
        {
            "name": name,
            "role": "phantom_engine",
            "status": "running",
            "image": tag,
            "cmd": loader_cmd,
            "enforce": True,
        }
    )
    snapshot["containers"] = containers
    snapshot["enforce_enrollment"] = {
        "requested": True,
        "loader_output": loader_output,
        "bpf_programs": programs,
    }


def _fixture_proof(root: Path) -> tuple[str, list[str]]:
    log_path = root / "var/lib/vantio/enforce-loader.out"
    program_path = root / "var/lib/vantio/bpf-programs.txt"
    try:
        text = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
    except OSError:
        text = ""
    try:
        raw = program_path.read_text(encoding="utf-8") if program_path.is_file() else ""
    except OSError:
        raw = ""
    return text, [line.strip() for line in raw.splitlines() if line.strip()]


def _manifest_allows(bundle: Path) -> bool:
    path = bundle / "artifacts" / "phantom-engine" / "PHANTOM-ARTIFACT-MANIFEST.json"
    if not path.is_file():
        return False
    try:
        document = read_json(path)
    except (OSError, ValueError):
        return False
    return isinstance(document, dict) and manifest_has_exec_deny(document)


def _license_reason(root: Path) -> tuple[str | None, dict | None]:
    token = read_stored_license(root / constants.LICENSE_RELATIVE)
    if not token:
        return "LICENSE_MISSING", None
    checked = verify_token(token)
    if not checked["ok"]:
        return str(checked["reason"]), None
    return None, checked["license"]


def _policy_reason(ctx: dict) -> str | None:
    path = ctx.get("policy_file")
    if path is None or not Path(path).is_file():
        return "POLICY_MISSING"
    try:
        document = load_policy_file(Path(path))
    except (OSError, ValueError):
        return "UNSIGNED_POLICY"
    result = verify_signed_policy(document)
    if not result.ok or not isinstance(result.policy, dict):
        return result.reason
    if result.policy.get("allow_enforcement") is not True or result.policy.get("enforcement") != "ENROLLED":
        return "POLICY_DOES_NOT_ALLOW_ENFORCEMENT"
    return None


def _plan_reason(ctx: dict, tx_dir: Path) -> str | None:
    if ctx.get("fixture_host"):
        return None
    plan_path = ctx.get("plan_path")
    plan_sha = str(ctx.get("plan_sha256") or "")
    current = tx_dir / "PLAN.json"
    if plan_path is None or not plan_sha or not current.is_file() or not Path(plan_path).is_file():
        return "PLAN_REQUIRED"
    if sha256_file(Path(plan_path)) != plan_sha or sha256_file(current) != plan_sha:
        return "PLAN_HASH_MISMATCH"
    return None


def _refuse(ctx: dict, reason: str, message: str, **extra: object) -> tuple[int, dict]:
    return constants.EXIT_BLOCKED, command_payload(
        "apply",
        str(extra.pop("state", "FAILED_SAFE")),
        message,
        reason=reason,
        transaction_id=extra.pop("transaction_id", ctx.get("transaction_id")),
        **extra,
    )
