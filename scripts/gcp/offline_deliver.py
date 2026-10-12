#!/usr/bin/env python3
"""Offline Phantom Engine delivery onto one private Ubuntu 24.04 lab VM.

The sealed bundle moves through gs://vantio-lab-oct08-handoff and then over
IAP. It is never a GitHub Actions artifact. This module does not call GCP
unless GCP_LAB_EXECUTE=1. It refuses the Navera project and any external
address.

Audience: INTERNAL_CLEAN_HOST_PROOF
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import redirect_stdout
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Mapping, Sequence

import lab_auto as lab
import redteam_brain as rtbrain
import redteam_campaign
import redteam_packet

CLAIM_CAP = "INTERNAL_CLEAN_HOST_PROOF"
LAB_PROJECT = "vantio-lab-oct08"
BUCKET = "vantio-lab-oct08-handoff"
HANDOFF_SA = "vantio-lab-handoff@vantio-lab-oct08.iam.gserviceaccount.com"
GHA_SA = "vantio-lab-gha@vantio-lab-oct08.iam.gserviceaccount.com"
# The provider that authenticated run 38055862852. Fetch runs in w3-lab-auto,
# which does not see the gcp-lab environment variable, so the workflow carries it.
WIF_PROVIDER = "projects/910881070503/locations/global/workloadIdentityPools/github-actions/providers/github"
SSH_WAIT_SECONDS = 300
REBOOT_WAIT_SECONDS = 480
PROBE_SSH_TIMEOUT = 20
CASE_SSH_TIMEOUT = 1200
SSHD_WAIT_SECONDS = 300
BATTERY_REPEATS = 2
FULL_BATTERY = ("kernel", "seal", "enterprise", "descendant-b1")
WIF_PROVIDER_RE = re.compile(
    r"^projects/[0-9]{6,20}/locations/global/workloadIdentityPools/github-actions/providers/github$"
)
NETWORK = "vantio-lab-offline"
SUBNET = "vantio-lab-offline-usc1"
NETWORK_TAG = "vantio-gcp-lab"
IMAGE_FAMILY = "ubuntu-2404-lts-amd64"
IMAGE_PROJECT = "ubuntu-os-cloud"
PACKAGE_IMAGE = "ubuntu:24.04"
SNAPSHOT = "20261008T000000Z"
SNAPSHOT_LINES = (
    "deb [check-valid-until=no] https://snapshot.ubuntu.com/ubuntu/20261008T000000Z noble main universe",
    "deb [check-valid-until=no] https://snapshot.ubuntu.com/ubuntu/20261008T000000Z noble-updates main universe",
    "deb [check-valid-until=no] https://snapshot.ubuntu.com/ubuntu/20261008T000000Z noble-security main universe",
)
POLICY_ALLOW_SEAL = "f882dd81297b02c11c55d9df69f00d9fffa710d1a87d36066a5645922804d753"
TRUST_SHA256 = "2e4a1da7bf44f0bddfc2a3ce3eda007fa6cc1455332f26769bd346fafc297876"
TRUST_KEY_ID = "test-nonprod-ed25519-2026-10-02"
TRUST_MEMBER = "vantio_enterprise_protocol/trust/test_nonprod_2026_10_02.json"
PUBLIC_INSTALLER_PIN = "e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e"
TRACKING_2A_SEAL = "16c9e5638c169e5fdd3fd7291b3225a809b18abfe464d717c2d31a398d5bda6a"
IMAGE_NAME = "vantio-phantom-engine:unpin-70a50bd"
GUEST_DIR = "/var/lib/vantio-lab/guest"
ROWS_JSON = "/var/lib/vantio-lab/enterprise-pe-rows.json"
ZONE = lab.ZONE
E2_MICRO_USD_PER_HOUR = Decimal("0.0084")
PD_BALANCED_USD_PER_GB_MONTH = Decimal("0.10")
DISK_GB = Decimal("10")
HOURS_PER_MONTH = Decimal("730")
MAX_SEAL_BYTES = 80_000_000
MAX_CONTRACT_BYTES = 20_000_000
MAX_MEMBER_BYTES = 2_000_000
RUN_ID_RE = re.compile(r"^[0-9]{1,20}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
SECRET_RE = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----"
    r"|AKIA[0-9A-Z]{16}"
    r"|(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|glpat-[A-Za-z0-9\-_]{20,}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|ya29\.[0-9A-Za-z\-_]+",
    re.S,
)
MAX_BATTERY_DEPTH = 8
PRIVATE_KEY_TEXT = re.compile(br"-----BEGIN [A-Z ]*PRIVATE KEY-----")
USAGE = (
    "usage: offline_deliver.py assert-bundle|upload-handoff|download-handoff|"
    "hash-debs|check-dispatch|create-instance|plumb-guest|run-batteries|run-redteam|run-self-service|delete-handoff|remove-oslogin-key|"
    "teardown-if-present"
)


def require_lab_project(project: str) -> str:
    if (
        not isinstance(project, str)
        or "navera" in project.lower()
        or project != LAB_PROJECT
        or not lab.valid_lab_project(project)
    ):
        raise SystemExit("refusing project")
    return project


def require_run_id(value: str) -> str:
    if RUN_ID_RE.fullmatch(value or "") is None:
        raise SystemExit("run_id")
    return value


def instance_name(run_id: str) -> str:
    name = f"{lab.NAME_PREFIX}{require_run_id(run_id)}"
    if len(name) > 63 or not name.startswith(lab.NAME_PREFIX):
        raise SystemExit("name")
    return name


def object_names(run_id: str) -> tuple[str, str]:
    prefix = require_run_id(run_id)
    return (f"{prefix}/seal.oci.tar", f"{prefix}/contract.tar")


def brain_requested(env: Mapping[str, str]) -> bool:
    raw = env.get("REDTEAM_BRAIN", "false").strip().lower()
    if raw not in ("true", "false"):
        raise SystemExit("brain")
    return raw == "true"


def brain_object_names(run_id: str) -> tuple[str, str]:
    prefix = require_run_id(run_id)
    return (f"{prefix}/{rtbrain.MODEL_NAME}", f"{prefix}/{rtbrain.RUNTIME_NAME}")


def handoff_objects(env: Mapping[str, str]) -> tuple[str, ...]:
    names = object_names(env.get("GITHUB_RUN_ID", ""))
    if brain_requested(env):
        return names + brain_object_names(env.get("GITHUB_RUN_ID", ""))
    return names


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def redact(text: str) -> str:
    cleaned = SECRET_RE.sub("[redacted]", text)
    token = os.environ.get("W3_LAB_PRIVATE_BUNDLE_TOKEN", "")
    if token:
        cleaned = cleaned.replace(token, "[redacted]")
    return cleaned


def classify_gcloud_cp(returncode: int, stderr: str) -> str:
    if returncode == 0:
        return "uploaded"
    text = stderr or ""
    if "storage.objects.get" in text or "403" in text:
        return "fallback_json"
    return "fail"


def estimate_gross_usd(hours: Decimal) -> Decimal:
    if hours < 0:
        raise SystemExit("hours")
    disk_per_hour = DISK_GB * PD_BALANCED_USD_PER_GB_MONTH / HOURS_PER_MONTH
    return (E2_MICRO_USD_PER_HOUR + disk_per_hour) * hours


def _money(amount: Decimal) -> str:
    return format(amount.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), "f")


def github_output(name: str, value: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_]+", name) or "\n" in value or "\r" in value:
        raise SystemExit("output")
    path = os.environ.get("GITHUB_OUTPUT", "").strip()
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def _require_execute(env: Mapping[str, str]) -> None:
    if env.get("GCP_LAB_EXECUTE") != "1":
        raise SystemExit("refusing to call gcloud")


def _evidence_dir(env: Mapping[str, str]) -> Path:
    raw = env.get("EVIDENCE_DIR", "").strip()
    path = Path(raw or "gcp-lab-evidence")
    path.mkdir(parents=True, exist_ok=True)
    return path


EVIDENCE_FILES = frozenset(
    {
        "bundle-digests.json",
        "cost-gate.json",
        "debs.json",
        "download.json",
        "gcp-lab-rows.json",
        "handoff-deleted.json",
        "handoff.json",
        "instance.json",
        "prepare-bundle.json",
        "guest-evidence.json",
        "redteam-packet.json",
        "teardown.json",
    }
)
CEILING_PATH = "/var/lib/vantio-pe-clean-host/d/secret"
HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
SHORT_RE = re.compile(r"^[A-Za-z0-9_.:@+/-]{1,80}$")
ENUMS = {
    "bucket": frozenset({BUCKET}),
    "claim_cap": frozenset({CLAIM_CAP}),
    "cloud": frozenset({"gcp"}),
    "image": frozenset({f"{IMAGE_PROJECT}/{IMAGE_FAMILY}", IMAGE_NAME}),
    "machine_type": frozenset({lab.MACHINE_TYPE, rtbrain.BRAIN_MACHINE}),
    "mode": frozenset({"plumb", "enterprise", "descendant-b1", "self-service"}),
    "network": frozenset({NETWORK}),
    "project_id": frozenset({LAB_PROJECT}),
    "status": frozenset({"PLUMB_DIGEST_MATCH", "BUNDLE_READY", "BLOCKED_BUNDLE", "VERIFIED_REMOVED", "NOT_REMOVED", "SELF_SERVICE"}),
    "subnet": frozenset({SUBNET}),
    "verify_status": frozenset({"VERIFIED_REMOVED", "NOT_REMOVED", "UNKNOWN"}),
    "zone": frozenset({ZONE}),
    "expected_oop_usd": frozenset({"0", "UNKNOWN"}),
    "out_of_pocket_usd": frozenset({"0"}),
    "spend_source": frozenset({"empty_project_no_vms_or_disks", "supplied"}),
}
