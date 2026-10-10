"""Signed policy loading. Unsigned policy is not applied.

Trust is a set of dev public keys. A key named inside the policy file is
not trusted unless that same public key is in the set. Production roots
and any key id that does not start with ``dev-nonprod-`` are refused.
The private key is not in this package.
"""

from __future__ import annotations

import base64
import json
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_DEV_PREFIX = "dev-nonprod-"
_DEV_CLASS = "dev_non_production"
_PACKAGED = Path(__file__).resolve().parent / "trust" / "dev-public-keys.json"
_OVERRIDE: tuple["DevPublicKey", ...] | None = None


@dataclass(frozen=True)
class DevPublicKey:
    key_id: str
    public_key: bytes


@dataclass(frozen=True)
class SignedPolicyResult:
    ok: bool
    reason: str
    policy: dict | None


def canonical_policy(policy: dict) -> bytes:
    return json.dumps(policy, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def packaged_dev_trust() -> tuple[DevPublicKey, ...]:
    if not _PACKAGED.is_file():
        return ()
    return trust_from_mapping(json.loads(_PACKAGED.read_text(encoding="utf-8")))


def trust_from_mapping(payload: object) -> tuple[DevPublicKey, ...]:
    if not isinstance(payload, dict) or not isinstance(payload.get("keys"), list):
        return ()
    keys: list[DevPublicKey] = []
    for item in payload["keys"]:
        if not isinstance(item, dict):
            continue
        key_id = item.get("key_id")
        public_b64 = item.get("public_key_b64")
        if item.get("key_class") != _DEV_CLASS or item.get("not_a_production_root") is not True:
            continue
        if not isinstance(key_id, str) or not key_id.startswith(_DEV_PREFIX):
            continue
        if not isinstance(public_b64, str):
            continue
        try:
            raw = base64.b64decode(public_b64, validate=True)
        except ValueError:
            continue
        if len(raw) != 32:
            continue
        keys.append(DevPublicKey(key_id, raw))
    return tuple(keys)


def active_dev_trust() -> tuple[DevPublicKey, ...]:
    if _OVERRIDE is not None:
        return _OVERRIDE
    return packaged_dev_trust()


@contextmanager
def dev_trust(keys: tuple[DevPublicKey, ...]) -> Iterator[None]:
    """Test-only trust override. The live default is the packaged dev set."""
    global _OVERRIDE
    previous = _OVERRIDE
    _OVERRIDE = keys
    try:
        yield
    finally:
        _OVERRIDE = previous


def verify_signed_policy(document: object, *, trust: tuple[DevPublicKey, ...] | None = None) -> SignedPolicyResult:
    """Return the policy only when a dev key in the trust set signed it."""
    keys = active_dev_trust() if trust is None else trust
    if not isinstance(document, dict):
        return SignedPolicyResult(False, "UNSIGNED_POLICY", None)
    policy = document.get("policy")
    signature = document.get("signature")
    if not isinstance(policy, dict) or not isinstance(signature, dict):
        return SignedPolicyResult(False, "UNSIGNED_POLICY", None)
    if set(document) != {"policy", "signature"}:
        return SignedPolicyResult(False, "MALFORMED", None)
    reason = _signature_ok(policy, signature, keys)
    if reason != "VERIFIED":
        return SignedPolicyResult(False, reason, None)
    return SignedPolicyResult(True, "VERIFIED", policy)


def sign_policy(policy: dict, *, key_id: str, public_key: bytes, sign) -> dict:
    if not key_id.startswith(_DEV_PREFIX):
        raise ValueError("dev key id required")
    raw = sign(canonical_policy(policy))
    return {
        "policy": policy,
        "signature": {
            "algorithm": "Ed25519",
            "key_class": _DEV_CLASS,
            "key_id": key_id,
            "not_a_production_root": True,
            "public_key_b64": base64.b64encode(public_key).decode("ascii"),
            "signature_b64": base64.b64encode(raw).decode("ascii"),
        },
    }


def _signature_ok(policy: dict, signature: dict, trust: tuple[DevPublicKey, ...]) -> str:
    if signature.get("algorithm") != "Ed25519":
        return "ALGORITHM_REFUSED"
    if signature.get("key_class") != _DEV_CLASS or signature.get("not_a_production_root") is not True:
        return "PRODUCTION_KEY_REFUSED"
    key_id = signature.get("key_id")
    if not isinstance(key_id, str) or not key_id.startswith(_DEV_PREFIX):
        return "PRODUCTION_KEY_REFUSED"
    try:
        presented = base64.b64decode(str(signature.get("public_key_b64")), validate=True)
        raw_signature = base64.b64decode(str(signature.get("signature_b64")), validate=True)
    except ValueError:
        return "SIGNATURE_INVALID"
    pinned = next((item.public_key for item in trust if item.key_id == key_id), None)
    if pinned is None or presented != pinned:
        return "UNTRUSTED_DEV_KEY"
    try:
        Ed25519PublicKey.from_public_bytes(pinned).verify(raw_signature, canonical_policy(policy))
    except (InvalidSignature, ValueError):
        return "SIGNATURE_INVALID"
    return "VERIFIED"
