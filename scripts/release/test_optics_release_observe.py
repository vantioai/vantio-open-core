"""Lab-only checks for the customer-shaped release observe step.

The published bytes stay identical because this step does not run the commands
that write them. It installs the registry packages and runs the documented
`vantio run` commands.
"""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PIN = "e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e"
UPLOAD = "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02"

PRODUCER_SHA256 = {
    ("enterprise-slsa-provenance.yml", "Install dependencies"): "a9247ec0a45d05e7f8087c1254528b4a2beb504c1bbc40309f363b93dfba4143",
    ("enterprise-slsa-provenance.yml", "Build @vantio/agent-sdk"): "1e34c21d78a450b8e4ca5408236409a2fb8a95afcba204d08183694d0110de0f",
    ("enterprise-slsa-provenance.yml", "Bundle artifacts"): "eb280f9cefaa61d99e67b401446bd879eb5ab2976f229613a16d58c01efb81c6",
    ("enterprise-slsa-provenance.yml", "Attest build provenance"): "82121f5399143347205160e628c7df09dd0166706dddd45d22dcd35d27047db3",
    ("enterprise-slsa-provenance.yml", "Provenance honesty note"): "f1f0f1e9d24c20091c777368567fcfed8073a80d72e7f306b01d9ae619b6ddc5",
    ("pypi-publish.yml", "Download sealed custody assets"): "a91843b05df90174a510c6599d51be229e8c22675eb431eebecff95b4fae5437",
    ("pypi-publish.yml", "Verify sealed bytes and stage the upload directory"): "d316efdfcd9cace74f01e8ebd4a12fc7bf35ca814b7838fdbd81a810b9d19e5a",
    ("pypi-publish.yml", "Publish sealed distributions to PyPI"): "0459cdda21c6bf996a19be5802438df922fa862ddd37efcfae930583db310b14",
    ("pypi-publish.yml", "Record publication coordinates"): "6bbf8335c2031d4f46a45ad6c1e2cbacd03d13131937f2add832ac323fa1ba0b",
    ("npm-publish.yml", "Write approval record"): "bbf7098db8fb4e1851b5eae258f1aa76ce17175955512439a71c20272e3060dd",
    ("npm-publish.yml", "Write release summary"): "9f8e6f04644efac14448c037dea7042c9539a2d8436666ce756d3f77eff94f19",
    ("mcp-registry-publish.yml", "Install mcp-publisher"): "e0854fdc1a007af84889ced22beba7a0ccebca9254fcea86ebd97e7939d59f9c",
    ("mcp-registry-publish.yml", "Authenticate (GitHub OIDC)"): "3b60b308ad6a4b73add4a00eb3f66f2ecf0285e51776038b5b94d88fc7932711",
    ("mcp-registry-publish.yml", "Wait for npm package version"): "43d8361b4cc61b070ad382149fc301f227e1233b3a9f2caeb725577b9047024e",
    ("mcp-registry-publish.yml", "Publish to MCP Registry"): "1f84a1c9c4ca761a7cadf1c5b89e70951452f21a89a75955d73b0c518c4dd2d1",
}

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
                observe, upload = observe_steps(job)
                self.assertEqual(job["steps"][-2]["name"], observe["name"])
                self.assertEqual(job["steps"][-1]["name"], upload["name"])
                self.assertIs(observe["continue-on-error"], True)
                self.assertEqual(observe["if"], "always()")
                self.assertEqual(observe["timeout-minutes"], 10)
                self.assertNotIn("permissions", observe)
                self.assertNotIn("env", observe)
                script = observe["run"]
                self.assertIn("npm install -g @vantio/cli", script)
                self.assertIn("pip install vantio-agent-sdk", script)
                self.assertIn("vantio run node -e 'process.exit(0)'", script)
                self.assertIn("vantio run python -c 'raise SystemExit(0)'", script)
                self.assertIn('cp -a "$HOME/.vantio/runs/." optics-observe-log/', script)
                for banned in BANNED:
                    self.assertNotIn(banned, script, f"{name} {job_id} {banned}")
                self.assertIs(upload["continue-on-error"], True)
                self.assertEqual(upload["if"], "always()")
                self.assertEqual(upload["uses"], UPLOAD)
                self.assertEqual(upload["with"]["name"], ARTIFACTS[(name, job_id)])
                self.assertEqual(upload["with"]["path"], "optics-observe-log")
                self.assertEqual(upload["with"]["if-no-files-found"], "warn")
                self.assertNotIn("permissions", upload)
            if name == "pypi-publish.yml":
                self.assertEqual(text.count("id-token: write"), 1)
                self.assertNotIn("contents: write", text)
                self.assertNotIn("optics_observe.py", text)

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


class ByteIdentityTests(unittest.TestCase):
    def test_customer_shell_does_not_change_published_files(self) -> None:
        doc = yaml.safe_load((ROOT / ".github/workflows/enterprise-slsa-provenance.yml").read_text(encoding="utf-8"))
        script = observe_steps(doc["jobs"]["build-and-attest"])[0]["run"]
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            home = root / "home"
            home.mkdir()
            files = {
                "vantio-artifacts.tar.gz": b"tar-bytes",
                "vantio-artifacts.sha256": b"sha-bytes\n",
                "release-approval.json": b'{"approved":true}\n',
                "pypi-sealed-upload/pkg.whl": b"wheel",
                "packages/vantio-agent-sdk/dist/index.js": b"dist",
            }
            for rel, data in files.items():
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            before = {rel: sha256(root / rel) for rel in files}
            bindir = root / "bin"
            bindir.mkdir()
            self.write_tool(bindir / "npm", "exit 0\n")
            self.write_tool(bindir / "pip", "exit 0\n")
            self.write_tool(
                bindir / "vantio",
                textwrap.dedent(
                    """\
                    #!/bin/sh
                    case "$*" in
                      *publish*|*pack*|*stage_sealed*|*custody*|*mcp-publisher*|*tar*)
                        echo changed > "$HOME/CORRUPT"
                        exit 9
                        ;;
                    esac
                    mkdir -p "$HOME/.vantio/runs"
                    printf '%s\\n' '{"plane":"optics"}' > "$HOME/.vantio/runs/run.json"
                    exit 0
                    """
                ),
            )
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
            env["GITHUB_WORKSPACE"] = str(root)
            result = subprocess.run(["bash", "-lc", script], cwd=root, env=env, check=False, capture_output=True, text=True)
            after = {rel: sha256(root / rel) for rel in files}
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((home / "CORRUPT").exists(), result.stderr)
            self.assertEqual(before, after)
            self.assertTrue((root / "optics-observe-log" / "run.json").is_file())

    def write_tool(self, path: Path, body: str) -> None:
        path.write_text(body, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)


class PinTests(unittest.TestCase):
    def test_public_installer_pin_is_unchanged(self) -> None:
        text = (ROOT / "packages/vantio-install/vantio_install/constants.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(text.count(PIN), 2)

    def test_friction_log_is_present(self) -> None:
        text = (ROOT / "docs/dogfood/CUSTOMER-FRICTION.md").read_text(encoding="utf-8")
        self.assertIn("Lab-only", text)
        self.assertIn("npm install -g @vantio/cli", text)
        self.assertNotIn("navera", text.lower())
        self.assertNotIn("price", text.lower())


if __name__ == "__main__":
    unittest.main()
