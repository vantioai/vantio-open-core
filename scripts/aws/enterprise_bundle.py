#!/usr/bin/env python3
"""Check the private Enterprise row bundle before any AWS call.

The seal file and the contract tar stay in the runner temp directory.
Evidence written here records hashes and reasons. It does not record the
read token, the tar bytes, or a private key.

Audience: INTERNAL_RESTRICTED
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tarfile
from pathlib import Path
from typing import Callable

import w3_lab_auto as lab

POLICY_ALLOW_SEAL = "f882dd81297b02c11c55d9df69f00d9fffa710d1a87d36066a5645922804d753"
PUBLIC_INSTALLER_PIN = "e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e"
TRACKING_2A_SEAL = "16c9e5638c169e5fdd3fd7291b3225a809b18abfe464d717c2d31a398d5bda6a"
TRUST_BUNDLE_SHA256 = "2e4a1da7bf44f0bddfc2a3ce3eda007fa6cc1455332f26769bd346fafc297876"
TRUST_KEY_ID = "test-nonprod-ed25519-2026-10-02"
TRUST_MEMBER = "vantio_enterprise_protocol/trust/test_nonprod_2026_10_02.json"
BUNDLE_SCHEMA = "vantio.lab-enterprise-pe-bundle/v1"
BUNDLE_REPO = "vantioai/vantio-enterprise-private"
DEFAULT_BUNDLE_TAG = "lab-bundle/enterprise-pe-2026-10-08"
# The release tag is deleted. These bytes live on this commit, which is not a tag.
BUNDLE_COMMIT = "6f3e86d11f37451081445cc7e7a243fd2e57e604"
BUNDLE_FILES = ("manifest.json", "seal.oci.tar", "contract.tar", "public-pin.oci.tar")
BUNDLE_TAG = re.compile(r"^lab-bundle/[A-Za-z0-9._-]{1,64}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
PRIVATE_KEY_TEXT = re.compile(br"-----BEGIN [A-Z ]*PRIVATE KEY-----")
MAX_MEMBER_BYTES = 2_000_000
MAX_CONTRACT_BYTES = 20_000_000
MAX_SEAL_BYTES = 80_000_000
Fetcher = Callable[[Path], None]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _member_refused(name: str) -> bool:
    if name.startswith("/") or name.startswith("\\"):
        return True
    parts = name.split("/")
    if ".." in parts or name.endswith("private-key.pem"):
        return True
    return False


def inspect_bundle(
    directory: Path,
    *,
    expected_seal: str = POLICY_ALLOW_SEAL,
    expected_trust: str = TRUST_BUNDLE_SHA256,
) -> dict[str, object]:
    """Refuse a bundle that is not the pinned non-production contract and seal."""
    if expected_seal in (PUBLIC_INSTALLER_PIN, TRACKING_2A_SEAL) or not HEX64.fullmatch(expected_seal):
        raise lab.GuardAbort("bundle_wrong_seal")
    if not HEX64.fullmatch(expected_trust):
        raise lab.GuardAbort("bundle_trust")
    manifest_path = directory / "manifest.json"
    seal_path = directory / "seal.oci.tar"
    contract_path = directory / "contract.tar"
    if not manifest_path.is_file() or not seal_path.is_file() or not contract_path.is_file():
        raise lab.GuardAbort("bundle_layout")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise lab.GuardAbort("bundle_manifest") from None
    if not isinstance(manifest, dict):
        raise lab.GuardAbort("bundle_manifest")
    if manifest.get("schema") != BUNDLE_SCHEMA:
        raise lab.GuardAbort("bundle_manifest")
    if manifest.get("not_a_production_root") is not True:
        raise lab.GuardAbort("bundle_production_root")
    if manifest.get("trust_key_id") != TRUST_KEY_ID:
        raise lab.GuardAbort("bundle_trust")
    enterprise_sha = manifest.get("enterprise_sha")
    if not isinstance(enterprise_sha, str) or HEX40.fullmatch(enterprise_sha) is None:
        raise lab.GuardAbort("bundle_manifest")
    if manifest.get("seal_sha256") != expected_seal:
        raise lab.GuardAbort("bundle_seal")
    contract_sha = manifest.get("contract_sha256")
    if not isinstance(contract_sha, str) or HEX64.fullmatch(contract_sha) is None:
        raise lab.GuardAbort("bundle_manifest")
    seal_size = seal_path.stat().st_size
    if seal_size <= 0 or seal_size > MAX_SEAL_BYTES:
        raise lab.GuardAbort("bundle_seal")
    seal_sha = sha256_file(seal_path)
    if seal_sha in (PUBLIC_INSTALLER_PIN, TRACKING_2A_SEAL):
        raise lab.GuardAbort("bundle_wrong_seal")
    if seal_sha != expected_seal:
        raise lab.GuardAbort("bundle_seal")
    file_contract_sha = sha256_file(contract_path)
    if file_contract_sha != contract_sha:
        raise lab.GuardAbort("bundle_contract")
    trust_body = _read_contract(contract_path)
    trust_sha = hashlib.sha256(trust_body).hexdigest()
    if trust_sha != expected_trust:
        raise lab.GuardAbort("bundle_trust")
    return {
        "contract_sha256": file_contract_sha,
        "enterprise_sha": enterprise_sha,
        "not_a_production_root": True,
        "seal_sha256": seal_sha,
        "trust_key_id": TRUST_KEY_ID,
        "trust_sha256": trust_sha,
    }


def _read_contract(path: Path) -> bytes:
    total = 0
    trust_body: bytes | None = None
    try:
        with tarfile.open(path, "r:*") as tar:
            members = tar.getmembers()
            if len(members) == 0 or len(members) > 200:
                raise lab.GuardAbort("bundle_contract")
            names = [member.name for member in members]
            if "guest_rows.py" not in names or "fixtures/grant.json" not in names:
                raise lab.GuardAbort("bundle_contract")
            if TRUST_MEMBER not in names:
                raise lab.GuardAbort("bundle_trust")
            for member in members:
                if _member_refused(member.name):
                    raise lab.GuardAbort(
                        "bundle_private_key" if member.name.endswith("private-key.pem") else "bundle_contract"
                    )
                if member.isdir():
                    continue
                if not member.isfile():
                    raise lab.GuardAbort("bundle_contract")
                if member.size < 0 or member.size > MAX_MEMBER_BYTES:
                    raise lab.GuardAbort("bundle_contract")
                total += member.size
                if total > MAX_CONTRACT_BYTES:
                    raise lab.GuardAbort("bundle_contract")
                handle = tar.extractfile(member)
                if handle is None:
                    raise lab.GuardAbort("bundle_contract")
                body = handle.read()
                if len(body) != member.size:
                    raise lab.GuardAbort("bundle_contract")
                if PRIVATE_KEY_TEXT.search(body):
                    raise lab.GuardAbort("bundle_private_key")
                if member.name == TRUST_MEMBER:
                    trust_body = body
    except tarfile.TarError:
        raise lab.GuardAbort("bundle_contract") from None
    if trust_body is None:
        raise lab.GuardAbort("bundle_trust")
    try:
        payload = json.loads(trust_body)
    except json.JSONDecodeError:
        raise lab.GuardAbort("bundle_trust") from None
    keys = payload.get("keys") if isinstance(payload, dict) else None
    if not isinstance(keys, list) or len(keys) != 1 or not isinstance(keys[0], dict):
        raise lab.GuardAbort("bundle_trust")
    key = keys[0]
    if key.get("not_a_production_root") is not True:
        raise lab.GuardAbort("bundle_production_root")
    if key.get("environment") != "NON-PRODUCTION" or key.get("label") != "TEST":
        raise lab.GuardAbort("bundle_trust")
    if key.get("key_id") != TRUST_KEY_ID:
        raise lab.GuardAbort("bundle_trust")
    return trust_body


def commit_download_args(name: str, commit: str) -> list[str]:
    if name not in BUNDLE_FILES or HEX40.fullmatch(commit) is None:
        raise lab.GuardAbort("bundle_download")
    return [
        "gh",
        "api",
        "-H",
        "Accept: application/vnd.github.raw",
        f"repos/{BUNDLE_REPO}/contents/lab-bundle/{name}?ref={commit}",
    ]


def download_commit_assets(token: str, commit: str, dest: Path) -> None:
    """Download the three bundle files from a commit. The token stays in the environment."""
    if not token or HEX40.fullmatch(commit) is None:
        raise lab.GuardAbort("bundle_download")
    dest.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.pop("GH_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)
    env["GH_TOKEN"] = token
    for name in BUNDLE_FILES:
        proc = subprocess.run(
            commit_download_args(name, commit),
            capture_output=True,
            check=False,
            env=env,
        )
        if proc.returncode != 0 or not proc.stdout:
            raise lab.GuardAbort("bundle_download")
        (dest / name).write_bytes(proc.stdout)


def download_release_assets(token: str, tag: str, dest: Path) -> None:
    """Download three release assets. The token stays in the environment."""
    if not token or BUNDLE_TAG.fullmatch(tag) is None:
        raise lab.GuardAbort("bundle_download")
    dest.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.pop("GH_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)
    env["GH_TOKEN"] = token
    proc = subprocess.run(
        [
            "gh",
            "release",
            "download",
            tag,
            "--repo",
            BUNDLE_REPO,
            "--pattern",
            "manifest.json",
            "--pattern",
            "seal.oci.tar",
            "--pattern",
            "contract.tar",
            "--dir",
            str(dest),
            "--clobber",
        ],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )
    if proc.returncode != 0:
        raise lab.GuardAbort("bundle_download")


def _evidence_text(payload: dict[str, object], token: str) -> None:
    text = json.dumps(payload)
    if token and token in text:
        raise lab.GuardAbort("token_in_evidence")
    if "PRIVATE KEY" in text or "BEGIN OPENSSH" in text:
        raise lab.GuardAbort("token_in_evidence")


def prepare_bundle(
    *,
    fetcher: Fetcher | None = None,
    expected_seal: str = POLICY_ALLOW_SEAL,
    expected_trust: str = TRUST_BUNDLE_SHA256,
) -> dict[str, object]:
    """Download and check the bundle. This function does not call AWS."""
    from w3_lab_steps import base_evidence, evidence_path, github_output

    token = os.environ.get("W3_LAB_PRIVATE_BUNDLE_TOKEN", "")
    tag = os.environ.get("W3_BUNDLE_TAG", DEFAULT_BUNDLE_TAG).strip()
    dest = Path(os.environ.get("W3_BUNDLE_DIR", "enterprise-bundle"))
    payload: dict[str, object] = base_evidence("bundle")
    payload["bundle_commit"] = BUNDLE_COMMIT
    payload["tag"] = ""
    try:
        if token.strip() == "":
            raise lab.GuardAbort("missing_token")
        if tag and BUNDLE_TAG.fullmatch(tag) is None:
            raise lab.GuardAbort("bundle_tag")
        if fetcher is None:
            download_commit_assets(token, BUNDLE_COMMIT, dest)
        else:
            fetcher(dest)
        payload.update(inspect_bundle(dest, expected_seal=expected_seal, expected_trust=expected_trust))
        payload["status"] = "BUNDLE_READY"
        github_output("ready", "true")
    except lab.GuardAbort as exc:
        payload["reason"] = exc.reason
        payload["status"] = "BLOCKED_BUNDLE"
        github_output("ready", "false")
        _evidence_text(payload, token)
        lab.write_json_with_hash(evidence_path("w3-lab-bundle.json"), payload)
        raise
    _evidence_text(payload, token)
    lab.write_json_with_hash(evidence_path("w3-lab-bundle.json"), payload)
    return payload
