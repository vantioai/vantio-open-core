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


def _read_pe_pin() -> str:
    """The Phantom Engine tip. scripts/gcp/pe-pin.txt is the only copy."""
    raw = Path(__file__).with_name("pe-pin.txt").read_text(encoding="utf-8").strip()
    if len(raw) != 40 or any(ch not in "0123456789abcdef" for ch in raw):
        raise RuntimeError("pe_git_sha")
    return raw


PE_GIT_SHA = _read_pe_pin()
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
    {
        "root-detach",
        "signals",
        "file-deny",
        "fork-inherit",
        "unix-socket",
        "ptrace-deny",
        "inbound",
        "bpffs-overmount",
        "af-packet",
        "stop-token",
        "pin-absent",
        "missing-path",
        "host-wide",
        "hard-link",
        "enrolled-root",
        "nonce-truncate",
        "ledger-forgery",
        "ptrace-task",
        "host-enroll",
        "same-boundary",
        "oom",
        "escapes",
        "clock",
        "k8s",
        "vlan",
        "reboot-pre",
        "expired-key",
        "uninstall",
        "uninstall-negative",
    }
)
STUB_PHASES = frozenset()
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
    "reboot_restored": frozenset({"NOT_RUN", "PASS", "FAIL", "REFUSED_LSM"}),
    "reboot_marker_open": frozenset({"absent"}),
    "live_enforcement": frozenset({"NOT_PROVEN"}),
    "fork_inherit": frozenset({"PASS", "INCONCLUSIVE", "FAIL_OPEN", "FAIL_UNATTRIBUTED", "FAIL_UNSCOPED"}),
    "fork_inherit_reason": frozenset({"not_collected"}),
    "root_detach": frozenset({"PASS", "FAIL"}),
    "root_detach_lsm": frozenset({"present", "absent"}),
    "root_detach_actor": frozenset({"outside_loader", "loader"}),
    "root_detach_programs_remain": frozenset({"yes", "no"}),
    "root_detach_pins_remain": frozenset({"yes", "no"}),
    "signal_process": frozenset({"up", "down"}),
    "boundary_unlisted": frozenset({"blocked", "connected", "restored"}),
    "boundary_exception": frozenset({"blocked", "connected", "restored"}),
    "boundary_expired": frozenset({"blocked", "connected", "restored"}),
    "boundary_unsigned": frozenset({"blocked", "connected", "restored"}),
    "boundary_stop": frozenset({"blocked", "connected", "restored"}),
    "oom_killed": frozenset({"yes", "no"}),
    "oom_programs": frozenset({"remain", "gone"}),
    "clock_moved": frozenset({"yes", "no"}),
    "clock_exp_passed": frozenset({"yes", "no"}),
    "clock_enforcement": frozenset({"fail_closed", "open"}),
    "teardown": frozenset({"RESTORED", "FAIL_STILL_UP", "FAIL_PINS", "FAIL_CONNECT", "FAIL_NO_TOKEN"}),
    "teardown_pins": frozenset({"absent", "remain"}),
    "harness_accept": frozenset({"yes", "no"}),
    "ledger_chain": frozenset({"ok", "fail"}),
    "unix_enrolled": frozenset({"denied", "connected"}),
    "unix_outside": frozenset({"denied", "connected"}),
    "unix_socket": frozenset({"PASS", "FAIL", "NOT_RUN"}),
    "ptrace_deny": frozenset({"PASS", "FAIL", "NOT_RUN"}),
    "ptrace_errno": frozenset({"0", "1"}),
    "process_vm_errno": frozenset({"0", "1", "13", "22"}),
    "proc_mem_errno": frozenset({"0", "1", "13"}),
    "pidfd_getfd_errno": frozenset({"0", "1"}),
    "inbound": frozenset({"PASS", "FAIL", "NOT_RUN"}),
    "inbound_enrolled": frozenset({"blocked", "connected"}),
    "inbound_outside": frozenset({"blocked", "connected"}),
    "bpffs_overmount": frozenset({"refused", "mounted", "NOT_RUN", "PASS", "FAIL"}),
    "bpffs_errno": frozenset({"0", "1"}),
    "bpffs_pins": frozenset({"remain", "hidden"}),
    "af_packet": frozenset({"PASS", "FAIL", "NOT_RUN"}),
    "af_packet_enrolled": frozenset({"denied", "ok"}),
    "af_packet_outside": frozenset({"denied", "ok"}),
    "stop_token": frozenset({"PASS", "FAIL", "NOT_RUN"}),
    "stop_expired": frozenset({"refused", "accepted"}),
    "stop_bare": frozenset({"refused", "accepted"}),
    "stop_replay": frozenset({"refused", "accepted"}),
    "stop_fresh": frozenset({"refused", "accepted"}),
    "pin_absent": frozenset({"REFUSED", "ENFORCING", "NOT_RUN", "PASS", "FAIL"}),
    "pin_present": frozenset({"REFUSED", "ENFORCING"}),
    "missing_path": frozenset({"PASS", "FAIL", "NOT_RUN"}),
    "missing_create": frozenset({"denied", "created"}),
    "missing_created": frozenset({"yes", "no"}),
    "hostwide_out": frozenset({"blocked", "allowed", "other"}),
    "hostwide_except": frozenset({"blocked", "allowed", "other"}),
    "hostwide_agent": frozenset({"blocked", "allowed", "other"}),
    "hardlink_before": frozenset({"denied", "allowed", "other"}),
    "hardlink_original": frozenset({"denied", "allowed", "other"}),
    "hardlink_root_link": frozenset({"created", "denied"}),
    "hardlink_after": frozenset({"denied", "allowed", "other"}),
    "hardlink_enrolled_link": frozenset({"denied", "created", "other"}),
    "root_enrolled_open": frozenset({"denied", "allowed", "other"}),
    "root_outside_open": frozenset({"denied", "allowed", "other"}),
    "nonce_first": frozenset({"accepted", "refused"}),
    "nonce_replay": frozenset({"replay", "other"}),
    "nonce_file": frozenset({"empty", "present"}),
    "ledger_genuine": frozenset({"ok", "bad"}),
    "ledger_key_changed": frozenset({"rejected", "accepted"}),
    "ledger_zero_prev": frozenset({"rejected", "accepted"}),
    "ledger_truncated": frozenset({"rejected", "accepted"}),
    "ledger_attacker": frozenset({"rejected", "accepted"}),
    "ptrace_unenrolled": frozenset({"0", "1", "13"}),
    "ptrace_enrolled_target": frozenset({"0", "1", "13"}),
    "ptrace_enrolled_caller": frozenset({"0", "1", "13"}),
    "k8s": frozenset({"PASS", "FAIL", "NOT_RUN"}),
    "k8s_enrolled": frozenset({"blocked", "connected"}),
    "k8s_outsider": frozenset({"blocked", "connected"}),
    "vlan": frozenset({"PASS", "FAIL", "NOT_RUN"}),
    "vlan_attached": frozenset({"yes", "no"}),
    "vlan_enrolled": frozenset({"denied", "allowed"}),
    "vlan_outside": frozenset({"denied", "allowed"}),
    "host_enroll": frozenset({"PASS", "FAIL", "NOT_RUN"}),
    "clock": frozenset({"PASS", "FAIL", "NOT_RUN"}),
    "reboot_post": frozenset({"PASS", "FAIL", "NOT_RUN"}),
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
            "signals",
            "file-deny",
            "fork-inherit",
            "unix-socket",
            "ptrace-deny",
            "inbound",
            "bpffs-overmount",
            "af-packet",
            "stop-token",
            "pin-absent",
            "missing-path",
            "host-wide",
            "hard-link",
            "enrolled-root",
            "nonce-truncate",
            "ledger-forgery",
            "ptrace-task",
            "host-enroll",
            "same-boundary",
            "oom",
            "escapes",
            "clock",
            "k8s",
            "vlan",
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
        "root_detach_on_pe_tip": "PASS_IF_ERRNO_1",
        "stub_phases": sorted(STUB_PHASES),
        "public_ip": False,
        "reboot_command": "mask-google-shutdown-scripts-then-systemctl-reboot-force",
        "reboot_restored": "REQUIRED",
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
            f'mkdir -p "{LAB_DIR}/lab-stop"',
            f'python3 "{GUEST_DIR}/lab_stop.py" init "{LAB_DIR}/lab-stop"',
            f'if [[ -x "{GUEST_LOADER}" ]]; then python3 "{GUEST_DIR}/lab_stop.py" pin "{LAB_DIR}/lab-stop" "{GUEST_LOADER}"; fi',
            "set -a",
            f'. "{LAB_DIR}/lab-stop/env"',
            "set +a",
            f'grade="{GUEST_DIR}/proof_grade.py"',
            'if [[ -f "$grade" ]]; then',
            "  set +e",
            '  case "$phase" in',
            "    unix-socket|ptrace-deny|inbound|bpffs-overmount|af-packet|stop-token|pin-absent|missing-path|host-wide|hard-link|enrolled-root|nonce-truncate|ledger-forgery|ptrace-task|k8s|vlan|host-enroll)",
            f'      bash "{GUEST_DIR}/guest_phases.sh" "$phase"',
            "      ;;",
            "    *)",
            f'      {GUEST_SCRIPT} --i-understand-this-attaches-ebpf "$phase"',
            "      ;;",
            "  esac",
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
        "fork_outsider",
        "fork_clone3",
        "root_detach_inside",
        "oom_inside",
        "reboot_post_inside",
        "teardown_inside",
    }:
        return text if pg.CONNECT_RE.fullmatch(value) else None
    if key == "signal":
        return text if pg.SIGNAL_RE.fullmatch(text) else None
    if key == "sent_packet":
        return text if pg.sent_packet_ok(text) else None
    if key.startswith("escape_") and key.split("_", 1)[1] in pg.ESCAPE_KINDS:
        return text if value.startswith("denied") or value.startswith("ok") else None
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
    if key == "fork_rows":
        return text if pg.FORK_ROWS_RE.fullmatch(text) else None
    if key == "drop_count":
        return text if pg.DROP_COUNT_RE.fullmatch(text) else None
    if key == "ledger_tls":
        return text if pg.LEDGER_TLS_RE.fullmatch(text) else None
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
    if payload.get("reboot_restored") not in (None, "NOT_RUN", "PASS", "FAIL"):
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
  local sent_line
  sent_line="$(python3 "$grade_py" sent-packet "${OUT}/last-tcpdump.txt")"
  note "$sent_line"
  note "$(python3 "$grade_py" ledger-line "$OUT/enforce.ndjson" --sent-line "$sent_line")"
  if [[ -f /run/vantio-drop-count ]]; then
    packets="$(awk -F= '/^packets=/{print $2}' /run/vantio-drop-count)"
    cgroup_skb="$(awk -F= '/^cgroup_skb=/{print $2}' /run/vantio-drop-count)"
    tc="$(awk -F= '/^tc=/{print $2}' /run/vantio-drop-count)"
    note "drop_count=packets=${packets:-0} cgroup_skb=${cgroup_skb:-0} tc=${tc:-0}"
  else
    note "drop_count=packets=0 cgroup_skb=0 tc=0"
  fi
  if python3 "$(cd "$(dirname "$0")" && pwd)/verify_ledger.py" "$OUT/enforce.ndjson" >/dev/null 2>&1; then
    note "ledger_chain=ok"
  else
    note "ledger_chain=fail"
  fi
  tls_rows="$(python3 - "$OUT/enforce.ndjson" <<'PY'
