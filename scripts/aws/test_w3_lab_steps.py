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

import enterprise_bundle  # noqa: E402
import w3_lab_auto as lab  # noqa: E402
import w3_lab_steps as steps  # noqa: E402

NOW = datetime(2026, 9, 30, 16, 0, tzinfo=timezone.utc)
SEAL = enterprise_bundle.POLICY_ALLOW_SEAL
PIN = enterprise_bundle.PUBLIC_INSTALLER_PIN
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
        "ImageId": lab.PINNED_IMAGE_ID,
        "State": {"Name": state},
        "Tags": owned_tags(),
    }


_MODULE_CWD: str | None = None
_MODULE_TMP: tempfile.TemporaryDirectory | None = None


def setUpModule() -> None:
    """Run from a temp dir so default-path evidence (w3-lab-arm.json,
    w3-lab-redteam-rows.json and their .sha256) never lands in the repo."""
    global _MODULE_CWD, _MODULE_TMP
    _MODULE_CWD = os.getcwd()
    _MODULE_TMP = tempfile.TemporaryDirectory()
    os.chdir(_MODULE_TMP.name)


def tearDownModule() -> None:
    if _MODULE_CWD is not None:
        os.chdir(_MODULE_CWD)
    if _MODULE_TMP is not None:
        _MODULE_TMP.cleanup()


class FakeAws:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.state = "running"
        self.dry_run = "denied"
        self.egress_revoke = "allowed"
        self.console = b"boot\nvantio-lab-marker seal=" + SEAL.encode() + b" pin=" + PIN.encode() + b"\n"

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(args))
        text = " ".join(args)
        if "--dry-run" in args:
            if "revoke-security-group-egress" in text and self.egress_revoke == "allowed":
                return completed(code=254, stderr="An error occurred (DryRunOperation) when calling the operation")
            if self.dry_run == "allowed":
                return completed(code=254, stderr="An error occurred (DryRunOperation) when calling the operation")
            return completed(code=254, stderr="An error occurred (UnauthorizedOperation) when calling the operation")
        if "describe-security-groups" in text and "--group-ids" in args:
            group_id = args[args.index("--group-ids") + 1]
            return completed({"SecurityGroups": [{"GroupId": group_id, "IpPermissionsEgress": []}]})
        if "get-caller-identity" in text:
            return completed({"Account": lab.ACCOUNT_ID, "Arn": "arn:aws:sts::960577828987:assumed-role/vantio-w3-lab-provision/s"})
        if "describe-images" in text:
            image_id = "ami-0123456789abcdef0"
            if "--image-ids" in args:
                image_id = args[args.index("--image-ids") + 1]
            return completed(
                {
                    "Images": [
                        {
                            "Architecture": "x86_64",
                            "CreationDate": "2026-09-01T00:00:00.000Z",
                            "ImageId": image_id,
                            "State": "available",
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
            raw = base64.b64encode(self.console).decode()
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
    def test_enablement_switches_match_the_checklist(self) -> None:
        caps = lab.load_lab_capabilities()
        self.assertTrue(caps["max_life_hours_36"])
        self.assertTrue(caps["ssh_instance_connect"])
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
            self.assertEqual(status, 0)
            body = json.loads(path.read_text())
            self.assertEqual(body["status"], "READY")
            self.assertTrue(body["proceed"])
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
            self.assertEqual(status, 0)
            body = json.loads(path.read_text())
            self.assertTrue(body["proceed"])
            self.assertEqual(body["status"], "READY")


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
        self.assertEqual(lab.sweeper_action(young, NOW), "keep")
        self.assertEqual(lab.sweeper_action(old, NOW), "delete_launch_age")
        soaked = dict(old)
        soaked["tags"] = dict(tags)
        soaked["tags"]["vantio-soak"] = "active"
        self.assertEqual(lab.sweeper_action(soaked, NOW), "keep_soak")
        group = {
            "type": "security-group",
            "id": "sg-0123456789abcdef0",
            "region": "us-east-2",
            "tags": soaked["tags"],
        }
        self.assertEqual(lab.sweeper_action(group, NOW), "keep_soak")
        self.assertNotIn("keep_soak", lab.DELETE_ACTIONS)
        with tempfile.TemporaryDirectory() as tmp:
            cap = Path(tmp) / "caps.json"
            cap.write_text(json.dumps({"max_life_hours_36": False, "ssh_instance_connect": False, "ssm": False}))
            os.environ["W3_LAB_CAPABILITIES"] = str(cap)
            try:
                self.assertEqual(lab.sweeper_action(young, NOW), "skip_life_not_enabled")
                self.assertEqual(lab.sweeper_action(old, NOW), "skip_life_not_enabled")
                self.assertEqual(lab.sweeper_action(soaked, NOW), "keep_soak")
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
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "caps.json"
            path.write_text(json.dumps({"ssh_instance_connect": False, "max_life_hours_36": False, "ssm": False}))
            os.environ["W3_LAB_CAPABILITIES"] = str(path)
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

    def test_collect_uploads_the_redacted_console(self) -> None:
        runner = FakeAws()
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["INSTANCE_ID"] = INSTANCE
            os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "collect.json")
            os.environ.pop("W3_CONSOLE_PATH", None)
            result = steps.execute_collect(runner)
            body = Path(os.environ["EVIDENCE_PATH"]).read_text()
            console_path = Path(tmp) / f"w3-lab-console-{INSTANCE}.txt"
            console = console_path.read_text(encoding="utf-8")
        self.assertTrue(result["marker_found"])
        self.assertEqual(result["collect_channel"], "console")
        self.assertIn("boot", console)
        self.assertIn("vantio-lab-marker", console)
        self.assertEqual(result["console_sha256"], hashlib.sha256(console.encode("utf-8")).hexdigest())
        self.assertEqual(result["console_file"], console_path.name)
        self.assertNotIn("boot", body)
        self.assertNotIn(SECRET, body)
        self.assertNotIn(SECRET, console)

    def test_collect_redacts_a_private_key_before_it_writes_the_console(self) -> None:
        secret = "-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n-----END OPENSSH PRIVATE KEY-----"
        raw = base64.b64encode(f"boot\n{secret}\n".encode()).decode()

        def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
            text = " ".join(args)
            if "get-caller-identity" in text:
                return completed({"Account": lab.ACCOUNT_ID})
            if "--instance-ids" in args:
                return completed({"Reservations": [{"Instances": [instance()]}]})
            if "get-console-output" in text:
                return completed({"Output": raw})
            return completed({})

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["INSTANCE_ID"] = INSTANCE
            os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "collect.json")
            os.environ.pop("W3_CONSOLE_PATH", None)
            result = steps.execute_collect(runner)
            console = (Path(tmp) / f"w3-lab-console-{INSTANCE}.txt").read_text(encoding="utf-8")
        self.assertNotIn("BEGIN OPENSSH", console)
        self.assertNotIn("abc", console)
        self.assertNotIn("PRIVATE KEY", console)
        self.assertIn("[redacted]", console)
        self.assertTrue(result["console_redacted"])
        self.assertEqual(result["console_sha256"], hashlib.sha256(console.encode("utf-8")).hexdigest())

    def test_a_cut_off_private_key_is_not_written(self) -> None:
        head, _changed = steps.redact("boot\n-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n")
        tail, _changed_tail = steps.redact("abc\n-----END OPENSSH PRIVATE KEY-----\nboot\n")
        self.assertNotIn("PRIVATE KEY", head)
        self.assertNotIn("abc", head)
        self.assertNotIn("PRIVATE KEY", tail)
        self.assertNotIn("abc", tail)
        raw = base64.b64encode(b"still PRIVATE KEY in the tail\n").decode()

        def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
            text = " ".join(args)
            if "get-caller-identity" in text:
                return completed({"Account": lab.ACCOUNT_ID})
            if "--instance-ids" in args:
                return completed({"Reservations": [{"Instances": [instance()]}]})
            if "get-console-output" in text:
                return completed({"Output": raw})
            return completed({})

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["INSTANCE_ID"] = INSTANCE
            os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "collect.json")
            os.environ.pop("W3_CONSOLE_PATH", None)
            with self.assertRaises(lab.GuardAbort) as caught:
                steps.execute_collect(runner)
            written = list(Path(tmp).glob("w3-lab-console-*.txt"))
        self.assertEqual(caught.exception.reason, "token_in_evidence")
        self.assertEqual(written, [])

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

    def test_teardown_refuses_an_active_soak_host(self) -> None:
        calls: list[list[str]] = []

        def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(list(args))
            text = " ".join(args)
            if "get-caller-identity" in text:
                return completed({"Account": lab.ACCOUNT_ID})
            if "--instance-ids" in args:
                body = instance()
                body["Tags"].append({"Key": "vantio-soak", "Value": "active"})
                return completed({"Reservations": [{"Instances": [body]}]})
            return completed({"Reservations": [], "Volumes": [], "SecurityGroups": [], "KeyPairs": []})

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["INSTANCE_ID"] = INSTANCE
            os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "teardown.json")
            with self.assertRaises(lab.GuardAbort) as caught:
                steps.execute_teardown(runner, NOW)
            body = json.loads(Path(os.environ["EVIDENCE_PATH"]).read_text())
        self.assertEqual(caught.exception.reason, "soak_active")
        self.assertEqual(body["status"], "REFUSED_SOAK")
        self.assertFalse(body["mutated"])
        self.assertFalse(any("terminate-instances" in " ".join(call) for call in calls))
        self.assertFalse(any("modify-instance-attribute" in " ".join(call) for call in calls))

    def test_founder_close_record_names_this_soak_only(self) -> None:
        record = json.loads(steps.FOUNDER_CLOSE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "CLOSED_BY_FOUNDER")
        self.assertEqual(record["closed_by"], "Zachary Balicki (Founder)")
        self.assertEqual(record["instance_id"], "i-0f38ffde5ad83c9f2")
        self.assertEqual(record["decision_time"], "2026-10-15T21:10:00-04:00")
        self.assertEqual(record["decision_time_spoken"], "2026-10-15 ~9:10 PM ET")
        self.assertEqual(record["note"], "26.9h was accepted")
        self.assertEqual(record["evidence_ref"], "SOAK-HASH-COMPARE.json")
        self.assertTrue(steps.founder_close_honored("i-0f38ffde5ad83c9f2", record))
        self.assertFalse(steps.founder_close_honored(INSTANCE, record))
        renamed = dict(record)
        renamed["instance_id"] = INSTANCE
        self.assertFalse(steps.founder_close_honored(INSTANCE, renamed))
        self.assertFalse(steps.founder_close_honored("i-0f38ffde5ad83c9f2", renamed))
        for key in ("closed_by", "note", "decision_time", "decision_time_spoken", "evidence_ref", "status"):
            changed = dict(record)
            changed[key] = "changed"
            self.assertFalse(steps.founder_close_honored("i-0f38ffde5ad83c9f2", changed), key)

    def test_founder_close_tears_down_only_the_recorded_soak(self) -> None:
        soak_id = "i-0f38ffde5ad83c9f2"
        state = {"name": "running"}
        calls: list[list[str]] = []

        def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(list(args))
            text = " ".join(args)
            if "get-caller-identity" in text:
                return completed({"Account": lab.ACCOUNT_ID})
            if "describe-instances" in text and "--instance-ids" in args:
                body = instance(state["name"])
                body["InstanceId"] = soak_id
                body["Tags"].append({"Key": "vantio-soak", "Value": "active"})
                return completed({"Reservations": [{"Instances": [body]}]})
            if "describe-instances" in text:
                if state["name"] in lab.OCCUPYING_STATES:
                    body = instance(state["name"])
                    body["InstanceId"] = soak_id
                    body["Tags"].append({"Key": "vantio-soak", "Value": "active"})
                    return completed({"Reservations": [{"Instances": [body]}]})
                return completed({"Reservations": []})
            if "modify-instance-attribute" in text:
                return completed({})
            if "terminate-instances" in text:
                state["name"] = "terminated"
                return completed({})
            if text.startswith("aws ec2 wait"):
                return completed(stdout="")
            return completed({"Volumes": [], "SecurityGroups": [], "KeyPairs": [], "Reservations": []})

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["INSTANCE_ID"] = soak_id
            os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "teardown.json")
            result = steps.execute_teardown(runner, NOW)
        self.assertEqual(result["status"], "VERIFIED_REMOVED")
        self.assertEqual(result["founder_close"]["status"], "CLOSED_BY_FOUNDER")
        self.assertEqual(result["founder_close"]["closed_by"], "Zachary Balicki (Founder)")
        self.assertEqual(result["founder_close"]["note"], "26.9h was accepted")
        self.assertEqual(result["founder_close"]["evidence_ref"], "SOAK-HASH-COMPARE.json")
        self.assertTrue(result["slot_clear"])
        joined = [" ".join(call) for call in calls]
        self.assertFalse(any("modify-instance-attribute" in item for item in joined))
        terminate_at = next(i for i, item in enumerate(joined) if "terminate-instances" in item)
        self.assertIn(soak_id, joined[terminate_at])

    def test_founder_close_refuses_a_changed_record(self) -> None:
        soak_id = "i-0f38ffde5ad83c9f2"
        calls: list[list[str]] = []

        def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(list(args))
            text = " ".join(args)
            if "get-caller-identity" in text:
                return completed({"Account": lab.ACCOUNT_ID})
            if "--instance-ids" in args:
                body = instance()
                body["InstanceId"] = soak_id
                body["Tags"].append({"Key": "vantio-soak", "Value": "active"})
                return completed({"Reservations": [{"Instances": [body]}]})
            return completed({"Reservations": [], "Volumes": [], "SecurityGroups": [], "KeyPairs": []})

        original = steps.FOUNDER_CLOSE_PATH
        with tempfile.TemporaryDirectory() as tmp:
            changed = json.loads(original.read_text(encoding="utf-8"))
            changed["closed_by"] = "someone else"
            path = Path(tmp) / "founder-soak-close.json"
            path.write_text(json.dumps(changed), encoding="utf-8")
            steps.FOUNDER_CLOSE_PATH = path
            os.environ["INSTANCE_ID"] = soak_id
            os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "teardown.json")
            try:
                with self.assertRaises(lab.GuardAbort) as caught:
                    steps.execute_teardown(runner, NOW)
                body = json.loads(Path(os.environ["EVIDENCE_PATH"]).read_text())
            finally:
                steps.FOUNDER_CLOSE_PATH = original
        self.assertEqual(caught.exception.reason, "soak_active")
        self.assertEqual(body["status"], "REFUSED_SOAK")
        self.assertFalse(any("terminate-instances" in " ".join(call) for call in calls))
        self.assertFalse(any("modify-instance-attribute" in " ".join(call) for call in calls))

    def test_founder_close_records_a_termination_lock(self) -> None:
        soak_id = "i-0f38ffde5ad83c9f2"
        calls: list[list[str]] = []

        def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(list(args))
            text = " ".join(args)
            if "get-caller-identity" in text:
                return completed({"Account": lab.ACCOUNT_ID})
            if "terminate-instances" in text:
                return completed(
                    code=254,
                    stderr=(
                        "An error occurred (OperationNotPermitted) when calling the TerminateInstances "
                        "operation: The instance may not be terminated. Modify its 'disableApiTermination' "
                        "instance attribute and try again."
                    ),
                )
            if "--instance-ids" in args:
                body = instance()
                body["InstanceId"] = soak_id
                body["Tags"].append({"Key": "vantio-soak", "Value": "active"})
                return completed({"Reservations": [{"Instances": [body]}]})
            return completed({"Reservations": [], "Volumes": [], "SecurityGroups": [], "KeyPairs": []})

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["INSTANCE_ID"] = soak_id
            os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "teardown.json")
            with self.assertRaises(lab.GuardAbort) as caught:
                steps.execute_teardown(runner, NOW)
            body = json.loads(Path(os.environ["EVIDENCE_PATH"]).read_text())
        self.assertTrue(steps.termination_protected(caught.exception.reason))
        self.assertFalse(steps.termination_protected("An error occurred (UnauthorizedOperation) when calling the ModifyInstanceAttribute operation"))
        self.assertEqual(body["status"], "TERMINATION_LOCK")
        self.assertEqual(body["called"], ["terminate-instances"])
        self.assertEqual(body["founder_close"]["status"], "CLOSED_BY_FOUNDER")
        self.assertFalse(body["mutated"])
        self.assertFalse(any("modify-instance-attribute" in " ".join(call) for call in calls))

    def test_absent_founder_instance_deletes_its_named_leftovers(self) -> None:
        soak_id = "i-0f38ffde5ad83c9f2"
        group_id = "sg-05de088ec47eca7c4"
        other_id = "sg-0abcabcabcabcabc0"
        groups = {"present": True}
        calls: list[list[str]] = []

        def group(group_id_value: str, name: str) -> dict:
            values = dict(lab.EXACT_TAGS)
            values["vantio:max-life-hours"] = "36"
            values["Name"] = name
            values["vantio:expires-at"] = "2026-10-15T00:00:00Z"
            values["vantio-soak"] = "active"
            tags = [{"Key": key, "Value": value} for key, value in values.items()]
            return {"GroupId": group_id_value, "Tags": tags}

        def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(list(args))
            text = " ".join(args)
            if "get-caller-identity" in text:
                return completed({"Account": lab.ACCOUNT_ID})
            if "describe-instances" in text and "--instance-ids" in args:
                return completed(code=254, stderr="InvalidInstanceID.NotFound")
            if "describe-instances" in text:
                return completed({"Reservations": []})
            if "describe-volumes" in text:
                return completed({"Volumes": []})
            if "describe-key-pairs" in text:
                return completed({"KeyPairs": []})
            if "describe-security-groups" in text:
                listed = []
                if groups["present"]:
                    listed.append(group(group_id, steps.FOUNDER_CLOSE_LAB_NAME))
                listed.append(group(other_id, "vantio-w3-lab-auto-other"))
                return completed({"SecurityGroups": listed})
            if "delete-security-group" in text:
                deleted = args[args.index("--group-id") + 1]
                if deleted == group_id:
                    groups["present"] = False
                    return completed({})
                return completed(code=254, stderr="An error occurred (UnauthorizedOperation)")
            if "modify-instance-attribute" in text or "terminate-instances" in text:
                return completed({})
            return completed({})

        decoy = "vantio-w3-lab-auto-decoy"
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["INSTANCE_ID"] = soak_id
            os.environ["LAB_NAME"] = decoy
            os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "teardown.json")
            result = steps.execute_teardown(runner, NOW)
            body = json.loads(Path(os.environ["EVIDENCE_PATH"]).read_text())
        self.assertEqual(os.environ.get("LAB_NAME"), decoy)
        self.assertEqual(result["status"], "VERIFIED_REMOVED")
        self.assertEqual(body["status"], "VERIFIED_REMOVED")
        self.assertEqual(result["name"], steps.FOUNDER_CLOSE_LAB_NAME)
        self.assertTrue(result["slot_clear"])
        self.assertTrue(result["mutated"])
        self.assertEqual(result["called"], ["delete-security-group"])
        self.assertEqual(result["founder_close"]["status"], "CLOSED_BY_FOUNDER")
        self.assertEqual(result["founder_close"]["instance_id"], soak_id)
        joined = [" ".join(call) for call in calls]
        self.assertFalse(any("modify-instance-attribute" in item for item in joined))
        self.assertFalse(any("terminate-instances" in item for item in joined))
        deletes = [item for item in joined if "delete-security-group" in item]
        self.assertEqual(len(deletes), 1)
        self.assertIn(group_id, deletes[0])
        self.assertNotIn(other_id, deletes[0])
        leftover = {
            "type": "security-group",
            "id": group_id,
            "region": lab.REGION,
            "tags": {
                **lab.EXACT_TAGS,
                "Name": steps.FOUNDER_CLOSE_LAB_NAME,
                "vantio:max-life-hours": "36",
                "vantio-soak": "active",
            },
        }
        self.assertEqual(lab.sweeper_action(leftover, NOW), "keep_soak")

    def test_absent_instance_without_the_founder_record_deletes_nothing(self) -> None:
        soak_id = "i-0f38ffde5ad83c9f2"
        calls: list[list[str]] = []

        def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(list(args))
            text = " ".join(args)
            if "get-caller-identity" in text:
                return completed({"Account": lab.ACCOUNT_ID})
            if "describe-instances" in text and "--instance-ids" in args:
                return completed(code=254, stderr="InvalidInstanceID.NotFound")
            if "describe-security-groups" in text:
                return completed(
                    {
                        "SecurityGroups": [
                            {
                                "GroupId": "sg-05de088ec47eca7c4",
                                "Tags": [{"Key": "Name", "Value": steps.FOUNDER_CLOSE_LAB_NAME}],
                            }
                        ]
                    }
                )
            return completed({"Reservations": [], "Volumes": [], "SecurityGroups": [], "KeyPairs": []})

        original = steps.FOUNDER_CLOSE_PATH
        with tempfile.TemporaryDirectory() as tmp:
            changed = json.loads(original.read_text(encoding="utf-8"))
            changed["note"] = "changed"
            path = Path(tmp) / "founder-soak-close.json"
            path.write_text(json.dumps(changed), encoding="utf-8")
            steps.FOUNDER_CLOSE_PATH = path
            os.environ["INSTANCE_ID"] = soak_id
            os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "teardown.json")
            try:
                with self.assertRaises(lab.GuardAbort) as caught:
                    steps.execute_teardown(runner, NOW)
                body = json.loads(Path(os.environ["EVIDENCE_PATH"]).read_text())
            finally:
                steps.FOUNDER_CLOSE_PATH = original
        self.assertEqual(caught.exception.reason, "instance_absent")
        self.assertEqual(body["status"], "NOT_FOUND")
        self.assertNotIn("called", body)
        self.assertFalse(any("delete-security-group" in " ".join(call) for call in calls))
        self.assertFalse(any("modify-instance-attribute" in " ".join(call) for call in calls))

        calls.clear()
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["INSTANCE_ID"] = INSTANCE
            os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "teardown.json")
            with self.assertRaises(lab.GuardAbort) as caught:
                steps.execute_teardown(runner, NOW)
            body = json.loads(Path(os.environ["EVIDENCE_PATH"]).read_text())
        self.assertEqual(caught.exception.reason, "instance_absent")
        self.assertEqual(body["status"], "NOT_FOUND")
        self.assertFalse(any("delete-security-group" in " ".join(call) for call in calls))

    def test_absent_founder_delete_stops_when_the_group_delete_is_denied(self) -> None:
        soak_id = "i-0f38ffde5ad83c9f2"
        calls: list[list[str]] = []

        def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(list(args))
            text = " ".join(args)
            if "get-caller-identity" in text:
                return completed({"Account": lab.ACCOUNT_ID})
            if "describe-instances" in text and "--instance-ids" in args:
                return completed(code=254, stderr="InvalidInstanceID.NotFound")
            if "describe-instances" in text:
                return completed({"Reservations": []})
            if "describe-volumes" in text:
                return completed({"Volumes": []})
            if "describe-key-pairs" in text:
                return completed({"KeyPairs": []})
            if "describe-security-groups" in text:
                tags = [{"Key": key, "Value": value} for key, value in lab.EXACT_TAGS.items()]
                tags.append({"Key": "Name", "Value": steps.FOUNDER_CLOSE_LAB_NAME})
                tags.append({"Key": "vantio-soak", "Value": "active"})
                return completed({"SecurityGroups": [{"GroupId": "sg-05de088ec47eca7c4", "Tags": tags}]})
            if "delete-security-group" in text:
                return completed(code=254, stderr="An error occurred (UnauthorizedOperation) when calling the DeleteSecurityGroup operation")
            return completed({})

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["INSTANCE_ID"] = soak_id
            os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "teardown.json")
            with self.assertRaises(lab.GuardAbort) as caught:
                steps.execute_teardown(runner, NOW)
            written = Path(os.environ["EVIDENCE_PATH"]).exists()
        self.assertEqual(caught.exception.reason, "delete_security_group")
        self.assertFalse(written)
        self.assertTrue(any("delete-security-group" in " ".join(call) for call in calls))
        self.assertFalse(any("modify-instance-attribute" in " ".join(call) for call in calls))

    def test_collect_does_not_call_cloudtrail_when_the_soak_host_is_gone(self) -> None:
        calls: list[list[str]] = []

        def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
            calls.append(list(args))
            text = " ".join(args)
            if "get-caller-identity" in text:
                return completed({"Account": lab.ACCOUNT_ID})
            if "describe-instances" in text:
                body = instance("terminated")
                body["LaunchTime"] = "2026-09-30T12:00:00Z"
                body["Tags"].append({"Key": "vantio-soak", "Value": "active"})
                return completed({"Reservations": [{"Instances": [body]}]})
            if "get-console-output" in text:
                raw = base64.b64encode(b"vantio-lab-check seq=3 name=soak result=pass sha256=" + b"c" * 64).decode()
                return completed({"Output": raw})
            return completed({})

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "collect.json")
            os.environ.pop("INSTANCE_ID", None)
            os.environ.pop("W3_RUNNER_CIDR", None)
            result = steps.execute_collect_due(runner, NOW)
        row = result["instances"][0]
        self.assertTrue(row["soak_active"])
        self.assertEqual(row["instance_state"], "terminated")
        self.assertEqual(row["cloudtrail"], {"recorded": False, "reason": "admin_soak_release"})
        self.assertEqual(row["check_count"], 1)
        self.assertEqual(row["console_file"], f"w3-lab-console-{INSTANCE}.txt")
        self.assertEqual(len(row["console_sha256"]), 64)
        self.assertFalse(any("lookup-events" in " ".join(call) or "cloudtrail" in " ".join(call) for call in calls))

    def test_each_due_instance_keeps_its_own_console(self) -> None:
        second = "i-0abcdef1234567890"

        def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
            text = " ".join(args)
            if "get-caller-identity" in text:
                return completed({"Account": lab.ACCOUNT_ID})
            if "describe-instances" in text and "--instance-ids" in args:
                wanted = args[args.index("--instance-ids") + 1]
                body = instance("terminated")
                body["InstanceId"] = wanted
                body["LaunchTime"] = "2026-09-30T12:00:00Z"
                return completed({"Reservations": [{"Instances": [body]}]})
            if "describe-instances" in text:
                first = instance("terminated")
                first["LaunchTime"] = "2026-09-30T12:00:00Z"
                other = instance("terminated")
                other["InstanceId"] = second
                other["LaunchTime"] = "2026-09-30T12:00:00Z"
                return completed({"Reservations": [{"Instances": [first, other]}]})
            if "get-console-output" in text:
                wanted = args[args.index("--instance-id") + 1]
                raw = base64.b64encode(f"console {wanted}\n".encode()).decode()
                return completed({"Output": raw})
            return completed({})

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "collect.json")
            os.environ.pop("INSTANCE_ID", None)
            os.environ.pop("W3_RUNNER_CIDR", None)
            result = steps.execute_collect_due(runner, NOW)
            names = sorted(path.name for path in Path(tmp).glob("w3-lab-console-*.txt"))
        rows = {row["instance_id"]: row for row in result["instances"]}
        self.assertEqual(names, sorted(row["console_file"] for row in rows.values()))
        self.assertEqual(set(rows), {INSTANCE, second})
        for row in rows.values():
            self.assertEqual(len(row["console_sha256"]), 64)
            self.assertNotEqual(rows[INSTANCE]["console_sha256"], rows[second]["console_sha256"])

    def test_ssh_failure_keeps_the_console_hash_on_the_row(self) -> None:
        def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
            text = " ".join(args)
            if "--dry-run" in args:
                return completed(code=254, stderr="An error occurred (DryRunOperation) when calling the operation")
            if "get-caller-identity" in text:
                return completed({"Account": lab.ACCOUNT_ID})
            if "describe-instances" in text and "--instance-ids" in args:
                body = instance()
                body["LaunchTime"] = "2026-09-30T12:00:00Z"
                return completed({"Reservations": [{"Instances": [body]}]})
            if "describe-instances" in text:
                body = instance()
                body["LaunchTime"] = "2026-09-30T12:00:00Z"
                return completed({"Reservations": [{"Instances": [body]}]})
            if "get-console-output" in text:
                raw = base64.b64encode(b"boot\nvantio-lab-marker seal=" + SEAL.encode() + b" pin=" + PIN.encode() + b"\n").decode()
                return completed({"Output": raw})
            return completed({})

        def ssh(_args: list[str], _script: str) -> subprocess.CompletedProcess[str]:
            return completed(code=255, stderr="Connection refused")

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "collect.json")
            os.environ["W3_STAMP"] = str(Path(tmp) / "stamp.json")
            os.environ["W3_RUNNER_CIDR"] = "1.1.1.1/32"
            os.environ.pop("INSTANCE_ID", None)
            os.environ.pop("W3_CONSOLE_PATH", None)
            result = steps.execute_collect_due(runner, NOW, ssh_runner=ssh)
            row = result["instances"][0]
            console = (Path(tmp) / row["console_file"]).read_bytes()
        self.assertEqual(row["reason"], "ssh")
        self.assertEqual(row["console_sha256"], hashlib.sha256(console).hexdigest())
        self.assertNotIn("PRIVATE KEY", console.decode("utf-8"))

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


