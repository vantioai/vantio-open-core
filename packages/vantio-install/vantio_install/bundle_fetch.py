"""License-gated download of a sealed bundle.

The endpoint allowlist is https://vantio.ai and https://www.vantio.ai.
Exactly one redirect is followed, and only to the GitHub release asset
hosts over https. The lab path stays http://127.0.0.1 or http://localhost
and does not follow redirects. The body is streamed to a partial file.
The 2 GiB cap is the hard stop. SHA256SUMS and SHA256SUMS.sig are checked
before the tree is moved into the bundle directory.

Production artifact keys (``prod-artifact-*``) are read only from the
packaged trust file. Test artifact keys verify only on the lab path.
"""

from __future__ import annotations

import base64
import hashlib
import http.client
import json
import os
import shutil
import ssl
import tarfile
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import urljoin, urlparse

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from vantio_install import constants
from vantio_install.artifact_verify import (
    _key_refusal,
    active_artifact_trust,
    packaged_production_trust,
)
from vantio_install.paths import _EXACT_DENY, _PREFIX_DENY

_FORBIDDEN = (
    "phantom-box",
    "phantom.box",
    "phantombox",
    "/home/vantioai",
    "vantio-sandbox",
)
_HTTP_RESULT = {
    401: (constants.EXIT_LICENSE_UNAUTHORIZED, "LICENSE_UNAUTHORIZED", "The license was not accepted."),
    403: (constants.EXIT_LICENSE_FORBIDDEN, "LICENSE_CANCELED_OR_EXPIRED", "license canceled or expired"),
    410: (constants.EXIT_DOWNLOAD_GONE, "DOWNLOAD_GONE", "The sealed bundle is no longer available."),
    429: (constants.EXIT_RATE_LIMITED, "RATE_LIMITED", "Too many download attempts for this license."),
}
_REDIRECTS = {301, 302, 303, 307, 308}
Transport = Callable[[str, dict[str, str], float], tuple[int, dict[str, str], Iterable[bytes]]]


def classify_endpoint(url: str) -> str:
    lowered = url.casefold()
    if any(marker in lowered for marker in _FORBIDDEN):
        return "PHANTOM_BOX_REFUSED"
    parsed = urlparse(url)
    if parsed.username or parsed.password:
        return "ENDPOINT_REFUSED"
    host = (parsed.hostname or "").lower().rstrip(".")
    if host in constants.FETCH_LAB_HOSTS:
        return "lab" if parsed.scheme == "http" else "SCHEME_REFUSED"
    if host in constants.FETCH_ENDPOINT_HOSTS:
        return "production" if parsed.scheme == "https" else "SCHEME_REFUSED"
    return "ENDPOINT_REFUSED"


