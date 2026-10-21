"""Lab-only checks for the customer-shaped CI observe step."""

from __future__ import annotations

import json
import os
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
CI_JOBS = {
    "lint-and-test-js": ("optics-observe-lint-and-test-js", 15),
    "test-python": ("optics-observe-test-python-${{ matrix.python-version }}", 20),
    "release-governance": ("optics-observe-release-governance", 15),
    "candidate-artifacts": ("optics-observe-candidate-artifacts", 15),
    "test-vantio-install": ("optics-observe-test-vantio-install", 15),
    "test-openshell-reconciliation": ("optics-observe-test-openshell-reconciliation", 15),
    "test-optics-agent-inventory": ("optics-observe-test-optics-agent-inventory", 15),
    "test-t5-kernel": ("optics-observe-test-t5-kernel", 15),
}
BANNED = (
    "optics_observe.py",
    "packages/vantio-cli",
    "--mcp-enforce",
    "npm publish",
    "npm pack",
    "python3 -m build",
    "python -m build",
    "sudo ",
    "secrets.",
    "GH_TOKEN",
)


class WorkflowWiringTests(unittest.TestCase):
    def test_ci_jobs_use_the_published_install(self) -> None:
        text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertNotIn("permissions:", text)
        doc = yaml.safe_load(text)
        self.assertIsNone(doc.get("permissions"))
        self.assertEqual(set(doc["jobs"]), set(CI_JOBS))
        for job_id, (artifact, minutes) in CI_JOBS.items():
            self.assert_customer_tail(doc["jobs"][job_id], artifact, minutes)
        python_job = doc["jobs"]["test-python"]["steps"][-2]["run"]
        self.assertIn("vantio run python -m unittest discover -s tests -t . -v", python_job)
        candidate = doc["jobs"]["candidate-artifacts"]["steps"][-2]["run"]
        self.assertNotIn("npm pack", candidate)
        self.assertNotIn("python3 -m build", candidate)

    def test_other_pull_request_workflows_use_the_published_install(self) -> None:
        docs = yaml.safe_load((ROOT / ".github/workflows/docs-release-governance.yml").read_text(encoding="utf-8"))
        self.assertEqual(docs["permissions"], {"contents": "read"})
        self.assert_customer_tail(
            docs["jobs"]["docs-release-governance"],
            "optics-observe-docs-release-governance",
            20,
        )
        self.assertIn(
            "vantio run node --test docs/scripts/check-docs-release.test.mjs",
            docs["jobs"]["docs-release-governance"]["steps"][-2]["run"],
        )
        hygiene = yaml.safe_load((ROOT / ".github/workflows/t0-own-stack-hygiene.yml").read_text(encoding="utf-8"))
        self.assertEqual(hygiene["permissions"], {"contents": "read"})
        job = hygiene["jobs"]["hygiene"]
        install = next(step for step in job["steps"] if step["name"] == "Install Optics observe CLI")
        upload = job["steps"][-1]
        self.assertNotIn("continue-on-error", install)
        self.assertNotIn("continue-on-error", upload)
        self.assertIn("vantio CLI install failed:", install["run"])
        self.assertIn("npm install -g --prefix", install["run"])
        checker = next(step for step in job["steps"] if step["name"] == "Test the checker")
        proof = next(step for step in job["steps"] if step["name"] == "Re-run the proof against the committed evidence")
        self.assertIn("vantio run python3 tests/gap/test_t0_openclaw_hygiene.py -v", checker["run"])
        self.assertIn("vantio run python3 scripts/gap/t0_proof.py --check", proof["run"])
        self.assertNotIn("process.exit(0)", install["run"])
        self.assertEqual(upload["with"]["name"], "optics-observe-hygiene")
        self.assertEqual(upload["with"]["if-no-files-found"], "warn")
        self.assertEqual(
            job["runs-on"],
            "${{ fromJSON(vars.VANTIO_ENROLLED_RUNNER == 'true' && '[\"self-hosted\", \"vantio-enrolled\"]' || '\"ubuntu-latest\"') }}",
        )

    def test_lab_workflows_wrap_real_commands(self) -> None:
        # The founder-approval guard workflow was retired on 2026-10-21 by Founder direction.
        self.assertFalse((ROOT / ".github/workflows/founder-approval-guard.yml").exists())
        runner = (
            "${{ fromJSON(vars.VANTIO_ENROLLED_RUNNER == 'true' && "
            "'[\"self-hosted\", \"vantio-enrolled\"]' || '\"ubuntu-latest\"') }}"
        )
        for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
            if not path.name.startswith(("gcp-lab", "w3-lab")):
                continue
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
            for job in doc["jobs"].values():
                if "runs-on" in job:
                    self.assertEqual(job["runs-on"], runner, path.name)
                steps = job.get("steps") or []
                if not steps:
                    continue
                install = next(step for step in steps if step.get("name") == "Install Optics observe CLI")
                upload = steps[-1]
                self.assertEqual(upload["name"], "Upload Optics observation log", path.name)
                self.assertNotIn("continue-on-error", install)
                self.assertNotIn("continue-on-error", upload)
                self.assertIn("vantio CLI install failed:", install["run"])
                wrapped = "\n".join(step.get("run") or "" for step in steps)
                self.assertIn("vantio run ", wrapped, path.name)
                self.assertNotIn("process.exit(0)", wrapped)

    def assert_customer_tail(self, job: dict, artifact: str, minutes: int) -> None:
        observe, upload = job["steps"][-2], job["steps"][-1]
        self.assertEqual(observe["name"], "Optics observe (Lab-only)")
        self.assertIs(observe["continue-on-error"], True)
        self.assertEqual(observe["if"], "always()")
        self.assertEqual(observe["timeout-minutes"], minutes)
        self.assertNotIn("permissions", observe)
        self.assertNotIn("env", observe)
        script = observe["run"]
        self.assertIn("npm install -g @vantio/cli", script)
        self.assertIn("pip install vantio-agent-sdk", script)
        self.assertIn("vantio run node -e 'process.exit(0)'", script)
        self.assertIn("vantio run python -c 'raise SystemExit(0)'", script)
        self.assertIn('cp -a "$HOME/.vantio/runs/." optics-observe-log/', script)
        for banned in BANNED:
            self.assertNotIn(banned, script)
        self.assertEqual(upload["name"], "Upload Optics observation log (Lab-only)")
        self.assertIs(upload["continue-on-error"], True)
        self.assertEqual(upload["if"], "always()")
        self.assertEqual(upload["uses"], UPLOAD)
        self.assertEqual(upload["with"]["name"], artifact)
        self.assertEqual(upload["with"]["path"], "optics-observe-log")
        self.assertEqual(upload["with"]["if-no-files-found"], "warn")


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