class SoakDurabilityTests(unittest.TestCase):
    def test_check_lines_survive_the_rest_of_the_console(self) -> None:
        digest = "a" * 64
        other = "b" * 64
        console = "\n".join(
            [
                "boot",
                f"vantio-lab-check seq=1 name=arm result=pass sha256={digest}",
                "Power down",
                f"vantio-lab-check seq=2 name=soak result=fail sha256={other}",
                "BEGIN OPENSSH PRIVATE KEY",
            ]
        )
        checks = steps.parse_check_lines(console, source="console")
        self.assertEqual([item["seq"] for item in checks], [1, 2])
        self.assertEqual(checks[1]["result"], "fail")
        self.assertNotIn("PRIVATE", json.dumps(checks))

    def test_idle_discovery_does_not_launch(self) -> None:
        runner = FakeAws()
        runner.state = "terminated"
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "collect.json")
            os.environ.pop("INSTANCE_ID", None)
            try:
                result = steps.execute_collect_due(runner, NOW)
            finally:
                os.environ.pop("EVIDENCE_PATH", None)
        self.assertEqual(result["status"], "IDLE")
        self.assertEqual(result["check_count"], 0)
        self.assertFalse(any("run-instances" in " ".join(call) for call in runner.calls))

    def test_record_check_script_parses(self) -> None:
        script = ROOT / "scripts/aws/lab-guests/record-check.sh"
        completed = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)


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
            self.assertIn("group: vantio-lab-slot", text, name)
            self.assertIn("cancel-in-progress: false", text, name)
            self.assertNotRegex(text, r"(?m)^\s*AWS_ACCESS_KEY_ID:", name)
        arm = (ROOT / ".github/workflows/w3-lab-auto-arm.yml").read_text(encoding="utf-8")
        self.assertIn("close-ssh", arm)
        self.assertIn("w3-lab-console-${{ github.run_id }}", arm)
        self.assertIn("w3-lab-console-*.txt", arm)
        self.assertIn("if: always()", arm)
        soak = (ROOT / ".github/workflows/w3-lab-auto-long-soak.yml").read_text(encoding="utf-8")
        self.assertIn("default: false", soak)
        self.assertIn("w3-lab-auto-cost-gate.yml@main # oidc-trust", soak)
        self.assertFalse((ROOT / ".github/workflows/w3-lab-auto-enterprise-pe.yml").exists())
        self.assertIn("enterprise_rows:", arm)
        self.assertIn("- self-service", arm)
        self.assertIn("- reboot-check", arm)
        collect = (ROOT / ".github/workflows/w3-lab-auto-collect.yml").read_text(encoding="utf-8")
        self.assertIn("w3-lab-console-*.txt", collect)
        self.assertIn("arm-self-service", arm)
        self.assertNotIn("packages/vantio-install/docs/INSTALL.md", arm)
        self.assertNotIn("packages/vantio-install/pyproject.toml", arm)
        self.assertIn("default: false", arm)
        self.assertIn("W3_LAB_PRIVATE_BUNDLE_TOKEN", arm)
        self.assertIn("w3-lab-auto-arm.yml@refs/heads/main", arm)
        self.assertNotIn("0.0.0.0/0", arm)
        teardown = (ROOT / ".github/workflows/w3-lab-auto-teardown.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/aws/founder-soak-close.json", teardown)
        self.assertIn("bundle_commit:", arm)
        self.assertIn("W3_BUNDLE_COMMIT: ${{ inputs.bundle_commit }}", arm)
        self.assertIn("W3_EXPECTED_SEAL: ${{ steps.canonical.outputs.seal }}", arm)
        self.assertIn("jq -r '.lane_seal.sha256'", arm)
        self.assertIn("scripts/clean-host/t5/", arm)
        self.assertIn("scripts/aws/lab-guests/t5-egress.sh", arm)
        self.assertIn("W3_BATTERY: ${{ inputs.battery }}", arm)
        preamble = Path(steps.__file__).read_text(encoding="utf-8").split("def ", 1)[0]
        self.assertNotIn("import t5_battery", preamble)
        enterprise = Path(steps.__file__).read_text(encoding="utf-8")
        start = enterprise.index("def execute_enterprise_rows")
        chunk = enterprise[start:start + 1800]
        self.assertIn("import t5_battery", chunk)
        self.assertNotIn("ece6349e", arm)
        self.assertNotIn("0f3b0ad", arm)
        bundle = (ROOT / "scripts/aws/enterprise_bundle.py").read_text(encoding="utf-8")
        self.assertNotIn("ece6349e", bundle)
        self.assertNotIn("0f3b0ad", bundle)