def with_bundle_asset(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if host in constants.FETCH_ENDPOINT_HOSTS and not parsed.query:
        join = "&" if "?" in url else "?"
        return url + join + "asset=bundle"
    return url


def redirect_refusal(location: str | None, count: int, kind: str, base: str) -> str | None:
    if kind != "production":
        return "REDIRECT_REFUSED"
    if count != 1:
        return "REDIRECT_LIMIT"
    if not location:
        return "REDIRECT_REFUSED"
    target = urljoin(base, location)
    parsed = urlparse(target)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https":
        return "REDIRECT_SCHEME_REFUSED"
    if host not in constants.FETCH_REDIRECT_HOSTS:
        return "REDIRECT_HOST_REFUSED"
    if parsed.username or parsed.password:
        return "REDIRECT_HOST_REFUSED"
    return None


def assert_bundle_dir(value: str) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value or value.startswith("~"):
        raise ValueError("bundle dir")
    raw = Path(value)
    if ".." in raw.parts:
        raise ValueError("bundle dir")
    resolved = raw if raw.is_absolute() else (Path.cwd() / raw).resolve(strict=False)
    text = resolved.as_posix()
    if text in _EXACT_DENY or text == "/":
        raise ValueError("bundle dir")
    for prefix in _PREFIX_DENY:
        if text == prefix or text.startswith(prefix + "/"):
            raise ValueError("bundle dir")
    return resolved


def fetch_bundle(
    url: str,
    bundle_dir: Path,
    *,
    token: str,
    transport: Transport | None = None,
    max_bytes: int = constants.FETCH_MAX_BYTES,
    timeout_s: float = 120,
) -> dict:
    """Download, verify, and unpack. The result does not include the token or the redirect URL."""
    kind = classify_endpoint(url)
    if kind not in {"lab", "production"}:
        return _refused(kind, constants.EXIT_BLOCKED)
    partial = bundle_dir.with_name(bundle_dir.name + ".partial")
    staging = bundle_dir.with_name(bundle_dir.name + ".unpack")
    opener = transport or _urllib_transport
    try:
        status, headers, chunks, followed = _read_response(url, token, kind, opener, timeout_s)
    except _RedirectRefused as exc:
        _cleanup(partial, staging)
        return _refused(exc.reason, constants.EXIT_BLOCKED)
    except (OSError, TimeoutError, http.client.HTTPException, ValueError):
        _cleanup(partial, staging)
        return _refused("INTERRUPTED_DOWNLOAD", constants.EXIT_FAILED_SAFE)
    mapped = _HTTP_RESULT.get(status)
    if mapped is not None:
        _drain(chunks)
        _cleanup(partial, staging)
        code, reason, message = mapped
        return _refused(reason, code, message=message)
    if status != 200:
        _drain(chunks)
        _cleanup(partial, staging)
        return _refused("HTTP_STATUS", constants.EXIT_BLOCKED, http_status=status)
    declared = _content_length(headers)
    if declared is not None and declared > max_bytes:
        _drain(chunks)
        _cleanup(partial, staging)
        return _refused("TOO_LARGE", constants.EXIT_BLOCKED)
    try:
        written = _stream(chunks, partial, max_bytes)
    except _TooLarge:
        _cleanup(partial, staging)
        return _refused("TOO_LARGE", constants.EXIT_BLOCKED)
    except (OSError, ValueError):
        _cleanup(partial, staging)
        return _refused("INTERRUPTED_DOWNLOAD", constants.EXIT_FAILED_SAFE)
    if declared is not None and declared != written:
        _cleanup(partial, staging)
        return _refused("INTERRUPTED_DOWNLOAD", constants.EXIT_FAILED_SAFE)
    try:
        tree = _extract(partial, staging, max_bytes)
        verdict = verify_unpacked(tree, production=kind == "production")
    except _TooLarge:
        _cleanup(partial, staging)
        return _refused("TOO_LARGE", constants.EXIT_BLOCKED)
    except (OSError, tarfile.TarError, ValueError):
        _cleanup(partial, staging)
        return _refused("TAR_REFUSED", constants.EXIT_BLOCKED)
    if verdict["reason"] != "VERIFIED":
        _cleanup(partial, staging)
        return _refused(verdict["reason"], constants.EXIT_BLOCKED, byte_count=written)
    if bundle_dir.exists() and any(bundle_dir.iterdir()):
        _cleanup(partial, staging)
        return _refused("BUNDLE_DIR_NONEMPTY", constants.EXIT_BLOCKED, byte_count=written)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    for child in tree.iterdir():
        shutil.move(str(child), str(bundle_dir / child.name))
    _cleanup(partial, staging)
    return {
        "ok": True,
        "reason": "VERIFIED",
        "exit_code": constants.EXIT_OK,
        "message": "Bundle verified.",
        "byte_count": written,
        "endpoint_host": (urlparse(url).hostname or ""),
        "redirects": followed,
        "production": kind == "production",
    }


def verify_unpacked(tree: Path, *, production: bool) -> dict:
    sums = tree / "SHA256SUMS"
    signature_path = tree / "SHA256SUMS.sig"
    if not sums.is_file() or not signature_path.is_file():
        return {"reason": "CHECKSUMS_MISSING"}
    try:
        record = json.loads(signature_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"reason": "SIGNATURE_INVALID"}
    if not isinstance(record, dict):
        return {"reason": "SIGNATURE_INVALID"}
    reason = _signature_reason(sums.read_bytes(), record, production=production)
    if reason != "VERIFIED":
        return {"reason": reason}
    try:
        rows = _checksum_rows(tree, sums)
    except ValueError:
        return {"reason": "SHA_MISMATCH"}
    for rel, expected, observed in rows:
        if observed != expected:
            return {"reason": "SHA_MISMATCH", "path": rel}
    return {"reason": "VERIFIED"}


def _signature_reason(sums: bytes, record: dict, *, production: bool) -> str:
    if record.get("algorithm") != "Ed25519":
        return "SIGNATURE_INVALID"
    key_id = record.get("key_id")
    if not isinstance(key_id, str):
        return "SIGNATURE_INVALID"
    if production:
        if key_id.startswith("test-nonprod"):
            return "TEST_KEY_ON_PRODUCTION_PATH"
        if record.get("key_class") != "production" or not key_id.startswith("prod-artifact-"):
            return "PRODUCTION_KEY_REQUIRED"
        keys = packaged_production_trust()
    else:
        refused = _key_refusal(record)
        if refused is not None:
            return refused
        keys = active_artifact_trust()
    pinned = keys.get(key_id)
    if pinned is None:
        return "UNTRUSTED_KEY"
    presented = record.get("public_key_b64")
    if presented is not None:
        try:
            if base64.b64decode(str(presented), validate=True) != pinned:
                return "UNTRUSTED_KEY"
        except ValueError:
            return "SIGNATURE_INVALID"
    try:
        signature = base64.b64decode(str(record.get("signature_b64")), validate=True)
        Ed25519PublicKey.from_public_bytes(pinned).verify(signature, sums)
    except (ValueError, InvalidSignature):
        return "SIGNATURE_INVALID"
    return "VERIFIED"


def _checksum_rows(tree: Path, sums: Path) -> list[tuple[str, str, str | None]]:
    rows: list[tuple[str, str, str | None]] = []
    root = tree.resolve()
    for line in sums.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) < 2 or len(parts[0]) != 64:
            raise ValueError("line")
        expect, rel = parts[0], parts[-1]
        if rel in {"SHA256SUMS", "SHA256SUMS.sig"}:
            continue
        target = (tree / rel).resolve()
        if root != target and root not in target.parents:
            raise ValueError("path")
        observed = _sha256(target) if target.is_file() else None
        rows.append((rel, expect, observed))
    if not rows:
        raise ValueError("empty")
    return rows


