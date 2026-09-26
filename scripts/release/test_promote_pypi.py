"""Independent tests for sealed PyPI promotion. No registry writes."""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import tarfile
import tempfile
import textwrap
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMOTE = ROOT / "scripts" / "release" / "promote_pypi.py"
COMMIT = "d9b163361683a70c2560c0d164424d3875dcf4a5"
CANARY = "pypi-canary-secret-value-xyz"
VERSION = "3.0.15"
SOURCE = b"def shield():\n    return 'local'\n"


def _repo(tmp: Path) -> None:
    pkg = tmp / "packages" / "vantio-agent-sdk-py"
    pkg.mkdir(parents=True)
    (pkg / "pyproject.toml").write_text(
        f'[project]\nname = "vantio-agent-sdk"\nversion = "{VERSION}"\n',
        encoding="utf-8",
    )


def _metadata() -> str:
    return f"Metadata-Version: 2.1\nName: vantio-agent-sdk\nVersion: {VERSION}\n"


def _wheel(path: Path, source: bytes = SOURCE) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("vantio/__init__.py", source)
        archive.writestr(f"vantio_agent_sdk-{VERSION}.dist-info/METADATA", _metadata())


def _sdist(path: Path, source: bytes = SOURCE) -> None:
    with tarfile.open(path, "w:gz") as archive:
        def add(name: str, data: bytes) -> None:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))

        prefix = f"vantio_agent_sdk-{VERSION}"
        add(f"{prefix}/PKG-INFO", _metadata().encode())
        add(f"{prefix}/vantio/__init__.py", source)


class Index(ThreadingHTTPServer):
    def __init__(self, directory: Path):
        self.directory = directory
        self.phase = directory / "phase"
        self.phase.write_text("absent", encoding="utf-8")
        self.lag_path = directory / "lag"
        self.corrupt_path = directory / "corrupt"
        self.live_hits = 0
        super().__init__(("127.0.0.1", 0), self._handler())

    def _handler(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path.endswith(f"/{VERSION}/json"):
                    if server.phase.read_text(encoding="utf-8").strip() != "live":
                        self.send_response(404)
                        self.end_headers()
                        return
                    server.live_hits += 1
                    lag = 0
                    if server.lag_path.is_file():
                        raw_lag = server.lag_path.read_text(encoding="utf-8").strip()
                        lag = int(raw_lag) if raw_lag.isdigit() else 0
                    if server.live_hits <= lag:
                        self.send_response(404)
                        self.end_headers()
                        return
                    wheel = server.directory / f"vantio_agent_sdk-{VERSION}-py3-none-any.whl"
                    sdist = server.directory / f"vantio_agent_sdk-{VERSION}.tar.gz"
                    if not wheel.is_file() or not sdist.is_file():
                        raw = b'{"urls":[]}'
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(raw)))
                        self.end_headers()
                        self.wfile.write(raw)
                        return
                    corrupt = server.corrupt_path.is_file()
                    wheel_digest = hashlib.sha256(b"corrupt-wheel" if corrupt else wheel.read_bytes()).hexdigest()
                    sdist_digest = hashlib.sha256(b"corrupt-sdist" if corrupt else sdist.read_bytes()).hexdigest()
                    body = {
                        "urls": [
                            {
                                "packagetype": "bdist_wheel",
                                "filename": wheel.name,
                                "url": f"http://127.0.0.1:{server.server_address[1]}/files/{wheel.name}",
                                "digests": {"sha256": wheel_digest},
                            },
                            {
                                "packagetype": "sdist",
                                "filename": sdist.name,
                                "url": f"http://127.0.0.1:{server.server_address[1]}/files/{sdist.name}",
                                "digests": {"sha256": sdist_digest},
                            },
                        ]
                    }
                    raw = json.dumps(body).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                if self.path.startswith("/files/"):
                    target = server.directory / self.path.rsplit("/", 1)[-1]
                    data = target.read_bytes() if target.is_file() else b""
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                self.send_response(404)
                self.end_headers()

            def log_message(self, fmt: str, *args: object) -> None:
                return

        return Handler


