"""Ephemeral dev keys for installer tests. The private key is not stored."""

from __future__ import annotations

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from vantio_install.signed_policy import DevPublicKey, sign_policy


def ephemeral_dev_key(key_id: str = "dev-nonprod-test") -> tuple[Ed25519PrivateKey, DevPublicKey]:
    if not key_id.startswith("dev-nonprod-"):
        raise ValueError("dev key id required")
    private = Ed25519PrivateKey.generate()
    raw = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private, DevPublicKey(key_id, raw)


def signed_envelope(policy: dict, private: Ed25519PrivateKey, key: DevPublicKey) -> dict:
    return sign_policy(policy, key_id=key.key_id, public_key=key.public_key, sign=private.sign)


def public_b64(key: DevPublicKey) -> str:
    return base64.b64encode(key.public_key).decode("ascii")
