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
import proof_grade as pg

PE_REPO = "vantioai/vantio-phantom-engine"
PE_GIT_SHA = "864289cb2c9c4135d74233c74c6655087de3f20d"
WORKFLOW_FILE = "gcp-lab-enforcement-proof.yml"
WORKFLOW_REF = f"vantioai/vantio-open-core/.github/workflows/{WORKFLOW_FILE}@refs/heads/main"
# Live WIF attribute condition. lab_auto.WORKFLOWS also names the proof file.
# Guest auth jobs stay in a file from this tuple.
LIVE_WIF_FILES = (
    "gcp-lab-cost-gate.yml",
    "gcp-lab-provision.yml",
    "gcp-lab-collect.yml",
    "gcp-lab-teardown.yml",
    "gcp-lab-sweeper.yml",
    "gcp-lab-verify-removed.yml",
)
WIF_AUTH_USE = "google-github-actions/auth@"
CALLED_WIF_FILE = "gcp-lab-cost-gate.yml"
LAB_DIR = "/var/lib/vantio-enforcement-proof"
PRE_REBOOT_DIR = "/var/lib/vantio-enforcement-proof-pre-reboot"
GUEST_DIR = od.GUEST_DIR
GUEST_LOADER = f"{GUEST_DIR}/vantio-loader"
GUEST_SCRIPT = f"{GUEST_DIR}/enforcement_proof_lab.sh"
GUEST_ENV = f"{GUEST_DIR}/proof.env"
GUEST_WRAPPER = f"{GUEST_DIR}/run-proof-phase.sh"
SLICES = ("full", "reboot-pre", "reboot-post")
SAME_BOOT = frozenset(
    {"root-detach", "file-deny", "reboot-pre", "expired-key", "uninstall", "uninstall-negative"}
)
# fork-inherit stays a fail-closed stub. root-detach is a real check.
STUB_PHASES = frozenset({"fork-inherit"})
SCRIPT_PHASES = frozenset({"compare", "reboot-post", *SAME_BOOT, *STUB_PHASES})
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
        {
            "PASS",
            "REFUSED_LSM",
            "INCONCLUSIVE",
            "FAIL_OPEN",
            "FAIL_UNATTRIBUTED",
            "FAIL_UNSCOPED",
            "FAIL_UNEXPECTED_ERRNO",
            "NOT_ENFORCING",
        }
    ),
    "file_deny": frozenset(
        {"PASS", "REFUSED_LSM", "NOT_ENFORCING", "FAIL_OPEN", "FAIL_UNATTRIBUTED", "INCONCLUSIVE"}
    ),
    "license_exp_claim": frozenset({"NOT_PROVEN", "REFUSED"}),
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
    "fork_inherit": frozenset({"PASS", "INCONCLUSIVE", "FAIL_OPEN", "FAIL_UNATTRIBUTED", "FAIL_UNSCOPED"}),
    "fork_inherit_reason": frozenset({"not_collected"}),
    "root_detach": frozenset({"PASS", "FAIL"}),
    "root_detach_lsm": frozenset({"present", "absent"}),
    "root_detach_actor": frozenset({"outside_loader", "loader"}),
    "root_detach_programs_remain": frozenset({"yes", "no"}),
    "root_detach_pins_remain": frozenset({"yes", "no"}),
    "harness_accept": frozenset({"yes", "no"}),
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


