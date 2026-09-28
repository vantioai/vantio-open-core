"""CLI for vantio-install. Stdout is one JSON object."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from vantio_install import constants
from vantio_install.engine import apply, plan, rollback, status, uninstall, verify_removal
from vantio_install.errors import InstallError
from vantio_install.util import now_et

_COMMANDS = {
    "plan": plan,
    "apply": apply,
    "status": status,
    "rollback": rollback,
    "uninstall": uninstall,
    "verify-removal": verify_removal,
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
