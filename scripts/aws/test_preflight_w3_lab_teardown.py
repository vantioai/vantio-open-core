#!/usr/bin/env python3
"""Tests for the w3-lab-teardown environment preflight.

These tests use canned GitHub API payloads. They do not call GitHub.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "aws"))

import preflight_w3_lab_teardown as preflight  # noqa: E402


def environment(**overrides) -> dict:
    payload = {
        "name": "w3-lab-teardown",
        "protection_rules": [
            {"type": "branch_policy"},
        ],
        "deployment_branch_policy": {"protected_branches": False, "custom_branch_policies": True},
    }
    payload.update(overrides)
    return payload


def with_reviewer(login: str = "someone", reviewer_id: int = 1) -> dict:
    payload = environment()
    payload["protection_rules"] = [
        {
            "type": "required_reviewers",
            "prevent_self_review": False,
            "reviewers": [
                {"type": "User", "reviewer": {"login": login, "id": reviewer_id}},
            ],
        },
        {"type": "branch_policy"},
    ]
    return payload


def branches(*names: str) -> dict:
    policies = [{"name": name, "type": "branch"} for name in names]
    return {"total_count": len(policies), "branch_policies": policies}


class PreflightTests(unittest.TestCase):
    def test_protected_main_only_environment_passes(self) -> None:
        ok, detail = preflight.evaluate(environment(), branches("main"))
        self.assertTrue(ok)
        self.assertIn("only branch main", detail)
        self.assertIn("no required reviewers", detail)

    def test_empty_reviewer_list_still_passes(self) -> None:
        payload = environment()
        payload["protection_rules"] = [
            {"type": "required_reviewers", "reviewers": []},
            {"type": "branch_policy"},
        ]
        ok, detail = preflight.evaluate(payload, branches("main"))
        self.assertTrue(ok)
        self.assertIn("no required reviewers", detail)

    def test_any_required_reviewer_fails(self) -> None:
        ok, detail = preflight.evaluate(with_reviewer(), branches("main"))
        self.assertFalse(ok)
        self.assertIn("required reviewer is still set", detail)

    def test_missing_environment_fails_with_founder_instruction(self) -> None:
        ok, detail = preflight.evaluate({"message": "Not Found", "status": "404"}, {"message": "Not Found"})
        self.assertFalse(ok)
        self.assertIn("does not exist", detail)
        self.assertIn("BEFORE any dispatch", detail)
        self.assertIn("delete it", detail)
        self.assertIn("auto-creates", detail)

    def test_unprotected_environment_fails(self) -> None:
        ok, detail = preflight.evaluate(
            environment(protection_rules=[], deployment_branch_policy=None),
            {"total_count": 0, "branch_policies": []},
        )
        self.assertFalse(ok)
        self.assertIn("deployment_branch_policy is missing", detail)
        self.assertIn("no required reviewers", detail)

    def test_founder_reviewer_fails(self) -> None:
        ok, detail = preflight.evaluate(with_reviewer("zacharybalicki", 269605088), branches("main"))
        self.assertFalse(ok)
        self.assertIn("required reviewer is still set", detail)

    def test_malformed_reviewer_list_fails(self) -> None:
        payload = environment()
        payload["protection_rules"] = [
            {"type": "required_reviewers"},
            {"type": "branch_policy"},
        ]
        ok, detail = preflight.evaluate(payload, branches("main"))
        self.assertFalse(ok)
        self.assertIn("required reviewer is still set", detail)

    def test_extra_branch_fails(self) -> None:
        ok, detail = preflight.evaluate(environment(), branches("main", "develop"))
        self.assertFalse(ok)
        self.assertIn("only main", detail)

    def test_protected_branches_flag_fails(self) -> None:
        payload = environment(
            deployment_branch_policy={"protected_branches": True, "custom_branch_policies": False}
        )
        ok, detail = preflight.evaluate(payload, branches("main"))
        self.assertFalse(ok)
        self.assertIn("protected_branches", detail)

    def test_tag_named_main_fails(self) -> None:
        policies = {"total_count": 1, "branch_policies": [{"name": "main", "type": "tag"}]}
        ok, detail = preflight.evaluate(environment(), policies)
        self.assertFalse(ok)
        self.assertIn("not the main branch", detail)

    def test_cli_exits_nonzero_on_missing_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / "environment.json"
            branch_path = Path(tmp) / "branches.json"
            env_path.write_text(json.dumps({"message": "Not Found"}), encoding="utf-8")
            branch_path.write_text("{}", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "aws" / "preflight_w3_lab_teardown.py"),
                    "--environment",
                    str(env_path),
                    "--branch-policies",
                    str(branch_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("PREFLIGHT FAIL", completed.stdout)


if __name__ == "__main__":
    unittest.main()
