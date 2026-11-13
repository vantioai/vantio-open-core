#!/usr/bin/env python3
"""Customer-install enforcement proof on one Ubuntu 24.04 lab VM.

The git tip is a Phantom Engine commit listed in pe-git-sha-allowlist.txt.
It is not a seal digest.
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
ALLOWLIST_FILE = Path(__file__).resolve().parent / "pe-git-sha-allowlist.txt"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
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
BUILD_SHA_NAME = "build-sha"
BUILD_SHA_PATH = f"{LAB_DIR}/{BUILD_SHA_NAME}"
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
USAGE = "usage: enforcement_proof.py precheck|sha|ancestor|plan|run|teardown"
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
