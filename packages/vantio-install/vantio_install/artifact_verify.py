"""Hash and signature check for a bundle archive.

The public installer pin is not changed here. Verification reads the file.
A non-production test key is required. A production root flag is refused.
Downloads are limited to loopback HTTP. A short read is deleted.
"""

from __future__ import annotations

import base64
import hashlib
import http.client
import json
import os
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_FORBIDDEN = (
    "/home/vantioai",
    "vantio-sandbox",
    "absolute_control/secret.token",
    "phantom-box",
    "phantom.box",
    "phantombox",
)
_SHA = set("0123456789abcdef")
_MAX_BYTES = 64 * 1024 * 1024
_PACKAGED_ARTIFACT = Path(__file__).resolve().parent / "trust" / "artifact-public-keys.json"
_ARTIFACT_OVERRIDE: dict[str, bytes] | None = None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


def verify_archive_file(
    path: Path,
    signature_record: dict,
    *,
    trust_keys: dict[str, bytes] | None = None,
) -> dict:
    """Hash path and verify the detached Ed25519 signature over the descriptor."""
    refused = _key_refusal(signature_record)
    if refused is not None:
        return _result(refused, hashed=False)
    document = signature_record.get("document")
    if not isinstance(document, dict):
        return _result("MALFORMED", hashed=False)
    filename = document.get("filename")
    expected = document.get("sha256")
    size = document.get("size_bytes")
    if not isinstance(filename, str) or not isinstance(expected, str) or type(size) is not int:
        return _result("MALFORMED", hashed=False)
    if _forbidden(filename) or _forbidden(path.name):
        return _result("DISCLOSURE_REFUSED", hashed=False, sha256=expected, filename=filename)
    if len(expected) != 64 or any(char not in _SHA for char in expected):
        return _result("MALFORMED", hashed=False)
    try:
        data = path.read_bytes()
    except OSError:
        return _result("BYTES_UNREADABLE", hashed=False, sha256=expected, filename=filename)
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected or len(data) != size:
        return _result("CORRUPT_ARTIFACT", hashed=True, sha256=digest, filename=filename, byte_count=len(data))
    try:
        public = base64.b64decode(str(signature_record.get("public_key_b64")), validate=True)
        signature = base64.b64decode(str(signature_record.get("signature_b64")), validate=True)
    except ValueError:
        return _result("SIGNATURE_INVALID", hashed=True, sha256=digest, filename=filename, byte_count=len(data))
    pinned = None if trust_keys is None else trust_keys.get(str(signature_record.get("key_id")))
    if pinned is None or pinned != public:
        return _result("UNTRUSTED_KEY", hashed=True, sha256=digest, filename=filename, byte_count=len(data))
    try:
        Ed25519PublicKey.from_public_bytes(pinned).verify(signature, _canonical(document))
    except (InvalidSignature, ValueError, TypeError):
        return _result("SIGNATURE_INVALID", hashed=True, sha256=digest, filename=filename, byte_count=len(data))
    return _result("VERIFIED", hashed=True, sha256=digest, filename=filename, byte_count=len(data), ok=True)


def fetch_to_file(url: str, destination: Path, *, timeout_s: float = 5) -> dict:
    """Download to a temporary file. Keep it only when the body matches Content-Length."""
    reason = _refuse_url(url)
    if reason is not None:
        return {"disposition": "REFUSED", "reason": reason, "fetched": False, "path": None}
    temporary = destination.with_name(destination.name + ".partial")
    if temporary.exists():
        temporary.unlink()
    try:
        opener = urllib.request.build_opener(_NoRedirect)
        with opener.open(url, timeout=timeout_s) as response:
            declared = response.headers.get("Content-Length")
            if declared is not None and int(declared) > _MAX_BYTES:
                raise urllib.error.URLError("too large")
            blob = response.read(_MAX_BYTES + 1)
            if len(blob) > _MAX_BYTES:
                raise urllib.error.URLError("too large")
        if declared is not None and int(declared) != len(blob):
            raise urllib.error.URLError("short read")
        temporary.write_bytes(blob)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, http.client.HTTPException):
        if temporary.exists():
            temporary.unlink()
        return {"disposition": "REFUSED", "reason": "INTERRUPTED_DOWNLOAD", "fetched": False, "path": None}
    os.replace(temporary, destination)
    return {"disposition": "FETCHED", "reason": "FETCHED", "fetched": True, "path": destination}


