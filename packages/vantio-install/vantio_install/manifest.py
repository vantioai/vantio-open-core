"""Bundle manifest load and digest checks against the frozen pin table."""

from __future__ import annotations

import json
from pathlib import Path

from vantio_install import constants
from vantio_install.errors import InstallError
from vantio_install.util import sha256_bytes, sha256_file


def pins() -> dict:
    return constants.FROZEN_PINS


def artifact_paths(bundle: Path, pin: dict | None = None) -> dict[str, Path]:
    pin = pin or pins()
    optics = bundle / "artifacts" / "optics"
    pe = bundle / "artifacts" / "phantom-engine"
    return {
        "optics_cli": optics / pin["optics_cli_filename"],
        "agent_sdk_npm": optics / pin["agent_sdk_npm_filename"],
        "agent_sdk_py_wheel": optics / pin["agent_sdk_py_wheel"],
        "agent_sdk_py_sdist": optics / pin["agent_sdk_py_sdist"],
        "pe_archive": pe / pin["pe_archive_name"],
        "pe_manifest": pe / "PHANTOM-ARTIFACT-MANIFEST.json",
    }


def load_manifest(bundle: Path) -> dict:
    path = bundle / "MANIFEST.json"
    if not path.is_file():
        raise InstallError("Bundle is missing MANIFEST.json.", exit_code=10, state="FAILED_SAFE")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InstallError("MANIFEST.json is not valid JSON.", exit_code=10, state="FAILED_SAFE") from exc
    if not isinstance(data, dict):
        raise InstallError("MANIFEST.json must be an object.", exit_code=10, state="FAILED_SAFE")
    return data


def missing_manifest_fields(manifest: dict) -> list[str]:
    return [field for field in constants.REQUIRED_MANIFEST_FIELDS if field not in manifest]


def bundle_digest(manifest_bytes: bytes) -> str:
    return "sha256:" + sha256_bytes(manifest_bytes)


def verify_sha256sums(bundle: Path) -> list[dict]:
    sums = bundle / "SHA256SUMS"
    if not sums.is_file():
        raise InstallError("Bundle is missing SHA256SUMS.", exit_code=2, state="PREFLIGHT_BLOCKED")
    rows = []
    root = bundle.resolve()
    for line in sums.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) < 2:
            raise InstallError("SHA256SUMS has a malformed line.", exit_code=2, state="PREFLIGHT_BLOCKED")
        expect, rel = parts[0], parts[-1]
        target = (bundle / rel).resolve()
        if root != target and root not in target.parents:
            raise InstallError("SHA256SUMS points outside the bundle.", exit_code=10, state="FAILED_SAFE")
        observed = sha256_file(target) if target.is_file() else None
        rows.append(
            {
                "path": rel,
                "expected_sha256": expect,
                "observed_sha256": observed,
                "match": observed == expect,
            }
        )
    return rows


def hash_named(path: Path) -> str | None:
    if not path.is_file():
        return None
    return sha256_file(path)


def scan_disclosure(path: Path) -> dict:
    found: list[str] = []
    if path.is_file():
        data = path.read_bytes()
        for needle in constants.DISCLOSURE_FORBIDDEN:
            if needle.encode("utf-8") in data:
                found.append(needle)
    return {"path": path.name, "forbidden_hits": found, "pass": not found}