def wif_auth_violations(files: Mapping[str, str], allowlist: Sequence[str] = LIVE_WIF_FILES) -> list[str]:
    """Files that call google auth outside the live WIF workflow allowlist."""
    return sorted(name for name, text in files.items() if isinstance(text, str) and WIF_AUTH_USE in text and name not in allowlist)


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
            "root-detach",
            "file-deny",
            "reboot-pre",
            "reboot",
            "reboot-post",
            "compare",
            "expired-key",
            "uninstall",
        )
    if slice_name == "reboot-pre":
        return ("compare", "root-detach", "file-deny", "reboot-pre", "reboot")
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
        "root_detach_on_pe_tip": "FAIL",
        "stub_phases": sorted(STUB_PHASES),
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
            'case "$phase" in',
            "  fork-inherit)",
            "    printf '%s\\n' fork_inherit=INCONCLUSIVE fork_inherit_reason=not_collected live_enforcement=NOT_PROVEN",
            "    exit 1",
            "    ;;",
            "esac",
            f'grade="{GUEST_DIR}/proof_grade.py"',
            'if [[ -f "$grade" ]]; then',
            "  set +e",
            f'  {GUEST_SCRIPT} --i-understand-this-attaches-ebpf "$phase"',
            "  rc=$?",
            "  set -e",
            f'  exec python3 "$grade" gate "$phase" "{LAB_DIR}/transcript.txt" "$rc"',
            "fi",
            f'exec {GUEST_SCRIPT} --i-understand-this-attaches-ebpf "$phase"',
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
    if key in {
        "audit_outside",
        "audit_inside",
        "enforce_inside",
        "enforce_outside",
        "fork_parent",
        "fork_child",
        "fork_grandchild",
        "fork_stranger",
        "root_detach_inside",
    }:
        return text if pg.CONNECT_RE.fullmatch(value) else None
    if key == "root_detach_uid":
        return text if value.isdigit() else None
    if key == "root_detach_attempt":
        return text if pg.ROOT_ATTEMPT_RE.fullmatch(text) else None
    if key == "root_detach_ledger":
        return text if pg.ROOT_LEDGER_RE.fullmatch(text) else None
    if key in {"open_inside", "open_outside"}:
        return text if pg.OPEN_RE.fullmatch(value) else None
    if key in {"reboot_post_boot_id", "reboot_pre_boot_id"}:
        return text if value == "missing" or pg.BOOT_RE.fullmatch(value) else None
    if key == "drop_counter":
        return text if pg.DROP_COUNTER_RE.fullmatch(text) else None
    if key == "ledger_drop":
        return text if pg.LEDGER_DROP_RE.fullmatch(text) else None
    if key == "fork_trace":
        return text if pg.FORK_TRACE_RE.fullmatch(value) else None
    if key == "fork_anchor":
        return text if pg.FORK_ANCHOR_RE.fullmatch(value) else None
    return None


def kept_lines(text: str) -> list[str]:
    found: list[str] = []
    for line in text.splitlines():
        kept = keep_line(line)
        if kept is not None and kept not in found:
            found.append(kept)
    return found


def phase_accepted(
    phase: str,
    lines: Sequence[str],
    returncode: int,
    observed_boots: Mapping[str, str] | None = None,
) -> bool:
    """Accept a phase only when proof_grade says the evidence holds.

    compare=PASS, file_deny=PASS, and reboot_wiped=PASS are not sufficient
    on their own. root-detach passes only when every detach attempt is refused.
    """
    return pg.phase_decision(phase, lines, returncode, observed_boots)


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


_OLD_COMPARE = """  note "enforce_inside=$(connect_once inside "$CGROUP")"
  note "enforce_outside=$(connect_once outside "")"
  note "ledger_$(ledger_has_block "$OUT/enforce.ndjson")"
  stop_loader_int
  local verdict
  verdict="$(python3 - "$OUT/transcript.txt" <<'PY'
import sys
text = open(sys.argv[1], encoding="utf-8", errors="replace").read().splitlines()
def field(prefix):
    for line in reversed(text):
        if line.startswith(prefix):
            return line.split("=", 1)[1]
    return ""
audit_out = field("audit_outside=connect where=outside ")
audit_in = field("audit_inside=connect where=inside ")
enf_in = field("enforce_inside=connect where=inside ")
enf_out = field("enforce_outside=connect where=outside ")
block = any(line.startswith("ledger_network_block=yes") for line in text)
def connected(item):
    return "result=connected" in item
def blocked(item):
    return "result=timeout" in item or "result=error" in item
if not (connected(audit_out) and connected(audit_in)):
    print("INCONCLUSIVE")
elif connected(enf_in):
    print("FAIL_OPEN")
elif not blocked(enf_in):
    print("INCONCLUSIVE")
elif not block:
    print("FAIL_UNATTRIBUTED")
elif not connected(enf_out):
    print("FAIL_UNSCOPED")
else:
    print("PASS")
PY
)"
"""