def _run(tmp: Path, *extra: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    base = {
        "PATH": os.environ.get("PATH", ""),
        "VANTIO_RELEASE_TEST": "1",
        "TWINE_PASSWORD": CANARY,
    }
    if env:
        base.update(env)
    return subprocess.run(
        [
            "python3",
            str(PROMOTE),
            "--version",
            VERSION,
            "--source-commit",
            COMMIT,
            "--checkout-sha",
            COMMIT,
            "--repo-root",
            str(tmp),
            *extra,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=base,
    )


def _serve(tmp: Path) -> tuple[Index, threading.Thread, str]:
    index = Index(tmp)
    thread = threading.Thread(target=index.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{index.server_address[1]}/pypi/vantio-agent-sdk"
    return index, thread, url


class PromotePyPITests(unittest.TestCase):
    def test_gate_absent_and_existing(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            _repo(tmp)
            index, _thread, url = _serve(tmp)
            try:
                absent = _run(tmp, "--metadata-url", url)
                self.assertEqual(absent.returncode, 0, absent.stderr)
                self.assertIn("GATE_OK", absent.stdout)
                self.assertNotIn(CANARY, absent.stdout + absent.stderr)
                index.phase.write_text("live", encoding="utf-8")
                exists = _run(tmp, "--metadata-url", url)
                self.assertEqual(exists.returncode, 2)
                self.assertIn("VERSION_ALREADY_EXISTS", exists.stdout)
            finally:
                index.shutdown()

    def test_source_mismatch_does_not_upload(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            _repo(tmp)
            wheel = tmp / f"vantio_agent_sdk-{VERSION}-py3-none-any.whl"
            sdist = tmp / f"vantio_agent_sdk-{VERSION}.tar.gz"
            _wheel(wheel)
            _sdist(sdist, b"def shield():\n    return 'other'\n")
            seen = tmp / "seen.txt"
            twine = tmp / "twine"
            twine.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$@\" > \"{seen}\"\nexit 0\n", encoding="utf-8")
            twine.chmod(0o755)
            index, _thread, url = _serve(tmp)
            try:
                result = _run(
                    tmp,
                    "--publish",
                    "--metadata-url",
                    url,
                    "--wheel",
                    str(wheel),
                    "--sdist",
                    str(sdist),
                    "--wheel-sha256",
                    hashlib.sha256(wheel.read_bytes()).hexdigest(),
                    "--sdist-sha256",
                    hashlib.sha256(sdist.read_bytes()).hexdigest(),
                    "--twine-bin",
                    str(twine),
                )
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("ARTIFACT_IDENTITY_MISMATCH", result.stdout)
                self.assertFalse(seen.exists())
            finally:
                index.shutdown()

    def test_twine_conflict_is_version_already_exists(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            _repo(tmp)
            wheel = tmp / f"vantio_agent_sdk-{VERSION}-py3-none-any.whl"
            sdist = tmp / f"vantio_agent_sdk-{VERSION}.tar.gz"
            _wheel(wheel)
            _sdist(sdist)
            twine = tmp / "twine"
            twine.write_text(
                textwrap.dedent(
                    f"""\
                    #!/bin/sh
                    echo "HTTPError: 400 File already exists" >&2
                    echo "{CANARY}" >&2
                    exit 1
                    """
                ),
                encoding="utf-8",
            )
            twine.chmod(0o755)
            index, _thread, url = _serve(tmp)
            try:
                result = _run(
                    tmp,
                    "--publish",
                    "--metadata-url",
                    url,
                    "--wheel",
                    str(wheel),
                    "--sdist",
                    str(sdist),
                    "--wheel-sha256",
                    hashlib.sha256(wheel.read_bytes()).hexdigest(),
                    "--sdist-sha256",
                    hashlib.sha256(sdist.read_bytes()).hexdigest(),
                    "--twine-bin",
                    str(twine),
                )
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("VERSION_ALREADY_EXISTS", result.stdout)
                self.assertNotIn("PUBLISHED", result.stdout)
                self.assertNotIn(CANARY, result.stdout + result.stderr)
            finally:
                index.shutdown()

    def test_sealed_upload_matches_registry_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            _repo(tmp)
            wheel = tmp / f"vantio_agent_sdk-{VERSION}-py3-none-any.whl"
            sdist = tmp / f"vantio_agent_sdk-{VERSION}.tar.gz"
            _wheel(wheel)
            _sdist(sdist)
            seen = tmp / "seen.txt"
            phase = tmp / "phase"
            twine = tmp / "twine"
            twine.write_text(
                textwrap.dedent(
                    f"""\
                    #!/bin/sh
                    printf '%s\\n' "$@" > "{seen}"
                    printf '%s\\n' live > "{phase}"
                    exit 0
                    """
                ),
                encoding="utf-8",
            )
            twine.chmod(0o755)
            index, _thread, url = _serve(tmp)
            try:
                result = _run(
                    tmp,
                    "--publish",
                    "--metadata-url",
                    url,
                    "--wheel",
                    str(wheel),
                    "--sdist",
                    str(sdist),
                    "--wheel-sha256",
                    hashlib.sha256(wheel.read_bytes()).hexdigest(),
                    "--sdist-sha256",
                    hashlib.sha256(sdist.read_bytes()).hexdigest(),
                    "--twine-bin",
                    str(twine),
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("PUBLISHED", result.stdout)
                recorded = seen.read_text(encoding="utf-8")
                self.assertIn(wheel.name, recorded)
                self.assertIn(sdist.name, recorded)
                self.assertNotIn("packages/vantio-agent-sdk-py", recorded)
                self.assertNotIn(CANARY, result.stdout + result.stderr)
            finally:
                index.shutdown()

    def test_wrong_hash_rejects_before_upload(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            _repo(tmp)
            wheel = tmp / f"vantio_agent_sdk-{VERSION}-py3-none-any.whl"
            sdist = tmp / f"vantio_agent_sdk-{VERSION}.tar.gz"
            _wheel(wheel)
            _sdist(sdist)
            seen = tmp / "seen.txt"
            twine = tmp / "twine"
            twine.write_text(f"#!/bin/sh\n: > \"{seen}\"\nexit 0\n", encoding="utf-8")
            twine.chmod(0o755)
            index, _thread, url = _serve(tmp)
            try:
                result = _run(
                    tmp,
                    "--publish",
                    "--metadata-url",
                    url,
                    "--wheel",
                    str(wheel),
                    "--sdist",
                    str(sdist),
                    "--wheel-sha256",
                    "a" * 64,
                    "--sdist-sha256",
                    hashlib.sha256(sdist.read_bytes()).hexdigest(),
                    "--twine-bin",
                    str(twine),
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn("ARTIFACT_HASH_MISMATCH", result.stdout)
                self.assertFalse(seen.exists())
            finally:
                index.shutdown()

    def _publish(self, tmp: Path, twine_body: str, *, lag: int = 0, corrupt: bool = False, attempts: str = "6") -> subprocess.CompletedProcess[str]:
        _repo(tmp)
        wheel = tmp / f"vantio_agent_sdk-{VERSION}-py3-none-any.whl"
        sdist = tmp / f"vantio_agent_sdk-{VERSION}.tar.gz"
        _wheel(wheel)
        _sdist(sdist)
        if lag:
            (tmp / "lag").write_text(str(lag), encoding="utf-8")
        if corrupt:
            (tmp / "corrupt").write_text("1", encoding="utf-8")
        twine = tmp / "twine"
        twine.write_text(twine_body, encoding="utf-8")
        twine.chmod(0o755)
        self.wheel = wheel
        self.sdist = sdist
        self.twine = twine
        return wheel, sdist, twine

    def test_delayed_visibility_then_exact_match(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            seen = tmp / "seen.txt"
            phase = tmp / "phase"
            wheel, sdist, twine = self._publish(
                tmp,
                textwrap.dedent(
                    f"""\
                    #!/bin/sh
                    printf '%s\\n' "$@" >> "{seen}"
                    printf '%s\\n' live > "{phase}"
                    echo "HTTP 202 Accepted"
                    exit 0
                    """
                ),
                lag=2,
            )
            index, _thread, url = _serve(tmp)
            try:
                result = _run(
                    tmp,
                    "--publish",
                    "--metadata-url",
                    url,
                    "--wheel",
                    str(wheel),
                    "--sdist",
                    str(sdist),
                    "--wheel-sha256",
                    hashlib.sha256(wheel.read_bytes()).hexdigest(),
                    "--sdist-sha256",
                    hashlib.sha256(sdist.read_bytes()).hexdigest(),
                    "--twine-bin",
                    str(twine),
                    env={
                        "VANTIO_REGISTRY_POLL_INTERVAL_SECONDS": "0",
                        "VANTIO_REGISTRY_POLL_MAX_ATTEMPTS": "6",
                    },
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("PUBLISHED_VERIFIED", result.stdout)
                self.assertIn("REGISTRY_PROCESSING", result.stderr)
                self.assertEqual(seen.read_text(encoding="utf-8").count("upload"), 1)
                self.assertNotIn(CANARY, result.stdout + result.stderr)
            finally:
                index.shutdown()

    def test_delayed_visibility_times_out_without_a_second_upload(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            seen = tmp / "seen.txt"
            phase = tmp / "phase"
            wheel, sdist, twine = self._publish(
                tmp,
                textwrap.dedent(
                    f"""\
                    #!/bin/sh
                    printf '%s\\n' "$@" >> "{seen}"
                    printf '%s\\n' live > "{phase}"
                    exit 0
                    """
                ),
                lag=50,
            )
            index, _thread, url = _serve(tmp)
            try:
                result = _run(
                    tmp,
                    "--publish",
                    "--metadata-url",
                    url,
                    "--wheel",
                    str(wheel),
                    "--sdist",
                    str(sdist),
                    "--wheel-sha256",
                    hashlib.sha256(wheel.read_bytes()).hexdigest(),
                    "--sdist-sha256",
                    hashlib.sha256(sdist.read_bytes()).hexdigest(),
                    "--twine-bin",
                    str(twine),
                    env={
                        "VANTIO_REGISTRY_POLL_INTERVAL_SECONDS": "0",
                        "VANTIO_REGISTRY_POLL_MAX_ATTEMPTS": "3",
                    },
                )
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("REGISTRY_TIMEOUT", result.stdout)
                self.assertNotIn("PUBLISHED_VERIFIED", result.stdout)
                self.assertEqual(seen.read_text(encoding="utf-8").count("upload"), 1)
            finally:
                index.shutdown()

    def test_visible_version_with_wrong_hash(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            seen = tmp / "seen.txt"
            phase = tmp / "phase"
            wheel, sdist, twine = self._publish(
                tmp,
                textwrap.dedent(
                    f"""\
                    #!/bin/sh
                    printf '%s\\n' "$@" >> "{seen}"
                    printf '%s\\n' live > "{phase}"
                    exit 0
                    """
                ),
                corrupt=True,
            )
            index, _thread, url = _serve(tmp)
            try:
                result = _run(
                    tmp,
                    "--publish",
                    "--metadata-url",
                    url,
                    "--wheel",
                    str(wheel),
                    "--sdist",
                    str(sdist),
                    "--wheel-sha256",
                    hashlib.sha256(wheel.read_bytes()).hexdigest(),
                    "--sdist-sha256",
                    hashlib.sha256(sdist.read_bytes()).hexdigest(),
                    "--twine-bin",
                    str(twine),
                    env={
                        "VANTIO_REGISTRY_POLL_INTERVAL_SECONDS": "0",
                        "VANTIO_REGISTRY_POLL_MAX_ATTEMPTS": "3",
                    },
                )
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("HASH_MISMATCH", result.stdout)
                self.assertEqual(seen.read_text(encoding="utf-8").count("upload"), 1)
            finally:
                index.shutdown()


if __name__ == "__main__":
    unittest.main()
