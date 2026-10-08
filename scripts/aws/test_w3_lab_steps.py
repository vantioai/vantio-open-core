#!/usr/bin/env python3
"""Fake-runner tests for lab steps. These tests do not call AWS."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "aws"))

import w3_lab_auto as lab  # noqa: E402
import w3_lab_steps as steps  # noqa: E402

NOW = datetime(2026, 9, 30, 16, 0, tzinfo=timezone.utc)
SEAL = "f882dd81297b02c11c55d9df69f00d9fffa710d1a87d36066a5645922804d753"
PIN = "e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e"
INSTANCE = "i-0123456789abcdef0"
SECRET = "SUPER-SECRET-PRIVATE"


def completed(payload: dict | None = None, *, code: int = 0, stderr: str = "", stdout: str = "") -> subprocess.CompletedProcess[str]:
    body = stdout if payload is None else json.dumps(payload)
    return subprocess.CompletedProcess(args=[], returncode=code, stdout=body, stderr=stderr)


def owned_tags() -> list[dict[str, str]]:
    tags = [{"Key": key, "Value": value} for key, value in lab.EXACT_TAGS.items()]
    tags.append({"Key": "Name", "Value": "vantio-w3-lab-auto-test"})
    tags.append({"Key": "vantio:expires-at", "Value": "2026-10-02T00:00:00Z"})
    return tags


def instance(state: str = "running") -> dict:
    return {
        "InstanceId": INSTANCE,
        "Placement": {"AvailabilityZone": "us-east-2a"},
        "PublicIpAddress": "1.1.1.1",
        "SecurityGroups": [{"GroupId": "sg-0123456789abcdef0"}],
        "State": {"Name": state},
        "Tags": owned_tags(),
    }


class FakeAws:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.state = "running"
        self.dry_run = "denied"

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(args))
        text = " ".join(args)
        if "--dry-run" in args:
            if self.dry_run == "allowed":
                return completed(code=254, stderr="An error occurred (DryRunOperation) when calling the operation")
            return completed(code=254, stderr="An error occurred (UnauthorizedOperation) when calling the operation")
        if "get-caller-identity" in text:
            return completed({"Account": lab.ACCOUNT_ID, "Arn": "arn:aws:sts::960577828987:assumed-role/vantio-w3-lab-provision/s"})
        if "describe-images" in text:
            return completed(
                {
                    "Images": [
                        {
                            "Architecture": "x86_64",
                            "CreationDate": "2026-09-01T00:00:00.000Z",
                            "ImageId": "ami-0123456789abcdef0",
                            "Name": "ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-20260901",
                            "OwnerId": lab.CANONICAL_OWNER,
                            "ProductCodes": [],
                            "Public": True,
                            "RootDeviceType": "ebs",
                        }
                    ]
                }
            )
        if "create-security-group" in text:
            return completed({"GroupId": "sg-0123456789abcdef0"})
        if "describe-instances" in text and "--instance-ids" in args:
            if self.state == "absent":
                return completed(code=254, stderr="InvalidInstanceID.NotFound")
            return completed({"Reservations": [{"Instances": [instance(self.state)]}]})
        if "describe-instances" in text:
            if self.state in lab.OCCUPYING_STATES:
                return completed({"Reservations": [{"Instances": [instance(self.state)]}]})
            return completed({"Reservations": []})
        if "describe-volumes" in text or "describe-security-groups" in text or "describe-key-pairs" in text:
            return completed({"Volumes": [], "SecurityGroups": [], "KeyPairs": []})
        if "get-console-output" in text:
            raw = base64.b64encode(b"boot\nvantio-lab-marker seal=" + SEAL.encode() + b" pin=" + PIN.encode() + b"\n").decode()
            return completed({"Output": raw})
        if "terminate-instances" in text:
            self.state = "terminated"
            return completed({})
        if text.startswith("aws ec2 wait"):
            return completed(stdout="")
        if "authorize-security-group-ingress" in text or "revoke-security-group-ingress" in text:
            return completed({})
        if "send-ssh-public-key" in text:
            return completed({})
        if "run-instances" in text:
            return completed(code=1, stderr="boom")
        return completed({})


class CapabilityTests(unittest.TestCase):
    def test_shipped_switch_is_off(self) -> None:
        caps = lab.load_lab_capabilities()
        self.assertFalse(caps["max_life_hours_36"])
        self.assertFalse(caps["ssh_instance_connect"])
        self.assertFalse(caps["ssm"])

    def test_arm_preflight_does_not_call_aws(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "w3-lab-arm.json"
            env = os.environ.copy()
            env["EVIDENCE_PATH"] = str(path)
            old = os.environ.get("EVIDENCE_PATH")
            os.environ["EVIDENCE_PATH"] = str(path)
            try:
                status = steps.preflight_arm()
            finally:
                if old is None:
                    os.environ.pop("EVIDENCE_PATH", None)
                else:
                    os.environ["EVIDENCE_PATH"] = old
            self.assertEqual(status, 2)
            body = json.loads(path.read_text())
            self.assertEqual(body["status"], "BLOCKED_IAM")
            self.assertFalse(body["mutated"])

    def test_long_soak_preflight_stops_before_aws(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "w3-lab-long-soak.json"
            os.environ["EVIDENCE_PATH"] = str(path)
            os.environ["SOAK_HOURS"] = "36"
            os.environ["EXECUTE"] = "true"
            try:
                status = steps.preflight_long_soak()
            finally:
                os.environ.pop("EVIDENCE_PATH", None)
                os.environ.pop("SOAK_HOURS", None)
                os.environ.pop("EXECUTE", None)
            self.assertEqual(status, 2)
            self.assertEqual(json.loads(path.read_text())["reason"], "max_life_hours_36_not_enabled")


class GuardTests(unittest.TestCase):
    def test_world_cidr_is_refused(self) -> None:
        with self.assertRaises(lab.GuardAbort):
            steps.require_global_32("0.0.0.0/0")

    def test_private_cidr_is_refused(self) -> None:
        with self.assertRaises(lab.GuardAbort):
            steps.require_global_32("10.1.2.3/32")

    def test_one_public_address_is_accepted(self) -> None:
        self.assertEqual(steps.require_global_32("1.1.1.1/32"), "1.1.1.1/32")

    def test_founder_session_tags_are_not_owned(self) -> None:
        tags = {
            "Name": "vantio-3a-soak-20261007T013900Z",
            "vantio:program": "w3-clean-host-lab",
            "vantio:purpose": "pe-3a-soak",
            "vantio:lifecycle": "lab",
            "vantio:destroyable": "true",
            "vantio:environment": "lab",
            "vantio:owner-role": "founder-console-session",
            "vantio:expires-at": "2026-10-08T13:39:00Z",
            "vantio:max-life-hours": "36",
            "vantio:shutdown-behavior": "terminate",
        }
        resource = {"type": "instance", "id": "i-07a9f1cfdcf43b592", "region": "us-east-2", "launch_time": "2026-10-07T01:39:06Z", "tags": tags}
        self.assertEqual(lab.sweeper_action(resource, NOW), "skip_not_owned")

    def test_thirty_six_hour_host_survives_the_seven_hour_mark(self) -> None:
        tags = dict(lab.EXACT_TAGS)
        tags["Name"] = "vantio-w3-lab-auto-long"
        tags["vantio:expires-at"] = "2026-10-02T00:00:00Z"
        tags["vantio:max-life-hours"] = "36"
        young = {
            "type": "instance",
            "id": INSTANCE,
            "region": "us-east-2",
            "launch_time": (NOW - timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tags": tags,
        }
        old = dict(young)
        old["launch_time"] = (NOW - timedelta(hours=36)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertEqual(lab.sweeper_action(young, NOW), "skip_life_not_enabled")
        self.assertEqual(lab.sweeper_action(old, NOW), "skip_life_not_enabled")
        with tempfile.TemporaryDirectory() as tmp:
            cap = Path(tmp) / "caps.json"
            cap.write_text(json.dumps({"max_life_hours_36": True, "ssh_instance_connect": False, "ssm": False}))
            os.environ["W3_LAB_CAPABILITIES"] = str(cap)
            try:
                self.assertEqual(lab.sweeper_action(young, NOW), "keep")
                self.assertEqual(lab.sweeper_action(old, NOW), "delete_launch_age")
            finally:
                os.environ.pop("W3_LAB_CAPABILITIES", None)

    def test_occupied_slot_does_not_call_run_instances(self) -> None:
        runner = FakeAws()
        with tempfile.TemporaryDirectory() as tmp:
            gate = Path(tmp) / "gate.json"
            gate.write_text(json.dumps(lab._passing_gate(NOW)))
            evidence = Path(tmp) / "launch.json"
            os.environ["COST_GATE_FILE"] = str(gate)
            os.environ["EVIDENCE_PATH"] = str(evidence)
            os.environ["GITHUB_RUN_ID"] = "slottest"
            try:
                with self.assertRaises(lab.GuardAbort) as caught:
                    lab.launch_from_env(runner, NOW)
            finally:
                os.environ.pop("COST_GATE_FILE", None)
                os.environ.pop("EVIDENCE_PATH", None)
                os.environ.pop("GITHUB_RUN_ID", None)
            self.assertEqual(caught.exception.reason, "slot_occupied")
            self.assertFalse(any("run-instances" in " ".join(call) for call in runner.calls))
            body = evidence.read_text()
            self.assertNotIn(SECRET, body)

    def test_failed_launch_deletes_the_new_security_group(self) -> None:
        runner = FakeAws()
        runner.state = "terminated"
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(lab.GuardAbort):
                lab.execute_launch(
                    {
                        "instance_type": "t3.micro",
                        "stop_after_minutes": 15,
                        "name": "vantio-w3-lab-auto-test",
                        "associate_public_ipv4": "false",
                    },
                    lab._passing_gate(NOW),
                    {"Account": lab.ACCOUNT_ID},
                    runner,
                    NOW,
                    user_data_path=Path(tmp) / "user-data.sh",
                )
        commands = [" ".join(call) for call in runner.calls]
        self.assertTrue(any("run-instances" in item for item in commands))
        self.assertTrue(any("delete-security-group" in item for item in commands))


class ArmCollectTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)

    def enable_ssh(self, tmp: str) -> None:
        path = Path(tmp) / "caps.json"
        path.write_text(json.dumps({"ssh_instance_connect": True, "max_life_hours_36": False, "ssm": False}))
        os.environ["W3_LAB_CAPABILITIES"] = str(path)

    def test_arm_stops_when_the_switch_is_off(self) -> None:
        runner = FakeAws()
        os.environ["INSTANCE_ID"] = INSTANCE
        with self.assertRaises(lab.GuardAbort) as caught:
            steps.execute_arm(runner)
        self.assertEqual(caught.exception.reason, "ssh_instance_connect_not_enabled")
        self.assertEqual(runner.calls, [])

    def test_denied_dry_run_does_not_open_ssh(self) -> None:
        runner = FakeAws()
        with tempfile.TemporaryDirectory() as tmp:
            self.enable_ssh(tmp)
            os.environ["INSTANCE_ID"] = INSTANCE
            os.environ["SEAL"] = SEAL
            os.environ["PUBLIC_PIN"] = PIN
            os.environ["W3_RUNNER_CIDR"] = "1.1.1.1/32"
            os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "arm.json")
            os.environ["W3_STAMP"] = str(Path(tmp) / "stamp.json")
            with self.assertRaises(lab.GuardAbort):
                steps.execute_arm(runner)
            body = Path(os.environ["EVIDENCE_PATH"]).read_text()
        self.assertIn("BLOCKED_IAM", body)
        self.assertNotIn(SECRET, body)
        self.assertFalse(any("authorize-security-group-ingress" in " ".join(call) and "--dry-run" not in call for call in runner.calls))

    def test_arm_shreds_the_key_and_keeps_it_out_of_evidence(self) -> None:
        runner = FakeAws()
        runner.dry_run = "allowed"

        def keygen(directory: Path) -> tuple[Path, str]:
            private = directory / "lab-ed25519"
            private.write_text(SECRET + "\n", encoding="utf-8")
            return private, "ssh-ed25519 AAAATEST vantio-lab"

        def ssh(args: list[str], script: str) -> subprocess.CompletedProcess[str]:
            self.assertNotIn(SECRET, " ".join(args))
            self.assertIn(SEAL, args)
            self.assertIn("vantio-lab-marker", script)
            return completed(stdout="ok")

        with tempfile.TemporaryDirectory() as tmp:
            self.enable_ssh(tmp)
            os.environ["INSTANCE_ID"] = INSTANCE
            os.environ["SEAL"] = SEAL
            os.environ["PUBLIC_PIN"] = PIN
            os.environ["W3_RUNNER_CIDR"] = "1.1.1.1/32"
            os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "arm.json")
            os.environ["W3_STAMP"] = str(Path(tmp) / "stamp.json")
            os.environ["W3_MARKER_SCRIPT"] = str(ROOT / "scripts/aws/lab-guests/marker.sh")
            result = steps.execute_arm(runner, keygen=keygen, ssh_runner=ssh)
            body = Path(os.environ["EVIDENCE_PATH"]).read_text()
            self.assertFalse((Path(tmp) / "lab-ed25519").exists())
        self.assertEqual(result["status"], "ARMED")
        self.assertNotIn(SECRET, body)
        self.assertNotIn("BEGIN OPENSSH PRIVATE KEY", body)
        joined = [" ".join(call) for call in runner.calls]
        self.assertTrue(any("authorize-security-group-ingress" in item and "--dry-run" not in item for item in joined))
        self.assertTrue(any("revoke-security-group-ingress" in item and "--dry-run" not in item for item in joined))

    def test_collect_keeps_the_console_body_out_of_the_artifact(self) -> None:
        runner = FakeAws()
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["INSTANCE_ID"] = INSTANCE
            os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "collect.json")
            result = steps.execute_collect(runner)
            body = Path(os.environ["EVIDENCE_PATH"]).read_text()
        self.assertTrue(result["marker_found"])
        self.assertEqual(result["collect_channel"], "console")
        self.assertNotIn("boot", body)
        self.assertNotIn(SECRET, body)

    def test_teardown_leaves_an_unowned_host(self) -> None:
        runner = FakeAws()

        def foreign(args: list[str]) -> subprocess.CompletedProcess[str]:
            runner.calls.append(list(args))
            if "get-caller-identity" in " ".join(args):
                return completed({"Account": lab.ACCOUNT_ID})
            if "--instance-ids" in args:
                foreign_instance = instance()
                foreign_instance["Tags"] = [{"Key": "Name", "Value": "vantio-3a-soak-20261007T013900Z"}]
                return completed({"Reservations": [{"Instances": [foreign_instance]}]})
            return completed({"Reservations": [], "Volumes": [], "SecurityGroups": [], "KeyPairs": []})

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["INSTANCE_ID"] = "i-07a9f1cfdcf43b592"
            os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "teardown.json")
            with self.assertRaises(lab.GuardAbort) as caught:
                steps.execute_teardown(foreign, NOW)
        self.assertEqual(caught.exception.reason, "not_owned")
        self.assertFalse(any("terminate-instances" in " ".join(call) for call in runner.calls))

    def test_verify_removed_when_the_owned_host_is_terminated(self) -> None:
        runner = FakeAws()
        runner.state = "terminated"
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["INSTANCE_ID"] = INSTANCE
            os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "verify.json")
            result = steps.execute_verify(runner, NOW)
            digest = (Path(tmp) / "verify.json.sha256").read_text().split()[0]
            body = (Path(tmp) / "verify.json").read_bytes()
        self.assertEqual(result["status"], "VERIFIED_REMOVED")
        self.assertEqual(digest, hashlib.sha256(body).hexdigest())
        self.assertFalse(any("terminate-instances" in " ".join(call) for call in runner.calls))


class WorkflowTextTests(unittest.TestCase):
    def test_new_workflows_stay_dispatch_only_and_exact_address(self) -> None:
        names = [
            "w3-lab-auto-arm.yml",
            "w3-lab-auto-collect.yml",
            "w3-lab-auto-teardown.yml",
            "w3-lab-auto-verify-removed.yml",
            "w3-lab-auto-long-soak.yml",
            "w3-lab-auto-provision.yml",
            "w3-lab-auto-sweeper.yml",
        ]
        for name in names:
            text = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            self.assertNotIn("pull_request:", text, name)
            self.assertNotIn("0.0.0.0/0", text, name)
            self.assertIn("group: w3-lab-free-ec2", text, name)
            self.assertNotRegex(text, r"(?m)^\s*AWS_ACCESS_KEY_ID:", name)
        arm = (ROOT / ".github/workflows/w3-lab-auto-arm.yml").read_text(encoding="utf-8")
        self.assertIn("close-ssh", arm)
        self.assertIn("if: always()", arm)
        soak = (ROOT / ".github/workflows/w3-lab-auto-long-soak.yml").read_text(encoding="utf-8")
        self.assertIn("default: false", soak)
        self.assertIn("w3-lab-auto-cost-gate.yml@main # oidc-trust", soak)


if __name__ == "__main__":
    unittest.main()
