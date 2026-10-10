#!/usr/bin/env python3
"""Run the public one-command installer on a lab host.

Does not call enterprise-rows.sh. Does not pass --artifact-trust or
--fixture-host. PROTECTED is a separate invocation and must be refused.
The packaged artifact trust file is the only trust input.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PHASES = (
    ("install", "OBSERVE"),
    ("install", "PROTECTED"),
    ("rollback", "OBSERVE"),
    ("uninstall", "OBSERVE"),
    ("verify-removal", "OBSERVE"),
)


def installer_argv(
    phase: str,
    protection: str,
    *,
    bundle: str,
    policy: str,
    signature: str,
    state_dir: str,
    transaction_id: str | None,
) -> list[str]:
    """Arguments for `python -m vantio_install`. No caller trust and no fixture host."""
    if phase not in {"install", "rollback", "uninstall", "verify-removal"}:
        raise ValueError("phase")
    if protection not in {"OBSERVE", "PROTECTED"}:
        raise ValueError("protection")
    argv = [
        "-m",
        "vantio_install",
        "install",
        "--phase",
        phase,
        "--requested-protection",
        protection,
        "--state-dir",
        state_dir,
        "--policy-file",
        policy,
    ]
    if phase == "install" and protection == "OBSERVE":
        argv.extend(
            [
                "--bundle",
                bundle,
                "--signature-file",
                signature,
                "--config",
                policy,
                "--i-accept-live-mutations",
                "--yes",
            ]
        )
    elif phase in {"rollback", "uninstall"} and transaction_id:
        argv.extend(
            [
                "--transaction-id",
                transaction_id,
                "--i-accept-live-mutations",
                "--yes",
            ]
        )
    elif phase == "verify-removal" and transaction_id:
        argv.extend(["--transaction-id", transaction_id])
    if "--artifact-trust" in argv or "--fixture-host" in argv:
        raise RuntimeError("caller trust is refused")
    return argv


def _row(phase: str, protection: str, body: dict) -> dict:
    return {
        "enterprise_rows": False,
        "phase": phase,
        "proof_state": body.get("proof_state", "NOT_PROVED"),
        "protection": protection,
        "reason": body.get("reason") or body.get("message"),
        "state": body.get("state"),
    }


def run_installer(invoke, *, bundle: str, policy: str, signature: str, state_dir: str) -> list[dict]:
    """Drive the five phases. invoke(argv, env) returns a JSON object."""
    rows: list[dict] = []
    transaction_id: str | None = None
    for phase, protection in PHASES:
        if phase != "install" and transaction_id is None:
            rows.append(
                {
                    "enterprise_rows": False,
                    "phase": phase,
                    "proof_state": "NOT_PROVED",
                    "protection": protection,
                    "reason": "INSTALL_DID_NOT_PLAN",
                    "state": "NOT_RUN",
                }
            )
            continue
        argv = installer_argv(
            phase,
            protection,
            bundle=bundle,
            policy=policy,
            signature=signature,
            state_dir=state_dir,
            transaction_id=transaction_id,
        )
        env = os.environ.copy()
        if "--i-accept-live-mutations" in argv:
            env["VANTIO_INSTALL_ALLOW_LIVE"] = "1"
        else:
            env.pop("VANTIO_INSTALL_ALLOW_LIVE", None)
        body = invoke(argv, env)
        if not isinstance(body, dict):
            body = {"state": "FAILED_SAFE", "reason": "MALFORMED", "proof_state": "NOT_PROVED"}
        if phase == "install" and protection == "OBSERVE" and isinstance(body.get("transaction_id"), str):
            transaction_id = body["transaction_id"]
        rows.append(_row(phase, protection, body))
    return rows


def enrollment_row() -> dict:
    try:
        from vantio_enterprise_protocol.self_service.host_enrollment import run_host_enrollment
    except ImportError:
        return {
            "enterprise_rows": False,
            "proof_state": "NOT_PROVED",
            "reason": "ENROLLMENT_PACKAGE_ABSENT",
            "status": "GAP",
        }
    body = run_host_enrollment()
    body["enterprise_rows"] = False
    body["status"] = "EXECUTED"
    return body


def _invoke_cli(argv: list[str], env: dict) -> dict:
    proc = subprocess.run(
        [sys.executable, *argv],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )
    try:
        body = json.loads(proc.stdout)
    except json.JSONDecodeError:
        body = {
            "message": (proc.stderr or proc.stdout or "")[-500:],
            "proof_state": "NOT_PROVED",
            "reason": "MALFORMED",
            "state": "FAILED_SAFE",
        }
    if isinstance(body, dict):
        return body
    return {"proof_state": "NOT_PROVED", "reason": "MALFORMED", "state": "FAILED_SAFE"}


def main() -> int:
    root = Path(os.environ.get("VANTIO_LAB_ROOT", "/tmp/vantio-lab"))
    record = {
        "enterprise_rows": False,
        "enrollment": enrollment_row(),
        "installer": run_installer(
            _invoke_cli,
            bundle=os.environ.get("VANTIO_INSTALL_BUNDLE", str(root / "bundle")),
            policy=os.environ.get("VANTIO_POLICY_FILE", str(root / "policy.json")),
            signature=os.environ.get("VANTIO_SIGNATURE_FILE", str(root / "signature.json")),
            state_dir=os.environ.get("VANTIO_STATE_DIR", "/var/lib/vantio/install"),
        ),
        "proof_state": "NOT_PROVED",
    }
    destination = Path(os.environ.get("VANTIO_SELF_SERVICE_OUT", "/tmp/self-service-rows.json"))
    destination.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    print(destination.read_text(encoding="utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
