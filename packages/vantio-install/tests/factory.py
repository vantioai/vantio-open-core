"""Build a fixture bundle whose bytes match an injected pin table."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from vantio_install import constants
from vantio_install.host import ready_host


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pins_for(files: dict[str, bytes]) -> dict:
    pins = copy.deepcopy(constants.FROZEN_PINS)
    pins["optics_cli_sha256"] = sha256(files["cli"])
    pins["agent_sdk_npm_sha256"] = sha256(files["npm"])
    pins["agent_sdk_py_wheel_sha256"] = sha256(files["wheel"])
    pins["pe_archive_sha256"] = sha256(files["archive"])
    return pins


def phantom_manifest(pins: dict) -> dict:
    return {
        "disclosure_status": "PASS",
        "forbidden_path_scan": "PASS",
        "source_commit": pins["pe_source_commit"],
        "archive_sha256": pins["pe_archive_sha256"],
        "manifest_digest": pins["pe_manifest_digest"],
        "config_digest": pins["pe_config_digest"],
        "loader_sha256": pins["pe_loader_sha256"],
        "layer_digests": list(pins["pe_layer_digests"]),
    }


def deployment_manifest(pins: dict) -> dict:
    return {
        "manifest_version": constants.MANIFEST_VERSION,
        "bundle_id": "vantio-node-bundle-1.0.0-stage-a-fab81efc0811-optics-0.3.24",
        "contract_version": constants.CONTRACT_VERSION,
        "proof_ceiling": constants.PROOF_CEILING,
        "products": {
            "optics_cli": pins["optics_cli_version"],
            "agent_sdk_npm": pins["agent_sdk_npm_version"],
            "agent_sdk_py": pins["agent_sdk_py_version"],
            "phantom_engine": pins["pe_source_commit"],
        },
        "artifacts": {
            "optics_cli": {"filename": pins["optics_cli_filename"], "sha256": pins["optics_cli_sha256"]},
            "agent_sdk_npm": {"filename": pins["agent_sdk_npm_filename"], "sha256": pins["agent_sdk_npm_sha256"]},
            "agent_sdk_py_wheel": {"filename": pins["agent_sdk_py_wheel"], "sha256": pins["agent_sdk_py_wheel_sha256"]},
            "pe_archive": {"filename": pins["pe_archive_name"], "sha256": pins["pe_archive_sha256"]},
        },
        "artifact_verification": {"algorithms": ["sha256"]},
        "configuration": {"install_mode": "observe-only", "enforcement": "NOT_ENABLED"},
        "filesystem_paths": {"installer_state": "/var/lib/vantio/install"},
        "privileges": {"docker": "detect", "assume_docker_group": False},
        "kernel_capabilities": {"arch": ["x86_64", "amd64"], "os": ["Ubuntu 24.04 LTS"], "cgroup": "cgroup2"},
        "network_requirements": {"telemetry": "DISABLED", "ghcr_0_1_0": "FORBIDDEN_AS_DEFAULT"},
        "workload_roots": {"customer_declared": True},
        "health": {"unknown_stays_unknown": True},
        "coverage": {"not_tested_stays_not_tested": True},
        "policy": {"enforcement_default": "NOT_ENABLED", "sg_zero_zero": "FORBIDDEN"},
        "evidence": {"required": ["TRANSACTION.json", "HEALTH.json", "RESIDUAL.json"]},
        "transaction": {"failure_terminal": "FAILED_SAFE"},
        "rollback": {"implies_verified_removed": False},
        "uninstall": {"scopes": ["pe", "optics", "all"]},
        "residual_inspection": {"results": ["EMPTY", "RESIDUAL_PRESENT", "UNKNOWN"]},
        "independent_verification": {"trust_installer_exit": False},
        "support_bundle": {"format": "tar.gz"},
        "version_compatibility": {"pe_source_commit": pins["pe_source_commit"]},
        "unsupported_environments": ["non-linux", "non-x86_64"],
        "exclusions": ["credentials", "private keys", "registry tokens"],
        "artifact_source": "sealed_archive",
    }


def write_bundle(root: Path, pins: dict, files: dict[str, bytes]) -> None:
    optics = root / "artifacts" / "optics"
    pe = root / "artifacts" / "phantom-engine"
    optics.mkdir(parents=True, exist_ok=True)
    pe.mkdir(parents=True, exist_ok=True)
    (optics / pins["optics_cli_filename"]).write_bytes(files["cli"])
    (optics / pins["agent_sdk_npm_filename"]).write_bytes(files["npm"])
    (optics / pins["agent_sdk_py_wheel"]).write_bytes(files["wheel"])
    (pe / pins["pe_archive_name"]).write_bytes(files["archive"])
    manifest_doc = phantom_manifest(pins)
    (pe / "PHANTOM-ARTIFACT-MANIFEST.json").write_text(json.dumps(manifest_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    deployment = deployment_manifest(pins)
    (root / "MANIFEST.json").write_text(json.dumps(deployment, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            rel = path.relative_to(root).as_posix()
            rows.append(f"{sha256(path.read_bytes())}  {rel}")
    (root / "SHA256SUMS").write_text("\n".join(rows) + "\n", encoding="utf-8")


def refresh_sums(root: Path) -> None:
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            rel = path.relative_to(root).as_posix()
            rows.append(f"{sha256(path.read_bytes())}  {rel}")
    (root / "SHA256SUMS").write_text("\n".join(rows) + "\n", encoding="utf-8")


def default_files() -> dict[str, bytes]:
    return {
        "cli": b"cli-fixture-bytes\n",
        "npm": b"npm-fixture-bytes\n",
        "wheel": b"wheel-fixture-bytes\n",
        "archive": b"pe-archive-fixture\n",
    }


def host() -> dict:
    return ready_host()