_NEW_COMPARE = """  local grade_py inside_line inside_packets inside_source
  local outside_line outside_packets outside_source
  grade_py="$(cd "$(dirname "$0")" && pwd)/proof_grade.py"
  if [[ ! -f "$grade_py" ]]; then
    note "compare_reason=grade_missing"
    record_compare "INCONCLUSIVE"
    finish_not_proven
    exit 1
  fi
  IFS=$'\\t' read -r inside_line inside_packets inside_source < <(measure_connect inside "$CGROUP")
  note "enforce_inside=${inside_line}"
  IFS=$'\\t' read -r outside_line outside_packets outside_source < <(measure_connect outside "")
  note "enforce_outside=${outside_line}"
  if [[ "$inside_source" == "$outside_source" && "$inside_source" != "missing" && "$inside_packets" != "missing" && "$outside_packets" != "missing" ]]; then
    note "drop_counter=source=${inside_source} inside=${inside_packets} outside=${outside_packets}"
  else
    note "drop_counter=source=missing inside=0 outside=0"
  fi
  note "$(python3 "$grade_py" ledger-line "$OUT/enforce.ndjson")"
  stop_loader_int
  local verdict
  verdict="$(python3 "$grade_py" compare-verdict "$OUT/transcript.txt")"
"""

_MEASURE_FN = r"""measure_connect() {
  local where="$1"
  local join="${2:-}"
  local line packets source iface pcap tpid before after
  iface="vproof-b"
  if ! ip link show "$iface" >/dev/null 2>&1; then
    iface="${IFACE:-}"
  fi
  if command -v tcpdump >/dev/null 2>&1 && [[ -n "$iface" ]] && ip link show "$iface" >/dev/null 2>&1; then
    pcap="$(mktemp)"
    tcpdump -n -i "$iface" -c 64 -w "$pcap" "host ${TARGET_IP} and port ${TARGET_PORT}" >/dev/null 2>&1 &
    tpid=$!
    sleep 0.2
    line="$(connect_once "$where" "$join")"
    sleep 0.4
    kill "$tpid" 2>/dev/null || true
    wait "$tpid" 2>/dev/null || true
    packets="$(tcpdump -n -r "$pcap" 2>/dev/null | wc -l | tr -d ' ')"
    rm -f "$pcap" || true
    packets="${packets:-0}"
    printf '%s\t%s\ttcpdump\n' "$line" "$packets"
    return 0
  fi
  if command -v nft >/dev/null 2>&1; then
    if ! nft list chain inet vantio_proof out >/dev/null 2>&1; then
      nft add table inet vantio_proof >/dev/null 2>&1 || true
      nft 'add chain inet vantio_proof out { type filter hook output priority 0 ; }' >/dev/null 2>&1 || true
      nft add rule inet vantio_proof out ip daddr "${TARGET_IP}" tcp dport "${TARGET_PORT}" counter >/dev/null 2>&1 || true
    fi
    before="$(nft list chain inet vantio_proof out 2>/dev/null | awk '/packets/ { for (i = 1; i <= NF; i++) if ($i == "packets") { print $(i + 1); exit } }')"
    before="${before:-0}"
    line="$(connect_once "$where" "$join")"
    after="$(nft list chain inet vantio_proof out 2>/dev/null | awk '/packets/ { for (i = 1; i <= NF; i++) if ($i == "packets") { print $(i + 1); exit } }')"
    after="${after:-0}"
    case "${before}${after}" in
      *[!0-9]*) printf '%s\tmissing\tmissing\n' "$line"; return 0 ;;
    esac
    packets="$((after - before))"
    printf '%s\t%s\tnft\n' "$line" "$packets"
    return 0
  fi
  if command -v iptables >/dev/null 2>&1; then
    iptables -C OUTPUT -d "${TARGET_IP}/32" -p tcp --dport "${TARGET_PORT}" -j ACCEPT >/dev/null 2>&1 \
      || iptables -I OUTPUT -d "${TARGET_IP}/32" -p tcp --dport "${TARGET_PORT}" -j ACCEPT >/dev/null 2>&1 \
      || true
    before="$(iptables -L OUTPUT -v -n -x | awk -v ip="${TARGET_IP}" -v port="${TARGET_PORT}" '$0 ~ ip && $0 ~ port { print $1; exit }')"
    before="${before:-0}"
    line="$(connect_once "$where" "$join")"
    after="$(iptables -L OUTPUT -v -n -x | awk -v ip="${TARGET_IP}" -v port="${TARGET_PORT}" '$0 ~ ip && $0 ~ port { print $1; exit }')"
    after="${after:-0}"
    case "${before}${after}" in
      *[!0-9]*) printf '%s\tmissing\tmissing\n' "$line"; return 0 ;;
    esac
    packets="$((after - before))"
    printf '%s\t%s\tiptables\n' "$line" "$packets"
    return 0
  fi
  line="$(connect_once "$where" "$join")"
  printf '%s\tmissing\tmissing\n' "$line"
}

"""

