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
REBOOT_WAIT_SECONDS = 600
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
IMAGE_NAME = "vantio-phantom-engine:r11-f8864c8"
GUEST_DIR = "/tmp/vantio-lab"
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
    if isinstance(guest_rc, int) and not isinstance(guest_rc, bool) and -1 <= guest_rc <= 255:
        kept["guest_rc"] = guest_rc
    if isinstance(entry.get("hold"), bool):
        kept["hold"] = entry["hold"]
    if isinstance(entry.get("enforcement_drop"), bool):
        kept["enforcement_drop"] = entry["enforcement_drop"]
    errno = entry.get("errno")
    if isinstance(errno, int) and not isinstance(errno, bool) and -1 <= errno <= 255:
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
            if isinstance(file_errno, int) and not isinstance(file_errno, bool) and -1 <= file_errno <= 255:
                row["file_errno"] = file_errno
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
        if key in {"loader_kill", "loader_restart"} and value in {"held", "fail"}:
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
                if result not in {"held", "fail", "ran"}:
                    continue
                row: dict[str, Any] = {"case": name, "result": result}
                errno = item.get("errno")
                if isinstance(errno, int) and not isinstance(errno, bool) and -1 <= errno <= 255:
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


def allow_battery(entry: Any, depth: int = 0) -> dict[str, Any] | None:
    """Keep the full proof fields from one repeat. Drop hostnames, paths, and raw events."""
    if depth > MAX_BATTERY_DEPTH or not isinstance(entry, dict):
        return None
    kept: dict[str, Any] = {}
    for key, value in entry.items():
        if key in {"grant", "revoke", "pre", "post", "probe"} and isinstance(value, dict):
            nested = allow_battery(value, depth + 1)
            if nested:
                kept[key] = nested
            continue
        if key in {"b1_pass", "descendant_pass", "deny_hold", "reboot_observed", "reboot_requested", "attributable", "enforcement_drop"} and isinstance(value, bool):
            kept[key] = value
            continue
        if key == "lineage_anchor" and isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 2**32:
            kept[key] = value
            continue
        if key == "path" and value == CEILING_PATH:
            kept[key] = value
            continue
        if key == "failed_cases" and isinstance(value, list):
            names = [
                item
                for item in value
                if isinstance(item, str) and re.fullmatch(r"[a-z0-9_-]{1,40}", item)
            ]
            kept[key] = names[:16]
            continue
        if key in {"denied_rows", "deny_pid", "bpftool_rc"} and isinstance(value, int) and not isinstance(value, bool):
            if key == "deny_pid" and not 0 <= value <= 2**22:
                continue
            if key == "denied_rows" and not 0 <= value <= 100000:
                continue
            if key == "bpftool_rc" and not -1 <= value <= 255:
                continue
            kept[key] = value
            continue
        if key == "loader_running" and isinstance(value, bool):
            kept[key] = value
            continue
        if key in {"enterprise_rc", "descendant_rc", "repeat"} and isinstance(value, int) and not isinstance(value, bool):
            if key == "repeat" and not 1 <= value <= BATTERY_REPEATS:
                continue
            kept[key] = value
            continue
        if key in {"nobody_errno", "errno"} and isinstance(value, int) and not isinstance(value, bool) and -1 <= value <= 255:
            kept[key] = value
            continue
        if key == "phase" and value in {"pre", "post"}:
            kept[key] = value
            continue
        if key == "battery" and value in {"enterprise", "descendant-b1"}:
            kept[key] = value
            continue
        if key == "result" and value in {"open_ok", "open_error", "probe_failed", "not_run", "pass", "fail"}:
            kept[key] = value
            continue
        if key == "image" and value == IMAGE_NAME:
            kept[key] = value
            continue
        if key == "boot_id" and isinstance(value, str) and re.fullmatch(r"[0-9a-f-]{36}", value):
            kept[key] = value
            continue
        if key == "kernel_btf" and isinstance(value, bool):
            kept[key] = value
            continue
        if key == "kernel_bpffs" and isinstance(value, bool):
            kept[key] = value
            continue
        if key == "kernel_cgroup_v2" and isinstance(value, bool):
            kept[key] = value
            continue
        if key == "kernel_lsm" and isinstance(value, str) and re.fullmatch(r"[a-z0-9,]{0,80}", value):
            kept[key] = value
            continue
        if key == "seal_checked" and isinstance(value, bool):
            kept[key] = value
            continue
        if key == "convergence_ms" and isinstance(value, (int, float)) and not isinstance(value, bool):
            if isinstance(value, int) and value.bit_length() > 32:
                continue
            try:
                number = float(value)
            except (OverflowError, ValueError):
                continue
            if 0 <= number <= 3_600_000:
                kept[key] = value
            continue
        if key == "rows" and isinstance(value, dict):
            nested = allow_battery(value, depth + 1)
            if nested:
                kept[key] = nested
            continue
    return kept or None


def battery_schedule(repeats: int = BATTERY_REPEATS) -> list[str]:
    """Each repeat is the full portable set: enterprise rows, then descendant-b1."""
    if not isinstance(repeats, int) or isinstance(repeats, bool) or repeats < 2:
        raise SystemExit("repeats")
    return [step for _ in range(repeats) for step in ("enterprise", "descendant-b1")]


def full_set_passes(repeats: Sequence[Mapping[str, Any]]) -> bool:
    if len(repeats) != BATTERY_REPEATS:
        return False
    indexes: list[int] = []
    for entry in repeats:
        index = entry.get("repeat")
        if not isinstance(index, int) or isinstance(index, bool):
            return False
        indexes.append(index)
        if entry.get("enterprise_rc") != 0 and entry.get("deny_hold") is not True:
            return False
        if entry.get("descendant_rc") != 0:
            return False
        if entry.get("b1_pass") is not True or entry.get("reboot_observed") is not True:
            return False
        if entry.get("kernel_btf") is not True or entry.get("kernel_cgroup_v2") is not True or entry.get("kernel_bpffs") is not True:
            return False
        if entry.get("seal_checked") is not True:
            return False
        rows = entry.get("rows")
        if not isinstance(rows, dict) or "grant" not in rows or "revoke" not in rows:
            return False
    return indexes == list(range(1, BATTERY_REPEATS + 1))


def write_evidence(path: Path, payload: Mapping[str, Any]) -> None:
    allowed = allow_record(payload)
    text = redact(json.dumps(allowed, indent=2, sort_keys=True) + "\n")
    if "PRIVATE KEY" in text or SECRET_RE.search(text) or "ghp_" in text:
        raise SystemExit("token_in_evidence")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise SystemExit("evidence_symlink")
    path.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    sidecar = path.with_name(path.name + ".sha256")
    if sidecar.is_symlink() or sidecar.is_dir():
        _remove_evidence_path(sidecar)
    sidecar.write_text(f"{digest}  {path.name}\n", encoding="utf-8")


def _member_refused(name: str) -> bool:
    if name.startswith("/") or name.startswith("\\"):
        return True
    return ".." in name.split("/")


def verify_seal_file(path: Path, expected: str) -> str:
    if expected in (PUBLIC_INSTALLER_PIN, TRACKING_2A_SEAL) or HEX64_RE.fullmatch(expected) is None:
        raise SystemExit("bundle_seal")
    if not path.is_file():
        raise SystemExit("bundle_layout")
    size = path.stat().st_size
    if size <= 0 or size > MAX_SEAL_BYTES:
        raise SystemExit("bundle_seal")
    digest = sha256_file(path)
    if digest in (PUBLIC_INSTALLER_PIN, TRACKING_2A_SEAL) or digest != expected:
        raise SystemExit("bundle_seal")
    return digest


def verify_contract_trust(path: Path, expected_trust: str) -> str:
    if HEX64_RE.fullmatch(expected_trust) is None:
        raise SystemExit("bundle_trust")
    if not path.is_file():
        raise SystemExit("bundle_layout")
    size = path.stat().st_size
    if size <= 0 or size > MAX_CONTRACT_BYTES:
        raise SystemExit("bundle_contract")
    found = False
    try:
        with tarfile.open(path, "r:*") as tar:
            members = tar.getmembers()
            if not members or len(members) > 200:
                raise SystemExit("bundle_contract")
            names = [member.name for member in members]
            if "guest_rows.py" not in names or TRUST_MEMBER not in names:
                raise SystemExit("bundle_contract")
            for member in members:
                if _member_refused(member.name) or member.name.endswith("private-key.pem"):
                    raise SystemExit("bundle_contract")
                if member.isdir():
                    continue
                if not member.isfile() or member.size < 0 or member.size > MAX_MEMBER_BYTES:
                    raise SystemExit("bundle_contract")
                handle = tar.extractfile(member)
                if handle is None:
                    raise SystemExit("bundle_contract")
                body = handle.read()
                if PRIVATE_KEY_TEXT.search(body):
                    raise SystemExit("bundle_private_key")
                if member.name != TRUST_MEMBER:
                    continue
                if hashlib.sha256(body).hexdigest() != expected_trust:
                    raise SystemExit("bundle_trust")
                payload = json.loads(body)
                keys = payload.get("keys") if isinstance(payload, dict) else None
                if not isinstance(keys, list) or len(keys) != 1 or not isinstance(keys[0], dict):
                    raise SystemExit("bundle_trust")
                key = keys[0]
                if key.get("not_a_production_root") is not True:
                    raise SystemExit("bundle_production_root")
                if key.get("environment") != "NON-PRODUCTION" or key.get("label") != "TEST":
                    raise SystemExit("bundle_trust")
                if key.get("key_id") != TRUST_KEY_ID:
                    raise SystemExit("bundle_trust")
                found = True
    except (tarfile.TarError, json.JSONDecodeError):
        raise SystemExit("bundle_contract") from None
    if not found:
        raise SystemExit("bundle_trust")
    return sha256_file(path)


