"""Transaction commands. Apply success is health plus evidence, never an exit code alone."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from vantio_install import bpf_pins, constants
from vantio_install.errors import InstallError
from vantio_install.boot_hold.service import status_body
from vantio_install.health import component_template, derive
from vantio_install.host import load_fixture, probe_live
from vantio_install.manifest import artifact_paths, bundle_digest, load_manifest, missing_manifest_fields
from vantio_install.live_executor import (
    ProductionObserver,
    authorize_live,
    clear_partial_mutation,
    resolve_tracefs_host,
    guard_readonly_command,
    live_operation_ids,
    partial_mutation_steps,
    residual_result,
)
from vantio_install.agent_sdk import agent_sdk_present
from vantio_install.optics_cli import optics_cli_present
from vantio_install.mutator import FixtureMutator, LiveMutator
from vantio_install.paths import assert_safe_root
from vantio_install.preflight import run_preflight
from vantio_install.residual import inspect as inspect_residual
from vantio_install.state_machine import RESIDUAL_STATES, TRANSIENT, transition
from vantio_install.support_bundle import build_support_bundle
from vantio_install.util import (
    canonical_json,
    now_et,
    pid_alive,
    read_json,
    redact_text,
    sha256_bytes,
    write_json,
)

_EVIDENCE_NAMES = (
    "TRANSACTION.json",
    "PREFLIGHT.json",
    "PLAN.json",
    "HEALTH.json",
    "ARTIFACT-VERIFICATION.json",
    "RESIDUAL.json",
    "SUPPORT-BUNDLE-INDEX.json",
    "APPLY-EVENT-LOG.jsonl",
    "HOST-SNAPSHOT.json",
    "CONFIG.json",
)


class Lock:
    def __init__(self, state_dir: Path) -> None:
        self.path = state_dir / "LOCK"

    def __enter__(self) -> "Lock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError as exc:
            raise InstallError(
                "Another install transaction holds the lock.",
                exit_code=constants.EXIT_FAILED_SAFE,
                state="FAILED_SAFE",
            ) from exc
        os.write(fd, f"{os.getpid()}\n".encode("ascii"))
        os.close(fd)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            return


def _clock(as_of: str | None) -> str:
    return as_of or now_et()


def _tx_dir(state_dir: Path, tx_id: str) -> Path:
    return state_dir / "transactions" / tx_id


def _load_tx(path: Path) -> dict:
    if not path.is_file():
        raise InstallError("Transaction record was not found.", exit_code=constants.EXIT_USAGE, state="FAILED_SAFE")
    return read_json(path)


def _move(tx: dict, target: str, stamp: str) -> None:
    transition(tx["state"], target)
    tx["state_history"].append({"from": tx["state"], "to": target, "at": stamp})
    tx["state"] = target
    tx["updated_at"] = stamp


def _event(evidence: Path, stamp: str, step: str, state: str, detail: str) -> None:
    line = json.dumps(
        {"at": stamp, "step": step, "state": state, "detail": redact_text(detail)},
        sort_keys=True,
    )
    path = evidence / "APPLY-EVENT-LOG.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _sync(tx_dir: Path, evidence: Path) -> None:
    evidence.mkdir(parents=True, exist_ok=True)
    for name in _EVIDENCE_NAMES:
        src = tx_dir / name
        if src.is_file():
            target = evidence / name
            target.write_bytes(src.read_bytes())


def _save_tx(tx_dir: Path, tx: dict) -> None:
    write_json(tx_dir / "TRANSACTION.json", tx)


def _exit_for(state: str) -> int:
    if state in {
        "PLANNED",
        "HEALTHY",
        "DEGRADED",
        "ROLLED_BACK",
        "UNINSTALLED",
        "VERIFIED_REMOVED",
        "PREFLIGHT_READY",
        "PREFLIGHT_READY_WITH_LIMITATIONS",
    }:
        return constants.EXIT_OK
    if state in {"PREFLIGHT_BLOCKED", "RESIDUAL_PRESENT", "RESIDUAL_FOUND"}:
        return constants.EXIT_BLOCKED
    if state == "UNSUPPORTED":
        return constants.EXIT_UNSUPPORTED
    if state == "FAILED_SAFE":
        return constants.EXIT_FAILED_SAFE
    if state in TRANSIENT or state in {"INTERRUPTED", "APPLIED", "CREATED"}:
        return constants.EXIT_INTERRUPTED
    return constants.EXIT_FAILED_SAFE


def _payload(command: str, tx: dict, **extra: object) -> dict:
    body = {
        "command": command,
        "transaction_id": tx["transaction_id"],
        "state": tx["state"],
        "evidence_dir": tx.get("evidence_dir"),
        "proof_state": constants.PROOF_STATE,
        "proof_ceiling": constants.PROOF_CEILING,
        "as_of_et": tx.get("updated_at"),
        "installer_version": constants.INSTALLER_VERSION,
        "install_mode": tx.get("install_mode", "observe-only"),
        "enforcement": tx.get("enforcement", "NOT_ENABLED"),
    }
    body.update(extra)
    if body["proof_state"] in constants.FORBIDDEN_PROOF_STATES:
        raise InstallError("Refusing a proof state above the ceiling.", exit_code=4, state="FAILED_SAFE")
    return body


def _load_config(path: Path) -> dict:
    if not path.is_file():
        raise InstallError("Config file was not found.", exit_code=constants.EXIT_USAGE, state="FAILED_SAFE")
    data = read_json(path)
    if not isinstance(data, dict):
        raise InstallError("Config must be a JSON object.", exit_code=constants.EXIT_USAGE, state="FAILED_SAFE")
    return data


def _validate_layout(config: dict, state_dir: Path, evidence_dir: Path) -> dict[str, Path]:
    roots = config.get("workload_roots")
    if not isinstance(roots, list) or not roots:
        raise InstallError("workload_roots must be a non-empty list.", exit_code=10, state="FAILED_SAFE")
    safe_roots = [assert_safe_root(str(item), label="workload_roots") for item in roots]
    stage = assert_safe_root(str(config.get("stage_dir") or (state_dir / "pe-stage")), label="stage_dir")
    prefix = assert_safe_root(str(config.get("prefix") or (state_dir / "prefix")), label="prefix")
    assert_safe_root(str(state_dir), label="state_dir")
    assert_safe_root(str(evidence_dir), label="evidence_dir")
    return {"stage": stage, "prefix": prefix, "workload": safe_roots[0]}


def _blank_health(tx_id: str, stamp: str, evidence: str) -> dict:
    return {
        "transaction_id": tx_id,
        "install_mode": "observe-only",
        "enforcement": "NOT_ENABLED",
        "components": component_template("NOT_TESTED"),
        "overall": "UNKNOWN",
        "as_of_et": stamp,
        "evidence_paths": [evidence],
    }


def _blank_residual() -> dict:
    return {"result": "UNKNOWN", "items": [], "scope": None, "probe_errors": []}


def _planned_steps(npm: dict) -> list[dict]:
    rows = []
    for index, step_id in enumerate(constants.APPLY_STEPS, start=1):
        row = {
            "ord": index,
            "id": step_id,
            "mutation": step_id in constants.HOST_MUTATION_STEPS,
            "mode": "observe-only",
            "enforcement": "NOT_ENABLED",
        }
        if step_id == "ensure_node":
            row["npm_action"] = npm["action"]
            if npm.get("argv"):
                row["argv"] = npm["argv"]
            if npm["action"] == "remediate":
                row["mutation"] = True
                row["prerequisite"] = npm["prerequisite"]
        rows.append(row)
    return rows


def _plan_prerequisites(npm: dict) -> list[dict]:
    if not npm.get("prerequisite"):
        return []
    row = {
        "id": "PF-NPM",
        "package": "npm",
        "text": npm["prerequisite"],
        "action": npm["action"],
    }
    if npm.get("argv"):
        row["argv"] = npm["argv"]
    return [row]


def _digests() -> dict:
    pin = constants.FROZEN_PINS
    return {
        "optics_cli_sha256": pin["optics_cli_sha256"],
        "agent_sdk_npm_sha256": pin["agent_sdk_npm_sha256"],
        "agent_sdk_py_wheel_sha256": pin["agent_sdk_py_wheel_sha256"],
        "pe_archive_sha256": pin["pe_archive_sha256"],
        "pe_manifest_digest": pin["pe_manifest_digest"],
        "pe_source_commit": pin["pe_source_commit"],
    }


def _new_tx(tx_id: str, stamp: str, bundle: Path, digest: str, evidence: Path, config: dict) -> dict:
    return {
        "transaction_id": tx_id,
        "state": "CREATED",
        "proof_state": constants.PROOF_STATE,
        "proof_ceiling": constants.PROOF_CEILING,
        "installer_version": constants.INSTALLER_VERSION,
        "bundle_dir": str(bundle),
        "bundle_id": None,
        "bundle_digest": digest,
        "config_digest": sha256_bytes(canonical_json(config).encode("utf-8")),
        "evidence_dir": str(evidence),
        "created_at": stamp,
        "updated_at": stamp,
        "completed_steps": [],
        "rollback_completed_steps": [],
        "planned_step_ids": list(constants.APPLY_STEPS),
        "mutation_in_progress": False,
        "owner_pid": None,
        "host_mutation_count": 0,
        "replayed": False,
        "health_overall": "UNKNOWN",
        "limitations": [],
        "state_history": [],
        "install_mode": config.get("install_mode", "observe-only"),
        "enforcement": config.get("enforcement", "NOT_ENABLED"),
        "phase": "created",
        "last_error": None,
        "scope": None,
        "preflight_status": None,
    }


def _require_yes(yes: bool, action: str) -> None:
    if yes:
        return
    raise InstallError(
        f"{action} needs --yes in this non-interactive Stage A installer.",
        exit_code=constants.EXIT_USAGE,
        state="FAILED_SAFE",
    )


def _fixture_hooks(config: dict, enabled: bool) -> dict:
    if not enabled:
        return {}
    return {
        "interrupt_after_step": config.get("interrupt_after_step"),
        "rollback_interrupt_after_step": config.get("rollback_interrupt_after_step"),
        "uninstall_leave": config.get("uninstall_leave") or [],
        "simulate_missing": config.get("simulate_missing") or [],
        "simulate_probe_errors": config.get("simulate_probe_errors") or [],
        "residual_probe_errors": config.get("residual_probe_errors") or [],
        "bpffs_root": config.get("bpffs_root") or "",
    }


def _removal_bpffs(ctx: dict, hooks: dict) -> Path | None:
    """Live removal reads ``/sys/fs/bpf``. A fixture reads ``bpffs_root`` when set.

    Fixture mode does not scan the machine running the tests unless the hook
    is set. Live mode does not honor ``bpffs_root`` from the config.
    """
    if ctx.get("fixture_host"):
        raw = str(hooks.get("bpffs_root") or "").strip()
        return Path(raw) if raw else None
    return bpf_pins.default_bpffs()


def _resolve_evidence(config: dict, tx_id: str, override: Path | None) -> Path:
    if override is not None:
        return override
    raw = str(config.get("evidence_root", f"/var/tmp/vantio-evidence/{tx_id}"))
    return Path(raw.replace("<transaction_id>", tx_id))


def _load_host(fixture: Path | None) -> dict:
    if fixture is not None:
        return load_fixture(fixture)
    return probe_live()


def _plan_document(tx_id: str, gate: str, missing: list[str], layout: dict[str, Path], npm: dict) -> dict:
    ready = gate in {"PREFLIGHT_READY", "PREFLIGHT_READY_WITH_LIMITATIONS"}
    return {
        "transaction_id": tx_id,
        "planned_steps": _planned_steps(npm) if ready else [],
        "prerequisites": _plan_prerequisites(npm),
        "artifact_digests": _digests(),
        "missing_manifest_fields": missing,
        "layout": {key: str(value) for key, value in layout.items()},
        "rollback_steps": [step for step in reversed(constants.APPLY_STEPS) if step in constants.HOST_MUTATION_STEPS],
        "residual_checks": ["container", "image", "stage", "bpf_pins", "clsact", "loader", "optics", "o7_record"],
        "live_operations": live_operation_ids(),
    }


def plan(ctx: dict) -> tuple[int, dict]:
    guard_readonly_command(ctx)
    if ctx.get("dry_run_flag") and ctx["command"] != "plan":
        raise InstallError("Apply does not accept --dry-run. Use plan.", exit_code=10, state="FAILED_SAFE")
    stamp = _clock(ctx.get("as_of"))
    config = _load_config(ctx["config_path"])
    bundle = ctx["bundle"]
    if bundle is None or not bundle.is_dir():
        raise InstallError("Plan needs a bundle directory.", exit_code=10, state="FAILED_SAFE")
    tx_id = ctx.get("transaction_id") or "vantio-tx-" + str(uuid.uuid4())
    evidence = _resolve_evidence(config, tx_id, ctx.get("evidence_dir"))
    state_dir = ctx["state_dir"]
    layout = _validate_layout(config, state_dir, evidence)
    if not (bundle / "MANIFEST.json").is_file():
        raise InstallError("Bundle is missing MANIFEST.json.", exit_code=10, state="FAILED_SAFE")
    manifest_bytes = (bundle / "MANIFEST.json").read_bytes()
    manifest = load_manifest(bundle)
    digest = bundle_digest(manifest_bytes)
    tx_dir = _tx_dir(state_dir, tx_id)
    with Lock(state_dir):
        existing = tx_dir / "TRANSACTION.json"
        if existing.is_file():
            tx = _load_tx(existing)
            if (
                tx["state"] == "PLANNED"
                and tx.get("bundle_digest") == digest
                and tx.get("config_digest") == sha256_bytes(canonical_json(config).encode("utf-8"))
            ):
                plan_doc = read_json(tx_dir / "PLAN.json")
                return constants.EXIT_OK, _payload(
                    "plan",
                    tx,
                    preflight_status=tx.get("preflight_status"),
                    limitations=tx.get("limitations") or [],
                    planned_steps=plan_doc["planned_steps"],
                    prerequisites=plan_doc.get("prerequisites") or [],
                    artifact_digests=plan_doc["artifact_digests"],
                    replayed=True,
                )
        else:
            tx = _new_tx(tx_id, stamp, bundle, digest, evidence, config)
            tx_dir.mkdir(parents=True, exist_ok=True)
            _save_tx(tx_dir, tx)
        if tx["state"] == "PLANNED":
            _move(tx, "CREATED", stamp)
        elif tx["state"] == "UNSUPPORTED":
            return constants.EXIT_UNSUPPORTED, _payload("plan", tx, preflight_status="UNSUPPORTED", limitations=[])
        elif tx["state"] not in {"CREATED", "PREFLIGHT_BLOCKED"}:
            raise InstallError(
                f"Plan cannot start from {tx['state']}.",
                exit_code=10,
                state=tx["state"],
            )
        if tx["state"] == "PREFLIGHT_BLOCKED":
            _move(tx, "PREFLIGHTING", stamp)
        elif tx["state"] == "CREATED":
            _move(tx, "PREFLIGHTING", stamp)
        host = _load_host(ctx.get("fixture_host"))
        report = run_preflight(
            bundle=bundle,
            config={**config, "transaction_id": tx_id},
            host=host,
            resuming=False,
            plan_present=False,
            config_present=True,
            bundle_digest_match=True,
        )
        missing = missing_manifest_fields(manifest)
        tx["bundle_id"] = manifest.get("bundle_id")
        tx["preflight_status"] = report["overall"]
        tx["limitations"] = report["limitations"]
        gate = {
            "READY": "PREFLIGHT_READY",
            "READY_WITH_LIMITATIONS": "PREFLIGHT_READY_WITH_LIMITATIONS",
            "BLOCKED": "PREFLIGHT_BLOCKED",
            "UNSUPPORTED": "UNSUPPORTED",
        }[report["overall"]]
        _move(tx, gate, stamp)
        plan_doc = _plan_document(tx_id, gate, missing, layout, report["npm"])
        if gate in {"PREFLIGHT_READY", "PREFLIGHT_READY_WITH_LIMITATIONS"}:
            _move(tx, "PLANNED", stamp)
        tx["phase"] = "plan"
        tx["owner_pid"] = None
        tx["mutation_in_progress"] = False
        _save_tx(tx_dir, tx)
        write_json(tx_dir / "PLAN.json", plan_doc)
        write_json(tx_dir / "PREFLIGHT.json", {**report, "transaction_id": tx_id, "as_of_et": stamp})
        write_json(tx_dir / "CONFIG.json", config)
        write_json(tx_dir / "HOST-SNAPSHOT.json", host)
        write_json(tx_dir / "HEALTH.json", _blank_health(tx_id, stamp, str(evidence)))
        write_json(tx_dir / "RESIDUAL.json", _blank_residual())
        write_json(
            tx_dir / "ARTIFACT-VERIFICATION.json",
            {"artifact_digests": _digests(), "match_required": True, "as_of_et": stamp},
        )
        write_json(tx_dir / "SUPPORT-BUNDLE-INDEX.json", {"status": "NOT_BUILT", "transaction_id": tx_id})
        _event(tx_dir, stamp, "plan", tx["state"], "plan finished")
        _sync(tx_dir, evidence)
        return _exit_for(tx["state"]), _payload(
            "plan",
            tx,
            preflight_status=report["overall"],
            limitations=report["limitations"],
            planned_steps=plan_doc["planned_steps"],
            prerequisites=plan_doc["prerequisites"],
            artifact_digests=plan_doc["artifact_digests"],
            failed_or_limiting_checks=[row["id"] for row in report["failed_or_limiting_checks"]],
        )


def _open_existing(ctx: dict) -> tuple[dict, Path, dict, dict]:
    tx_id = ctx.get("transaction_id")
    if not tx_id:
        raise InstallError("This command needs --transaction-id.", exit_code=10, state="FAILED_SAFE")
    state_dir = ctx["state_dir"]
    tx_dir = _tx_dir(state_dir, tx_id)
    tx = _load_tx(tx_dir / "TRANSACTION.json")
    config_path = tx_dir / "CONFIG.json"
    if ctx.get("config_path") and ctx["config_path"].is_file():
        config = _load_config(ctx["config_path"])
    elif config_path.is_file():
        config = read_json(config_path)
    else:
        raise InstallError("Transaction config is missing.", exit_code=4, state="FAILED_SAFE")
    return tx, tx_dir, config, {}


def _mutator(ctx: dict, snapshot: dict, config: dict, grant=None):
    if ctx.get("fixture_host"):
        stage = assert_safe_root(str(config.get("stage_dir") or (ctx["state_dir"] / "pe-stage")), label="stage_dir")
        prefix = assert_safe_root(str(config.get("prefix") or (ctx["state_dir"] / "prefix")), label="prefix")
        return FixtureMutator(snapshot, prefix, stage), stage, prefix
    return (
        LiveMutator(
            grant,
            runner=ctx.get("live_runner"),
            observer=ctx.get("live_observer") or ProductionObserver(),
            snapshot=snapshot,
        ),
        Path(str(config.get("stage_dir") or "/var/tmp/vantio-pe")),
        Path(str(config.get("prefix") or "/var/lib/vantio/prefix")),
    )


def _live_grant(ctx: dict, tx: dict, tx_dir: Path, config: dict, bundle: Path, host: dict):
    if ctx.get("fixture_host"):
        return None
    return authorize_live(
        command=str(ctx.get("command") or ""),
        tx=tx,
        tx_dir=tx_dir,
        config=config,
        bundle=bundle,
        host=host,
        plan_path=ctx.get("plan_path"),
        plan_sha256=ctx.get("plan_sha256"),
        accept_live_mutations=bool(ctx.get("accept_live_mutations")),
        euid=ctx.get("live_euid"),
        tracefs_probe=ctx.get("tracefs_probe"),
    )


def _boot_hold_root(ctx: dict, state_dir: Path) -> str:
    if ctx.get("fixture_host"):
        return str(state_dir / "boot-hold-host")
    return "/"


def _step_ctx(tx: dict, config: dict, bundle: Path, hooks: dict, observe_path: Path, boot_hold_root: str) -> dict:
    return {
        "transaction_id": tx["transaction_id"],
        "config": config,
        "paths": artifact_paths(bundle),
        "observe_config_path": str(observe_path),
        "simulate_missing": hooks.get("simulate_missing") or [],
        "simulate_probe_errors": hooks.get("simulate_probe_errors") or [],
        "uninstall_leave": hooks.get("uninstall_leave") or [],
        "bpffs_root": hooks.get("bpffs_root") or "",
        "boot_hold_root": boot_hold_root,
    }


def apply(ctx: dict) -> tuple[int, dict]:
    if ctx.get("dry_run_flag"):
        raise InstallError("Apply does not accept --dry-run. Use plan.", exit_code=10, state="FAILED_SAFE")
    _require_yes(bool(ctx.get("yes")), "apply")
    stamp = _clock(ctx.get("as_of"))
    state_dir = ctx["state_dir"]
    with Lock(state_dir):
        tx, tx_dir, config, _unused = _open_existing(ctx)
        evidence = Path(tx["evidence_dir"])
        bundle = Path(ctx["bundle"]) if ctx.get("bundle") else Path(tx["bundle_dir"])
        manifest_bytes = (bundle / "MANIFEST.json").read_bytes()
        digest = bundle_digest(manifest_bytes)
        hooks = _fixture_hooks(config, bool(ctx.get("fixture_host")))
        if tx["state"] in {"HEALTHY", "DEGRADED"} and tx.get("bundle_digest") == digest:
            if not ctx.get("fixture_host"):
                raise InstallError(
                    "This transaction is already committed. Live apply will not run it again.",
                    exit_code=constants.EXIT_FAILED_SAFE,
                    state="FAILED_SAFE",
                    failure_class="FAILED_SAFE",
                )
            tx["replayed"] = True
            _save_tx(tx_dir, tx)
            _sync(tx_dir, evidence)
            health = read_json(tx_dir / "HEALTH.json") if (tx_dir / "HEALTH.json").is_file() else {}
            return _exit_for(tx["state"]), _payload(
                "apply",
                tx,
                health_overall=health.get("overall", tx.get("health_overall")),
                components=health.get("components", {}),
                limitations=tx.get("limitations") or [],
                replayed=True,
            )
        if tx["state"] == "PREFLIGHT_BLOCKED":
            return constants.EXIT_BLOCKED, _payload("apply", tx, limitations=tx.get("limitations") or [])
        if tx["state"] == "UNSUPPORTED":
            return constants.EXIT_UNSUPPORTED, _payload("apply", tx, limitations=tx.get("limitations") or [])
        if tx["state"] not in {"PLANNED", "INTERRUPTED", "APPLYING"}:
            raise InstallError(f"Apply cannot start from {tx['state']}.", exit_code=10, state=tx["state"])
        if tx["state"] == "INTERRUPTED" and tx.get("phase") == "rollback":
            raise InstallError("Resume rollback, not apply.", exit_code=10, state="INTERRUPTED")
        plan_present = (tx_dir / "PLAN.json").is_file()
        if digest != tx.get("bundle_digest") or not plan_present or not (tx_dir / "CONFIG.json").is_file():
            if tx["state"] == "PLANNED":
                _move(tx, "APPLYING", stamp)
            _move(tx, "FAILED_SAFE", stamp)
            tx["last_error"] = "checkpoint or bundle digest mismatch"
            tx["phase"] = "apply"
            _save_tx(tx_dir, tx)
            _event(tx_dir, stamp, "resume", "FAILED_SAFE", tx["last_error"])
            _sync(tx_dir, evidence)
            return constants.EXIT_FAILED_SAFE, _payload("apply", tx, limitations=tx.get("limitations") or [])
        done = list(tx.get("completed_steps") or [])
        if done != list(constants.APPLY_STEPS[: len(done)]):
            if tx["state"] != "APPLYING":
                _move(tx, "APPLYING", stamp)
            _move(tx, "FAILED_SAFE", stamp)
            tx["last_error"] = "checkpoint prefix is not intact"
            _save_tx(tx_dir, tx)
            _sync(tx_dir, evidence)
            return constants.EXIT_FAILED_SAFE, _payload("apply", tx)
        snapshot_path = tx_dir / "HOST-SNAPSHOT.json"
        snapshot = read_json(snapshot_path) if snapshot_path.is_file() else load_fixture(ctx["fixture_host"])
        grant = None if ctx.get("fixture_host") else _live_grant(ctx, tx, tx_dir, config, bundle, snapshot)
        if tx["state"] == "INTERRUPTED":
            _move(tx, "APPLYING", stamp)
        elif tx["state"] == "PLANNED":
            _move(tx, "APPLYING", stamp)
        mutator, stage, prefix = _mutator(ctx, snapshot, config, grant)
        observe_path = tx_dir / "observe-config.json"
        step_ctx = _step_ctx(tx, config, bundle, hooks, observe_path, _boot_hold_root(ctx, state_dir))
        tx["mutation_in_progress"] = True
        tx["owner_pid"] = os.getpid()
        tx["phase"] = "apply"
        _save_tx(tx_dir, tx)
        checked_host, allow_unrecorded_tracefs = resolve_tracefs_host(
            snapshot,
            command="apply",
            probe=ctx.get("tracefs_probe"),
        )
        recheck = run_preflight(
            bundle=bundle,
            config={**config, "transaction_id": tx["transaction_id"]},
            host=checked_host,
            resuming=True,
            plan_present=True,
            config_present=True,
            bundle_digest_match=digest == tx.get("bundle_digest"),
            allow_unrecorded_tracefs=allow_unrecorded_tracefs,
        )
        if recheck["overall"] in {"BLOCKED", "UNSUPPORTED"}:
            _move(tx, "FAILED_SAFE", stamp)
            tx["last_error"] = "resume preflight failed closed"
            tx["preflight_status"] = recheck["overall"]
            tx["mutation_in_progress"] = False
            tx["owner_pid"] = None
            write_json(tx_dir / "PREFLIGHT.json", {**recheck, "transaction_id": tx["transaction_id"], "as_of_et": stamp})
            _save_tx(tx_dir, tx)
            _event(tx_dir, stamp, "resume-preflight", "FAILED_SAFE", tx["last_error"])
            _sync(tx_dir, evidence)
            return constants.EXIT_FAILED_SAFE, _payload("apply", tx, limitations=tx.get("limitations") or [])
        current_step: str | None = None
        try:
            for step_id in constants.APPLY_STEPS:
                current_step = step_id
                if step_id in done:
                    continue
                if step_id == "verify_artifacts":
                    report = run_preflight(
                        bundle=bundle,
                        config={**config, "transaction_id": tx["transaction_id"]},
                        host=checked_host,
                        resuming=True,
                        plan_present=True,
                        config_present=True,
                        bundle_digest_match=True,
                        allow_unrecorded_tracefs=allow_unrecorded_tracefs,
                    )
                    if report["overall"] in {"BLOCKED", "UNSUPPORTED"}:
                        _move(tx, "FAILED_SAFE", stamp)
                        tx["last_error"] = "artifact verification failed on resume"
                        tx["preflight_status"] = report["overall"]
                        break
                elif step_id == "mark_applied":
                    _move(tx, "APPLIED", stamp)
                    tx["health_overall"] = "UNKNOWN"
                elif step_id == "collect_health":
                    health = derive(snapshot, config, limitations=tx.get("limitations") or [])
                    health.update(
                        {
                            "transaction_id": tx["transaction_id"],
                            "as_of_et": stamp,
                            "evidence_paths": [str(evidence)],
                            "boot_hold": status_body(Path(step_ctx["boot_hold_root"])),
                            "reboot_row": "NOT_PROVED",
                        }
                    )
                    write_json(tx_dir / "HEALTH.json", health)
                    tx["health_overall"] = health["overall"]
                    if health["overall"] == "PASS":
                        _move(tx, "HEALTHY", stamp)
                    elif health["overall"] == "PASS_WITH_LIMITATIONS":
                        _move(tx, "DEGRADED", stamp)
                    else:
                        _move(tx, "FAILED_SAFE", stamp)
                        tx["last_error"] = f"health overall {health['overall']}"
                elif step_id == "write_support_index":
                    write_json(tx_dir / "HOST-SNAPSHOT.json", snapshot)
                    _sync(tx_dir, evidence)
                    build_support_bundle(evidence, tx["transaction_id"], snapshot)
                    if (evidence / "SUPPORT-BUNDLE-INDEX.json").is_file():
                        (tx_dir / "SUPPORT-BUNDLE-INDEX.json").write_bytes(
                            (evidence / "SUPPORT-BUNDLE-INDEX.json").read_bytes()
                        )
                else:
                    mutator.apply_step(step_id, step_ctx)
                clear_partial_mutation(tx_dir, step_id)
                done.append(step_id)
                tx["completed_steps"] = done
                tx["host_mutation_count"] = getattr(mutator, "mutation_count", 0)
                write_json(tx_dir / "HOST-SNAPSHOT.json", snapshot)
                _save_tx(tx_dir, tx)
                _event(tx_dir, stamp, step_id, tx["state"], step_id)
                if hooks.get("interrupt_after_step") == step_id and tx["state"] in {"APPLYING", "APPLIED"}:
                    _move(tx, "INTERRUPTED", stamp)
                    tx["last_error"] = f"interrupted after {step_id}"
                    break
            tx["mutation_in_progress"] = False
            tx["owner_pid"] = None
            _save_tx(tx_dir, tx)
            _sync(tx_dir, evidence)
        except InstallError as exc:
            target = exc.state if exc.state in {"INTERRUPTED", "FAILED_SAFE"} else "FAILED_SAFE"
            if tx["state"] == "APPLYING" and target != tx["state"]:
                _move(tx, target, stamp)
            elif tx["state"] == "APPLIED" and target in {"FAILED_SAFE", "INTERRUPTED"}:
                _move(tx, target, stamp)
            tx["last_error"] = str(exc)
            if exc.failure_class:
                tx["live_failure_class"] = exc.failure_class
            if (
                exc.failure_class == "ROLLBACK_REQUIRED"
                and current_step in constants.HOST_MUTATION_STEPS
                and current_step not in done
            ):
                required = [step for step in (tx.get("rollback_required_steps") or []) if isinstance(step, str)]
                if current_step not in required:
                    required.append(current_step)
                tx["rollback_required_steps"] = required
            tx["mutation_in_progress"] = False
            tx["owner_pid"] = None
            _save_tx(tx_dir, tx)
            _event(tx_dir, stamp, "apply", tx["state"], str(exc))
            _sync(tx_dir, evidence)
            return exc.exit_code, _payload(
                "apply",
                tx,
                limitations=tx.get("limitations") or [],
                last_error=str(exc),
                live_failure_class=exc.failure_class,
            )
        health = read_json(tx_dir / "HEALTH.json") if (tx_dir / "HEALTH.json").is_file() else _blank_health(
            tx["transaction_id"], stamp, str(evidence)
        )
        return _exit_for(tx["state"]), _payload(
            "apply",
            tx,
            health_overall=health.get("overall"),
            components=health.get("components"),
            limitations=tx.get("limitations") or [],
            replayed=False,
        )


def status(ctx: dict) -> tuple[int, dict]:
    guard_readonly_command(ctx)
    stamp = _clock(ctx.get("as_of"))
    state_dir = ctx["state_dir"]
    with Lock(state_dir):
        tx, tx_dir, _config, _unused = _open_existing(ctx)
        if tx["state"] in TRANSIENT and not pid_alive(tx.get("owner_pid")):
            _move(tx, "INTERRUPTED", stamp)
            tx["mutation_in_progress"] = False
            tx["last_error"] = tx.get("last_error") or "process died mid-transaction"
            _save_tx(tx_dir, tx)
            _sync(tx_dir, Path(tx["evidence_dir"]))
        elif tx["state"] == "APPLIED" and not pid_alive(tx.get("owner_pid")) and tx.get("mutation_in_progress"):
            _move(tx, "INTERRUPTED", stamp)
            tx["mutation_in_progress"] = False
            _save_tx(tx_dir, tx)
            _sync(tx_dir, Path(tx["evidence_dir"]))
        health = {}
        if (tx_dir / "HEALTH.json").is_file():
            health = read_json(tx_dir / "HEALTH.json")
        return _exit_for(tx["state"]), _payload(
            "status",
            tx,
            health_overall=health.get("overall", "UNKNOWN"),
            limitations=tx.get("limitations") or [],
            completed_steps=tx.get("completed_steps") or [],
            phase=tx.get("phase"),
        )


def _reverse_steps(completed: list[str], already: list[str], extras: list[str] | None = None) -> list[str]:
    order = {step: index for index, step in enumerate(constants.APPLY_STEPS)}
    sequence = [step for step in completed if step in constants.HOST_MUTATION_STEPS]
    for step in extras or []:
        if step not in constants.HOST_MUTATION_STEPS or step in sequence:
            continue
        slot = len(sequence)
        for index, existing in enumerate(sequence):
            if order.get(step, len(order)) < order.get(existing, len(order)):
                slot = index
                break
        sequence.insert(slot, step)
    return [step for step in reversed(sequence) if step not in already]


def _rollback_extras(tx: dict, tx_dir: Path, prefix: Path) -> list[str]:
    extras: list[str] = []
    recorded = list(tx.get("rollback_required_steps") or []) + partial_mutation_steps(tx_dir)
    for step in recorded:
        if isinstance(step, str) and step not in extras:
            extras.append(step)
    if optics_cli_present(prefix) and "install_optics_cli" not in extras:
        extras.append("install_optics_cli")
    if agent_sdk_present(prefix) and "install_agent_sdks" not in extras:
        extras.append("install_agent_sdks")
    return extras


def rollback(ctx: dict) -> tuple[int, dict]:
    _require_yes(bool(ctx.get("yes")), "rollback")
    stamp = _clock(ctx.get("as_of"))
    with Lock(ctx["state_dir"]):
        tx, tx_dir, config, _unused = _open_existing(ctx)
        evidence = Path(tx["evidence_dir"])
        hooks = _fixture_hooks(config, bool(ctx.get("fixture_host")))
        if tx["state"] == "APPLIED":
            _move(tx, "INTERRUPTED", stamp)
        if tx["state"] not in {
            "HEALTHY",
            "DEGRADED",
            "FAILED_SAFE",
            "INTERRUPTED",
            "APPLYING",
            "ROLLING_BACK",
            *RESIDUAL_STATES,
        }:
            raise InstallError(f"Rollback cannot start from {tx['state']}.", exit_code=10, state=tx["state"])
        snapshot = read_json(tx_dir / "HOST-SNAPSHOT.json")
        bundle = Path(tx["bundle_dir"])
        grant = None if ctx.get("fixture_host") else _live_grant(ctx, tx, tx_dir, config, bundle, snapshot)
        if tx["state"] in {"INTERRUPTED", "APPLYING", "HEALTHY", "DEGRADED", "FAILED_SAFE"} or tx["state"] in RESIDUAL_STATES:
            _move(tx, "ROLLING_BACK", stamp)
        mutator, _stage, _prefix = _mutator(ctx, snapshot, config, grant)
        prefix = getattr(mutator, "prefix", _prefix)
        step_ctx = _step_ctx(tx, config, bundle, hooks, tx_dir / "observe-config.json", _boot_hold_root(ctx, ctx["state_dir"]))
        tx["mutation_in_progress"] = True
        tx["owner_pid"] = os.getpid()
        tx["phase"] = "rollback"
        already = list(tx.get("rollback_completed_steps") or [])
        if optics_cli_present(prefix):
            already = [step for step in already if step != "install_optics_cli"]
        if agent_sdk_present(prefix):
            already = [step for step in already if step != "install_agent_sdks"]
        pending = _reverse_steps(
            list(tx.get("completed_steps") or []),
            already,
            _rollback_extras(tx, tx_dir, prefix),
        )
        _save_tx(tx_dir, tx)
        try:
            for step_id in pending:
                mutator.rollback_step(step_id, step_ctx)
                tx["rollback_completed_steps"].append(step_id)
                write_json(tx_dir / "HOST-SNAPSHOT.json", snapshot)
                _save_tx(tx_dir, tx)
                _event(tx_dir, stamp, "rollback:" + step_id, tx["state"], step_id)
                if hooks.get("rollback_interrupt_after_step") == step_id:
                    _move(tx, "INTERRUPTED", stamp)
                    tx["last_error"] = f"rollback interrupted after {step_id}"
                    break
            else:
                mutator.unpin_remaining(step_ctx)
                write_json(tx_dir / "HOST-SNAPSHOT.json", snapshot)
                _move(tx, "ROLLED_BACK", stamp)
                tx["last_error"] = None
            health = derive(snapshot, config, limitations=tx.get("limitations") or [])
            health.update(
                {
                    "transaction_id": tx["transaction_id"],
                    "as_of_et": stamp,
                    "evidence_paths": [str(evidence)],
                }
            )
            write_json(tx_dir / "HEALTH.json", health)
            tx["health_overall"] = health["overall"]
            tx["mutation_in_progress"] = False
            tx["owner_pid"] = None
            _save_tx(tx_dir, tx)
            _sync(tx_dir, evidence)
        except InstallError as exc:
            tx["mutation_in_progress"] = False
            tx["owner_pid"] = None
            if exc.failure_class:
                tx["live_failure_class"] = exc.failure_class
            if tx["state"] == "ROLLING_BACK":
                target = "INTERRUPTED" if exc.state == "INTERRUPTED" else "FAILED_SAFE"
                _move(tx, target, stamp)
            _save_tx(tx_dir, tx)
            _sync(tx_dir, evidence)
            raise
        return _exit_for(tx["state"]), _payload(
            "rollback",
            tx,
            limitations=["Run verify-removal before treating the host as clean."],
            health_overall=tx.get("health_overall", "UNKNOWN"),
        )


def uninstall(ctx: dict) -> tuple[int, dict]:
    _require_yes(bool(ctx.get("yes")), "uninstall")
    stamp = _clock(ctx.get("as_of"))
    scope = ctx.get("scope") or "all"
    if scope == "all_product_owned":
        scope = "all"
    with Lock(ctx["state_dir"]):
        tx, tx_dir, config, _unused = _open_existing(ctx)
        evidence = Path(tx["evidence_dir"])
        hooks = _fixture_hooks(config, bool(ctx.get("fixture_host")))
        if tx["state"] == "ROLLED_BACK":
            raise InstallError(
                "Rollback already reversed this transaction. Run verify-removal.",
                exit_code=10,
                state="ROLLED_BACK",
            )
        if tx["state"] == "APPLIED":
            _move(tx, "INTERRUPTED", stamp)
        if tx["state"] == "INTERRUPTED":
            pass
        elif tx["state"] in {"HEALTHY", "DEGRADED", "FAILED_SAFE"} or tx["state"] in RESIDUAL_STATES:
            pass
        else:
            raise InstallError(f"Uninstall cannot start from {tx['state']}.", exit_code=10, state=tx["state"])
        snapshot = read_json(tx_dir / "HOST-SNAPSHOT.json")
        bundle = Path(tx["bundle_dir"])
        grant = None if ctx.get("fixture_host") else _live_grant(ctx, tx, tx_dir, config, bundle, snapshot)
        if tx["state"] == "INTERRUPTED" or tx["state"] in {"HEALTHY", "DEGRADED", "FAILED_SAFE"} or tx["state"] in RESIDUAL_STATES:
            _move(tx, "UNINSTALLING", stamp)
        mutator, _stage, _prefix = _mutator(ctx, snapshot, config, grant)
        step_ctx = _step_ctx(tx, config, bundle, hooks, tx_dir / "observe-config.json", _boot_hold_root(ctx, ctx["state_dir"]))
        tx["scope"] = scope
        tx["phase"] = "uninstall"
        tx["mutation_in_progress"] = True
        tx["owner_pid"] = os.getpid()
        _save_tx(tx_dir, tx)
        try:
            mutator.uninstall(scope, step_ctx)
            if scope in {"pe", "all"}:
                mutator.unpin_remaining(step_ctx)
            write_json(tx_dir / "HOST-SNAPSHOT.json", snapshot)
            health = derive(snapshot, config, limitations=tx.get("limitations") or [])
            health.update(
                {
                    "transaction_id": tx["transaction_id"],
                    "as_of_et": stamp,
                    "evidence_paths": [str(evidence)],
                }
            )
            write_json(tx_dir / "HEALTH.json", health)
            tx["health_overall"] = health["overall"]
            _move(tx, "UNINSTALLED", stamp)
            tx["mutation_in_progress"] = False
            tx["owner_pid"] = None
            _save_tx(tx_dir, tx)
            _event(tx_dir, stamp, "uninstall", "UNINSTALLED", scope)
            _sync(tx_dir, evidence)
        except InstallError as exc:
            tx["mutation_in_progress"] = False
            if exc.failure_class:
                tx["live_failure_class"] = exc.failure_class
            if tx["state"] == "UNINSTALLING":
                target = "INTERRUPTED" if exc.state == "INTERRUPTED" else "FAILED_SAFE"
                _move(tx, target, stamp)
            _save_tx(tx_dir, tx)
            _sync(tx_dir, evidence)
            raise
        return _exit_for(tx["state"]), _payload(
            "uninstall",
            tx,
            limitations=["UNINSTALLED is not removal proof. Run verify-removal."],
            health_overall="UNKNOWN",
            scope=scope,
        )


def verify_removal(ctx: dict) -> tuple[int, dict]:
    guard_readonly_command(ctx)
    stamp = _clock(ctx.get("as_of"))
    scope = ctx.get("scope") or "all"
    if scope == "all_product_owned":
        scope = "all"
    with Lock(ctx["state_dir"]):
        tx, tx_dir, config, _unused = _open_existing(ctx)
        evidence = Path(tx["evidence_dir"])
        if tx["state"] not in {"UNINSTALLED", "ROLLED_BACK", "VERIFIED_REMOVED", "RESIDUAL_PRESENT"}:
            raise InstallError(
                f"verify-removal runs after uninstall or rollback, not from {tx['state']}.",
                exit_code=10,
                state=tx["state"],
            )
        _move(tx, "VERIFYING_REMOVAL", stamp)
        snapshot = read_json(tx_dir / "HOST-SNAPSHOT.json")
        hooks = _fixture_hooks(config, bool(ctx.get("fixture_host")))
        if hooks.get("residual_probe_errors"):
            snapshot["probe_errors"] = list(hooks["residual_probe_errors"])
        stage = assert_safe_root(str(config.get("stage_dir") or (ctx["state_dir"] / "pe-stage")), label="stage_dir")
        prefix = assert_safe_root(str(config.get("prefix") or (ctx["state_dir"] / "prefix")), label="prefix")
        bpffs = _removal_bpffs(ctx, hooks)
        report = inspect_residual(
            snapshot,
            scope=scope,
            prefix=prefix,
            stage=stage,
            iface=str(config.get("iface", "")),
            bpffs=bpffs,
        )
        report["transaction_id"] = tx["transaction_id"]
        report["as_of_et"] = stamp
        if not ctx.get("fixture_host"):
            report["result"] = residual_result(report.get("items") or [], report.get("probe_errors") or [])
        if report["result"] == "PASS":
            report["result"] = "RESIDUAL_FOUND"
        write_json(tx_dir / "RESIDUAL.json", report)
        if report["result"] == "EMPTY":
            _move(tx, "VERIFIED_REMOVED", stamp)
        elif report["result"] == "UNKNOWN":
            _move(tx, "FAILED_SAFE", stamp)
            tx["last_error"] = "residual probe returned UNKNOWN"
        elif report["result"] == "RESIDUAL_FOUND":
            _move(tx, "RESIDUAL_FOUND", stamp)
        else:
            _move(tx, "RESIDUAL_PRESENT", stamp)
        tx["phase"] = "verify-removal"
        tx["scope"] = scope
        _save_tx(tx_dir, tx)
        _event(tx_dir, stamp, "verify-removal", tx["state"], report["result"])
        _sync(tx_dir, evidence)
        return _exit_for(tx["state"]), _payload(
            "verify-removal",
            tx,
            residual_result=report["result"],
            residual_items=report["items"],
            health_overall="UNKNOWN",
            scope=scope,
        )

