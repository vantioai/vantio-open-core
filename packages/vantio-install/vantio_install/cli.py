"""CLI for vantio-install. Stdout is one JSON object."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vantio_install import constants
from vantio_install.enforce_apply import apply_enforce_enrolled
from vantio_install.engine import apply, plan, rollback, status, uninstall, verify_removal
from vantio_install.errors import InstallError
from vantio_install.gates import command_payload
from vantio_install.one_command import run_one_command
from vantio_install.self_serve import run_enroll, run_fetch, run_host_prep, run_unenroll
from vantio_install.util import now_et


def _apply(ctx: dict) -> tuple[int, dict]:
    if ctx.get("exec_preset") and not ctx.get("enforce_enrolled"):
        return constants.EXIT_BLOCKED, command_payload(
            "apply",
            "FAILED_SAFE",
            "Pass --enforce-enrolled with --exec-preset.",
            reason="EXEC_PRESET_REQUIRES_ENFORCE",
            transaction_id=ctx.get("transaction_id"),
        )
    if ctx.get("enforce_enrolled"):
        return apply_enforce_enrolled(ctx)
    return apply(ctx)

_COMMANDS = {
    "plan": plan,
    "apply": _apply,
    "status": status,
    "rollback": rollback,
    "uninstall": uninstall,
    "verify-removal": verify_removal,
    "install": run_one_command,
    "fetch": run_fetch,
    "host-prep": run_host_prep,
    "enroll": run_enroll,
    "unenroll": run_unenroll,
}


def _parser() -> argparse.ArgumentParser:
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--json", action="store_true", help="Machine-readable stdout")
    parent.add_argument("--state-dir", default="/var/lib/vantio/install")
    parent.add_argument("--evidence-dir")
    parent.add_argument("--bundle")
    parent.add_argument("--config")
    parent.add_argument("--transaction-id")
    parent.add_argument("--fixture-host")
    parent.add_argument("--as-of")
    parent.add_argument("--yes", action="store_true")
    parent.add_argument("--scope", default="all", choices=["pe", "optics", "all", "all_product_owned"])
    parent.add_argument("--dry-run", action="store_true")
    parent.add_argument("--i-accept-live-mutations", action="store_true")
    parent.add_argument("--plan", default=None)
    parent.add_argument("--plan-sha256", default=None)
    parent.add_argument("--phase", default="install", choices=["install", "rollback", "uninstall", "verify-removal"])
    parent.add_argument("--signature-file", default=None)
    parent.add_argument("--artifact-url", default=None)
    parent.add_argument("--requested-protection", default="OBSERVE", choices=["OBSERVE", "PROTECTED"])
    parent.add_argument("--policy-file", default=None)
    parent.add_argument("--artifact-trust", default=None)
    parent.add_argument("--license", default=None)
    parent.add_argument("--endpoint", default=constants.FETCH_DEFAULT_ENDPOINT)
    parent.add_argument("--bundle-dir", default=None)
    parent.add_argument("--write-lsm", action="store_true")
    parent.add_argument("--i-accept-reboot", action="store_true")
    parent.add_argument("--enforce-enrolled", action="store_true")
    parent.add_argument("--exec-preset", default=None)
    parent.add_argument("--unit", default=None)
    parser = argparse.ArgumentParser(prog="vantio-install")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in _COMMANDS:
        sub.add_parser(name, parents=[parent])
    return parser


def _ctx(args: argparse.Namespace) -> dict:
    return {
        "command": args.command,
        "bundle": Path(args.bundle) if args.bundle else None,
        "config_path": Path(args.config) if args.config else None,
        "state_dir": Path(args.state_dir),
        "evidence_dir": Path(args.evidence_dir) if args.evidence_dir else None,
        "fixture_host": Path(args.fixture_host) if args.fixture_host else None,
        "transaction_id": args.transaction_id,
        "as_of": args.as_of,
        "yes": bool(args.yes),
        "scope": args.scope,
        "dry_run_flag": bool(args.dry_run),
        "accept_live_mutations": bool(args.i_accept_live_mutations),
        "plan_path": Path(args.plan) if args.plan else None,
        "plan_sha256": args.plan_sha256,
        "phase": args.phase,
        "signature_file": Path(args.signature_file) if args.signature_file else None,
        "artifact_url": args.artifact_url,
        "requested_protection": args.requested_protection,
        "policy_file": Path(args.policy_file) if args.policy_file else None,
        "artifact_trust": Path(args.artifact_trust) if args.artifact_trust else None,
        "license": args.license,
        "endpoint": args.endpoint,
        "bundle_dir": args.bundle_dir,
        "write_lsm": bool(args.write_lsm),
        "accept_reboot": bool(args.i_accept_reboot),
        "enforce_enrolled": bool(args.enforce_enrolled),
        "exec_preset": args.exec_preset,
        "unit": args.unit,
    }


def _error_payload(command: str | None, tx_id: str | None, state: str, message: str) -> dict:
    return {
        "command": command,
        "transaction_id": tx_id,
        "state": state,
        "evidence_dir": None,
        "proof_state": constants.PROOF_STATE,
        "proof_ceiling": constants.PROOF_CEILING,
        "as_of_et": now_et(),
        "message": message,
        "installer_version": constants.INSTALLER_VERSION,
    }


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return int(code) if isinstance(code, int) else 10
    command = _COMMANDS.get(args.command)
    if command is None:
        payload = _error_payload(args.command, args.transaction_id, "FAILED_SAFE", "Unknown command.")
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return constants.EXIT_USAGE
    try:
        code, payload = command(_ctx(args))
    except InstallError as exc:
        payload = _error_payload(args.command, args.transaction_id, exc.state, str(exc))
        if exc.failure_class:
            payload["live_failure_class"] = exc.failure_class
        code = exc.exit_code
    except Exception as exc:  # noqa: BLE001 — last-resort crash envelope
        payload = _error_payload(args.command, args.transaction_id, "FAILED_SAFE", exc.__class__.__name__)
        code = constants.EXIT_CRASH
    if payload.get("proof_state") in constants.FORBIDDEN_PROOF_STATES:
        payload["proof_state"] = constants.PROOF_STATE
        payload["state"] = "FAILED_SAFE"
        code = constants.EXIT_FAILED_SAFE
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