_OLD_EXPIRED = """  if grep -E "LICENSE_INVALID|license_exp" "$OUT/expired.log" >/dev/null 2>&1; then
    note "license_exp_observation=REFUSED"
  else
    note "license_exp_observation=NOT_CONSULTED"
  fi
  note "license_exp_claim=NOT_PROVEN"
  finish_not_proven
}
"""

_NEW_EXPIRED = """  if grep -E "LICENSE_INVALID|license_exp" "$OUT/expired.log" >/dev/null 2>&1; then
    note "license_exp_observation=REFUSED"
    note "license_exp_claim=REFUSED"
    finish_not_proven
  else
    note "license_exp_observation=NOT_CONSULTED"
    note "license_exp_claim=NOT_PROVEN"
    finish_not_proven
    exit 1
  fi
}
"""

_OLD_REBOOT = """  note "reboot_post_boot_id=$new"
  if [[ -z "$old" || "$old" == "$new" ]]; then
    note "reboot_wiped=INCONCLUSIVE"
    finish_not_proven
    exit 0
  fi
"""

_NEW_REBOOT = """  note "reboot_pre_boot_id=${old:-missing}"
  note "reboot_post_boot_id=${new:-missing}"
  if [[ -z "$old" || -z "$new" || "$old" == "missing" || "$new" == "missing" || "$old" == "$new" ]]; then
    note "reboot_wiped=INCONCLUSIVE"
    finish_not_proven
    exit 1
  fi
"""


_ROOT_FN = r"""phase_root_detach() {
  require_compare_pass
  require_root
  note "root_detach_uid=$(id -u)"
  if ! record_host; then
    note "root_detach_lsm=absent"
    note "root_detach=FAIL"
    finish_not_proven
    exit 1
  fi
  note "root_detach_lsm=present"
  if ! prepare_net; then
    note "root_detach=FAIL"
    finish_not_proven
    exit 1
  fi
  mkdir -p "$CGROUP"
  start_listener
  start_loader "$OUT/root-detach.log" "$LOADER" --enforce --iface "$IFACE" \
    --startup-enroll-cgroup "$CGROUP" --output-file "$OUT/root-detach.ndjson"
  local banner
  banner="$(wait_banner "$OUT/root-detach.log")"
  note "root_detach_banner=$banner"
  local attempt_py grade_py
  attempt_py="$(cd "$(dirname "$0")" && pwd)/root_detach_attempt.py"
  grade_py="$(cd "$(dirname "$0")" && pwd)/proof_grade.py"
  if [[ ! -f "$attempt_py" || ! -f "$grade_py" ]]; then
    note "root_detach_actor=loader"
    note "root_detach_attempt=prog_detach target=missing result=skipped errno=0"
    note "root_detach_attempt=link_detach target=missing result=skipped errno=0"
    note "root_detach_attempt=unlink target=missing result=skipped errno=0"
    note "root_detach_programs_remain=no"
    note "root_detach_pins_remain=no"
    note "root_detach=FAIL"
    finish_not_proven
    exit 1
  fi
  while IFS= read -r line; do
    note "$line"
  done < <(python3 "$attempt_py" "$CGROUP" /sys/fs/bpf "${LOADER_PID:-0}")
  note "root_detach_inside=$(connect_once inside "$CGROUP")"
  local ledger
  ledger="$(python3 "$grade_py" ledger-line "$OUT/root-detach.ndjson")"
  note "root_detach_ledger=${ledger#ledger_drop=}"
  local verdict
  verdict="$(python3 "$grade_py" root-detach-verdict "$OUT/transcript.txt")"
  note "root_detach=$verdict"
  stop_loader_int
  finish_not_proven
  if [[ "$verdict" != "PASS" ]]; then
    exit 1
  fi
}

"""


def _stage_py(dest: Path, name: str) -> Path:
    src = Path(__file__).resolve().with_name(name)
    target = dest / name
    target.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    os.chmod(target, 0o644)
    return target


