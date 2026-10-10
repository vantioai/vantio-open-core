#!/usr/bin/env python3
"""The phantom-box trigger plans gh commands and does not call AWS."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lab_oidc_trigger as trigger  # noqa: E402


class TriggerTests(unittest.TestCase):
    def test_plan_does_not_call_gh_and_strips_aws_env(self) -> None:
        calls: list[list[str]] = []

        def gh(argv: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
            calls.append(argv)
            self.assertNotIn("AWS_PROFILE", env)
            self.assertNotIn("AWS_SECRET_ACCESS_KEY", env)
            return subprocess.CompletedProcess(argv, 0, "", "")

        environ = {
            "PATH": "/usr/bin",
            "AWS_PROFILE": "lab960577828987",
            "AWS_SECRET_ACCESS_KEY": "not-a-real-secret",
        }
        status = trigger.main(
            ["plan", "launch", "--field", "instance_type=t3.micro"],
            environ=environ,
            gh_runner=gh,
        )
        self.assertEqual(status, 0)
        self.assertEqual(calls, [])

    def test_launch_execute_without_slot_ack_does_not_dispatch(self) -> None:
        calls: list[list[str]] = []

        def gh(argv: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
            calls.append(list(argv))
            return subprocess.CompletedProcess(argv, 0, "", "")

        status = trigger.main(
            ["dispatch", "launch", "--execute", "--field", "instance_type=t3.micro"],
            environ={"PATH": "/usr/bin"},
            gh_runner=gh,
        )
        self.assertEqual(status, 2)
        self.assertEqual(calls, [])

    def test_launch_dispatch_is_gh_only(self) -> None:
        seen: dict[str, object] = {}

        def gh(argv: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
            seen["argv"] = list(argv)
            seen["env"] = dict(env)
            return subprocess.CompletedProcess(argv, 0, "", "")

        status = trigger.main(
            ["dispatch", "launch", "--execute", "--confirm-slot-clear", "--field", "instance_type=t3.micro"],
            environ={"PATH": "/usr/bin", "AWS_ACCESS_KEY_ID": "AKIAEXAMPLE"},
            gh_runner=gh,
        )
        self.assertEqual(status, 0)
        argv = seen["argv"]
        self.assertIsInstance(argv, list)
        assert isinstance(argv, list)
        self.assertEqual(argv[0], "gh")
        self.assertIn("w3-lab-auto-provision.yml", argv)
        self.assertNotIn("aws", argv)
        env = seen["env"]
        assert isinstance(env, dict)
        self.assertNotIn("AWS_ACCESS_KEY_ID", env)

    def test_long_soak_true_still_needs_the_slot_ack(self) -> None:
        calls: list[list[str]] = []

        def gh(argv: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
            calls.append(list(argv))
            return subprocess.CompletedProcess(argv, 0, "", "")

        status = trigger.main(
            ["dispatch", "long-soak", "--execute", "--field", "execute=true"],
            environ={"PATH": "/usr/bin"},
            gh_runner=gh,
        )
        self.assertEqual(status, 2)
        self.assertEqual(calls, [])

    def test_newline_field_is_refused(self) -> None:
        with self.assertRaises(trigger.TriggerError):
            trigger.parse_fields(["instance_id=i-0123456789abcdef0\n--extra"])

    def test_enterprise_rows_dispatch_does_not_launch(self) -> None:
        seen: dict[str, object] = {}

        def gh(argv: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
            seen["argv"] = list(argv)
            return subprocess.CompletedProcess(argv, 0, "", "")

        status = trigger.main(
            [
                "dispatch",
                "arm",
                "--execute",
                "--field",
                "instance_id=i-0123456789abcdef0",
                "--field",
                "enterprise_rows=true",
            ],
            environ={"PATH": "/usr/bin", "AWS_ACCESS_KEY_ID": "AKIAEXAMPLE"},
            gh_runner=gh,
        )
        self.assertEqual(status, 0)
        argv = seen["argv"]
        assert isinstance(argv, list)
        self.assertIn("w3-lab-auto-arm.yml", argv)
        self.assertIn("enterprise_rows=true", argv)
        self.assertNotIn("w3-lab-auto-provision.yml", argv)
        self.assertNotIn("aws", argv)

    def test_self_service_battery_is_legal_without_enterprise_rows(self) -> None:
        seen: dict[str, object] = {}

        def gh(argv: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
            seen["argv"] = list(argv)
            return subprocess.CompletedProcess(argv, 0, "", "")

        status = trigger.main(
            [
                "dispatch",
                "arm",
                "--execute",
                "--field",
                "instance_id=i-0123456789abcdef0",
                "--field",
                "battery=self-service",
                "--field",
                "enterprise_rows=false",
                "--field",
                "redteam_brain=false",
            ],
            environ={"PATH": "/usr/bin"},
            gh_runner=gh,
        )
        self.assertEqual(status, 0)
        argv = seen["argv"]
        assert isinstance(argv, list)
        self.assertIn("battery=self-service", argv)
        with self.assertRaises(trigger.TriggerError):
            trigger.validate_fields("arm", {"battery": "self-service", "enterprise_rows": "true"})

    def test_describe_only_does_not_need_the_slot_ack(self) -> None:
        seen: dict[str, object] = {}

        def gh(argv: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
            seen["argv"] = list(argv)
            return subprocess.CompletedProcess(argv, 0, "", "")

        status = trigger.main(
            [
                "dispatch",
                "launch",
                "--execute",
                "--field",
                "describe_only=true",
                "--field",
                "image_id=ami-0fa99aa8f97f9e30b",
            ],
            environ={"PATH": "/usr/bin"},
            gh_runner=gh,
        )
        self.assertEqual(status, 0)
        argv = seen["argv"]
        assert isinstance(argv, list)
        self.assertIn("describe_only=true", argv)
        self.assertIn("image_id=ami-0fa99aa8f97f9e30b", argv)
        self.assertNotIn("run-instances", argv)

    def test_bundle_tag_outside_the_lab_prefix_is_refused(self) -> None:
        with self.assertRaises(trigger.TriggerError):
            trigger.validate_fields("arm", {"bundle_tag": "v1.2.3"})

    def test_brain_launch_requires_the_120_minute_cap(self) -> None:
        trigger.validate_fields(
            "launch",
            {"instance_type": "m7i-flex.large", "stop_after_minutes": "120", "close_egress": "true"},
        )
        with self.assertRaises(trigger.TriggerError):
            trigger.validate_fields("launch", {"instance_type": "m7i-flex.large", "stop_after_minutes": "121"})
        with self.assertRaises(trigger.TriggerError):
            trigger.validate_fields("launch", {"instance_type": "m7i-flex.large"})
        with self.assertRaises(trigger.TriggerError):
            trigger.validate_fields("long-soak", {"instance_type": "m7i-flex.large"})
        trigger.validate_fields("arm", {"redteam_brain": "true", "enterprise_rows": "true"})

    def test_watch_plan_is_not_a_dispatch(self) -> None:
        status = trigger.main(["watch", "--run-id", "123"], environ={"PATH": "/usr/bin"}, gh_runner=None)
        self.assertEqual(status, 0)


if __name__ == "__main__":
    unittest.main()