def _read_response(url: str, token: str, kind: str, transport: Transport, timeout_s: float):
    headers = {"Accept": "application/octet-stream"}
    if token:
        headers["Authorization"] = "Bearer " + token
    status, resp_headers, chunks = transport(url, headers, timeout_s)
    followed = 0
    current = url
    while status in _REDIRECTS:
        followed += 1
        location = resp_headers.get("Location") or resp_headers.get("location")
        reason = redirect_refusal(location, followed, kind, current)
        if reason is not None:
            raise _RedirectRefused(reason)
        current = urljoin(current, location or "")
        status, resp_headers, chunks = transport(
            current,
            {"Accept": "application/octet-stream"},
            timeout_s,
        )
    return status, resp_headers, chunks, followed


class _RedirectRefused(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class _TooLarge(Exception):
    pass


def _stream(chunks: Iterable[bytes], partial: Path, max_bytes: int) -> int:
    if partial.exists():
        partial.unlink()
    partial.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with partial.open("wb") as handle:
        for chunk in chunks:
            if not chunk:
                continue
            written += len(chunk)
            if written > max_bytes:
                raise _TooLarge()
            handle.write(chunk)
        handle.flush()
        os.fsync(handle.fileno())
    return written


def _extract(archive: Path, staging: Path, max_bytes: int) -> Path:
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    total = 0
    with tarfile.open(archive, "r:*") as tar:
        for member in tar.getmembers():
            if member.issym() or member.islnk() or member.isdev():
                raise ValueError("link")
            name = member.name
            if not name or name.startswith("/") or ".." in Path(name).parts:
                raise ValueError("path")
            target = (staging / name).resolve()
            root = staging.resolve()
            if root != target and root not in target.parents:
                raise ValueError("path")
            if member.isfile():
                total += int(member.size)
                if total > max_bytes:
                    raise _TooLarge()
            elif not member.isdir():
                raise ValueError("member")
        try:
            tar.extractall(staging, filter="data")
        except TypeError:
            tar.extractall(staging)
    sums = staging / "SHA256SUMS"
    if sums.is_file():
        return staging
    children = [path for path in staging.iterdir() if path.is_dir()]
    if len(children) == 1 and (children[0] / "SHA256SUMS").is_file():
        return children[0]
    return staging


def _urllib_transport(url: str, headers: dict[str, str], timeout_s: float):
    parsed = urlparse(url)
    port = parsed.port
    if parsed.scheme == "https":
        conn: http.client.HTTPConnection = http.client.HTTPSConnection(
            parsed.hostname or "",
            port or 443,
            timeout=timeout_s,
            context=ssl.create_default_context(),
        )
    elif parsed.scheme == "http":
        conn = http.client.HTTPConnection(parsed.hostname or "", port or 80, timeout=timeout_s)
    else:
        raise ValueError("scheme")
    path = parsed.path or "/"
    if parsed.query:
        path = path + "?" + parsed.query
    try:
        conn.request("GET", path, headers=headers)
        response = conn.getresponse()
        status = response.status
        resp_headers = {key: value for key, value in response.getheaders()}

        def chunks() -> Iterable[bytes]:
            try:
                while True:
                    blob = response.read(1024 * 1024)
                    if not blob:
                        break
                    yield blob
            finally:
                conn.close()

        # Materialize only when the caller iterates. Close the socket then.
        return status, resp_headers, chunks()
    except Exception:
        conn.close()
        raise


def _drain(chunks: Iterable[bytes]) -> None:
    try:
        for _chunk in chunks:
            continue
    except (OSError, http.client.HTTPException, ValueError):
        return


def _content_length(headers: dict[str, str]) -> int | None:
    raw = headers.get("Content-Length") or headers.get("content-length")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cleanup(*paths: Path) -> None:
    for path in paths:
        try:
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
        except OSError:
            continue


def _refused(reason: str, code: int, **extra: object) -> dict:
    body = {
        "ok": False,
        "reason": reason,
        "exit_code": code,
        "message": str(extra.pop("message", reason)),
        "byte_count": extra.get("byte_count", 0),
    }
    body.update(extra)
    return body