_DROP = object()


def _trust(root: bool = True) -> bytes:
    return json.dumps(
        {
            "keys": [
                {
                    "algorithm": "ed25519",
                    "created": "2026-10-02",
                    "environment": "NON-PRODUCTION",
                    "fingerprint_sha256": "ab",
                    "key_class": "test",
                    "key_id": "test-nonprod-ed25519-2026-10-02",
                    "label": "TEST",
                    "not_a_production_root": root,
                    "public_key_b64": "AA==",
                }
            ]
        }
    ).encode()


def _tar_bytes(members: list[tuple[str, bytes]]) -> bytes:
    import io
    import tarfile

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, body in members:
            info = tarfile.TarInfo(name)
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))
    return buffer.getvalue()


class EnterpriseBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)

    def _write_bundle(self, directory: Path, *, root: bool = True, seal: bytes = b"seal-bytes", extra: tuple[str, bytes] | None = None) -> str:
        trust = _trust(root)
        members = [
            ("guest_rows.py", b"print('rows')\n"),
            ("fixtures/grant.json", b"{}\n"),
            ("vantio_enterprise_protocol/trust/test_nonprod_2026_10_02.json", trust),
        ]
        if extra is not None:
            members.append(extra)
        contract = _tar_bytes(members)
        (directory / "contract.tar").write_bytes(contract)
        (directory / "seal.oci.tar").write_bytes(seal)
        seal_sha = hashlib.sha256(seal).hexdigest()
        trust_sha = hashlib.sha256(trust).hexdigest()
        manifest = {
            "schema": "vantio.lab-enterprise-pe-bundle/v1",
            "seal_sha256": seal_sha,
            "contract_sha256": hashlib.sha256(contract).hexdigest(),
            "enterprise_sha": "56a6048c9b1d9907dc4f5879bdaa485d909dae1f",
            "trust_key_id": "test-nonprod-ed25519-2026-10-02",
            "not_a_production_root": True,
            "lab_only": True,
            "customer_release": False,
        }
        (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return trust_sha

    def test_missing_token_does_not_require_aws_and_stays_out_of_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "bundle.json")
            os.environ["W3_BUNDLE_DIR"] = str(Path(tmp) / "dest")
            os.environ.pop("W3_LAB_PRIVATE_BUNDLE_TOKEN", None)
            with self.assertRaises(lab.GuardAbort) as caught:
                enterprise_bundle.prepare_bundle()
            body = Path(os.environ["EVIDENCE_PATH"]).read_text(encoding="utf-8")
        self.assertEqual(caught.exception.reason, "missing_token")
        self.assertIn("BLOCKED_BUNDLE", body)
        self.assertNotIn("ghp_", body)

    def test_production_root_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            trust_sha = self._write_bundle(directory, root=False)
            with self.assertRaises(lab.GuardAbort) as caught:
                enterprise_bundle.inspect_bundle(
                    directory,
                    expected_seal=hashlib.sha256(b"seal-bytes").hexdigest(),
                    expected_trust=trust_sha,
                )
        self.assertEqual(caught.exception.reason, "bundle_production_root")

    def test_private_key_member_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self._write_bundle(directory, extra=("vantio_enterprise_protocol/private-key.pem", b"nope"))
            with self.assertRaises(lab.GuardAbort) as caught:
                enterprise_bundle.inspect_bundle(
                    directory,
                    expected_seal=hashlib.sha256(b"seal-bytes").hexdigest(),
                    expected_trust="a" * 64,
                )
        self.assertEqual(caught.exception.reason, "bundle_private_key")

    def test_public_pin_cannot_stand_in_for_the_seal(self) -> None:
        with self.assertRaises(lab.GuardAbort) as caught:
            enterprise_bundle.inspect_bundle(Path("."), expected_seal=PIN)
        self.assertEqual(caught.exception.reason, "bundle_wrong_seal")

    def test_matching_bundle_is_ready_and_hides_the_token(self) -> None:
        token = "github_pat_test_token_value"
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            source.mkdir()
            trust_sha = self._write_bundle(source)
            seal_sha = hashlib.sha256(b"seal-bytes").hexdigest()
            os.environ["W3_LAB_PRIVATE_BUNDLE_TOKEN"] = token
            os.environ["W3_BUNDLE_TAG"] = "lab-bundle/enterprise-pe-2026-10-08"
            os.environ["W3_BUNDLE_DIR"] = str(Path(tmp) / "dest")
            os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "bundle.json")

            def fetch(dest: Path) -> None:
                dest.mkdir(parents=True, exist_ok=True)
                for name in ("manifest.json", "seal.oci.tar", "contract.tar"):
                    (dest / name).write_bytes((source / name).read_bytes())

            result = enterprise_bundle.prepare_bundle(
                fetcher=fetch,
                expected_seal=seal_sha,
                expected_trust=trust_sha,
            )
            body = Path(os.environ["EVIDENCE_PATH"]).read_text(encoding="utf-8")
        self.assertEqual(result["status"], "BUNDLE_READY")
        self.assertNotIn(token, body)
        self.assertEqual(result["not_a_production_root"], True)

    def test_bundle_download_uses_the_pinned_commit_and_not_a_tag(self) -> None:
        args = enterprise_bundle.commit_download_args(
            "seal.oci.tar",
            enterprise_bundle.BUNDLE_COMMIT,
        )
        text = " ".join(args)
        self.assertIn(enterprise_bundle.BUNDLE_COMMIT, text)
        self.assertIn("application/vnd.github.raw", text)
        self.assertNotIn("release", text)
        self.assertNotIn("lab-bundle/enterprise-pe-2026-10-08", text)
        pin_args = " ".join(enterprise_bundle.public_pin_download_args(enterprise_bundle.BUNDLE_COMMIT))
        self.assertIn("lab-bundle/public-pin.oci.tar", pin_args)
        self.assertIn(enterprise_bundle.BUNDLE_COMMIT, pin_args)
        self.assertNotIn("release", pin_args)
        with tempfile.TemporaryDirectory() as tmp:
            wrong = Path(tmp) / "public-pin.oci.tar"
            wrong.write_bytes(b"not-the-public-pin")
            with self.assertRaises(lab.GuardAbort) as caught:
                enterprise_bundle.verify_public_pin(wrong)
            self.assertEqual(caught.exception.reason, "public_pin_digest")
        steps_text = Path(steps.__file__).read_text(encoding="utf-8")
        self.assertIn("verify_public_pin", steps_text)
        self.assertIn('copy_to(guest_dir / "product_uninstall_census.py", "product_uninstall_census.py")', steps_text)
        shell = Path(steps.__file__).resolve().parent.joinpath("lab-guests", "enterprise-rows.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('last.get("name") == "reupgrade"', shell)
        self.assertIn("authorized_uninstall", shell)

    def test_row_pull_sends_a_fresh_instance_connect_key(self) -> None:
        text = Path(steps.__file__).read_text(encoding="utf-8")
        helper = text[text.find("def _pull_lab_rows"): text.find("def _reboot_log_tail")]
        self.assertIn("LAB_ROWS_REMOTE", helper)
        self.assertNotIn("/tmp/enterprise-pe-rows.json", helper)
        note = helper.find("Instance Connect keys last 60 seconds")
        refresh = helper.find("_run_with_fresh_key")
        self.assertGreater(note, 0)
        self.assertLess(note, refresh)
        key_helper = text[text.find("def _run_with_fresh_key"): text.find("def _ssh_failure")]
        self.assertIn("connect + [public]", key_helper)
        execute = text[text.find("def execute_enterprise_rows"):]
        self.assertNotIn("/tmp/enterprise-pe-rows.json", execute)
        self.assertIn('f"{ssh_user}@{host}:{LAB_ROWS_REMOTE}"', helper)

    def test_real_pins_stay_on_the_policy_allow_seal(self) -> None:
        self.assertEqual(enterprise_bundle.POLICY_ALLOW_SEAL, SEAL)
        self.assertEqual(enterprise_bundle.PUBLIC_INSTALLER_PIN, PIN)
        self.assertEqual(enterprise_bundle.TRACKING_2A_SEAL, enterprise_bundle._SEAL.tracking_seal())
        self.assertTrue(enterprise_bundle.TRACKING_2A_SEAL.startswith("16c9e563"))
        self.assertNotEqual(enterprise_bundle.TRACKING_2A_SEAL, SEAL)
        self.assertEqual(
            enterprise_bundle.TRUST_BUNDLE_SHA256,
            "2e4a1da7bf44f0bddfc2a3ce3eda007fa6cc1455332f26769bd346fafc297876",
        )
        self.assertEqual(
            enterprise_bundle.BUNDLE_COMMIT,
            "75b6a94c1a50f07d3cc419a904ee08260c9c32ff",
        )

    def _patch_manifest(self, directory: Path, **fields: object) -> None:
        path = directory / "manifest.json"
        body = json.loads(path.read_text(encoding="utf-8"))
        for key, value in fields.items():
            if value is _DROP:
                body.pop(key, None)
            else:
                body[key] = value
        path.write_text(json.dumps(body), encoding="utf-8")

    def test_seal_file_that_does_not_match_the_manifest_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            trust_sha = self._write_bundle(directory)
            (directory / "seal.oci.tar").write_bytes(b"different-seal-bytes")
            with self.assertRaises(lab.GuardAbort) as caught:
                enterprise_bundle.inspect_bundle(
                    directory,
                    expected_seal=hashlib.sha256(b"seal-bytes").hexdigest(),
                    expected_trust=trust_sha,
                )
        self.assertEqual(caught.exception.reason, "bundle_seal")

    def test_manifest_digest_that_does_not_match_the_seal_file_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            trust_sha = self._write_bundle(directory)
            other = hashlib.sha256(b"different-seal-bytes").hexdigest()
            self._patch_manifest(directory, seal_sha256=other)
            with self.assertRaises(lab.GuardAbort) as caught:
                enterprise_bundle.inspect_bundle(
                    directory,
                    expected_seal=other,
                    expected_trust=trust_sha,
                )
        self.assertEqual(caught.exception.reason, "bundle_seal")

    def test_lab_only_must_be_exactly_true(self) -> None:
        for value in (False, "true", _DROP):
            with self.subTest(value=value):
                with tempfile.TemporaryDirectory() as tmp:
                    directory = Path(tmp)
                    trust_sha = self._write_bundle(directory)
                    self._patch_manifest(directory, lab_only=value)
                    with self.assertRaises(lab.GuardAbort) as caught:
                        enterprise_bundle.inspect_bundle(
                            directory,
                            expected_seal=hashlib.sha256(b"seal-bytes").hexdigest(),
                            expected_trust=trust_sha,
                        )
                self.assertEqual(caught.exception.reason, "bundle_not_lab_only")

    def test_customer_release_must_be_exactly_false(self) -> None:
        for value in (True, "false", _DROP):
            with self.subTest(value=value):
                with tempfile.TemporaryDirectory() as tmp:
                    directory = Path(tmp)
                    trust_sha = self._write_bundle(directory)
                    self._patch_manifest(directory, customer_release=value)
                    with self.assertRaises(lab.GuardAbort) as caught:
                        enterprise_bundle.inspect_bundle(
                            directory,
                            expected_seal=hashlib.sha256(b"seal-bytes").hexdigest(),
                            expected_trust=trust_sha,
                        )
                self.assertEqual(caught.exception.reason, "bundle_customer_release")

    def test_prepare_reads_seal_and_commit_from_the_environment(self) -> None:
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            source.mkdir()
            trust_sha = self._write_bundle(source)
            seal_sha = hashlib.sha256(b"seal-bytes").hexdigest()
            os.environ["W3_LAB_PRIVATE_BUNDLE_TOKEN"] = "github_pat_test_token_value"
            os.environ["W3_BUNDLE_DIR"] = str(Path(tmp) / "dest")
            os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "bundle.json")
            os.environ["W3_EXPECTED_SEAL"] = seal_sha
            os.environ["W3_BUNDLE_COMMIT"] = commit

            def fetch(dest: Path) -> None:
                dest.mkdir(parents=True, exist_ok=True)
                for name in ("manifest.json", "seal.oci.tar", "contract.tar"):
                    (dest / name).write_bytes((source / name).read_bytes())

            result = enterprise_bundle.prepare_bundle(fetcher=fetch, expected_trust=trust_sha)
        self.assertEqual(result["status"], "BUNDLE_READY")
        self.assertEqual(result["bundle_commit"], commit)
        self.assertEqual(result["seal_sha256"], seal_sha)
        self.assertIs(result["lab_only"], True)
        self.assertIs(result["customer_release"], False)

    def test_empty_bundle_commit_keeps_the_pinned_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            source.mkdir()
            trust_sha = self._write_bundle(source)
            seal_sha = hashlib.sha256(b"seal-bytes").hexdigest()
            os.environ["W3_LAB_PRIVATE_BUNDLE_TOKEN"] = "github_pat_test_token_value"
            os.environ["W3_BUNDLE_DIR"] = str(Path(tmp) / "dest")
            os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "bundle.json")
            os.environ["W3_EXPECTED_SEAL"] = seal_sha
            os.environ.pop("W3_BUNDLE_COMMIT", None)

            def fetch(dest: Path) -> None:
                dest.mkdir(parents=True, exist_ok=True)
                for name in ("manifest.json", "seal.oci.tar", "contract.tar"):
                    (dest / name).write_bytes((source / name).read_bytes())

            result = enterprise_bundle.prepare_bundle(fetcher=fetch, expected_trust=trust_sha)
        self.assertEqual(result["bundle_commit"], enterprise_bundle.BUNDLE_COMMIT)


class EnterpriseRowSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)

    def _env_ready(self, tmp: str) -> None:
        path = Path(tmp) / "caps.json"
        path.write_text(json.dumps({"ssh_instance_connect": True, "max_life_hours_36": True, "ssm": False}))
        os.environ["W3_LAB_CAPABILITIES"] = str(path)
        os.environ["INSTANCE_ID"] = INSTANCE
        os.environ["SEAL"] = SEAL
        os.environ["PUBLIC_PIN"] = PIN
        os.environ["W3_RUNNER_CIDR"] = "1.1.1.1/32"
        os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "arm.json")
        os.environ["W3_STAMP"] = str(Path(tmp) / "stamp.json")
        os.environ["W3_BUNDLE_DIR"] = str(Path(tmp) / "bundle")
        os.environ["W3_ROWS_PATH"] = str(Path(tmp) / "rows.json")
        Path(os.environ["W3_BUNDLE_DIR"]).mkdir()

    def test_checker_seal_mismatch_does_not_call_aws(self) -> None:
        runner = FakeAws()
        with tempfile.TemporaryDirectory() as tmp:
            self._env_ready(tmp)
            with self.assertRaises(lab.GuardAbort) as caught:
                steps.execute_enterprise_rows(
                    runner,
                    checker=lambda _path: {"seal_sha256": "ab" * 32},
                )
        self.assertEqual(caught.exception.reason, "bundle_wrong_seal")
        self.assertEqual(runner.calls, [])

    def test_bad_bundle_does_not_call_aws(self) -> None:
        runner = FakeAws()
        with tempfile.TemporaryDirectory() as tmp:
            self._env_ready(tmp)
            os.environ["W3_BUNDLE_DIR"] = str(Path(tmp) / "missing")
            with self.assertRaises(lab.GuardAbort) as caught:
                steps.execute_enterprise_rows(runner)
        self.assertEqual(caught.exception.reason, "bundle_layout")
        self.assertEqual(runner.calls, [])

    def test_self_service_missing_tree_does_not_call_aws(self) -> None:
        runner = FakeAws()
        with tempfile.TemporaryDirectory() as tmp:
            self._env_ready(tmp)
            os.environ["W3_BATTERY"] = "self-service"
            os.environ["W3_SELF_SERVICE_DIR"] = str(Path(tmp) / "missing")
            with self.assertRaises(lab.GuardAbort) as caught:
                steps.execute_enterprise_rows(runner)
        self.assertEqual(caught.exception.reason, "self_service_layout")
        self.assertEqual(runner.calls, [])

    def test_self_service_shell_does_not_pass_caller_trust(self) -> None:
        script = steps._self_service_shell("/var/lib/vantio-lab/enterprise-bundle", "/tmp/enterprise-pe-rows.json")
        self.assertNotIn("--artifact-trust", script)
        self.assertNotIn("--fixture-host", script)
        self.assertNotIn("contract.tar", script)
        self.assertIn("VANTIO_LAB_SCOPE=lab-nonprod", script)
        self.assertIn("self_service.py", script)
        text = Path(steps.__file__).read_text(encoding="utf-8")
        guard = text.find('if battery != "self-service":')
        seal = text.find('copy_to(bundle_dir / "seal.oci.tar"', guard)
        contract = text.find('copy_to(bundle_dir / "contract.tar"', guard)
        self.assertGreater(seal, guard)
        self.assertGreater(contract, guard)

    def test_self_service_private_key_is_refused_before_aws(self) -> None:
        runner = FakeAws()
        with tempfile.TemporaryDirectory() as tmp:
            self._env_ready(tmp)
            staged = Path(tmp) / "staged"
            staged.mkdir()
            for name in (
                "self_service.py",
                "self-service.tar",
                "lab-artifact-trust.json",
                "lab-dev-trust.json",
                "policy.json",
                "signature.json",
            ):
                (staged / name).write_text("{}\n", encoding="utf-8")
            (staged / "signature.json").write_text(
                "-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----\n",
                encoding="utf-8",
            )
            os.environ["W3_BATTERY"] = "self-service"
            os.environ["W3_SELF_SERVICE_DIR"] = str(staged)
            with self.assertRaises(lab.GuardAbort) as caught:
                steps.execute_enterprise_rows(runner)
        self.assertEqual(caught.exception.reason, "token_in_evidence")
        self.assertEqual(runner.calls, [])

    def test_guest_failure_still_revokes_and_shreds(self) -> None:
        runner = FakeAws()
        runner.dry_run = "allowed"

        def keygen(directory: Path) -> tuple[Path, str]:
            private = directory / "lab-ed25519"
            private.write_text(SECRET + "\n", encoding="utf-8")
            return private, "ssh-ed25519 AAAATEST vantio-lab"

        def ssh(args: list[str], script: str) -> subprocess.CompletedProcess[str]:
            self.assertNotIn(SECRET, " ".join(args))
            if args[0] == "ssh" and "enterprise-rows.sh" in " ".join(args):
                return completed(code=1, stdout="guest failed")
            if args[0] == "scp" and "enterprise-pe-rows.json" in " ".join(args):
                Path(args[-1]).write_text(json.dumps({"guest": "failed", "convergence_ms": 5597.3}), encoding="utf-8")
            return completed(stdout="")

        with tempfile.TemporaryDirectory() as tmp:
            self._env_ready(tmp)
            with self.assertRaises(lab.GuardAbort) as caught:
                steps.execute_enterprise_rows(
                    runner,
                    keygen=keygen,
                    ssh_runner=ssh,
                    checker=lambda _path: {"seal_sha256": SEAL, "not_a_production_root": True},
                )
            body = Path(os.environ["EVIDENCE_PATH"]).read_text(encoding="utf-8")
            self.assertFalse((Path(tmp) / "lab-ed25519").exists())
        self.assertEqual(caught.exception.reason, "guest")
        self.assertIn("FAILED", body)
        self.assertNotIn(SECRET, body)
        joined = [" ".join(call) for call in runner.calls]
        self.assertTrue(any("revoke-security-group-ingress" in item and "--dry-run" not in item for item in joined))

    def test_rows_upload_keeps_the_guest_result(self) -> None:
        runner = FakeAws()
        runner.dry_run = "allowed"

        def keygen(directory: Path) -> tuple[Path, str]:
            private = directory / "lab-ed25519"
            private.write_text("key\n", encoding="utf-8")
            return private, "ssh-ed25519 AAAATEST vantio-lab"

        def ssh(args: list[str], script: str) -> subprocess.CompletedProcess[str]:
            if args[0] == "scp" and "enterprise-pe-rows.json" in " ".join(args):
                Path(args[-1]).write_text(
                    json.dumps({"convergence_ms": 5597.3, "revoke": {"probe": {"nobody_errno": 13}}}),
                    encoding="utf-8",
                )
            return completed(stdout="")

        with tempfile.TemporaryDirectory() as tmp:
            self._env_ready(tmp)
            result = steps.execute_enterprise_rows(
                runner,
                keygen=keygen,
                ssh_runner=ssh,
                checker=lambda _path: {"seal_sha256": SEAL},
            )
            rows = json.loads(Path(os.environ["W3_ROWS_PATH"]).read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "ENTERPRISE_ROWS")
        self.assertEqual(rows["convergence_ms"], 5597.3)
        self.assertFalse((Path(tmp) / "seal.oci.tar").exists())

    def test_publickey_on_a_new_connection_pushes_the_key_again(self) -> None:
        runner = FakeAws()
        runner.dry_run = "allowed"
        seen = {"mkdir": 0}

        def keygen(directory: Path) -> tuple[Path, str]:
            private = directory / "lab-ed25519"
            private.write_text("key\n", encoding="utf-8")
            return private, "ssh-ed25519 AAAATEST vantio-lab"

        def ssh(args: list[str], script: str) -> subprocess.CompletedProcess[str]:
            if args[0] == "ssh" and "mkdir" in " ".join(args):
                seen["mkdir"] += 1
                if seen["mkdir"] == 1:
                    return completed(code=255, stderr="ubuntu@1.1.1.1: Permission denied (publickey).\n")
            if args[0] == "scp" and "enterprise-pe-rows.json" in " ".join(args):
                Path(args[-1]).write_text(json.dumps({"ok": True}), encoding="utf-8")
            return completed(stdout="")

        old_sleep = steps.time.sleep
        steps.time.sleep = lambda _seconds: None
        try:
            with tempfile.TemporaryDirectory() as tmp:
                self._env_ready(tmp)
                result = steps.execute_enterprise_rows(
                    runner,
                    keygen=keygen,
                    ssh_runner=ssh,
                    checker=lambda _path: {"seal_sha256": SEAL},
                )
        finally:
            steps.time.sleep = old_sleep
        sends = [call for call in runner.calls if "send-ssh-public-key" in call]
        self.assertGreaterEqual(len(sends), 2)
        self.assertIn("ubuntu", sends[0])
        self.assertEqual(result["status"], "ENTERPRISE_ROWS")
        self.assertEqual(seen["mkdir"], 2)

    def test_guest_exit_is_not_retried_as_a_key_miss(self) -> None:
        runner = FakeAws()
        runner.dry_run = "allowed"
        seen = {"bash": 0}

        def keygen(directory: Path) -> tuple[Path, str]:
            private = directory / "lab-ed25519"
            private.write_text("key\n", encoding="utf-8")
            return private, "ssh-ed25519 AAAATEST vantio-lab"

        def ssh(args: list[str], script: str) -> subprocess.CompletedProcess[str]:
            if args[0] == "ssh" and "enterprise-rows.sh" in " ".join(args):
                seen["bash"] += 1
                return completed(code=2, stderr="rows failed")
            if args[0] == "scp" and "enterprise-pe-rows.json" in " ".join(args):
                Path(args[-1]).write_text("{}", encoding="utf-8")
            return completed(stdout="")

        with tempfile.TemporaryDirectory() as tmp:
            self._env_ready(tmp)
            with self.assertRaises(lab.GuardAbort) as caught:
                steps.execute_enterprise_rows(
                    runner,
                    keygen=keygen,
                    ssh_runner=ssh,
                    checker=lambda _path: {"seal_sha256": SEAL},
                )
        self.assertEqual(seen["bash"], 1)
        self.assertEqual(caught.exception.reason, "guest")

    def test_guest_text_that_mentions_a_closed_connection_is_not_retried(self) -> None:
        runner = FakeAws()
        runner.dry_run = "allowed"
        seen = {"bash": 0}

        def keygen(directory: Path) -> tuple[Path, str]:
            private = directory / "lab-ed25519"
            private.write_text("key\n", encoding="utf-8")
            return private, "ssh-ed25519 AAAATEST vantio-lab"

        def ssh(args: list[str], script: str) -> subprocess.CompletedProcess[str]:
            if args[0] == "ssh" and "enterprise-rows.sh" in " ".join(args):
                seen["bash"] += 1
                return completed(code=1, stdout="probe Connection refused")
            if args[0] == "scp" and "enterprise-pe-rows.json" in " ".join(args):
                Path(args[-1]).write_text("{}", encoding="utf-8")
            return completed(stdout="")

        with tempfile.TemporaryDirectory() as tmp:
            self._env_ready(tmp)
            with self.assertRaises(lab.GuardAbort) as caught:
                steps.execute_enterprise_rows(
                    runner,
                    keygen=keygen,
                    ssh_runner=ssh,
                    checker=lambda _path: {"seal_sha256": SEAL},
                )
        self.assertEqual(seen["bash"], 1)
        self.assertEqual(caught.exception.reason, "guest")

    def test_ssh_failure_redacts_before_it_truncates(self) -> None:
        secret = "-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n-----END OPENSSH PRIVATE KEY-----"
        proc = completed(code=1, stderr=("x" * 400) + secret + "\nPermission denied (publickey)")
        with self.assertRaises(lab.GuardAbort) as caught:
            steps._ssh_failure(proc)
        self.assertNotIn("BEGIN OPENSSH", caught.exception.reason)
        self.assertNotIn("abc", caught.exception.reason)
        self.assertIn("publickey", caught.exception.reason)

    def test_phase_egress_env_uses_the_private_address(self) -> None:
        self.assertEqual(
            steps.phase_egress_env("172.31.24.10"),
            ["VANTIO_EGRESS_HOST=172.31.24.10", "VANTIO_EGRESS_PORT=4879"],
        )
        self.assertEqual(steps.phase_egress_env("192.0.2.2"), [])
        self.assertEqual(steps.phase_egress_env("  "), [])
        self.assertEqual(steps.private_ipv4({"PrivateIpAddress": "10.0.0.5"}), "10.0.0.5")

    def test_guest_script_parses(self) -> None:
        script = ROOT / "scripts/aws/lab-guests/enterprise-rows.sh"
        completed_run = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        self.assertEqual(completed_run.returncode, 0, completed_run.stderr)
        text = script.read_text(encoding="utf-8")
        self.assertNotIn("apt-get", text)
        self.assertIn("refusing network apt", text)
        self.assertIn("UNINSTALL_VERIFIED", text)
        self.assertIn("deny_attr_post_kill", text)
        self.assertLess(text.index("authorized_uninstall"), text.index('exit "$rc"'))
        chown_at = text.index('sudo chown -R "$(id -un):$(id -un)" "$stage"')
        patch_at = text.index("path.write_text(text.replace(probe, probed)")
        self.assertLess(chown_at, patch_at)
        self.assertIn("brain=/var/lib/vantio-lab/brain", text)
        self.assertIn("VANTIO_BRAIN_DIR", text)
        self.assertIn("normalize_loaded_image", text)
        self.assertIn("accept_loaded_image", text)
        self.assertNotIn('test "$image" = "$image_name"', text)
        self.assertIn("AccuracySec=1s", text)
        self.assertIn("reboot_not_scheduled", text)
        self.assertIn("--system --slice=system.slice", text)
        self.assertIn("--unit=\"$unit\"", text)
        self.assertIn("unit=vantio-lab-lsm-reboot", text)
        self.assertIn('if [ "${2:-}" = "reboot-check" ]; then', text)
        check = text[text.index('if [ "${2:-}" = "reboot-check" ]; then') : text.index('sudo rm -rf "$stage"')]
        self.assertLess(check.index("sudo rm -f /tmp/enterprise-pe-rows.json"), check.index("schedule_forced_reboot"))
        self.assertLess(check.index("stamp_host_evidence"), check.index("publish_durable_rows"))
        self.assertLess(check.index("publish_durable_rows"), check.index("schedule_forced_reboot"))
        self.assertLess(check.index("ensure_stock_reboot_script"), check.index("reboot_script_missing"))
        self.assertLess(check.index("reboot_script_missing"), check.index("schedule_forced_reboot"))
        ensure = text[text.index("ensure_stock_reboot_script() {") : text.index("stage_reboot_guest_files() {")]
        self.assertIn("install_stock_reboot_script", ensure)
        self.assertIn("[ -x /var/lib/vantio-lab/reboot-with-grub.sh ]", ensure)
        schedule = text[text.index("schedule_forced_reboot() {") : text.index("# A second boot already has bpf")]
        self.assertLess(schedule.index("stage_reboot_guest_files"), schedule.index("systemd-run"))
        self.assertNotIn("install_stock_reboot_script", schedule)
        staged = text[text.index("stage_reboot_guest_files() {") : text.index("schedule_forced_reboot() {")]
        self.assertIn("/var/lib/vantio-lab/guest/baseline_diag.py", staged)
        b1_at = text.index('if [ "$mode" = "descendant-b1" ]; then')
        b1 = text[b1_at : text.index('case "$mode" in', b1_at)]
        self.assertLess(b1.index("publish_durable_rows"), b1.index('if [ "$phase" = "pre" ] && [ "$rc" -eq 0 ]; then'))
        descendant_at = b1.index('if [ "$phase" = "pre" ] && [ "$rc" -eq 0 ]; then')
        descendant = b1[descendant_at : b1.index('exit "$rc"', descendant_at)]
        self.assertLess(descendant.index("ensure_stock_reboot_script"), descendant.index("schedule_forced_reboot"))
        self.assertIn('python3 "$here/redteam_rows.py" "$stage" pre', b1)
        self.assertNotIn('redteam_rows.py" "$stage" post', b1)
        self.assertIn("/var/lib/vantio-lab/redteam-rows.json", b1)
        self.assertIn("r15-container-exit|2c-upgrade-rollback", text)
        guard_at = text.index('if [ "$mode" = "lsm-guard" ]; then')
        guard = text[text.rfind("publish_durable_rows", 0, guard_at) : text.index('exit "$rc"', guard_at)]
        self.assertLess(guard.index("publish_durable_rows"), guard.index("schedule_forced_reboot"))
        self.assertIn('open("/var/lib/vantio-lab/enterprise-pe-rows.json")', guard)
        self.assertIn("sudo python3", check)
        self.assertIn("systemctl stop vantio-lab-lsm-reboot.timer", check)
        self.assertNotIn("schedule_forced_reboot vantio-lab", text)
        self.assertNotIn("systemctl reboot --force", text)
        self.assertEqual(text.count("schedule_forced_reboot()"), 1)
        self.assertIn('sudo python3 - "$here/sticky_write.py"', text)
        uninstall = text[text.index("authorized_uninstall()"): text.index("\nmode=${2:-enterprise}")]
        self.assertLess(uninstall.index("sudo rm -f /var/lib/vantio-lab/vantio-uninstall.out"), uninstall.index("ensure_working_bpftool"))
        self.assertIn('echo "UNINSTALL_RESIDUAL bpftool missing" | tee -a /var/lib/vantio-lab/vantio-uninstall.out', uninstall)
        self.assertIn('echo "UNINSTALL_NOT_VERIFIED rc=$urc" | tee -a /var/lib/vantio-lab/vantio-uninstall.out', uninstall)
        self.assertIn('echo "UNINSTALL_RESIDUAL bpffs"', uninstall)
        self.assertIn("| tee -a /var/lib/vantio-lab/vantio-uninstall.out", uninstall)
        self.assertNotIn("sudo tee -a /var/lib/vantio-lab/vantio-uninstall.out", uninstall)
        self.assertNotIn("/tmp/vantio-uninstall.out", uninstall)
        self.assertIn("stamp_host_evidence", text)
        self.assertIn('sudo env VANTIO_IMAGE_NAME="${VANTIO_IMAGE_NAME:-}" python3 - "$here"', text)
        self.assertIn(
            'VANTIO_IMAGE_NAME="${VANTIO_IMAGE_NAME:-}" VANTIO_EGRESS_HOST="${VANTIO_EGRESS_HOST:-}" VANTIO_EGRESS_PORT="${VANTIO_EGRESS_PORT:-}" python3 "$here/phase2_host.py"',
            text,
        )
        self.assertIn(
            'VANTIO_IMAGE_NAME="${VANTIO_IMAGE_NAME:-}" VANTIO_EGRESS_HOST="${VANTIO_EGRESS_HOST:-}" VANTIO_EGRESS_PORT="${VANTIO_EGRESS_PORT:-}" bash /var/lib/vantio-lab/bin/soak-hourly.sh',
            text,
        )
        diag = (ROOT / "scripts/aws/lab-guests/baseline_diag.py").read_text(encoding="utf-8")
        self.assertIn('Path("/sys/kernel/security/lockdown")', diag)
        self.assertIn("def read_image_name", diag)
        self.assertNotIn("systemctl reboot --force || true", text)
        self.assertIn(
            "sudo rm -f /var/lib/vantio-lab/b1-pre.json /var/lib/vantio-lab/enterprise-pe-rows.json /tmp/enterprise-pe-rows.json",
            text,
        )
        auto_text = (ROOT / "scripts/aws/w3_lab_auto.py").read_text(encoding="utf-8")
        steps_text = (ROOT / "scripts/aws/w3_lab_steps.py").read_text(encoding="utf-8")
        self.assertIn('BRAIN_GUEST_DIR = "/var/lib/vantio-lab/brain"', auto_text)
        self.assertIn("lab.BRAIN_GUEST_DIR", steps_text)
        self.assertIn("brain_not_landed", steps_text)
        rows_text = (ROOT / "scripts/gcp/lab-guests/redteam_rows.py").read_text(encoding="utf-8")
        self.assertNotIn("pe.escape.move", rows_text)
        self.assertIn("grade_tamper", rows_text)
        fetch = ROOT / "scripts/aws/fetch_offline_debs.sh"
        fetch_run = subprocess.run(["bash", "-n", str(fetch)], capture_output=True, text=True)
        self.assertEqual(fetch_run.returncode, 0, fetch_run.stderr)

    def test_loaded_image_rule_is_the_guest_shell(self) -> None:
        script = ROOT / "scripts/aws/lab-guests/enterprise-rows.sh"
        text = script.read_text(encoding="utf-8")
        start = text.index("normalize_loaded_image()")
        end = text.index("\nload=$(sudo docker load")
        funcs = text[start:end]
        self.assertIn("loaded_image_refused", funcs)
        self.assertIn("^vantio-phantom-engine:[0-9a-f]{7,40}$", funcs)
        rows = Path("/tmp/enterprise-pe-rows.json")
        saved = rows.read_bytes() if rows.is_file() else None
        program = (
            "set -u\n"
            "publish_durable_rows() { return 0; }\n"
            "image_name=vantio-phantom-engine:egress-2e6ab54\n"
            f"{funcs}\n"
            'if [ "$1" = accept ]; then accept_loaded_image "$2"; else normalize_loaded_image "$2"; fi\n'
        )

        def run(mode: str, payload: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                ["bash", "-c", program, "image-rule", mode, payload],
                capture_output=True,
                text=True,
            )

        try:
            rows.unlink(missing_ok=True)
            accepted = run("accept", "Loaded image: vantio-phantom-engine:deb6faa3\n")
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            self.assertEqual(accepted.stdout.strip(), "vantio-phantom-engine:deb6faa3")
            historical = run(
                "accept",
                "Loaded image: docker.io/library/vantio-phantom-engine:egress-2e6ab54\r\n",
            )
            self.assertEqual(historical.returncode, 0, historical.stderr)
            self.assertEqual(historical.stdout.strip(), "vantio-phantom-engine:egress-2e6ab54")
            seven = "a" * 7
            short_ok = run("name", f"vantio-phantom-engine:{seven}")
            self.assertEqual(short_ok.returncode, 0, short_ok.stderr)
            self.assertEqual(short_ok.stdout.strip(), f"vantio-phantom-engine:{seven}")
            forty = "b" * 40
            long_ok = run("name", f"vantio-phantom-engine:{forty}")
            self.assertEqual(long_ok.returncode, 0, long_ok.stderr)
            self.assertEqual(long_ok.stdout.strip(), f"vantio-phantom-engine:{forty}")
            for bad in (
                "Loaded image: vantio-phantom-engine:latest\n",
                "Loaded image: vantio-phantom-engine:" + ("c" * 6) + "\n",
                "Loaded image: vantio-phantom-engine:" + ("d" * 41) + "\n",
                "Loaded image: other:deb6faa3\n",
                "Loaded image: vantio-phantom-engine:DEB6FAA3\n",
                "\n",
            ):
                rows.unlink(missing_ok=True)
                refused = run("accept", bad)
                self.assertEqual(refused.returncode, 6, refused.stderr)
                body = json.loads(rows.read_text(encoding="utf-8"))
                self.assertEqual(body["reason"], "loaded_image_refused")
                self.assertIs(body["lab_pass"], False)
                self.assertIs(body["reboot_requested"], False)
        finally:
            if saved is None:
                rows.unlink(missing_ok=True)
            else:
                rows.write_bytes(saved)

    def test_uninstall_tail_is_not_labeled_programs_not_removed(self) -> None:
        runner = FakeAws()
        runner.dry_run = "allowed"

        def keygen(directory: Path) -> tuple[Path, str]:
            private = directory / "lab-ed25519"
            private.write_text("key\n", encoding="utf-8")
            return private, "ssh-ed25519 AAAATEST vantio-lab"

        def ssh(args: list[str], script: str) -> subprocess.CompletedProcess[str]:
            if args[0] == "ssh" and "enterprise-rows.sh" in " ".join(args):
                return completed(code=1, stdout="UNINSTALL_NOT_VERIFIED")
            if args[0] == "scp" and "enterprise-pe-rows.json" in " ".join(args):
                Path(args[-1]).write_text(
                    json.dumps(
                        {
                            "boot_id": "boot-a",
                            "removal": {"verified_removed": True, "loader_programs": []},
                            "uninstall_tail": "UNINSTALL_NOT_VERIFIED rc=1\n",
                        }
                    ),
                    encoding="utf-8",
                )
            if args[0] == "ssh" and "boot_id" in " ".join(args):
                return completed(stdout="boot-a\n")
            return completed(stdout="")

        with tempfile.TemporaryDirectory() as tmp:
            self._env_ready(tmp)
            with self.assertRaises(lab.GuardAbort) as caught:
                steps.execute_enterprise_rows(
                    runner,
                    keygen=keygen,
                    ssh_runner=ssh,
                    checker=lambda _path: {"seal_sha256": SEAL},
                )
        self.assertEqual(caught.exception.reason, "uninstall_not_verified")
        self.assertEqual(
            steps._guest_failure_reason({"uninstall_tail": "UNINSTALL_VERIFIED\nUNINSTALL_GRUB_LSM\n"}),
            "uninstall_grub_lsm",
        )

    def test_a_rows_file_from_another_boot_fails_closed(self) -> None:
        runner = FakeAws()
        runner.dry_run = "allowed"

        def keygen(directory: Path) -> tuple[Path, str]:
            private = directory / "lab-ed25519"
            private.write_text("key\n", encoding="utf-8")
            return private, "ssh-ed25519 AAAATEST vantio-lab"

        def ssh(args: list[str], script: str) -> subprocess.CompletedProcess[str]:
            if args[0] == "scp" and "enterprise-pe-rows.json" in " ".join(args):
                Path(args[-1]).write_text(json.dumps({"boot_id": "old-boot"}), encoding="utf-8")
            if args[0] == "ssh" and "boot_id" in " ".join(args):
                return completed(stdout="new-boot\n")
            return completed(stdout="")

        with tempfile.TemporaryDirectory() as tmp:
            self._env_ready(tmp)
            with self.assertRaises(lab.GuardAbort) as caught:
                steps.execute_enterprise_rows(
                    runner,
                    keygen=keygen,
                    ssh_runner=ssh,
                    checker=lambda _path: {"seal_sha256": SEAL},
                )
        self.assertEqual(caught.exception.reason, "stale_rows")

    def test_reboot_check_confirms_a_new_boot_id(self) -> None:
        runner = FakeAws()
        runner.dry_run = "allowed"
        released = {"n": 0}

        def keygen(directory: Path) -> tuple[Path, str]:
            private = directory / "lab-ed25519"
            private.write_text("key\n", encoding="utf-8")
            return private, "ssh-ed25519 AAAATEST vantio-lab"

        def ssh(args: list[str], script: str) -> subprocess.CompletedProcess[str]:
            joined = " ".join(args)
            if args[0] == "scp" and "enterprise-pe-rows.json" in joined:
                Path(args[-1]).write_text(
                    json.dumps(
                        {
                            "battery": "reboot-check",
                            "boot_id": "boot-old",
                            "reboot_requested": True,
                            "unit": "vantio-lab-lsm-reboot",
                        }
                    ),
                    encoding="utf-8",
                )
            if args[0] == "ssh" and args[-1] == "/proc/sys/kernel/random/boot_id":
                return completed(stdout="boot-new\n")
            if args[0] == "ssh" and args[-1] == "/proc/cmdline":
                return completed(
                    stdout="root=PARTUUID ro console=ttyS0 lsm=lockdown,capability,landlock,yama,apparmor,bpf\n"
                )
            if args[0] == "ssh" and args[-1] == "/sys/kernel/security/lsm":
                return completed(stdout="lockdown,capability,landlock,yama,apparmor,bpf\n")
            if args[0] == "ssh" and args[-1] == "/sys/kernel/security/lockdown":
                return completed(stdout="[none] integrity confidentiality\n")
            return completed(stdout="")

        def wait(*_args: object, **kwargs: object) -> str:
            note = kwargs.get("note")
            if isinstance(note, dict):
                note["before"] = "boot-old"
            release = kwargs.get("release")
            if callable(release):
                release()
                released["n"] += 1
            return "boot-new"

        original = steps._wait_for_reboot
        steps._wait_for_reboot = wait
        try:
            with tempfile.TemporaryDirectory() as tmp:
                self._env_ready(tmp)
                os.environ["W3_BATTERY"] = "reboot-check"
                result = steps.execute_enterprise_rows(
                    runner,
                    keygen=keygen,
                    ssh_runner=ssh,
                    checker=lambda _path: {"seal_sha256": SEAL},
                )
        finally:
            steps._wait_for_reboot = original
        self.assertEqual(result["status"], "REBOOT_CHECKED")
        self.assertEqual(result["scheduled_boot_id"], "boot-old")
        self.assertEqual(result["boot_id"], "boot-new")
        self.assertEqual(released["n"], 1)
        post = result["post_boot"]
        self.assertEqual(post["boot_id"], "boot-new")
        self.assertEqual(
            post["cmdline"],
            "root=PARTUUID ro console=ttyS0 lsm=lockdown,capability,landlock,yama,apparmor,bpf",
        )
        self.assertEqual(post["lsm"], "lockdown,capability,landlock,yama,apparmor,bpf")
        self.assertEqual(post["lockdown"], "[none] integrity confidentiality")
        self.assertEqual(post["image_name"], "ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-20260901")
        self.assertTrue(result["console_file"].startswith("w3-lab-console-"))
        self.assertEqual(len(result["console_sha256"]), 64)
        self.assertTrue(any("get-console-output" in call for call in runner.calls))

    def _keygen(self, directory: Path) -> tuple[Path, str]:
        private = directory / "lab-ed25519"
        private.write_text("key\n", encoding="utf-8")
        return private, "ssh-ed25519 AAAATEST vantio-lab"

    def test_reboot_check_reads_the_record_that_survives_tmpfs(self) -> None:
        runner = FakeAws()
        runner.dry_run = "allowed"
        pulled: list[str] = []

        def ssh(args: list[str], script: str) -> subprocess.CompletedProcess[str]:
            joined = " ".join(args)
            if args[0] == "scp" and "enterprise-pe-rows.json" in joined:
                pulled.append(joined)
                if "/tmp/enterprise-pe-rows.json" in joined:
                    raise AssertionError("reboot-check pulled /tmp")
                Path(args[-1]).write_text(
                    json.dumps(
                        {
                            "battery": "reboot-check",
                            "boot_id": "boot-old",
                            "reboot_requested": True,
                            "unit": "vantio-lab-lsm-reboot",
                        }
                    ),
                    encoding="utf-8",
                )
            if args[0] == "ssh" and args[-1] == "/proc/sys/kernel/random/boot_id":
                return completed(stdout="boot-new\n")
            if args[0] == "ssh" and args[-1] == "/proc/cmdline":
                return completed(stdout="root=PARTUUID ro console=ttyS0 lsm=lockdown,capability,apparmor,bpf\n")
            if args[0] == "ssh" and args[-1] == "/sys/kernel/security/lsm":
                return completed(stdout="lockdown,capability,apparmor,bpf\n")
            if args[0] == "ssh" and args[-1] == "/sys/kernel/security/lockdown":
                return completed(stdout="[none] integrity confidentiality\n")
            return completed(stdout="")

        def wait(*_args: object, **kwargs: object) -> str:
            note = kwargs.get("note")
            if isinstance(note, dict):
                note["before"] = "boot-old"
            return "boot-new"

        original = steps._wait_for_reboot
        steps._wait_for_reboot = wait
        try:
            with tempfile.TemporaryDirectory() as tmp:
                self._env_ready(tmp)
                os.environ["W3_BATTERY"] = "reboot-check"
                result = steps.execute_enterprise_rows(
                    runner,
                    keygen=self._keygen,
                    ssh_runner=ssh,
                    checker=lambda _path: {"seal_sha256": SEAL},
                )
        finally:
            steps._wait_for_reboot = original
        self.assertEqual(result["status"], "REBOOT_CHECKED")
        self.assertEqual(result["boot_id"], "boot-new")
        self.assertTrue(pulled)
        self.assertTrue(all("/var/lib/vantio-lab/enterprise-pe-rows.json" in item for item in pulled))

    def test_a_missing_record_is_rows_missing_even_when_the_log_has_json(self) -> None:
        runner = FakeAws()
        runner.dry_run = "allowed"
        record = json.dumps(
            {
                "battery": "reboot-check",
                "boot_id": "boot-old",
                "reboot_requested": True,
                "unit": "vantio-lab-lsm-reboot",
            }
        )

        def ssh(args: list[str], script: str) -> subprocess.CompletedProcess[str]:
            joined = " ".join(args)
            if args[0] == "scp" and "enterprise-pe-rows.json" in joined:
                return completed(code=1, stderr="No such file")
            if args[0] == "ssh" and "enterprise-rows.sh" in joined:
                return completed(stdout=f"seal.oci.tar: OK\nreboot_scheduled\n{record}\n")
            if args[0] == "ssh" and args[-1] == "/proc/sys/kernel/random/boot_id":
                return completed(stdout="boot-new\n")
            return completed(stdout="")

        def wait(*_args: object, **kwargs: object) -> str:
            note = kwargs.get("note")
            if isinstance(note, dict):
                note["before"] = "boot-old"
            return "boot-new"

        original = steps._wait_for_reboot
        steps._wait_for_reboot = wait
        try:
            with tempfile.TemporaryDirectory() as tmp:
                self._env_ready(tmp)
                os.environ["W3_BATTERY"] = "reboot-check"
                with self.assertRaises(lab.GuardAbort) as caught:
                    steps.execute_enterprise_rows(
                        runner,
                        keygen=self._keygen,
                        ssh_runner=ssh,
                        checker=lambda _path: {"seal_sha256": SEAL},
                    )
        finally:
            steps._wait_for_reboot = original
        self.assertEqual(caught.exception.reason, "rows_missing")

    def test_a_malformed_record_is_rows_malformed(self) -> None:
        runner = FakeAws()
        runner.dry_run = "allowed"

        def ssh(args: list[str], script: str) -> subprocess.CompletedProcess[str]:
            joined = " ".join(args)
            if args[0] == "scp" and "enterprise-pe-rows.json" in joined:
                Path(args[-1]).write_text("not-json\n", encoding="utf-8")
            if args[0] == "ssh" and args[-1] == "/proc/sys/kernel/random/boot_id":
                return completed(stdout="boot-new\n")
            return completed(stdout="")

        with tempfile.TemporaryDirectory() as tmp:
            self._env_ready(tmp)
            with self.assertRaises(lab.GuardAbort) as caught:
                steps.execute_enterprise_rows(
                    runner,
                    keygen=self._keygen,
                    ssh_runner=ssh,
                    checker=lambda _path: {"seal_sha256": SEAL},
                )
        self.assertEqual(caught.exception.reason, "rows_malformed")

    def test_descendant_b1_reads_the_durable_record_after_tmp_is_wiped(self) -> None:
        runner = FakeAws()
        runner.dry_run = "allowed"
        pulled: list[str] = []

        def ssh(args: list[str], script: str) -> subprocess.CompletedProcess[str]:
            joined = " ".join(args)
            if args[0] == "scp" and "redteam-rows.json" in joined:
                pulled.append(joined)
                if "/tmp/redteam-rows.json" in joined:
                    raise AssertionError("descendant-b1 pulled /tmp redteam rows")
                Path(args[-1]).write_text(
                    json.dumps({"attempts": [{"technique_id": "pe.tamper.loader_kill"}]}),
                    encoding="utf-8",
                )
            if args[0] == "scp" and "enterprise-pe-rows.json" in joined:
                pulled.append(joined)
                if "/tmp/enterprise-pe-rows.json" in joined:
                    raise AssertionError("descendant-b1 pulled /tmp")
                Path(args[-1]).write_text(
                    json.dumps(
                        {
                            "battery": "descendant-b1",
                            "reboot_observed": True,
                            "pre": {"boot_id": "boot-old", "descendant_pass": True},
                            "post": {"boot_id": "boot-new", "descendant_pass": True},
                        }
                    ),
                    encoding="utf-8",
                )
            if args[0] == "ssh" and args[-1] == "/proc/sys/kernel/random/boot_id":
                return completed(stdout="boot-new\n")
            return completed(stdout="")

        def wait(*_args: object, **kwargs: object) -> str:
            note = kwargs.get("note")
            if isinstance(note, dict):
                note["before"] = "boot-old"
            return "boot-new"

        original = steps._wait_for_reboot
        steps._wait_for_reboot = wait
        try:
            with tempfile.TemporaryDirectory() as tmp:
                self._env_ready(tmp)
                os.environ["W3_BATTERY"] = "descendant-b1"
                result = steps.execute_enterprise_rows(
                    runner,
                    keygen=self._keygen,
                    ssh_runner=ssh,
                    checker=lambda _path: {"seal_sha256": SEAL},
                )
        finally:
            steps._wait_for_reboot = original
        self.assertEqual(result["status"], "DESCENDANT_B1")
        self.assertEqual(result["boot_id"], "boot-new")
        enterprise_pulls = [item for item in pulled if "enterprise-pe-rows.json" in item]
        redteam_pulls = [item for item in pulled if "redteam-rows.json" in item]
        self.assertTrue(enterprise_pulls)
        self.assertTrue(all("/var/lib/vantio-lab/enterprise-pe-rows.json" in item for item in enterprise_pulls))
        self.assertTrue(redteam_pulls)
        self.assertTrue(all("/var/lib/vantio-lab/redteam-rows.json" in item for item in redteam_pulls))
        self.assertTrue(result.get("redteam_rows_sha256"))

    def test_descendant_b1_start_window_warning_is_informational(self) -> None:
        runner = FakeAws()
        runner.dry_run = "allowed"
        pulled: list[str] = []

        def ssh(args: list[str], script: str) -> subprocess.CompletedProcess[str]:
            joined = " ".join(args)
            if args[0] == "scp" and "redteam-rows.json" in joined:
                pulled.append(joined)
                if "/tmp/redteam-rows.json" in joined:
                    raise AssertionError("descendant-b1 pulled /tmp redteam rows")
                Path(args[-1]).write_text(
                    json.dumps({"attempts": [{"technique_id": "pe.tamper.loader_kill"}]}),
                    encoding="utf-8",
                )
            if args[0] == "scp" and "enterprise-pe-rows.json" in joined:
                pulled.append(joined)
                if "/tmp/enterprise-pe-rows.json" in joined:
                    raise AssertionError("descendant-b1 pulled /tmp")
                Path(args[-1]).write_text(
                    json.dumps(
                        {
                            "battery": "descendant-b1",
                            "reboot_observed": True,
                            "pre": {"boot_id": "boot-old", "descendant_pass": True, "scoped_banner": "scoped",
                                    "start_window_rows": {"status": "none_missing", "delayed": 0, "dropped": 0}},
                            "post": {"boot_id": "boot-new", "descendant_pass": True,
                                     "scoped_banner": "scoped_banner_without_ledger_line",
                                     "start_window_rows": {"status": "delayed", "delayed": 1, "dropped": 0, "checked": []}},
                        }
                    ),
                    encoding="utf-8",
                )
            if args[0] == "ssh" and args[-1] == "/proc/sys/kernel/random/boot_id":
                return completed(stdout="boot-new\n")
            return completed(stdout="")

        def wait(*_args: object, **kwargs: object) -> str:
            note = kwargs.get("note")
            if isinstance(note, dict):
                note["before"] = "boot-old"
            return "boot-new"

        original = steps._wait_for_reboot
        steps._wait_for_reboot = wait
        try:
            with tempfile.TemporaryDirectory() as tmp:
                self._env_ready(tmp)
                os.environ["W3_BATTERY"] = "descendant-b1"
                result = steps.execute_enterprise_rows(
                    runner,
                    keygen=self._keygen,
                    ssh_runner=ssh,
                    checker=lambda _path: {"seal_sha256": SEAL},
                )
        finally:
            steps._wait_for_reboot = original
        self.assertEqual(result["status"], "DESCENDANT_B1")
        self.assertEqual(result["boot_id"], "boot-new")
        enterprise_pulls = [item for item in pulled if "enterprise-pe-rows.json" in item]
        redteam_pulls = [item for item in pulled if "redteam-rows.json" in item]
        self.assertTrue(enterprise_pulls)
        self.assertTrue(all("/var/lib/vantio-lab/enterprise-pe-rows.json" in item for item in enterprise_pulls))
        self.assertTrue(redteam_pulls)
        self.assertTrue(all("/var/lib/vantio-lab/redteam-rows.json" in item for item in redteam_pulls))
        self.assertEqual(result["warnings"], ["post_scoped_banner=scoped_banner_without_ledger_line"])
        self.assertEqual(
            result["b1_start_window"],
            {"pre": {"status": "none_missing", "delayed": 0, "dropped": 0}, "post": {"status": "delayed", "delayed": 1, "dropped": 0}},
        )
        self.assertNotIn("reason", result)

    def test_b1_warning_helpers_never_grade(self) -> None:
        self.assertEqual(steps._b1_scoped_banner_warnings(None), [])
        self.assertEqual(steps._b1_scoped_banner_warnings({"pre": {"scoped_banner": "scoped"}}), [])
        self.assertEqual(
            steps._b1_scoped_banner_warnings({"pre": {"scoped_banner": "missing"}, "post": {"descendant_pass": False}}),
            ["pre_scoped_banner=missing"],
        )
        self.assertEqual(steps._b1_start_window({"post": {"start_window_rows": "x"}}), {})
        source = Path(steps.__file__).read_text(encoding="utf-8")
        block = source.split('if battery == "descendant-b1":\n                # Informational only', 1)[1]
        block = block.split("redteam_local =", 1)[0]
        self.assertNotIn('"status"', block)
        self.assertNotIn('"reason"', block)
        self.assertNotIn("GuardAbort", block)

    def test_lsm_guard_reads_the_durable_record_after_tmp_is_wiped(self) -> None:
        runner = FakeAws()
        runner.dry_run = "allowed"
        pulled: list[str] = []

        def ssh(args: list[str], script: str) -> subprocess.CompletedProcess[str]:
            joined = " ".join(args)
            if args[0] == "scp" and "enterprise-pe-rows.json" in joined:
                pulled.append(joined)
                if "/tmp/enterprise-pe-rows.json" in joined:
                    raise AssertionError("lsm-guard pulled /tmp")
                Path(args[-1]).write_text(
                    json.dumps(
                        {
                            "battery": "lsm-guard",
                            "boot_id": "boot-new",
                            "host_result": "GUARD_PROVED",
                            "reboot_requested": True,
                        }
                    ),
                    encoding="utf-8",
                )
            if args[0] == "ssh" and args[-1] == "/proc/sys/kernel/random/boot_id":
                return completed(stdout="boot-new\n")
            return completed(stdout="")

        with tempfile.TemporaryDirectory() as tmp:
            self._env_ready(tmp)
            os.environ["W3_BATTERY"] = "lsm-guard"
            result = steps.execute_enterprise_rows(
                runner,
                keygen=self._keygen,
                ssh_runner=ssh,
                checker=lambda _path: {"seal_sha256": SEAL},
            )
        self.assertEqual(result["status"], "PHASE2")
        self.assertEqual(result["boot_id"], "boot-new")
        self.assertTrue(pulled)
        self.assertTrue(all("/var/lib/vantio-lab/enterprise-pe-rows.json" in item for item in pulled))

    def test_reboot_check_fails_when_the_new_boot_has_no_cmdline(self) -> None:
        runner = FakeAws()
        runner.dry_run = "allowed"

        def keygen(directory: Path) -> tuple[Path, str]:
            private = directory / "lab-ed25519"
            private.write_text("key\n", encoding="utf-8")
            return private, "ssh-ed25519 AAAATEST vantio-lab"

        def ssh(args: list[str], script: str) -> subprocess.CompletedProcess[str]:
            joined = " ".join(args)
            if args[0] == "scp" and "enterprise-pe-rows.json" in joined:
                Path(args[-1]).write_text(
                    json.dumps(
                        {
                            "battery": "reboot-check",
                            "boot_id": "boot-old",
                            "reboot_requested": True,
                            "unit": "vantio-lab-lsm-reboot",
                        }
                    ),
                    encoding="utf-8",
                )
            if args[0] == "ssh" and args[-1] == "/proc/sys/kernel/random/boot_id":
                return completed(stdout="boot-new\n")
            if args[0] == "ssh" and args[-1] == "/sys/kernel/security/lsm":
                return completed(stdout="lockdown,capability,apparmor\n")
            if args[0] == "ssh" and args[-1] == "/sys/kernel/security/lockdown":
                return completed(stdout="[none] integrity confidentiality\n")
            return completed(stdout="")

        def wait(*_args: object, **kwargs: object) -> str:
            note = kwargs.get("note")
            if isinstance(note, dict):
                note["before"] = "boot-old"
            return "boot-new"

        original = steps._wait_for_reboot
        steps._wait_for_reboot = wait
        try:
            with tempfile.TemporaryDirectory() as tmp:
                self._env_ready(tmp)
                os.environ["W3_BATTERY"] = "reboot-check"
                with self.assertRaises(lab.GuardAbort) as caught:
                    steps.execute_enterprise_rows(
                        runner,
                        keygen=keygen,
                        ssh_runner=ssh,
                        checker=lambda _path: {"seal_sha256": SEAL},
                    )
        finally:
            steps._wait_for_reboot = original
        self.assertEqual(caught.exception.reason, "post_boot_incomplete")
        self.assertFalse(any("get-console-output" in call for call in runner.calls))

    def test_reboot_check_fails_when_the_new_boot_is_still_stock(self) -> None:
        runner = FakeAws()
        runner.dry_run = "allowed"
        runner.console = b"stock console\n"
        stock_lsm = "lockdown,capability,landlock,yama,apparmor,ima,evm"
        stock_cmdline = (
            "BOOT_IMAGE=/vmlinuz-7.0.0-1013-aws "
            "root=PARTUUID=1feb5770-cc6a-4240-8c18-3b802f140518 "
            "ro console=tty1 console=ttyS0 nvme_core.io_timeout=4294967295 panic=-1"
        )

        def ssh(args: list[str], script: str) -> subprocess.CompletedProcess[str]:
            joined = " ".join(args)
            if args[0] == "scp" and "enterprise-pe-rows.json" in joined:
                Path(args[-1]).write_text(
                    json.dumps(
                        {
                            "battery": "reboot-check",
                            "boot_id": "boot-old",
                            "reboot_requested": True,
                            "unit": "vantio-lab-lsm-reboot",
                        }
                    ),
                    encoding="utf-8",
                )
            if args[0] == "ssh" and args[-1] == "/proc/sys/kernel/random/boot_id":
                return completed(stdout="boot-new\n")
            if args[0] == "ssh" and args[-1] == "/proc/cmdline":
                return completed(stdout=stock_cmdline + "\n")
            if args[0] == "ssh" and args[-1] == "/sys/kernel/security/lsm":
                return completed(stdout=stock_lsm + "\n")
            if args[0] == "ssh" and args[-1] == "/sys/kernel/security/lockdown":
                return completed(stdout="[none] integrity confidentiality\n")
            return completed(stdout="")

        def wait(*_args: object, **kwargs: object) -> str:
            note = kwargs.get("note")
            if isinstance(note, dict):
                note["before"] = "boot-old"
            return "boot-new"

        original = steps._wait_for_reboot
        steps._wait_for_reboot = wait
        try:
            with tempfile.TemporaryDirectory() as tmp:
                self._env_ready(tmp)
                os.environ["W3_BATTERY"] = "reboot-check"
                with self.assertRaises(lab.GuardAbort) as caught:
                    steps.execute_enterprise_rows(
                        runner,
                        keygen=self._keygen,
                        ssh_runner=ssh,
                        checker=lambda _path: {"seal_sha256": SEAL},
                    )
                body = json.loads(Path(os.environ["EVIDENCE_PATH"]).read_text(encoding="utf-8"))
        finally:
            steps._wait_for_reboot = original
        self.assertEqual(caught.exception.reason, "bpf_still_absent")
        self.assertEqual(body["status"], "FAILED")
        self.assertNotEqual(body["status"], "REBOOT_CHECKED")
        self.assertEqual(body["post_boot"]["lsm"], stock_lsm)
        self.assertEqual(body["post_boot"]["cmdline"], stock_cmdline)
        self.assertFalse(any("get-console-output" in call for call in runner.calls))

    def test_reboot_check_fails_when_the_serial_log_is_empty(self) -> None:
        runner = FakeAws()
        runner.dry_run = "allowed"
        runner.console = b""

        def keygen(directory: Path) -> tuple[Path, str]:
            private = directory / "lab-ed25519"
            private.write_text("key\n", encoding="utf-8")
            return private, "ssh-ed25519 AAAATEST vantio-lab"

        def ssh(args: list[str], script: str) -> subprocess.CompletedProcess[str]:
            joined = " ".join(args)
            if args[0] == "scp" and "enterprise-pe-rows.json" in joined:
                Path(args[-1]).write_text(
                    json.dumps(
                        {
                            "battery": "reboot-check",
                            "boot_id": "boot-old",
                            "reboot_requested": True,
                            "unit": "vantio-lab-lsm-reboot",
                        }
                    ),
                    encoding="utf-8",
                )
            if args[0] == "ssh" and args[-1] == "/proc/sys/kernel/random/boot_id":
                return completed(stdout="boot-new\n")
            if args[0] == "ssh" and args[-1] == "/proc/cmdline":
                return completed(stdout="root=PARTUUID ro console=ttyS0 lsm=lockdown,capability,apparmor,bpf\n")
            if args[0] == "ssh" and args[-1] == "/sys/kernel/security/lsm":
                return completed(stdout="lockdown,capability,apparmor,bpf\n")
            if args[0] == "ssh" and args[-1] == "/sys/kernel/security/lockdown":
                return completed(stdout="[none] integrity confidentiality\n")
            return completed(stdout="")

        def wait(*_args: object, **kwargs: object) -> str:
            note = kwargs.get("note")
            if isinstance(note, dict):
                note["before"] = "boot-old"
            return "boot-new"

        original = steps._wait_for_reboot
        steps._wait_for_reboot = wait
        try:
            with tempfile.TemporaryDirectory() as tmp:
                self._env_ready(tmp)
                os.environ["W3_BATTERY"] = "reboot-check"
                with self.assertRaises(lab.GuardAbort) as caught:
                    steps.execute_enterprise_rows(
                        runner,
                        keygen=keygen,
                        ssh_runner=ssh,
                        checker=lambda _path: {"seal_sha256": SEAL},
                    )
        finally:
            steps._wait_for_reboot = original
        self.assertEqual(caught.exception.reason, "console_missing")


