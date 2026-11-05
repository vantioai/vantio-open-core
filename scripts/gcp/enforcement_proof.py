#!/usr/bin/env python3
"""Customer-install enforcement proof on one Ubuntu 24.04 lab VM.

The git tip is a Phantom Engine commit. It is not a seal digest.
gcp-lab-provision.yml stays the sealed-bundle path and is not this command.

This module does not call GCP unless GCP_LAB_EXECUTE=1.
It does not run scripts/enforcement_proof_lab.sh. The guest does, over IAP.
live_enforcement stays NOT_PROVEN. This file cannot write PROVEN.

Audience: INTERNAL_CLEAN_HOST_PROOF
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shlex
import subprocess
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, Mapping, Sequence

import lab_auto as lab
import offline_deliver as od

PE_REPO = "vantioai/vantio-phantom-engine"
PE_GIT_SHA = "864289cb2c9c4135d74233c74c6655087de3f20d"
WORKFLOW_FILE = "gcp-lab-enforcement-proof.yml"
WORKFLOW_REF = f"vantioai/vantio-open-core/.github/workflows/{WORKFLOW_FILE}@refs/heads/main"
LAB_DIR = "/var/lib/vantio-enforcement-proof"
PRE_REBOOT_DIR = "/var/lib/vantio-enforcement-proof-pre-reboot"
GUEST_DIR = od.GUEST_DIR
GUEST_LOADER = f"{GUEST_DIR}/vantio-loader"
GUEST_SCRIPT = f"{GUEST_DIR}/enforcement_proof_lab.sh"
GUEST_ENV = f"{GUEST_DIR}/proof.env"
GUEST_WRAPPER = f"{GUEST_DIR}/run-proof-phase.sh"
SLICES = ("full", "reboot-pre", "reboot-post")
SAME_BOOT = frozenset({"file-deny", "reboot-pre", "expired-key", "uninstall", "uninstall-negative"})
SCRIPT_PHASES = frozenset({"compare", "reboot-post", *SAME_BOOT})
MIN_MINUTES = 90
HOST_RE = re.compile(r"^[a-z][a-z0-9-]{2,39}$")
INSTANCE_RE = re.compile(r"^vantio-gcp-lab-[a-z0-9][a-z0-9-]{0,46}$")
ELF_MAGIC = b"\x7fELF"
PRIVATE_MARKER = re.compile(
    r"BEGIN (?:OPENSSH )?PRIVATE KEY"
    r"|GOOGLE_APPLICATION_CREDENTIALS="
    r"|/var/lib/vantio/production"
    r"|production-signing-key"
)
LINE_VALUES = {
    "compare": frozenset(
        {"PASS", "REFUSED_LSM", "INCONCLUSIVE", "FAIL_OPEN", "FAIL_UNATTRIBUTED", "FAIL_UNSCOPED", "NOT_ENFORCING"}
    ),
    "file_deny": frozenset(
        {"PASS", "REFUSED_LSM", "NOT_ENFORCING", "FAIL_OPEN", "FAIL_UNATTRIBUTED", "INCONCLUSIVE"}
    ),
    "license_exp_claim": frozenset({"NOT_PROVEN"}),
    "license_exp_observation": frozenset({"NOT_CONSULTED", "REFUSED"}),
    "expired_key": frozenset(
        {"FAIL_private_key_remains", "FAIL_production_key_path", "FAIL_credentials_set", "INCONCLUSIVE"}
    ),
    "uninstall": frozenset(
        {"VERIFIED", "RESIDUAL", "REFUSED_OR_UNKNOWN", "NOT_RUN_NO_APPROVAL", "REFUSED_NOT_ENROLLED"}
    ),
    "uninstall_negative": frozenset({"REFUSED", "UNEXPECTED", "FAIL_PIN_MISSING"}),
    "reboot_pre": frozenset({"RECORDED"}),
    "reboot_wiped": frozenset({"NOT_RUN", "PASS", "FAIL_PINS_SURVIVED", "INCONCLUSIVE"}),
    "reboot_restored": frozenset({"NOT_RUN", "PASS", "REFUSED_LSM"}),
    "reboot_marker_open": frozenset({"absent"}),
    "live_enforcement": frozenset({"NOT_PROVEN"}),
    "phase_order": frozenset({"compare_required"}),
    "bpf_lsm": frozenset({"present", "absent"}),
    "audit_banner": frozenset(
        {"AUDIT", "REFUSED_LSM", "REFUSED_IFACE", "NOT_ENFORCING", "ENFORCING", "LOADER_EXITED", "TIMEOUT"}
    ),
    "enforce_banner": frozenset(
        {"AUDIT", "REFUSED_LSM", "REFUSED_IFACE", "NOT_ENFORCING", "ENFORCING", "LOADER_EXITED", "TIMEOUT"}
    ),
    "file_deny_banner": frozenset(
        {"AUDIT", "REFUSED_LSM", "REFUSED_IFACE", "NOT_ENFORCING", "ENFORCING", "LOADER_EXITED", "TIMEOUT"}
    ),
    "file_deny_row": frozenset({"yes", "no"}),
    "ledger_network_block": frozenset({"yes", "no"}),
}
CONNECT_RE = re.compile(
    r"^connect where=(?:inside|outside) result=(?:connected|timeout|error|cgroup_join_failed|setuid_failed) "
    r"errno=[0-9]+(?: elapsed_ms=[0-9.]+)?$"
)
OPEN_RE = re.compile(r"^result=(?:ok|error|cgroup_join_failed|setuid_failed) errno=[0-9]+$")
BOOT_RE = re.compile(r"^[0-9a-f-]{1,80}$")
LOADER_LIB_OK = re.compile(
    r"linux-vdso|ld-linux|libc\.so|libm\.so|libgcc_s\.so|libpthread\.so|libdl\.so|librt\.so|not a dynamic executable"
)
LOADER_LIB_BAD = re.compile(r"libssl|libcrypto")
LAB_FILES = (
    "host.txt",
    "compare.result",
    "audit.ndjson",
    "enforce.ndjson",
    "file-deny.ndjson",
    "expired.ndjson",
    "expired.log",
    "reboot-pre.txt",
    "transcript.txt",
    "uninstall.txt",
    "uninstall-negative.txt",
)
USAGE = "usage: enforcement_proof.py precheck|plan|run|teardown"
REBOOT_COMMAND = (
    "sudo systemctl mask --now google-shutdown-scripts.service >/dev/null 2>&1 || true; "
    "sync; "
    "sudo systemctl reset-failed vantio-proof-reboot >/dev/null 2>&1 || true; "
    "if ! sudo systemd-run --on-active=8s --unit=vantio-proof-reboot systemctl reboot --force; then "
    "sudo systemctl reboot --force || true; "
    "fi"
)
ARCHIVE_COMMAND = (
    "sudo rm -rf /var/lib/vantio-enforcement-proof-pre-reboot && "
    "sudo cp -a /var/lib/vantio-enforcement-proof /var/lib/vantio-enforcement-proof-pre-reboot"
)
PREPARE_COMMAND = (
    "set -euo pipefail; "
    "sudo mkdir -p /var/lib/vantio-lab /var/lib/vantio-enforcement-proof; "
    "sudo chown -R \"$(id -u):$(id -g)\" /var/lib/vantio-lab; "
    "chmod 755 /var/lib/vantio-lab /var/lib/vantio-lab/guest /var/lib/vantio-enforcement-proof; "
    "chmod 600 /var/lib/vantio-lab/guest/proof.env; "
    "chmod 755 /var/lib/vantio-lab/guest/run-proof-phase.sh "
    "/var/lib/vantio-lab/guest/vantio-loader /var/lib/vantio-lab/guest/enforcement_proof_lab.sh; "
    "if [ -f /var/lib/vantio-lab/guest/debs.tar ]; then "
    "mkdir -p /var/lib/vantio-lab/guest/debs; "
    "tar -xf /var/lib/vantio-lab/guest/debs.tar -C /var/lib/vantio-lab/guest/debs; "
    "sudo dpkg -i /var/lib/vantio-lab/guest/debs/*.deb || "
    "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-download --no-install-recommends -f; "
    "sudo dpkg -s python3-cryptography >/dev/null; "
    "fi; "
    "if ! findmnt -n /sys/fs/bpf >/dev/null 2>&1; then "
    "sudo mkdir -p /sys/fs/bpf; "
    "sudo mount -t bpf bpf /sys/fs/bpf; "
    "fi"
)
REFRESH_COMMAND = (
    "chmod 600 /var/lib/vantio-lab/guest/proof.env && "
    "chmod 755 /var/lib/vantio-lab/guest/run-proof-phase.sh"
)


def host_name_ok(value: object) -> bool:
    return (
        isinstance(value, str)
        and HOST_RE.fullmatch(value) is not None
        and not value.startswith(lab.NAME_PREFIX.rstrip("-"))
        and not lab.names_partner(value)
    )


def instance_name_ok(value: object) -> bool:
    return isinstance(value, str) and INSTANCE_RE.fullmatch(value) is not None and len(value) <= 63


def run_go_ok(value: object) -> bool:
    if not isinstance(value, str) or len(value) < 8 or len(value) > 400:
        return False
    return "\n" not in value and "\r" not in value and "\x00" not in value


def approval_ok(value: object) -> bool:
    if value in ("", None):
        return True
    return run_go_ok(value)


def proof_minutes(value: object) -> int:
    try:
        minutes = lab.bounded_minutes(value)
    except ValueError as exc:
        raise SystemExit("stop_after_minutes") from exc
    if minutes < MIN_MINUTES:
        raise SystemExit("stop_after_minutes")
    return minutes


def sha_ok(value: object) -> bool:
    return value == PE_GIT_SHA


def phases_for(slice_name: str) -> tuple[str, ...]:
    """Script-legal order for one slice.

    expired-key and uninstall call require_compare_pass, which demands the
    compare marker boot id equal the current boot. They cannot follow
    reboot-post until compare has run again on the new boot. full and
    reboot-post insert that second compare. The script's uninstall phase
    runs uninstall-negative itself.
    """
    if slice_name == "full":
        return (
            "compare",
            "file-deny",
            "reboot-pre",
            "reboot",
            "reboot-post",
            "compare",
            "expired-key",
            "uninstall",
        )
    if slice_name == "reboot-pre":
        return ("compare", "file-deny", "reboot-pre", "reboot")
    if slice_name == "reboot-post":
        return ("reboot-post", "compare", "expired-key", "uninstall")
    raise SystemExit("slice")


def phase_order_allowed(phases: Sequence[str]) -> bool:
    """True when each phase can see the compare marker the script requires."""
    if tuple(phases) == ("reboot-post",):
        return True
    if phases and phases[0] == "reboot-post":
        if "reboot" in phases[1:] or phases[1:].count("reboot-post"):
            return False
        if len(phases) > 1 and phases[1] != "compare":
            return False
        seen_compare = False
        for phase in phases[1:]:
            if phase == "compare":
                if seen_compare:
                    return False
                seen_compare = True
                continue
            if phase not in SAME_BOOT or not seen_compare:
                return False
        return True
    seen_reboot = False
    seen_compare = False
    seen_compare_since_reboot = False
    compares = 0
    reboot_posts = 0
    for phase in phases:
        if phase == "reboot":
            if seen_reboot or not seen_compare:
                return False
            seen_reboot = True
            seen_compare_since_reboot = False
            continue
        if phase == "compare":
            compares += 1
            if compares > 2:
                return False
            seen_compare = True
            if seen_reboot:
                seen_compare_since_reboot = True
            continue
        if phase == "reboot-post":
            reboot_posts += 1
            if reboot_posts > 1 or not seen_reboot or seen_compare_since_reboot:
                return False
            continue
        if phase not in SAME_BOOT:
            return False
        if not seen_compare or (seen_reboot and not seen_compare_since_reboot):
            return False
    return seen_compare


def public_plan(slice_name: str) -> dict[str, Any]:
    phases = phases_for(slice_name)
    if not phase_order_allowed(phases):
        raise SystemExit("phase_order")
    return {
        "image_family": od.IMAGE_FAMILY,
        "image_project": od.IMAGE_PROJECT,
        "lab_dir": LAB_DIR,
        "live_enforcement": "NOT_PROVEN",
        "machine_type": lab.MACHINE_TYPE,
        "network": od.NETWORK,
        "pe_git_sha": PE_GIT_SHA,
        "pe_repo": PE_REPO,
        "phases": list(phases),
        "project_id": od.LAB_PROJECT,
        "public_ip": False,
        "reboot_command": "mask-google-shutdown-scripts-then-systemctl-reboot-force",
        "reboot_restored": "NOT_RUN",
        "slice": slice_name,
        "zone": lab.ZONE,
    }


def ssh_phase_command(phase: str) -> str:
    if phase not in SCRIPT_PHASES:
        raise SystemExit("phase")
    return f"sudo bash {GUEST_WRAPPER} {shlex.quote(phase)}"


def wrapper_script() -> str:
    names = " ".join(sorted(SCRIPT_PHASES))
    return "\n".join(
        [
            "#!/bin/bash",
            "set -euo pipefail",
            'phase="${1:?}"',
            f"case \"$phase\" in {names.replace(' ', '|')}) ;; *) echo unknown_phase >&2; exit 2 ;; esac",
            "set -a",
            f". {GUEST_ENV}",
            "set +a",
            "unset GOOGLE_APPLICATION_CREDENTIALS || true",
            'if [[ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]]; then echo credentials_set >&2; exit 1; fi',
            f"exec {GUEST_SCRIPT} --i-understand-this-attaches-ebpf \"$phase\"",
            "",
        ]
    )


def env_file_text(env: Mapping[str, str]) -> str:
    go = env.get("PROOF_RUN_GO", "")
    host = env.get("PROOF_HOST_NAME", "")
    if not run_go_ok(go) or not host_name_ok(host):
        raise SystemExit("run_go")
    lines = [
        "VANTIO_LAB_ENFORCEMENT_PROOF=1",
        f"VANTIO_LAB_RUN_GO={shlex.quote(go)}",
        f"VANTIO_LAB_HOST={shlex.quote(host)}",
        f"VANTIO_LAB_HOST_ALLOWLIST={shlex.quote(host)}",
        f"VANTIO_LAB_DIR={shlex.quote(LAB_DIR)}",
        f"VANTIO_LOADER={shlex.quote(GUEST_LOADER)}",
    ]
    approval = env.get("PROOF_UNINSTALL_APPROVAL", "") or ""
    if approval:
        if not approval_ok(approval):
            raise SystemExit("uninstall_approval")
        lines.append(f"VANTIO_LAB_UNINSTALL_APPROVAL={shlex.quote(approval)}")
    return "\n".join(lines) + "\n"


def redact(text: str, env: Mapping[str, str]) -> str:
    cleaned = od.redact(text)
    for key in ("PROOF_RUN_GO", "PROOF_UNINSTALL_APPROVAL"):
        value = env.get(key) or ""
        if value:
            cleaned = cleaned.replace(value, "[redacted]")
    return cleaned


def keep_line(line: str) -> str | None:
    text = line.strip()
    if not text or "=" not in text:
        return None
    key, value = text.split("=", 1)
    allowed = LINE_VALUES.get(key)
    if allowed is not None:
        return text if value in allowed else None
    if key in {"audit_outside", "audit_inside", "enforce_inside", "enforce_outside"}:
        return text if CONNECT_RE.fullmatch(value) else None
    if key in {"open_inside", "open_outside"}:
        return text if OPEN_RE.fullmatch(value) else None
    if key == "reboot_post_boot_id":
        return text if value == "missing" or BOOT_RE.fullmatch(value) else None
    return None


def kept_lines(text: str) -> list[str]:
    found: list[str] = []
    for line in text.splitlines():
        kept = keep_line(line)
        if kept is not None and kept not in found:
            found.append(kept)
    return found


def phase_accepted(phase: str, lines: Sequence[str], returncode: int) -> bool:
    if returncode == 255:
        return False
    if phase == "compare":
        return returncode == 0 and "compare=PASS" in lines
    if phase == "file-deny":
        return returncode == 0 and "file_deny=PASS" in lines
    if phase == "reboot-pre":
        return returncode == 0 and "reboot_pre=RECORDED" in lines
    if phase == "reboot-post":
        return (
            returncode == 0
            and "reboot_wiped=PASS" in lines
            and "reboot_restored=NOT_RUN" in lines
        )
    if phase == "expired-key":
        if returncode != 0:
            return False
        if any(line.startswith("expired_key=FAIL") for line in lines):
            return False
        return "license_exp_claim=NOT_PROVEN" in lines
    if phase == "uninstall":
        return any(
            line in lines
            for line in (
                "uninstall=VERIFIED",
                "uninstall=NOT_RUN_NO_APPROVAL",
                "uninstall=REFUSED_NOT_ENROLLED",
            )
        )
    return False


def loader_libs_ok(text: str) -> bool:
    if LOADER_LIB_BAD.search(text):
        return False
    if "not a dynamic executable" in text:
        return True
    rows = [line.strip() for line in text.splitlines() if line.strip()]
    if not rows:
        return False
    return all(LOADER_LIB_OK.search(line) for line in rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def check_loader_dir(directory: Path) -> str:
    loader = directory / "vantio-loader"
    script = directory / "enforcement_proof_lab.sh"
    loader_hash = directory / "loader.sha256"
    script_hash = directory / "script.sha256"
    libs = directory / "ldd.txt"
    if not loader.is_file() or not script.is_file() or not libs.is_file():
        raise SystemExit("loader_missing")
    if loader.read_bytes()[:4] != ELF_MAGIC:
        raise SystemExit("loader_elf")
    if not loader_libs_ok(libs.read_text(encoding="utf-8", errors="replace")):
        raise SystemExit("loader_libs")
    expect_loader = loader_hash.read_text(encoding="utf-8").strip()
    expect_script = script_hash.read_text(encoding="utf-8").strip()
    if expect_loader != _sha256(loader) or expect_script != _sha256(script):
        raise SystemExit("loader_sha")
    return expect_loader


def _mixed(env: Mapping[str, str]) -> None:
    for key in ("RUN_BATTERIES", "SELF_SERVICE", "T5_EGRESS", "REDTEAM_BRAIN"):
        if env.get(key, "").strip().lower() == "true":
            raise SystemExit("mixed_mode")
    if env.get("GOOGLE_APPLICATION_CREDENTIALS") or env.get("GCP_SA_KEY"):
        raise SystemExit("static_credentials")


def precheck(env: Mapping[str, str]) -> int:
    """Validate dispatch inputs. Prints lengths and the public git tip only."""
    try:
        _mixed(env)
        slice_name = env.get("PROOF_SLICE", "")
        if slice_name not in SLICES:
            raise SystemExit("slice")
        if not sha_ok(env.get("PE_GIT_SHA", "")):
            raise SystemExit("pe_git_sha")
        if not run_go_ok(env.get("PROOF_RUN_GO", "")):
            raise SystemExit("run_go")
        if not host_name_ok(env.get("PROOF_HOST_NAME", "")):
            raise SystemExit("host_name")
        if not approval_ok(env.get("PROOF_UNINSTALL_APPROVAL", "") or ""):
            raise SystemExit("uninstall_approval")
        proof_minutes(env.get("STOP_AFTER_MINUTES", ""))
        named = env.get("INSTANCE_NAME", "") or ""
        if slice_name == "reboot-post":
            if not instance_name_ok(named):
                raise SystemExit("name")
        elif named:
            raise SystemExit("name")
        if not phase_order_allowed(phases_for(slice_name)):
            raise SystemExit("phase_order")
    except SystemExit as exc:
        reason = exc.code if isinstance(exc.code, str) else "precheck"
        print(reason, file=sys.stderr)
        return 1
    go = env.get("PROOF_RUN_GO", "")
    host = env.get("PROOF_HOST_NAME", "")
    print(
        "\n".join(
            [
                "precheck=pass",
                f"slice={env.get('PROOF_SLICE', '')}",
                f"sha={PE_GIT_SHA}",
                f"run_go_len={len(go)}",
                f"host_len={len(host)}",
            ]
        )
    )
    return 0


def instance_create_argv(env: Mapping[str, str], script_path: str) -> list[str]:
    project = od.require_lab_project(env.get("GCP_LAB_PROJECT", ""))
    host = env.get("PROOF_HOST_NAME", "")
    if not host_name_ok(host):
        raise SystemExit("host_name")
    minutes = proof_minutes(env.get("STOP_AFTER_MINUTES", "120"))
    raw_now = env.get("GCP_LAB_NOW_EPOCH")
    now = int(raw_now) if raw_now else int(time.time())
    name = od.instance_name(env.get("GITHUB_RUN_ID", ""))
    labels = od.offline_labels(now, minutes)
    plan = {
        "boot_disk_gb": lab.BOOT_DISK_GB,
        "image_family": od.IMAGE_FAMILY,
        "image_project": od.IMAGE_PROJECT,
        "labels": labels,
        "machine_type": lab.MACHINE_TYPE,
        "name": name,
        "network": od.NETWORK,
        "project_id": project,
        "public_ip": False,
        "service_account": None,
        "subnet": od.SUBNET,
    }
    argv = od.offline_create_argv(plan, script_path)
    argv.append(f"--hostname={host}.vantio-lab-oct08.internal")
    if lab.names_partner(" ".join(argv), env=env):
        raise SystemExit("address")
    return argv


def allow_evidence(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("live_enforcement") != "NOT_PROVEN":
        raise SystemExit("claim")
    if payload.get("reboot_restored") not in (None, "NOT_RUN"):
        raise SystemExit("claim")
    allowed = {
        "image_family",
        "instance_name",
        "lab_dir",
        "live_enforcement",
        "loader_sha256",
        "machine_type",
        "observations",
        "pe_git_sha",
        "phases",
        "project_id",
        "public_ip",
        "reboot_restored",
        "result",
        "slice",
        "stopped",
        "zone",
    }
    kept = {key: payload[key] for key in allowed if key in payload}
    if kept.get("pe_git_sha") not in (None, PE_GIT_SHA):
        raise SystemExit("pe_git_sha")
    blob = json.dumps(kept)
    if PRIVATE_MARKER.search(blob):
        raise SystemExit("evidence")
    return kept


class GcloudTransport:
    """IAP and create calls. Tests pass a fake with the same methods."""

    def instances(self, project: str) -> list[dict[str, Any]]:
        return od._list_instances(project)

    def create(self, env: Mapping[str, str]) -> str:
        project = od.require_lab_project(env.get("GCP_LAB_PROJECT", ""))
        if lab.slot_occupied(self.instances(project)):
            raise SystemExit("slot_occupied")
        name = od.instance_name(env.get("GITHUB_RUN_ID", ""))
        script_dir = Path(env.get("RUNNER_TEMP") or "/tmp")
        script_path = script_dir / "gcp-enforcement-proof-startup.sh"
        script_path.write_text(od.offline_startup(proof_minutes(env.get("STOP_AFTER_MINUTES", "120"))), encoding="utf-8")
        od._run_ok(instance_create_argv(env, str(script_path)), "create")
        od._wait_until_running(project, name)
        return name

    def ssh(self, project: str, name: str, command: str) -> subprocess.CompletedProcess[str]:
        return od._ssh(project, name, command, timeout_s=od.CASE_SSH_TIMEOUT)

    def scp(self, project: str, name: str, paths: Sequence[Path]) -> None:
        od._scp_to(project, name, list(paths))

    def wait_ssh(self, project: str, name: str) -> str:
        return od._wait_ssh(project, name, od.SSH_WAIT_SECONDS)

    def wait_boot(self, project: str, name: str, before: str) -> str:
        return od._wait_boot(project, name, before, od.REBOOT_WAIT_SECONDS)

    def boot_id(self, project: str, name: str) -> str:
        completed = self.ssh(project, name, "cat /proc/sys/kernel/random/boot_id")
        boot = (completed.stdout or "").strip()
        if completed.returncode != 0 or not boot or "\n" in boot:
            raise SystemExit("ssh")
        return boot


def _owned(instances: Sequence[Mapping[str, Any]], name: str) -> bool:
    matched = next((item for item in instances if item.get("name") == name), None)
    if not isinstance(matched, Mapping):
        return False
    return lab.labels_owned(matched.get("labels"), name)


def _write_guest_files(env: Mapping[str, str], dest: Path, *, with_loader: bool) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    env_path = dest / "proof.env"
    env_path.write_text(env_file_text(env), encoding="utf-8")
    os.chmod(env_path, 0o600)
    wrapper = dest / "run-proof-phase.sh"
    wrapper.write_text(wrapper_script(), encoding="utf-8")
    os.chmod(wrapper, 0o755)
    paths = [env_path, wrapper]
    if not with_loader:
        return paths
    loader_dir = Path(env.get("LOADER_DIR", ""))
    check_loader_dir(loader_dir)
    paths.append(loader_dir / "vantio-loader")
    paths.append(loader_dir / "enforcement_proof_lab.sh")
    deb_dir = Path(env.get("DEB_DIR", ""))
    if not deb_dir.is_dir() or not any(deb_dir.glob("*.deb")):
        raise SystemExit("offline_debs_missing")
    packed = dest / "debs.tar"
    od.pack_debs(deb_dir, packed)
    paths.append(packed)
    return paths


def _pull_tree(
    transport: GcloudTransport,
    project: str,
    name: str,
    remote_dir: str,
    dest: Path,
    env: Mapping[str, str],
) -> list[str]:
    wrote: list[str] = []
    dest.mkdir(parents=True, exist_ok=True)
    for rel in LAB_FILES:
        completed = transport.ssh(project, name, f"sudo cat {shlex.quote(remote_dir + '/' + rel)}")
        target = dest / rel
        if completed.returncode != 0:
            continue
        text = redact(completed.stdout or "", env)
        if PRIVATE_MARKER.search(text):
            target.with_suffix(target.suffix + ".withheld").write_text("withheld=private_key_marker\n", encoding="utf-8")
            wrote.append(rel + ".withheld")
            continue
        if len(text) > 2_000_000:
            text = text[:2_000_000]
        target.write_text(text, encoding="utf-8")
        wrote.append(rel)
    return wrote


def _evidence_dir(env: Mapping[str, str]) -> Path:
    path = Path(env.get("EVIDENCE_DIR") or (env.get("RUNNER_TEMP") or "/tmp") + "/gcp-lab-evidence")
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_proof(env: Mapping[str, str], transport: GcloudTransport | None = None) -> int:
    if env.get("GCP_LAB_EXECUTE") != "1":
        print("refusing to call gcloud", file=sys.stderr)
        return 2
    if precheck(env) != 0:
        return 1
    od._gate_ok(env)
    project = od.require_lab_project(env.get("GCP_LAB_PROJECT", ""))
    slice_name = env["PROOF_SLICE"]
    phases = phases_for(slice_name)
    transport = transport or GcloudTransport()
    evidence = _evidence_dir(env)
    stage_dir = Path(env.get("RUNNER_TEMP") or "/tmp") / "enforcement-proof-stage"
    observations: list[str] = []
    stopped = ""
    name = ""
    loader_sha = ""
    try:
        if slice_name == "reboot-post":
            name = env.get("INSTANCE_NAME", "")
            if not _owned(transport.instances(project), name):
                raise SystemExit("skip_not_owned")
            transport.wait_ssh(project, name)
            transport.scp(project, name, _write_guest_files(env, stage_dir, with_loader=False))
            prepared = transport.ssh(project, name, REFRESH_COMMAND)
            if prepared.returncode != 0:
                raise SystemExit("ssh")
        else:
            loader_sha = check_loader_dir(Path(env.get("LOADER_DIR", "")))
            if lab.slot_occupied(transport.instances(project)):
                raise SystemExit("slot_occupied")
            name = transport.create(env)
            transport.wait_ssh(project, name)
            transport.scp(project, name, _write_guest_files(env, stage_dir, with_loader=True))
            prepared = transport.ssh(project, name, PREPARE_COMMAND)
            if prepared.returncode != 0:
                raise SystemExit("guest_prepare")
        compares = 0
        for index, phase in enumerate(phases, start=1):
            if phase == "reboot":
                before = transport.boot_id(project, name)
                completed = transport.ssh(project, name, REBOOT_COMMAND)
                text = redact((completed.stdout or "") + (completed.stderr or ""), env)
                (evidence / f"{index:02d}-reboot.log").write_text(text, encoding="utf-8")
                after = transport.wait_boot(project, name, before)
                if completed.returncode not in (0, 255) or not od.reboot_ready(before, after):
                    stopped = "reboot"
                    break
                continue
            if phase == "compare":
                compares += 1
                if compares == 2:
                    archived = transport.ssh(project, name, ARCHIVE_COMMAND)
                    if archived.returncode != 0:
                        stopped = "archive"
                        break
                    _pull_tree(transport, project, name, LAB_DIR, evidence / "pre-reboot", env)
            command = ssh_phase_command(phase)
            completed = transport.ssh(project, name, command)
            text = redact((completed.stdout or "") + (completed.stderr or ""), env)
            (evidence / f"{index:02d}-{phase}.log").write_text(text, encoding="utf-8")
            lines = kept_lines(text)
            observations.extend(line for line in lines if line not in observations)
            _pull_tree(transport, project, name, LAB_DIR, evidence / "lab", env)
            if not phase_accepted(phase, lines, completed.returncode):
                stopped = phase
                break
    except SystemExit as exc:
        stopped = stopped or (exc.code if isinstance(exc.code, str) else "failed")
    payload = allow_evidence(
        {
            "image_family": od.IMAGE_FAMILY,
            "instance_name": name,
            "lab_dir": LAB_DIR,
            "live_enforcement": "NOT_PROVEN",
            "loader_sha256": loader_sha,
            "machine_type": lab.MACHINE_TYPE,
            "observations": observations,
            "pe_git_sha": PE_GIT_SHA,
            "phases": list(phases),
            "project_id": project,
            "public_ip": False,
            "reboot_restored": "NOT_RUN",
            "result": "OBSERVED" if not stopped else "STOPPED",
            "slice": slice_name,
            "stopped": stopped,
            "zone": lab.ZONE,
        }
    )
    if not payload.get("loader_sha256"):
        payload.pop("loader_sha256", None)
    (evidence / "enforcement-proof.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload))
    if name:
        od.github_output("instance_name", name)
    if stopped:
        print(stopped, file=sys.stderr)
        return 2
    return 0


def teardown_target(env: Mapping[str, str]) -> str:
    if env.get("PROOF_SLICE") == "reboot-post":
        name = env.get("INSTANCE_NAME", "")
    else:
        name = env.get("INSTANCE_NAME", "") or od.instance_name(env.get("GITHUB_RUN_ID", ""))
    if not instance_name_ok(name):
        raise SystemExit("name")
    return name


def teardown_named(env: Mapping[str, str]) -> int:
    """Delete one owned lab VM. Used when the proof job failed after create."""
    if env.get("GCP_LAB_EXECUTE") != "1":
        print("refusing to call gcloud", file=sys.stderr)
        return 2
    project = od.require_lab_project(env.get("GCP_LAB_PROJECT", ""))
    name = teardown_target(env)
    child = dict(env)
    child["INSTANCE_NAME"] = name
    child["GCP_LAB_PROJECT"] = project
    child["GCP_LAB_EXECUTE"] = "1"
    lab.execute_teardown(child)
    status = "UNKNOWN"
    verify_rc = 2
    for _ in range(12):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            verify_rc = lab.execute_verify(child)
        try:
            parsed = json.loads(buffer.getvalue() or "{}")
        except json.JSONDecodeError:
            parsed = {}
        if isinstance(parsed, dict) and isinstance(parsed.get("status"), str):
            status = parsed["status"]
        if verify_rc == 0 and status == "VERIFIED_REMOVED":
            break
        time.sleep(10)
    payload = allow_evidence(
        {
            "instance_name": name,
            "live_enforcement": "NOT_PROVEN",
            "pe_git_sha": PE_GIT_SHA,
            "project_id": project,
            "public_ip": False,
            "reboot_restored": "NOT_RUN",
            "result": "OBSERVED" if status == "VERIFIED_REMOVED" and deleted == 0 else "STOPPED",
            "slice": env.get("PROOF_SLICE", ""),
            "stopped": "" if status == "VERIFIED_REMOVED" and deleted == 0 else "teardown",
            "zone": lab.ZONE,
        }
    )
    payload["verify_status"] = status
    print(json.dumps({"instance_name": name, "verify_status": status, "live_enforcement": "NOT_PROVEN"}))
    _evidence_dir(env).joinpath("enforcement-proof-teardown.json").write_text(
        json.dumps({"instance_name": name, "verify_status": status, "live_enforcement": "NOT_PROVEN"}) + "\n",
        encoding="utf-8",
    )
    if status == "VERIFIED_REMOVED" and verify_rc == 0:
        return 0
    return 2


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    command = args[0] if args else ""
    try:
        if command == "precheck":
            return precheck(os.environ)
        if command == "plan":
            slice_name = os.environ.get("PROOF_SLICE", "full")
            print(json.dumps(public_plan(slice_name)))
            return 0
        if command == "run":
            return run_proof(os.environ)
        if command == "teardown":
            return teardown_named(os.environ)
    except SystemExit as exc:
        reason = exc.code
        if reason not in (0, None):
            print(reason if isinstance(reason, str) else "failed", file=sys.stderr)
            return 2
        return 0
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