import json, sys
rows = bad = 0
for line in open(sys.argv[1], encoding="utf-8", errors="replace"):
    line = line.strip()
    if not line.startswith("{"):
        continue
    try:
        row = json.loads(line)
    except json.JSONDecodeError:
        continue
    if row.get("EventType") != "TLS_EGRESS":
        continue
    rows += 1
    try:
        severed = int(row.get("BytesSevered") or 0)
        observed = int(row.get("BytesObserved") or 0)
    except (TypeError, ValueError):
        bad += 1
        continue
    if severed != 0 or observed <= 0:
        bad += 1
if bad:
    print("bad")
else:
    print(f"rows={rows}")
PY
)"
  if [[ "$tls_rows" == bad ]]; then
    note "ledger_tls=rows=bad"
  else
    note "ledger_tls=${tls_rows}"
  fi
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
  local sniff_py sniff_out sniff_count sniff_line sniff_status
  sniff_py="$(cd "$(dirname "$0")" && pwd)/proof_grade.py"
  if [[ -f "$sniff_py" ]]; then
    sniff_out="$(mktemp)"
    python3 "$sniff_py" sniff-syn "${TARGET_IP}" "${TARGET_PORT}" 2 >"$sniff_out" &
    tpid=$!
    sleep 0.2
    line="$(connect_once "$where" "$join")"
    wait "$tpid" 2>/dev/null || true
    IFS=$'\t' read -r sniff_count sniff_line sniff_status < "$sniff_out" || true
    rm -f "$sniff_out" || true
    sniff_count="${sniff_count:-0}"
    if [[ "$sniff_status" == "ok" ]]; then
      if [[ -n "$sniff_line" ]]; then
        printf '%s\n' "$sniff_line" >"$OUT/last-tcpdump.txt"
      fi
      if [[ "$sniff_count" != "0" || "$line" != *result=connected* ]]; then
        printf '%s\t%s\tafpacket\n' "$line" "$sniff_count"
        return 0
      fi
    fi
  fi
  if command -v tcpdump >/dev/null 2>&1 && [[ -n "$iface" ]] && ip link show "$iface" >/dev/null 2>&1; then
    pcap="$(mktemp)"
    tcpdump -n -i lo -c 8 -w - "host ${TARGET_IP} and port ${TARGET_PORT}" >"$pcap" 2>/dev/null &
    tpid=$!
    sleep 0.2
    line="$(connect_once "$where" "$join")"
    sleep 0.4
    kill "$tpid" 2>/dev/null || true
    wait "$tpid" 2>/dev/null || true
    tcpdump -nn -v -r "$pcap" >"$OUT/last-tcpdump.txt" 2>/dev/null || true
    packets="$(tcpdump -n -r "$pcap" 2>/dev/null | wc -l | tr -d ' ')"
    rm -f "$pcap" || true
    packets="${packets:-0}"
    if [[ "$packets" != "0" || "$line" != *result=connected* ]]; then
      printf '%s\t%s\ttcpdump\n' "$line" "$packets"
      return 0
    fi
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