# A 2F pass row names when the loader died and what the pass claims.
TAMPER_CLAIM = {
    "kill_timing": "after_map_swap",
    "claim_scope": "kill after deny-attr map swap; ready-to-swap gap not covered (VAN-45)",
}


class PhaseBatteryVerdictTests(unittest.TestCase):
    """A phase battery is graded from its rows, not from a green guest exit."""

    def setUp(self) -> None:
        self._env = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)

    def test_each_battery_passes_only_on_its_own_result(self) -> None:
        passing = {
            "r15-container-exit": "RECORDED",
            "2d-crash-recovery": "PASS",
            "2e-performance": "PASS",
            "2f-tamper": "PASS",
            "2g-distro": "PASS",
            "lsm-guard": "GUARD_PROVED",
        }
        for battery, result in passing.items():
            claim = TAMPER_CLAIM if battery == "2f-tamper" else {}
            verdict = steps.phase_battery_verdict(battery, {"battery": battery, "host_result": result, **claim})
            self.assertTrue(verdict["pass"], battery)
            self.assertEqual(verdict["reason"], "battery_pass")
        for result in ("LSM_ALREADY_ACTIVE", "LSM_ENABLED"):
            self.assertTrue(steps.phase_battery_verdict("lsm-guard", {"battery": "lsm-guard", "host_result": result})["pass"])
        upgraded = steps.phase_battery_verdict(
            "2c-upgrade-rollback",
            {"battery": "2c-upgrade-rollback", "host_result": "RECORDED", "upgrade_pass": True},
        )
        self.assertTrue(upgraded["pass"])
        # A pass word that belongs to another battery is not a pass.
        self.assertFalse(steps.phase_battery_verdict("2f-tamper", {"battery": "2f-tamper", "host_result": "RECORDED"})["pass"])
        self.assertFalse(
            steps.phase_battery_verdict("r15-container-exit", {"battery": "r15-container-exit", "host_result": "PASS"})["pass"]
        )
        self.assertFalse(steps.phase_battery_verdict("lsm-guard", {"battery": "lsm-guard", "host_result": "PASS"})["pass"])

    def test_fail_not_graded_and_hold_are_named(self) -> None:
        cases = {
            "FAIL": "battery_fail",
            "NOT_GRADED": "battery_not_graded",
            "HOLD": "battery_hold",
            "SOMETHING": "battery_result_unknown",
        }
        for result, reason in cases.items():
            verdict = steps.phase_battery_verdict(
                "2f-tamper",
                {"battery": "2f-tamper", "host_result": result, "reason": "enrolled_egress_timeout"},
            )
            self.assertFalse(verdict["pass"])
            self.assertEqual(verdict["reason"], reason)
            self.assertEqual(verdict["row_reason"], "enrolled_egress_timeout")
        missing = steps.phase_battery_verdict("2d-crash-recovery", None)
        self.assertEqual(missing["reason"], "battery_rows_missing")
        self.assertFalse(missing["pass"])
        no_result = steps.phase_battery_verdict("2d-crash-recovery", {"battery": "2d-crash-recovery"})
        self.assertEqual(no_result["reason"], "battery_result_unknown")

    PASS_ROWS = {
        "r15-container-exit": {"host_result": "RECORDED"},
        "2c-upgrade-rollback": {"host_result": "RECORDED", "upgrade_pass": True},
        "2d-crash-recovery": {"host_result": "PASS"},
        "2e-performance": {"host_result": "PASS"},
        "2f-tamper": {"host_result": "PASS", **TAMPER_CLAIM},
        "2g-distro": {"host_result": "PASS"},
        "lsm-guard": {"host_result": "GUARD_PROVED"},
    }

    def test_no_graded_battery_passes_on_a_non_pass_row(self) -> None:
        """Council: every graded battery x every non-pass shape. A mutant that lets one through dies here."""
        self.assertEqual(set(self.PASS_ROWS), set(steps.PHASE_BATTERY_PASS))
        non_pass = {
            "not_graded": ({"host_result": "NOT_GRADED"}, "battery_not_graded"),
            "hold": ({"host_result": "HOLD"}, "battery_hold"),
            "fail": ({"host_result": "FAIL"}, "battery_fail"),
            "unknown_result": ({"host_result": "MAYBE"}, "battery_result_unknown"),
            "no_result": ({}, "battery_result_unknown"),
        }
        for battery, passing in self.PASS_ROWS.items():
            # The control: this battery's own pass row does pass.
            control = steps.phase_battery_verdict(battery, {"battery": battery, **passing})
            self.assertTrue(control["pass"], battery)
            for label, (shape, reason) in non_pass.items():
                with self.subTest(battery=battery, case=label):
                    row = {"battery": battery, **passing, "reason": "x"}
                    row.pop("host_result")
                    row.update(shape)
                    verdict = steps.phase_battery_verdict(battery, row)
                    self.assertIs(verdict["pass"], False)
                    self.assertEqual(verdict["reason"], reason)
            with self.subTest(battery=battery, case="missing_battery_field"):
                verdict = steps.phase_battery_verdict(battery, dict(passing))
                self.assertIs(verdict["pass"], False)
                self.assertEqual(verdict["reason"], "battery_mismatch")
            for wrong in ("", None, battery.upper(), battery + " "):
                with self.subTest(battery=battery, case=f"battery_field={wrong!r}"):
                    verdict = steps.phase_battery_verdict(battery, {**passing, "battery": wrong})
                    self.assertIs(verdict["pass"], False)
                    self.assertEqual(verdict["reason"], "battery_mismatch")

    def test_2c_record_without_upgrade_pass_is_a_fail(self) -> None:
        verdict = steps.phase_battery_verdict(
            "2c-upgrade-rollback",
            {"battery": "2c-upgrade-rollback", "host_result": "RECORDED", "upgrade_pass": False},
        )
        self.assertFalse(verdict["pass"])
        self.assertEqual(verdict["reason"], "battery_fail")
        failed = steps.phase_battery_verdict(
            "2c-upgrade-rollback",
            {"battery": "2c-upgrade-rollback", "host_result": "FAIL", "reason": "baseline_enforcement"},
        )
        self.assertEqual(failed["reason"], "battery_fail")

    def test_other_battery_rows_and_harness_errors_do_not_pass(self) -> None:
        other = steps.phase_battery_verdict("2f-tamper", {"battery": "2d-crash-recovery", "host_result": "PASS"})
        self.assertEqual(other["reason"], "battery_mismatch")
        self.assertFalse(other["pass"])
        broken = steps.phase_battery_verdict(
            "2f-tamper",
            {"battery": "2f-tamper", "host_result": "PASS", "harness_error": "SystemExit loader 1"},
        )
        self.assertEqual(broken["reason"], "battery_harness_error")
        self.assertFalse(broken["pass"])

    def test_batteries_outside_phase_two_are_not_graded_here(self) -> None:
        for battery in ("soak-hourly", "descendant-b1", "enterprise", "webshell", "reboot-check"):
            self.assertIsNone(steps.phase_battery_verdict(battery, {"host_result": "FAIL"}))

    def test_the_verdict_line_reaches_the_step_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = Path(tmp) / "summary.md"
            os.environ["GITHUB_STEP_SUMMARY"] = str(summary)
            line = steps.report_battery_verdict(
                {"battery": "2f-tamper", "host_result": "NOT_GRADED", "pass": False, "reason": "battery_not_graded", "row_reason": "enrolled_egress_timeout"}
            )
            self.assertIn("BATTERY_VERDICT battery=2f-tamper", line)
            self.assertIn("pass=false", line)
            self.assertEqual(summary.read_text(encoding="utf-8"), line + "\n")

    def test_every_phase_battery_except_soak_has_a_pass_rule(self) -> None:
        source = Path(steps.__file__).read_text(encoding="utf-8")
        block = source.split("phase_batteries = {", 1)[1].split("}", 1)[0]
        listed = {item.strip().strip('",') for item in block.splitlines() if item.strip().strip('",')}
        self.assertEqual(listed - {"soak-hourly"}, set(steps.PHASE_BATTERY_PASS))


