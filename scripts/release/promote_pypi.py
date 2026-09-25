#!/usr/bin/env python3
"""Promote one sealed vantio-agent-sdk wheel and sdist.

This script never builds. Exit 0 means the gate passed, or both sealed files
were uploaded and the registry downloads matched them. Exit 2 is
VERSION_ALREADY_EXISTS and is not a successful publication.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

PACKAGE = "vantio-agent-sdk"
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9.-]+)?$")
SHA_RE = re.compile(r"^[a-f0-9]{40}$")
HEX64_RE = re.compile(r"^[a-f0-9]{64}$")
SECRET_KEYS = ("TWINE_PASSWORD", "TWINE_API_KEY", "PYPI_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")


def redact(text: str) -> str:
    out = text
    for key in SECRET_KEYS:
        secret = os.environ.get(key)
        if secret and len(secret) >= 6:
            out = out.replace(secret, "[REDACTED]")
    return out


def emit(status: str, **extra: object) -> None:
    sys.stdout.write("RELEASE_RESULT " + redact(json.dumps({"status": status, **extra})) + "\n")


def fail(status: str, message: str, code: int = 1, **extra: object) -> None:
    sys.stderr.write(f"vantio-release: {redact(message)}\n")
    emit(status, **extra)
    raise SystemExit(code)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def assert_safe_name(name: str) -> None:
    parts = Path(name).parts
    if name.startswith("/") or name.startswith("\\") or ".." in parts or name.startswith("../"):
        fail("UNSAFE_ARCHIVE_MEMBER", f"unsafe archive member {name}")


def read_wheel_sources(path: Path) -> dict[str, bytes]:
    sources: dict[str, bytes] = {}
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            assert_safe_name(info.filename)
            if info.is_dir():
                continue
            # Zip external attributes: high 16 bits are the Unix mode.
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                fail("UNSAFE_ARCHIVE_MEMBER", f"wheel contains a symlink {info.filename}")
            if info.filename.startswith("vantio/") and info.filename.endswith(".py"):
                sources[info.filename] = archive.read(info)
            if info.filename.endswith("METADATA"):
                sources[info.filename] = archive.read(info)
    return sources


def read_sdist_sources(path: Path) -> dict[str, bytes]:
    sources: dict[str, bytes] = {}
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            assert_safe_name(member.name)
            if member.issym() or member.islnk():
                fail("UNSAFE_ARCHIVE_MEMBER", f"sdist contains a link {member.name}")
            if not member.isfile():
                continue
            extracted = archive.extractfile(member)
            if extracted is None:
                continue
            data = extracted.read()
            relative = "/".join(Path(member.name).parts[1:])
            if relative.startswith("vantio/") and relative.endswith(".py"):
                sources[relative] = data
            if relative == "PKG-INFO":
                sources["PKG-INFO"] = data
    return sources


def metadata_version(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("Version:"):
            return line.split(":", 1)[1].strip()
        if line.startswith("Name:"):
            continue
    return None


def metadata_name(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("Name:"):
            return line.split(":", 1)[1].strip()
    return None


def fetch_json(url: str) -> tuple[int, dict | None]:
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "vantio-release-promote"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read()
            return response.status, json.loads(body.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return 404, None
        fail("REGISTRY_LOOKUP_FAILED", f"PyPI lookup failed ({exc.code})")
    except urllib.error.URLError:
        fail("REGISTRY_LOOKUP_FAILED", "PyPI lookup could not connect")
    return 0, None


def project_version(pyproject: Path) -> str:
    # The version line is a single assignment. Avoid a TOML dependency.
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"\s*$', pyproject.read_text(encoding="utf-8"))
    if not match:
        fail("SOURCE_PACKAGE_MISSING", "pyproject.toml has no version")
    return match.group(1)


def runtime_map(sources: dict[str, bytes]) -> dict[str, str]:
    return {
        name: hashlib.sha256(data).hexdigest()
        for name, data in sorted(sources.items())
        if name.startswith("vantio/") and name.endswith(".py")
    }


def classify_twine(stdout: str, stderr: str, code: int) -> str | None:
    text = f"{stdout}\n{stderr}"
    if code == 0:
        return None
    if re.search(r"File already exists|409 Conflict|already been (uploaded|published)", text, re.I):
        return "VERSION_ALREADY_EXISTS"
    return "PUBLISH_FAILED"


def download(url: str, dest: Path) -> None:
    if not url.startswith("https://files.pythonhosted.org/") and not (
        os.environ.get("VANTIO_RELEASE_TEST") == "1" and url.startswith("http://127.0.0.1")
    ):
        fail("REGISTRY_HASH_MISMATCH", "registry file URL is not the public PyPI file host")
    request = urllib.request.Request(url, headers={"User-Agent": "vantio-release-promote"})
    with urllib.request.urlopen(request, timeout=60) as response:
        dest.write_bytes(response.read())


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote sealed vantio-agent-sdk artifacts")
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--checkout-sha", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--wheel")
    parser.add_argument("--sdist")
    parser.add_argument("--wheel-sha256")
    parser.add_argument("--sdist-sha256")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--twine-bin", default="twine")
    parser.add_argument("--metadata-url", default="")
    args = parser.parse_args()

    if not VERSION_RE.match(args.version):
        fail("VERSION_REJECTED", "version is empty or not semver-safe")
    if not SHA_RE.match(args.source_commit) or args.source_commit != args.checkout_sha:
        fail("SOURCE_COMMIT_MISMATCH", "source commit must be the full checkout SHA")

    pyproject = Path(args.repo_root) / "packages" / "vantio-agent-sdk-py" / "pyproject.toml"
    if not pyproject.is_file():
        fail("SOURCE_PACKAGE_MISSING", "checkout is missing pyproject.toml")
    if project_version(pyproject) != args.version:
        fail("VERSION_MISMATCH", "pyproject.toml version does not match the request")

    index_base = args.metadata_url.rstrip("/") if args.metadata_url else "https://pypi.org/pypi/vantio-agent-sdk"
    status, _payload = fetch_json(f"{index_base}/{args.version}/json")
    if status == 200:
        fail(
            "VERSION_ALREADY_EXISTS",
            f"{PACKAGE}=={args.version} is already on the registry",
            2,
            package=PACKAGE,
            version=args.version,
            source_commit=args.source_commit,
        )
    if status != 404:
        fail("REGISTRY_LOOKUP_FAILED", f"unexpected PyPI status {status}")

    if not args.publish:
        emit("GATE_OK", package=PACKAGE, version=args.version, source_commit=args.source_commit, publish=False)
        return

    wheel = Path(args.wheel or "")
    sdist = Path(args.sdist or "")
    if not wheel.is_file() or not sdist.is_file():
        fail("ARTIFACT_MISSING", "sealed wheel and sdist are both required")
    if args.wheel_sha256 is None or not HEX64_RE.match(args.wheel_sha256):
        fail("HASH_REJECTED", "wheel SHA-256 is missing or malformed")
    if args.sdist_sha256 is None or not HEX64_RE.match(args.sdist_sha256):
        fail("HASH_REJECTED", "sdist SHA-256 is missing or malformed")
    wheel_sha = sha256_file(wheel)
    sdist_sha = sha256_file(sdist)
    if wheel_sha != args.wheel_sha256 or sdist_sha != args.sdist_sha256:
        fail("ARTIFACT_HASH_MISMATCH", "sealed artifact hash does not match the approved hash")

    expected_wheel = f"vantio_agent_sdk-{args.version}-py3-none-any.whl"
    expected_sdist = f"vantio_agent_sdk-{args.version}.tar.gz"
    if wheel.name != expected_wheel or sdist.name != expected_sdist:
        fail("ARTIFACT_IDENTITY_MISMATCH", "sealed filenames do not match the requested version")

    wheel_sources = read_wheel_sources(wheel)
    sdist_sources = read_sdist_sources(sdist)
    wheel_meta = next((data.decode("utf-8", "replace") for name, data in wheel_sources.items() if name.endswith("METADATA")), "")
    sdist_meta = sdist_sources.get("PKG-INFO", b"").decode("utf-8", "replace")
    if metadata_name(wheel_meta) != PACKAGE or metadata_version(wheel_meta) != args.version:
        fail("ARTIFACT_IDENTITY_MISMATCH", "wheel metadata identity does not match")
    if metadata_name(sdist_meta) != PACKAGE or metadata_version(sdist_meta) != args.version:
        fail("ARTIFACT_IDENTITY_MISMATCH", "sdist metadata identity does not match")
    if runtime_map(wheel_sources) != runtime_map(sdist_sources) or not runtime_map(wheel_sources):
        fail("ARTIFACT_IDENTITY_MISMATCH", "wheel and sdist runtime sources differ")

    twine = subprocess.run(
        [args.twine_bin, "upload", "--non-interactive", str(wheel), str(sdist)],
        check=False,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    classified = classify_twine(twine.stdout, twine.stderr, twine.returncode)
    if classified == "VERSION_ALREADY_EXISTS":
        fail(classified, "PyPI already has this version", 2, package=PACKAGE, version=args.version)
    if classified == "PUBLISH_FAILED":
        detail = redact((twine.stderr or twine.stdout or "twine upload failed").strip().splitlines()[-1:])
        fail("PUBLISH_FAILED", detail[0] if detail else "twine upload failed")

    status, payload = fetch_json(f"{index_base}/{args.version}/json")
    if status != 200 or not payload:
        fail("REGISTRY_HASH_MISMATCH", "PyPI did not return the version after upload")
    urls = {item.get("packagetype"): item for item in payload.get("urls") or []}
    for kind, sealed, digest in (("bdist_wheel", wheel, wheel_sha), ("sdist", sdist, sdist_sha)):
        item = urls.get(kind)
        if not item:
            fail("REGISTRY_HASH_MISMATCH", f"PyPI response is missing {kind}")
        reported = ((item.get("digests") or {}).get("sha256"))
        if reported != digest:
            fail(
                "REGISTRY_HASH_MISMATCH",
                f"PyPI sha256 for {kind} does not match the sealed file",
                package=PACKAGE,
                version=args.version,
                sealed_sha256=digest,
                registry_sha256=reported,
            )
        with tempfile.TemporaryDirectory(prefix="vantio-pypi-verify-") as tmp:
            dest = Path(tmp) / Path(str(item["filename"])).name
            download(str(item["url"]), dest)
            remote = sha256_file(dest)
            if remote != digest or dest.stat().st_size != sealed.stat().st_size:
                fail("REGISTRY_HASH_MISMATCH", f"downloaded {kind} does not match the sealed file")
    emit(
        "PUBLISHED",
        package=PACKAGE,
        version=args.version,
        source_commit=args.source_commit,
        wheel_sha256=wheel_sha,
        sdist_sha256=sdist_sha,
    )


if __name__ == "__main__":
    main()
