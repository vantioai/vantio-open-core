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
DOC_PATH = ROOT / "docs" / "internal" / "c8-teardown" / "README.md"
SCRIPT_PATH = ROOT / "scripts" / "aws" / "verify_w3_lab_teardown.py"
ROLE_ARN = "arn:aws:iam::960577828987:role/vantio-w3-lab-teardown"
POLICY_SHA256 = "2fd3909fe84cbe93b15c5525ece0d247d0f4f4a91e333346001d512e1efc5215"


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
        self.assertEqual(set(self.doc["jobs"]), {"verify"})
        self.assertEqual(self.doc["permissions"], {"contents": "read", "id-token": "write"})
        self.assertNotIn("contents: write", self.raw)
        self.assertEqual(self.job["environment"], "w3-lab-teardown")
        self.assertEqual(self.job["timeout-minutes"], 20)
        self.assertIs(self.doc["concurrency"]["cancel-in-progress"], False)
        settings = self.assume["with"]
        self.assertEqual(self.assume["uses"], "aws-actions/configure-aws-credentials@v6")
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
        self.assertEqual(checkout["uses"], "actions/checkout@v4")
        self.assertIs(checkout["with"]["persist-credentials"], False)
        self.assertIn("scripts/aws/verify_w3_lab_teardown.py", checkout["with"]["sparse-checkout"])
        upload = self.steps[-1]
        self.assertEqual(upload["uses"], "actions/upload-artifact@v4")
        self.assertEqual(upload["if"], "always()")
        self.assertIn("w3-lab-teardown-verify.json", upload["with"]["path"])
        joined = "\n".join(step.get("run", "") for step in self.steps)
        self.assertIn('test "$GITHUB_EVENT_NAME" = "workflow_dispatch"', joined)
        self.assertIn('test "$GITHUB_REPOSITORY" = "vantioai/vantio-open-core"', joined)
        self.assertIn('test "$GITHUB_REF" = "refs/heads/main"', joined)

    def test_doc_and_script_share_the_policy_hash(self) -> None:
        doc = DOC_PATH.read_text(encoding="utf-8")
        script = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertIn("INTERNAL_RESTRICTED", doc)
        self.assertIn(POLICY_SHA256, doc)
        self.assertIn(POLICY_SHA256, script)
        self.assertIn("vantio-w3-class-b-lab-01", doc)
        self.assertIn("STAGE_B_BILLING_CLOSE_PASS", doc)
        self.assertIn("NONINTERACTIVE_TEARDOWN_READY", doc)
        self.assertIn("STAGE_B_BILLING_CLOSE_PENDING", doc)
        self.assertIn("403", doc)
        self.assertIn("zacharybalicki", doc)


if __name__ == "__main__":
    unittest.main()
