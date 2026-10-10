#!/usr/bin/env python3
"""Run the public one-command installer on a lab host.

Does not run the enterprise row script. Does not pass --artifact-trust or
--fixture-host. PROTECTED is a separate invocation and must be refused.
Lab trust is the process environment, not a caller flag. The packaged
trust files stay empty.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

try:
    from vantio_enterprise_protocol.self_service.host_enrollment import run_host_enrollment
except ImportError:
    run_host_enrollment = None

PHASES = (
    ("install", "OBSERVE"),
    ("install", "PROTECTED"),
    ("rollback", "OBSERVE"),
    ("uninstall", "OBSERVE"),
    ("verify-removal", "OBSERVE"),
)


def up_iface() -> str:
    """Prefer an interface that is already up. ens5 is the usual lab NIC."""
    net = Path("/sys/class/net")
    if not net.is_dir():
        return "ens5"
    names: list[str] = []
    for path in net.iterdir():
        if path.name == "lo":
            continue
        try:
            state = (path / "operstate").read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if state == "up":
            names.append(path.name)
    for preferred in ("ens5", "ens4", "eth0"):
        if preferred in names:
            return preferred
    if names:
        return sorted(names)[0]
    return "ens5"


def _as_root(argv: list[str]) -> list[str]:
    if os.geteuid() == 0:
        return argv
    return ["sudo", *argv]


def install_offline_debs(root: Path) -> None:
    """Install debs copied by the runner. This does not refresh package indexes."""
    debs = sorted(path for path in (root / "debs").glob("*.deb") if path.is_file())
    if not debs:
        return
    argv = _as_root(["dpkg", "-i", *[str(path) for path in debs]])
    for _ in range(5):
        if subprocess.run(argv, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            return


def install_ca_bundle(root: Path) -> None:
    source = root / "ca-certificates.crt"
    if not source.is_file() or source.stat().st_size < 1000:
        return
    _as_root_cp = _as_root(["cp", str(source), "/usr/local/share/ca-certificates/vantio-lab.crt"])
    subprocess.run(_as_root(["mkdir", "-p", "/usr/local/share/ca-certificates"]), check=False)
    subprocess.run(_as_root_cp, check=False)
    subprocess.run(_as_root(["cp", str(source), "/etc/ssl/certs/ca-certificates.crt"]), check=False)


def write_observe_config(path: Path) -> None:
    for directory in (
        Path("/var/lib/vantio/workload"),
        Path("/var/lib/vantio/evidence"),
        Path("/var/lib/vantio/pe-stage"),
        Path("/var/lib/vantio/prefix"),
        Path("/var/lib/vantio/install"),
    ):
        subprocess.run(_as_root(["mkdir", "-p", str(directory)]), check=False)
    config = {
        "artifact_source": "sealed_archive",
        "enforcement": "NOT_ENABLED",
        "enterprise_inclusion": "OPTIONAL_SOURCE_ONLY_NOT_PACKAGED_AUTHORITY",
        "evidence_root": "/var/lib/vantio/evidence",
        "iface": up_iface(),
        "install_mode": "observe-only",
        "install_motion": "customer-local",
        "non_interactive": True,
        "otlp": "DISABLED",
        "path_deny": "disabled",
        "prefix": "/var/lib/vantio/prefix",
        "stage_dir": "/var/lib/vantio/pe-stage",
        "traffic_control": "audit-only",
        "transfer_required": False,
        "transfer_source_cidrs": [],
        "workload_roots": ["/var/lib/vantio/workload"],
    }
    path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def installer_argv(
    phase: str,
    protection: str,
    *,
    bundle: str,
    policy: str,
    signature: str,
    state_dir: str,
    config: str,
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
                config,
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


def run_installer(
    invoke,
    *,
    bundle: str,
    policy: str,
    signature: str,
    state_dir: str,
    config: str,
) -> list[dict]:
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
            config=config,
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
    if run_host_enrollment is None:
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
    install_offline_debs(root)
    install_ca_bundle(root)
    config = root / "config.json"
    write_observe_config(config)
    record = {
        "enterprise_rows": False,
        "enrollment": enrollment_row(),
        "installer": run_installer(
            _invoke_cli,
            bundle=os.environ.get("VANTIO_INSTALL_BUNDLE", str(root / "bundle")),
            policy=os.environ.get("VANTIO_POLICY_FILE", str(root / "policy.json")),
            signature=os.environ.get("VANTIO_SIGNATURE_FILE", str(root / "signature.json")),
            state_dir=os.environ.get("VANTIO_STATE_DIR", "/var/lib/vantio/install"),
            config=os.environ.get("VANTIO_CONFIG_FILE", str(config)),
        ),
        "proof_state": "NOT_PROVED",
    }
    destination = Path(os.environ.get("VANTIO_SELF_SERVICE_OUT", "/tmp/self-service-rows.json"))
    destination.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    print(destination.read_text(encoding="utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
