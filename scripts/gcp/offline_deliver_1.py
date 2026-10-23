#!/usr/bin/env python3
"""Offline Phantom Engine delivery onto one private Ubuntu 24.04 lab VM.

The sealed bundle moves through gs://vantio-lab-oct08-handoff and then over
IAP. It is never a GitHub Actions artifact. This module does not call GCP
unless GCP_LAB_EXECUTE=1. It refuses a deployment-partner project and any external
address.

Audience: INTERNAL_CLEAN_HOST_PROOF
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shlex
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
TRUST_SHA256 = "2e4a1da7bf44f0bddfc2a3ce3eda007fa6cc1455332f26769bd346fafc297876"
TRUST_KEY_ID = "test-nonprod-ed25519-2026-10-02"
TRUST_MEMBER = "vantio_enterprise_protocol/trust/test_nonprod_2026_10_02.json"
POLICY_ALLOW_SEAL = redteam_packet.POLICY_ALLOW_SEAL
PUBLIC_INSTALLER_PIN = redteam_packet.PUBLIC_PIN
TRACKING_2A_SEAL = redteam_packet.TRACKING_SEAL
IMAGE_NAME = "vantio-phantom-engine:egress-2e6ab54"
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
    "hash-debs|check-dispatch|create-instance|plumb-guest|run-batteries|run-t5-egress|run-redteam|run-self-service|delete-handoff|remove-oslogin-key|"
    "serial-console|teardown-if-present"
)


def require_lab_project(project: str) -> str:
    if (
        not isinstance(project, str)
        or lab.names_partner(project)
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


# phase2_host.run_2c needs this file beside seal.oci.tar on the guest (#320).
PUBLIC_PIN_FILE = "public-pin.oci.tar"


def public_pin_object_name(run_id: str) -> str:
    return f"{require_run_id(run_id)}/{PUBLIC_PIN_FILE}"


def verify_public_pin_file(path: Path) -> str:
    """Return the sha256 only when the file is the public installer pin."""
    if not path.is_file():
        raise SystemExit("public_pin_absent")
    size = path.stat().st_size
    if size <= 0 or size > MAX_SEAL_BYTES:
        raise SystemExit("public_pin_digest")
    digest = sha256_file(path)
    if digest != PUBLIC_INSTALLER_PIN:
        raise SystemExit("public_pin_digest")
    return digest


def handoff_objects(env: Mapping[str, str]) -> tuple[str, ...]:
    run_id = env.get("GITHUB_RUN_ID", "")
    names = object_names(run_id)
    if brain_requested(env):
        names = names + brain_object_names(run_id)
    if batteries_requested(env):
        names = names + (public_pin_object_name(run_id),)
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
        "lsm-guard.json",
        "redteam-packet.json",
        "teardown.json",
    }
)
CEILING_PATH = "/var/lib/vantio-pe-clean-host/d/secret"
HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
SHORT_RE = re.compile(r"^[A-Za-z0-9_.:@+/-]{1,80}$")
LOCKDOWN_RE = re.compile(
    r"^(?:none|\[none\]|integrity|\[integrity\]|confidentiality|\[confidentiality\])"
    r"(?: (?:none|\[none\]|integrity|\[integrity\]|confidentiality|\[confidentiality\])){0,3}$"
)
EXACT_IMAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+/-]{0,159}$")


def exact_image_name(value: object) -> str:
    """The image that booted. The family used at create time is not this name."""
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text or "\n" in text or "*" in text or text in {IMAGE_FAMILY, f"{IMAGE_PROJECT}/{IMAGE_FAMILY}"}:
        return ""
    if EXACT_IMAGE_RE.fullmatch(text) is None:
        return ""
    return text


def lockdown_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if LOCKDOWN_RE.fullmatch(text) is None:
        return ""
    return text


def host_evidence_fields(body: object) -> dict[str, str]:
    if not isinstance(body, dict):
        return {}
    kept: dict[str, str] = {}
    lockdown = lockdown_text(body.get("lockdown"))
    if lockdown:
        kept["lockdown"] = lockdown
    name = exact_image_name(body.get("image_name"))
    if name:
        kept["image_name"] = name
    return kept


def image_name_from_disk(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    source = payload.get("sourceImage")
    if not isinstance(source, str) or not source or "\n" in source:
        return ""
    return exact_image_name(source.rstrip("/").rsplit("/", 1)[-1])
ENUMS = {
    "bucket": frozenset({BUCKET}),
    "claim_cap": frozenset({CLAIM_CAP}),
    "cloud": frozenset({"gcp"}),
    # offline_deliver_4.PHASE_DISTRO_SCOPE. Part 4 loads after this table.
    "distro_scope": frozenset({"ubuntu-2404-only"}),
    "image": frozenset({f"{IMAGE_PROJECT}/{IMAGE_FAMILY}", IMAGE_NAME}),
    "machine_type": frozenset({lab.MACHINE_TYPE, rtbrain.BRAIN_MACHINE}),
    "mode": frozenset({"plumb", "enterprise", "descendant-b1", "self-service", "t5-egress"}),
    "network": frozenset({NETWORK}),
    "project_id": frozenset({LAB_PROJECT}),
    "status": frozenset(
        {
            "PLUMB_DIGEST_MATCH",
            "BUNDLE_READY",
            "BLOCKED_BUNDLE",
            "VERIFIED_REMOVED",
            "NOT_REMOVED",
            "SELF_SERVICE",
            "T5_EGRESS",
        }
    ),
    "subnet": frozenset({SUBNET}),
    "verify_status": frozenset({"VERIFIED_REMOVED", "NOT_REMOVED", "UNKNOWN"}),
    "zone": frozenset({ZONE}),
    "expected_oop_usd": frozenset({"0", "UNKNOWN"}),
    "out_of_pocket_usd": frozenset({"0"}),
    "spend_source": frozenset({"empty_project_no_vms_or_disks", "supplied"}),
}


# The guest prints "Loaded image: <tag>" from docker load of the sealed tar.
# enterprise-rows.sh accepts the historical lab tag or an engine-commit tag.
LOADED_IMAGE_RE = re.compile(r"vantio-phantom-engine:[0-9a-f]{7,40}")
LOADED_LINE_RE = re.compile(r"^(?:Loaded image: |IMAGE_LINE=)(?:docker\.io/library/)?(\S+)\s*$", re.M)
_LSM_RE = re.compile(r"[a-z0-9,]{0,120}")
_WORD_RE = re.compile(r"[a-z0-9_]{1,40}")
# Only the warnings the lab emits: descendant_b1's scoped_banner status
# (BANNER_STATUS other than "scoped") and phase2_host's late deny row flags.
# Anything else is dropped.
_WARNING_RE = re.compile(
    r"(?:pre_|post_)?scoped_banner=(?:missing|not_checked|scoped_banner_without_ledger_line)"
    r"|late_deny_row_(?:before|after)_restart"
)
# Above this, a deny row is flagged as late (phase2_host.DENY_ROW_LATE_S).
DENY_ROW_LATE_S = 0.5
_EVENT_TIME_RE = re.compile(r"[0-9T:.+Z -]{1,40}")
_BOOT_ID_RE = re.compile(r"[0-9a-f-]{36}")


def engine_image(value: object) -> str:
    """The loaded engine tag, or "" when it is not one the guest would accept."""
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if text.startswith("docker.io/library/"):
        text = text[len("docker.io/library/"):]
    if text == IMAGE_NAME or LOADED_IMAGE_RE.fullmatch(text):
        return text
    return ""


def loaded_image_from_text(text: object) -> str:
    """The last accepted tag the guest printed, or ""."""
    if not isinstance(text, str):
        return ""
    found = ""
    for match in LOADED_LINE_RE.finditer(text):
        tag = engine_image(match.group(1))
        if tag:
            found = tag
    return found


def _int_in(value: object, low: int, high: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def _seconds(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return 0 <= float(value) <= 3600


def _allow_start_timing(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    kept: dict[str, Any] = {}
    for key in ("banner_wait_s", "probe_done_after_banner_s", "banner_to_ledger_s", "ledger_timeout_s", "start_wait_s"):
        item = value.get(key)
        if item is None and key in value:
            kept[key] = None
        elif _seconds(item):
            kept[key] = item
    if _int_in(value.get("ledger_since"), 0, 10_000_000):
        kept["ledger_since"] = value["ledger_since"]
    if isinstance(value.get("ledger_seen"), bool):
        kept["ledger_seen"] = value["ledger_seen"]
    return kept


def _allow_start_probe(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    kept: dict[str, Any] = {}
    if _int_in(value.get("pid"), 0, 2**22):
        kept["pid"] = value["pid"]
    for key in ("file_errno", "net_errno"):
        if _int_in(value.get(key), 0, 255):
            kept[key] = value[key]
    if _int_in(value.get("lineage_anchor"), 0, 2**32):
        kept["lineage_anchor"] = value["lineage_anchor"]
    if _seconds(value.get("took_s")):
        kept["took_s"] = value["took_s"]
    if isinstance(value.get("pass"), bool):
        kept["pass"] = value["pass"]
    if "file_event" in value:
        kept["file_event"] = bool(value.get("file_event"))
    error = value.get("error")
    if isinstance(error, str):
        kind = error.split(":", 1)[0].strip()
        kept["error"] = kind if re.fullmatch(r"[A-Za-z]{1,40}", kind) else "error"
    return kept


def _allow_window_entry(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    name = value.get("name")
    status = value.get("status")
    if not isinstance(name, str) or re.fullmatch(r"[a-z0-9_-]{1,40}", name) is None:
        return None
    if status not in {"recorded", "delayed", "dropped", "probe_not_denied"}:
        return None
    kept: dict[str, Any] = {"name": name, "status": status}
    if _int_in(value.get("pid"), 0, 2**22):
        kept["pid"] = value["pid"]
    if _int_in(value.get("file_errno"), 0, 255):
        kept["file_errno"] = value["file_errno"]
    index = value.get("row_index")
    if index is None or _int_in(index, 0, 10_000_000):
        kept["row_index"] = index
    if isinstance(value.get("after_ledger_line"), bool):
        kept["after_ledger_line"] = value["after_ledger_line"]
    row_time = value.get("row_time")
    if _seconds(row_time) or (isinstance(row_time, (int, float)) and not isinstance(row_time, bool) and 0 <= row_time < 2**42):
        kept["row_time"] = row_time
    elif isinstance(row_time, str) and _EVENT_TIME_RE.fullmatch(row_time):
        kept["row_time"] = row_time
    return kept


def _allow_start_window(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    kept: dict[str, Any] = {"informational": True}
    status = value.get("status")
    if status in {"none_missing", "delayed", "dropped", "mixed", "error"}:
        kept["status"] = status
    for key in ("delayed", "dropped"):
        if _int_in(value.get(key), 0, 1000):
            kept[key] = value[key]
    index = value.get("ledger_line_index")
    if index is None or _int_in(index, 0, 10_000_000):
        kept["ledger_line_index"] = index
    line_time = value.get("ledger_line_time")
    if isinstance(line_time, (int, float)) and not isinstance(line_time, bool) and 0 <= line_time < 2**42:
        kept["ledger_line_time"] = line_time
    elif isinstance(line_time, str) and _EVENT_TIME_RE.fullmatch(line_time):
        kept["ledger_line_time"] = line_time
    checked = value.get("checked")
    if isinstance(checked, list):
        kept["checked"] = [item for item in (_allow_window_entry(entry) for entry in checked) if item][:24]
    error = value.get("error")
    if isinstance(error, str):
        kind = error.split(":", 1)[0].strip()
        kept["error"] = kind if re.fullmatch(r"[A-Za-z]{1,40}", kind) else "error"
    return kept


def _allow_boot_lsm(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    kept: dict[str, Any] = {}
    for key in ("lsm", "cmdline_lsm"):
        item = value.get(key)
        if isinstance(item, str) and _LSM_RE.fullmatch(item):
            kept[key] = item
    if isinstance(value.get("bpf_lsm_active"), bool):
        kept["bpf_lsm_active"] = value["bpf_lsm_active"]
    return kept


def _allow_reassert(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    kept: dict[str, Any] = {}
    for key in ("ok", "written"):
        if isinstance(value.get(key), bool):
            kept[key] = value[key]
    reason = value.get("reason")
    if isinstance(reason, str) and _WORD_RE.fullmatch(reason):
        kept["reason"] = reason
    lsm_value = value.get("lsm_value")
    if isinstance(lsm_value, str) and _LSM_RE.fullmatch(lsm_value):
        kept["lsm_value"] = lsm_value
    boot = value.get("boot_id")
    if isinstance(boot, str) and _BOOT_ID_RE.fullmatch(boot):
        kept["boot_id"] = boot
    return kept


def _allow_warnings(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    return [item for item in value if isinstance(item, str) and _WARNING_RE.fullmatch(item)][:8]


# descendant_b1.py (#357) start-window and LSM fields. Informational; none of them gates a pass.
START_FIELD_SANITIZERS = {
    "start_timing": _allow_start_timing,
    "start_probe": _allow_start_probe,
    "start_window_rows": _allow_start_window,
    "warnings": _allow_warnings,
    "boot_lsm": _allow_boot_lsm,
    "lab_lsm_reassert": _allow_reassert,
}


def allow_start_fields(body: object) -> dict[str, Any]:
    """Keep the descendant-b1 start fields that pass their allowlist. A None value stays None."""
    if not isinstance(body, dict):
        return {}
    kept: dict[str, Any] = {}
    for key, clean in START_FIELD_SANITIZERS.items():
        if key not in body:
            continue
        if body[key] is None:
            kept[key] = None
            continue
        value = clean(body[key])
        if value is not None:
            kept[key] = value
    return kept


CYCLE_STEP_NAMES = ("baseline", "upgrade", "rollback", "reupgrade")
BPF_PROG_NAME_RE = re.compile(r"[A-Za-z0-9_.:-]{1,64}")
BPFFS_VANTIO_RE = re.compile(r"/sys/fs/bpf/vantio[A-Za-z0-9_./-]{0,120}")
# Named 2C host findings phase2_grade can emit (phase2_grade.CYCLE_FINDINGS:
# PUBLIC_PIN_RESIDUE_FINDING and PUBLIC_PIN_UNATTRIBUTED_FINDING).
PUBLIC_PIN_UNATTRIBUTED = "public_pin_unattributed_deny"
PIN_CYCLE_STEPS = frozenset({"baseline", "rollback"})
KNOWN_CYCLE_FINDINGS = frozenset({"public_pin_leaves_bpf_residue", PUBLIC_PIN_UNATTRIBUTED})


def allow_cycle_findings(value: Any) -> list[dict[str, Any]]:
    """Named 2C host findings (phase2_grade grade_image_cycle findings[]).

    For example public_pin_leaves_bpf_residue with the census detail: bpf
    program names and bpffs pins under /sys/fs/bpf/vantio*, or
    public_pin_unattributed_deny on a pin step with errno 13. Anything else is
    dropped. A finding is carried as evidence; it never changes a grade here.
    """
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        finding = item.get("finding")
        step = item.get("step")
        if finding not in KNOWN_CYCLE_FINDINGS:
            continue
        if step not in CYCLE_STEP_NAMES:
            continue
        row: dict[str, Any] = {"finding": finding, "step": step}
        programs = item.get("loader_programs")
        if isinstance(programs, list):
            row["loader_programs"] = [
                name for name in programs if isinstance(name, str) and BPF_PROG_NAME_RE.fullmatch(name)
            ][:32]
        paths = item.get("bpffs_vantio")
        if isinstance(paths, list):
            row["bpffs_vantio"] = [
                path
                for path in paths
                if isinstance(path, str) and BPFFS_VANTIO_RE.fullmatch(path) and ".." not in path.split("/")
            ][:32]
        rc = item.get("bpftool_rc")
        if isinstance(rc, int) and not isinstance(rc, bool) and 0 <= rc <= 255:
            row["bpftool_rc"] = rc
        if finding == PUBLIC_PIN_UNATTRIBUTED:
            # The finding says the pin enforced: only a pin step, only errno 13.
            errno = item.get("file_errno")
            if step not in PIN_CYCLE_STEPS or type(errno) is not int or errno != 13:
                continue
            row["file_errno"] = 13
        rows.append(row)
    return rows[:8]


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
    findings = allow_cycle_findings(entry.get("findings"))
    if findings:
        kept["findings"] = findings
    kept.update(allow_start_fields(entry))
    image = engine_image(entry.get("image"))
    if image:
        kept["image"] = image
    for phase in ("before", "after"):
        if _seconds(entry.get(f"{phase}_row_wait_s")):
            kept[f"{phase}_row_wait_s"] = entry[f"{phase}_row_wait_s"]
        if isinstance(entry.get(f"{phase}_row_seen"), bool):
            kept[f"{phase}_row_seen"] = entry[f"{phase}_row_seen"]
    restart_rows = allow_restart_rows(entry.get("restart_rows"))
    if restart_rows:
        kept["restart_rows"] = restart_rows
    if _seconds(entry.get("late_s")) and entry.get("claim_scope") == LATE_CLAIM_SCOPE:
        kept["late_s"] = entry["late_s"]
        kept["claim_scope"] = entry["claim_scope"]
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
                    r"[0-9]{1,20}/(seal\.oci\.tar|contract\.tar|public-pin\.oci\.tar|qwen2\.5-3b-instruct-q4_k_m\.gguf|llama-b11540-bin-ubuntu-x64\.tar\.gz)",
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
        if key == "image":
            if isinstance(value, str) and value in ENUMS["image"]:
                kept[key] = value
            elif engine_image(value):
                # Store the normalised tag, never the raw guest string.
                kept[key] = engine_image(value)
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
        if key == "stock_lsm" and isinstance(value, str) and re.fullmatch(r"[a-z0-9,]{0,80}", value):
            kept[key] = value
            continue
        if key in {"lockdown", "kernel_lockdown"}:
            text = lockdown_text(value)
            if text:
                kept[key] = text
            continue
        if key == "image_name":
            text = exact_image_name(value)
            if text:
                kept[key] = text
            continue
        if key == "lsm_guard" and isinstance(value, str) and re.fullmatch(r"[a-z0-9_]{1,40}", value):
            kept[key] = value
            continue
        if key == "host_result" and isinstance(value, str) and value in {
            "",
            "FAIL",
            "GUARD_PROVED",
            "LSM_ALREADY_ACTIVE",
            "LSM_ENABLED",
        }:
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
            "interim",
            "phases_complete",
            "stock_bpf_lsm",
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
        if key == "loader_restart_findings" and isinstance(value, list):
            kept[key] = allow_cycle_findings(value)
            continue
        if key == "loader_kill_restart_rows" and isinstance(value, dict):
            kept[key] = allow_restart_rows(value)
            continue
        if key == "loader_kill_late_s" and (value is None or _seconds(value)):
            kept[key] = value
            continue
        if key == "loader_kill_claim_scope" and value == LATE_CLAIM_SCOPE:
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
        if key == "phases" and isinstance(value, list):
            # offline_deliver_4.py. Each row's pass is recomputed on the way in.
            kept["phases"] = [item for item in (allow_phase_row(entry) for entry in value[:3]) if item]
            continue
        if key == "distro_excluded" and isinstance(value, list):
            kept["distro_excluded"] = [dict(item) for item in DISTRO_EXCLUDED if item in value]
            continue
        if key == "phases_pass":
            continue
    if "phases" in kept:
        kept["phases_pass"] = phases_pass(kept["phases"])
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
        if key in {"nobody_errno", "errno"} and isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 255:
            kept[key] = value
            continue
        if key == "phase" and value in {"pre", "post"}:
            kept[key] = value
            continue
        if key == "verifier" and value in {"accepted", "rejected", "not_run"}:
            kept[key] = value
            continue
        if key == "user_port" and value in {"pass", "fail", "not_run"}:
            kept[key] = value
            continue
        if key == "kernel_attach" and value in {"Lab-only", "Roadmap"}:
            kept[key] = value
            continue
        if key == "label" and value in {"Verified", "Lab-only", "Roadmap"}:
            kept[key] = value
            continue
        if key == "cgroup" and value == "/sys/fs/cgroup/vantio-t5-lab.slice/t5-drill":
            kept[key] = value
            continue
        if key in {"attached", "outside_unaffected"} and isinstance(value, bool):
            kept[key] = value
            continue
        if key == "enrolled_slice" and value is False:
            kept[key] = value
            continue
        if key == "uptime_seconds" and isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 7200:
            kept[key] = value
            continue
        if key == "battery" and value in {"enterprise", "descendant-b1", "t5-egress"}:
            kept[key] = value
            continue
        if key == "result" and value in {"open_ok", "open_error", "probe_failed", "not_run", "pass", "fail"}:
            kept[key] = value
            continue
        if key == "image" and engine_image(value):
            kept[key] = engine_image(value)
            continue
        if key in START_FIELD_SANITIZERS:
            kept.update(allow_start_fields({key: value}))
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
        if key in {"lockdown", "kernel_lockdown"}:
            text = lockdown_text(value)
            if text:
                kept[key] = text
            continue
        if key == "image_name":
            text = exact_image_name(value)
            if text:
                kept[key] = text
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


def t5_requested(env: Mapping[str, str]) -> bool:
    raw = env.get("T5_EGRESS", "false").strip().lower()
    if raw not in ("true", "false"):
        raise SystemExit("t5_egress")
    return raw == "true"


def _load_t5_battery(env: Mapping[str, str]) -> Any:
    # Fetch and teardown import this module and do not check out t5.
    # Load it only when the t5-egress input is set.
    if not t5_requested(env):
        raise SystemExit("t5_egress")
    t5_dir = Path(__file__).resolve().parents[1] / "clean-host" / "t5"
    if str(t5_dir) not in sys.path:
        sys.path.insert(0, str(t5_dir))
    import t5_battery

    return t5_battery


def assert_t5_dispatch(env: Mapping[str, str]) -> str:
    """t5-egress is one battery. It does not run the enterprise set."""
    if not t5_requested(env):
        raise SystemExit("t5_egress")
    if batteries_requested(env) or env.get("SELF_SERVICE", "false").strip().lower() == "true" or brain_requested(env):
        raise SystemExit("t5_egress")
    project = require_lab_project(env.get("GCP_LAB_PROJECT", ""))
    if lab.names_partner(project):
        raise SystemExit("partner")
    seal = expected_seal(env)
    if seal != _load_t5_battery(env).LANE_SEAL:
        raise SystemExit("seal")
    return seal


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
    if lab.names_partner(joined) or "--address=" in joined:
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


def _refuse_scp(reason: str) -> None:
    print(f"scp_refused {reason}", file=sys.stderr)
    raise SystemExit("scp")


def iap_scp_argv(project: str, sources: Sequence[str], destination: str) -> list[str]:
    require_lab_project(project)
    if not sources:
        _refuse_scp("no_sources")
    parts = [*sources, destination]
    remote = [item for item in parts if ":" in item]
    if len(remote) != 1:
        _refuse_scp(f"remote_count={len(remote)}")
    host = remote[0].split(":", 1)[0]
    if not host.startswith(lab.NAME_PREFIX) or ".." in remote[0]:
        _refuse_scp(f"host={host}")
    for item in parts:
        if "\n" in item or "\x00" in item:
            _refuse_scp("bad_character")
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
    if mode in {"2c-upgrade-rollback", "2d-crash-recovery", "lsm-guard", "2e-performance", "2f-tamper", "2g-distro"} and phase == "":
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


def _run(argv: list[str], timeout_s: int | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(argv, check=False, capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return subprocess.CompletedProcess(argv, 255, stdout, stderr + "\noperation timed out")


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