def expected_seal(env: Mapping[str, str]) -> str:
    raw = env.get("EXPECTED_SEAL", "").strip().lower()
    if HEX64_RE.fullmatch(raw) is None or raw in (PUBLIC_INSTALLER_PIN, TRACKING_2A_SEAL):
        raise SystemExit("seal")
    return raw


def batteries_requested(env: Mapping[str, str]) -> bool:
    raw = env.get("RUN_BATTERIES", "false").strip().lower()
    if raw not in ("true", "false"):
        raise SystemExit("batteries")
    return raw == "true"


def refuse_batteries(env: Mapping[str, str]) -> str:
    """Batteries are refused for the plumbing-only seal f882dd81."""
    seal = expected_seal(env)
    if batteries_requested(env) and seal == POLICY_ALLOW_SEAL:
        raise SystemExit("batteries_refused_old_seal")
    return seal


def assert_bundle_dir(directory: Path, expected: str) -> dict[str, str]:
    seal = verify_seal_file(directory / "seal.oci.tar", expected)
    contract = verify_contract_trust(directory / "contract.tar", TRUST_SHA256)
    return {"seal_sha256": seal, "contract_sha256": contract, "trust_sha256": TRUST_SHA256}


def offline_labels(now_epoch: int, minutes: int) -> dict[str, str]:
    minutes = lab.bounded_minutes(minutes)
    if not isinstance(now_epoch, int) or isinstance(now_epoch, bool) or now_epoch < 1_700_000_000:
        raise SystemExit("now")
    return {
        lab.LABEL_LAB: "gcp",
        lab.LABEL_OWNER: "gha",
        lab.LABEL_EXPIRES: str(now_epoch + minutes * 60),
        lab.LABEL_LIFE: str(minutes),
    }


def offline_startup(minutes: int) -> str:
    minutes = lab.bounded_minutes(minutes)
    return "\n".join(
        [
            "#!/bin/bash",
            "set -u",
            f"shutdown -h +{minutes} || systemd-run --on-active={minutes}min --unit=vantio-gcp-lab-stop /sbin/shutdown -h now",
            "",
        ]
    )


def offline_create_argv(plan: Mapping[str, Any], script_path: str) -> list[str]:
    project = require_lab_project(str(plan["project_id"]))
    name = str(plan["name"])
    if not name.startswith(lab.NAME_PREFIX):
        raise SystemExit("name")
    if plan.get("public_ip") is not False or plan.get("service_account") is not None:
        raise SystemExit("address")
    if plan.get("network") != NETWORK or plan.get("subnet") != SUBNET:
        raise SystemExit("network")
    if plan.get("image_family") != IMAGE_FAMILY or plan.get("image_project") != IMAGE_PROJECT:
        raise SystemExit("image")
    labels = plan["labels"]
    if not lab.labels_owned(labels, name):
        raise SystemExit("labels")
    machine = str(plan.get("machine_type") or lab.MACHINE_TYPE)
    disk = str(plan.get("boot_disk_gb") or lab.BOOT_DISK_GB)
    micro = machine == lab.MACHINE_TYPE and disk == lab.BOOT_DISK_GB
    brain = machine == rtbrain.BRAIN_MACHINE and disk == "30GB"
    if not micro and not brain:
        raise SystemExit("machine")
    label_arg = ",".join(f"{key}={labels[key]}" for key in sorted(labels))
    argv = [
        "gcloud",
        "compute",
        "instances",
        "create",
        name,
        f"--project={project}",
        f"--zone={ZONE}",
        f"--machine-type={machine}",
        f"--image-family={IMAGE_FAMILY}",
        f"--image-project={IMAGE_PROJECT}",
        f"--boot-disk-size={disk}",
        "--boot-disk-type=pd-balanced",
        f"--network={NETWORK}",
        f"--subnet={SUBNET}",
        "--no-address",
        "--no-service-account",
        "--no-scopes",
        f"--tags={NETWORK_TAG}",
        "--metadata=enable-oslogin=TRUE,block-project-ssh-keys=TRUE",
        f"--metadata-from-file=startup-script={script_path}",
        "--shielded-secure-boot",
        "--shielded-vtpm",
        "--shielded-integrity-monitoring",
        f"--labels={label_arg}",
    ]
    joined = " ".join(argv)
    if "navera" in joined.lower() or "--address=" in joined:
        raise SystemExit("address")
    return argv


def iap_ssh_argv(project: str, name: str, command: str) -> list[str]:
    require_lab_project(project)
    if not name.startswith(lab.NAME_PREFIX):
        raise SystemExit("name")
    if "\n" in command or "\x00" in command:
        raise SystemExit("command")
    return [
        "gcloud",
        "compute",
        "ssh",
        name,
        f"--project={project}",
        f"--zone={ZONE}",
        "--tunnel-through-iap",
        "--ssh-key-expire-after=1h",
        "--quiet",
        "--strict-host-key-checking=no",
        "--ssh-flag=-oServerAliveInterval=30",
        "--ssh-flag=-oServerAliveCountMax=20",
        "--command",
        command,
    ]


def iap_scp_argv(project: str, sources: Sequence[str], destination: str) -> list[str]:
    require_lab_project(project)
    if not sources:
        raise SystemExit("scp")
    parts = [*sources, destination]
    remote = [item for item in parts if ":" in item]
    if len(remote) != 1:
        raise SystemExit("scp")
    host = remote[0].split(":", 1)[0]
    if not host.startswith(lab.NAME_PREFIX) or ".." in remote[0]:
        raise SystemExit("scp")
    for item in parts:
        if "\n" in item or "\x00" in item:
            raise SystemExit("scp")
    return [
        "gcloud",
        "compute",
        "scp",
        f"--project={project}",
        f"--zone={ZONE}",
        "--tunnel-through-iap",
        "--ssh-key-expire-after=1h",
        "--quiet",
        "--strict-host-key-checking=no",
        "--scp-flag=-oServerAliveInterval=30",
        "--scp-flag=-oServerAliveCountMax=20",
        *list(sources),
        destination,
    ]


def guest_command(seal: str, mode: str, phase: str = "") -> str:
    if HEX64_RE.fullmatch(seal) is None or seal in (PUBLIC_INSTALLER_PIN, TRACKING_2A_SEAL):
        raise SystemExit("seal")
    script = f"{GUEST_DIR}/enterprise-rows.sh"
    if mode == "plumb" and phase == "":
        return f"bash {script} {seal} plumb"
    if mode == "enterprise" and phase == "":
        return f"bash {script} {seal} enterprise"
    if mode == "descendant-b1" and phase in ("pre", "post"):
        return f"bash {script} {seal} descendant-b1 {phase}"
    if mode in {"2c-upgrade-rollback", "2d-crash-recovery"} and phase == "":
        return f"bash {script} {seal} {mode}"
    raise SystemExit("battery")


def reboot_ready(before: str, after: str) -> bool:
    return bool(before) and bool(after) and before != after and "\n" not in before and "\n" not in after


def deb_manifest(directory: Path) -> list[dict[str, str]]:
    debs = sorted(path for path in directory.glob("*.deb") if path.is_file())
    if not debs:
        raise SystemExit("offline_debs_missing")
    return [{"name": path.name, "sha256": sha256_file(path)} for path in debs]


def pack_debs(directory: Path, dest: Path) -> list[dict[str, str]]:
    rows = deb_manifest(directory)
    with tarfile.open(dest, "w") as tar:
        for row in rows:
            tar.add(directory / row["name"], arcname=row["name"])
    return rows


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(argv, check=False, capture_output=True, text=True)
    return completed


def _run_ok(argv: list[str], reason: str) -> subprocess.CompletedProcess[str]:
    completed = _run(argv)
    if completed.returncode != 0:
        detail = redact((completed.stderr or "") + (completed.stdout or ""))
        if detail:
            print(detail[-2000:], file=sys.stderr)
        raise SystemExit(reason)
    return completed


def _access_token() -> str:
    completed = _run_ok(["gcloud", "auth", "print-access-token"], "access_token")
    token = completed.stdout.strip()
    if not token or "\n" in token:
        raise SystemExit("access_token")
    return token


def _json_request(url: str, token: str, data: bytes | None, method: str) -> bytes:
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:500]
        print(redact(f"storage {exc.code} {body}"), file=sys.stderr)
        raise SystemExit("storage") from None


def content_range(offset: int, length: int, total: int) -> str:
    if offset < 0 or length < 1 or offset + length > total or total < 1:
        raise SystemExit("handoff_upload")
    return f"bytes {offset}-{offset + length - 1}/{total}"


def resumable_upload(
    bucket: str,
    object_name: str,
    path: Path,
    token: str,
    *,
    max_bytes: int = MAX_SEAL_BYTES,
) -> None:
    """Chunked resumable upload. A failed session is not replaced by a one-shot body."""
    if bucket != BUCKET or ".." in object_name or object_name.startswith("/"):
        raise SystemExit("object")
    total = path.stat().st_size
    if total <= 0 or total > max_bytes:
        raise SystemExit("handoff_upload")
    quoted = urllib.parse.quote(object_name, safe="")
    start = urllib.request.Request(
        f"https://storage.googleapis.com/upload/storage/v1/b/{bucket}/o?uploadType=resumable&name={quoted}",
        data=json.dumps({"name": object_name}).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "application/octet-stream",
            "X-Upload-Content-Length": str(total),
        },
    )
    try:
        with urllib.request.urlopen(start, timeout=60) as resp:
            session = resp.headers.get("Location")
    except urllib.error.HTTPError as exc:
        print(redact(f"resumable start {exc.code}"), file=sys.stderr)
        raise SystemExit("handoff_upload") from None
    if not session or not session.startswith("https://"):
        raise SystemExit("handoff_upload")
    chunk_size = 8 * 1024 * 1024
    offset = 0
    with path.open("rb") as handle:
        while offset < total:
            chunk = handle.read(chunk_size)
            if not chunk:
                raise SystemExit("handoff_upload")
            put = urllib.request.Request(
                session,
                data=chunk,
                method="PUT",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Length": str(len(chunk)),
                    "Content-Range": content_range(offset, len(chunk), total),
                },
            )
            try:
                with urllib.request.urlopen(put, timeout=180) as resp:
                    if resp.status not in (200, 201):
                        raise SystemExit("handoff_upload")
                return
            except urllib.error.HTTPError as exc:
                if exc.code != 308:
                    print(redact(f"resumable put {exc.code}"), file=sys.stderr)
                    raise SystemExit("handoff_upload") from None
                offset += len(chunk)
    raise SystemExit("handoff_upload")