class PhaseBatteryRunTests(unittest.TestCase):
    """End to end through arm-enterprise with fake AWS and SSH."""

    def setUp(self) -> None:
        self._env = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)

    def _env_ready(self, tmp: str, battery: str) -> None:
        path = Path(tmp) / "caps.json"
        path.write_text(json.dumps({"ssh_instance_connect": True, "max_life_hours_36": True, "ssm": False}))
        os.environ["W3_LAB_CAPABILITIES"] = str(path)
        os.environ["INSTANCE_ID"] = INSTANCE
        os.environ["SEAL"] = SEAL
        os.environ["PUBLIC_PIN"] = PIN
        os.environ["W3_RUNNER_CIDR"] = "1.1.1.1/32"
        os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "arm.json")
        os.environ["W3_STAMP"] = str(Path(tmp) / "stamp.json")
        os.environ["W3_BUNDLE_DIR"] = str(Path(tmp) / "bundle")
        os.environ["W3_ROWS_PATH"] = str(Path(tmp) / "rows.json")
        os.environ["W3_REDTEAM_PATH"] = str(Path(tmp) / "redteam.json")
        os.environ["W3_BATTERY"] = battery
        os.environ.pop("GITHUB_STEP_SUMMARY", None)
        Path(os.environ["W3_BUNDLE_DIR"]).mkdir()

    def _keygen(self, directory: Path) -> tuple[Path, str]:
        private = directory / "lab-ed25519"
        private.write_text("key\n", encoding="utf-8")
        return private, "ssh-ed25519 AAAATEST vantio-lab"

    def _run(self, battery: str, rows: dict, *, guest_rc: int = 0, stale_redteam: bool = False):
        runner = FakeAws()
        runner.dry_run = "allowed"
        pulled: list[str] = []

        def ssh(args: list[str], script: str) -> subprocess.CompletedProcess[str]:
            joined = " ".join(args)
            if args[0] == "scp" and "redteam-rows.json" in joined:
                pulled.append(joined)
                Path(args[-1]).write_text(json.dumps({"attempts": [{"row": "stale-b1"}]}), encoding="utf-8")
            if args[0] == "scp" and "enterprise-pe-rows.json" in joined:
                Path(args[-1]).write_text(json.dumps(rows), encoding="utf-8")
            if args[0] == "ssh" and args[-1] == "/proc/sys/kernel/random/boot_id":
                return completed(stdout="boot-new\n")
            if args[0] == "ssh" and "enterprise-rows.sh" in joined and battery in joined:
                return completed(stdout="", code=guest_rc)
            return completed(stdout="")

        tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        self._env_ready(tmp, battery)
        redteam = Path(os.environ["W3_REDTEAM_PATH"])
        if stale_redteam:
            redteam.write_text('{"attempts": []}\n', encoding="utf-8")
            redteam.with_name(redteam.name + ".sha256").write_text("x  redteam.json\n", encoding="utf-8")
        error = None
        result = None
        try:
            result = steps.execute_enterprise_rows(
                runner,
                keygen=self._keygen,
                ssh_runner=ssh,
                checker=lambda _path: {"seal_sha256": SEAL},
            )
        except lab.GuardAbort as exc:
            error = exc
        evidence = json.loads(Path(os.environ["EVIDENCE_PATH"]).read_text(encoding="utf-8"))
        return result, error, evidence, pulled, Path(tmp)

    def test_a_graded_fail_with_guest_exit_zero_fails_the_arm(self) -> None:
        rows = {"battery": "2d-crash-recovery", "boot_id": "boot-new", "host_result": "FAIL", "reason": "no_new_deny_after_restart"}
        result, error, evidence, _pulled, tmp = self._run("2d-crash-recovery", rows)
        self.assertIsNone(result)
        self.assertIsNotNone(error)
        self.assertEqual(error.reason, "battery_fail")
        self.assertEqual(evidence["status"], "FAILED")
        self.assertEqual(evidence["reason"], "battery_fail")
        self.assertEqual(evidence["guest_rc"], 0)
        self.assertEqual(evidence["battery_verdict"]["row_reason"], "no_new_deny_after_restart")
        self.assertFalse(evidence["battery_verdict"]["pass"])
        # The rows were stored before the arm failed, so they still upload.
        self.assertTrue((tmp / "rows.json").is_file())
        self.assertIn("rows_sha256", evidence)

    def test_not_graded_keeps_the_guest_exit_code_and_records_the_verdict(self) -> None:
        rows = {"battery": "2f-tamper", "boot_id": "boot-new", "host_result": "NOT_GRADED", "reason": "enrolled_egress_timeout"}
        _result, error, evidence, _pulled, _tmp = self._run("2f-tamper", rows, guest_rc=2)
        self.assertIsNotNone(error)
        self.assertEqual(evidence["guest_rc"], 2)
        self.assertEqual(evidence["status"], "FAILED")
        self.assertEqual(evidence["battery_verdict"]["reason"], "battery_not_graded")
        self.assertEqual(evidence["battery_verdict"]["host_result"], "NOT_GRADED")

    def test_a_pass_is_still_phase2(self) -> None:
        rows = {"battery": "2f-tamper", "boot_id": "boot-new", "host_result": "PASS", "reason": "post_kill_holds", **TAMPER_CLAIM}
        result, error, evidence, _pulled, _tmp = self._run("2f-tamper", rows)
        self.assertIsNone(error)
        self.assertEqual(result["status"], "PHASE2")
        self.assertTrue(evidence["battery_verdict"]["pass"])
        self.assertNotIn("reason", evidence)

    def test_a_2f_pass_without_claim_fields_fails_the_arm(self) -> None:
        rows = {"battery": "2f-tamper", "boot_id": "boot-new", "host_result": "PASS", "kill_timing": "not_killed"}
        result, error, evidence, _pulled, _tmp = self._run("2f-tamper", rows)
        self.assertIsNone(result)
        self.assertIsNotNone(error)
        self.assertEqual(error.reason, "claim_fields_missing")
        self.assertEqual(evidence["status"], "FAILED")
        self.assertFalse(evidence["battery_verdict"]["pass"])
        self.assertEqual(evidence["battery_verdict"]["reason"], "claim_fields_missing")

    def test_non_b1_battery_never_pulls_or_keeps_redteam_rows(self) -> None:
        rows = {"battery": "2f-tamper", "boot_id": "boot-new", "host_result": "PASS", **TAMPER_CLAIM}
        result, _error, evidence, pulled, tmp = self._run("2f-tamper", rows, stale_redteam=True)
        self.assertEqual(pulled, [])
        self.assertFalse((tmp / "redteam.json").exists())
        self.assertFalse((tmp / "redteam.json.sha256").exists())
        self.assertNotIn("redteam_rows_sha256", evidence)
        self.assertEqual(result["redteam_rows"], "not_collected_for_battery")

    def test_redteam_pull_is_inside_the_b1_branch(self) -> None:
        source = Path(steps.__file__).read_text(encoding="utf-8")
        start = source.index('redteam_local = Path(os.environ.get("W3_REDTEAM_PATH"')
        block = source[start: source.index("live_boot = _remote_boot_id(remote)", start)]
        b1 = block.index('if battery == "descendant-b1":')
        self.assertGreater(block.index("REDTEAM_ROWS_REMOTE"), b1)
        self.assertEqual(block.count("REDTEAM_ROWS_REMOTE"), 1)
        self.assertNotIn("elif pulled_redteam", block)