def packaged_artifact_trust() -> dict[str, bytes]:
    """Return the keys shipped in this package. The file is empty until a Founder pins one."""
    if not _PACKAGED_ARTIFACT.is_file():
        return {}
    try:
        return load_artifact_trust(_PACKAGED_ARTIFACT)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def active_artifact_trust() -> dict[str, bytes]:
    """Live installs use the packaged set. Tests may set a temporary override."""
    if _ARTIFACT_OVERRIDE is not None:
        return dict(_ARTIFACT_OVERRIDE)
    return packaged_artifact_trust()


@contextmanager
def artifact_trust_override(keys: dict[str, bytes]) -> Iterator[None]:
    """Test-only trust override. The command line cannot set this."""
    global _ARTIFACT_OVERRIDE
    previous = _ARTIFACT_OVERRIDE
    _ARTIFACT_OVERRIDE = dict(keys)
    try:
        yield
    finally:
        _ARTIFACT_OVERRIDE = previous


def load_artifact_trust(path: Path) -> dict[str, bytes]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("keys"), list):
        raise ValueError("trust")
    keys: dict[str, bytes] = {}
    for item in payload["keys"]:
        if not isinstance(item, dict):
            continue
        key_id = item.get("key_id")
        if (
            not isinstance(key_id, str)
            or not key_id.startswith("test-nonprod-artifact-")
            or item.get("key_class") != "test_non_production"
            or item.get("not_a_production_root") is not True
        ):
            continue
        raw = base64.b64decode(str(item.get("public_key_b64")), validate=True)
        if len(raw) == 32:
            keys[key_id] = raw
    return keys


def load_signature_file(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("signature file")
    return payload


def _key_refusal(record: dict) -> str | None:
    key_id = record.get("key_id")
    key_class = record.get("key_class")
    flag = record.get("not_a_production_root")
    if not isinstance(key_id, str) or not key_id.startswith("test-nonprod-"):
        return "PRODUCTION_KEY_REFUSED"
    if key_class != "test_non_production" or flag is not True:
        return "PRODUCTION_KEY_REFUSED"
    if not key_id.startswith("test-nonprod-artifact-"):
        return "ARTIFACT_KEY_REFUSED"
    return None


def _refuse_url(url: str) -> str | None:
    lowered = url.casefold()
    if any(marker in lowered for marker in _FORBIDDEN):
        return "PHANTOM_BOX_REFUSED"
    parsed = urlparse(url)
    if parsed.scheme != "http":
        return "ENDPOINT_REFUSED"
    if (parsed.hostname or "") not in {"127.0.0.1", "localhost"}:
        return "ENDPOINT_REFUSED"
    return None


def _forbidden(value: str) -> bool:
    lowered = value.casefold()
    return any(fragment.casefold() in lowered for fragment in _FORBIDDEN)


def canonical_descriptor(document: dict) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _canonical(document: dict) -> bytes:
    return canonical_descriptor(document)


def _result(
    reason: str,
    *,
    hashed: bool,
    sha256: str = "",
    filename: str = "",
    byte_count: int = 0,
    ok: bool = False,
) -> dict:
    return {
        "disposition": "VERIFIED" if ok else "REFUSED",
        "reason": reason,
        "bytes_hashed_here": hashed,
        "sha256": sha256,
        "filename": filename,
        "byte_count": byte_count,
        "public_pin_moved": False,
        "fetched": False,
    }