def harden_lab_script(text: str) -> str:
    """Patch the copied lab script so a false PASS is not what the guest records.

    A stub without phase_compare is returned unchanged. A lab script that has
    drifted off the pinned markers fails closed instead of being copied as-is.
    """
    if "phase_compare()" not in text:
        return text
    missing = [
        name
        for name, needle in (
            ("compare", _OLD_COMPARE),
            ("expired", _OLD_EXPIRED),
            ("reboot", _OLD_REBOOT),
            ("case", 'case "$PHASE" in\n'),
        )
        if needle not in text
    ]
    if missing:
        raise SystemExit("lab_script_marker")
    patched = text.replace(_OLD_COMPARE, _NEW_COMPARE, 1)
    patched = patched.replace("phase_compare() {", _MEASURE_FN + "phase_compare() {", 1)
    patched = patched.replace(_OLD_EXPIRED, _NEW_EXPIRED, 1)
    patched = patched.replace(_OLD_REBOOT, _NEW_REBOOT, 1)
    patched = patched.replace('case "$PHASE" in\n', _ROOT_FN + 'case "$PHASE" in\n', 1)
    patched = patched.replace(
        "  compare) phase_compare ;;\n",
        "  compare) phase_compare ;;\n  root-detach) phase_root_detach ;;\n",
        1,
    )
    if 'result=timeout" in item or "result=error" in item' in patched:
        raise SystemExit("lab_script_marker")
    return patched


def _write_guest_files(env: Mapping[str, str], dest: Path, *, with_loader: bool) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    env_path = dest / "proof.env"
    env_path.write_text(env_file_text(env), encoding="utf-8")
    os.chmod(env_path, 0o600)
    wrapper = dest / "run-proof-phase.sh"
    wrapper.write_text(wrapper_script(), encoding="utf-8")
    os.chmod(wrapper, 0o755)
    paths = [env_path, wrapper, _stage_py(dest, "proof_grade.py"), _stage_py(dest, "root_detach_attempt.py")]
    if not with_loader:
        return paths
    loader_dir = Path(env.get("LOADER_DIR", ""))
    check_loader_dir(loader_dir)
    paths.append(loader_dir / "vantio-loader")
    original = (loader_dir / "enforcement_proof_lab.sh").read_text(encoding="utf-8")
    hardened = dest / "enforcement_proof_lab.sh"
    hardened.write_text(harden_lab_script(original), encoding="utf-8")
    os.chmod(hardened, 0o755)
    paths.append(hardened)
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
        observed_boots: dict[str, str] = {}
        for index, phase in enumerate(phases, start=1):
            if phase == "reboot":
                before = transport.boot_id(project, name)
                completed = transport.ssh(project, name, REBOOT_COMMAND)
                text = redact((completed.stdout or "") + (completed.stderr or ""), env)
                (evidence / f"{index:02d}-reboot.log").write_text(text, encoding="utf-8")
                after = transport.wait_boot(project, name, before)
                observed_boots = {"before": before, "after": after}
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
            boots = observed_boots if phase == "reboot-post" else None
            if not phase_accepted(phase, lines, completed.returncode, boots):
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
    deleted = lab.execute_teardown(child)
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
    removed = deleted == 0 and verify_rc == 0 and status == "VERIFIED_REMOVED"
    payload = allow_evidence(
        {
            "instance_name": name,
            "live_enforcement": "NOT_PROVEN",
            "pe_git_sha": PE_GIT_SHA,
            "project_id": project,
            "public_ip": False,
            "reboot_restored": "NOT_RUN",
            "result": "OBSERVED" if removed else "STOPPED",
            "slice": env.get("PROOF_SLICE", ""),
            "stopped": "" if removed else "teardown",
            "zone": lab.ZONE,
        }
    )
    payload["verify_status"] = status
    payload["deleted"] = deleted
    print(json.dumps({"instance_name": name, "verify_status": status, "deleted": deleted, "live_enforcement": "NOT_PROVEN"}))
    _evidence_dir(env).joinpath("enforcement-proof-teardown.json").write_text(
        json.dumps(
            {
                "instance_name": name,
                "verify_status": status,
                "deleted": deleted,
                "live_enforcement": "NOT_PROVEN",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    if removed:
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
