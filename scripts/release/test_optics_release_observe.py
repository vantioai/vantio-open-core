"""Checks that release workflows observe the commands they actually run.

The PyPI upload action and the unchanged producer steps keep their bytes.
The install step fails when the CLI cannot be installed.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


def _partner_markers() -> list[str]:
    """Deployment-partner substrings from VANTIO_PARTNER_MARKERS. Unset means none."""
    raw = os.environ.get("VANTIO_PARTNER_MARKERS", "")
    return [item.strip().lower() for item in raw.split(",") if item.strip()]

ROOT = Path(__file__).resolve().parents[2]
PIN = "e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e"
UPLOAD = "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02"

PRODUCER_SHA256 = {
    ("enterprise-slsa-provenance.yml", "Install dependencies"): "a9247ec0a45d05e7f8087c1254528b4a2beb504c1bbc40309f363b93dfba4143",
    ("enterprise-slsa-provenance.yml", "Build @vantio/agent-sdk"): "1e34c21d78a450b8e4ca5408236409a2fb8a95afcba204d08183694d0110de0f",
    ("enterprise-slsa-provenance.yml", "Bundle artifacts"): "eb280f9cefaa61d99e67b401446bd879eb5ab2976f229613a16d58c01efb81c6",
    ("enterprise-slsa-provenance.yml", "Attest build provenance"): "82121f5399143347205160e628c7df09dd0166706dddd45d22dcd35d27047db3",
    ("enterprise-slsa-provenance.yml", "Provenance honesty note"): "f1f0f1e9d24c20091c777368567fcfed8073a80d72e7f306b01d9ae619b6ddc5",
    ("pypi-publish.yml", "Publish sealed distributions to PyPI"): "0459cdda21c6bf996a19be5802438df922fa862ddd37efcfae930583db310b14",
    ("pypi-publish.yml", "Record publication coordinates"): "86a89301eab696b3aacc08a00e6e3a4d102a0d4310f5268c775f94b275ff25bf",
    ("npm-publish.yml", "Write release summary"): "9f8e6f04644efac14448c037dea7042c9539a2d8436666ce756d3f77eff94f19",
    ("mcp-registry-publish.yml", "Install mcp-publisher"): "e0854fdc1a007af84889ced22beba7a0ccebca9254fcea86ebd97e7939d59f9c",
}
WRAPPED = {
    ("pypi-publish.yml", "Stop when 3.1.2 is already on PyPI"): "vantio run python3 scripts/release/stage_sealed_pypi.py --reject-existing-version",
    ("pypi-publish.yml", "Download sealed custody assets"): "vantio run python3 scripts/release/fetch_custody_release.py",
    ("pypi-publish.yml", "Verify sealed bytes and stage the upload directory"): "vantio run python3 scripts/release/stage_sealed_pypi.py",
    ("npm-publish.yml", "Gate sealed request"): "vantio run node scripts/release/promote_npm.mjs --gate",
    ("npm-publish.yml", "Re-check coordinates after approval"): "vantio run node scripts/release/promote_npm.mjs --gate",
    ("npm-publish.yml", "Write approval record"): "vantio run python3 - <<'PY'",
    ("mcp-registry-publish.yml", "Authenticate (GitHub OIDC)"): "vantio run mcp-publisher login github-oidc",
    ("mcp-registry-publish.yml", "Publish to MCP Registry"): "vantio run mcp-publisher publish",
}
RUNNER = (
    "${{ fromJSON(vars.VANTIO_ENROLLED_RUNNER == 'true' && "
    "'[\"self-hosted\", \"vantio-enrolled\"]' || '\"ubuntu-latest\"') }}"
)

PERMISSIONS = {
    "npm-publish.yml": {"contents": "read"},
    "pypi-publish.yml": {"contents": "read"},
    "mcp-registry-publish.yml": {"contents": "read", "id-token": "write"},
    "enterprise-slsa-provenance.yml": {"id-token": "write", "contents": "read", "attestations": "write"},
}
JOB_PERMISSIONS = {
    ("npm-publish.yml", "validate"): None,
    ("npm-publish.yml", "record-approval"): {"contents": "read", "actions": "write"},
    ("pypi-publish.yml", "publish"): {"contents": "read", "id-token": "write"},
    ("mcp-registry-publish.yml", "publish"): None,
    ("enterprise-slsa-provenance.yml", "build-and-attest"): None,
}
ARTIFACTS = {
    ("npm-publish.yml", "validate"): "optics-observe-validate",
    ("npm-publish.yml", "record-approval"): "optics-observe-record-approval",
    ("pypi-publish.yml", "publish"): "optics-observe-pypi-publish",
    ("mcp-registry-publish.yml", "publish"): "optics-observe-mcp-publish",
    ("enterprise-slsa-provenance.yml", "build-and-attest"): "optics-observe-provenance",
}
BANNED = (
    "optics_observe.py",
    "packages/vantio-cli",
    "--mcp-enforce",
    "npm publish",
    "mcp-publisher",
    "stage_sealed_pypi.py",
    "fetch_custody_release.py",
    "vantio-artifacts.tar.gz",
    "release-approval.json",
    "npm pack",
    "python -m build",
    "python3 -m build",
    "secrets.",
    "GH_TOKEN",
    "sudo ",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def step_blob(step: dict) -> bytes:
    run = step.get("run") or ""
    if isinstance(run, str):
        run = run.rstrip("\n")
    uses = step.get("uses") or ""
    return (run + "\n" + uses).encode()


def observe_steps(job: dict) -> tuple[dict, dict]:
    observe = [step for step in job["steps"] if step.get("name") == "Optics observe (Lab-only)"]
    upload = [step for step in job["steps"] if step.get("name") == "Upload Optics observation log (Lab-only)"]
    if len(observe) != 1 or len(upload) != 1:
        raise AssertionError(job.get("name"))
    return observe[0], upload[0]


def step_named(job: dict, name: str) -> dict:
    found = [step for step in job.get("steps") or [] if step.get("name") == name]
    if len(found) != 1:
        raise AssertionError(name)
    return found[0]


class ReleaseWiringTests(unittest.TestCase):
    def test_customer_install_and_unchanged_permissions(self) -> None:
        for name, permissions in PERMISSIONS.items():
            text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
            doc = yaml.safe_load(text)
            self.assertEqual(doc.get("permissions"), permissions)
            if name != "enterprise-slsa-provenance.yml":
                self.assertNotIn("\n  push:", "\n" + text.split("jobs:", 1)[0])
            for job_id, job in doc["jobs"].items():
                self.assertEqual(job.get("permissions"), JOB_PERMISSIONS[(name, job_id)])
                if name == "enterprise-slsa-provenance.yml":
                    self.assert_legacy_noop(job, ARTIFACTS[(name, job_id)])
                    continue
                self.assertEqual(job["runs-on"], RUNNER)
                self.assert_real_observe(job, ARTIFACTS[(name, job_id)])
            if name == "pypi-publish.yml":
                self.assertEqual(text.count("id-token: write"), 1)
                self.assertNotIn("contents: write", text)
                self.assertNotIn("optics_observe.py", text)
                self.assertIn("pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33 # release/v1", text)

    def assert_legacy_noop(self, job: dict, artifact: str) -> None:
        observe, upload = observe_steps(job)
        self.assertEqual(job["steps"][-2]["name"], observe["name"])
        self.assertEqual(job["steps"][-1]["name"], upload["name"])
        self.assertIs(observe["continue-on-error"], True)
        self.assertIn("vantio run node -e 'process.exit(0)'", observe["run"])
        self.assertIs(upload["continue-on-error"], True)
        self.assertEqual(upload["with"]["name"], artifact)

    def assert_real_observe(self, job: dict, artifact: str) -> None:
        install = step_named(job, "Install Optics observe CLI")
        collect = step_named(job, "Collect Optics observation log")
        upload = step_named(job, "Upload Optics observation log")
        self.assertEqual(job["steps"][-2]["name"], collect["name"])
        self.assertEqual(job["steps"][-1]["name"], upload["name"])
        self.assertNotIn("continue-on-error", install)
        self.assertNotIn("continue-on-error", collect)
        self.assertNotIn("continue-on-error", upload)
        self.assertEqual(install["timeout-minutes"], 5)
        self.assertEqual(collect["if"], "always()")
        self.assertEqual(upload["if"], "always()")
        script = install["run"]
        self.assertIn("set -euo pipefail", script)
        self.assertIn("npm install -g --prefix", script)
        self.assertIn("@vantio/cli", script)
        self.assertIn("python3 -m pip install --disable-pip-version-check --user vantio-agent-sdk", script)
        self.assertIn("vantio CLI install failed:", script)
        self.assertNotIn("set +e", script)
        self.assertNotIn("exit 0", script)
        self.assertNotIn("process.exit(0)", script)
        for banned in BANNED:
            self.assertNotIn(banned, script, banned)
        self.assertIn('cp -a "${HOME}/.vantio/runs/." optics-observe-log/', collect["run"])
        self.assertNotIn("permissions", install)
        self.assertNotIn("env", install)
        self.assertEqual(upload["uses"], UPLOAD)
        self.assertEqual(upload["with"]["name"], artifact)
        self.assertEqual(upload["with"]["path"], "optics-observe-log")
        node_wrapped = any("vantio run node " in (step.get("run") or "") for step in job["steps"])
        if "steps.npm-wait.outcome" in collect["run"]:
            self.assertEqual(upload["with"]["if-no-files-found"], "warn")
            self.assertIn("exit 1", collect["run"])
        elif node_wrapped:
            self.assertEqual(upload["with"]["if-no-files-found"], "error")
            self.assertIn("exit 1", collect["run"])
        else:
            self.assertEqual(upload["with"]["if-no-files-found"], "warn")
        self.assertNotIn("permissions", upload)

    def test_producer_steps_keep_their_bytes(self) -> None:
        for (name, step_name), digest in PRODUCER_SHA256.items():
            doc = yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))
            found = None
            for job in doc["jobs"].values():
                for step in job["steps"]:
                    if step.get("name") == step_name:
                        found = step
            self.assertIsNotNone(found, step_name)
            self.assertEqual(hashlib.sha256(step_blob(found)).hexdigest(), digest)

    def test_real_commands_are_wrapped(self) -> None:
        for (name, step_name), snippet in WRAPPED.items():
            doc = yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))
            found = None
            for job in doc["jobs"].values():
                for step in job["steps"]:
                    if step.get("name") == step_name:
                        found = step
            self.assertIsNotNone(found, step_name)
            self.assertIn(snippet, found["run"])
            self.assertNotIn("process.exit(0)", found["run"])
            self.assertNotIn("continue-on-error", found)


class ByteIdentityTests(unittest.TestCase):
    def test_install_failure_is_loud_and_does_not_touch_release_files(self) -> None:
        doc = yaml.safe_load((ROOT / ".github/workflows/pypi-publish.yml").read_text(encoding="utf-8"))
        script = step_named(doc["jobs"]["publish"], "Install Optics observe CLI")["run"]
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            home = root / "home"
            home.mkdir()
            sealed = root / "pypi-sealed-upload" / "pkg.whl"
            sealed.parent.mkdir()
            sealed.write_bytes(b"wheel")
            before = sha256(sealed)
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["PATH"] = "/bin"
            env["RUNNER_TEMP"] = str(root / "runner")
            env["GITHUB_PATH"] = str(root / "github-path")
            env["GITHUB_WORKSPACE"] = str(root)
            result = subprocess.run(["bash", "-c", script], cwd=root, env=env, check=False, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("vantio CLI install failed: npm is not on PATH", result.stderr)
            self.assertEqual(sha256(sealed), before)
            self.assertFalse((home / "CORRUPT").exists())


class PinTests(unittest.TestCase):
    def test_public_installer_pin_is_unchanged(self) -> None:
        seal = json.loads((ROOT / "release" / "pe-canonical-seal.json").read_text(encoding="utf-8"))
        text = (ROOT / "packages/vantio-install/vantio_install/constants.py").read_text(encoding="utf-8")
        self.assertEqual(seal["public_pin"]["archive_sha256"], PIN)
        self.assertNotIn(PIN, text)
        self.assertIn("pe-canonical-seal.json", text)

    def test_friction_log_is_present(self) -> None:
        text = (ROOT / "docs/dogfood/CUSTOMER-FRICTION.md").read_text(encoding="utf-8")
        self.assertIn("Lab-only", text)
        self.assertIn("npm install -g @vantio/cli", text)
        for marker in _partner_markers():
            self.assertNotIn(marker, text.lower())
        self.assertNotIn("price", text.lower())


if __name__ == "__main__":
    unittest.main()
