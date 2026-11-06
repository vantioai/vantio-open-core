#!/usr/bin/env python3
"""Mint one lab-only Ed25519 stop key for a single proof run.

The key id starts with dev-nonprod-lab-. The trust file says it is not a
production root. The private seed is raw bytes in the lab directory, not a
PEM and not a production path. Nothing here is printed.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import sys
import time
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat


def _canonical(policy: dict) -> bytes:
    return json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()


def _public_b64(key: Ed25519PrivateKey) -> str:
    raw = key.public_key().public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
    return base64.b64encode(raw).decode("ascii")


def _document(key: Ed25519PrivateKey, key_id: str, policy: dict) -> dict:
    if not key_id.startswith("dev-nonprod-lab-"):
        raise SystemExit("lab_key")
    signature = key.sign(_canonical(policy))
    return {
        "policy": policy,
        "signature": {
            "algorithm": "Ed25519",
            "key_class": "dev_non_production",
            "key_id": key_id,
            "not_a_production_root": True,
            "public_key_b64": _public_b64(key),
            "signature_b64": base64.b64encode(signature).decode("ascii"),
        },
    }


def _load_key(root: Path) -> tuple[Ed25519PrivateKey, str]:
    seed = (root / "seed").read_bytes()
    if len(seed) != 32:
        raise SystemExit("lab_key")
    key = Ed25519PrivateKey.from_private_bytes(seed)
    key_id = (root / "key-id").read_text(encoding="utf-8").strip()
    if not key_id.startswith("dev-nonprod-lab-"):
        raise SystemExit("lab_key")
    return key, key_id


def _lab_root() -> Path:
    trust = os.environ.get("VANTIO_LAB_DEV_TRUST", "")
    if not trust:
        raise SystemExit("lab_trust")
    return Path(trust).resolve().parent


def init(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    seed = key.private_bytes(encoding=Encoding.Raw, format=PrivateFormat.Raw, encryption_algorithm=NoEncryption())
    if b"PRIVATE KEY" in seed:
        raise SystemExit("lab_key")
    key_id = "dev-nonprod-lab-" + secrets.token_hex(4)
    (root / "seed").write_bytes(seed)
    os.chmod(root / "seed", 0o600)
    (root / "key-id").write_text(key_id + "\n", encoding="utf-8")
    trust = {
        "audience": "LAB_NONPROD",
        "not_a_production_root": True,
        "keys": [
            {
                "key_class": "dev_non_production",
                "key_id": key_id,
                "not_a_production_root": True,
                "public_key_b64": _public_b64(key),
            }
        ],
    }
    proof = secrets.token_bytes(32)
    if proof == b"\x00" * 32:
        proof = b"\x01" + proof[1:]
    policy = {"action": "stop", "exp": int(time.time()) + 7200, "proof_b64": base64.b64encode(proof).decode("ascii")}
    (root / "trust.json").write_text(json.dumps(trust), encoding="utf-8")
    (root / "stop.json").write_text(json.dumps(_document(key, key_id, policy)), encoding="utf-8")
    env = "\n".join(
        [
            "VANTIO_LAB_SCOPE=lab-nonprod",
            f"VANTIO_LAB_DEV_TRUST={root / 'trust.json'}",
            f"VANTIO_LAB_STOP_TOKEN={root / 'stop.json'}",
            "",
        ]
    )
    (root / "env").write_text(env, encoding="utf-8")
    os.chmod(root / "env", 0o600)


def _write_exception(dest: Path, cgroup: str, exp: int) -> None:
    key, key_id = _load_key(_lab_root())
    policy = {"except_cgroups": [cgroup], "exp": exp}
    dest.write_text(json.dumps(_document(key, key_id, policy)), encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        return 2
    command = argv[1]
    if command == "init" and len(argv) == 3:
        init(Path(argv[2]))
        return 0
    if command == "exception" and len(argv) == 4:
        _write_exception(Path(argv[2]) / "exceptions.json", argv[3], int(time.time()) + 3600)
        return 0
    if command == "expired-exception" and len(argv) == 4:
        _write_exception(Path(argv[2]) / "expired.json", argv[3], int(time.time()) - 10)
        return 0
    if command == "unsigned" and len(argv) == 4:
        dest = Path(argv[2]) / "unsigned.json"
        dest.write_text(json.dumps({"policy": {"except_cgroups": [argv[3]], "exp": int(time.time()) + 3600}}), encoding="utf-8")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
