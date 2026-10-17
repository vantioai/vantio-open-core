"""Lab-only proof that release observe does not change published bytes."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ci"))

import optics_observe as observe  # noqa: E402

PIN = "e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e"
UPLOAD = "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02"

# SHA-256 of the producer step script or action id. These steps are not edited
# by the observe addition. A change here means the publish path changed.
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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def step_blob(step: dict) -> bytes:
    return ((step.get("run") or "") + "\n" + (step.get("uses") or "")).encode()


class ReleaseWiringTests(unittest.TestCase):
    def test_permissions_and_observe_tail(self) -> None:
        for name, permissions in PERMISSIONS.items():
            text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
            doc = yaml.safe_load(text)
            self.assertEqual(doc.get("permissions"), permissions)
            if name != "enterprise-slsa-provenance.yml":
                self.assertNotIn("\n  push:", "\n" + text.split("jobs:", 1)[0])
                self.assertNotIn("pull_request:", text)
            for job_id, job in doc["jobs"].items():
                self.assertEqual(job.get("permissions"), JOB_PERMISSIONS[(name, job_id)])
                observe_step, upload = job["steps"][-2], job["steps"][-1]
                self.assertEqual(observe_step["name"], observe.OBSERVE_STEP)
                self.assertIs(observe_step["continue-on-error"], True)
                self.assertEqual(observe_step["if"], "always()")
                self.assertEqual(observe_step["timeout-minutes"], 10)
                self.assertNotIn("permissions", observe_step)
                self.assertEqual(observe_step["env"]["OPTICS_OBSERVE_POLICY"], "release")
                self.assertEqual(observe_step["env"]["OPTICS_OBSERVE_WORKFLOW"], f".github/workflows/{name}")
                self.assertEqual(observe_step["env"]["OPTICS_OBSERVE_JOB"], job_id)
                self.assertNotIn("secrets.", observe_step["run"])
                self.assertNotIn("--mcp-enforce", observe_step["run"])
                self.assertEqual(upload["name"], observe.UPLOAD_STEP)
                self.assertIs(upload["continue-on-error"], True)
                self.assertEqual(upload["if"], "always()")
                self.assertEqual(upload["uses"], UPLOAD)
                self.assertEqual(upload["with"]["name"], ARTIFACTS[(name, job_id)])
                self.assertEqual(upload["with"]["if-no-files-found"], "warn")
                self.assertNotIn("permissions", upload)
            if name == "pypi-publish.yml":
                self.assertNotIn("inputs.", text)
                self.assertEqual(text.count("id-token: write"), 1)
                self.assertNotIn("contents: write", text)

    def test_producer_steps_keep_their_bytes(self) -> None:
        for (name, step_name), digest in PRODUCER_SHA256.items():
            text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
            found = None
            for steps in observe.parse_jobs(text).values():
                for step in steps:
                    if step.get("name") == step_name:
                        found = step
            self.assertIsNotNone(found, step_name)
            self.assertEqual(hashlib.sha256(step_blob(found)).hexdigest(), digest)
            item = observe.classify(found, name, "replay", {})
            self.assertEqual(item["action"], "skip", step_name)
            self.assertNotEqual(item["reason"], "observe")


class ByteIdentityTests(unittest.TestCase):
    def test_provenance_bundle_bytes_stay_identical(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            dist = root / "packages" / "vantio-agent-sdk" / "dist"
            bindir = root / "packages" / "vantio-cli" / "bin"
            dist.mkdir(parents=True)
            bindir.mkdir(parents=True)
            (dist / "index.js").write_text("dist-bytes\n", encoding="utf-8")
            (bindir / "vantio.js").write_text("bin-bytes\n", encoding="utf-8")
            text = (ROOT / ".github/workflows/enterprise-slsa-provenance.yml").read_text(encoding="utf-8")
            bundle = next(step["run"] for step in observe.parse_jobs(text)["build-and-attest"] if step["name"] == "Bundle artifacts")
            subprocess.run(["bash", "-lc", bundle], cwd=root, check=True)
            before = {
                "tar": sha256(root / "vantio-artifacts.tar.gz"),
                "sha": sha256(root / "vantio-artifacts.sha256"),
                "dist": sha256(dist / "index.js"),
                "bin": sha256(bindir / "vantio.js"),
            }
            called: list[str] = []

            def runner(item: dict, ctx: dict) -> tuple[int, bool]:
                called.append(item.get("name") or "")
                (ctx["cwd"] / "vantio-artifacts.tar.gz").write_bytes(b"changed-by-observe")
                return 0, False

            self.run_job(root, "enterprise-slsa-provenance.yml", "build-and-attest", runner)
            after = {
                "tar": sha256(root / "vantio-artifacts.tar.gz"),
                "sha": sha256(root / "vantio-artifacts.sha256"),
                "dist": sha256(dist / "index.js"),
                "bin": sha256(bindir / "vantio.js"),
            }
            self.assertEqual(called, [])
            self.assertEqual(before, after)
            print(f"BYTE_IDENTITY provenance tar={before['tar']} shafile={before['sha']}", file=sys.stderr)

    def test_release_files_stay_identical_when_safe_commands_run(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            files = {
                "release-approval.json": b'{"approved":true,"package":"example"}\n',
                "pypi-sealed-upload/vantio_agent_sdk-3.1.0-py3-none-any.whl": b"wheel-bytes",
                "pypi-sealed-upload/vantio_agent_sdk-3.1.0.tar.gz": b"sdist-bytes",
                "packages/vantio-optics-mcp/server.json": b'{"name":"vantio-optics-mcp"}\n',
                "packages/vantio-gate-mcp/server.json": b'{"name":"vantio-gate-mcp"}\n',
            }
            for rel, data in files.items():
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            before = {rel: sha256(root / rel) for rel in files}
            calls: list[tuple[str, str]] = []

            def runner(item: dict, ctx: dict) -> tuple[int, bool]:
                script = item.get("script") or ""
                calls.append((ctx["label"], item.get("name") or ""))
                if not observe.release_allowed(script):
                    for rel in files:
                        (root / rel).write_bytes(b"changed-by-observe")
                return 0, False

            self.run_job(root, "npm-publish.yml", "validate", runner, label="npm-validate")
            self.run_job(root, "npm-publish.yml", "record-approval", runner, label="npm-record")
            self.run_job(root, "pypi-publish.yml", "publish", runner, label="pypi")
            self.run_job(root, "mcp-registry-publish.yml", "publish", runner, label="mcp")
            after = {rel: sha256(root / rel) for rel in files}
            self.assertEqual(before, after)
            self.assertEqual(
                calls,
                [
                    ("npm-validate", "Gate sealed request"),
                    ("npm-record", "Re-check coordinates after approval"),
                    ("pypi", "Require the trusted-publisher workflow identity"),
                    ("pypi", "Stop when 3.1.0 is already on PyPI"),
                    ("mcp", "Reject unknown package"),
                    ("mcp", "Validate server.json"),
                ],
            )
            print(
                "BYTE_IDENTITY "
                + " ".join(f"{name}={digest}" for name, digest in before.items()),
                file=sys.stderr,
            )

    def run_job(self, root: Path, workflow: str, job: str, runner, label: str = "") -> dict:
        env = os.environ.copy()
        env.update(
            {
                "OPTICS_OBSERVE_WORKFLOW": str(ROOT / ".github" / "workflows" / workflow),
                "OPTICS_OBSERVE_JOB": job,
                "OPTICS_OBSERVE_POLICY": "replay",
                "OPTICS_OBSERVE_ROOT": str(root),
                "OPTICS_OBSERVE_OUT": str(root / "out" / label),
                "OPTICS_OBSERVE_CLI": str(ROOT / "packages/vantio-cli/bin/vantio.js"),
                "OPTICS_OBSERVE_COMMAND_TIMEOUT": "5",
                "OPTICS_OBSERVE_INPUT_PACKAGE": "vantio-optics-mcp",
                "OPTICS_OBSERVE_INPUT_VERSION": "0.0.0",
                "OPTICS_OBSERVE_INPUT_COMMIT": "a" * 40,
                "OPTICS_OBSERVE_INPUT_SHA256": "b" * 64,
                "RUNNER_TEMP": str(root / "runner" / label),
                "GITHUB_SHA": "c" * 40,
                "GITHUB_ACTOR": "optics-observe-test",
            }
        )

        def wrapped(item: dict, ctx: dict) -> tuple[int, bool]:
            ctx = dict(ctx)
            ctx["label"] = label
            return runner(item, ctx)

        return observe.run_observation(env, wrapped)


class PinTests(unittest.TestCase):
    def test_public_installer_pin_is_unchanged(self) -> None:
        text = (ROOT / "packages/vantio-install/vantio_install/constants.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(text.count(PIN), 2)

    def test_observer_source_has_no_prices_or_navera(self) -> None:
        text = (ROOT / "scripts/ci/optics_observe.py").read_text(encoding="utf-8").lower()
        self.assertNotIn("navera", text)
        self.assertNotIn("price", text)


if __name__ == "__main__":
    unittest.main()
