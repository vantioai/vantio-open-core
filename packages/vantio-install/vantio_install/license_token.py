"""Offline Phantom Engine license tokens.

A token is ``vl1.`` + base64url(payload JSON) + ``.`` + base64url(Ed25519
signature over the ASCII bytes ``vl1.`` + payload_b64). The signature covers
those exact characters. The payload is not re-serialized before the check.

The packaged trust file ships empty. Tests inject keys through
``license_trust_override``. The command line cannot set that override.
The accepted token is stored at mode 0600 and is never copied into a
health record. Health keeps sub, qty, interval, exp, and kid.
"""

from __future__ import annotations

import base64
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_PACKAGED = Path(__file__).resolve().parent / "trust" / "license-public-keys.json"
_OVERRIDE: tuple[dict, ...] | None = None
_FIELDS = ("v", "kid", "sku", "cus", "sub", "qty", "interval", "iat", "exp", "mode")
_PUBLIC_FIELDS = ("sub", "qty", "interval", "exp", "kid")


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def b64url_decode(text: str) -> bytes:
    if not text or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for char in text):
        raise ValueError("base64url")
    pad = "=" * ((4 - len(text) % 4) % 4)
    return base64.urlsafe_b64decode(text + pad)


def issue_token(payload: dict, private_key) -> str:
    """Sign one token. Tests call this. The private key is not stored."""
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = b64url_encode(raw)
    signed = b"vl1." + payload_b64.encode("ascii")
    signature = private_key.sign(signed)
    return "vl1." + payload_b64 + "." + b64url_encode(signature)


def public_license_fields(payload: dict) -> dict:
    return {key: payload[key] for key in _PUBLIC_FIELDS}


def packaged_license_keys() -> tuple[dict, ...]:
    if not _PACKAGED.is_file():
        return ()
    try:
        return keys_from_mapping(json.loads(_PACKAGED.read_text(encoding="utf-8")))
    except (OSError, ValueError, json.JSONDecodeError):
        return ()


def keys_from_mapping(payload: object) -> tuple[dict, ...]:
    if not isinstance(payload, dict) or not isinstance(payload.get("keys"), list):
        return ()
    keys: list[dict] = []
    for item in payload["keys"]:
        parsed = _parse_key(item)
        if parsed is not None:
            keys.append(parsed)
    return tuple(keys)


def active_license_keys() -> tuple[dict, ...]:
    if _OVERRIDE is not None:
        return _OVERRIDE
    return packaged_license_keys()


@contextmanager
def license_trust_override(keys: tuple[dict, ...] | list[dict]) -> Iterator[None]:
    """Test-only trust override. The command line cannot set this."""
    global _OVERRIDE
    previous = _OVERRIDE
    normalized: list[dict] = []
    for item in keys:
        parsed = _parse_key(item)
        if parsed is None:
            raise ValueError("license trust key")
        normalized.append(parsed)
    _OVERRIDE = tuple(normalized)
    try:
        yield
    finally:
        _OVERRIDE = previous


def verify_token(token: str, *, keys: tuple[dict, ...] | None = None, now: int | None = None) -> dict:
    """Verify one token. The result never includes the token."""
    trust = active_license_keys() if keys is None else keys
    clock = int(time.time()) if now is None else now
    text = token.strip()
    parts = text.split(".")
    if len(parts) != 3 or parts[0] != "vl1" or not parts[1] or not parts[2]:
        return _refused("MALFORMED")
    try:
        raw = b64url_decode(parts[1])
        signature = b64url_decode(parts[2])
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError, json.JSONDecodeError):
        return _refused("MALFORMED")
    if not isinstance(payload, dict) or set(payload) != set(_FIELDS):
        return _refused("MALFORMED")
    reason = _payload_reason(payload)
    if reason is not None:
        body = _refused(reason)
        if reason == "EXPIRED":
            body["exp"] = payload.get("exp")
        return body
    kid = payload["kid"]
    pinned = next((item for item in trust if item["kid"] == kid), None)
    if pinned is None:
        return _refused("UNKNOWN_KID")
    if pinned["mode"] != payload["mode"]:
        return _refused("MODE_MISMATCH")
    signed = b"vl1." + parts[1].encode("ascii")
    try:
        Ed25519PublicKey.from_public_bytes(pinned["public_key"]).verify(signature, signed)
    except (InvalidSignature, ValueError):
        return _refused("BAD_SIGNATURE")
    if clock >= int(payload["exp"]):
        return _refused("EXPIRED", exp=int(payload["exp"]))
    return {
        "ok": True,
        "reason": "VERIFIED",
        "payload": payload,
        "license": public_license_fields(payload),
    }


def store_license(token: str, path: Path) -> None:
    """Write the accepted token at mode 0600. Callers do not log the token."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, token.strip().encode("ascii") + b"\n")
        os.fsync(fd)
    finally:
        os.close(fd)
    os.chmod(path, 0o600)


def read_stored_license(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError):
        return None


def _parse_key(item: object) -> dict | None:
    if not isinstance(item, dict):
        return None
    kid = item.get("kid")
    mode = item.get("mode")
    raw_b64 = item.get("public_key_b64")
    if item.get("alg") != "Ed25519":
        return None
    if not isinstance(kid, str) or not kid or any(char.isspace() for char in kid):
        return None
    if mode not in {"test", "live"} or not isinstance(raw_b64, str):
        return None
    try:
        raw = base64.b64decode(raw_b64, validate=True)
    except ValueError:
        return None
    if len(raw) != 32:
        return None
    return {"kid": kid, "alg": "Ed25519", "mode": mode, "public_key": raw, "public_key_b64": raw_b64}


def _payload_reason(payload: dict) -> str | None:
    if type(payload.get("v")) is not int or payload["v"] != 1:
        return "MALFORMED"
    kid = payload.get("kid")
    if not isinstance(kid, str) or not kid or any(char.isspace() for char in kid):
        return "MALFORMED"
    if payload.get("sku") != "phantom-engine":
        return "SKU_MISMATCH"
    for key in ("cus", "sub"):
        value = payload.get(key)
        if not isinstance(value, str) or not value or any(char.isspace() for char in value):
            return "MALFORMED"
    if type(payload.get("qty")) is not int or payload["qty"] < 1:
        return "MALFORMED"
    if payload.get("interval") not in {"month", "year"}:
        return "MALFORMED"
    if type(payload.get("iat")) is not int or type(payload.get("exp")) is not int:
        return "MALFORMED"
    if payload.get("mode") not in {"test", "live"}:
        return "MALFORMED"
    return None


def _refused(reason: str, **extra: object) -> dict:
    body = {"ok": False, "reason": reason, "payload": None, "license": None}
    body.update(extra)
    return body
