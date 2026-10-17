"""Lab-only checks for the CI Optics observe step."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ci"))

import optics_observe as observe  # noqa: E402

PIN = "e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e"
UPLOAD = "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02"
CI_JOBS = {
    "lint-and-test-js": "optics-observe-lint-and-test-js",
    "test-python": "optics-observe-test-python-${{ matrix.python-version }}",
    "release-governance": "optics-observe-release-governance",
    "candidate-artifacts": "optics-observe-candidate-artifacts",
    "test-vantio-install": "optics-observe-test-vantio-install",
    "test-openshell-reconciliation": "optics-observe-test-openshell-reconciliation",
    "test-optics-agent-inventory": "optics-observe-test-optics-agent-inventory",
    "test-t5-kernel": "optics-observe-test-t5-kernel",
}
PRODUCER_MARKERS = (
    "vantio-artifacts.tar.gz",
    "release-approval.json",
    "--upload-dir",
    "npm pack",
    "python3 -m build",
    "python -m build",
    "mcp-publisher publish",
    "mcp-publisher login",
    "fetch_custody_release.py",
    "GITHUB_STEP_SUMMARY",
    "--publish",
    "gh release",
    "git tag",
    "github.token",
    "secrets.",
)


def norm_run(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return value.rstrip("\n")


class ParserTests(unittest.TestCase):
    def test_parser_matches_pyyaml_for_ci_workflows(self) -> None:
        for rel in (
            ".github/workflows/ci.yml",
            ".github/workflows/t0-own-stack-hygiene.yml",
            ".github/workflows/docs-release-governance.yml",
        ):
            text = (ROOT / rel).read_text(encoding="utf-8")
            doc = yaml.safe_load(text)
            parsed = observe.parse_jobs(text)
            self.assertEqual(list(doc["jobs"]), list(parsed))
            for job_id, job in doc["jobs"].items():
                steps = job.get("steps") or []
                ours = parsed[job_id]
                self.assertEqual(len(steps), len(ours), job_id)
                for raw, got in zip(steps, ours):
                    self.assertEqual(raw.get("name"), got.get("name"))
                    self.assertEqual(norm_run(raw.get("run")), got.get("run"))
                    self.assertEqual(raw.get("working-directory"), got.get("working_directory"))
                    self.assertEqual(raw.get("env") or {}, got.get("env") or {})


class PolicyTests(unittest.TestCase):
    def test_release_workflows_stay_on_the_release_policy(self) -> None:
        for name in observe.RELEASE_WORKFLOWS:
            self.assertEqual(observe.effective_policy("replay", name), "release")
            self.assertEqual(observe.effective_policy(None, f".github/workflows/{name}"), "release")

    def test_release_plan_does_not_run_producers_or_publishers(self) -> None:
        subs = {
            "inputs.package": "vantio-optics-mcp",
            "inputs.version": "0.0.0",
            "inputs.source_commit": "a" * 40,
            "inputs.artifact_sha256": "b" * 64,
            "github.sha": "c" * 40,
        }
        for name in sorted(observe.RELEASE_WORKFLOWS):
            text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
            for job_id in observe.parse_jobs(text):
                for item in observe.plan_job(text, name, job_id, "replay", subs):
                    if item["action"] != "run":
                        continue
                    script = item.get("script") or ""
                    for marker in PRODUCER_MARKERS:
                        self.assertNotIn(marker, script, f"{name} {item.get('name')} ran {marker}")
                    self.assertNotIn("--mcp-enforce", script)

    def test_ci_policy_replays_shell_commands(self) -> None:
        text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        items = observe.plan_job(text, "ci.yml", "lint-and-test-js", "replay", {})
        ran = [item["name"] for item in items if item["action"] == "run"]
        self.assertIn("Test @vantio/cli", ran)
        self.assertIn("Lint @vantio/cli", ran)


class WorkflowWiringTests(unittest.TestCase):
    def test_ci_jobs_end_with_a_non_gating_observe_step(self) -> None:
        text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertNotIn("permissions:", text)
        doc = yaml.safe_load(text)
        self.assertIsNone(doc.get("permissions"))
        self.assertEqual(set(doc["jobs"]), set(CI_JOBS))
        for job_id, artifact in CI_JOBS.items():
            self.assert_tail(doc["jobs"][job_id], artifact, "replay", "900", 45)
            env = doc["jobs"][job_id]["steps"][-2]["env"]
            self.assertEqual(env["OPTICS_OBSERVE_WORKFLOW"], ".github/workflows/ci.yml")
            self.assertEqual(env["OPTICS_OBSERVE_JOB"], job_id)

    def test_other_pull_request_workflows_are_wired(self) -> None:
        cases = (
            (".github/workflows/t0-own-stack-hygiene.yml", "hygiene", "optics-observe-hygiene", {"contents": "read"}),
            (
                ".github/workflows/docs-release-governance.yml",
                "docs-release-governance",
                "optics-observe-docs-release-governance",
                {"contents": "read"},
            ),
        )
        for rel, job_id, artifact, permissions in cases:
            text = (ROOT / rel).read_text(encoding="utf-8")
            doc = yaml.safe_load(text)
            self.assertEqual(doc["permissions"], permissions)
            self.assert_tail(doc["jobs"][job_id], artifact, "replay", "900", 45)
            self.assertNotIn("secrets.", text[text.rfind(observe.OBSERVE_STEP) :])

    def test_founder_guard_and_lab_workflows_are_not_instrumented(self) -> None:
        guard = (ROOT / ".github/workflows/founder-approval-guard.yml").read_text(encoding="utf-8")
        self.assertNotIn("optics_observe.py", guard)
        self.assertNotIn(observe.OBSERVE_STEP, guard)
        for path in (ROOT / ".github/workflows").glob("*.yml"):
            if path.name.startswith(("gcp-lab", "w3-lab")):
                self.assertNotIn("optics_observe.py", path.read_text(encoding="utf-8"))

    def assert_tail(self, job: dict, artifact: str, policy: str, timeout: str, minutes: int) -> None:
        observe_step, upload = job["steps"][-2], job["steps"][-1]
        self.assertEqual(observe_step["name"], observe.OBSERVE_STEP)
        self.assertIs(observe_step["continue-on-error"], True)
        self.assertEqual(observe_step["if"], "always()")
        self.assertEqual(observe_step["timeout-minutes"], minutes)
        self.assertNotIn("permissions", observe_step)
        self.assertIn("python3 scripts/ci/optics_observe.py", observe_step["run"])
        self.assertNotIn("--mcp-enforce", observe_step["run"])
        self.assertEqual(observe_step["env"]["OPTICS_OBSERVE_POLICY"], policy)
        self.assertEqual(observe_step["env"]["OPTICS_OBSERVE_COMMAND_TIMEOUT"], timeout)
        self.assertEqual(upload["name"], observe.UPLOAD_STEP)
        self.assertIs(upload["continue-on-error"], True)
        self.assertEqual(upload["if"], "always()")
        self.assertEqual(upload["uses"], UPLOAD)
        self.assertEqual(upload["with"]["name"], artifact)
        self.assertEqual(upload["with"]["path"], "${{ runner.temp }}/optics-observe-artifact")
        self.assertEqual(upload["with"]["if-no-files-found"], "warn")
        self.assertNotIn("permissions", upload)


class RuntimeTests(unittest.TestCase):
    def test_real_cli_observe_writes_a_run_log_in_observe_mode(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            out = root / "out"
            mode_out = root / "mode.txt"
            workflow = root / "workflow.yml"
            workflow.write_text(
                textwrap.dedent(
                    """\
                    jobs:
                      demo:
                        steps:
                          - name: Exit cleanly
                            run: node -e 'require("fs").writeFileSync(process.env.OPTICS_MODE_OUT, process.env.VANTIO_MCP_MODE || "")'
                    """
                ),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env.update(
                {
                    "OPTICS_OBSERVE_WORKFLOW": str(workflow),
                    "OPTICS_OBSERVE_JOB": "demo",
                    "OPTICS_OBSERVE_POLICY": "replay",
                    "OPTICS_OBSERVE_ROOT": str(root),
                    "OPTICS_OBSERVE_OUT": str(out),
                    "OPTICS_OBSERVE_CLI": str(ROOT / "packages/vantio-cli/bin/vantio.js"),
                    "OPTICS_OBSERVE_COMMAND_TIMEOUT": "30",
                    "OPTICS_MODE_OUT": str(mode_out),
                    "RUNNER_TEMP": str(root / "runner"),
                    "VANTIO_MCP_MODE": "enforce",
                }
            )
            env.pop("VANTIO_API_KEY", None)
            manifest = observe.run_observation(env)
            self.assertEqual(manifest["evidence_label"], "Lab-only")
            self.assertEqual(manifest["mode"], "observe")
            self.assertEqual(manifest["enforcement"], "not_enabled")
            self.assertEqual(manifest["mcp_mode"], "observe")
            ran = [item for item in manifest["commands"] if item["action"] == "ran"]
            self.assertEqual(len(ran), 1)
            self.assertEqual(ran[0]["exit_code"], 0)
            self.assertEqual(mode_out.read_text(encoding="utf-8"), "observe")
            logs = list((out / "runs").glob("*.json"))
            self.assertEqual(len(logs), 1)
            body = json.loads(logs[0].read_text(encoding="utf-8"))
            self.assertEqual(body["plane"], "optics")
            self.assertEqual(body["summary"]["blocked"], 0)
            self.assertNotIn("--mcp-enforce", logs[0].read_text(encoding="utf-8"))

    def test_command_failure_does_not_fail_the_process(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            workflow = root / "workflow.yml"
            workflow.write_text(
                "jobs:\n  demo:\n    steps:\n      - name: Fail\n        run: exit 7\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env.update(
                {
                    "OPTICS_OBSERVE_WORKFLOW": str(workflow),
                    "OPTICS_OBSERVE_JOB": "demo",
                    "OPTICS_OBSERVE_ROOT": str(root),
                    "OPTICS_OBSERVE_OUT": str(root / "out"),
                    "OPTICS_OBSERVE_CLI": str(ROOT / "packages/vantio-cli/bin/vantio.js"),
                    "OPTICS_OBSERVE_COMMAND_TIMEOUT": "30",
                    "RUNNER_TEMP": str(root / "runner"),
                }
            )
            result = subprocess.run([sys.executable, str(ROOT / "scripts/ci/optics_observe.py")], check=False, env=env, cwd=root)
            self.assertEqual(result.returncode, 0)
            manifest = json.loads((root / "out" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["commands"][0]["exit_code"], 7)
            self.assertEqual(manifest["commands"][0]["action"], "ran")

    def test_child_env_strips_tokens_and_forces_observe(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            log = root / "fake.json"
            fake = root / "fake-vantio.js"
            fake.write_text(
                textwrap.dedent(
                    """\
                    const fs = require("fs");
                    const payload = {
                      argv: process.argv.slice(2),
                      mode: process.env.VANTIO_MCP_MODE || "",
                      keys: Object.keys(process.env).filter((key) => /TOKEN|SECRET|PASSWORD|API_KEY/i.test(key)),
                    };
                    fs.writeFileSync(process.env.OPTICS_FAKE_LOG, JSON.stringify(payload));
                    process.exit(0);
                    """
                ),
                encoding="utf-8",
            )
            workflow = root / "workflow.yml"
            workflow.write_text(
                "jobs:\n  demo:\n    steps:\n      - name: Noop\n        run: exit 0\n",
                encoding="utf-8",
            )
            secret = "test-token-value-not-real"
            env = os.environ.copy()
            env.update(
                {
                    "OPTICS_OBSERVE_WORKFLOW": str(workflow),
                    "OPTICS_OBSERVE_JOB": "demo",
                    "OPTICS_OBSERVE_ROOT": str(root),
                    "OPTICS_OBSERVE_OUT": str(root / "out"),
                    "OPTICS_OBSERVE_CLI": str(fake),
                    "OPTICS_OBSERVE_COMMAND_TIMEOUT": "30",
                    "OPTICS_FAKE_LOG": str(log),
                    "RUNNER_TEMP": str(root / "runner"),
                    "GITHUB_TOKEN": secret,
                    "VANTIO_MCP_MODE": "enforce",
                    "VANTIO_API_KEY": secret,
                }
            )
            observe.run_observation(env)
            payload = json.loads(log.read_text(encoding="utf-8"))
            self.assertEqual(payload["argv"][:2], ["run", "node"])
            self.assertNotIn("--mcp-enforce", payload["argv"])
            self.assertEqual(payload["mode"], "observe")
            self.assertEqual(payload["keys"], [])
            self.assertFalse(secret in log.read_text(encoding="utf-8"))

    def test_sparse_extract_does_not_create_workspace_packages(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "repo"
            pkg = root / "packages" / "vantio-cli" / "bin"
            pkg.mkdir(parents=True)
            (pkg / "vantio.js").write_text("#!/usr/bin/env node\nprocess.exit(0);\n", encoding="utf-8")
            env = os.environ.copy()
            env.update({"GIT_AUTHOR_NAME": "Optics Test", "GIT_AUTHOR_EMAIL": "optics@example.com", "GIT_COMMITTER_NAME": "Optics Test", "GIT_COMMITTER_EMAIL": "optics@example.com"})
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True, env=env)
            subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True, env=env)
            subprocess.run(["git", "commit", "-m", "cli"], cwd=root, check=True, capture_output=True, env=env)
            shutil.rmtree(root / "packages")
            outside = Path(raw) / "temp"
            outside.mkdir()
            found = observe.locate_cli(root, outside, {})
            self.assertIsNotNone(found)
            self.assertFalse((root / "packages").exists())
            self.assertTrue(str(found).startswith(str(outside)))
            self.assertIsNone(observe.locate_cli(root, root / "inside", {}))
            self.assertFalse((root / "packages").exists())


class PinTests(unittest.TestCase):
    def test_public_installer_pin_is_unchanged(self) -> None:
        text = (ROOT / "packages/vantio-install/vantio_install/constants.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(text.count(PIN), 2)
        self.assertTrue(PIN.startswith(observe.PUBLIC_PIN_PREFIX))

    def test_observer_source_has_no_prices_or_navera(self) -> None:
        text = (ROOT / "scripts/ci/optics_observe.py").read_text(encoding="utf-8").lower()
        self.assertNotIn("navera", text)
        self.assertNotIn("price", text)


if __name__ == "__main__":
    unittest.main()
