#!/usr/bin/env python3
"""Offline Phantom Engine delivery onto one private Debian 12 lab VM.

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

CLAIM_CAP = "INTERNAL_CLEAN_HOST_PROOF"
LAB_PROJECT = "vantio-lab-oct08"
BUCKET = "vantio-lab-oct08-handoff"
HANDOFF_SA = "vantio-lab-handoff@vantio-lab-oct08.iam.gserviceaccount.com"
NETWORK = "vantio-lab-offline"
SUBNET = "vantio-lab-offline-usc1"
NETWORK_TAG = "vantio-gcp-lab"
IMAGE_FAMILY = "debian-12"
IMAGE_PROJECT = "debian-cloud"
DEBIAN_IMAGE = "debian:12@sha256:bc49dc1918ee1a47a93e65b5e4676e8680fb754b133197b92ca52bfe6731d5f0"
SNAPSHOT = "20261008T000000Z"
SNAPSHOT_LINES = (
    "deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/20261008T000000Z bookworm main",
    "deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/20261008T000000Z bookworm-updates main",
    "deb [check-valid-until=no] https://snapshot.debian.org/archive/debian-security/20261008T000000Z bookworm-security main",
)
POLICY_ALLOW_SEAL = "f882dd81297b02c11c55d9df69f00d9fffa710d1a87d36066a5645922804d753"
TRUST_SHA256 = "2e4a1da7bf44f0bddfc2a3ce3eda007fa6cc1455332f26769bd346fafc297876"
TRUST_KEY_ID = "test-nonprod-ed25519-2026-10-02"
TRUST_MEMBER = "vantio_enterprise_protocol/trust/test_nonprod_2026_10_02.json"
PUBLIC_INSTALLER_PIN = "e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e"
TRACKING_2A_SEAL = "16c9e5638c169e5fdd3fd7291b3225a809b18abfe464d717c2d31a398d5bda6a"
IMAGE_NAME = "vantio-phantom-engine:policy-allow-df61d97"
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
    r"|ghp_[A-Za-z0-9]{20,}"
    r"|ya29\.[0-9A-Za-z\-_]+",
    re.S,
)
PRIVATE_KEY_TEXT = re.compile(br"-----BEGIN [A-Z ]*PRIVATE KEY-----")
USAGE = (
    "usage: offline_deliver.py assert-bundle|upload-handoff|download-handoff|"
    "hash-debs|check-dispatch|create-instance|plumb-guest|run-batteries|delete-handoff|remove-oslogin-key|"
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


def write_evidence(path: Path, payload: Mapping[str, Any]) -> None:
    text = redact(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    if "PRIVATE KEY" in text or SECRET_RE.search(text):
        raise SystemExit("token_in_evidence")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    path.with_name(path.name + ".sha256").write_text(f"{digest}  {path.name}\n", encoding="utf-8")


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
    """Batteries wait for a new seal. The current policy-allow seal stays plumbing-only."""
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
    label_arg = ",".join(f"{key}={labels[key]}" for key in sorted(labels))
    argv = [
        "gcloud",
        "compute",
        "instances",
        "create",
        name,
        f"--project={project}",
        f"--zone={ZONE}",
        f"--machine-type={lab.MACHINE_TYPE}",
        f"--image-family={IMAGE_FAMILY}",
        f"--image-project={IMAGE_PROJECT}",
        f"--boot-disk-size={lab.BOOT_DISK_GB}",
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
        "--ssh-flag=-oServerAliveCountMax=120",
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
        "--ssh-flag=-oServerAliveInterval=30",
        "--ssh-flag=-oServerAliveCountMax=120",
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


def json_media_upload(bucket: str, object_name: str, path: Path, token: str) -> None:
    if bucket != BUCKET or ".." in object_name or object_name.startswith("/"):
        raise SystemExit("object")
    quoted = urllib.parse.quote(object_name, safe="")
    url = f"https://storage.googleapis.com/upload/storage/v1/b/{bucket}/o?uploadType=media&name={quoted}"
    _json_request(url, token, path.read_bytes(), "POST")


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


def upload_one(bucket: str, object_name: str, path: Path) -> str:
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
    print(json.dumps({"object": object_name, "via": "json", "reason": "storage.objects.get"}))
    token = _access_token()
    try:
        json_media_upload(bucket, object_name, path, token)
    finally:
        token = ""
    return "json"


def _missing_object(text: str) -> bool:
    lowered = text.lower()
    return "matched no objects" in lowered or "404" in lowered or "not found" in lowered


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
    names = object_names(env.get("GITHUB_RUN_ID", ""))
    directory = Path(env.get("W3_BUNDLE_DIR", ""))
    checked = assert_bundle_dir(directory, expected_seal(env))
    paths = (directory / "seal.oci.tar", directory / "contract.tar")
    via = [upload_one(BUCKET, name, path) for name, path in zip(names, paths)]
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
        write_evidence(_evidence_dir(env) / "download.json", payload)
        print(json.dumps(payload))
        return 0
    finally:
        delete_objects(names, missing_ok=True)


def hash_debs(env: Mapping[str, str]) -> int:
    directory = Path(env.get("DEB_DIR", ""))
    rows = deb_manifest(directory)
    payload = {
        "claim_cap": CLAIM_CAP,
        "debian_image": DEBIAN_IMAGE,
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
    labels = offline_labels(now, minutes)
    plan = {
        "image_family": IMAGE_FAMILY,
        "image_project": IMAGE_PROJECT,
        "labels": labels,
        "name": name,
        "network": NETWORK,
        "project_id": project,
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
        "image": f"{IMAGE_PROJECT}/{IMAGE_FAMILY}",
        "machine_type": lab.MACHINE_TYPE,
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


def _stored_guest(path: Path, fallback: str) -> Any:
    if path.is_file():
        parsed = _load_json_file(path)
        if parsed is not None:
            return parsed
        return redact(path.read_text(encoding="utf-8", errors="replace")[-20000:])
    return redact(fallback[-8000:])


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
    rows = pack_debs(deb_dir, dest / "debs.tar")
    return rows


def _run_guest(project: str, name: str, command: str, reason: str) -> subprocess.CompletedProcess[str]:
    completed = _ssh(project, name, command)
    if completed.returncode != 0:
        detail = redact((completed.stdout or "") + (completed.stderr or ""))
        print(detail[-4000:], file=sys.stderr)
        raise SystemExit(reason)
    return completed


def _wait_until_running(project: str, name: str) -> None:
    deadline = time.time() + 180
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
    _wait_ssh(project, name, 300)


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
        if payload_dir.exists():
            shutil.rmtree(payload_dir, ignore_errors=True)
        remove_os_login_key()


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
    guest_rc = 1
    descendant_rc = 1
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
                payload_dir / "debs.tar",
            ],
        )
        for local_name in ("seal.oci.tar", "contract.tar"):
            (payload_dir / local_name).unlink(missing_ok=True)
        enterprise = _ssh(project, name, guest_command(seal, "enterprise"))
        guest_rc = enterprise.returncode
        enterprise_path = evidence / "enterprise-rows.json"
        kernel_path = evidence / "kernel-facts.json"
        _scp_from(project, name, "/tmp/enterprise-pe-rows.json", enterprise_path)
        _scp_from(project, name, "/tmp/gcp-kernel-facts.json", kernel_path)
        if enterprise.returncode != 0:
            print(redact((enterprise.stdout or "") + (enterprise.stderr or ""))[-4000:], file=sys.stderr)
            raise SystemExit("enterprise")
        before = _wait_ssh(project, name, 60)
        pre = _ssh(project, name, guest_command(seal, "descendant-b1", "pre"))
        pre_text = redact((pre.stdout or "") + (pre.stderr or ""))
        deadline = time.time() + 180
        after = ""
        while time.time() < deadline:
            probe = _ssh(project, name, "cat /proc/sys/kernel/random/boot_id")
            boot = (probe.stdout or "").strip()
            if probe.returncode == 0 and reboot_ready(before, boot):
                after = boot
                break
            if probe.returncode == 0 and boot == before and "PY_RC=" in pre_text and "PY_RC=0" not in pre_text:
                print(pre_text[-4000:], file=sys.stderr)
                raise SystemExit("descendant_pre")
            time.sleep(10)
        if not reboot_ready(before, after):
            print(pre_text[-4000:], file=sys.stderr)
            raise SystemExit("reboot")
        post = _run_guest(project, name, guest_command(seal, "descendant-b1", "post"), "descendant_post")
        descendant_rc = post.returncode
        descendant_path = evidence / "descendant-b1.json"
        _scp_from(project, name, "/tmp/enterprise-pe-rows.json", descendant_path)
        result = {
            "claim_cap": CLAIM_CAP,
            "cloud": "gcp",
            "debian_image": DEBIAN_IMAGE,
            "debs": debs,
            "descendant_b1": _stored_guest(descendant_path, post.stdout or ""),
            "descendant_rc": descendant_rc,
            "enterprise_rc": guest_rc,
            "enterprise_rows": _stored_guest(enterprise_path, enterprise.stdout or ""),
            "image": IMAGE_NAME,
            "kernel": _load_json_file(kernel_path),
            "network": NETWORK,
            "public_ip": False,
            "reboot_observed": True,
            "seal_sha256": seal,
            "snapshot": SNAPSHOT,
            "subnet": SUBNET,
            "trust_sha256": TRUST_SHA256,
        }
        write_evidence(evidence / "gcp-lab-rows.json", result)
        print(json.dumps({"enterprise_rc": guest_rc, "descendant_rc": descendant_rc, "claim_cap": CLAIM_CAP}))
        return 0
    finally:
        if payload_dir.exists():
            shutil.rmtree(payload_dir, ignore_errors=True)
        remove_os_login_key()


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
    delete_objects(object_names(env.get("GITHUB_RUN_ID", "")), missing_ok=True)
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
    created = _creation_epoch(project, name)
    now = int(time.time())
    hours = Decimal("0")
    if created is not None and now >= created:
        hours = Decimal(now - created) / Decimal("3600")
    gross = estimate_gross_usd(hours)
    instances = _list_instances(project)
    matched = next((item for item in instances if item.get("name") == name), None)
    deleted = False
    if matched is not None:
        if not lab.labels_owned(matched.get("labels"), name):
            raise SystemExit("skip_not_owned")
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
    delete_objects(object_names(env.get("GITHUB_RUN_ID", "")), missing_ok=True)
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
