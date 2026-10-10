#!/usr/bin/env python3
"""Stage a lab-only trust pair and a pin-checked installer bundle.

Private keys stay in memory and are not written. Public files are labelled
LAB_NONPROD and are not a production signing root. The packaged trust files
in vantio-install stay empty. A file is copied into the bundle only when its
sha256 is the frozen pin. A different file is not renamed onto that pin.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import subprocess
import sys
import tarfile
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from vantio_install import constants
from vantio_install.artifact_verify import canonical_descriptor
from vantio_install.signed_policy import sign_policy

ARTIFACT_ID = "test-nonprod-artifact-lab-ci"
DEV_ID = "dev-nonprod-lab-ci"
POLICY = {"enforcement": "NOT_ENABLED", "install_mode": "observe-only"}
AUDIENCE = "LAB_NONPROD"
_PRIVATE_PEM = re.compile(br"-----BEGIN [A-Z ]*PRIVATE KEY-----")


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def place_if_pin(source: Path, dest: Path, expected: str) -> bool:
    """Copy source to dest only when the bytes are the frozen pin."""
    if not source.is_file() or len(expected) != 64:
        return False
    if _sha256(source) != expected:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(source.read_bytes())
    return True


def _public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes_raw()


def _trust(key_id: str, key_class: str, public: bytes) -> dict:
    return {
        "audience": AUDIENCE,
        "not_a_production_root": True,
        "keys": [
            {
                "key_class": key_class,
                "key_id": key_id,
                "not_a_production_root": True,
                "public_key_b64": _b64(public),
            }
        ],
    }


def _signature(archive: Path, private: Ed25519PrivateKey, public: bytes) -> dict:
    document = {
        "filename": archive.name,
        "sha256": _sha256(archive),
        "size_bytes": archive.stat().st_size,
    }
    signature = private.sign(canonical_descriptor(document))
    return {
        "document": document,
        "key_class": "test_non_production",
        "key_id": ARTIFACT_ID,
        "not_a_production_root": True,
        "public_key_b64": _b64(public),
        "signature_b64": _b64(signature),
    }


def _manifest(pins: dict) -> dict:
    return {
        "manifest_version": constants.MANIFEST_VERSION,
        "bundle_id": "vantio-node-bundle-lab-nonprod",
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


def _phantom(pins: dict) -> dict:
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


def _refresh_sums(bundle: Path) -> None:
    rows = []
    for path in sorted(bundle.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            rel = path.relative_to(bundle).as_posix()
            rows.append(f"{_sha256(path)}  {rel}")
    (bundle / "SHA256SUMS").write_text("\n".join(rows) + "\n", encoding="utf-8")


def _copy_pinned(source_dir: Path | None, bundle: Path, pins: dict) -> list[str]:
    if source_dir is None or not source_dir.is_dir():
        return []
    placed: list[str] = []
    optics = bundle / "artifacts" / "optics"
    pe = bundle / "artifacts" / "phantom-engine"
    mapping = (
        (pins["optics_cli_filename"], pins["optics_cli_sha256"], optics),
        (pins["agent_sdk_npm_filename"], pins["agent_sdk_npm_sha256"], optics),
        (pins["agent_sdk_py_wheel"], pins["agent_sdk_py_wheel_sha256"], optics),
        (pins["agent_sdk_py_sdist"], pins["agent_sdk_py_sdist_sha256"], optics),
        (pins["pe_archive_name"], pins["pe_archive_sha256"], pe),
    )
    for name, expected, folder in mapping:
        if place_if_pin(source_dir / name, folder / name, expected):
            placed.append(name)
    return placed


def _refuse_tree(directory: Path) -> None:
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(directory).as_posix()
        if ".." in rel.split("/") or path.name in {"contract.tar", "private-key.pem"} or path.suffix == ".pem":
            raise SystemExit("self_service_layout")
        blob = path.read_bytes()
        if _PRIVATE_PEM.search(blob):
            raise SystemExit("private_key")


def pack(directory: Path, dest: Path) -> None:
    """Pack the staged tree. The tar is not a member of itself."""
    _refuse_tree(directory)
    if dest.exists():
        dest.unlink()
    with tarfile.open(dest, "w") as tar:
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.resolve() == dest.resolve():
                continue
            rel = path.relative_to(directory).as_posix()
            if rel == "self-service.tar" or ".." in rel.split("/"):
                continue
            tar.add(path, arcname=rel, recursive=False)
    _refuse_tree(directory)


def stage(dest: Path, pinned_dir: Path | None = None) -> dict[str, object]:
    pins = constants.FROZEN_PINS
    artifact = Ed25519PrivateKey.generate()
    dev = Ed25519PrivateKey.generate()
    artifact_pub = _public(artifact)
    dev_pub = _public(dev)
    dest.mkdir(parents=True, exist_ok=True)
    bundle = dest / "bundle"
    pe = bundle / "artifacts" / "phantom-engine"
    pe.mkdir(parents=True, exist_ok=True)
    placed = _copy_pinned(pinned_dir, bundle, pins)
    archive = pe / pins["pe_archive_name"]
    matched = archive.is_file() and _sha256(archive) == pins["pe_archive_sha256"]
    (dest / "lab-artifact-trust.json").write_text(
        json.dumps(_trust(ARTIFACT_ID, "test_non_production", artifact_pub), indent=2) + "\n",
        encoding="utf-8",
    )
    (dest / "lab-dev-trust.json").write_text(
        json.dumps(_trust(DEV_ID, "dev_non_production", dev_pub), indent=2) + "\n",
        encoding="utf-8",
    )
    envelope = sign_policy(POLICY, key_id=DEV_ID, public_key=dev_pub, sign=dev.sign)
    (dest / "policy.json").write_text(json.dumps(envelope, indent=2) + "\n", encoding="utf-8")
    if matched:
        record = _signature(archive, artifact, artifact_pub)
    else:
        record = {"audience": AUDIENCE, "archive": "absent", "not_a_production_root": True}
    (dest / "signature.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    (pe / "PHANTOM-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(_phantom(pins), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (bundle / "MANIFEST.json").write_text(
        json.dumps(_manifest(pins), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _refresh_sums(bundle)
    return {
        "archive_pin_match": matched,
        "audience": AUDIENCE,
        "not_a_production_root": True,
        "placed": placed,
    }


def _run(argv: list[str], cwd: Path) -> None:
    subprocess.run(argv, check=False, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def fetch_pinned(dest: Path) -> list[str]:
    """Download public pin files. Keep a file only when the hash matches."""
    dest.mkdir(parents=True, exist_ok=True)
    scratch = dest / ".fetch"
    if scratch.exists():
        for child in scratch.iterdir():
            if child.is_file():
                child.unlink()
    scratch.mkdir(exist_ok=True)
    pins = constants.FROZEN_PINS
    _run(
        [
            "gh",
            "release",
            "download",
            "custody-py-3.1.0",
            "--repo",
            "vantioai/vantio-open-core",
            "--dir",
            str(scratch),
            "--clobber",
            "--pattern",
            pins["agent_sdk_py_wheel"],
            "--pattern",
            pins["agent_sdk_py_sdist"],
        ],
        scratch,
    )
    _run(["npm", "pack", "@vantio/cli@0.3.24", "--ignore-scripts", "--pack-destination", str(scratch)], scratch)
    _run(["npm", "pack", "@vantio/agent-sdk@0.2.4", "--ignore-scripts", "--pack-destination", str(scratch)], scratch)
    kept: list[str] = []
    expected = {
        pins["agent_sdk_py_wheel"]: pins["agent_sdk_py_wheel_sha256"],
        pins["agent_sdk_py_sdist"]: pins["agent_sdk_py_sdist_sha256"],
        pins["optics_cli_filename"]: pins["optics_cli_sha256"],
        pins["agent_sdk_npm_filename"]: pins["agent_sdk_npm_sha256"],
        pins["pe_archive_name"]: pins["pe_archive_sha256"],
    }
    for path in scratch.iterdir():
        if not path.is_file():
            continue
        digest = _sha256(path)
        for name, pin in expected.items():
            if digest == pin:
                target = dest / name
                target.write_bytes(path.read_bytes())
                kept.append(name)
                break
        path.unlink()
    return sorted(set(kept))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        raise SystemExit("usage: stage_lab_trust.py stage DEST [PINNED] | fetch DEST")
    if args[0] == "fetch" and len(args) == 2:
        print(json.dumps({"kept": fetch_pinned(Path(args[1]))}, sort_keys=True))
        return 0
    if args[0] == "stage" and len(args) in {2, 3}:
        dest = Path(args[1])
        pinned = Path(args[2]) if len(args) == 3 else None
        result = stage(dest, pinned)
        pack(dest, dest / "self-service.tar")
        result["tar"] = "self-service.tar"
        print(json.dumps(result, sort_keys=True))
        return 0
    raise SystemExit("usage: stage_lab_trust.py stage DEST [PINNED] | fetch DEST")


if __name__ == "__main__":
    raise SystemExit(main())
