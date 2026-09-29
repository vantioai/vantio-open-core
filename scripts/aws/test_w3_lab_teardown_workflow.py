#!/usr/bin/env python3
"""Contract tests for the manual W3 lab teardown OIDC workflow.

These tests parse the workflow. They do not assume a role.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "w3-lab-teardown-verify.yml"
SCRIPT_PATH = ROOT / "scripts" / "aws" / "verify_w3_lab_teardown.py"
ROLE_ARN = "arn:aws:iam::960577828987:role/vantio-w3-lab-teardown"
POLICY_SHA256 = "2fd3909fe84cbe93b15c5525ece0d247d0f4f4a91e333346001d512e1efc5215"
CHECKOUT_USES = "actions/checkout@11d5960a326750d5838078e36cf38b85af677262"
UPLOAD_USES = "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02"
AWS_USES = "aws-actions/configure-aws-credentials@e1253824e5c10ff9df46874f81ed3ec929e19cfd"


def trigger_of(document: dict) -> dict:
    if True in document:
        return document[True]
    return document["on"]


class WorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.doc = yaml.safe_load(cls.raw)
        cls.job = cls.doc["jobs"]["verify"]
        cls.preflight = cls.doc["jobs"]["preflight"]
        cls.steps = cls.job["steps"]
        cls.trigger = trigger_of(cls.doc)
        cls.assume = next(step for step in cls.steps if step.get("id") == "aws")
        cls.verify = next(step for step in cls.steps if step.get("name") == "Verify role boundaries")

    def test_manual_trigger_only(self) -> None:
        self.assertEqual(list(self.trigger), ["workflow_dispatch"])
        self.assertNotIn("pull_request", self.trigger)
        self.assertNotIn("push", self.trigger)
        self.assertNotIn("schedule", self.trigger)
        self.assertNotIn("workflow_call", self.trigger)
        self.assertNotIn("\n  push:", self.raw)
        self.assertNotIn("\n  pull_request:", self.raw)
        self.assertEqual(self.trigger["workflow_dispatch"]["inputs"]["run_destructive_fixtures"]["default"], False)

    def test_oidc_permissions_environment_and_role(self) -> None:
        self.assertEqual(set(self.doc["jobs"]), {"preflight", "verify"})
        self.assertEqual(self.doc["permissions"], {"contents": "read", "id-token": "write"})
        self.assertNotIn("contents: write", self.raw)
        self.assertNotIn("environment", self.preflight)
        self.assertEqual(self.preflight["permissions"], {"contents": "read"})
        self.assertNotIn("administration", self.preflight["permissions"])
        self.assertNotIn("administration:", self.raw)
        self.assertNotIn("id-token", self.preflight["permissions"])
        self.assertEqual(self.job["needs"], "preflight")
        self.assertEqual(self.job["environment"], "w3-lab-teardown")
        self.assertEqual(self.job["timeout-minutes"], 20)
        self.assertIs(self.doc["concurrency"]["cancel-in-progress"], False)
        settings = self.assume["with"]
        self.assertEqual(self.assume["uses"], AWS_USES)
        self.assertIn(f"uses: {AWS_USES} # v6", self.raw)
        self.assertEqual(settings["role-to-assume"], ROLE_ARN)
        self.assertEqual(settings["aws-region"], "us-east-2")
        self.assertEqual(str(settings["role-duration-seconds"]), "3600")
        self.assertEqual(settings["role-session-name"], "w3-lab-teardown-verify-${{ github.run_id }}")
        self.assertEqual(settings["audience"], "sts.amazonaws.com")
        self.assertEqual(str(settings["allowed-account-ids"]), "960577828987")
        self.assertIs(settings["use-existing-credentials"], False)
        self.assertIs(settings["output-credentials"], True)
        self.assertIs(self.assume["continue-on-error"], True)
        for banned in ("aws-access-key-id", "aws-secret-access-key", "aws-session-token", "force-skip-oidc"):
            self.assertNotIn(banned, settings)

    def test_secret_outputs_are_not_passed_on(self) -> None:
        env = self.verify["env"]
        blob = "\n".join(str(value) for value in env.values())
        self.assertIn("steps.aws.outputs.aws-expiration", blob)
        self.assertNotIn("aws-secret-access-key", blob)
        self.assertNotIn("aws-session-token", blob)
        self.assertNotIn("aws-access-key-id", blob)
        self.assertIn("RUN_DESTRUCTIVE_FIXTURES", env)
        self.assertIn("false", env["RUN_DESTRUCTIVE_FIXTURES"])

    def test_checkout_and_artifact(self) -> None:
        checkout = self.steps[2]
        self.assertEqual(checkout["uses"], CHECKOUT_USES)
        self.assertIn(f"uses: {CHECKOUT_USES} # v4", self.raw)
        self.assertIs(checkout["with"]["persist-credentials"], False)
        self.assertIn("scripts/aws/verify_w3_lab_teardown.py", checkout["with"]["sparse-checkout"])
        upload = self.steps[-1]
        self.assertEqual(upload["uses"], UPLOAD_USES)
        self.assertIn(f"uses: {UPLOAD_USES} # v4", self.raw)
        self.assertEqual(upload["if"], "always()")
        self.assertIn("w3-lab-teardown-verify.json", upload["with"]["path"])
        joined = "\n".join(step.get("run", "") for step in self.steps)
        self.assertIn('test "$GITHUB_EVENT_NAME" = "workflow_dispatch"', joined)
        self.assertIn('test "$GITHUB_REPOSITORY" = "vantioai/vantio-open-core"', joined)
        self.assertIn('test "$GITHUB_REF" = "refs/heads/main"', joined)
        workflow_ref = 'test "$GITHUB_WORKFLOW_REF" = "vantioai/vantio-open-core/.github/workflows/w3-lab-teardown-verify.yml@refs/heads/main"'
        self.assertIn(workflow_ref, joined)
        preflight_joined = "\n".join(step.get("run", "") for step in self.preflight["steps"])
        self.assertIn(workflow_ref, preflight_joined)
        self.assertEqual(self.raw.count(workflow_ref), 2)
        self.assertIn("gh api repos/vantioai/vantio-open-core/environments/w3-lab-teardown", preflight_joined)

    def test_script_and_workflow_share_the_policy_hash(self) -> None:
        script = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertIn(POLICY_SHA256, script)
        self.assertIn("INTERNAL_RESTRICTED", script)
        self.assertIn("vantio-w3-class-b-lab-01", script)
        self.assertIn("NONINTERACTIVE_TEARDOWN_READY", script)
        self.assertIn("prepared_digest", script)
        self.assertIn("GetUser", script)
        self.assertIn("CreateSecurityGroup --dry-run", script)
        self.assertIn("STAGE_B_BILLING_CLOSE_PASS", self.raw)
        self.assertIn("NONINTERACTIVE_TEARDOWN_READY", self.raw)
        self.assertNotIn("docs/internal/", self.raw)
        self.assertNotIn("i-0deadbeef0deadbee", script)
        self.assertIn("does not call TerminateInstances", self.raw)
        self.assertNotIn("calls TerminateInstances only with --dry-run", self.raw)


if __name__ == "__main__":
    unittest.main()
