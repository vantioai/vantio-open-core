#!/usr/bin/env python3
"""Guards for unheld w3 lab launch and sweep.

These tests use a fake AWS runner. They do not call AWS.
"""

from __future__ import annotations

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

NOW = datetime(2026, 9, 30, 16, 0, tzinfo=timezone.utc)


def completed(payload: dict | None = None, *, code: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    stdout = "" if payload is None else json.dumps(payload)
    return subprocess.CompletedProcess(args=[], returncode=code, stdout=stdout, stderr=stderr)


class FakeAws:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.image_state = "available"
        self.egress_denied = False
        self.ipv6_absent = False
        self.egress_open = False

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(args))
        text = " ".join(args)
        if "revoke-security-group-egress" in text and "--dry-run" in args:
            if self.egress_denied:
                return completed(
                    code=254,
                    stderr="An error occurred (AccessDenied) when calling the RevokeSecurityGroupEgress operation: User is not authorized",
                )
            return completed(
                code=254,
                stderr="An error occurred (DryRunOperation) when calling the RevokeSecurityGroupEgress operation: Request would have succeeded, but DryRun flag is set.",
            )
        if "revoke-security-group-egress" in text and "::/0" in text and self.ipv6_absent:
            return completed(
                code=254,
                stderr="An error occurred (InvalidPermission.NotFound) when calling the RevokeSecurityGroupEgress operation",
            )
        if "describe-security-groups" in text and "--group-ids" in args:
            group_id = args[args.index("--group-ids") + 1]
            rules = [{"IpProtocol": "-1", "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}] if self.egress_open else []
            return completed({"SecurityGroups": [{"GroupId": group_id, "IpPermissionsEgress": rules}]})
        if "get-caller-identity" in text:
            return completed({"Account": lab.ACCOUNT_ID, "Arn": "arn:aws:iam::960577828987:role/vantio-w3-lab-provision"})
        if "describe-images" in text:
            image_id = "ami-0123456789abcdef0"
            if "--image-ids" in args:
                image_id = args[args.index("--image-ids") + 1]
            return completed(
                {
                    "Images": [
                        {
                            "ImageId": image_id,
                            "State": self.image_state,
                            "OwnerId": lab.CANONICAL_OWNER,
                            "Name": "ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-20260901",
                            "Architecture": "x86_64",
                            "RootDeviceType": "ebs",
                            "Public": True,
                            "CreationDate": "2026-09-01T00:00:00.000Z",
                            "ProductCodes": [],
                            "BlockDeviceMappings": [{"Ebs": {"SnapshotId": "snap-0123456789abcdef0"}}],
                        }
                    ]
                }
            )
        if "create-security-group" in text:
            return completed({"GroupId": "sg-0123456789abcdef0"})
        if "run-instances" in text:
            return completed({"Instances": [{"InstanceId": "i-0123456789abcdef0"}]})
        if text.startswith("aws ce") or "get-cost-and-usage" in text:
            raise AssertionError(text)
        return completed({})

    def commands(self) -> list[str]:
        found = []
        for call in self.calls:
            if len(call) >= 3:
                found.append(call[2])
        return found


def owned_tags(expiry: str) -> dict[str, str]:
    tags = dict(lab.EXACT_TAGS)
    tags["Name"] = "vantio-w3-lab-auto-fixture"
    tags["vantio:expires-at"] = expiry
    tags["vantio:purpose"] = lab.PURPOSE_VALUE
    return tags


def passing_gate() -> dict:
    return lab.evaluate_cost_gate(
        {
            "accountId": lab.ACCOUNT_ID,
            "accountPlanType": "FREE",
            "accountPlanStatus": "ACTIVE",
            "accountPlanRemainingCredits": {"amount": "3.00", "unit": "USD"},
            "accountPlanExpirationDate": "2026-10-02T00:00:00Z",
        },
        NOW,
    )


def launch_spec(*, close_egress: bool = False) -> dict:
    return {
        "instance_type": "t3.micro",
        "stop_after_minutes": 15,
        "purpose": lab.PURPOSE_VALUE,
        "name": "vantio-w3-lab-auto-test",
        "associate_public_ipv4": "false",
        "close_egress": close_egress,
    }


class GateAbortTests(unittest.TestCase):
    def test_unknown_billing_aborts_before_aws(self) -> None:
        runner = FakeAws()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(lab.GuardAbort) as caught:
                lab.execute_launch(
                    launch_spec(),
                    {},
                    {"Account": lab.ACCOUNT_ID},
                    runner,
                    NOW,
                    user_data_path=Path(tmp) / "user-data.sh",
                )
        self.assertEqual(caught.exception.reason, "unknown_billing")
        self.assertEqual(runner.calls, [])

    def test_paid_plan_aborts_as_unknown_out_of_pocket(self) -> None:
        gate = lab.evaluate_cost_gate(
            {
                "accountId": lab.ACCOUNT_ID,
                "accountPlanType": "PAID",
                "accountPlanStatus": "ACTIVE",
                "accountPlanRemainingCredits": {"amount": "50.00", "unit": "USD"},
                "accountPlanExpirationDate": "2026-10-02T00:00:00Z",
            },
            NOW,
        )
        self.assertEqual(gate["expected_oop_usd"], "UNKNOWN")
        self.assertTrue(gate["abort"])
        self.assertEqual(gate["cost_explorer"], "not_called")
        runner = FakeAws()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(lab.GuardAbort) as caught:
                lab.execute_launch(
                    launch_spec(),
                    gate,
                    {"Account": lab.ACCOUNT_ID},
                    runner,
                    NOW,
                    user_data_path=Path(tmp) / "user-data.sh",
                )
        self.assertEqual(caught.exception.reason, "unknown_billing")
        self.assertEqual(runner.calls, [])

    def test_positive_oop_aborts_before_aws(self) -> None:
        gate = passing_gate()
        gate["expected_oop_usd"] = "0.01"
        runner = FakeAws()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(lab.GuardAbort) as caught:
                lab.execute_launch(
                    launch_spec(),
                    gate,
                    {"Account": lab.ACCOUNT_ID},
                    runner,
                    NOW,
                    user_data_path=Path(tmp) / "user-data.sh",
                )
        self.assertEqual(caught.exception.reason, "oop")
        self.assertEqual(runner.calls, [])

    def test_exact_two_dollar_credits_abort(self) -> None:
        gate = lab.evaluate_cost_gate(
            {
                "accountId": lab.ACCOUNT_ID,
                "accountPlanType": "FREE",
                "accountPlanStatus": "ACTIVE",
                "accountPlanRemainingCredits": {"amount": "2.00", "unit": "USD"},
                "accountPlanExpirationDate": "2026-10-02T00:00:00Z",
            },
            NOW,
        )
        self.assertEqual(gate["expected_oop_usd"], "UNKNOWN")
        self.assertIn("credits_not_above_ceiling", gate["reasons"])


class IdentityAndRegionTests(unittest.TestCase):
    def test_other_account_is_refused(self) -> None:
        runner = FakeAws()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(lab.GuardAbort) as caught:
                lab.execute_launch(
                    launch_spec(),
                    passing_gate(),
                    {"Account": "111122223333"},
                    runner,
                    NOW,
                    user_data_path=Path(tmp) / "user-data.sh",
                )
        self.assertEqual(caught.exception.reason, "account_id")
        self.assertEqual(runner.calls, [])

    def test_forbidden_account_is_refused(self) -> None:
        runner = FakeAws()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(lab.GuardAbort) as caught:
                lab.execute_launch(
                    launch_spec(),
                    passing_gate(),
                    {"Account": lab.FORBIDDEN_ACCOUNT_ID},
                    runner,
                    NOW,
                    user_data_path=Path(tmp) / "user-data.sh",
                )
        self.assertEqual(caught.exception.reason, "forbidden_account")
        self.assertEqual(runner.calls, [])

    def test_other_region_launch_is_refused(self) -> None:
        runner = FakeAws()
        spec = launch_spec()
        spec["region"] = "us-west-2"
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(lab.GuardAbort) as caught:
                lab.execute_launch(
                    spec,
                    passing_gate(),
                    {"Account": lab.ACCOUNT_ID},
                    runner,
                    NOW,
                    user_data_path=Path(tmp) / "user-data.sh",
                )
        self.assertEqual(caught.exception.reason, "region")
        self.assertEqual(runner.calls, [])

    def test_cost_explorer_command_is_refused(self) -> None:
        with self.assertRaises(lab.GuardAbort) as caught:
            lab.refuse_forbidden_command(["aws", "ce", "get-cost-and-usage", "--region", "us-east-1"])
        self.assertEqual(caught.exception.reason, "cost_explorer")


class SweepGuardTests(unittest.TestCase):
    def test_untagged_resource_is_not_deleted(self) -> None:
        runner = FakeAws()
        resource = {
            "type": "instance",
            "id": "i-0123456789abcdef0",
            "region": "us-east-2",
            "launch_time": "2026-09-30T12:00:00Z",
            "tags": {"Name": "someone-elses-box"},
        }
        result = lab.execute_sweep({"Account": lab.ACCOUNT_ID}, [resource], runner, NOW)
        self.assertEqual(result["actions"][0]["action"], "skip_not_owned")
        self.assertEqual(result["actions"][0]["called"], [])
        self.assertNotIn("terminate-instances", runner.commands())

    def test_other_region_resource_is_not_deleted(self) -> None:
        runner = FakeAws()
        resource = {
            "type": "instance",
            "id": "i-0123456789abcdef0",
            "region": "us-west-2",
            "launch_time": "2026-09-30T12:00:00Z",
            "tags": owned_tags("2026-09-30T12:05:00Z"),
        }
        result = lab.execute_sweep({"Account": lab.ACCOUNT_ID}, [resource], runner, NOW)
        self.assertEqual(result["actions"][0]["action"], "skip_wrong_region")
        self.assertNotIn("terminate-instances", runner.commands())

    def test_other_account_sweep_is_refused(self) -> None:
        runner = FakeAws()
        with self.assertRaises(lab.GuardAbort) as caught:
            lab.execute_sweep({"Account": "111122223333"}, [], runner, NOW)
        self.assertEqual(caught.exception.reason, "account_id")
        self.assertEqual(runner.calls, [])

    def test_expired_owned_instance_is_terminated(self) -> None:
        runner = FakeAws()
        resource = {
            "type": "instance",
            "id": "i-0123456789abcdef0",
            "region": "us-east-2",
            "launch_time": "2026-09-30T15:00:00Z",
            "tags": owned_tags("2026-09-30T15:05:00Z"),
        }
        result = lab.execute_sweep({"Account": lab.ACCOUNT_ID}, [resource], runner, NOW)
        self.assertEqual(result["actions"][0]["action"], "delete_expired")
        self.assertIn("terminate-instances", result["actions"][0]["called"])
        self.assertIn("terminate-instances", runner.commands())
        self.assertFalse(result["noninteractive_teardown_ready"])

    def test_destroyable_false_is_not_deleted(self) -> None:
        runner = FakeAws()
        tags = owned_tags("2026-09-30T15:05:00Z")
        tags["vantio:destroyable"] = "false"
        resource = {
            "type": "instance",
            "id": "i-0123456789abcdef0",
            "region": "us-east-2",
            "launch_time": "2026-09-30T15:00:00Z",
            "tags": tags,
        }
        result = lab.execute_sweep({"Account": lab.ACCOUNT_ID}, [resource], runner, NOW)
        self.assertNotIn("terminate-instances", runner.commands())
        self.assertNotEqual(result["actions"][0]["action"], "delete_expired")


class LaunchShapeTests(unittest.TestCase):
    def test_passing_gate_launches_one_terminating_instance(self) -> None:
        runner = FakeAws()
        with tempfile.TemporaryDirectory() as tmp:
            result = lab.execute_launch(
                launch_spec(),
                passing_gate(),
                {"Account": lab.ACCOUNT_ID},
                runner,
                NOW,
                user_data_path=Path(tmp) / "user-data.sh",
            )
        self.assertEqual(result["instance_id"], "i-0123456789abcdef0")
        self.assertEqual(result["expected_oop_usd"], "0")
        self.assertFalse(result["cost_explorer_called"])
        self.assertFalse(result["associate_public_ipv4"])
        self.assertEqual(result["shutdown_behavior"], "terminate")
        self.assertFalse(result["noninteractive_teardown_ready"])
        run = next(call for call in runner.calls if "run-instances" in call)
        self.assertEqual(run[run.index("--count") + 1], "1")
        self.assertEqual(run[run.index("--instance-initiated-shutdown-behavior") + 1], "terminate")
        self.assertEqual(run[run.index("--region") + 1], "us-east-2")
        self.assertEqual(run[run.index("--image-id") + 1], lab.PINNED_IMAGE_ID)
        self.assertIn(lab.LAB_SUBNET_ID, " ".join(run))
        self.assertNotIn(lab.FORBIDDEN_ACCOUNT_ID, " ".join(run))
        self.assertNotIn("iam-instance-profile", " ".join(run))
        self.assertEqual(runner.commands().count("run-instances"), 1)
        self.assertFalse(result["default_egress_revoked"])
        self.assertEqual(result["egress"], "default_allow")
        self.assertFalse(result["close_egress"])
        joined = " ".join(" ".join(call) for call in runner.calls)
        self.assertNotIn("revoke-security-group-egress", joined)
        self.assertNotIn("release-address", joined)

    def test_default_launch_ignores_a_missing_revoke_permission(self) -> None:
        runner = FakeAws()
        runner.egress_denied = True
        with tempfile.TemporaryDirectory() as tmp:
            result = lab.execute_launch(
                launch_spec(),
                passing_gate(),
                {"Account": lab.ACCOUNT_ID},
                runner,
                NOW,
                user_data_path=Path(tmp) / "user-data.sh",
            )
        self.assertEqual(result["egress"], "default_allow")
        self.assertIn("run-instances", runner.commands())
        self.assertNotIn("revoke-security-group-egress", runner.commands())
        self.assertNotIn("release-address", " ".join(" ".join(call) for call in runner.calls))

    def test_close_egress_revokes_before_launch(self) -> None:
        runner = FakeAws()
        with tempfile.TemporaryDirectory() as tmp:
            result = lab.execute_launch(
                launch_spec(close_egress=True),
                passing_gate(),
                {"Account": lab.ACCOUNT_ID},
                runner,
                NOW,
                user_data_path=Path(tmp) / "user-data.sh",
            )
        self.assertTrue(result["default_egress_revoked"])
        self.assertEqual(result["egress"], "revoked")
        self.assertNotIn("release-address", " ".join(" ".join(call) for call in runner.calls))
        revoke_at = next(i for i, call in enumerate(runner.calls) if "revoke-security-group-egress" in call and "--dry-run" not in call)
        run_at = next(i for i, call in enumerate(runner.calls) if "run-instances" in call)
        self.assertLess(revoke_at, run_at)
        revoked = " ".join(runner.calls[revoke_at])
        self.assertIn("0.0.0.0/0", revoked)
        self.assertIn('"IpProtocol":"-1"', revoked)

    def test_denied_egress_revoke_does_not_launch(self) -> None:
        runner = FakeAws()
        runner.egress_denied = True
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(lab.GuardAbort) as caught:
                lab.execute_launch(
                    launch_spec(close_egress=True),
                    passing_gate(),
                    {"Account": lab.ACCOUNT_ID},
                    runner,
                    NOW,
                    user_data_path=Path(tmp) / "user-data.sh",
                )
        self.assertEqual(caught.exception.reason, lab.EGRESS_REVOKE_DENIED)
        self.assertNotIn("run-instances", runner.commands())
        self.assertIn("delete-security-group", runner.commands())
        self.assertNotIn("release-address", " ".join(" ".join(call) for call in runner.calls))

    def test_missing_ipv6_egress_rule_still_launches(self) -> None:
        runner = FakeAws()
        runner.ipv6_absent = True
        with tempfile.TemporaryDirectory() as tmp:
            result = lab.execute_launch(
                launch_spec(close_egress=True),
                passing_gate(),
                {"Account": lab.ACCOUNT_ID},
                runner,
                NOW,
                user_data_path=Path(tmp) / "user-data.sh",
            )
        self.assertEqual(result["instance_id"], "i-0123456789abcdef0")
        self.assertTrue(result["default_egress_revoked"])

    def test_remaining_allow_all_egress_does_not_launch(self) -> None:
        runner = FakeAws()
        runner.egress_open = True
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(lab.GuardAbort) as caught:
                lab.execute_launch(
                    launch_spec(close_egress=True),
                    passing_gate(),
                    {"Account": lab.ACCOUNT_ID},
                    runner,
                    NOW,
                    user_data_path=Path(tmp) / "user-data.sh",
                )
        self.assertEqual(caught.exception.reason, "egress_still_open")
        self.assertNotIn("run-instances", runner.commands())
        self.assertIn("delete-security-group", runner.commands())

    def test_deregistered_image_does_not_create_a_group(self) -> None:
        runner = FakeAws()
        runner.image_state = "deregistered"
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(lab.GuardAbort) as caught:
                lab.execute_launch(
                    {"name": "vantio-w3-lab-auto-gone", "image_id": lab.PINNED_IMAGE_ID},
                    passing_gate(),
                    {"Account": lab.ACCOUNT_ID},
                    runner,
                    NOW,
                    user_data_path=Path(tmp) / "user-data.sh",
                )
        self.assertEqual(caught.exception.reason, "image_unavailable")
        self.assertNotIn("run-instances", runner.commands())
        self.assertNotIn("create-security-group", runner.commands())

    def test_debian_describe_records_the_official_name_and_snapshot(self) -> None:
        payload = {
            "Images": [
                {
                    "ImageId": "ami-063d15a058243cf84",
                    "State": "available",
                    "OwnerId": lab.DEBIAN_OWNER,
                    "Name": "debian-12-amd64-20261006-2623",
                    "Architecture": "x86_64",
                    "RootDeviceType": "ebs",
                    "Public": True,
                    "VirtualizationType": "hvm",
                    "ProductCodes": [],
                    "BlockDeviceMappings": [{"Ebs": {"SnapshotId": "snap-0a01c7c7b7c87682a"}}],
                }
            ]
        }
        facts = lab.image_facts(payload, "ami-063d15a058243cf84")
        self.assertEqual(facts["image_name"], "debian-12-amd64-20261006-2623")
        self.assertEqual(facts["image_owner"], lab.DEBIAN_OWNER)
        self.assertEqual(facts["snapshot_ids"], ["snap-0a01c7c7b7c87682a"])

    def test_describe_only_does_not_launch(self) -> None:
        runner = FakeAws()
        saved = {key: os.environ.get(key) for key in ("COST_GATE_FILE", "DESCRIBE_ONLY", "IMAGE_ID", "EVIDENCE_PATH")}
        with tempfile.TemporaryDirectory() as tmp:
            gate = Path(tmp) / "gate.json"
            gate.write_text(json.dumps(passing_gate()), encoding="utf-8")
            os.environ["COST_GATE_FILE"] = str(gate)
            os.environ["DESCRIBE_ONLY"] = "true"
            os.environ["IMAGE_ID"] = lab.PINNED_IMAGE_ID
            os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "out.json")
            try:
                result = lab.launch_from_env(runner, NOW)
            finally:
                for key, value in saved.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
        self.assertEqual(result["image_id"], lab.PINNED_IMAGE_ID)
        self.assertEqual(result["image_state"], "available")
        self.assertEqual(result["image_owner"], lab.CANONICAL_OWNER)
        self.assertIn("ubuntu-noble-24.04-amd64-server", result["image_name"])
        self.assertEqual(result["snapshot_ids"], ["snap-0123456789abcdef0"])
        self.assertFalse(result["launched"])
        self.assertNotIn("run-instances", runner.commands())
        self.assertNotIn("create-security-group", runner.commands())

    def test_false_string_does_not_request_a_public_address(self) -> None:
        plan = lab.plan_launch({"associate_public_ipv4": "false", "name": "vantio-w3-lab-auto-plan"}, NOW)
        self.assertFalse(plan["associate_public_ipv4"])
        self.assertIn("shutdown -h +15", lab.build_user_data(15))


class DebianImageTests(unittest.TestCase):
    def test_official_debian12_image_is_accepted(self) -> None:
        ami = "ami-0deb120000000001"
        payload = {
            "Images": [
                {
                    "ImageId": ami,
                    "State": "available",
                    "OwnerId": lab.DEBIAN_OWNER,
                    "Name": "debian-12-amd64-20251008-2233",
                    "Architecture": "x86_64",
                    "RootDeviceType": "ebs",
                    "Public": True,
                    "VirtualizationType": "hvm",
                    "ProductCodes": [],
                }
            ]
        }
        self.assertEqual(lab.require_available_image(payload, ami), ami)

    def test_debian_daily_name_is_rejected(self) -> None:
        payload = {
            "Images": [
                {
                    "ImageId": "ami-0deb120000000002",
                    "State": "available",
                    "OwnerId": lab.DEBIAN_OWNER,
                    "Name": "debian-12-amd64-daily-20251008",
                    "Architecture": "x86_64",
                    "RootDeviceType": "ebs",
                    "Public": True,
                    "VirtualizationType": "hvm",
                }
            ]
        }
        with self.assertRaises(lab.GuardAbort) as caught:
            lab.require_available_image(payload, "ami-0deb120000000002")
        self.assertEqual(caught.exception.reason, "image_rejected")

    def test_other_owner_is_still_rejected(self) -> None:
        payload = {
            "Images": [
                {
                    "ImageId": "ami-0deb120000000003",
                    "State": "available",
                    "OwnerId": "137112412989",
                    "Name": "debian-12-amd64-20251008-2233",
                    "Architecture": "x86_64",
                    "RootDeviceType": "ebs",
                    "Public": True,
                    "VirtualizationType": "hvm",
                }
            ]
        }
        with self.assertRaises(lab.GuardAbort) as caught:
            lab.require_available_image(payload, "ami-0deb120000000003")
        self.assertEqual(caught.exception.reason, "image_owner")


if __name__ == "__main__":
    unittest.main()