def json_media_download(bucket: str, object_name: str, path: Path, token: str) -> None:
    if bucket != BUCKET or ".." in object_name or object_name.startswith("/"):
        raise SystemExit("object")
    quoted = urllib.parse.quote(object_name, safe="")
    url = f"https://storage.googleapis.com/storage/v1/b/{bucket}/o/{quoted}?alt=media"
    path.write_bytes(_json_request(url, token, None, "GET"))


def _json_delete(bucket: str, object_name: str, token: str, *, missing_ok: bool) -> None:
    quoted = urllib.parse.quote(object_name, safe="")
    url = f"https://storage.googleapis.com/storage/v1/b/{bucket}/o/{quoted}"
    req = urllib.request.Request(url, method="DELETE", headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=60):
            return
    except urllib.error.HTTPError as exc:
        if missing_ok and exc.code == 404:
            return
        print(redact(f"storage delete {exc.code}"), file=sys.stderr)
        raise SystemExit("storage_delete") from None


def upload_one(bucket: str, object_name: str, path: Path, *, max_bytes: int = MAX_SEAL_BYTES) -> str:
    dest = f"gs://{bucket}/{object_name}"
    completed = _run(["gcloud", "storage", "cp", str(path), dest])
    text = (completed.stderr or "") + (completed.stdout or "")
    kind = classify_gcloud_cp(completed.returncode, text)
    if kind == "uploaded":
        print(json.dumps({"object": object_name, "via": "gcloud"}))
        return "gcloud"
    if kind != "fallback_json":
        print(redact(text)[-2000:], file=sys.stderr)
        raise SystemExit("handoff_upload")
    print(json.dumps({"object": object_name, "via": "resumable", "reason": "storage.objects.get"}))
    token = _access_token()
    try:
        resumable_upload(bucket, object_name, path, token, max_bytes=max_bytes)
    finally:
        token = ""
    return "resumable"


def _missing_object(text: str) -> bool:
    """True only when gcloud says the object is gone.

    Strip gs:// URIs first. A run id such as 14042 contains the digits 404, and
    a 403 that quotes that URI must not count as a missing object. "command
    not found" is a failed delete, not a missing object.
    """
    without_uris = re.sub(r"gs://\S+", " ", text or "")
    lowered = without_uris.lower()
    if "command not found" in lowered or "no such file or directory" in lowered:
        return False
    if "matched no objects" in lowered:
        return True
    if re.search(r"(?<![0-9])404(?![0-9])", lowered):
        return True
    return "not found" in lowered


def delete_objects(names: Sequence[str], *, missing_ok: bool) -> None:
    uris = [f"gs://{BUCKET}/{name}" for name in names]
    completed = _run(["gcloud", "storage", "rm", *uris])
    text = (completed.stderr or "") + (completed.stdout or "")
    if completed.returncode == 0:
        return
    if missing_ok and _missing_object(text):
        return
    token = _access_token()
    try:
        for name in names:
            _json_delete(BUCKET, name, token, missing_ok=missing_ok)
    finally:
        token = ""


def _enabled(env: Mapping[str, str]) -> None:
    """The generic probe switch stays off. Offline delivery is its own switch."""
    _require_execute(env)
    capabilities = lab.load_capabilities()
    if capabilities.get("offline_delivery_enabled") is not True:
        raise SystemExit("offline_delivery_disabled")
    if capabilities.get("launch_enabled") is True:
        raise SystemExit("launch_enabled")


def _gate_ok(env: Mapping[str, str]) -> dict[str, Any]:
    try:
        gate = json.loads(env.get("GCP_LAB_GATE_JSON") or "")
    except json.JSONDecodeError:
        raise SystemExit("cost_gate") from None
    if not isinstance(gate, dict) or gate.get("expected_oop_usd") != "0" or gate.get("abort") is not False:
        raise SystemExit("cost_gate")
    return gate


def assert_bundle_command(env: Mapping[str, str]) -> int:
    directory = Path(env.get("W3_BUNDLE_DIR", ""))
    checked = assert_bundle_dir(directory, expected_seal(env))
    evidence = _evidence_dir(env)
    write_evidence(evidence / "bundle-digests.json", {**checked, "claim_cap": CLAIM_CAP})
    github_output("seal_sha256", checked["seal_sha256"])
    github_output("contract_sha256", checked["contract_sha256"])
    print(json.dumps(checked))
    return 0


def upload_handoff(env: Mapping[str, str]) -> int:
    _require_execute(env)
    project = require_lab_project(env.get("GCP_LAB_PROJECT", ""))
    names = list(object_names(env.get("GITHUB_RUN_ID", "")))
    directory = Path(env.get("W3_BUNDLE_DIR", ""))
    checked = assert_bundle_dir(directory, expected_seal(env))
    paths = [directory / "seal.oci.tar", directory / "contract.tar"]
    limits = [MAX_SEAL_BYTES, MAX_SEAL_BYTES]
    if brain_requested(env):
        brain_dir = Path(env.get("BRAIN_DIR", ""))
        try:
            rtbrain.verify_files(brain_dir)
        except ValueError:
            raise SystemExit("model_sha") from None
        brain_names = brain_object_names(env.get("GITHUB_RUN_ID", ""))
        names.extend(brain_names)
        paths.extend([brain_dir / rtbrain.MODEL_NAME, brain_dir / rtbrain.RUNTIME_NAME])
        limits.extend([rtbrain.MODEL_BYTES, rtbrain.RUNTIME_BYTES])
    via = [
        upload_one(BUCKET, name, path, max_bytes=limit)
        for name, path, limit in zip(names, paths, limits)
    ]
    payload = {
        "bucket": BUCKET,
        "claim_cap": CLAIM_CAP,
        "contract_sha256": checked["contract_sha256"],
        "objects": list(names),
        "project_id": project,
        "seal_sha256": checked["seal_sha256"],
        "trust_sha256": checked["trust_sha256"],
        "via": via,
    }
    write_evidence(_evidence_dir(env) / "handoff.json", payload)
    github_output("seal_sha256", checked["seal_sha256"])
    github_output("contract_sha256", checked["contract_sha256"])
    print(json.dumps({"bucket": BUCKET, "prefix": require_run_id(env.get("GITHUB_RUN_ID", ""))}))
    return 0


