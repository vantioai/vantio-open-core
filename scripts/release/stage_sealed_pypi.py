#!/usr/bin/env python3
"""Stage the sealed vantio-agent-sdk 3.1.0 upload directory.

This module never builds and never uploads. The governed production upload
client is pypa/gh-action-pypi-publish in .github/workflows/pypi-publish.yml.

scripts/release/promote_pypi.py is unchanged historical code. It is not the
authorized Trusted Publisher upload path, and this module does not call it.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import stat
import sys
import tarfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import NoReturn
from zipfile import ZipFile

PACKAGE = "vantio-agent-sdk"
VERSION = "3.1.0"
WHEEL_NAME = "vantio_agent_sdk-3.1.0-py3-none-any.whl"
SDIST_NAME = "vantio_agent_sdk-3.1.0.tar.gz"
WHEEL_SHA256 = "dcf84cb3c4f144ece21032001657bfd9c91067faeffbefd0fb2ae19d6109dbeb"
SDIST_SHA256 = "9f991291d5e44a23e17a9b0d7db24f6e7048d4c76cf0a9c37e35ccbcfe999c4f"
WHEEL_BYTES = 39235
SDIST_BYTES = 59669
UPLOAD_DIR_NAME = "pypi-sealed-upload"
WHEEL_METADATA = f"vantio_agent_sdk-{VERSION}.dist-info/METADATA"
SDIST_METADATA = f"vantio_agent_sdk-{VERSION}/PKG-INFO"
PRODUCTION_METADATA_URL = f"https://pypi.org/pypi/{PACKAGE}/{VERSION}/json"
WORKFLOW_REF = "vantioai/vantio-open-core/.github/workflows/pypi-publish.yml@refs/heads/main"
METADATA_BYTE_CAP = 1_000_000

PIN_ENV = {
    "SEALED_PACKAGE": PACKAGE,
    "SEALED_VERSION": VERSION,
    "SEALED_WHEEL_NAME": WHEEL_NAME,
    "SEALED_SDIST_NAME": SDIST_NAME,
    "SEALED_WHEEL_SHA256": WHEEL_SHA256,
    "SEALED_SDIST_SHA256": SDIST_SHA256,
    "SEALED_WHEEL_BYTES": str(WHEEL_BYTES),
    "SEALED_SDIST_BYTES": str(SDIST_BYTES),
}

EXPECTED_FILES = {
    WHEEL_NAME: (WHEEL_BYTES, WHEEL_SHA256),
    SDIST_NAME: (SDIST_BYTES, SDIST_SHA256),
}


class StageFailure(Exception):
    def __init__(self, status: str, message: str, code: int = 1) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.code = code


def fail(status: str, message: str, code: int = 1) -> NoReturn:
    raise StageFailure(status, message, code)


def emit(status: str, **extra: object) -> None:
    sys.stdout.write("STAGE_RESULT " + json.dumps({"status": status, **extra}, sort_keys=True) + "\n")


def require_pins() -> None:
    for key, expected in PIN_ENV.items():
        actual = os.environ.get(key)
        if actual is None:
            fail("PIN_MISSING", f"missing {key}")
        if actual != expected:
            fail("PIN_MISMATCH", f"{key} does not match the sealed pin")


def assert_actions_context() -> None:
    if os.environ.get("VANTIO_STAGE_ENFORCE_ACTIONS_CONTEXT") != "1":
        return
    if os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch":
        fail("TRIGGER_REJECTED", "event is not workflow_dispatch")
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        fail("TRIGGER_REJECTED", "ref is not refs/heads/main")
    if os.environ.get("GITHUB_REPOSITORY") != "vantioai/vantio-open-core":
        fail("TRIGGER_REJECTED", "repository is not vantioai/vantio-open-core")
    if os.environ.get("GITHUB_WORKFLOW_REF") != WORKFLOW_REF:
        fail("TRIGGER_REJECTED", "workflow ref is not pypi-publish.yml on main")


def reject_traversal(raw: str) -> None:
    if not raw or "\x00" in raw or "\\" in raw or raw.startswith("~"):
        fail("UNSAFE_PATH", "path is empty or unsafe")
    if ".." in Path(raw).parts:
        fail("UNSAFE_PATH", "path traversal is rejected")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def directory_names(path: Path) -> set[str]:
    if path.is_symlink():
        fail("UNSAFE_PATH", f"{path.name} is a symlink")
    if not path.is_dir():
        fail("ARTIFACT_MISSING", f"{path.name} is not a directory")
    names: set[str] = set()
    with os.scandir(path) as entries:
        for entry in entries:
            if entry.is_symlink():
                fail("UNSAFE_PATH", f"{entry.name} is a symlink")
            if not entry.is_file(follow_symlinks=False):
                fail("UNSAFE_PATH", f"{entry.name} is not a regular file")
            names.add(entry.name)
    return names


def read_regular_file(path: Path, expected_size: int) -> bytes:
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode):
        fail("UNSAFE_PATH", f"{path.name} is a symlink")
    if not stat.S_ISREG(info.st_mode):
        fail("UNSAFE_PATH", f"{path.name} is not a regular file")
    if info.st_nlink != 1:
        fail("DUPLICATE_FILE", f"{path.name} has more than one link")
    if info.st_size != expected_size:
        fail("SIZE_MISMATCH", f"{path.name} is {info.st_size} bytes")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags)
    try:
        confirmed = os.fstat(fd)
        if (
            not stat.S_ISREG(confirmed.st_mode)
            or confirmed.st_nlink != 1
            or confirmed.st_size != expected_size
        ):
            fail("UNSAFE_PATH", f"{path.name} changed while being read")
        data = os.read(fd, expected_size + 1)
    finally:
        os.close(fd)
    if len(data) != expected_size:
        fail("SIZE_MISMATCH", f"{path.name} read {len(data)} bytes")
    return data


def read_sealed_directory(path: Path) -> dict[str, bytes]:
    found = directory_names(path)
    expected = set(EXPECTED_FILES)
    if not expected <= found:
        fail("MISSING_FILE", "sealed wheel and sdist are both required")
    if found != expected:
        fail("EXTRA_FILE", "upload set must be exactly the sealed wheel and sdist")
    payloads: dict[str, bytes] = {}
    for name, (size, digest) in EXPECTED_FILES.items():
        data = read_regular_file(path / name, size)
        actual = sha256(data)
        if actual != digest:
            fail("ARTIFACT_HASH_MISMATCH", f"{name} SHA-256 does not match the sealed pin")
        payloads[name] = data
    return payloads


def reject_member_name(name: str) -> None:
    if not name or "\x00" in name or "\\" in name or name.startswith("/") or name.startswith("\\"):
        fail("UNSAFE_ARCHIVE_MEMBER", "archive member path is unsafe")
    if ".." in Path(name).parts:
        fail("UNSAFE_ARCHIVE_MEMBER", "archive member path traversal is rejected")


def header_values(text: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for line in text.splitlines():
        if line == "":
            break
        if line.startswith((" ", "\t")) or ":" not in line:
            fail("ARTIFACT_IDENTITY_MISMATCH", "metadata header is folded or malformed")
        key, value = line.split(":", 1)
        found.setdefault(key, []).append(value.strip())
    return found


def require_identity(text: str) -> None:
    headers = header_values(text)
    if headers.get("Name") != [PACKAGE] or headers.get("Version") != [VERSION]:
        fail("ARTIFACT_IDENTITY_MISMATCH", "distribution is not vantio-agent-sdk 3.1.0")


def assert_wheel_identity(data: bytes) -> None:
    metadata: list[bytes] = []
    with ZipFile(io.BytesIO(data)) as archive:
        for info in archive.infolist():
            reject_member_name(info.filename)
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                fail("UNSAFE_ARCHIVE_MEMBER", "wheel contains a symlink")
            if info.filename != WHEEL_METADATA:
                continue
            if info.file_size > METADATA_BYTE_CAP:
                fail("ARTIFACT_IDENTITY_MISMATCH", "wheel metadata is too large")
            metadata.append(archive.read(info))
    if len(metadata) != 1:
        fail("ARTIFACT_IDENTITY_MISMATCH", "wheel METADATA is missing or duplicated")
    require_identity(metadata[0].decode("utf-8"))


def assert_sdist_identity(data: bytes) -> None:
    metadata: list[bytes] = []
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member in archive.getmembers():
            reject_member_name(member.name)
            if member.issym() or member.islnk():
                fail("UNSAFE_ARCHIVE_MEMBER", "sdist contains a link")
            if member.name != SDIST_METADATA:
                continue
            if member.size > METADATA_BYTE_CAP or not member.isfile():
                fail("ARTIFACT_IDENTITY_MISMATCH", "sdist PKG-INFO is not a regular file")
            extracted = archive.extractfile(member)
            if extracted is None:
                fail("ARTIFACT_IDENTITY_MISMATCH", "sdist PKG-INFO is unreadable")
            metadata.append(extracted.read(METADATA_BYTE_CAP + 1))
    if len(metadata) != 1 or len(metadata[0]) > METADATA_BYTE_CAP:
        fail("ARTIFACT_IDENTITY_MISMATCH", "sdist PKG-INFO is missing, duplicated, or too large")
    require_identity(metadata[0].decode("utf-8"))


def assert_package_identity(wheel: bytes, sdist: bytes) -> None:
    assert_wheel_identity(wheel)
    assert_sdist_identity(sdist)


def prepare_upload_directory(path: Path) -> None:
    if path.is_symlink():
        fail("UNSAFE_PATH", "upload directory is a symlink")
    if path.exists() and not path.is_dir():
        fail("UNSAFE_PATH", "upload path is not a directory")
    try:
        path.mkdir(mode=0o755, exist_ok=True)
    except OSError as exc:
        fail("UNSAFE_PATH", f"could not create the upload directory ({exc.errno})")
    if path.is_symlink() or not path.is_dir():
        fail("UNSAFE_PATH", "upload directory is not a real directory")
    with os.scandir(path) as entries:
        for entry in entries:
            if entry.is_symlink() or entry.is_file(follow_symlinks=False):
                os.unlink(entry.path)
                continue
            fail("UNSAFE_PATH", "upload directory contains a subdirectory")


def write_exclusive(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o644)
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                fail("UNSAFE_PATH", f"could not write {path.name}")
            view = view[written:]
    except Exception:
        os.close(fd)
        os.unlink(path)
        raise
    os.close(fd)


def stage(source: Path, upload: Path) -> dict[str, object]:
    require_pins()
    assert_actions_context()
    reject_traversal(str(source))
    reject_traversal(str(upload))
    if upload.name != UPLOAD_DIR_NAME:
        fail("DESIGNATED_DIRECTORY", "upload directory must be named pypi-sealed-upload")
    if source.is_symlink() or (upload.exists() and upload.is_symlink()):
        fail("UNSAFE_PATH", "refusing a symlink directory")
    source_resolved = source.resolve()
    upload_resolved = upload.resolve()
    if (
        source_resolved == upload_resolved
        or upload_resolved in source_resolved.parents
        or source_resolved in upload_resolved.parents
    ):
        fail("UNSAFE_PATH", "source and upload directories must be separate")
    payloads = read_sealed_directory(source)
    assert_package_identity(payloads[WHEEL_NAME], payloads[SDIST_NAME])
    prepare_upload_directory(upload)
    for name in (WHEEL_NAME, SDIST_NAME):
        write_exclusive(upload / name, payloads[name])
    confirmed = read_sealed_directory(upload)
    if confirmed != payloads:
        fail("ARTIFACT_HASH_MISMATCH", "staged bytes differ from the sealed source")
    assert_package_identity(confirmed[WHEEL_NAME], confirmed[SDIST_NAME])
    return {
        "package": PACKAGE,
        "published": False,
        "sdist": SDIST_NAME,
        "sdist_bytes": SDIST_BYTES,
        "sdist_sha256": SDIST_SHA256,
        "version": VERSION,
        "wheel": WHEEL_NAME,
        "wheel_bytes": WHEEL_BYTES,
        "wheel_sha256": WHEEL_SHA256,
    }


def classify_registry_status(status: int) -> None:
    if status == 200:
        fail("VERSION_ALREADY_EXISTS", f"{PACKAGE}=={VERSION} is already on the registry", 2)
    if status == 404:
        return
    fail("REGISTRY_LOOKUP_FAILED", f"unexpected registry status {status}")


def resolve_metadata_url(override: str) -> str:
    if not override:
        return PRODUCTION_METADATA_URL
    if os.environ.get("VANTIO_RELEASE_TEST") != "1":
        fail("REGISTRY_URL_REJECTED", "metadata URL override is not available")
    parsed = urllib.parse.urlparse(override)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1":
        fail("REGISTRY_URL_REJECTED", "test metadata URL must be loopback http")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        fail("REGISTRY_URL_REJECTED", "metadata URL must not carry credentials or a query")
    suffix = f"/{PACKAGE}/{VERSION}/json"
    if not parsed.path.endswith(suffix):
        fail("REGISTRY_URL_REJECTED", "metadata URL must name vantio-agent-sdk 3.1.0")
    return override


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> None:
        return None


def fetch_status(url: str) -> int:
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"Accept": "application/json", "User-Agent": "vantio-release-stage"},
    )
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=60) as response:
            response.read(65536)
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except urllib.error.URLError:
        fail("REGISTRY_LOOKUP_FAILED", "registry lookup could not connect")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage sealed vantio-agent-sdk 3.1.0 distributions")
    parser.add_argument("--source")
    parser.add_argument("--upload-dir")
    parser.add_argument("--reject-existing-version", action="store_true")
    parser.add_argument("--metadata-url", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    try:
        assert_actions_context()
        if args.reject_existing_version:
            if args.source or args.upload_dir:
                fail("USAGE", "version check does not take a directory")
            classify_registry_status(fetch_status(resolve_metadata_url(args.metadata_url)))
            emit("VERSION_ABSENT", package=PACKAGE, published=False, version=VERSION)
            return
        if args.metadata_url:
            fail("USAGE", "staging does not take a registry URL")
        if not args.source or not args.upload_dir:
            fail("USAGE", "source and upload-dir are required")
        emit("STAGED", **stage(Path(args.source), Path(args.upload_dir)))
    except StageFailure as exc:
        sys.stderr.write(f"vantio-release: {exc.message}\n")
        emit(exc.status, published=False)
        raise SystemExit(exc.code) from exc


if __name__ == "__main__":
    main()
