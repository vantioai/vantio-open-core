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
        with tempfile.TemporaryDirectory() as tmp:
            cap = Path(tmp) / "caps.json"
            cap.write_text(json.dumps({"max_life_hours_36": False, "ssh_instance_connect": False, "ssm": False}))
            os.environ["W3_LAB_CAPABILITIES"] = str(cap)
            try:
                self.assertEqual(lab.sweeper_action(young, NOW), "skip_life_not_enabled")
                self.assertEqual(lab.sweeper_action(old, NOW), "skip_life_not_enabled")
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
            self.assertIn("group: w3-lab-free-ec2", text, name)
            self.assertNotRegex(text, r"(?m)^\s*AWS_ACCESS_KEY_ID:", name)
        arm = (ROOT / ".github/workflows/w3-lab-auto-arm.yml").read_text(encoding="utf-8")
        self.assertIn("close-ssh", arm)
        self.assertIn("if: always()", arm)
        soak = (ROOT / ".github/workflows/w3-lab-auto-long-soak.yml").read_text(encoding="utf-8")
        self.assertIn("default: false", soak)
        self.assertIn("w3-lab-auto-cost-gate.yml@main # oidc-trust", soak)
        self.assertFalse((ROOT / ".github/workflows/w3-lab-auto-enterprise-pe.yml").exists())
        self.assertIn("enterprise_rows:", arm)
        self.assertIn("default: false", arm)
        self.assertIn("W3_LAB_PRIVATE_BUNDLE_TOKEN", arm)
        self.assertIn("w3-lab-auto-arm.yml@refs/heads/main", arm)
        self.assertNotIn("0.0.0.0/0", arm)


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

    def test_real_pins_stay_on_the_policy_allow_seal(self) -> None:
        self.assertEqual(enterprise_bundle.POLICY_ALLOW_SEAL, SEAL)
        self.assertEqual(enterprise_bundle.PUBLIC_INSTALLER_PIN, PIN)
        self.assertEqual(
            enterprise_bundle.TRACKING_2A_SEAL,
            "16c9e5638c169e5fdd3fd7291b3225a809b18abfe464d717c2d31a398d5bda6a",
        )
        self.assertEqual(
            enterprise_bundle.TRUST_BUNDLE_SHA256,
            "2e4a1da7bf44f0bddfc2a3ce3eda007fa6cc1455332f26769bd346fafc297876",
        )


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

    def test_bad_bundle_does_not_call_aws(self) -> None:
        runner = FakeAws()
        with tempfile.TemporaryDirectory() as tmp:
            self._env_ready(tmp)
            os.environ["W3_BUNDLE_DIR"] = str(Path(tmp) / "missing")
            with self.assertRaises(lab.GuardAbort) as caught:
                steps.execute_enterprise_rows(runner)
        self.assertEqual(caught.exception.reason, "bundle_layout")
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

    def test_ssh_failure_redacts_before_it_truncates(self) -> None:
        secret = "-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n-----END OPENSSH PRIVATE KEY-----"
        proc = completed(code=1, stderr=("x" * 400) + secret + "\nPermission denied (publickey)")
        with self.assertRaises(lab.GuardAbort) as caught:
            steps._ssh_failure(proc)
        self.assertNotIn("BEGIN OPENSSH", caught.exception.reason)
        self.assertNotIn("abc", caught.exception.reason)
        self.assertIn("publickey", caught.exception.reason)

    def test_guest_script_parses(self) -> None:
        script = ROOT / "scripts/aws/lab-guests/enterprise-rows.sh"
        completed_run = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        self.assertEqual(completed_run.returncode, 0, completed_run.stderr)


if __name__ == "__main__":
    unittest.main()
