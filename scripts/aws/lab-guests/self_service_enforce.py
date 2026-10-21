#!/usr/bin/env python3
"""Lab battery for observe, host-prep, reboot, and enforce.

The installer does not reboot. When VANTIO_LAB_SCHEDULE_REBOOT=1 this script
schedules the workflow reboot after host-prep. A test token is minted in the
workflow process. Only the public key and the token file are written. The
guest installs that public key through the test-only license override.

Rows keep enterprise_rows and redteam_brain false. The license token is not
written into the row JSON.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from vantio_install.cli import main as install_main
from vantio_install.health import bpf_lsm_active
from vantio_install.license_token import issue_token, license_trust_override, store_license
from vantio_install.signed_policy import DevPublicKey, dev_trust, sign_policy

PHASES_PRE_READY = ("plan", "apply-observe", "host-prep")
PHASES_POST = ("apply-enforce", "enroll", "probe", "uninstall", "verify-removal")
UNIT = "lab-workload"


def schedule_workflow_reboot() -> bool:
    """Schedule the lab reboot. Returns whether a timer was requested."""
    if os.environ.get("VANTIO_LAB_SCHEDULE_REBOOT") != "1":
        return False
    proc = subprocess.run(
        ["systemd-run", "--on-active=45s", "--unit", "vantio-lab-reboot", "systemctl", "reboot"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.returncode == 0


def run_pre(invoke, *, lsm_has_bpf: bool, schedule_reboot) -> dict:
    """Steps before the workflow reboot."""
    steps: list[dict] = []
    if not lsm_has_bpf:
        steps.append(_call(invoke, "host-prep"))
        requested = bool(schedule_reboot())
        return {
            "order": "host-prep-before-plan",
            "reboot_requested": requested,
            "steps": steps,
            "observe_done": False,
        }
    steps.append(_call(invoke, "plan"))
    steps.append(_call(invoke, "apply-observe"))
    steps.append(_call(invoke, "host-prep"))
    requested = bool(schedule_reboot())
    observe_done = steps[0]["code"] == 0 and steps[1]["code"] == 0
    return {
        "order": "plan-apply-host-prep",
        "reboot_requested": requested,
        "steps": steps,
        "observe_done": observe_done,
    }


def run_post(invoke, *, observe_done: bool, probe, grub_dropin_present) -> dict:
    """Steps after the workflow reboot."""
    steps: list[dict] = []
    if not observe_done:
        steps.append(_call(invoke, "plan"))
        steps.append(_call(invoke, "apply-observe"))
    steps.append(_call(invoke, "apply-enforce"))
    steps.append(_call(invoke, "enroll"))
    probed = probe()
    steps.append({"phase": "probe", "code": 0, "body": probed})
    steps.append(_call(invoke, "uninstall"))
    steps.append(_call(invoke, "verify-removal"))
    verify = next(item for item in steps if item["phase"] == "verify-removal")
    return {
        "steps": steps,
        "probes": probed,
        "verify_state": (verify["body"] or {}).get("state"),
        "grub_dropin": bool(grub_dropin_present()),
    }


def grade(document: dict) -> dict:
    """PASS only when the enforce battery's removal and errno rows hold."""
    reasons: list[str] = []
    if document.get("enterprise_rows") is not False:
        reasons.append("enterprise_rows")
    if document.get("redteam_brain") is not False:
        reasons.append("redteam_brain")
    pre = document.get("pre") if isinstance(document.get("pre"), dict) else {}
    post = document.get("post") if isinstance(document.get("post"), dict) else {}
    if pre.get("reboot_requested") is not True:
        reasons.append("reboot_not_requested")
    probes = post.get("probes") if isinstance(post.get("probes"), dict) else {}
    if probes.get("enrolled_egress_errno") != 1:
        reasons.append("enrolled_egress")
    if probes.get("enrolled_file_errno") != 13:
        reasons.append("enrolled_file")
    if probes.get("unenrolled_egress_errno") == 1 or probes.get("unenrolled_file_errno") == 13:
        reasons.append("unenrolled_affected")
    if post.get("verify_state") != "VERIFIED_REMOVED":
        reasons.append("verify_removal")
    if post.get("grub_dropin") is not False:
        reasons.append("grub_dropin")
    pre_boot = pre.get("boot_id")
    post_boot = post.get("boot_id")
    if isinstance(pre_boot, str) and isinstance(post_boot, str) and pre_boot and post_boot and pre_boot == post_boot:
        reasons.append("boot_unchanged")
    return {"result": "PASS" if not reasons else "FAIL", "reasons": reasons}


