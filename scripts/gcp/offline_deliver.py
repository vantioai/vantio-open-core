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
IMAGE_NAME = "vantio-phantom-engine:carry-3f5fcb1"
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


def _allow_capture(entry: Any) -> dict[str, Any] | None:
    """One guest result: case name, pid, anchor, path, and errno. Nothing else."""
    if not isinstance(entry, dict):
        return None
    name = entry.get("name")
    if not isinstance(name, str) or re.fullmatch(r"[a-z0-9-]{1,40}", name) is None:
        return None
    kept: dict[str, Any] = {"name": name}
    guest_rc = entry.get("guest_rc")
    if isinstance(guest_rc, int) and not isinstance(guest_rc, bool) and 0 <= guest_rc <= 255:
        kept["guest_rc"] = guest_rc
    if isinstance(entry.get("hold"), bool):
        kept["hold"] = entry["hold"]
    if isinstance(entry.get("enforcement_drop"), bool):
        kept["enforcement_drop"] = entry["enforcement_drop"]
    errno = entry.get("errno")
    if isinstance(errno, int) and not isinstance(errno, bool) and 0 <= errno <= 255:
        kept["errno"] = errno
    pid = entry.get("pid")
    if isinstance(pid, int) and not isinstance(pid, bool) and 0 <= pid <= 2**22:
        kept["pid"] = pid
    anchor = entry.get("lineage_anchor")
    if isinstance(anchor, int) and not isinstance(anchor, bool) and 0 <= anchor <= 2**32:
        kept["lineage_anchor"] = anchor
    if entry.get("path") == CEILING_PATH:
        kept["path"] = CEILING_PATH
    uid = entry.get("uid")
    if uid in (0, 65534):
        kept["uid"] = uid
    reasons = entry.get("fail_reasons")
    if isinstance(reasons, list):
        kept["fail_reasons"] = [
            item for item in reasons if isinstance(item, str) and re.fullmatch(r"[a-z0-9_]{1,40}", item)
        ][:16]
    failed = entry.get("failed_cases")
    if isinstance(failed, list):
        kept["failed_cases"] = [
            item for item in failed if isinstance(item, str) and re.fullmatch(r"[a-z0-9_-]{1,40}", item)
        ][:16]
    not_run = entry.get("not_run")
    if isinstance(not_run, list):
        kept["not_run"] = [
            item for item in not_run if isinstance(item, str) and re.fullmatch(r"[a-z0-9_-]{1,40}", item)
        ][:16]
    cases = entry.get("cases")
    if isinstance(cases, list):
        rows = []
        for item in cases:
            if not isinstance(item, dict):
                continue
            case_name = item.get("name")
            if not isinstance(case_name, str) or re.fullmatch(r"[a-z0-9_-]{1,40}", case_name) is None:
                continue
            row: dict[str, Any] = {"name": case_name}
            if isinstance(item.get("pass"), bool):
                row["pass"] = item["pass"]
            if isinstance(item.get("expect_deny"), bool):
                row["expect_deny"] = item["expect_deny"]
            file_errno = item.get("file_errno")
            if isinstance(file_errno, int) and not isinstance(file_errno, bool) and 0 <= file_errno <= 255:
                row["file_errno"] = file_errno
            net_errno = item.get("net_errno")
            if isinstance(net_errno, int) and not isinstance(net_errno, bool) and 0 <= net_errno <= 255:
                row["net_errno"] = net_errno
            reason = item.get("reason")
            if isinstance(reason, str) and re.fullmatch(r"[a-z0-9_]{1,40}", reason):
                row["reason"] = reason
            if item.get("skipped") is True:
                row["skipped"] = True
            case_pid = item.get("pid")
            if isinstance(case_pid, int) and not isinstance(case_pid, bool) and 0 <= case_pid <= 2**22:
                row["pid"] = case_pid
            case_anchor = item.get("lineage_anchor")
            if isinstance(case_anchor, int) and not isinstance(case_anchor, bool) and 0 <= case_anchor <= 2**32:
                row["lineage_anchor"] = case_anchor
            if item.get("path") == CEILING_PATH:
                row["path"] = CEILING_PATH
            rows.append(row)
        if rows:
            kept["cases"] = rows[:24]
    return kept


