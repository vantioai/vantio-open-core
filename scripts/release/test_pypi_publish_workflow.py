"""Non-publishing tests for the PyPI trusted publisher workflow.

These tests parse the workflow and exercise the sealed-byte gate locally.
They do not upload, and they do not call the publish action.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "release"))

import stage_sealed_pypi as stage  # noqa: E402

WORKFLOW_PATH = ROOT / ".github" / "workflows" / "pypi-publish.yml"
STAGE_PATH = ROOT / "scripts" / "release" / "stage_sealed_pypi.py"
FETCH_PATH = ROOT / "scripts" / "release" / "fetch_custody_release.py"
WHEEL_SHA256 = "6a0e4aff4c3d520df0016ae2d56c97fd2c5a7a09e184edd63c59044f558685b8"
SDIST_SHA256 = "8a03682afd2058788bd044fbd3784d3b837067bf5ff189d6be5b09434ec96799"
WHEEL_BYTES = 33997
SDIST_BYTES = 57039
WHEEL_NAME = "vantio_agent_sdk-3.1.1-py3-none-any.whl"
SDIST_NAME = "vantio_agent_sdk-3.1.1.tar.gz"
PIN_ENV = {
    "SEALED_PACKAGE": "vantio-agent-sdk",
    "SEALED_VERSION": "3.1.1",
    "SEALED_WHEEL_NAME": WHEEL_NAME,
    "SEALED_SDIST_NAME": SDIST_NAME,
    "SEALED_WHEEL_SHA256": WHEEL_SHA256,
    "SEALED_SDIST_SHA256": SDIST_SHA256,
    "SEALED_WHEEL_BYTES": str(WHEEL_BYTES),
    "SEALED_SDIST_BYTES": str(SDIST_BYTES),
}


def _run(args: list[str], *, pins: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    base = {"PATH": os.environ.get("PATH", "")}
    if pins:
        base.update(PIN_ENV)
    if env:
        base.update(env)
    return subprocess.run(
        [sys.executable, str(STAGE_PATH), *args],
        check=False,
        capture_output=True,
        text=True,
        env=base,
    )


def _status(result: subprocess.CompletedProcess[str]) -> str:
    for line in result.stdout.splitlines():
        if line.startswith("STAGE_RESULT "):
            return str(json.loads(line.removeprefix("STAGE_RESULT "))["status"])
    return ""


def _pair(directory: Path, wheel: bytes, sdist: bytes) -> None:
    (directory / WHEEL_NAME).write_bytes(wheel)
    (directory / SDIST_NAME).write_bytes(sdist)


def _metadata(name: str = "vantio-agent-sdk", version: str = "3.1.1") -> bytes:
    return f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\n\nbody\n".encode()


def _wheel(name: str = "vantio-agent-sdk", version: str = "3.1.1", *, link: bool = False, traversal: bool = False) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        info = zipfile.ZipInfo(f"vantio_agent_sdk-{version}.dist-info/METADATA")
        archive.writestr(info, _metadata(name, version))
        if link:
            linked = zipfile.ZipInfo("vantio/link.py")
            linked.external_attr = (0o120777) << 16
            archive.writestr(linked, "target")
        if traversal:
            archive.writestr("../outside.py", "nope")
    return buffer.getvalue()


def _sdist(name: str = "vantio-agent-sdk", version: str = "3.1.1", *, link: bool = False) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        payload = _metadata(name, version)
        info = tarfile.TarInfo(f"vantio_agent_sdk-{version}/PKG-INFO")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
        if link:
            linked = tarfile.TarInfo(f"vantio_agent_sdk-{version}/vantio/link.py")
            linked.type = tarfile.SYMTYPE
            linked.linkname = "target"
            archive.addfile(linked)
    return buffer.getvalue()


class WorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.doc = yaml.safe_load(cls.raw)
        cls.job = cls.doc["jobs"]["publish"]
        cls.steps = cls.job["steps"]
        trigger = cls.doc.get(True, cls.doc.get("on"))
        cls.trigger = trigger

    def test_yaml_file_and_trigger(self) -> None:
        self.assertEqual(WORKFLOW_PATH.name, "pypi-publish.yml")
        self.assertEqual(list(self.trigger), ["workflow_dispatch"])
        self.assertIsNone(self.trigger["workflow_dispatch"])
        self.assertNotIn("pull_request", self.trigger)
        self.assertNotIn("push", self.trigger)
        self.assertNotIn("workflow_call", self.trigger)
        self.assertNotIn("release", self.trigger)
        self.assertNotIn("pull_request:", self.raw)
        self.assertNotIn("\n  push:", self.raw)
        self.assertNotIn("inputs.", self.raw)

    def test_job_identity_permissions_and_environment(self) -> None:
        self.assertEqual(set(self.doc["jobs"]), {"publish"})
        self.assertEqual(self.doc["permissions"], {"contents": "read"})
        self.assertEqual(self.job["environment"], {"name": "pypi"})
        self.assertEqual(self.job["permissions"], {"contents": "read", "id-token": "write"})
        self.assertEqual(self.raw.count("id-token: write"), 1)
        self.assertNotIn("contents: write", self.raw)
        self.assertEqual(self.doc["concurrency"]["group"], "pypi-vantio-agent-sdk-3.1.1")
        self.assertIs(self.doc["concurrency"]["cancel-in-progress"], False)
        self.assertEqual(self.job["timeout-minutes"], 20)
        self.assertIn("not treat the tag as immutable", self.raw)
        self.assertIn("not the authorized Trusted Publisher upload path", self.raw)

    def test_step_order_and_checkout_cannot_supply_distributions(self) -> None:
        names = [step["name"] for step in self.steps]
        self.assertEqual(
            names,
            [
                "Checkout release scripts",
                "Require the trusted-publisher workflow identity",
                "Stop when 3.1.1 is already on PyPI",
                "Download sealed custody assets",
                "Verify sealed bytes and stage the upload directory",
                "Publish sealed distributions to PyPI",
                "Record publication coordinates",
                "Optics observe (Lab-only)",
                "Upload Optics observation log (Lab-only)",
            ],
        )
        checkout = self.steps[0]
        checkout_uses = "actions/checkout@11d5960a326750d5838078e36cf38b85af677262"
        self.assertEqual(checkout["uses"], checkout_uses)
        self.assertIn(f"uses: {checkout_uses} # v4", self.raw)
        self.assertIs(checkout["with"]["persist-credentials"], False)
        self.assertEqual(
            [line.strip() for line in checkout["with"]["sparse-checkout"].splitlines() if line.strip()],
            [
                "scripts/release/fetch_custody_release.py",
                "scripts/release/stage_sealed_pypi.py",
            ],
        )
        self.assertIs(checkout["with"]["sparse-checkout-cone-mode"], False)
        self.assertNotIn("promote_pypi.py", checkout["with"]["sparse-checkout"])
        self.assertNotIn("packages", checkout["with"]["sparse-checkout"])
        identity = self.steps[1]["run"]
        for banned in (
            "packages/vantio-agent-sdk-py",
            "packages/vantio-cli",
            "packages/optics-evidence-contract",
            "dist",
            "pypi-sealed-upload",
        ):
            self.assertIn(banned, identity)
        self.assertLess(names.index("Download sealed custody assets"), names.index("Publish sealed distributions to PyPI"))
        self.assertLess(names.index("Stop when 3.1.1 is already on PyPI"), names.index("Verify sealed bytes and stage the upload directory"))
        self.assertEqual(names.index("Publish sealed distributions to PyPI"), names.index("Verify sealed bytes and stage the upload directory") + 1)
        self.assertEqual(names[-2], "Optics observe (Lab-only)")
        self.assertEqual(names[-1], "Upload Optics observation log (Lab-only)")
        observe = self.steps[-2]
        upload = self.steps[-1]
        self.assertIs(observe["continue-on-error"], True)
        self.assertEqual(observe["if"], "always()")
        self.assertNotIn("permissions", observe)
        self.assertNotIn("env", observe)
        self.assertIn("npm install -g @vantio/cli", observe["run"])
        self.assertIn("pip install vantio-agent-sdk", observe["run"])
        self.assertNotIn("optics_observe.py", observe["run"])
        self.assertNotIn("--mcp-enforce", observe["run"])
        self.assertEqual(upload["with"]["path"], "optics-observe-log")
        self.assertIs(upload["continue-on-error"], True)
        self.assertEqual(upload["if"], "always()")
        self.assertNotIn("permissions", upload)

    def test_publish_action_is_oidc_and_explicit(self) -> None:
        publish = self.steps[5]
        publish_uses = "pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33"
        self.assertEqual(publish["uses"], publish_uses)
        self.assertIn(f"uses: {publish_uses} # release/v1", self.raw)
        self.assertEqual(
            set(publish["with"]),
            {"packages-dir", "verbose", "print-hash", "skip-existing"},
        )
        self.assertEqual(publish["with"]["packages-dir"], "pypi-sealed-upload")
        self.assertIs(publish["with"]["verbose"], False)
        self.assertIs(publish["with"]["print-hash"], False)
        self.assertIs(publish["with"]["skip-existing"], False)
        self.assertNotIn("env", publish)
        self.assertNotIn("password", publish["with"])
        self.assertNotIn("user", publish["with"])
        for step in self.steps:
            self.assertNotIn("password", step.get("run", "").lower())
            for key in step.get("env", {}):
                self.assertNotIn("PASSWORD", key)
                self.assertNotIn("PYPI", key)
        self.assertNotIn("username", self.raw.lower())
        self.assertNotIn("PYPI_TOKEN", self.raw)
        self.assertNotIn("TWINE", self.raw.upper())
        self.assertNotIn("secrets.", self.raw)
        self.assertNotIn("repository-url", self.raw)
        self.assertNotIn("repository_url", self.raw)
        self.assertNotIn("test.pypi", self.raw)
        self.assertNotIn("attestations:", self.raw)
        self.assertEqual(self.raw.count("github.token"), 1)
        for banned in ("twine", "python -m build", "hatch build", "setup.py", "promote_pypi.py --publish", "skip-existing: true"):
            self.assertNotIn(banned, self.raw)
        for step in self.steps:
            script = step.get("run", "")
            self.assertNotIn("promote_pypi.py", script)
            self.assertNotIn("twine", script)

    def test_pins_match_the_sealed_constants(self) -> None:
        staged = self.steps[4]
        self.assertEqual(staged["env"], {**PIN_ENV, "VANTIO_STAGE_ENFORCE_ACTIONS_CONTEXT": "1"})
        self.assertIn("stage_sealed_pypi.py", staged["run"])
        self.assertIn("$GITHUB_WORKSPACE/pypi-sealed-upload", staged["run"])
        self.assertNotIn("--metadata-url", staged["run"])
        download = self.steps[3]
        self.assertEqual(download["env"], {"GH_TOKEN": "${{ github.token }}"})
        self.assertIn("--tag custody-py-3.1.1", download["run"])
        self.assertIn(f"--wheel-name {WHEEL_NAME}", download["run"])
        self.assertIn(f"--sdist-name {SDIST_NAME}", download["run"])
        self.assertIn("--version 3.1.1", download["run"])
        self.assertNotIn("*", download["run"])
        reject = self.steps[2]
        self.assertIn("--reject-existing-version", reject["run"])
        self.assertNotIn("--metadata-url", reject["run"])
        self.assertNotIn("test.pypi", reject["run"])
        self.assertEqual(stage.WHEEL_SHA256, WHEEL_SHA256)
        self.assertEqual(stage.SDIST_SHA256, SDIST_SHA256)
        self.assertEqual(stage.WHEEL_BYTES, WHEEL_BYTES)
        self.assertEqual(stage.SDIST_BYTES, SDIST_BYTES)
        self.assertEqual(stage.PIN_ENV, PIN_ENV)
        self.assertEqual(stage.PRODUCTION_METADATA_URL, "https://pypi.org/pypi/vantio-agent-sdk/3.1.1/json")

    def test_other_workflows_do_not_publish_python(self) -> None:
        for path in (ROOT / ".github" / "workflows").glob("*.yml"):
            if path.name == "pypi-publish.yml":
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("gh-action-pypi-publish", text)
            self.assertNotIn("stage_sealed_pypi.py", text)

    def test_python_version_pin_remains(self) -> None:
        pyproject = (ROOT / "packages/vantio-agent-sdk-py/pyproject.toml").read_text(encoding="utf-8")
        init = (ROOT / "packages/vantio-agent-sdk-py/vantio/__init__.py").read_text(encoding="utf-8")
        self.assertIn('version = "3.1.1"', pyproject)
        self.assertIn('__version__ = "3.1.1"', init)


class SealedGateTests(unittest.TestCase):
    def test_stager_has_no_upload_client(self) -> None:
        source = STAGE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("subprocess", source)
        self.assertNotIn("twine", source.lower())
        self.assertNotIn("python -m build", source)
        self.assertNotIn("setup.py", source)

    def test_missing_extra_and_renamed_files_fail(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            source = tmp / "source"
            source.mkdir()
            upload = tmp / "pypi-sealed-upload"
            (source / SDIST_NAME).write_bytes(b"y" * 20)
            missing = _run(["--source", str(source), "--upload-dir", str(upload)])
            self.assertEqual(missing.returncode, 1)
            self.assertEqual(_status(missing), "MISSING_FILE")
            self.assertFalse(upload.exists())

            (source / WHEEL_NAME).write_bytes(b"x" * 20)
            (source / "evidence.sqlite").write_bytes(b"db")
            (source / "vantio-cli-0.3.24.tgz").write_bytes(b"cli")
            (source / "optics-evidence-contract-0.0.0.tar.gz").write_bytes(b"pkg")
            extra = _run(["--source", str(source), "--upload-dir", str(upload)])
            self.assertEqual(_status(extra), "EXTRA_FILE")
            self.assertFalse(upload.exists())

            (source / "evidence.sqlite").unlink()
            (source / "vantio-cli-0.3.24.tgz").unlink()
            (source / "optics-evidence-contract-0.0.0.tar.gz").unlink()
            (source / WHEEL_NAME).unlink()
            (source / "vantio-agent-sdk-3.1.0-py3-none-any.whl").write_bytes(b"x" * 20)
            renamed = _run(["--source", str(source), "--upload-dir", str(upload)])
            self.assertEqual(_status(renamed), "MISSING_FILE")

    def test_size_and_hash_mismatch_fail_before_staging(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            source = tmp / "source"
            source.mkdir()
            upload = tmp / "pypi-sealed-upload"
            outside = tmp / "outside"
            outside.mkdir()
            _pair(source, b"x" * 10, b"y" * SDIST_BYTES)
            sized = _run(["--source", str(source), "--upload-dir", str(upload)])
            self.assertEqual(_status(sized), "SIZE_MISMATCH")
            self.assertFalse(upload.exists())
            self.assertEqual(list(outside.iterdir()), [])

            _pair(source, b"x" * WHEEL_BYTES, b"y" * SDIST_BYTES)
            mismatched = _run(["--source", str(source), "--upload-dir", str(upload)])
            self.assertEqual(_status(mismatched), "ARTIFACT_HASH_MISMATCH")
            self.assertFalse(upload.exists())
            marker = upload / "evil.whl"
            upload.mkdir()
            marker.write_bytes(b"rebuilt")
            preserved = _run(["--source", str(source), "--upload-dir", str(upload)])
            self.assertEqual(_status(preserved), "ARTIFACT_HASH_MISMATCH")
            self.assertEqual(marker.read_bytes(), b"rebuilt")

    def test_symlink_hardlink_traversal_and_injection_fail(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            source = tmp / "source"
            source.mkdir()
            upload = tmp / "pypi-sealed-upload"
            target = tmp / "target"
            target.write_bytes(b"x" * WHEEL_BYTES)
            (source / SDIST_NAME).write_bytes(b"y" * SDIST_BYTES)
            (source / WHEEL_NAME).symlink_to(target)
            linked = _run(["--source", str(source), "--upload-dir", str(upload)])
            self.assertEqual(_status(linked), "UNSAFE_PATH")
            self.assertFalse(upload.exists())

        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            source = tmp / "source"
            source.mkdir()
            _pair(source, b"x" * WHEEL_BYTES, b"y" * SDIST_BYTES)
            os.link(source / WHEEL_NAME, tmp / "hardlink")
            duplicate = _run(["--source", str(source), "--upload-dir", str(tmp / "pypi-sealed-upload")])
            self.assertEqual(_status(duplicate), "DUPLICATE_FILE")

        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            source = tmp / "source"
            source.mkdir()
            _pair(source, b"x" * WHEEL_BYTES, b"y" * SDIST_BYTES)
            (source / "$(touch pwned).whl").write_bytes(b"nope")
            injected = _run(["--source", str(source), "--upload-dir", str(tmp / "pypi-sealed-upload")])
            self.assertEqual(_status(injected), "EXTRA_FILE")
            self.assertFalse((tmp / "pwned").exists())
            traversal = _run(
                ["--source", str(source), "--upload-dir", str(tmp / "nested" / ".." / "pypi-sealed-upload")]
            )
            self.assertEqual(_status(traversal), "UNSAFE_PATH")
            wrong_dir = _run(["--source", str(source), "--upload-dir", str(tmp / "dist")])
            self.assertEqual(_status(wrong_dir), "DESIGNATED_DIRECTORY")

    def test_pin_and_trigger_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            upload = Path(raw) / "pypi-sealed-upload"
            upper = _run(
                ["--source", str(Path(raw) / "missing"), "--upload-dir", str(upload)],
                env={"SEALED_WHEEL_SHA256": WHEEL_SHA256.upper()},
            )
            self.assertEqual(_status(upper), "PIN_MISMATCH")
            self.assertFalse(upload.exists())
            dropped = dict(PIN_ENV)
            dropped.pop("SEALED_SDIST_SHA256")
            missing_pin = _run(
                ["--source", str(Path(raw) / "missing"), "--upload-dir", str(upload)],
                pins=False,
                env=dropped,
            )
            self.assertEqual(_status(missing_pin), "PIN_MISSING")

        rejected = _run(
            ["--reject-existing-version"],
            pins=False,
            env={
                "VANTIO_STAGE_ENFORCE_ACTIONS_CONTEXT": "1",
                "GITHUB_EVENT_NAME": "pull_request",
                "GITHUB_REF": "refs/heads/main",
                "GITHUB_REPOSITORY": "vantioai/vantio-open-core",
                "GITHUB_WORKFLOW_REF": stage.WORKFLOW_REF,
            },
        )
        self.assertEqual(_status(rejected), "TRIGGER_REJECTED")
        pushed = _run(
            ["--source", "sealed", "--upload-dir", "pypi-sealed-upload"],
            env={
                "VANTIO_STAGE_ENFORCE_ACTIONS_CONTEXT": "1",
                "GITHUB_EVENT_NAME": "push",
                "GITHUB_REF": "refs/heads/main",
                "GITHUB_REPOSITORY": "vantioai/vantio-open-core",
                "GITHUB_WORKFLOW_REF": stage.WORKFLOW_REF,
            },
        )
        self.assertEqual(_status(pushed), "TRIGGER_REJECTED")

    def test_existing_version_fails_and_absence_is_local_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            seen: list[str] = []

            class Handler(BaseHTTPRequestHandler):
                def do_GET(self) -> None:  # noqa: N802
                    seen.append(self.command)
                    status = 200 if tmp.joinpath("live").exists() else 404
                    self.send_response(status)
                    self.end_headers()

                def do_POST(self) -> None:  # noqa: N802
                    seen.append("POST")
                    self.send_response(500)
                    self.end_headers()

                def log_message(self, fmt: str, *args: object) -> None:
                    return

            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f"http://127.0.0.1:{server.server_address[1]}/pypi/vantio-agent-sdk/3.1.1/json"
            try:
                absent = _run(
                    ["--reject-existing-version", "--metadata-url", url],
                    pins=False,
                    env={"VANTIO_RELEASE_TEST": "1"},
                )
                self.assertEqual(absent.returncode, 0, absent.stderr)
                self.assertEqual(_status(absent), "VERSION_ABSENT")
                tmp.joinpath("live").write_text("1", encoding="utf-8")
                exists = _run(
                    ["--reject-existing-version", "--metadata-url", url],
                    pins=False,
                    env={"VANTIO_RELEASE_TEST": "1"},
                )
                self.assertEqual(exists.returncode, 2, exists.stdout + exists.stderr)
                self.assertEqual(_status(exists), "VERSION_ALREADY_EXISTS")
                self.assertNotIn("POST", seen)
                self.assertTrue(seen)
                self.assertTrue(all(method == "GET" for method in seen))
            finally:
                server.shutdown()
                server.server_close()

        rejected = _run(
            ["--reject-existing-version", "--metadata-url", "https://test.pypi.org/legacy/"],
            pins=False,
            env={"VANTIO_RELEASE_TEST": "1"},
        )
        self.assertEqual(_status(rejected), "REGISTRY_URL_REJECTED")
        blocked = _run(
            ["--reject-existing-version", "--metadata-url", "http://127.0.0.1/pypi/vantio-agent-sdk/3.1.1/json"],
            pins=False,
        )
        self.assertEqual(_status(blocked), "REGISTRY_URL_REJECTED")
        with self.assertRaises(stage.StageFailure) as unexpected:
            stage.classify_registry_status(500)
        self.assertEqual(unexpected.exception.status, "REGISTRY_LOOKUP_FAILED")
        stage.classify_registry_status(404)

    def test_identity_rejects_other_packages_and_unsafe_archives(self) -> None:
        with self.assertRaises(stage.StageFailure) as other:
            stage.assert_wheel_identity(_wheel("vantio-cli"))
        self.assertEqual(other.exception.status, "ARTIFACT_IDENTITY_MISMATCH")
        with self.assertRaises(stage.StageFailure) as pkg:
            stage.assert_sdist_identity(_sdist("optics-evidence-contract"))
        self.assertEqual(pkg.exception.status, "ARTIFACT_IDENTITY_MISMATCH")
        with self.assertRaises(stage.StageFailure) as sqlite_name:
            stage.assert_wheel_identity(_wheel("sqlite-store"))
        self.assertEqual(sqlite_name.exception.status, "ARTIFACT_IDENTITY_MISMATCH")
        with self.assertRaises(stage.StageFailure) as linked:
            stage.assert_wheel_identity(_wheel(link=True))
        self.assertEqual(linked.exception.status, "UNSAFE_ARCHIVE_MEMBER")
        with self.assertRaises(stage.StageFailure) as traversal:
            stage.assert_wheel_identity(_wheel(traversal=True))
        self.assertEqual(traversal.exception.status, "UNSAFE_ARCHIVE_MEMBER")
        with self.assertRaises(stage.StageFailure) as sdist_link:
            stage.assert_sdist_identity(_sdist(link=True))
        self.assertEqual(sdist_link.exception.status, "UNSAFE_ARCHIVE_MEMBER")
        stage.assert_package_identity(_wheel(), _sdist())

    def test_custody_dry_run_uses_the_pinned_names(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(FETCH_PATH),
                "--tag",
                "custody-py-3.1.1",
                "--version",
                "3.1.1",
                "--wheel-name",
                WHEEL_NAME,
                "--sdist-name",
                SDIST_NAME,
                "--dest",
                "/tmp/vantio-sealed-custody-dry-run",
                "--dry-run",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("custody-py-3.1.1", result.stdout)
        self.assertIn(WHEEL_NAME, result.stdout)
        self.assertIn(SDIST_NAME, result.stdout)
        self.assertIn("vantioai/vantio-open-core", result.stdout)
        self.assertNotIn("*", result.stdout)

    def test_real_sealed_bytes_stage_when_fixture_is_present(self) -> None:
        fixture = os.environ.get("VANTIO_SEALED_DIR")
        if not fixture:
            self.skipTest("VANTIO_SEALED_DIR is not set")
        supplied = Path(fixture)
        wheel = supplied / WHEEL_NAME
        sdist = supplied / SDIST_NAME
        self.assertEqual(wheel.stat().st_size, WHEEL_BYTES)
        self.assertEqual(sdist.stat().st_size, SDIST_BYTES)
        self.assertEqual(hashlib.sha256(wheel.read_bytes()).hexdigest(), WHEEL_SHA256)
        self.assertEqual(hashlib.sha256(sdist.read_bytes()).hexdigest(), SDIST_SHA256)
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            source = tmp / "custody"
            source.mkdir()
            (source / WHEEL_NAME).write_bytes(wheel.read_bytes())
            (source / SDIST_NAME).write_bytes(sdist.read_bytes())
            if any(path.name not in {WHEEL_NAME, SDIST_NAME} for path in supplied.iterdir()):
                dirty = _run(["--source", str(supplied), "--upload-dir", str(tmp / "dirty" / "pypi-sealed-upload")])
                self.assertEqual(_status(dirty), "EXTRA_FILE")
            upload = tmp / "pypi-sealed-upload"
            outside = tmp / "outside"
            outside.mkdir()
            upload.mkdir()
            (upload / "rebuilt.whl").write_bytes(b"not-the-sealed-wheel")
            result = _run(["--source", str(source), "--upload-dir", str(upload)])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(_status(result), "STAGED")
            payload = json.loads(result.stdout.removeprefix("STAGE_RESULT ").strip())
            self.assertIs(payload["published"], False)
            self.assertEqual({path.name for path in upload.iterdir()}, {SDIST_NAME, WHEEL_NAME})
            staged_wheel = upload / WHEEL_NAME
            staged_sdist = upload / SDIST_NAME
            self.assertFalse(staged_wheel.is_symlink())
            self.assertFalse(staged_sdist.is_symlink())
            self.assertEqual(staged_wheel.stat().st_nlink, 1)
            self.assertEqual(staged_sdist.stat().st_nlink, 1)
            self.assertEqual(stat.S_ISREG(staged_wheel.stat().st_mode), True)
            self.assertEqual(staged_wheel.read_bytes(), wheel.read_bytes())
            self.assertEqual(staged_sdist.read_bytes(), sdist.read_bytes())
            self.assertEqual(staged_wheel.stat().st_size, WHEEL_BYTES)
            self.assertEqual(staged_sdist.stat().st_size, SDIST_BYTES)
            self.assertEqual(list(outside.iterdir()), [])
            self.assertNotIn("rebuilt.whl", {path.name for path in upload.iterdir()})


class SealedByteTests(unittest.TestCase):
    def test_prepare_script_prints_the_tag_command_and_does_not_create_it(self) -> None:
        script = ROOT / "scripts" / "release" / "prepare_custody_py_3_1_1.py"
        source = script.read_text(encoding="utf-8")
        self.assertNotIn("subprocess", source)
        self.assertNotIn("git tag -a", source)
        refused = subprocess.run([sys.executable, str(script), "--apply"], check=False, capture_output=True, text=True)
        self.assertEqual(refused.returncode, 2, refused.stderr)
        self.assertIn("does not create custody-py-3.1.1", refused.stderr)
        result = subprocess.run([sys.executable, str(script)], check=False, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("TAG_CREATED false", result.stdout)
        self.assertIn("custody-py-3.1.1", result.stdout)
        self.assertIn(WHEEL_NAME, result.stdout)
        self.assertIn(SDIST_NAME, result.stdout)
        self.assertIn("gh release create", result.stdout)
        listed = subprocess.run(["git", "tag", "--list", "custody-py-3.1.1"], check=False, capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(listed.stdout.strip(), "")

    def test_second_build_matches_the_sealed_files(self) -> None:
        pins = json.loads((ROOT / "docs/programs/release-engineering/SEALED-RELEASE-PINS.json").read_text(encoding="utf-8"))
        row = pins["python"]
        self.assertEqual(row["state"], "SEALED_BYTES_RECORDED_NOT_PUBLISHED")
        self.assertIs(row["custody_tag_created"], False)
        self.assertEqual(row["publisher_commit"], "63df79c8f81cc90a03bea559838c0989d0e35ebc")
        self.assertEqual(row["prior_state"], "PUBLISHED_REGISTRY_BYTES_VERIFIED_CLIENT_PROVED")
        stored = {}
        for name, rel, digest, size in (
            (WHEEL_NAME, row["wheel_path"], WHEEL_SHA256, WHEEL_BYTES),
            (SDIST_NAME, row["sdist_path"], SDIST_SHA256, SDIST_BYTES),
        ):
            data = (ROOT / rel).read_bytes()
            self.assertEqual(len(data), size)
            self.assertEqual(hashlib.sha256(data).hexdigest(), digest)
            stored[name] = data
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            tools = tmp / "tools"
            install = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "--target",
                    str(tools),
                    *row["build_requires"],
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(install.returncode, 0, install.stderr)
            env = os.environ.copy()
            env["PYTHONPATH"] = str(tools)
            env["SOURCE_DATE_EPOCH"] = row["source_date_epoch"]
            env["PYTHONHASHSEED"] = "0"
            env["TZ"] = "UTC"
            env.pop("PYTHONSAFEPATH", None)
            built = tmp / "dist"
            result = subprocess.run(
                [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(built), str(ROOT / "packages" / "vantio-agent-sdk-py")],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for name, data in stored.items():
                rebuilt = (built / name).read_bytes()
                self.assertEqual(hashlib.sha256(rebuilt).hexdigest(), hashlib.sha256(data).hexdigest(), name)
                self.assertEqual(rebuilt, data, name)


if __name__ == "__main__":
    unittest.main()
