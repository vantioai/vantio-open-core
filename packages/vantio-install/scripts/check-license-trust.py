#!/usr/bin/env python3
"""Check the packaged license trust file after the public key is pasted.

Reads one local JSON file. It does not read the environment, does not
accept a URL, and does not treat a placeholder row as a key. Prints
PASS or FAIL.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

_DEFAULT = Path(__file__).resolve().parents[1] / "vantio_install" / "trust" / "license-public-keys.json"
_LIVE_KID = "lic-live-2026-10"
_LIVE_FIELDS = frozenset({"kid", "alg", "public_key_b64", "mode"})
_ALPHABET = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
_PRIVATE_MARK = "PRIVATE KEY"


def _add(failures: list[str], message: str) -> None:
    if message not in failures:
        failures.append(message)


def _pem(text: str) -> bool:
    return _PRIVATE_MARK in text


def decode_standard_b64(text: str) -> bytes | None:
    """Return raw bytes for canonical standard base64, or None."""
    if not text or len(text) % 4 != 0:
        return None
    if any(char not in _ALPHABET for char in text):
        return None
    if "=" in text.rstrip("="):
        return None
    try:
        raw = base64.b64decode(text, validate=True)
    except ValueError:
        return None
    if base64.b64encode(raw).decode("ascii") != text:
        return None
    return raw


def _note_key_material(value: str, failures: list[str]) -> None:
    if _pem(value):
        _add(failures, "private-key material")
        return
    raw = decode_standard_b64(value)
    if raw is None:
        return
    if _PRIVATE_MARK.encode("ascii") in raw:
        _add(failures, "private-key material")
        return
    if len(raw) == 64:
        _add(failures, "private-key material")


def _check_public(value: object, failures: list[str]) -> None:
    if not isinstance(value, str) or _pem(value):
        if isinstance(value, str) and _pem(value):
            _add(failures, "private-key material")
        _add(failures, "public_key_b64 must be standard padded base64 of 32 bytes")
        return
    raw = decode_standard_b64(value)
    if raw is None:
        _add(failures, "public_key_b64 must be standard padded base64 of 32 bytes")
        return
    if _PRIVATE_MARK.encode("ascii") in raw or len(raw) == 64:
        _add(failures, "private-key material")
        return
    if len(raw) != 32:
        _add(failures, "public_key_b64 must be standard padded base64 of 32 bytes")


def _walk_strings(node: object, failures: list[str]) -> None:
    if isinstance(node, str):
        _note_key_material(node, failures)
        return
    if isinstance(node, dict):
        for value in node.values():
            _walk_strings(value, failures)
        return
    if isinstance(node, list):
        for value in node:
            _walk_strings(value, failures)


def check_text(text: str) -> list[str]:
    """Return failure reasons. An empty list means the file passes."""
    failures: list[str] = []
    if _pem(text):
        _add(failures, "private-key material")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        _add(failures, "trust file is not a JSON object with a keys array")
        return failures
    if not isinstance(payload, dict) or not isinstance(payload.get("keys"), list):
        _add(failures, "trust file is not a JSON object with a keys array")
        return failures
    keys = payload["keys"]
    live_rows = [item for item in keys if isinstance(item, dict) and item.get("mode") == "live"]
    if len(keys) != 1 or len(live_rows) != 1:
        _add(failures, "expected exactly one live row")
    kids = [item.get("kid") for item in keys if isinstance(item, dict) and isinstance(item.get("kid"), str)]
    if any(kids.count(kid) > 1 for kid in kids):
        _add(failures, "duplicate kid")
    if len(live_rows) == 1:
        row = live_rows[0]
        if row.get("kid") != _LIVE_KID:
            _add(failures, "live kid must be lic-live-2026-10")
        if row.get("alg") != "Ed25519":
            _add(failures, "live alg must be Ed25519")
        if "placeholder" in row:
            _add(failures, "placeholder row is not a trusted key")
        if not set(row).issubset(_LIVE_FIELDS):
            _add(failures, "live row has a field other than kid, alg, public_key_b64, and mode")
        _check_public(row.get("public_key_b64"), failures)
    _walk_strings(payload, failures)
    return failures


def check_path(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ["trust file is not readable"]
    return check_text(text)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) > 1 or any(arg.startswith("-") or "://" in arg for arg in args):
        print("FAIL")
        print("usage: python3 scripts/check-license-trust.py [trust-file]", file=sys.stderr)
        return 1
    path = _DEFAULT if not args else Path(args[0])
    failures = check_path(path)
    if failures:
        print("FAIL")
        for item in failures:
            print(item, file=sys.stderr)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