def allow_record(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Keep only known keys and typed values. Unknown fields are dropped."""
    kept: dict[str, Any] = {}
    for key, value in payload.items():
        if key == "verify" and isinstance(value, dict):
            status = value.get("status")
            if isinstance(status, str) and status in ENUMS["verify_status"]:
                kept["verify_status"] = status
            continue
        if key == "kernel" and isinstance(value, dict):
            for flag, dest in (("btf", "kernel_btf"), ("bpffs", "kernel_bpffs"), ("cgroup_v2", "kernel_cgroup_v2")):
                if isinstance(value.get(flag), bool):
                    kept[dest] = value[flag]
            lsm = value.get("lsm")
            if isinstance(lsm, str) and re.fullmatch(r"[a-z0-9,]{0,80}", lsm):
                kept["kernel_lsm"] = lsm
            continue
        if key == "debs" and isinstance(value, list):
            rows = []
            for item in value:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                digest = item.get("sha256")
                if (
                    isinstance(name, str)
                    and re.fullmatch(r"[A-Za-z0-9.+_-]{1,120}", name)
                    and SECRET_RE.search(name) is None
                    and not name.lower().startswith(("ghp_", "gho_", "ghu_", "ghs_", "ghr_", "github_pat_"))
                    and "private" not in name.lower()
                    and isinstance(digest, str)
                    and HEX64_RE.fullmatch(digest)
                ):
                    rows.append({"name": name, "sha256": digest})
            kept["debs"] = rows
            continue
        if key == "objects" and isinstance(value, list):
            names = [
                item
                for item in value
                if isinstance(item, str)
                and re.fullmatch(
                    r"[0-9]{1,20}/(seal\.oci\.tar|contract\.tar|qwen2\.5-3b-instruct-q4_k_m\.gguf|llama-b11540-bin-ubuntu-x64\.tar\.gz)",
                    item,
                )
            ]
            kept["objects"] = names
            continue
        if key == "via" and isinstance(value, list):
            kept["via"] = [item for item in value if item in ("gcloud", "resumable")]
            continue
        if key == "reasons" and isinstance(value, list):
            kept["reasons"] = [
                item for item in value if isinstance(item, str) and re.fullmatch(r"[a-z0-9_]{1,40}", item)
            ]
            continue
        if key in ENUMS:
            if isinstance(value, str) and value in ENUMS[key]:
                kept[key] = value
            continue
        if key in {"seal_sha256", "contract_sha256", "trust_sha256"} and isinstance(value, str) and HEX64_RE.fullmatch(value):
            kept[key] = value
            continue
        if key in {"enterprise_sha", "bundle_commit"} and isinstance(value, str) and HEX40_RE.fullmatch(value):
            kept[key] = value
            continue
        if key in {
            "abort",
            "batteries",
            "deleted",
            "kernel_btf",
            "kernel_bpffs",
            "kernel_cgroup_v2",
            "mutated",
            "public_ip",
            "reboot_observed",
            "uninstall_verified",
            "deny_attr_post_kill",
            "vm_digest_match",
        } and isinstance(value, bool):
            kept[key] = value
            continue
        if key in {"enterprise_rc", "descendant_rc", "debs_count"} and isinstance(value, int) and not isinstance(value, bool):
            kept[key] = value
            continue
        if key in {"estimated_gross_usd", "hours", "worst_case_run_usd"} and isinstance(value, str) and re.fullmatch(r"[0-9]{1,8}(\.[0-9]{1,4})?", value):
            kept[key] = value
            continue
        if key == "lab_project_id" and value == LAB_PROJECT:
            kept[key] = value
            continue
        if key == "package_image" and value == PACKAGE_IMAGE:
            kept[key] = value
            continue
        if key == "snapshot" and value == SNAPSHOT:
            kept[key] = value
            continue
        if key == "name" and isinstance(value, str) and re.fullmatch(r"vantio-gcp-lab-[0-9]{1,20}", value):
            kept[key] = value
            continue
        if key == "account_id" and isinstance(value, str) and re.fullmatch(r"[0-9]{12}", value):
            kept[key] = value
            continue
        if key == "step" and value in {"bundle", "arm", "teardown", "verify-removed"}:
            kept[key] = value
            continue
        if key == "repeats" and isinstance(value, list):
            rows = [item for item in (allow_battery(entry) for entry in value) if item]
            if len(rows) == BATTERY_REPEATS:
                kept["repeats"] = rows
            continue
        if key == "self_service" and isinstance(value, list):
            rows = []
            for item in value:
                if not isinstance(item, dict):
                    continue
                phase = item.get("phase")
                protection = item.get("protection")
                state = item.get("state")
                reason = item.get("reason")
                if phase not in {"install", "rollback", "uninstall", "verify-removal", "enrollment"}:
                    continue
                if protection not in {"OBSERVE", "PROTECTED", "NONE"}:
                    continue
                if not isinstance(state, str) or re.fullmatch(r"[A-Z0-9_]{1,40}", state) is None:
                    continue
                if not isinstance(reason, str) or re.fullmatch(r"[A-Z0-9_]{0,40}", reason) is None:
                    continue
                rows.append(
                    {
                        "phase": phase,
                        "proof_state": "NOT_PROVED",
                        "protection": protection,
                        "reason": reason,
                        "state": state,
                    }
                )
            kept["self_service"] = rows
            continue
        if key in {"loader_kill", "loader_restart"} and value in {"held", "fail", "infra_retry", "setup_invalid"}:
            kept[key] = value
            continue
        if key == "cases" and isinstance(value, list):
            rows = []
            for item in value:
                if not isinstance(item, dict):
                    continue
                name = item.get("case")
                result = item.get("result")
                if name not in {"enterprise", "descendant-b1", "loader-kill", "loader-restart"}:
                    continue
                if result not in {"held", "fail", "ran", "infra_retry", "setup_invalid"}:
                    continue
                row: dict[str, Any] = {"case": name, "result": result}
                errno = item.get("errno")
                if (
                    result not in {"setup_invalid", "infra_retry"}
                    and isinstance(errno, int)
                    and not isinstance(errno, bool)
                    and 0 <= errno <= 255
                ):
                    row["errno"] = errno
                pid = item.get("deny_pid")
                if isinstance(pid, int) and not isinstance(pid, bool) and 0 <= pid <= 2**22:
                    row["deny_pid"] = pid
                count = item.get("denied_rows")
                if isinstance(count, int) and not isinstance(count, bool) and 0 <= count <= 100000:
                    row["denied_rows"] = count
                anchor = item.get("lineage_anchor")
                if isinstance(anchor, int) and not isinstance(anchor, bool) and 0 <= anchor <= 2**32:
                    row["lineage_anchor"] = anchor
                path = item.get("path")
                if path == CEILING_PATH:
                    row["path"] = path
                rows.append(row)
            kept["cases"] = rows
            continue
        if key == "captures" and isinstance(value, list):
            rows = [item for item in (_allow_capture(entry) for entry in value) if item]
            if rows:
                kept["captures"] = rows
            continue
        if key == "full_set":
            continue
    if "repeats" in kept:
        kept["full_set"] = full_set_passes(kept["repeats"])
    return kept
