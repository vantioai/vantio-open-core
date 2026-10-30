#!/usr/bin/env python3
"""Check the private Enterprise row bundle before any AWS call.

The seal file and the contract tar stay in the runner temp directory.
Evidence written here records hashes and reasons. It does not record the
read token, the tar bytes, or a private key.

Audience: INTERNAL_RESTRICTED
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from typing import Callable

import w3_lab_auto as lab


def _load_seal():
    origin = Path(__file__).resolve().parent
    for parent in (origin, *origin.parents):
        for candidate in (parent / "pe_canonical_seal.py", parent / "scripts" / "release" / "pe_canonical_seal.py"):
            if not candidate.is_file():
                continue
            cached = sys.modules.get("pe_canonical_seal")
            if cached is not None:
                return cached
            spec = importlib.util.spec_from_file_location("pe_canonical_seal", candidate)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules["pe_canonical_seal"] = module
            spec.loader.exec_module(module)
            return module
    raise FileNotFoundError("pe_canonical_seal.py")


_SEAL = _load_seal()

# Batteries do not run on the older plumbing-only image. GCP still treats it that way.
PLUMBING_ONLY_SEAL = _SEAL.plumbing_only_seal()
# Zachary, 2026-10-16. Previous working seal prefix: bbb1025d.
POLICY_ALLOW_SEAL = _SEAL.lane_seal()
PUBLIC_INSTALLER_PIN = _SEAL.public_pin()
TRACKING_2A_SEAL = _SEAL.tracking_seal()
TRUST_BUNDLE_SHA256 = "2e4a1da7bf44f0bddfc2a3ce3eda007fa6cc1455332f26769bd346fafc297876"
TRUST_KEY_ID = "test-nonprod-ed25519-2026-10-02"
TRUST_MEMBER = "vantio_enterprise_protocol/trust/test_nonprod_2026_10_02.json"
BUNDLE_SCHEMA = "vantio.lab-enterprise-pe-bundle/v1"
BUNDLE_REPO = "vantioai/vantio-enterprise-private"
DEFAULT_BUNDLE_TAG = "lab-bundle/enterprise-pe-2026-10-08"
# The release tag is deleted. These bytes live on this commit, which is not a tag.
BUNDLE_COMMIT = "75b6a94c1a50f07d3cc419a904ee08260c9c32ff"
BUNDLE_FILES = ("manifest.json", "seal.oci.tar", "contract.tar")
# The public installer archive lives beside the working seal on the lab bundle
# commit. It is not a seal. inspect_bundle still refuses this digest as expected_seal.
PUBLIC_PIN_FILE = "public-pin.oci.tar"
BUNDLE_TAG = re.compile(r"^lab-bundle/[A-Za-z0-9._-]{1,64}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
PRIVATE_KEY_TEXT = re.compile(br"-----BEGIN [A-Z ]*PRIVATE KEY-----")
MAX_MEMBER_BYTES = 2_000_000
MAX_CONTRACT_BYTES = 20_000_000
MAX_SEAL_BYTES = 80_000_000
# Public gh downloads. 401 and 404 are not retried. A digest mismatch is not a download error.
DOWNLOAD_ATTEMPTS = 3
DOWNLOAD_TIMEOUT_SECONDS = 120
DOWNLOAD_BACKOFF_SECONDS = (2, 4)
DOWNLOAD_ERRORS = frozenset({"http_4xx", "http_5xx", "timeout", "empty_body", "oversize", "gh_rc_nonzero"})
_NO_RETRY_HTTP = frozenset({401, 404})
_HTTP_STATUS_RE = re.compile(r"HTTP (\d{3})")
_DOWNLOAD_EVIDENCE_KEYS = frozenset(
    {
        "pin_http_status",
        "pin_error",
        "pin_attempts",
        "bundle_http_status",
        "bundle_error",
        "bundle_attempts",
        "bundle_file",
    }
)
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
    if manifest.get("lab_only") is not True:
        raise lab.GuardAbort("bundle_not_lab_only")
    if manifest.get("customer_release") is not False:
        raise lab.GuardAbort("bundle_customer_release")
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
        "customer_release": False,
        "enterprise_sha": enterprise_sha,
        "lab_only": True,
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


def public_pin_download_args(commit: str) -> list[str]:
    """Fetch the public installer archive from the same pinned bundle commit."""
    if HEX40.fullmatch(commit) is None:
        raise lab.GuardAbort("public_pin_download")
    return [
        "gh",
        "api",
        "-H",
        "Accept: application/vnd.github.raw",
        f"repos/{BUNDLE_REPO}/contents/lab-bundle/{PUBLIC_PIN_FILE}?ref={commit}",
    ]


def http_status_from_stderr(stderr: str) -> int | None:
    """Pull one HTTP status out of gh stderr. The text itself is not kept."""
    match = _HTTP_STATUS_RE.search(stderr)
    if match is None:
        return None
    status = int(match.group(1))
    if 100 <= status <= 599:
        return status
    return None


def classify_download_attempt(
    *,
    returncode: int | None,
    stdout: bytes,
    stderr: str,
    timed_out: bool,
    max_bytes: int | None,
) -> tuple[str | None, int | None]:
    """Return (error enum or None when the body is usable, http status or None).

    Pure. No network. A digest mismatch is not classified here and is not retried.
    """
    status = http_status_from_stderr(stderr)
    if timed_out:
        return "timeout", status
    if returncode != 0:
        if status is not None and 500 <= status <= 599:
            return "http_5xx", status
        if status is not None and 400 <= status <= 499:
            return "http_4xx", status
        return "gh_rc_nonzero", status
    if not stdout:
        return "empty_body", status
    if max_bytes is not None and len(stdout) > max_bytes:
        return "oversize", status
    return None, status


def download_should_retry(error: str, http_status: int | None) -> bool:
    """Retry transport failures. 401 and 404 repeat the same answer."""
    if http_status in _NO_RETRY_HTTP:
        return False
    return error in DOWNLOAD_ERRORS


def _stderr_text(raw: bytes | str | None) -> str:
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return raw


def _download_sleep(seconds: float) -> None:
    time.sleep(seconds)


def _download_fields(
    prefix: str,
    *,
    attempts: int,
    error: str | None = None,
    http_status: int | None = None,
    bundle_file: str | None = None,
) -> dict[str, object]:
    fields: dict[str, object] = {f"{prefix}_attempts": attempts}
    if error is not None:
        fields[f"{prefix}_error"] = error
    if http_status is not None:
        fields[f"{prefix}_http_status"] = http_status
    if bundle_file is not None:
        fields["bundle_file"] = bundle_file
    return fields


def _redacted_download_line(*, http_status: int | None, error: str, attempt: int) -> str:
    shown = str(http_status) if http_status is not None else "none"
    return f"download status={shown} class={error} attempt={attempt}"


def _gh_env(token: str) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("GH_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)
    env["GH_TOKEN"] = token
    return env


def _download_with_retry(
    args: list[str],
    env: dict[str, str],
    *,
    reason: str,
    prefix: str,
    max_bytes: int | None,
    bundle_file: str | None = None,
) -> tuple[bytes, dict[str, object]]:
    """Download once to three times. Raises GuardAbort(reason) on the final failure.

    The exception payload holds only enum and number fields. One redacted line
    goes to stderr when the download is abandoned. gh's stderr is not kept.
    """
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        timed_out = False
        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                check=False,
                env=env,
                timeout=DOWNLOAD_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = exc.output if isinstance(exc.output, bytes) else b""
            stderr = _stderr_text(exc.stderr if isinstance(exc.stderr, (bytes, str)) or exc.stderr is None else None)
            returncode = None
        else:
            stdout = proc.stdout if isinstance(proc.stdout, bytes) else b""
            stderr = _stderr_text(proc.stderr if isinstance(proc.stderr, (bytes, str)) or proc.stderr is None else None)
            returncode = proc.returncode
        error, status = classify_download_attempt(
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            timed_out=timed_out,
            max_bytes=max_bytes,
        )
        if error is None:
            return stdout, _download_fields(prefix, attempts=attempt, bundle_file=None)
        if attempt == DOWNLOAD_ATTEMPTS or not download_should_retry(error, status):
            print(
                _redacted_download_line(http_status=status, error=error, attempt=attempt),
                file=sys.stderr,
            )
            raise lab.GuardAbort(
                reason,
                _download_fields(
                    prefix,
                    attempts=attempt,
                    error=error,
                    http_status=status,
                    bundle_file=bundle_file,
                ),
            ) from None
        _download_sleep(DOWNLOAD_BACKOFF_SECONDS[attempt - 1])
    raise lab.GuardAbort(reason, _download_fields(prefix, attempts=DOWNLOAD_ATTEMPTS, bundle_file=bundle_file)) from None


def _copy_download_fields(payload: dict[str, object], fields: dict[str, object]) -> None:
    for key, value in fields.items():
        if key in _DOWNLOAD_EVIDENCE_KEYS:
            payload[key] = value


def verify_public_pin(path: Path) -> str:
    """Keep the file only when its sha256 is the public installer pin."""
    if not path.is_file():
        raise lab.GuardAbort("public_pin_absent")
    size = path.stat().st_size
    if size <= 0 or size > MAX_SEAL_BYTES:
        raise lab.GuardAbort("public_pin_digest")
    digest = sha256_file(path)
    if digest != PUBLIC_INSTALLER_PIN or digest == POLICY_ALLOW_SEAL:
        raise lab.GuardAbort("public_pin_digest")
    return digest


def stage_public_pin(token: str, commit: str, dest: Path) -> tuple[str, dict[str, object]]:
    """Download public-pin.oci.tar and refuse it unless the digest matches.

    The digest check runs once, after a usable body is on disk. It is not retried.
    """
    if not token or HEX40.fullmatch(commit) is None:
        raise lab.GuardAbort("public_pin_download")
    dest.mkdir(parents=True, exist_ok=True)
    body, fields = _download_with_retry(
        public_pin_download_args(commit),
        _gh_env(token),
        reason="public_pin_download",
        prefix="pin",
        max_bytes=MAX_SEAL_BYTES,
    )
    path = dest / PUBLIC_PIN_FILE
    path.write_bytes(body)
    try:
        digest = verify_public_pin(path)
    except lab.GuardAbort as exc:
        if exc.reason == "public_pin_digest":
            exc.payload = {**exc.payload, "pin_attempts": fields["pin_attempts"]}
        raise
    return digest, fields


def download_commit_assets(token: str, commit: str, dest: Path) -> dict[str, object]:
    """Download the three bundle files from a commit. The token stays in the environment."""
    if not token or HEX40.fullmatch(commit) is None:
        raise lab.GuardAbort("bundle_download")
    dest.mkdir(parents=True, exist_ok=True)
    env = _gh_env(token)
    worst = 1
    slow_file: str | None = None
    for name in BUNDLE_FILES:
        body, fields = _download_with_retry(
            commit_download_args(name, commit),
            env,
            reason="bundle_download",
            prefix="bundle",
            max_bytes=None,
            bundle_file=name,
        )
        attempts = fields["bundle_attempts"]
        if isinstance(attempts, int) and attempts >= worst:
            worst = attempts
            slow_file = name
        (dest / name).write_bytes(body)
    recorded: dict[str, object] = {"bundle_attempts": worst}
    if slow_file is not None and worst > 1:
        recorded["bundle_file"] = slow_file
    return recorded


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
    env_seal = os.environ.get("W3_EXPECTED_SEAL", "").strip().lower()
    if env_seal:
        expected_seal = env_seal
    env_commit = os.environ.get("W3_BUNDLE_COMMIT", "").strip()
    commit = env_commit or BUNDLE_COMMIT
    dest = Path(os.environ.get("W3_BUNDLE_DIR", "enterprise-bundle"))
    payload: dict[str, object] = base_evidence("bundle")
    payload["bundle_commit"] = commit
    payload["tag"] = ""
    try:
        if token.strip() == "":
            raise lab.GuardAbort("missing_token")
        if tag and BUNDLE_TAG.fullmatch(tag) is None:
            raise lab.GuardAbort("bundle_tag")
        if HEX40.fullmatch(commit) is None:
            raise lab.GuardAbort("bundle_download")
        if fetcher is None:
            _copy_download_fields(payload, download_commit_assets(token, commit, dest))
        else:
            fetcher(dest)
        payload.update(inspect_bundle(dest, expected_seal=expected_seal, expected_trust=expected_trust))
        if os.environ.get("W3_BATTERY", "").strip() == "2c-upgrade-rollback":
            digest, pin_fields = stage_public_pin(token, commit, dest)
            payload["public_pin_sha256"] = digest
            _copy_download_fields(payload, pin_fields)
        payload["status"] = "BUNDLE_READY"
        github_output("ready", "true")
    except lab.GuardAbort as exc:
        payload["reason"] = exc.reason
        _copy_download_fields(payload, exc.payload)
        payload["status"] = "BLOCKED_BUNDLE"
        github_output("ready", "false")
        _evidence_text(payload, token)
        lab.write_json_with_hash(evidence_path("w3-lab-bundle.json"), payload)
        raise
    _evidence_text(payload, token)
    lab.write_json_with_hash(evidence_path("w3-lab-bundle.json"), payload)
    return payload