def stream_media_download(bucket: str, object_name: str, path: Path, token: str, exact: int) -> None:
    if bucket != BUCKET or ".." in object_name or object_name.startswith("/") or exact < 1:
        raise SystemExit("object")
    quoted = urllib.parse.quote(object_name, safe="")
    url = f"https://storage.googleapis.com/storage/v1/b/{bucket}/o/{quoted}?alt=media"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    written = 0
    try:
        with urllib.request.urlopen(request, timeout=180) as response, path.open("wb") as handle:
            while True:
                chunk = response.read(8 * 1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > exact:
                    raise SystemExit("handoff_download")
                handle.write(chunk)
    except urllib.error.HTTPError as exc:
        print(redact(f"brain download {exc.code}"), file=sys.stderr)
        raise SystemExit("handoff_download") from None
    if written != exact:
        raise SystemExit("handoff_download")


def download_exact(bucket: str, object_name: str, path: Path, exact: int) -> None:
    dest = f"gs://{bucket}/{object_name}"
    completed = _run(["gcloud", "storage", "cp", dest, str(path)])
    if completed.returncode == 0 and path.is_file() and path.stat().st_size == exact:
        return
    text = (completed.stderr or "") + (completed.stdout or "")
    if "403" not in text and "storage.objects.get" not in text and completed.returncode != 0:
        print(redact(text)[-2000:], file=sys.stderr)
        raise SystemExit("handoff_download")
    token = _access_token()
    try:
        stream_media_download(bucket, object_name, path, token, exact)
    finally:
        token = ""


def download_one(bucket: str, object_name: str, path: Path) -> None:
    dest = f"gs://{bucket}/{object_name}"
    completed = _run(["gcloud", "storage", "cp", dest, str(path)])
    if completed.returncode == 0 and path.is_file() and path.stat().st_size > 0:
        return
    text = (completed.stderr or "") + (completed.stdout or "")
    if classify_gcloud_cp(completed.returncode, text) != "fallback_json" and completed.returncode != 0:
        if "403" not in text and "storage.objects.get" not in text:
            print(redact(text)[-2000:], file=sys.stderr)
            raise SystemExit("handoff_download")
    token = _access_token()
    try:
        json_media_download(bucket, object_name, path, token)
    finally:
        token = ""


def download_handoff(env: Mapping[str, str]) -> int:
    _require_execute(env)
    require_lab_project(env.get("GCP_LAB_PROJECT", ""))
    expected_contract = env.get("EXPECTED_CONTRACT_SHA256", "").strip()
    if HEX64_RE.fullmatch(expected_contract) is None:
        raise SystemExit("contract_sha")
    directory = Path(env.get("W3_BUNDLE_DIR", ""))
    directory.mkdir(parents=True, exist_ok=True)
    names = object_names(env.get("GITHUB_RUN_ID", ""))
    seal_path = directory / "seal.oci.tar"
    contract_path = directory / "contract.tar"
    try:
        download_one(BUCKET, names[0], seal_path)
        download_one(BUCKET, names[1], contract_path)
        seal = verify_seal_file(seal_path, expected_seal(env))
        fetched = env.get("FETCHED_SEAL", "").strip().lower()
        if fetched and fetched != seal:
            raise SystemExit("seal")
        contract = verify_contract_trust(contract_path, TRUST_SHA256)
        if contract != expected_contract:
            raise SystemExit("contract_sha")
        payload = {
            "claim_cap": CLAIM_CAP,
            "contract_sha256": contract,
            "deleted": True,
            "seal_sha256": seal,
            "trust_sha256": TRUST_SHA256,
        }
        if brain_requested(env):
            brain_dir = Path(env.get("BRAIN_DIR", ""))
            brain_dir.mkdir(parents=True, exist_ok=True)
            brain_names = brain_object_names(env.get("GITHUB_RUN_ID", ""))
            download_exact(BUCKET, brain_names[0], brain_dir / rtbrain.MODEL_NAME, rtbrain.MODEL_BYTES)
            download_exact(BUCKET, brain_names[1], brain_dir / rtbrain.RUNTIME_NAME, rtbrain.RUNTIME_BYTES)
            try:
                rtbrain.verify_files(brain_dir)
            except ValueError:
                raise SystemExit("model_sha") from None
        write_evidence(_evidence_dir(env) / "download.json", payload)
        print(json.dumps(payload))
        return 0
    finally:
        delete_objects(handoff_objects(env), missing_ok=True)


def hash_debs(env: Mapping[str, str]) -> int:
    directory = Path(env.get("DEB_DIR", ""))
    rows = deb_manifest(directory)
    payload = {
        "claim_cap": CLAIM_CAP,
        "package_image": PACKAGE_IMAGE,
        "debs": rows,
        "snapshot": SNAPSHOT,
    }
    write_evidence(_evidence_dir(env) / "debs.json", payload)
    print(json.dumps({"count": len(rows), "snapshot": SNAPSHOT}))
    return 0


def _list_instances(project: str) -> list[dict[str, Any]]:
    completed = _run_ok(
        ["gcloud", "compute", "instances", "list", f"--project={project}", "--format=json"],
        "instances",
    )
    text = completed.stdout.strip()
    parsed = json.loads(text) if text else []
    if not isinstance(parsed, list):
        raise SystemExit("instances")
    return [item for item in parsed if isinstance(item, dict)]


def create_instance(env: Mapping[str, str]) -> int:
    _enabled(env)
    project = require_lab_project(env.get("GCP_LAB_PROJECT", ""))
    gate = _gate_ok(env)
    name = instance_name(env.get("GITHUB_RUN_ID", ""))
    instances = _list_instances(project)
    if lab.slot_occupied(instances):
        raise SystemExit("slot_occupied")
    now = int(env["GCP_LAB_NOW_EPOCH"]) if env.get("GCP_LAB_NOW_EPOCH") else int(time.time())
    minutes = lab.bounded_minutes(env.get("STOP_AFTER_MINUTES", "120"))
    if brain_requested(env):
        try:
            gross = rtbrain.assert_under_cap(rtbrain.BRAIN_MACHINE, minutes, rtbrain.BRAIN_DISK_GB)
        except ValueError:
            raise SystemExit("cost") from None
        machine = rtbrain.BRAIN_MACHINE
        disk = "30GB"
    else:
        gross = None
        machine = lab.MACHINE_TYPE
        disk = lab.BOOT_DISK_GB
    labels = offline_labels(now, minutes)
    plan = {
        "image_family": IMAGE_FAMILY,
        "image_project": IMAGE_PROJECT,
        "labels": labels,
        "name": name,
        "network": NETWORK,
        "project_id": project,
        "boot_disk_gb": disk,
        "machine_type": machine,
        "public_ip": False,
        "service_account": None,
        "subnet": SUBNET,
    }
    script_dir = Path(env.get("RUNNER_TEMP") or "/tmp")
    script_path = script_dir / "gcp-offline-startup.sh"
    script_path.write_text(offline_startup(minutes), encoding="utf-8")
    _run_ok(offline_create_argv(plan, str(script_path)), "create")
    payload = {
        "claim_cap": CLAIM_CAP,
        "expected_oop_usd": gate["expected_oop_usd"],
        "estimated_gross_usd": _money(gross) if gross is not None else _money(estimate_gross_usd(Decimal(minutes) / Decimal(60))),
        "image": f"{IMAGE_PROJECT}/{IMAGE_FAMILY}",
        "machine_type": machine,
        "name": name,
        "network": NETWORK,
        "project_id": project,
        "public_ip": False,
        "subnet": SUBNET,
        "zone": ZONE,
    }
    write_evidence(_evidence_dir(env) / "instance.json", payload)
    github_output("instance_name", name)
    print(json.dumps(payload))
    return 0


def _ssh(project: str, name: str, command: str) -> subprocess.CompletedProcess[str]:
    return _run(iap_ssh_argv(project, name, command))


def _wait_ssh(project: str, name: str, timeout_s: int) -> str:
    deadline = time.time() + timeout_s
    last = ""
    while time.time() < deadline:
        probe = _ssh(project, name, "cat /proc/sys/kernel/random/boot_id")
        boot = (probe.stdout or "").strip()
        if probe.returncode == 0 and boot and "\n" not in boot:
            return boot
        last = redact((probe.stderr or "")[-400:])
        time.sleep(10)
    print(last, file=sys.stderr)
    raise SystemExit("ssh")


def _wait_boot(project: str, name: str, before: str, timeout_s: int) -> str:
    """Wait until the guest boot id changes. SSH errors while it reboots are expected."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        probe = _ssh(project, name, "cat /proc/sys/kernel/random/boot_id")
        boot = (probe.stdout or "").strip()
        if probe.returncode == 0 and reboot_ready(before, boot):
            return boot
        time.sleep(10)
    return ""


def _scp_to(project: str, name: str, sources: Sequence[Path]) -> None:
    for path in sources:
        _run_ok(
            iap_scp_argv(project, [str(path)], f"{name}:{GUEST_DIR}/{path.name}"),
            "scp",
        )


def _scp_from(project: str, name: str, remote: str, dest: Path) -> bool:
    if not remote.startswith("/tmp/"):
        raise SystemExit("scp")
    completed = _run(iap_scp_argv(project, [f"{name}:{remote}"], str(dest)))
    return completed.returncode == 0 and dest.is_file()


def _load_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


RAW_GUEST_NAMES = (
    "gcp-plumb.json",
    "enterprise-rows.json",
    "kernel-facts.json",
    "descendant-b1.json",
    "redteam-rows.json",
)


def _remove_evidence_path(path: Path) -> None:
    """Remove a file, directory, or symlink without following the link.

    Walk iteratively. shutil.rmtree recurses in Python and raises RecursionError
    on a deep tree, which would skip the rest of the evidence cleanup.
    """
    try:
        pending = [path]
        ordered: list[Path] = []
        seen: set[str] = set()
        while pending:
            current = pending.pop()
            identity = str(current)
            if identity in seen:
                continue
            seen.add(identity)
            ordered.append(current)
            try:
                if current.is_symlink() or not current.is_dir():
                    continue
                pending.extend(current.iterdir())
            except OSError:
                continue
        for current in reversed(ordered):
            try:
                if current.is_symlink() or not current.is_dir():
                    current.unlink(missing_ok=True)
                else:
                    current.rmdir()
            except OSError:
                continue
    except Exception:
        return


def drop_guest_copies(directory: Path) -> None:
    """Guest files are folded into the redacted evidence JSON. The raw copies
    must not sit in the directory that becomes a public artifact."""
    for name in RAW_GUEST_NAMES:
        _remove_evidence_path(directory / name)
        _remove_evidence_path(directory / f"{name}.sha256")


def prune_evidence(directory: Path) -> list[str]:
    """Leave only allowlisted evidence files, rewritten through the key allowlist."""
    drop_guest_copies(directory)
    kept: list[str] = []
    try:
        for path in list(directory.iterdir()):
            try:
                if path.is_symlink() or path.is_dir() or not path.is_file():
                    _remove_evidence_path(path)
                    continue
                stem = path.name[:-7] if path.name.endswith(".sha256") else path.name
                if stem not in EVIDENCE_FILES:
                    _remove_evidence_path(path)
                    continue
                if path.suffix != ".json":
                    continue
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
                    _remove_evidence_path(path)
                    _remove_evidence_path(path.with_name(path.name + ".sha256"))
                    continue
                if not isinstance(payload, dict):
                    _remove_evidence_path(path)
                    _remove_evidence_path(path.with_name(path.name + ".sha256"))
                    continue
                if path.name == "redteam-packet.json":
                    redteam_packet.write_packet(path, payload)
                    kept.append(path.name)
                    continue
                write_evidence(path, payload)
                kept.append(path.name)
            except (Exception, SystemExit):
                _remove_evidence_path(path)
                _remove_evidence_path(path.with_name(path.name + ".sha256"))
    finally:
        for path in list(directory.iterdir()):
            if path.is_symlink() or path.is_dir():
                _remove_evidence_path(path)
                continue
            if path.name.endswith(".sha256"):
                if not (directory / path.name[:-7]).is_file():
                    _remove_evidence_path(path)
                continue
            if path.name not in EVIDENCE_FILES:
                _remove_evidence_path(path)
    return sorted(kept)


def _stored_guest(path: Path, fallback: str) -> Any:
    if path.is_file():
        parsed = _load_json_file(path)
        if parsed is not None:
            return parsed
        return redact(path.read_text(encoding="utf-8", errors="replace")[-20000:])
    return redact(fallback[-8000:])


def _phase_scripts(env: Mapping[str, str]) -> tuple[Path, Path]:
    host = Path(env.get("PHASE2_HOST", "scripts/aws/lab-guests/phase2_host.py"))
    grade = Path(env.get("PHASE2_GRADE", "scripts/aws/lab-guests/phase2_grade.py"))
    if not host.is_file() or not grade.is_file():
        raise SystemExit("phase2")
    return host, grade


def _last_object(text: str) -> dict[str, Any] | None:
    start = text.rfind("{")
    while start >= 0:
        try:
            parsed = json.loads(text[start:])
        except json.JSONDecodeError:
            start = text.rfind("{", 0, start)
            continue
        if isinstance(parsed, dict):
            return parsed
        start = text.rfind("{", 0, start)
    return None


def _ndjson_pids(body: Mapping[str, Any] | None) -> list[int]:
    if not isinstance(body, dict):
        return []
    raw = body.get("ndjson_denied_pids")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, int) and not isinstance(item, bool) and item > 0][:8]


def _sample_held(sample: Mapping[str, Any] | None) -> bool:
    """Errno 13 on the signed ceiling, with a DENIED row for that same pid and anchor."""
    if not isinstance(sample, dict) or sample.get("file_errno") != 13 or sample.get("path") != CEILING_PATH:
        return False
    pid = sample.get("pid")
    anchor = sample.get("lineage_anchor")
    event = sample.get("deny_event")
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return False
    if isinstance(anchor, bool) or not isinstance(anchor, int) or anchor <= 0:
        return False
    if not isinstance(event, dict):
        return False
    return event.get("pid") == pid and event.get("lineage_anchor") == anchor and event.get("path") == CEILING_PATH


def _loader_word(mode: str, body: Mapping[str, Any] | None) -> str:
    """Held only when the measured probe itself is denied. An older pid does not count."""
    if not isinstance(body, dict):
        return "fail"
    if mode == "2d-crash-recovery":
        unenrolled = body.get("unenrolled_after")
        if not isinstance(unenrolled, dict) or unenrolled.get("file_errno") != 0:
            return "fail"
        if _sample_held(body.get("while_loader_up")) and _sample_held(body.get("enrolled_after")):
            return "held"
        return "fail"
    if mode == "2c-upgrade-rollback":
        if _sample_held(body.get("deny_before")) and _sample_held(body.get("deny_after")):
            return "held"
        return "fail"
    return "fail"


def _event_anchor(event: Mapping[str, Any] | None) -> tuple[int, int]:
    if not isinstance(event, dict):
        return 0, 0
    pid = event.get("Pid")
    if pid is None:
        pid = event.get("pid")
    anchor = event.get("lineage_anchor")
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        pid = 0
    if isinstance(anchor, bool) or not isinstance(anchor, int) or anchor <= 0:
        anchor = 0
    attempted = event.get("PathAttempted") or event.get("Payload") or event.get("path")
    matched = event.get("PolicyRuleMatched")
    denied = event.get("ActionTaken") == "DENIED" or (
        isinstance(matched, str) and matched.startswith("ENFORCE_DENIED:")
    )
    if not denied or attempted != CEILING_PATH:
        return 0, 0
    return pid, anchor


def _enterprise_hold(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    """A revoke deny with pid and anchor is a hold even when the guest script exits 1."""
    revoke = raw.get("revoke") if isinstance(raw, dict) else None
    probe = revoke.get("probe") if isinstance(revoke, dict) else None
    event = revoke.get("block_event") if isinstance(revoke, dict) else None
    errno = probe.get("nobody_errno") if isinstance(probe, dict) else -1
    if not isinstance(errno, int) or isinstance(errno, bool):
        errno = -1
    pid, anchor = _event_anchor(event if isinstance(event, dict) else None)
    return {
        "errno": errno,
        "hold": errno == 13 and pid > 0 and anchor > 0,
        "lineage_anchor": anchor,
        "path": CEILING_PATH,
        "pid": pid,
        "uid": 65534,
    }


def _enterprise_fail_reasons(raw: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(raw, dict):
        return ["guest_json_missing"]
    reasons: list[str] = []
    grant = raw.get("grant_loader") if isinstance(raw.get("grant_loader"), dict) else {}
    if grant.get("rc") != 0:
        reasons.append("grant_loader")
    if grant.get("audit") is not True:
        reasons.append("grant_audit")
    if grant.get("path_observe") is not True:
        reasons.append("grant_observe")
    probe = raw.get("grant_probe") if isinstance(raw.get("grant_probe"), dict) else {}
    if probe.get("nobody_errno") != 0:
        reasons.append("grant_errno")
    unchanged = raw.get("unchanged") if isinstance(raw.get("unchanged"), dict) else {}
    if unchanged.get("conflict_reason") != "VERSION_CONFLICT":
        reasons.append("conflict_reason")
    if unchanged.get("generation") != unchanged.get("generation_before"):
        reasons.append("generation_moved")
    freeze = raw.get("freeze") if isinstance(raw.get("freeze"), dict) else {}
    if freeze.get("widen_reason") != "FROZEN":
        reasons.append("freeze_reason")
    unreachable = raw.get("unreachable") if isinstance(raw.get("unreachable"), dict) else {}
    if unreachable.get("reason") != "ENTERPRISE_UNREACHABLE":
        reasons.append("unreachable_reason")
    revoke = raw.get("revoke") if isinstance(raw.get("revoke"), dict) else {}
    revoke_probe = revoke.get("probe") if isinstance(revoke.get("probe"), dict) else {}
    if revoke_probe.get("nobody_errno") != 13:
        reasons.append("revoke_errno")
    removal = raw.get("removal") if isinstance(raw.get("removal"), dict) else {}
    if removal.get("verified_removed") is not True:
        reasons.append("programs_not_removed")
    return reasons


def _case_capture(item: Mapping[str, Any]) -> dict[str, Any]:
    event = item.get("file_event") if isinstance(item.get("file_event"), dict) else {}
    anchor = event.get("lineage_anchor") if isinstance(event, dict) else 0
    if isinstance(anchor, bool) or not isinstance(anchor, int):
        anchor = 0
    return {
        "expect_deny": item.get("expect_deny") is True,
        "file_errno": item.get("file_errno") if isinstance(item.get("file_errno"), int) else -1,
        "lineage_anchor": anchor,
        "name": item.get("name") if isinstance(item.get("name"), str) else "",
        "pass": item.get("pass") is True,
        "path": CEILING_PATH,
        "pid": item.get("pid") if isinstance(item.get("pid"), int) else 0,
    }


def _descendant_cases(raw: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(raw, dict):
        return []
    body = raw.get("pre") if isinstance(raw.get("pre"), dict) else raw
    cases = body.get("cases") if isinstance(body, dict) else None
    if not isinstance(cases, list):
        post = raw.get("post") if isinstance(raw.get("post"), dict) else None
        cases = post.get("cases") if isinstance(post, dict) else None
    if not isinstance(cases, list):
        return []
    return [_case_capture(item) for item in cases if isinstance(item, dict)]


def _py_rc(text: str) -> int | None:
    match = re.search(r"PY_RC=(\d+)", text)
    if match is None:
        return None
    return int(match.group(1))


def _collect_denied_pids(payload: Any, found: list[int] | None = None) -> list[int]:
    if found is None:
        found = []
    if isinstance(payload, dict):
        pid = payload.get("Pid")
        if payload.get("ActionTaken") == "DENIED" and isinstance(pid, int) and not isinstance(pid, bool) and pid > 0 and pid not in found:
            found.append(pid)
        for value in payload.values():
            if len(found) >= 8:
                break
            _collect_denied_pids(value, found)
    elif isinstance(payload, list):
        for item in payload:
            if len(found) >= 8:
                break
            _collect_denied_pids(item, found)
    return found


def _probe_case(name: str, result: str, sample: Mapping[str, Any] | None) -> dict[str, Any]:
    errno = sample.get("file_errno") if isinstance(sample, dict) else -1
    pid = sample.get("pid") if isinstance(sample, dict) else 0
    anchor = sample.get("lineage_anchor") if isinstance(sample, dict) else 0
    if not isinstance(errno, int) or isinstance(errno, bool):
        errno = -1
    if not isinstance(pid, int) or isinstance(pid, bool):
        pid = 0
    if not isinstance(anchor, int) or isinstance(anchor, bool):
        anchor = 0
    return _case_row(name, result, errno, [pid] if pid > 0 else [], anchor)


def _loader_capture(name: str, case: Mapping[str, Any]) -> dict[str, Any]:
    body = case.get("body") if isinstance(case.get("body"), dict) else {}
    if name == "loader-kill":
        sample = body.get("enrolled_after") if isinstance(body.get("enrolled_after"), dict) else {}
        before = body.get("while_loader_up") if isinstance(body.get("while_loader_up"), dict) else {}
    else:
        sample = body.get("deny_after") if isinstance(body.get("deny_after"), dict) else {}
        before = body.get("deny_before") if isinstance(body.get("deny_before"), dict) else {}
    return {
        "cases": [
            _case_capture(
                {
                    "expect_deny": True,
                    "file_errno": before.get("file_errno"),
                    "file_event": before.get("deny_event"),
                    "name": "before",
                    "pass": _sample_held(before),
                    "pid": before.get("pid"),
                }
            ),
            _case_capture(
                {
                    "expect_deny": True,
                    "file_errno": sample.get("file_errno"),
                    "file_event": sample.get("deny_event"),
                    "name": "after",
                    "pass": _sample_held(sample),
                    "pid": sample.get("pid"),
                }
            ),
        ],
        "enforcement_drop": body.get("enforcement_drop") is True,
        "errno": sample.get("file_errno") if isinstance(sample.get("file_errno"), int) else -1,
        "guest_rc": case.get("rc") if isinstance(case.get("rc"), int) else -1,
        "hold": case.get("word") == "held",
        "lineage_anchor": sample.get("lineage_anchor") if isinstance(sample.get("lineage_anchor"), int) else 0,
        "name": name,
        "path": CEILING_PATH,
        "pid": sample.get("pid") if isinstance(sample.get("pid"), int) else 0,
        "uid": 65534,
    }


def _case_row(name: str, result: str, errno: int, pids: list[int], anchor: int = 0) -> dict[str, Any]:
    return {
        "case": name,
        "denied_rows": len(pids),
        "deny_pid": pids[-1] if pids else 0,
        "errno": errno if -1 <= errno <= 255 else -1,
        "lineage_anchor": anchor if isinstance(anchor, int) and anchor > 0 else 0,
        "path": CEILING_PATH,
        "result": result,
    }


def _pull_guest_json(project: str, name: str) -> dict[str, Any] | None:
    local = Path(tempfile.mkdtemp(prefix="vantio-guest-")) / "rows.json"
    try:
        if not _scp_from(project, name, "/tmp/enterprise-pe-rows.json", local):
            return None
        parsed = _load_json_file(local)
        return parsed if isinstance(parsed, dict) else None
    finally:
        shutil.rmtree(local.parent, ignore_errors=True)


def _loader_case(project: str, name: str, seal: str, mode: str) -> dict[str, Any]:
    completed = _ssh(project, name, guest_command(seal, mode))
    text = (completed.stdout or "") + (completed.stderr or "")
    body = _pull_guest_json(project, name)
    if body is None:
        parsed = _last_object(text)
        body = parsed if isinstance(parsed, dict) else {}
    word = _loader_word(mode, body)
    sample = body.get("enrolled_after") if mode == "2d-crash-recovery" else body.get("deny_after")
    pid = sample.get("pid") if isinstance(sample, dict) else 0
    anchor = sample.get("lineage_anchor") if isinstance(sample, dict) else 0
    print(
        json.dumps(
            {
                "anchor": anchor if isinstance(anchor, int) else 0,
                "deny_pid": pid if isinstance(pid, int) else 0,
                "enforcement_drop": body.get("enforcement_drop") is True,
                "mode": mode,
                "rc": completed.returncode,
                "result": word,
            }
        ),
        flush=True,
    )
    if completed.returncode != 0 or word != "held":
        print(redact(text)[-1500:], file=sys.stderr)
    return {"body": body, "rc": completed.returncode, "word": word}


def _stage_payload(env: Mapping[str, str], dest: Path) -> list[dict[str, str]]:
    bundle = Path(env.get("W3_BUNDLE_DIR", ""))
    deb_dir = Path(env.get("DEB_DIR", ""))
    guest = Path(env.get("GUEST_SCRIPT", ""))
    descendant = Path(env.get("DESCENDANT_SCRIPT", ""))
    checked = assert_bundle_dir(bundle, expected_seal(env))
    if checked["contract_sha256"] != env.get("EXPECTED_CONTRACT_SHA256", "").strip():
        raise SystemExit("contract_sha")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    shutil.copy2(bundle / "seal.oci.tar", dest / "seal.oci.tar")
    shutil.copy2(bundle / "contract.tar", dest / "contract.tar")
    script_dest = dest / "enterprise-rows.sh"
    shutil.copy2(guest, script_dest)
    script_dest.chmod(0o755)
    shutil.copy2(descendant, dest / "descendant_b1.py")
    host, grade = _phase_scripts(env)
    shutil.copy2(host, dest / "phase2_host.py")
    shutil.copy2(grade, dest / "phase2_grade.py")
    rows = pack_debs(deb_dir, dest / "debs.tar")
    bundle = deb_dir / "ca-certificates.crt"
    if not bundle.is_file() or bundle.stat().st_size < 1000:
        raise SystemExit("ca_bundle")
    shutil.copy2(bundle, dest / "ca-certificates.crt")
    return rows


def _run_guest(project: str, name: str, command: str, reason: str) -> subprocess.CompletedProcess[str]:
    completed = _ssh(project, name, command)
    if completed.returncode != 0:
        detail = redact((completed.stdout or "") + (completed.stderr or ""))
        print(detail[-4000:], file=sys.stderr)
        raise SystemExit(reason)
    return completed


def _wait_until_running(project: str, name: str) -> None:
    deadline = time.time() + SSH_WAIT_SECONDS
    status = ""
    while time.time() < deadline:
        described = _run(
            [
                "gcloud",
                "compute",
                "instances",
                "describe",
                name,
                f"--project={project}",
                f"--zone={ZONE}",
                "--format=value(status)",
            ]
        )
        status = (described.stdout or "").strip()
        if described.returncode == 0 and status == "RUNNING":
            break
        time.sleep(5)
    if status != "RUNNING":
        raise SystemExit("instance_status")
    _wait_ssh(project, name, SSH_WAIT_SECONDS)


def plumb_guest(env: Mapping[str, str]) -> int:
    """Copy the bundle over IAP and re-check the digest. Does not run batteries."""
    _enabled(env)
    if batteries_requested(env):
        raise SystemExit("batteries")
    project = require_lab_project(env.get("GCP_LAB_PROJECT", ""))
    _gate_ok(env)
    seal = expected_seal(env)
    name = instance_name(env.get("GITHUB_RUN_ID", ""))
    evidence = _evidence_dir(env)
    bundle = Path(env.get("W3_BUNDLE_DIR", ""))
    guest = Path(env.get("GUEST_SCRIPT", ""))
    checked = assert_bundle_dir(bundle, seal)
    if checked["contract_sha256"] != env.get("EXPECTED_CONTRACT_SHA256", "").strip():
        raise SystemExit("contract_sha")
    payload_dir = Path(env.get("RUNNER_TEMP") or "/tmp") / "gcp-guest-payload"
    if payload_dir.exists():
        shutil.rmtree(payload_dir)
    payload_dir.mkdir(parents=True)
    try:
        shutil.copy2(bundle / "seal.oci.tar", payload_dir / "seal.oci.tar")
        shutil.copy2(bundle / "contract.tar", payload_dir / "contract.tar")
        script_dest = payload_dir / "enterprise-rows.sh"
        shutil.copy2(guest, script_dest)
        script_dest.chmod(0o755)
        _wait_until_running(project, name)
        made = _ssh(project, name, f"rm -rf {GUEST_DIR} && mkdir -p {GUEST_DIR}")
        if made.returncode != 0:
            raise SystemExit("ssh")
        _scp_to(
            project,
            name,
            [payload_dir / "seal.oci.tar", payload_dir / "contract.tar", script_dest],
        )
        for local_name in ("seal.oci.tar", "contract.tar"):
            (payload_dir / local_name).unlink(missing_ok=True)
        ran = _ssh(project, name, guest_command(seal, "plumb"))
        if ran.returncode != 0:
            print(redact((ran.stdout or "") + (ran.stderr or ""))[-4000:], file=sys.stderr)
            raise SystemExit("plumb")
        local = evidence / "gcp-plumb.json"
        if not _scp_from(project, name, "/tmp/gcp-plumb.json", local):
            raise SystemExit("plumb")
        body = _load_json_file(local)
        if not isinstance(body, dict) or body.get("seal_sha256") != seal or body.get("batteries") is not False:
            raise SystemExit("seal")
        result = {
            "batteries": False,
            "claim_cap": CLAIM_CAP,
            "cloud": "gcp",
            "mode": "plumb",
            "network": NETWORK,
            "public_ip": False,
            "seal_sha256": seal,
            "status": "PLUMB_DIGEST_MATCH",
            "trust_sha256": TRUST_SHA256,
            "vm_digest_match": True,
        }
        write_evidence(evidence / "gcp-lab-rows.json", result)
        print(json.dumps(result))
        return 0
    finally:
        drop_guest_copies(evidence)
        if payload_dir.exists():
            shutil.rmtree(payload_dir, ignore_errors=True)
        remove_os_login_key()


def _kernel_flags(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    flags: dict[str, Any] = {}
    for source, dest in (("btf", "kernel_btf"), ("bpffs", "kernel_bpffs"), ("cgroup_v2", "kernel_cgroup_v2")):
        if isinstance(payload.get(source), bool):
            flags[dest] = payload[source]
    lsm = payload.get("lsm")
    if isinstance(lsm, str) and re.fullmatch(r"[a-z0-9,]{0,80}", lsm):
        flags["kernel_lsm"] = lsm
    return flags


def _finish_repeat(
    summary: dict[str, Any],
    *,
    enterprise_rc: int,
    descendant_rc: int,
    observed: bool,
    repeat: int,
    rows: dict[str, Any] | None,
) -> dict[str, Any]:
    summary.update(
        {
            "battery": "descendant-b1",
            "descendant_rc": descendant_rc,
            "enterprise_rc": enterprise_rc,
            "reboot_observed": observed,
            "repeat": repeat,
            "seal_checked": True,
        }
    )
    if rows:
        summary["rows"] = rows
    return summary


def _run_one_battery(
    project: str,
    name: str,
    seal: str,
    evidence: Path,
    repeat: int,
    captures: list[dict[str, Any]],
) -> dict[str, Any]:
    """Enterprise grant/revoke, then descendant-b1. A failed enterprise row does not skip the rest."""
    enterprise = _ssh(project, name, guest_command(seal, "enterprise"))
    kernel_path = evidence / "kernel-facts.json"
    raw = _pull_guest_json(project, name)
    got_kernel = _scp_from(project, name, "/tmp/gcp-kernel-facts.json", kernel_path)
    if enterprise.returncode != 0:
        print(redact((enterprise.stdout or "") + (enterprise.stderr or ""))[-1500:], file=sys.stderr)
    hold = _enterprise_hold(raw if isinstance(raw, dict) else None)
    ledger = raw.get("z_ledger") if isinstance(raw, dict) else None
    summary: dict[str, Any] = {
        "denied_rows": 1 if hold["hold"] else 0,
        "deny_hold": hold["hold"],
        "deny_pid": hold["pid"],
        "errno": hold["errno"],
        "lineage_anchor": hold["lineage_anchor"],
        "path": CEILING_PATH,
    }
    captures.append(
        {
            "errno": hold["errno"],
            "fail_reasons": _enterprise_fail_reasons(raw if isinstance(raw, dict) else None)
            if enterprise.returncode != 0
            else [],
            "guest_rc": enterprise.returncode,
            "hold": hold["hold"],
            "lineage_anchor": hold["lineage_anchor"],
            "name": f"enterprise-{repeat}",
            "path": CEILING_PATH,
            "pid": hold["pid"],
            "uid": 65534,
        }
    )
    if isinstance(ledger, dict) and isinstance(ledger.get("bpftool_rc"), int):
        summary["bpftool_rc"] = ledger["bpftool_rc"]
    if isinstance(ledger, dict) and isinstance(ledger.get("loader_running"), bool):
        summary["loader_running"] = ledger["loader_running"]
    if got_kernel and kernel_path.is_file():
        summary.update(_kernel_flags(_load_json_file(kernel_path)))
    grant_probe = raw.get("grant_probe") if isinstance(raw, dict) else {}
    grant_errno = grant_probe.get("nobody_errno") if isinstance(grant_probe, dict) else -1
    if not isinstance(grant_errno, int) or isinstance(grant_errno, bool):
        grant_errno = -1
    enterprise_rows = allow_battery(
        {
            "grant": {
                "probe": {
                    "nobody_errno": grant_errno,
                    "result": "open_ok" if grant_errno == 0 else "open_error",
                }
            },
            "image": IMAGE_NAME,
            "revoke": {
                "probe": {
                    "nobody_errno": hold["errno"],
                    "result": "open_error" if hold["errno"] == 13 else "open_ok",
                }
            },
        }
    )
    before = _wait_ssh(project, name, SSH_WAIT_SECONDS)
    pre = _ssh(project, name, guest_command(seal, "descendant-b1", "pre"))
    pre_text = redact((pre.stdout or "") + (pre.stderr or ""))
    after = _wait_boot(project, name, before, REBOOT_WAIT_SECONDS)
    observed = reboot_ready(before, after)
    pre_guest = _pull_guest_json(project, name)
    pre_cases = _descendant_cases(pre_guest)
    failed = []
    if isinstance(pre_guest, dict):
        body = pre_guest.get("pre") if isinstance(pre_guest.get("pre"), dict) else pre_guest
        if isinstance(body, dict) and isinstance(body.get("failed_cases"), list):
            failed = [item for item in body["failed_cases"] if isinstance(item, str)]
        not_run = body.get("not_run") if isinstance(body, dict) else []
    pre_rc = _py_rc(pre_text)
    captures.append(
        {
            "cases": pre_cases,
            "failed_cases": failed,
            "not_run": [item for item in not_run if isinstance(item, str)] if isinstance(not_run, list) else [],
            "guest_rc": pre_rc if pre_rc is not None else pre.returncode,
            "hold": bool(pre_cases) and all(item["pass"] for item in pre_cases if item["expect_deny"]),
            "name": f"descendant-pre-{repeat}",
            "path": CEILING_PATH,
        }
    )
    if not observed:
        print(pre_text[-1500:], file=sys.stderr)
        return _finish_repeat(
            summary,
            enterprise_rc=enterprise.returncode,
            descendant_rc=pre_rc if pre_rc is not None else pre.returncode,
            observed=False,
            repeat=repeat,
            rows=enterprise_rows,
        )
    post = _ssh(project, name, guest_command(seal, "descendant-b1", "post"))
    post_text = (post.stdout or "") + (post.stderr or "")
    if post.returncode != 0:
        print(redact(post_text)[-1500:], file=sys.stderr)
    guest = _pull_guest_json(project, name)
    post_cases = _descendant_cases({"post": guest.get("post")} if isinstance(guest, dict) else None)
    if isinstance(guest, dict):
        nested = allow_battery(guest) or {}
        summary.update(nested)
        held_case = next((item for item in post_cases if item["expect_deny"] and item["pass"] and item["pid"]), None)
        if held_case is None:
            held_case = next((item for item in pre_cases if item["expect_deny"] and item["pass"] and item["pid"]), None)
        if held_case:
            summary["desc_deny_pid"] = held_case["pid"]
            summary["desc_lineage_anchor"] = held_case["lineage_anchor"]
            summary["desc_denied_rows"] = 1
    captures.append(
        {
            "cases": post_cases,
            "failed_cases": [
                item["name"] for item in post_cases if item["expect_deny"] and not item["pass"]
            ],
            "guest_rc": _py_rc(post_text) if _py_rc(post_text) is not None else post.returncode,
            "hold": summary.get("b1_pass") is True,
            "lineage_anchor": summary.get("desc_lineage_anchor") or 0,
            "name": f"descendant-post-{repeat}",
            "path": CEILING_PATH,
            "pid": summary.get("desc_deny_pid") or 0,
        }
    )
    post_rc = _py_rc(post_text)
    return _finish_repeat(
        summary,
        enterprise_rc=enterprise.returncode,
        descendant_rc=post_rc if post_rc is not None else post.returncode,
        observed=observed,
        repeat=repeat,
        rows=enterprise_rows,
    )


def run_batteries(env: Mapping[str, str]) -> int:
    _enabled(env)
    project = require_lab_project(env.get("GCP_LAB_PROJECT", ""))
    _gate_ok(env)
    if not batteries_requested(env):
        raise SystemExit("batteries")
    name = instance_name(env.get("GITHUB_RUN_ID", ""))
    seal = refuse_batteries(env)
    evidence = _evidence_dir(env)
    payload_dir = Path(env.get("RUNNER_TEMP") or "/tmp") / "gcp-guest-payload"
    debs = _stage_payload(env, payload_dir)
    captures: list[dict[str, Any]] = []
    try:
        _wait_until_running(project, name)
        made = _ssh(project, name, f"rm -rf {GUEST_DIR} && mkdir -p {GUEST_DIR}")
        if made.returncode != 0:
            raise SystemExit("ssh")
        _scp_to(
            project,
            name,
            [
                payload_dir / "seal.oci.tar",
                payload_dir / "contract.tar",
                payload_dir / "enterprise-rows.sh",
                payload_dir / "descendant_b1.py",
                payload_dir / "phase2_host.py",
                payload_dir / "phase2_grade.py",
                payload_dir / "debs.tar",
                payload_dir / "ca-certificates.crt",
            ],
        )
        for local_name in ("seal.oci.tar", "contract.tar"):
            (payload_dir / local_name).unlink(missing_ok=True)
        repeats: list[dict[str, Any]] = []
        schedule = battery_schedule(BATTERY_REPEATS)
        if schedule != ["enterprise", "descendant-b1"] * BATTERY_REPEATS:
            raise SystemExit("repeats")
        for index in range(BATTERY_REPEATS):
            if index:
                back = _wait_boot(project, name, "down", REBOOT_WAIT_SECONDS)
                if not back:
                    captures.append(
                        {
                            "fail_reasons": ["host_down_after_reboot"],
                            "guest_rc": -1,
                            "hold": False,
                            "name": f"repeat-{index + 1}",
                        }
                    )
                    break
            repeat = _run_one_battery(project, name, seal, evidence, index + 1, captures)
            repeats.append(repeat)
        passed = full_set_passes(repeats)
        kill = _loader_case(project, name, seal, "2d-crash-recovery")
        restart = _loader_case(project, name, seal, "2c-upgrade-rollback")
        loader_kill = kill["word"]
        loader_restart = restart["word"]
        captures.extend(
            [
                _loader_capture("loader-kill", kill),
                _loader_capture("loader-restart", restart),
            ]
        )
        cases: list[dict[str, Any]] = []
        for repeat in repeats:
            errno = repeat.get("errno")
            pid = repeat.get("deny_pid")
            anchor = repeat.get("lineage_anchor")
            cases.append(
                _case_row(
                    "enterprise",
                    "held" if repeat.get("deny_hold") is True else "fail",
                    errno if isinstance(errno, int) else -1,
                    [pid] if isinstance(pid, int) and pid > 0 else [],
                    anchor if isinstance(anchor, int) else 0,
                )
            )
            desc_pid = repeat.get("desc_deny_pid")
            desc_anchor = repeat.get("desc_lineage_anchor")
            desc_errno = -1
            cases.append(
                _case_row(
                    "descendant-b1",
                    "held" if repeat.get("b1_pass") is True and isinstance(desc_pid, int) and desc_pid > 0 else "fail",
                    desc_errno,
                    [desc_pid] if isinstance(desc_pid, int) and desc_pid > 0 else [],
                    desc_anchor if isinstance(desc_anchor, int) else 0,
                )
            )
        kill_sample = kill["body"].get("enrolled_after") if isinstance(kill["body"], dict) else None
        cases.append(_probe_case("loader-kill", loader_kill, kill_sample if isinstance(kill_sample, dict) else None))
        restart_sample = restart["body"].get("deny_after") if isinstance(restart["body"], dict) else None
        cases.append(
            _probe_case("loader-restart", loader_restart, restart_sample if isinstance(restart_sample, dict) else None)
        )
        result = {
            "batteries": True,
            "captures": captures,
            "cases": cases,
            "claim_cap": CLAIM_CAP,
            "cloud": "gcp",
            "package_image": PACKAGE_IMAGE,
            "loader_kill": loader_kill,
            "loader_restart": loader_restart,
            "debs": debs,
            "full_set": passed,
            "image": IMAGE_NAME,
            "mode": "enterprise",
            "network": NETWORK,
            "public_ip": False,
            "repeats": repeats,
            "seal_sha256": seal,
            "snapshot": SNAPSHOT,
            "subnet": SUBNET,
            "trust_sha256": TRUST_SHA256,
        }
        print(json.dumps({"cases": cases, "loader_kill": loader_kill, "loader_restart": loader_restart}), flush=True)
        write_evidence(evidence / "guest-evidence.json", {"captures": captures, "claim_cap": CLAIM_CAP})
        if not passed or loader_kill != "held" or loader_restart != "held":
            write_evidence(evidence / "gcp-lab-rows.json", result)
            raise SystemExit("battery" if not passed else "loader")
        write_evidence(evidence / "gcp-lab-rows.json", result)
        print(json.dumps({"full_set": True, "repeats": BATTERY_REPEATS, "claim_cap": CLAIM_CAP}))
        return 0
    finally:
        if captures:
            try:
                write_evidence(
                    evidence / "guest-evidence.json",
                    {"captures": captures, "claim_cap": CLAIM_CAP},
                )
            except SystemExit:
                pass
        drop_guest_copies(evidence)
        if payload_dir.exists():
            shutil.rmtree(payload_dir, ignore_errors=True)
        remove_os_login_key()


def self_service_requested(env: Mapping[str, str]) -> bool:
    raw = env.get("SELF_SERVICE", "false").strip().lower()
    if raw not in ("true", "false"):
        raise SystemExit("self_service")
    return raw == "true"


def _self_service_rows(body: object) -> list[dict[str, str]]:
    if not isinstance(body, dict):
        return []
    rows: list[dict[str, str]] = []
    installer = body.get("installer")
    if isinstance(installer, list):
        for item in installer:
            if not isinstance(item, dict):
                continue
            reason = item.get("reason")
            rows.append(
                {
                    "phase": str(item.get("phase") or ""),
                    "protection": str(item.get("protection") or ""),
                    "reason": reason if isinstance(reason, str) else "",
                    "state": str(item.get("state") or ""),
                }
            )
    enrollment = body.get("enrollment")
    if isinstance(enrollment, dict):
        reason = enrollment.get("reason")
        rows.append(
            {
                "phase": "enrollment",
                "protection": "NONE",
                "reason": reason if isinstance(reason, str) else "",
                "state": str(enrollment.get("status") or "GAP"),
            }
        )
    return rows


def run_self_service(env: Mapping[str, str]) -> int:
    """Copy the staged installer and run it. Does not run enterprise rows."""
    _require_execute(env)
    if batteries_requested(env) or not self_service_requested(env):
        raise SystemExit("self_service")
    project = require_lab_project(env.get("GCP_LAB_PROJECT", ""))
    seal = expected_seal(env)
    staged = Path(env.get("W3_SELF_SERVICE_DIR", ""))
    tar_path = staged / "self-service.tar"
    if not tar_path.is_file() or not (staged / "lab-artifact-trust.json").is_file():
        raise SystemExit("self_service_layout")
    name = instance_name(env.get("GITHUB_RUN_ID", ""))
    _wait_until_running(project, name)
    _wait_ssh(project, name, SSH_WAIT_SECONDS)
    made = _ssh(project, name, f"rm -rf {GUEST_DIR} && mkdir -p {GUEST_DIR}")
    if made.returncode != 0:
        raise SystemExit("ssh")
    _scp_to(project, name, [tar_path])
    deb_dir = Path(env.get("DEB_DIR", ""))
    if deb_dir.is_dir() and any(deb_dir.glob("*.deb")):
        packed = Path(env.get("RUNNER_TEMP") or "/tmp") / "self-service-debs.tar"
        pack_debs(deb_dir, packed)
        _scp_to(project, name, [packed])
        ca_bundle = deb_dir / "ca-certificates.crt"
        if ca_bundle.is_file() and ca_bundle.stat().st_size >= 1000:
            _scp_to(project, name, [ca_bundle])
    script = (
        "set -euo pipefail; "
        f"tar -xf {GUEST_DIR}/self-service.tar -C {GUEST_DIR}; "
        f"if [ -f {GUEST_DIR}/self-service-debs.tar ]; then mkdir -p {GUEST_DIR}/debs; "
        f"tar -xf {GUEST_DIR}/self-service-debs.tar -C {GUEST_DIR}/debs; fi; "
        "sudo env "
        f"PYTHONPATH={GUEST_DIR} "
        "VANTIO_LAB_SCOPE=lab-nonprod "
        f"VANTIO_LAB_ARTIFACT_TRUST={GUEST_DIR}/lab-artifact-trust.json "
        f"VANTIO_LAB_DEV_TRUST={GUEST_DIR}/lab-dev-trust.json "
        f"VANTIO_LAB_ROOT={GUEST_DIR} "
        f"VANTIO_INSTALL_BUNDLE={GUEST_DIR}/bundle "
        f"VANTIO_POLICY_FILE={GUEST_DIR}/policy.json "
        f"VANTIO_SIGNATURE_FILE={GUEST_DIR}/signature.json "
        "VANTIO_STATE_DIR=/var/lib/vantio/install "
        "VANTIO_SELF_SERVICE_OUT=/tmp/self-service-rows.json "
        f"python3 {GUEST_DIR}/self_service.py"
    )
    if "--artifact-trust" in script or "--fixture-host" in script or "\n" in script:
        raise SystemExit("self_service_layout")
    _run_guest(project, name, f"bash -c {json.dumps(script)}", "self_service")
    evidence = _evidence_dir(env)
    local = evidence / "self-service-rows.json"
    pulled = _scp_from(project, name, "/tmp/self-service-rows.json", local)
    body = _load_json_file(local) if pulled else {}
    write_evidence(
        evidence / "gcp-lab-rows.json",
        {
            "claim_cap": CLAIM_CAP,
            "cloud": "gcp",
            "mode": "self-service",
            "mutated": True,
            "network": NETWORK,
            "public_ip": False,
            "seal_sha256": seal,
            "self_service": _self_service_rows(body),
            "status": "SELF_SERVICE",
            "subnet": SUBNET,
        },
    )
    if local.is_file() and not local.is_symlink():
        local.unlink()
    print(json.dumps({"mode": "self-service", "status": "SELF_SERVICE"}))
    return 0


def remove_os_login_key() -> int:
    pub = Path.home() / ".ssh" / "google_compute_engine.pub"
    if not pub.is_file():
        return 0
    completed = _run(["gcloud", "compute", "os-login", "ssh-keys", "remove", f"--key-file={pub}", "--quiet"])
    if completed.returncode != 0:
        print(redact((completed.stderr or "")[-500:]), file=sys.stderr)
    return 0


def delete_handoff(env: Mapping[str, str]) -> int:
    _require_execute(env)
    require_lab_project(env.get("GCP_LAB_PROJECT", ""))
    delete_objects(handoff_objects(env), missing_ok=True)
    write_evidence(_evidence_dir(env) / "handoff-deleted.json", {"deleted": True, "bucket": BUCKET})
    return 0


def _creation_epoch(project: str, name: str) -> int | None:
    completed = _run(
        [
            "gcloud",
            "compute",
            "instances",
            "describe",
            name,
            f"--project={project}",
            f"--zone={ZONE}",
            "--format=value(creationTimestamp)",
        ]
    )
    stamp = (completed.stdout or "").strip()
    if completed.returncode != 0 or not stamp:
        return None
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())


def teardown_if_present(env: Mapping[str, str]) -> int:
    _require_execute(env)
    project = require_lab_project(env.get("GCP_LAB_PROJECT", ""))
    name = instance_name(env.get("GITHUB_RUN_ID", ""))
    deleted = False
    skipped = False
    hours = Decimal("0")
    gross = Decimal("0")
    try:
        created = _creation_epoch(project, name)
        now = int(time.time())
        if created is not None and now >= created:
            hours = Decimal(now - created) / Decimal("3600")
        gross = estimate_gross_usd(hours)
        instances = _list_instances(project)
        matched = next((item for item in instances if item.get("name") == name), None)
        if matched is not None:
            if not lab.labels_owned(matched.get("labels"), name):
                skipped = True
            else:
                _run_ok(
                    [
                        "gcloud",
                        "compute",
                        "instances",
                        "delete",
                        name,
                        f"--project={project}",
                        f"--zone={lab.instance_zone(matched)}",
                        "--delete-disks=all",
                        "--quiet",
                    ],
                    "teardown",
                )
                deleted = True
    finally:
        delete_objects(handoff_objects(env), missing_ok=True)
    if skipped:
        write_evidence(
            _evidence_dir(env) / "teardown.json",
            {"claim_cap": CLAIM_CAP, "deleted": False, "name": name, "verify_status": "UNKNOWN"},
        )
        return 2
    os.environ["INSTANCE_NAME"] = name
    os.environ["GCP_LAB_PROJECT"] = project
    os.environ["GCP_LAB_EXECUTE"] = "1"
    verify: dict[str, Any] = {"status": "UNKNOWN"}
    verify_rc = 2
    for _ in range(12):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            verify_rc = lab.execute_verify(os.environ)
        try:
            parsed = json.loads(buffer.getvalue())
        except json.JSONDecodeError:
            parsed = {"status": "UNKNOWN"}
        if isinstance(parsed, dict):
            verify = parsed
        if verify_rc == 0 and verify.get("status") == "VERIFIED_REMOVED":
            break
        time.sleep(10)
    payload = {
        "claim_cap": CLAIM_CAP,
        "cost_basis": "e2-micro 0.0084 USD/h plus 10GB pd-balanced, against trial credit; not a billing export",
        "deleted": deleted,
        "estimated_gross_usd": _money(gross),
        "expected_oop_usd": "0",
        "hours": _money(hours),
        "name": name,
        "out_of_pocket_usd": "0",
        "verify": verify,
    }
    write_evidence(_evidence_dir(env) / "teardown.json", payload)
    print(json.dumps(payload))
    if verify.get("status") != "VERIFIED_REMOVED" or verify_rc != 0:
        return 2
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    command = args[0] if args else ""
    env = os.environ
    try:
        if command == "assert-bundle":
            return assert_bundle_command(env)
        if command == "upload-handoff":
            return upload_handoff(env)
        if command == "download-handoff":
            return download_handoff(env)
        if command == "hash-debs":
            return hash_debs(env)
        if command == "prune-evidence":
            directory = _evidence_dir(env)
            print(json.dumps({"kept": prune_evidence(directory)}))
            return 0
        if command == "check-dispatch":
            refuse_batteries(env)
            print(json.dumps({"batteries": batteries_requested(env), "seal_sha256": expected_seal(env)}))
            return 0
        if command == "create-instance":
            return create_instance(env)
        if command == "plumb-guest":
            return plumb_guest(env)
        if command == "run-batteries":
            return run_batteries(env)
        if command == "run-self-service":
            return run_self_service(env)
        if command == "run-redteam":
            return redteam_campaign.execute(env, sys.modules[__name__])
        if command == "delete-handoff":
            return delete_handoff(env)
        if command == "remove-oslogin-key":
            return remove_os_login_key()
        if command == "teardown-if-present":
            return teardown_if_present(env)
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