class RebootWaitTests(unittest.TestCase):
    def test_ssh_that_stays_up_on_the_same_boot_uses_the_observe_budget(self) -> None:
        now = {"t": 0.0}

        def clock() -> float:
            return now["t"]

        def pause(seconds: float) -> None:
            now["t"] += seconds

        def remote(argv: list[str], script: str) -> subprocess.CompletedProcess[str]:
            if argv[:1] == ["cat"]:
                return completed(stdout="boot-a\n")
            return completed(stdout="")

        with self.assertRaises(lab.GuardAbort) as caught:
            steps._wait_for_reboot(
                lambda _args: completed(payload={}),
                INSTANCE,
                remote,
                ["aws", "sts", "get-caller-identity"],
                quiet_budget=0,
                return_budget=10,
                clock=clock,
                pause=pause,
                describe=lambda _runner, _instance_id: {"State": {"Name": "running"}},
            )
        self.assertEqual(caught.exception.reason, "reboot_timeout")
        self.assertEqual(now["t"], 10)

    def test_the_quiet_window_does_not_open_ssh(self) -> None:
        now = {"t": 0.0}
        calls: list[tuple[float, str]] = []

        def clock() -> float:
            return now["t"]

        def pause(seconds: float) -> None:
            now["t"] += seconds

        def remote(argv: list[str], script: str) -> subprocess.CompletedProcess[str]:
            calls.append((now["t"], argv[0]))
            if argv[:1] == ["cat"]:
                return completed(stdout="boot-b\n" if now["t"] >= 10 else "boot-a\n")
            return completed(stdout="")

        def release() -> None:
            calls.append((now["t"], "release"))

        found = steps._wait_for_reboot(
            lambda _args: completed(payload={}),
            INSTANCE,
            remote,
            ["aws", "sts", "get-caller-identity"],
            quiet_budget=10,
            return_budget=10,
            clock=clock,
            pause=pause,
            describe=lambda _runner, _instance_id: {"State": {"Name": "running"}},
            release=release,
        )
        self.assertEqual(found, "boot-b")
        self.assertEqual(calls[0], (0.0, "cat"))
        self.assertEqual(calls[1], (0.0, "release"))
        self.assertFalse(any(name != "release" and 0 < stamp < 10 for stamp, name in calls))
        self.assertGreaterEqual(now["t"], 10)

    def test_a_changed_boot_id_ends_the_wait(self) -> None:
        now = {"t": 0.0}
        seen = {"n": 0}

        def clock() -> float:
            return now["t"]

        def pause(seconds: float) -> None:
            now["t"] += seconds

        def remote(argv: list[str], script: str) -> subprocess.CompletedProcess[str]:
            if argv[:1] == ["cat"]:
                seen["n"] += 1
                return completed(stdout="boot-b\n" if seen["n"] >= 2 else "boot-a\n")
            return completed(stdout="")

        found = steps._wait_for_reboot(
            lambda _args: completed(payload={}),
            INSTANCE,
            remote,
            ["aws", "sts", "get-caller-identity"],
            quiet_budget=0,
            return_budget=30,
            clock=clock,
            pause=pause,
            describe=lambda _runner, _instance_id: {"State": {"Name": "running"}},
        )
        self.assertEqual(found, "boot-b")
        self.assertEqual(now["t"], 0)

    def test_return_budget_starts_after_the_quiet_window(self) -> None:
        now = {"t": 0.0}

        def clock() -> float:
            return now["t"]

        def pause(seconds: float) -> None:
            now["t"] += seconds

        def remote(argv: list[str], script: str) -> subprocess.CompletedProcess[str]:
            if argv[:1] == ["cat"]:
                return completed(stdout="boot-a\n")
            return completed(code=255, stderr="Connection refused")

        with self.assertRaises(lab.GuardAbort) as caught:
            steps._wait_for_reboot(
                lambda _args: completed(payload={}),
                INSTANCE,
                remote,
                ["aws", "sts", "get-caller-identity"],
                quiet_budget=0,
                return_budget=30,
                clock=clock,
                pause=pause,
                describe=lambda _runner, _instance_id: {"State": {"Name": "stopped"}},
            )
        self.assertEqual(caught.exception.reason, "reboot_timeout")
        self.assertGreaterEqual(now["t"], 30)
        self.assertLess(now["t"], 40)

    def test_ssh_returning_on_the_same_boot_is_not_a_reboot(self) -> None:
        now = {"t": 0.0}
        down = {"value": True}

        def clock() -> float:
            return now["t"]

        def pause(seconds: float) -> None:
            now["t"] += seconds

        def remote(argv: list[str], script: str) -> subprocess.CompletedProcess[str]:
            if argv == ["true"] and down["value"]:
                down["value"] = False
                return completed(code=255, stderr="Connection refused")
            if argv[:1] == ["cat"]:
                return completed(stdout="boot-a\n")
            return completed(stdout="")

        with self.assertRaises(lab.GuardAbort) as caught:
            steps._wait_for_reboot(
                lambda _args: completed(payload={}),
                INSTANCE,
                remote,
                ["aws", "sts", "get-caller-identity"],
                quiet_budget=0,
                return_budget=20,
                clock=clock,
                pause=pause,
                describe=lambda _runner, _instance_id: {"State": {"Name": "running"}},
            )
        self.assertEqual(caught.exception.reason, "reboot_timeout")
        self.assertGreaterEqual(now["t"], 20)
        self.assertLess(now["t"], 30)

    def test_waiter_does_not_reach_for_a_manager_session(self) -> None:
        import inspect

        source = inspect.getsource(steps._wait_for_reboot).lower()
        self.assertNotIn("send-command", source)
        self.assertNotIn("start-session", source)
        self.assertNotIn("ssm", source)

    def test_rows_from_another_boot_are_refused(self) -> None:
        self.assertTrue(steps._rows_disagree_with_boot({"boot_id": "old-boot"}, "new-boot"))
        self.assertFalse(steps._rows_disagree_with_boot({"pre": {"boot_id": "old-boot"}, "post": {"boot_id": "new-boot"}}, "new-boot"))
        self.assertFalse(steps._rows_disagree_with_boot({}, "new-boot"))
        self.assertEqual(
            steps._guest_failure_reason({"removal": {"verified_removed": False}}),
            "programs_not_removed",
        )
        self.assertEqual(
            steps._guest_failure_reason(
                {"removal": {"verified_removed": True}, "uninstall_tail": "UNINSTALL_NOT_VERIFIED rc=1\n"}
            ),
            "uninstall_not_verified",
        )
        self.assertEqual(steps._guest_failure_reason({"removal": {"verified_removed": True}}), "guest")
        self.assertEqual(
            steps._guest_failure_reason({"reason": "reboot_script_missing"}),
            "reboot_script_missing",
        )


class ProductUninstallCensusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(ROOT / "scripts" / "aws" / "lab-guests"))

    def test_the_shell_does_not_detach_before_the_product_uninstall(self) -> None:
        text = (ROOT / "scripts/aws/lab-guests/enterprise-rows.sh").read_text(encoding="utf-8")
        self.assertNotIn("release_loaded_lab_programs", text)
        self.assertNotIn("release_lab_programs.py", text)
        self.assertNotIn("bpftool cgroup detach", text)
        final = text[text.index("esac\nset +e") :]
        self.assertLess(final.index("ensure_working_bpftool"), final.index('python3 "$stage/guest_rows.py"'))
        self.assertLess(final.index('python3 "$stage/guest_rows.py"'), final.index('authorized_uninstall "$image" no 0'))
        self.assertLess(
            final.index('authorized_uninstall "$image" no 0'),
            final.index("product_uninstall_census.py"),
        )
        source = (ROOT / "scripts/aws/w3_lab_steps.py").read_text(encoding="utf-8")
        self.assertEqual(source.count('copy_to(script_path.with_name("product_uninstall_census.py")'), 1)
        self.assertNotIn("release_lab_programs.py", source)
        arm = (ROOT / ".github/workflows/w3-lab-auto-arm.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/aws/lab-guests/product_uninstall_census.py", arm)
        census = (ROOT / "scripts/aws/lab-guests/product_uninstall_census.py").read_text(encoding="utf-8")
        self.assertNotIn("cgroup detach", census)
        self.assertNotIn(".unlink(", census)
        self.assertIn("write_replacing", census)

    def test_a_remaining_engine_program_is_not_removed(self) -> None:
        from product_uninstall_census import (
            bpffs_vantio_paths,
            classify_bpffs,
            finish_code,
            loaded_programs,
            regression_still_holds,
        )

        self.assertEqual(
            loaded_programs([{"name": "cgroup_skb_egre"}, {"name": "sshd"}], ""),
            ["cgroup_skb_egress_enforce"],
        )
        self.assertEqual(
            loaded_programs([{"name": "sshd", "pinned": ["/sys/fs/bpf/vantio_maps"]}], ""),
            ["/sys/fs/bpf/vantio_maps"],
        )
        self.assertEqual(bpffs_vantio_paths("/sys/fs/bpf/vantio_prog\n/sys/fs/bpf/other\n"), ["/sys/fs/bpf/vantio_prog"])
        self.assertEqual(classify_bpffs(mounted=False, find_rc=1, text="/sys/fs/bpf/vantio_prog"), [])
        self.assertEqual(classify_bpffs(mounted=True, find_rc=1, text=""), ["find_failed"])
        digest = "sha256:5d7095cb4fa029c388cce558e95336fd73e8e65930a7b58a31976b4d96163848"
        secret = "/var/lib/vantio-pe-clean-host/d/secret"
        rows = {
            "grant_loader": {
                "rc": 0,
                "audit": True,
                "scoped": False,
                "path_deny": False,
                "path_observe": True,
                "phantom_deny": False,
            },
            "grant_probe": {"nobody_errno": 0},
            "grant_allow_event": {
                "ActionTaken": "POLICY_ALLOW",
                "EventType": "POLICY_ALLOW",
                "Uid": 65534,
                "open_result": "open_ok",
                "Payload": secret,
                "PolicyRuleMatched": f"POLICY_ALLOW:{secret}",
                "policy_digest": digest,
            },
            "unchanged": {
                "unsigned_changed": False,
                "replay_changed": False,
                "conflict_changed": False,
                "conflict_reason": "VERSION_CONFLICT",
                "generation": 2,
                "generation_before": 2,
            },
            "unchanged_probe": {"nobody_errno": 0},
            "freeze": {"widen_changed": False, "widen_reason": "FROZEN"},
            "unreachable": {"changed": False, "reason": "ENTERPRISE_UNREACHABLE"},
            "revoke": {
                "policy_digest": digest,
                "probe": {"nobody_errno": 13},
                "block_event": {
                    "ActionTaken": "DENIED",
                    "EventType": "SYSCALL_OPENAT",
                    "Uid": 65534,
                    "BytesSevered": 0,
                    "Payload": secret,
                    "PolicyRuleMatched": f"ENFORCE_DENIED:{secret}",
                    "policy_digest": digest,
                },
            },
        }
        self.assertTrue(regression_still_holds(rows))
        self.assertEqual(finish_code(verified_removed=True, guest_rc=1, rows=rows), 0)
        self.assertEqual(finish_code(verified_removed=False, guest_rc=1, rows=rows), 1)
        broken = json.loads(json.dumps(rows))
        broken["grant_loader"]["rc"] = 1
        self.assertEqual(finish_code(verified_removed=True, guest_rc=1, rows=broken), 1)
        unlabeled = json.loads(json.dumps(rows))
        unlabeled["grant_allow_event"].pop("EventType")
        self.assertEqual(finish_code(verified_removed=True, guest_rc=1, rows=unlabeled), 1)



class TamperClaimScopeTests(unittest.TestCase):
    """Council #364: every 2F verdict prints the kill timing and, when graded, the claim scope."""

    SCOPE = "kill after deny-attr map swap; ready-to-swap gap not covered (VAN-45)"

    def _line(self, body: dict) -> tuple[dict, str]:
        verdict = steps.phase_battery_verdict("2f-tamper", body)
        saved = os.environ.pop("GITHUB_STEP_SUMMARY", None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                summary = Path(tmp) / "summary.md"
                os.environ["GITHUB_STEP_SUMMARY"] = str(summary)
                line = steps.report_battery_verdict(verdict)
                self.assertEqual(summary.read_text(encoding="utf-8"), line + "\n")
        finally:
            os.environ.pop("GITHUB_STEP_SUMMARY", None)
            if saved is not None:
                os.environ["GITHUB_STEP_SUMMARY"] = saved
        return verdict, line

    def test_graded_2f_prints_timing_and_scope(self) -> None:
        for result in ("PASS", "FAIL", "HOLD"):
            with self.subTest(result=result):
                verdict, line = self._line(
                    {"battery": "2f-tamper", "host_result": result, "kill_timing": "after_map_swap", "claim_scope": self.SCOPE}
                )
                self.assertEqual(verdict["kill_timing"], "after_map_swap")
                self.assertEqual(verdict["claim_scope"], self.SCOPE)
                self.assertTrue(line.startswith("BATTERY_VERDICT battery=2f-tamper "))
                self.assertIn(f"host_result={result}", line)
                self.assertTrue(line.endswith(f' kill_timing=after_map_swap claim_scope="{self.SCOPE}"'), line)

    def test_refused_2f_prints_timing_and_a_dash_for_scope(self) -> None:
        verdict, line = self._line(
            {"battery": "2f-tamper", "host_result": "NOT_GRADED", "reason": "map_swap_timeout", "kill_timing": "after_map_swap"}
        )
        self.assertFalse(verdict["pass"])
        self.assertIsNone(verdict["claim_scope"])
        self.assertIn("row_reason=map_swap_timeout", line)
        self.assertTrue(line.endswith(' kill_timing=after_map_swap claim_scope="-"'), line)

    def test_missing_fields_print_as_dashes(self) -> None:
        verdict, line = self._line({"battery": "2f-tamper", "host_result": "PASS"})
        self.assertFalse(verdict["pass"])
        self.assertEqual(verdict["reason"], "claim_fields_missing")
        self.assertTrue(line.endswith(' kill_timing=- claim_scope="-"'), line)
        mismatch, line = self._line({"battery": "2d-crash-recovery", "host_result": "PASS", "kill_timing": "after_map_swap"})
        self.assertEqual(mismatch["reason"], "battery_mismatch")
        self.assertIn("kill_timing=after_map_swap", line)
        odd, line = self._line(
            {"battery": "2f-tamper", "host_result": "PASS", "kill_timing": "after\nmap swap", "claim_scope": 'a "b"\nc'}
        )
        self.assertEqual(line.count("\n"), 0)
        self.assertTrue(line.endswith(" kill_timing=after map swap claim_scope=\"a 'b' c\""), line)
        self.assertFalse(odd["pass"])

    def test_2f_pass_needs_kill_timing_and_claim_scope(self) -> None:
        good = {"battery": "2f-tamper", "host_result": "PASS", "kill_timing": "after_map_swap", "claim_scope": self.SCOPE}
        verdict = steps.phase_battery_verdict("2f-tamper", good)
        self.assertTrue(verdict["pass"])
        self.assertEqual(verdict["reason"], "battery_pass")
        self.assertTrue(steps.phase_battery_verdict("2f-tamper", dict(good, claim_scope="x"))["pass"])
        bad = {
            "no_timing": {"kill_timing": None},
            "not_killed": {"kill_timing": "not_killed"},
            "timing_case": {"kill_timing": "AFTER_MAP_SWAP"},
            "timing_padded": {"kill_timing": " after_map_swap"},
            "no_scope": {"claim_scope": None},
            "empty_scope": {"claim_scope": ""},
            "blank_scope": {"claim_scope": " \t\n"},
            "scope_not_str": {"claim_scope": 7},
        }
        for label, change in bad.items():
            with self.subTest(label=label):
                verdict, line = self._line(dict(good, **change))
                self.assertFalse(verdict["pass"])
                self.assertEqual(verdict["reason"], "claim_fields_missing")
                self.assertEqual(verdict["reason"], steps.TAMPER_CLAIM_FIELDS_MISSING)
                self.assertEqual(verdict["host_result"], "PASS")
                self.assertIn("pass=false reason=claim_fields_missing", line)
        for key in ("kill_timing", "claim_scope"):
            with self.subTest(dropped=key):
                body = dict(good)
                del body[key]
                self.assertEqual(steps.phase_battery_verdict("2f-tamper", body)["reason"], "claim_fields_missing")
        # A graded FAIL or HOLD keeps its own reason; the claim check guards only a pass.
        for result, reason in (("FAIL", "battery_fail"), ("HOLD", "battery_hold"), ("NOT_GRADED", "battery_not_graded")):
            with self.subTest(result=result):
                self.assertEqual(steps.phase_battery_verdict("2f-tamper", {"battery": "2f-tamper", "host_result": result})["reason"], reason)
        # Other batteries pass without the 2F fields.
        self.assertTrue(steps.phase_battery_verdict("2d-crash-recovery", {"battery": "2d-crash-recovery", "host_result": "PASS"})["pass"])

    def test_other_batteries_do_not_print_2f_fields(self) -> None:
        verdict = steps.phase_battery_verdict(
            "2d-crash-recovery", {"battery": "2d-crash-recovery", "host_result": "PASS", "kill_timing": "after_map_swap"}
        )
        self.assertNotIn("kill_timing", verdict)
        saved = os.environ.pop("GITHUB_STEP_SUMMARY", None)
        try:
            line = steps.report_battery_verdict(verdict)
        finally:
            if saved is not None:
                os.environ["GITHUB_STEP_SUMMARY"] = saved
        self.assertNotIn("kill_timing", line)
        self.assertNotIn("claim_scope", line)

    def test_host_constants_match_what_the_report_expects(self) -> None:
        grade_text = Path(steps.__file__).resolve().parent.joinpath("lab-guests", "phase2_grade.py").read_text(encoding="utf-8")
        self.assertIn(f'CLAIM_SCOPE_2F = "{self.SCOPE}"', grade_text)
        self.assertIn('KILL_TIMING_AFTER_MAP_SWAP = "after_map_swap"', grade_text)
        self.assertIn(f'KILL_TIMING_AFTER_MAP_SWAP = "{steps.TAMPER_KILL_TIMING}"', grade_text)
        self.assertIn(f'CLAIM_FIELDS_MISSING = "{steps.TAMPER_CLAIM_FIELDS_MISSING}"', grade_text)


if __name__ == "__main__":
    unittest.main()