def mint(dest: Path) -> dict:
    """Write a test license and an enforce policy. The private keys are not stored."""
    dest.mkdir(parents=True, exist_ok=True)
    license_private = Ed25519PrivateKey.generate()
    dev_private = Ed25519PrivateKey.generate()
    license_public = license_private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    dev_public = dev_private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    def b64(raw: bytes) -> str:
        return base64.b64encode(raw).decode("ascii")

    now = int(time.time())
    payload = {
        "v": 1,
        "kid": "lic-test-lab",
        "sku": "phantom-engine",
        "cus": "cus_lab",
        "sub": "sub_lab",
        "qty": 1,
        "interval": "month",
        "iat": now,
        "exp": now + 7 * 24 * 3600,
        "mode": "test",
    }
    token = issue_token(payload, license_private)
    license_path = dest / "license.token"
    fd = os.open(license_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, token.encode("ascii") + b"\n")
    finally:
        os.close(fd)
    os.chmod(license_path, 0o600)
    (dest / "lab-license-public.json").write_text(
        json.dumps(
            {
                "keys": [
                    {
                        "kid": "lic-test-lab",
                        "alg": "Ed25519",
                        "public_key_b64": b64(license_public),
                        "mode": "test",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    policy = sign_policy(
        {"allow_enforcement": True, "enforcement": "ENROLLED"},
        key_id="dev-nonprod-lab-enforce",
        public_key=dev_public,
        sign=dev_private.sign,
    )
    (dest / "enforce-policy.json").write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")
    (dest / "enforce-dev-public.json").write_text(
        json.dumps(
            {
                "keys": [
                    {
                        "key_id": "dev-nonprod-lab-enforce",
                        "key_class": "dev_non_production",
                        "not_a_production_root": True,
                        "public_key_b64": b64(dev_public),
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    del license_private
    del dev_private
    return {
        "kid": "lic-test-lab",
        "files": [
            "license.token",
            "lab-license-public.json",
            "enforce-policy.json",
            "enforce-dev-public.json",
        ],
    }


def _call(invoke, phase: str) -> dict:
    code, body = invoke(_argv(phase))
    return {"phase": phase, "code": code, "body": _public_body(body)}


def _argv(phase: str) -> list[str]:
    """Argument lists. No caller trust flag and no fixture host."""
    common = ["--state-dir", _env("VANTIO_STATE_DIR", "/var/lib/vantio/install"), "--json"]
    bundle = ["--bundle", _env("VANTIO_INSTALL_BUNDLE", "/var/lib/vantio/bundle")]
    config = ["--config", _env("VANTIO_CONFIG", "/var/lib/vantio/install/observe.json")]
    transaction = ["--transaction-id", _env("VANTIO_TRANSACTION_ID", "vantio-tx-lab")]
    live = ["--i-accept-live-mutations"]
    if phase == "plan":
        argv = ["plan", *bundle, *config, *common, *transaction]
    elif phase == "apply-observe":
        argv = ["apply", *bundle, *config, *common, *transaction, "--yes", *live]
    elif phase == "host-prep":
        argv = ["host-prep", *common, *transaction, "--write-lsm", "--i-accept-reboot", *live]
    elif phase == "apply-enforce":
        argv = [
            "apply",
            *bundle,
            *config,
            *common,
            *transaction,
            "--yes",
            *live,
            "--enforce-enrolled",
            "--policy-file",
            _env("VANTIO_ENFORCE_POLICY", "/var/lib/vantio-lab/enterprise-bundle/enforce-policy.json"),
        ]
    elif phase == "enroll":
        argv = ["enroll", *common, *transaction, "--unit", UNIT, *live]
    elif phase == "uninstall":
        argv = ["uninstall", *common, *transaction, "--yes", "--scope", "all", *live]
    elif phase == "verify-removal":
        argv = ["verify-removal", *common, *transaction, "--scope", "all"]
    else:
        raise ValueError("phase")
    if "--artifact-trust" in argv or "--fixture-host" in argv:
        raise RuntimeError("caller trust is refused")
    return argv


def _public_body(body: dict) -> dict:
    if not isinstance(body, dict):
        return {}
    kept = {}
    for key in ("state", "reason", "protection_state", "message", "preflight_status"):
        if key in body:
            kept[key] = body[key]
    text = json.dumps(kept)
    if "vl1." in text or "BEGIN " in text:
        return {"state": kept.get("state"), "reason": "REDACTED"}
    return kept


def _with_plan(argv: list[str]) -> list[str]:
    """Live apply, uninstall, and rollback need the plan hash. Fixture tests do not."""
    if not argv or argv[0] not in {"apply", "uninstall", "rollback"}:
        return argv
    if "--plan" in argv:
        return argv
    state = Path(_env("VANTIO_STATE_DIR", "/var/lib/vantio/install"))
    tx = _env("VANTIO_TRANSACTION_ID", "vantio-tx-lab")
    plan = state / "transactions" / tx / "PLAN.json"
    if not plan.is_file():
        return argv
    digest = hashlib.sha256(plan.read_bytes()).hexdigest()
    return [*argv, "--plan", str(plan), "--plan-sha256", digest]


def _write_observe_config() -> None:
    path = Path(_env("VANTIO_CONFIG", "/var/lib/vantio/install/observe.json"))
    if path.is_file():
        return
    for directory in (
        Path("/var/lib/vantio/workload"),
        Path("/var/lib/vantio/evidence"),
        Path("/var/lib/vantio/pe-stage"),
        Path("/var/lib/vantio/prefix"),
        path.parent,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    config = {
        "artifact_source": "sealed_archive",
        "enforcement": "NOT_ENABLED",
        "enterprise_inclusion": "OPTIONAL_SOURCE_ONLY_NOT_PACKAGED_AUTHORITY",
        "evidence_root": "/var/lib/vantio/evidence",
        "iface": "ens5",
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


def _env(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def _document(pre: dict, post: dict) -> dict:
    return {
        "battery": "self-service-enforce",
        "enterprise_rows": False,
        "redteam_brain": False,
        "boot_id": post.get("boot_id") or pre.get("boot_id") or "",
        "pre": pre,
        "post": post,
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["mint"] and len(args) == 2:
        summary = mint(Path(args[1]))
        sys.stdout.write(json.dumps(summary, sort_keys=True) + "\n")
        return 0
    phase = os.environ.get("VANTIO_ENFORCE_PHASE", "pre").strip() or "pre"
    out = Path(os.environ.get("VANTIO_SELF_SERVICE_OUT", "/tmp/self-service-enforce-rows.json"))
    _write_observe_config()
    if phase == "pre":
        pre = run_pre(_live_invoke, lsm_has_bpf=_lsm_has_bpf(), schedule_reboot=schedule_workflow_reboot)
        pre["boot_id"] = _boot_id()
        _write(out, _document(pre, {}))
        failed = any(step.get("code") not in {0, None} for step in pre.get("steps") or [])
        return 1 if failed else 0
    if phase == "post":
        previous = {}
        if out.is_file():
            try:
                previous = json.loads(out.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                previous = {}
        pre = previous.get("pre") if isinstance(previous.get("pre"), dict) else {}
        with _overrides():
            post = run_post(
                _live_invoke,
                observe_done=bool(pre.get("observe_done")),
                probe=_probe,
                grub_dropin_present=lambda: Path("/etc/default/grub.d/99-vantio-lsm.cfg").is_file(),
            )
        post["boot_id"] = _boot_id()
        document = _document(pre, post)
        graded = grade(document)
        document["result"] = graded["result"]
        document["reasons"] = graded["reasons"]
        _write(out, document)
        return 0 if graded["result"] == "PASS" else 1
    sys.stderr.write("phase\n")
    return 2


def _live_invoke(argv: list[str]) -> tuple[int, dict]:
    argv = _with_plan(argv)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = install_main(argv)
    try:
        body = json.loads(buffer.getvalue() or "{}")
    except json.JSONDecodeError:
        body = {}
    return code, body if isinstance(body, dict) else {}


@contextlib.contextmanager
def _overrides():
    """Install the minted public keys for this process, then drop them."""
    root = Path(os.environ.get("VANTIO_LAB_ROOT", "/var/lib/vantio-lab/enterprise-bundle"))
    license_doc = json.loads((root / "lab-license-public.json").read_text(encoding="utf-8"))
    dev_doc = json.loads((root / "enforce-dev-public.json").read_text(encoding="utf-8"))
    dev_keys = []
    for item in dev_doc.get("keys") or []:
        raw = base64.b64decode(str(item.get("public_key_b64")), validate=True)
        dev_keys.append(DevPublicKey(str(item.get("key_id")), raw))
    token = (root / "license.token").read_text(encoding="ascii").strip()
    store_license(token, Path("/etc/vantio/license"))
    with license_trust_override(tuple(license_doc.get("keys") or [])), dev_trust(tuple(dev_keys)):
        yield


def _lsm_has_bpf() -> bool:
    path = Path("/sys/kernel/security/lsm")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return bpf_lsm_active(text)


def _boot_id() -> str:
    path = Path("/proc/sys/kernel/random/boot_id")
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _probe() -> dict:
    enrolled = _errno(enrolled=True)
    plain = _errno(enrolled=False)
    return {
        "enrolled_egress_errno": enrolled.get("egress"),
        "enrolled_file_errno": enrolled.get("file"),
        "unenrolled_egress_errno": plain.get("egress"),
        "unenrolled_file_errno": plain.get("file"),
    }


def _errno(*, enrolled: bool) -> dict:
    script = (
        "import errno,socket\n"
        "try:\n"
        "    s=socket.socket(); s.settimeout(2); s.connect(('203.0.113.1', 9)); eg=0\n"
        "except OSError as exc:\n"
        "    eg=exc.errno or 0\n"
        "try:\n"
        "    open('/var/lib/vantio/lab-file-deny','a').close(); fl=0\n"
        "except OSError as exc:\n"
        "    fl=exc.errno or 0\n"
        "print(f'{eg} {fl}')\n"
    )
    argv = ["python3", "-c", script]
    if enrolled:
        argv = [
            "systemd-run",
            "--quiet",
            "--pipe",
            "--wait",
            "--collect",
            "--uid",
            "nobody",
            "--slice",
            "vantio-enrolled.slice",
            *argv,
        ]
    else:
        argv = ["systemd-run", "--quiet", "--pipe", "--wait", "--collect", "--uid", "nobody", *argv]
    proc = subprocess.run(argv, check=False, capture_output=True, text=True)
    parts = (proc.stdout or "").split()
    if len(parts) != 2:
        return {"egress": None, "file": None}
    try:
        return {"egress": int(parts[0]), "file": int(parts[1])}
    except ValueError:
        return {"egress": None, "file": None}


def _write(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
