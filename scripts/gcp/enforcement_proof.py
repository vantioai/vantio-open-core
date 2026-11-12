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