_OLD_STOP = r"""stop_loader_int() {
  if [[ -n "${LOADER_PID}" ]] && kill -0 "$LOADER_PID" 2>/dev/null; then
    kill -INT "$LOADER_PID" 2>/dev/null || true
    wait "$LOADER_PID" 2>/dev/null || true
  fi
  LOADER_PID=""
}
"""

_NEW_STOP = r"""stop_loader_int() {
  if [[ -z "${LOADER_PID}" ]] || ! kill -0 "$LOADER_PID" 2>/dev/null; then
    LOADER_PID=""
    return 0
  fi
  local enforcing=0
  if tr '\0' ' ' < "/proc/${LOADER_PID}/cmdline" 2>/dev/null | grep -q -- '--enforce'; then
    enforcing=1
  fi
  if [[ "$enforcing" == "1" ]]; then
    if [[ -z "${VANTIO_LAB_STOP_TOKEN:-}" || ! -x "$LOADER" ]]; then
      note "teardown=FAIL_NO_TOKEN"
      return 1
    fi
    local stop_token="$VANTIO_LAB_STOP_TOKEN"
    local stop_dir stop_py
    stop_dir="$(dirname "$VANTIO_LAB_STOP_TOKEN")"
    stop_py="$(cd "$(dirname "$0")" && pwd)/lab_stop.py"
    if [[ -f "$stop_py" ]]; then
      python3 "$stop_py" next-stop "$stop_dir" >/dev/null 2>&1 || true
      if [[ -f "$stop_dir/stop-next.json" ]]; then
        stop_token="$stop_dir/stop-next.json"
      fi
    fi
    loader_gone() {
      [[ -n "${LOADER_PID}" ]] || return 0
      local state=""
      if [[ -r "/proc/${LOADER_PID}/stat" ]]; then
        state="$(awk '{print $3}' "/proc/${LOADER_PID}/stat" 2>/dev/null || true)"
      fi
      if [[ "$state" == "Z" ]] || ! kill -0 "$LOADER_PID" 2>/dev/null; then
        wait "$LOADER_PID" 2>/dev/null || true
        return 0
      fi
      return 1
    }
    send_stop() {
      timeout 20 env VANTIO_LAB_SCOPE=lab-nonprod \
        VANTIO_LAB_DEV_TRUST="${VANTIO_LAB_DEV_TRUST:-}" \
        "$LOADER" --authenticated-stop --stop-token "$1" \
        >"$OUT/stop.log" 2>&1 || true
      if grep -F "authenticated stop accepted" "$OUT/stop.log" >/dev/null 2>&1; then
        note "teardown_stop=accepted"
      else
        note "teardown_stop=refused"
      fi
    }
    send_stop "$stop_token"
    local i
    for i in $(seq 1 50); do
      if loader_gone; then
        break
      fi
      sleep 0.3
    done
    if ! loader_gone; then
      if [[ -f "$stop_py" ]]; then
        python3 "$stop_py" next-stop "$stop_dir" >/dev/null 2>&1 || true
        if [[ -f "$stop_dir/stop-next.json" ]]; then
          stop_token="$stop_dir/stop-next.json"
        fi
      fi
      send_stop "$stop_token"
      for i in $(seq 1 50); do
        if loader_gone; then
          break
        fi
        sleep 0.3
      done
    fi
    if ! loader_gone; then
      note "teardown=FAIL_STILL_UP"
      return 1
    fi
    # vantio_used_nonce stays after a signed stop. It is the replay store.
    if find /sys/fs/bpf -name 'vantio*' ! -name 'vantio_used_nonce' -print -quit 2>/dev/null | grep -q .; then
      note "teardown_pins=remain"
      note "teardown=FAIL_PINS"
      LOADER_PID=""
      return 1
    fi
    note "teardown_pins=absent"
    local restored
    restored="$(connect_once inside "$CGROUP")"
    note "teardown_inside=${restored}"
    LOADER_PID=""
    if [[ "$restored" != *result=connected* && "$restored" != *"errno=111"* ]]; then
      note "teardown=FAIL_CONNECT"
      return 1
    fi
    note "teardown=RESTORED"
    return 0
  fi
  kill -INT "$LOADER_PID" 2>/dev/null || true
  wait "$LOADER_PID" 2>/dev/null || true
  LOADER_PID=""
}
"""

