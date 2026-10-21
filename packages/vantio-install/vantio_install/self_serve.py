"""Customer commands: fetch, host-prep, enroll, and unenroll."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from vantio_install import constants
from vantio_install.bundle_fetch import assert_bundle_dir, fetch_bundle, with_bundle_asset
from vantio_install.engine import Lock, _enforce_runner, _load_tx, _save_tx, _sync, _tx_dir
from vantio_install.enroll import normalize_unit, remove_dropin, write_dropin
from vantio_install.errors import InstallError
from vantio_install.gates import command_payload, require_live_gates
from vantio_install.host_prep import prepare
from vantio_install.license_token import store_license, verify_token
from vantio_install.server_root import server_root
from vantio_install.util import read_json, redact_text, write_json


def run_fetch(ctx: dict) -> tuple[int, dict]:
    require_live_gates(ctx)
    raw = ctx.get("license")
    if not isinstance(raw, str) or not raw.strip():
        return _fail("fetch", "LICENSE_MISSING", "A license token or @file is required.", constants.EXIT_USAGE)
    try:
        token = _read_license_arg(raw)
    except OSError:
        return _fail("fetch", "LICENSE_FILE_MISSING", "The license file could not be read.", constants.EXIT_USAGE)
    if not token:
        return _fail("fetch", "LICENSE_MISSING", "The license file is empty.", constants.EXIT_USAGE)
    checked = verify_token(token)
    if not checked["ok"]:
        return _license_failure("fetch", checked)
    bundle_raw = ctx.get("bundle_dir")
    if not isinstance(bundle_raw, str) or not bundle_raw:
        return _fail("fetch", "BUNDLE_DIR_REQUIRED", "fetch needs --bundle-dir.", constants.EXIT_USAGE)
    try:
        bundle_dir = assert_bundle_dir(bundle_raw)
    except ValueError:
        return _fail("fetch", "BUNDLE_DIR_REFUSED", "The bundle directory is not an allowed path.", constants.EXIT_USAGE)
    endpoint = with_bundle_asset(str(ctx.get("endpoint") or constants.FETCH_DEFAULT_ENDPOINT))
    if token in endpoint:
        return _fail("fetch", "TOKEN_IN_URL", "The license token must not be placed in the URL.", constants.EXIT_USAGE)
    root = server_root(ctx, create=True)
    store_license(token, root / constants.LICENSE_RELATIVE)
    result = fetch_bundle(endpoint, bundle_dir, token=token)
    license_fields = checked["license"]
    _maybe_record_license(ctx, license_fields)
    payload = command_payload(
        "fetch",
        "VERIFIED" if result["ok"] else "FAILED_SAFE",
        str(result["message"]),
        reason=result["reason"],
        byte_count=result.get("byte_count", 0),
        endpoint_host=result.get("endpoint_host", ""),
        license=license_fields,
        bundle_dir=str(bundle_dir) if result["ok"] else None,
    )
    if "http_status" in result:
        payload["http_status"] = result["http_status"]
    return int(result["exit_code"]), payload


def run_host_prep(ctx: dict) -> tuple[int, dict]:
    require_live_gates(ctx)
    if not ctx.get("write_lsm"):
        return _fail("host-prep", "WRITE_LSM_REQUIRED", "host-prep needs --write-lsm.", constants.EXIT_USAGE)
    if not ctx.get("accept_reboot"):
        return _fail(
            "host-prep",
            "REBOOT_ACCEPTANCE_REQUIRED",
            "host-prep needs --i-accept-reboot. The installer does not reboot by itself.",
            constants.EXIT_USAGE,
        )
    root = server_root(ctx, create=True)
    calls: list[list[str]] = []

    def updater(argv: list[str]) -> int:
        if any(part == "reboot" for part in argv):
            raise InstallError("The installer does not reboot.", exit_code=4, state="FAILED_SAFE")
        calls.append(list(argv))
        if ctx.get("fixture_host"):
            return 0
        return int(subprocess.run(argv, check=False).returncode)

    prepared = prepare(root, updater)
    _attach_host_prep(ctx, prepared, calls)
    code = constants.EXIT_OK if prepared["ok"] else constants.EXIT_BLOCKED
    state = "RECORDED" if prepared["ok"] else "FAILED_SAFE"
    return code, command_payload(
        "host-prep",
        state,
        str(prepared["message"]),
        reason=prepared["result"],
        pre_lsm=prepared["pre_lsm"],
        boot_id=prepared["boot_id"],
        dropin_sha256=prepared["dropin_sha256"],
        transaction_id=ctx.get("transaction_id"),
        commands=calls,
    )


def run_enroll(ctx: dict) -> tuple[int, dict]:
    return _enroll(ctx, remove=False)


def run_unenroll(ctx: dict) -> tuple[int, dict]:
    return _enroll(ctx, remove=True)


def _enroll(ctx: dict, *, remove: bool) -> tuple[int, dict]:
    command = "unenroll" if remove else "enroll"
    require_live_gates(ctx)
    unit = str(ctx.get("unit") or "")
    normalized = normalize_unit(unit)
    if normalized is None:
        return _fail(command, "UNIT_REFUSED", "That unit name is refused.", constants.EXIT_BLOCKED)
    tx_id = ctx.get("transaction_id")
    if not tx_id:
        return _fail(command, "TRANSACTION_REQUIRED", "This command needs --transaction-id.", constants.EXIT_USAGE)
    root = server_root(ctx, create=True)
    state_dir = Path(ctx["state_dir"])
    with Lock(state_dir):
        tx_dir = _tx_dir(state_dir, tx_id)
        tx_path = tx_dir / "TRANSACTION.json"
        if not tx_path.is_file():
            return _fail(command, "TRANSACTION_MISSING", "The transaction was not found.", constants.EXIT_USAGE)
        tx = _load_tx(tx_path)
        snapshot_path = tx_dir / "HOST-SNAPSHOT.json"
        snapshot = read_json(snapshot_path) if snapshot_path.is_file() else {}
        runner = _enforce_runner(ctx, snapshot)
        if remove:
            result = remove_dropin(root, normalized, runner)
        else:
            result = write_dropin(root, normalized, runner)
        units = [item for item in tx.get("enrolled_units") or [] if isinstance(item, str)]
        if result["ok"] and not remove and normalized not in units:
            units.append(normalized)
        if result["ok"] and remove:
            units = [item for item in units if item != normalized]
        tx["enrolled_units"] = units
        _save_tx(tx_dir, tx)
        if snapshot_path.is_file():
            write_json(snapshot_path, snapshot)
        evidence = tx.get("evidence_dir")
        if evidence:
            _sync(tx_dir, Path(str(evidence)))
    code = constants.EXIT_OK if result["ok"] else constants.EXIT_BLOCKED
    return code, command_payload(
        command,
        "RECORDED" if result["ok"] else "FAILED_SAFE",
        str(result["reason"]),
        reason=result["reason"],
        unit=result.get("unit", normalized),
        transaction_id=tx_id,
        enrolled_units=units,
        evidence_dir=tx.get("evidence_dir"),
    )


def manifest_has_exec_deny(document: dict) -> bool:
    caps = document.get("capabilities")
    if isinstance(caps, list) and "exec_deny" in caps:
        return True
    kernel = document.get("kernel_capabilities")
    if isinstance(kernel, list) and "exec_deny" in kernel:
        return True
    if isinstance(kernel, dict) and kernel.get("exec_deny") is True:
        return True
    return False


def _read_license_arg(raw: str) -> str:
    text = raw.strip()
    if text.startswith("@"):
        return Path(text[1:]).read_text(encoding="ascii").strip()
    return text


def _license_failure(command: str, checked: dict) -> tuple[int, dict]:
    reason = str(checked["reason"])
    message = reason
    if reason == "EXPIRED":
        message = "license canceled or expired"
    return _fail(command, reason, message, constants.EXIT_BLOCKED, exp=checked.get("exp"))


def _fail(command: str, reason: str, message: str, code: int, **extra: object) -> tuple[int, dict]:
    safe = redact_text(message)
    return code, command_payload(command, "FAILED_SAFE", safe, reason=reason, **extra)


def _attach_host_prep(ctx: dict, prepared: dict, calls: list[list[str]]) -> None:
    record = {
        "result": prepared["result"],
        "pre_lsm": prepared["pre_lsm"],
        "boot_id": prepared["boot_id"],
        "dropin_sha256": prepared["dropin_sha256"],
        "message": prepared["message"],
        "commands": calls,
    }
    tx_id = ctx.get("transaction_id")
    state_dir = Path(ctx["state_dir"])
    if not tx_id:
        state_dir.mkdir(parents=True, exist_ok=True)
        write_json(state_dir / "HOST-PREP.json", record)
        return
    tx_dir = _tx_dir(state_dir, str(tx_id))
    tx_path = tx_dir / "TRANSACTION.json"
    if not tx_path.is_file():
        state_dir.mkdir(parents=True, exist_ok=True)
        write_json(state_dir / "HOST-PREP.json", record)
        return
    with Lock(state_dir):
        tx = _load_tx(tx_path)
        tx["host_prep"] = record
        _save_tx(tx_dir, tx)
        evidence = tx.get("evidence_dir")
        if evidence:
            _sync(tx_dir, Path(str(evidence)))


def _maybe_record_license(ctx: dict, fields: dict) -> None:
    tx_id = ctx.get("transaction_id")
    if not tx_id:
        return
    state_dir = Path(ctx["state_dir"])
    tx_dir = _tx_dir(state_dir, str(tx_id))
    health_path = tx_dir / "HEALTH.json"
    tx_path = tx_dir / "TRANSACTION.json"
    if not tx_path.is_file() or not health_path.is_file():
        return
    with Lock(state_dir):
        tx = _load_tx(tx_path)
        health = read_json(health_path)
        health["license"] = fields
        tx["license"] = fields
        write_json(health_path, health)
        _save_tx(tx_dir, tx)
        evidence = tx.get("evidence_dir")
        if evidence:
            _sync(tx_dir, Path(str(evidence)))


def load_policy_file(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))