_OLD_CLEANUP = r"""  if [[ -n "${LOADER_PID}" ]] && kill -0 "$LOADER_PID" 2>/dev/null; then
    kill -INT "$LOADER_PID" 2>/dev/null || true
    wait "$LOADER_PID" 2>/dev/null || true
  fi
"""

_NEW_CLEANUP = r"""  stop_loader_int || true
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
  start_loader "$OUT/root-detach.log" "$LOADER" --enforce --stop-authority "${VANTIO_LAB_STOP_TOKEN}" --iface "$IFACE" \
    --startup-enroll-cgroup "$CGROUP" --output-file "$OUT/root-detach.ndjson"
  local banner
  banner="$(wait_banner "$OUT/root-detach.log")"
  note "root_detach_banner=$banner"
  local attempt_py grade_py
  attempt_py="$(cd "$(dirname "$0")" && pwd)/root_detach_attempt.py"
  grade_py="$(cd "$(dirname "$0")" && pwd)/proof_grade.py"
  if [[ "$banner" != "ENFORCING" || ! -f "$attempt_py" || ! -f "$grade_py" ]]; then
    note "root_detach_actor=loader"
    note "root_detach=FAIL"
    finish_not_proven
    exit 1
  fi
  while IFS= read -r line; do
    note "$line"
  done < <(python3 "$attempt_py" "$LOADER" "$CGROUP" /sys/fs/bpf/vantio_enrolled_cgroups)
  if [[ -e /sys/fs/bpf/vantio_cgroup_skb_egress_enforce || -e /sys/fs/bpf/vantio_enrolled_cgroups ]]; then
    note "root_detach_programs_remain=yes"
  else
    note "root_detach_programs_remain=no"
  fi
  if [[ -e /sys/fs/bpf/vantio_enrolled_cgroups ]]; then
    note "root_detach_pins_remain=yes"
  else
    note "root_detach_pins_remain=no"
  fi
  local inside_line sent_line ledger
  inside_line="$(measure_connect inside "$CGROUP" | cut -f1)"
  note "root_detach_inside=${inside_line}"
  measure_connect outside "" >/dev/null
  sent_line="$(python3 "$grade_py" sent-packet "$OUT/last-tcpdump.txt")"
  note "$sent_line"
  ledger="$(python3 "$grade_py" ledger-line "$OUT/root-detach.ndjson" --sent-line "$sent_line")"
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

phase_signals() {
  require_compare_pass
  require_root
  if ! prepare_net; then
    note "signal_process=down"
    finish_not_proven
    exit 1
  fi
  mkdir -p "$CGROUP"
  start_listener
  start_loader "$OUT/signals.log" "$LOADER" --enforce --stop-authority "${VANTIO_LAB_STOP_TOKEN}" --iface "$IFACE" \
    --startup-enroll-cgroup "$CGROUP" --output-file "$OUT/signals.ndjson"
  local banner
  banner="$(wait_banner "$OUT/signals.log")"
  if [[ "$banner" != "ENFORCING" ]]; then
    note "signal_process=down"
    finish_not_proven
    exit 1
  fi
  local pair name signum result pins connect line
  for pair in INT:SIGINT TERM:SIGTERM HUP:SIGHUP; do
    signum="${pair%%:*}"
    name="${pair#*:}"
    kill -"$signum" "$LOADER_PID" 2>/dev/null || true
    sleep 0.4
    result=detached
    pins=gone
    connect=restored
    if kill -0 "$LOADER_PID" 2>/dev/null && grep -F "unauthenticated stop refused signal=${name}" "$OUT/signals.log" >/dev/null 2>&1; then
      result=refused
    fi
    if [[ -e /sys/fs/bpf/vantio_enrolled_cgroups ]]; then
      pins=remain
    fi
    line="$(connect_once inside "$CGROUP")"
    if [[ "$line" == *result=timeout* || "$line" == *"errno=1"* ]]; then
      connect=blocked
    fi
    note "signal=${name} result=${result} pins=${pins} connect=${connect}"
  done
  if kill -0 "$LOADER_PID" 2>/dev/null; then
    note "signal_process=up"
  else
    note "signal_process=down"
  fi
  local grade_py verdict
  grade_py="$(cd "$(dirname "$0")" && pwd)/proof_grade.py"
  verdict="$(python3 "$grade_py" gate signals "$OUT/transcript.txt" 0)"
  note "$verdict"
  stop_loader_int
  finish_not_proven
  if [[ "$verdict" != "harness_accept=yes" ]]; then
    exit 1
  fi
}

phase_oom() {
  require_compare_pass
  require_root
  if ! prepare_net; then
    note "oom_killed=no"
    finish_not_proven
    exit 1
  fi
  mkdir -p "$CGROUP" /sys/fs/cgroup/vantio-oom
  if ! echo 67108864 > /sys/fs/cgroup/vantio-oom/memory.max 2>/dev/null; then
    note "oom_killed=no"
    note "oom_programs=gone"
    finish_not_proven
    exit 1
  fi
  mkdir -p "$CGROUP"
  start_listener
  start_loader "$OUT/oom.log" "$LOADER" --enforce --stop-authority "${VANTIO_LAB_STOP_TOKEN}" --oom-stress --iface "$IFACE" \
    --startup-enroll-cgroup "$CGROUP" --output-file "$OUT/oom.ndjson"
  local banner
  banner="$(wait_banner "$OUT/oom.log")"
  if [[ "$banner" != "ENFORCING" ]]; then
    note "oom_killed=no"
    finish_not_proven
    exit 1
  fi
  echo "$LOADER_PID" > /sys/fs/cgroup/vantio-oom/cgroup.procs 2>/dev/null || true
  : > /run/vantio-oom-go
  local i
  for i in $(seq 1 25); do
    if ! kill -0 "$LOADER_PID" 2>/dev/null; then
      break
    fi
    sleep 1
  done
  if kill -0 "$LOADER_PID" 2>/dev/null; then
    note "oom_killed=no"
  else
    note "oom_killed=yes"
    LOADER_PID=""
  fi
  if [[ -e /sys/fs/bpf/vantio_enrolled_cgroups ]]; then
    note "oom_programs=remain"
  else
    note "oom_programs=gone"
  fi
  note "oom_inside=$(connect_once inside "$CGROUP")"
  local grade_py verdict
  grade_py="$(cd "$(dirname "$0")" && pwd)/proof_grade.py"
  verdict="$(python3 "$grade_py" gate oom "$OUT/transcript.txt" 0)"
  note "$verdict"
  if [[ -n "${VANTIO_LAB_STOP_TOKEN:-}" ]]; then
    env VANTIO_LAB_SCOPE=lab-nonprod VANTIO_LAB_DEV_TRUST="${VANTIO_LAB_DEV_TRUST:-}" \
      "$LOADER" --authenticated-stop --stop-token "$VANTIO_LAB_STOP_TOKEN" >"$OUT/oom-stop.log" 2>&1 || true
  fi
  rm -f /run/vantio-oom-go
  finish_not_proven
  if [[ "$verdict" != "harness_accept=yes" ]]; then
    exit 1
  fi
}

phase_escapes() {
  require_compare_pass
  require_root
  if ! prepare_net; then
    note "escape_exec=ok errno=0"
    finish_not_proven
    exit 1
  fi
  mkdir -p "$CGROUP"
  start_listener
  start_loader "$OUT/escapes.log" "$LOADER" --enforce --stop-authority "${VANTIO_LAB_STOP_TOKEN}" --iface "$IFACE" \
    --startup-enroll-cgroup "$CGROUP" --output-file "$OUT/escapes.ndjson"
  local banner
  banner="$(wait_banner "$OUT/escapes.log")"
  if [[ "$banner" != "ENFORCING" ]]; then
    note "escape_exec=ok errno=0"
    finish_not_proven
    exit 1
  fi
  local probe_py
  probe_py="$(cd "$(dirname "$0")" && pwd)/escape_probes.py"
  while IFS= read -r line; do
    note "$line"
  done < <(python3 "$probe_py" "$CGROUP" "$TARGET_IP" "$TARGET_PORT" "$OUT")
  local grade_py verdict
  grade_py="$(cd "$(dirname "$0")" && pwd)/proof_grade.py"
  verdict="$(python3 "$grade_py" gate escapes "$OUT/transcript.txt" 0)"
  note "$verdict"
  stop_loader_int
  finish_not_proven
  if [[ "$verdict" != "harness_accept=yes" ]]; then
    exit 1
  fi
}

phase_clock() {
  if [[ "${VANTIO_LAB_ALLOW_CLOCK:-}" != "1" ]]; then
    note "clock=NOT_RUN"
    finish_not_proven
    exit 0
  fi
  require_compare_pass
  require_root
  local saved now
  saved="$(date -u +%Y-%m-%dT%H:%M:%S)"
  now="$(date +%s)"
  python3 - "$OUT/clock" "$((now + 30))" <<'PY'
import base64, json, os, sys, time
from pathlib import Path
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
except ImportError:
    raise SystemExit(1)
root = Path(sys.argv[1])
root.mkdir(parents=True, exist_ok=True)
exp = int(sys.argv[2])
key = Ed25519PrivateKey.generate()
raw = key.public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
policy = {"action": "observe", "exp": exp}
payload = json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()
document = {"policy": policy, "signature": {
    "algorithm": "Ed25519", "key_class": "dev_non_production",
    "key_id": "dev-nonprod-lab-clock", "not_a_production_root": True,
    "public_key_b64": base64.b64encode(raw).decode("ascii"),
    "signature_b64": base64.b64encode(key.sign(payload)).decode("ascii"),
}}
(root / "policy.json").write_text(json.dumps(document), encoding="utf-8")
trust = {"audience": "LAB_NONPROD", "not_a_production_root": True, "keys": [{
    "key_class": "dev_non_production", "key_id": "dev-nonprod-lab-clock",
    "not_a_production_root": True, "public_key_b64": base64.b64encode(raw).decode("ascii"),
}]}
lab = os.environ.get("VANTIO_LAB_DEV_TRUST", "")
if lab:
    extra = json.loads(Path(lab).read_text(encoding="utf-8"))
    trust["keys"].extend(extra.get("keys", []))
(root / "trust.json").write_text(json.dumps(trust), encoding="utf-8")
print("ephemeral_private_key=not_written")
PY
  if ! date -u -s "@$((now + 120))" >/dev/null 2>&1; then
    note "clock_moved=no"
    finish_not_proven
    exit 1
  fi
  trap 'date -u -s "$saved" >/dev/null 2>&1 || true' RETURN
  note "clock_moved=yes"
  note "clock_exp_passed=yes"
  start_loader "$OUT/clock.log" env VANTIO_LAB_SCOPE=lab-nonprod \
    VANTIO_LAB_DEV_TRUST="$OUT/clock/trust.json" VANTIO_POLICY_PATH="$OUT/clock/policy.json" \
    "$LOADER" --enforce --stop-authority "${VANTIO_LAB_STOP_TOKEN}" --iface "$IFACE" \
    --startup-enroll-cgroup "$CGROUP" --output-file "$OUT/clock.ndjson"
  local banner
  banner="$(wait_banner "$OUT/clock.log")"
  date -u -s "$saved" >/dev/null 2>&1 || true
  if grep -E "POLICY_EXPIRED|license_exp" "$OUT/clock.log" >/dev/null 2>&1 || [[ "$banner" != "ENFORCING" ]]; then
    note "clock_enforcement=fail_closed"
  else
    note "clock_enforcement=open"
  fi
  stop_loader_int || true
  local grade_py verdict
  grade_py="$(cd "$(dirname "$0")" && pwd)/proof_grade.py"
  verdict="$(python3 "$grade_py" gate clock "$OUT/transcript.txt" 0)"
  note "$verdict"
  finish_not_proven
  if [[ "$verdict" != "harness_accept=yes" ]]; then
    exit 1
  fi
}

phase_c15_boundary() {
  require_compare_pass
  require_root
  local stop_py grade_py dir
  stop_py="$(cd "$(dirname "$0")" && pwd)/lab_stop.py"
  grade_py="$(cd "$(dirname "$0")" && pwd)/proof_grade.py"
  dir="$OUT/boundary-harness"
  rm -rf "$dir"
  mkdir -p "$dir"
  local unlisted="$CGROUP-unlisted" exempt="$CGROUP-exempt"
  mkdir -p "$unlisted" "$exempt"
  if ! prepare_net; then
    note "boundary_unlisted=connected"
    finish_not_proven
    exit 1
  fi
  python3 "$stop_py" exception "$dir" "$exempt" || true
  start_listener
  start_loader "$OUT/boundary-harness.log" "$LOADER" --enforce --stop-authority "${VANTIO_LAB_STOP_TOKEN}" --host-cgroup-enroll \
    --cgroup-exception-file "$dir/exceptions.json" --iface "$IFACE" --output-file "$OUT/boundary-harness.ndjson"
  local banner line
  banner="$(wait_banner "$OUT/boundary-harness.log")"
  if [[ "$banner" != "ENFORCING" ]]; then
    note "boundary_unlisted=connected"
    finish_not_proven
    exit 1
  fi
  line="$(connect_once unlisted "$unlisted")"
  if [[ "$line" == *result=timeout* || "$line" == *"errno=1"* ]]; then
    note "boundary_unlisted=blocked"
  else
    note "boundary_unlisted=connected"
  fi
  line="$(connect_once exempt "$exempt")"
  if [[ "$line" == *result=connected* ]]; then
    note "boundary_exception=connected"
  else
    note "boundary_exception=blocked"
  fi
  stop_loader_int
  python3 "$stop_py" expired-exception "$dir" "$exempt" || true
  start_loader "$OUT/boundary-expired.log" "$LOADER" --enforce --stop-authority "${VANTIO_LAB_STOP_TOKEN}" --host-cgroup-enroll \
    --cgroup-exception-file "$dir/expired.json" --iface "$IFACE" --output-file "$OUT/boundary-expired.ndjson"
  banner="$(wait_banner "$OUT/boundary-expired.log")"
  line="$(connect_once exempt "$exempt")"
  if [[ "$banner" == "ENFORCING" && ( "$line" == *result=timeout* || "$line" == *"errno=1"* ) ]]; then
    note "boundary_expired=blocked"
  else
    note "boundary_expired=connected"
  fi
  stop_loader_int || true
  python3 "$stop_py" unsigned "$dir" "$exempt" || true
  start_loader "$OUT/boundary-unsigned.log" "$LOADER" --enforce --stop-authority "${VANTIO_LAB_STOP_TOKEN}" --host-cgroup-enroll \
    --cgroup-exception-file "$dir/unsigned.json" --iface "$IFACE" --output-file "$OUT/boundary-unsigned.ndjson"
  banner="$(wait_banner "$OUT/boundary-unsigned.log")"
  line="$(connect_once exempt "$exempt")"
  if [[ "$banner" == "ENFORCING" && ( "$line" == *result=timeout* || "$line" == *"errno=1"* ) ]]; then
    note "boundary_unsigned=blocked"
  else
    note "boundary_unsigned=connected"
  fi
  stop_loader_int || true
  line="$(connect_once unlisted "$unlisted")"
  if [[ "$line" == *result=connected* ]]; then
    note "boundary_stop=restored"
  else
    note "boundary_stop=blocked"
  fi
  local verdict
  verdict="$(python3 "$grade_py" gate same-boundary "$OUT/transcript.txt" 0)"
  note "$verdict"
  finish_not_proven
  if [[ "$verdict" != "harness_accept=yes" ]]; then
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
    patched = patched.replace("--enforce --", '--enforce --stop-authority "${VANTIO_LAB_STOP_TOKEN}" --')
    patched = patched.replace("--enforce \\\n", '--enforce --stop-authority "${VANTIO_LAB_STOP_TOKEN}" \\\n')
    patched = patched.replace(
        'start_loader "$OUT/enforce.log"',
        'rm -f "$OUT/enforce.ndjson" "$OUT/enforce.ndjson.head"\n  start_loader "$OUT/enforce.log"',
        1,
    )
    patched = patched.replace(
        'PYTHONPATH="${PYTHONPATH:-}:$(pwd)/python"',
        'PYTHONPATH="${PYTHONPATH:-}:$(cd "$(dirname "$0")" && pwd)/python"',
    )
    if _OLD_STOP in patched:
        patched = patched.replace(_OLD_STOP, _NEW_STOP, 1)
    if _OLD_CLEANUP in patched:
        patched = patched.replace(_OLD_CLEANUP, _NEW_CLEANUP, 1)
    patched = patched.replace(
        '  note "fork_outsider=$(connect_once outsider "")"\n  stop_loader_int\n',
        '  note "fork_outsider=$(connect_once outsider "")"\n'
        '  while IFS= read -r line; do\n'
        '    note "$line"\n'
        '  done < <(python3 - "$OUT/fork.ndjson" <<\'PY\'\n'
        "import json, sys\n"
        "ids, anchors, paths, severed = [], [], [], []\n"
        "for line in open(sys.argv[1], encoding='utf-8', errors='replace'):\n"
        "    line = line.strip()\n"
        "    if not line.startswith('{'):\n"
        "        continue\n"
        "    try:\n"
        "        row = json.loads(line)\n"
        "    except json.JSONDecodeError:\n"
        "        continue\n"
        "    if row.get('EventType') != 'NETWORK_BLOCK' or row.get('ActionTaken') != 'BLOCKED':\n"
        "        continue\n"
        "    ids.append(str(row.get('TraceId') or ''))\n"
        "    paths.append(str(row.get('DropPath') or ''))\n"
        "    try:\n"
        "        anchors.append(int(row.get('lineage_anchor') or 0))\n"
        "        severed.append(int(row.get('BytesSevered') or 0))\n"
        "    except (TypeError, ValueError):\n"
        "        anchors.append(0)\n"
        "        severed.append(0)\n"
        "same = len(set(anchors)) == 1 and anchors and anchors[0] > 0\n"
        "same = same and severed and min(severed) > 0 and set(paths) == {'cgroup_skb'}\n"
        "zero = any(item in ('', '0', '0000000000000000') for item in ids) or not ids\n"
        "anchor = anchors[0] if same and not zero else 0\n"
        "print('fork_rows=blocks=%s anchor=%s trace_zero=%s drop_path=%s' % (len(anchors), anchor, 'yes' if zero or anchor == 0 else 'no', 'cgroup_skb' if anchor else 'absent'))\n"
        "print(f'fork_anchor=parent={anchor} child={anchor} grandchild={anchor}')\n"
        "PY\n"
        ")\n"
        "  stop_loader_int\n",
        1,
    )
    patched = patched.replace(
        "    os._exit(0)\n",
        "    sys.stdout.flush()\n    os._exit(0)\n",
        1,
    )
    patched = patched.replace(
        '''  verdict="$(PYTHONPATH="python${PYTHONPATH:+:$PYTHONPATH}" python3 - "$OUT/transcript.txt" "$OUT/fork.ndjson" <<'PY'
import sys
from holds.verdicts import fork_inherit_verdict
transcript = open(sys.argv[1], encoding="utf-8", errors="replace").read()
ledger = open(sys.argv[2], encoding="utf-8", errors="replace").read()
print(fork_inherit_verdict(transcript, ledger))
PY
)"''',
        '''  local grade_py
  grade_py="$(cd "$(dirname "$0")" && pwd)/proof_grade.py"
  verdict="$(python3 "$grade_py" fork-inherit-verdict "$OUT/transcript.txt")"''',
        1,
    )
    patched = patched.replace(
        '  note "reboot_wiped=PASS"\n  note "reboot_restored=NOT_RUN"\n  finish_not_proven\n}\n',
        '  note "reboot_wiped=PASS"\n'
        '  if ! prepare_net; then\n'
        '    note "reboot_restored=FAIL"\n'
        '    finish_not_proven\n'
        '    exit 1\n'
        '  fi\n'
        '  mkdir -p "$CGROUP"\n'
        '  start_listener\n'
        '  start_loader "$OUT/reboot-post.log" "$LOADER" --enforce --stop-authority "${VANTIO_LAB_STOP_TOKEN}" --iface "$IFACE" \\\n'
        '    --startup-enroll-cgroup "$CGROUP" --output-file "$OUT/reboot-post.ndjson"\n'
        '  local banner restored\n'
        '  banner="$(wait_banner "$OUT/reboot-post.log")"\n'
        '  restored="$(connect_once inside "$CGROUP")"\n'
        '  note "reboot_post_inside=${restored}"\n'
        '  if [[ "$banner" == "ENFORCING" && ( "$restored" == *result=timeout* || "$restored" == *"errno=1"* ) ]]; then\n'
        '    note "reboot_restored=PASS"\n'
        '  else\n'
        '    note "reboot_restored=FAIL"\n'
        '    stop_loader_int || true\n'
        '    finish_not_proven\n'
        '    exit 1\n'
        '  fi\n'
        '  stop_loader_int\n'
        '  finish_not_proven\n'
        '}\n',
        1,
    )
    patched = patched.replace('case "$PHASE" in\n', _ROOT_FN + 'case "$PHASE" in\n', 1)
    patched = patched.replace(
        "  compare) phase_compare ;;\n",
        "  compare) phase_compare ;;\n"
        "  root-detach) phase_root_detach ;;\n"
        "  signals) phase_signals ;;\n"
        "  oom) phase_oom ;;\n"
        "  escapes) phase_escapes ;;\n"
        "  clock) phase_clock ;;\n"
        "  same-boundary) phase_c15_boundary ;;\n",
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
    paths = [
        env_path,
        wrapper,
        _stage_py(dest, "proof_grade.py"),
        _stage_py(dest, "root_detach_attempt.py"),
        _stage_py(dest, "lab_stop.py"),
        _stage_py(dest, "escape_probes.py"),
        _stage_py(dest, "verify_ledger.py"),
        _stage_py(dest, "guest_phases.sh"),
    ]
    holds = Path(__file__).resolve().with_name("python") / "holds"
    hold_dir = dest / "python" / "holds"
    hold_dir.mkdir(parents=True, exist_ok=True)
    for item in holds.iterdir():
        if item.suffix == ".py":
            target = hold_dir / item.name
            target.write_text(item.read_text(encoding="utf-8"), encoding="utf-8")
            paths.append(target)
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
    not_run: list[str] = []
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
            outcome = pg.phase_outcome(phase, lines, completed.returncode, boots)
            if outcome == "NOT_RUN":
                not_run.append(phase)
                continue
            if outcome != "PASS":
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
            "reboot_restored": (
                "PASS"
                if "reboot_restored=PASS" in observations
                else "FAIL"
                if any(line.startswith("reboot_restored=FAIL") for line in observations)
                else "NOT_RUN"
            ),
            "result": "FAIL" if stopped else "NOT_PASS" if not_run else "PASS",
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
    if stopped or not_run:
        print(stopped or "not_run", file=sys.stderr)
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
