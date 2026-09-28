#!/usr/bin/env python3
"""Behavior tests for the W3 lab teardown OIDC verifier.

These tests never call AWS. A fake client returns canned CLI results.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "aws"))

import verify_w3_lab_teardown as verify  # noqa: E402

NOW = datetime(2026, 9, 28, 18, 37, 16, tzinfo=timezone.utc)
LAB_INSTANCE = "i-01111111111111111"
OTHER_INSTANCE = "i-02222222222222222"
VOLUME_ID = "vol-03333333333333333"
GROUP_ID = "sg-04444444444444444"
ALLOCATION_ID = "eipalloc-05555555555555555"
ASSOCIATION_ID = "eipassoc-06666666666666666"
CANARY_KEY = "ASIAIOSFODNN7EXAMPLE"


def aws_json(payload: dict) -> verify.AwsResult:
    return verify.AwsResult(0, json.dumps(payload), "")


def aws_error(code: str, message: str = "no") -> verify.AwsResult:
    return verify.AwsResult(254, "", f"An error occurred ({code}) when calling the operation: {message}")


def lab_tags(**overrides: str) -> list[dict[str, str]]:
    values = dict(verify.LAB_TAGS)
    values.update(overrides)
    return [{"Key": key, "Value": value} for key, value in values.items()]


def volume_tags() -> list[dict[str, str]]:
    values = dict(verify.VOLUME_TAGS)
    return [{"Key": key, "Value": value} for key, value in values.items()]


def instance(instance_id: str, tags: list[dict[str, str]] | None = None, state: str = "running") -> dict:
    return {"InstanceId": instance_id, "State": {"Name": state}, "Tags": tags or []}


def reservations(*items: dict) -> dict:
    return {"Reservations": [{"Instances": list(items)}]}


class FakeAws:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []
        self.routes: list[tuple] = []

    def add(self, predicate, result) -> FakeAws:
        self.routes.append((predicate, result))
        return self

    def __call__(self, args: list[str], region: str) -> verify.AwsResult:
        self.calls.append((region, list(args)))
        for predicate, result in self.routes:
            if predicate(region, args):
                if callable(result):
                    return result(region, args)
                return result
        raise AssertionError(f"unexpected aws {region} {args}")


def starts(region: str, *prefix: str):
    def predicate(got_region: str, args: list[str]) -> bool:
        return got_region == region and args[: len(prefix)] == list(prefix)

    return predicate


def describe_instances(region: str, *, filtered: bool = False, by_id: bool = False):
    def predicate(got_region: str, args: list[str]) -> bool:
        if got_region != region or args[:2] != ["ec2", "describe-instances"]:
            return False
        has_filters = "--filters" in args
        has_ids = "--instance-ids" in args
        return has_filters is filtered and has_ids is by_id

    return predicate


def context(**overrides) -> verify.Context:
    data = {
        "now": NOW,
        "expiration": "2026-09-28T19:37:16Z",
        "requested_duration_seconds": 3600,
        "run_destructive": False,
        "fixture_instance_id": "",
        "fixture_volume_id": "",
        "fixture_security_group_id": "",
        "fixture_keypair_name": "",
        "fixture_eip_allocation_id": "",
        "role_session_name": "w3-lab-teardown-verify-1",
        "repository": verify.REPOSITORY,
        "run_id": "1",
        "run_attempt": "1",
        "assume_outcome": "success",
        "action_account_id": verify.ACCOUNT_ID,
        "action_arn": f"arn:aws:sts::{verify.ACCOUNT_ID}:assumed-role/{verify.ROLE_NAME}/w3-lab-teardown-verify-1",
        "access_key_id": CANARY_KEY,
    }
    data.update(overrides)
    return verify.Context(**data)


def caller_payload() -> dict:
    return {
        "Account": verify.ACCOUNT_ID,
        "Arn": f"arn:aws:sts::{verify.ACCOUNT_ID}:assumed-role/{verify.ROLE_NAME}/w3-lab-teardown-verify-1",
        "UserId": "AROAEXAMPLE:w3-lab-teardown-verify-1",
    }


def happy_aws() -> FakeAws:
    lab = instance(LAB_INSTANCE, lab_tags())
    other = instance(OTHER_INSTANCE)
    fake = FakeAws()
    fake.add(starts(verify.REGION, "sts", "get-caller-identity"), aws_json(caller_payload()))
    fake.add(describe_instances(verify.REGION, filtered=True), aws_json(reservations(lab)))
    fake.add(describe_instances(verify.REGION), aws_json(reservations(lab, other)))
    fake.add(starts(verify.REGION, "ec2", "terminate-instances"), aws_error("UnauthorizedOperation", "explicit deny"))
    fake.add(starts(verify.REGION, "ec2", "create-security-group"), aws_error("UnauthorizedOperation", "explicit deny"))
    fake.add(starts(verify.REGION, "iam", "create-user"), aws_error("AccessDenied", "explicit deny"))
    fake.add(starts(verify.OTHER_REGION, "ce", "get-cost-and-usage"), aws_error("AccessDeniedException", "explicit deny"))
    fake.add(describe_instances(verify.OTHER_REGION), aws_error("UnauthorizedOperation", "not authorized"))
    fake.add(starts(verify.OTHER_REGION, "ec2", "terminate-instances"), aws_error("UnauthorizedOperation", "explicit deny"))
    fake.add(starts(verify.REGION, "cloudtrail", "lookup-events"), aws_json({"Events": []}))
    return fake


def statuses(report: dict) -> dict[int, str]:
    return {int(item["id"]): item["status"] for item in report["checks"]}


def calls_named(fake: FakeAws, service: str, action: str) -> list[tuple[str, list[str]]]:
    return [item for item in fake.calls if item[1][:2] == [service, action]]


class VerifierTests(unittest.TestCase):
    def test_happy_path_passes_without_destructive_calls(self) -> None:
        fake = happy_aws()
        report = verify.run_checks(fake, context(), sleep=lambda _seconds: None)
        self.assertEqual(report["overall"], "PASS")
        self.assertEqual(
            statuses(report),
            {
                1: "PASS",
                2: "PASS",
                3: "PASS",
                4: "PASS",
                5: "PASS",
                6: "PASS",
                7: "PASS",
                8: "PASS",
                9: "NOT_RUN_AWAITING_FIXTURES",
                10: "NOT_RUN_AWAITING_FIXTURES",
                11: "NOT_RUN_AWAITING_FIXTURES",
                12: "NOT_RUN_AWAITING_FIXTURES",
                13: "NOT_RUN_AWAITING_FIXTURES",
                14: "PASS",
                15: "DOCUMENTED",
            },
        )
        self.assertIn("event_count=0", report["checks"][13]["detail"])
        self.assertIn("Expiration=2026-09-28T19:37:16Z", report["checks"][14]["detail"])
        self.assertEqual(report["policy_sha256"], verify.POLICY_SHA256)
        terminated = calls_named(fake, "ec2", "terminate-instances")
        self.assertEqual([item[0] for item in terminated], [verify.REGION, verify.OTHER_REGION])
        self.assertIn(OTHER_INSTANCE, terminated[0][1])
        self.assertNotIn(LAB_INSTANCE, terminated[0][1])
        self.assertIn(verify.SENTINEL_INSTANCE_ID, terminated[1][1])
        create = calls_named(fake, "ec2", "create-security-group")
        self.assertEqual(create[0][1][-1], "--dry-run")
        rendered = json.dumps(report)
        self.assertNotIn(CANARY_KEY, rendered)
        self.assertNotIn("run-instances", rendered)

    def test_zero_lab_instances_still_pass_describe(self) -> None:
        fake = happy_aws()
        fake.routes[1] = (describe_instances(verify.REGION, filtered=True), aws_json(reservations()))
        report = verify.run_checks(fake, context())
        self.assertEqual(statuses(report)[3], "PASS")
        self.assertIn("count=0", report["checks"][2]["detail"])

    def test_no_instances_skips_negative_terminate(self) -> None:
        fake = happy_aws()
        fake.routes[2] = (describe_instances(verify.REGION), aws_json(reservations()))
        report = verify.run_checks(fake, context())
        self.assertEqual(statuses(report)[4], "SKIP")
        self.assertIn("no EC2 instances", report["checks"][3]["detail"])
        self.assertEqual(calls_named(fake, "ec2", "terminate-instances")[0][0], verify.OTHER_REGION)

    def test_only_lab_tagged_instances_skip_negative_terminate(self) -> None:
        fake = happy_aws()
        fake.routes[2] = (describe_instances(verify.REGION), aws_json(reservations(instance(LAB_INSTANCE, lab_tags()))))
        report = verify.run_checks(fake, context())
        self.assertEqual(statuses(report)[4], "SKIP")
        self.assertIn("authorized lab tags", report["checks"][3]["detail"])
        regions = [item[0] for item in calls_named(fake, "ec2", "terminate-instances")]
        self.assertNotIn(verify.REGION, regions)

    def test_partial_tags_are_the_deny_probe(self) -> None:
        partial = instance(OTHER_INSTANCE, lab_tags())
        partial["Tags"] = [item for item in partial["Tags"] if item["Key"] != "vantio:destroyable"]
        fake = happy_aws()
        fake.routes[2] = (describe_instances(verify.REGION), aws_json(reservations(instance(LAB_INSTANCE, lab_tags()), partial)))
        report = verify.run_checks(fake, context())
        self.assertEqual(statuses(report)[4], "PASS")
        terminated = calls_named(fake, "ec2", "terminate-instances")[0][1]
        self.assertIn(OTHER_INSTANCE, terminated)

    def test_wrong_account_blocks_later_mutations(self) -> None:
        fake = FakeAws()
        payload = caller_payload()
        payload["Account"] = "000000000000"
        fake.add(starts(verify.REGION, "sts", "get-caller-identity"), aws_json(payload))
        report = verify.run_checks(fake, context())
        self.assertEqual(report["overall"], "FAIL")
        self.assertEqual(statuses(report)[1], "FAIL")
        self.assertEqual(statuses(report)[5], "FAIL")
        self.assertEqual(statuses(report)[9], "NOT_RUN_AWAITING_FIXTURES")
        self.assertEqual(fake.calls, [(verify.REGION, ["sts", "get-caller-identity"])])

    def test_similar_role_name_does_not_match(self) -> None:
        self.assertFalse(
            verify.identity_matches(
                f"arn:aws:sts::{verify.ACCOUNT_ID}:assumed-role/{verify.ROLE_NAME}-admin/session",
                verify.ACCOUNT_ID,
            )
        )
        self.assertTrue(
            verify.identity_matches(
                f"arn:aws:sts::{verify.ACCOUNT_ID}:assumed-role/{verify.ROLE_NAME}/session",
                verify.ACCOUNT_ID,
            )
        )

    def test_assume_failure_does_not_call_aws(self) -> None:
        fake = FakeAws()
        report = verify.run_checks(fake, context(assume_outcome="failure", run_destructive=True))
        self.assertEqual(fake.calls, [])
        self.assertEqual(report["overall"], "FAIL")
        self.assertEqual(statuses(report)[1], "FAIL")
        self.assertEqual(statuses(report)[9], "FAIL")
        self.assertIn("not attempted", report["checks"][8]["detail"])

    def test_accepted_terminate_of_untagged_instance_fails(self) -> None:
        fake = happy_aws()
        fake.routes[3] = (
            starts(verify.REGION, "ec2", "terminate-instances"),
            aws_json({"TerminatingInstances": [{"InstanceId": OTHER_INSTANCE}]}),
        )
        report = verify.run_checks(fake, context())
        self.assertEqual(statuses(report)[4], "FAIL")
        self.assertIn("was accepted", report["checks"][3]["detail"])

    def test_dry_run_success_fails_create_check(self) -> None:
        fake = happy_aws()
        fake.routes[4] = (
            starts(verify.REGION, "ec2", "create-security-group"),
            aws_error("DryRunOperation", "Request would have succeeded"),
        )
        report = verify.run_checks(fake, context())
        self.assertEqual(statuses(report)[5], "FAIL")
        self.assertIn("DryRunOperation", report["checks"][4]["detail"])

    def test_created_security_group_is_a_failure_and_delete_is_attempted(self) -> None:
        fake = happy_aws()
        fake.routes[4] = (
            starts(verify.REGION, "ec2", "create-security-group"),
            aws_json({"GroupId": "sg-09999999999999999"}),
        )
        fake.add(starts(verify.REGION, "ec2", "delete-security-group"), aws_error("UnauthorizedOperation"))
        report = verify.run_checks(fake, context())
        self.assertEqual(statuses(report)[5], "FAIL")
        self.assertTrue(calls_named(fake, "ec2", "delete-security-group"))

    def test_created_iam_user_attempts_delete(self) -> None:
        fake = happy_aws()
        fake.routes[5] = (starts(verify.REGION, "iam", "create-user"), aws_json({"User": {"UserName": verify.PROBE_IAM_USER}}))
        fake.add(starts(verify.REGION, "iam", "delete-user"), aws_error("AccessDenied", "explicit deny"))
        report = verify.run_checks(fake, context())
        self.assertEqual(statuses(report)[6], "FAIL")
        self.assertTrue(calls_named(fake, "iam", "delete-user"))

    def test_billing_success_fails(self) -> None:
        fake = happy_aws()
        fake.routes[6] = (starts(verify.OTHER_REGION, "ce", "get-cost-and-usage"), aws_json({"ResultsByTime": []}))
        report = verify.run_checks(fake, context())
        self.assertEqual(statuses(report)[7], "FAIL")

    def test_other_region_describe_success_fails(self) -> None:
        fake = happy_aws()
        fake.routes[7] = (describe_instances(verify.OTHER_REGION), aws_json(reservations()))
        report = verify.run_checks(fake, context())
        self.assertEqual(statuses(report)[8], "FAIL")
        self.assertIn("was allowed", report["checks"][7]["detail"])

    def test_describe_denied_fails_lab_inventory(self) -> None:
        fake = happy_aws()
        fake.routes[1] = (describe_instances(verify.REGION, filtered=True), aws_error("UnauthorizedOperation"))
        report = verify.run_checks(fake, context())
        self.assertEqual(statuses(report)[3], "FAIL")

    def test_cloudtrail_denial_fails_and_empty_success_notes_delay(self) -> None:
        fake = happy_aws()
        fake.routes[9] = (starts(verify.REGION, "cloudtrail", "lookup-events"), aws_error("AccessDeniedException"))
        report = verify.run_checks(fake, context())
        self.assertEqual(statuses(report)[14], "FAIL")

    def test_session_longer_than_one_hour_fails(self) -> None:
        report = verify.run_checks(happy_aws(), context(expiration="2026-09-28T20:37:16Z"))
        self.assertEqual(statuses(report)[2], "FAIL")
        report = verify.run_checks(happy_aws(), context(requested_duration_seconds=7200))
        self.assertEqual(statuses(report)[2], "FAIL")

    def test_missing_expiration_still_passes_when_request_is_capped(self) -> None:
        report = verify.run_checks(happy_aws(), context(expiration=""))
        self.assertEqual(statuses(report)[2], "PASS")
        self.assertIn("not available", report["checks"][1]["detail"])
        self.assertIn("3600", report["checks"][1]["detail"])

    def test_javascript_date_expiration_parses(self) -> None:
        raw = "Mon Sep 28 2026 19:37:16 GMT+0000 (Coordinated Universal Time)"
        self.assertEqual(verify.parse_time(raw), NOW + timedelta(hours=1))
        self.assertEqual(verify.parse_time('"2026-09-28T19:37:16.000Z"'), NOW + timedelta(hours=1))

    def test_redact_hides_access_keys(self) -> None:
        text = verify.redact(f"key {CANARY_KEY} aws_session_token=secretvalue")
        self.assertNotIn(CANARY_KEY, text)
        self.assertIn("ASIA****************", text)
        self.assertIn("<redacted>", text)

    def test_destructive_false_string_does_not_enable_close(self) -> None:
        with mock.patch.dict(os.environ, {"RUN_DESTRUCTIVE_FIXTURES": "TRUE", "REQUESTED_ROLE_DURATION_SECONDS": "3600"}, clear=True):
            ctx = verify.context_from_environ(now=NOW)
        self.assertFalse(ctx.run_destructive)

    def test_destructive_close_refuses_untagged_instance(self) -> None:
        fake = happy_aws()
        fake.add(describe_instances(verify.REGION, by_id=True), aws_json(reservations(instance(OTHER_INSTANCE))))
        report = verify.run_checks(
            fake,
            context(run_destructive=True, fixture_instance_id=OTHER_INSTANCE),
            sleep=lambda _seconds: None,
        )
        self.assertEqual(statuses(report)[9], "FAIL")
        self.assertIn("refused", report["checks"][8]["detail"])
        terminated = [item for item in calls_named(fake, "ec2", "terminate-instances") if item[0] == verify.REGION]
        self.assertEqual(len(terminated), 1)
        self.assertIn(OTHER_INSTANCE, terminated[0][1])

    def test_destructive_close_runs_dependency_order_for_tagged_fixtures(self) -> None:
        fake = happy_aws()
        fake.add(
            describe_instances(verify.REGION, by_id=True),
            aws_json(reservations(instance(LAB_INSTANCE, lab_tags()))),
        )
        volume_calls = {"n": 0}

        def volume_describe(_region, _args):
            volume_calls["n"] += 1
            if volume_calls["n"] == 1:
                return aws_json(
                    {
                        "Volumes": [
                            {
                                "VolumeId": VOLUME_ID,
                                "State": "in-use",
                                "Attachments": [{"InstanceId": LAB_INSTANCE, "State": "attached"}],
                                "Tags": volume_tags(),
                            }
                        ]
                    }
                )
            return aws_json({"Volumes": [{"VolumeId": VOLUME_ID, "State": "available", "Attachments": [], "Tags": volume_tags()}]})

        fake.add(starts(verify.REGION, "ec2", "describe-volumes"), volume_describe)
        fake.add(starts(verify.REGION, "ec2", "detach-volume"), aws_json({"VolumeId": VOLUME_ID}))
        fake.add(starts(verify.REGION, "ec2", "delete-volume"), aws_json({"VolumeId": VOLUME_ID}))
        fake.add(
            starts(verify.REGION, "ec2", "describe-security-groups"),
            aws_json({"SecurityGroups": [{"GroupId": GROUP_ID, "GroupName": "lab", "Tags": lab_tags()}]}),
        )
        fake.add(starts(verify.REGION, "ec2", "delete-security-group"), aws_json({}))
        fake.add(starts(verify.REGION, "ec2", "describe-key-pairs"), aws_json({"KeyPairs": [{"KeyName": verify.AUTHORIZED_KEY_PAIR}]}))
        fake.add(starts(verify.REGION, "ec2", "delete-key-pair"), aws_json({}))
        fake.add(
            starts(verify.REGION, "ec2", "describe-addresses"),
            aws_json(
                {
                    "Addresses": [
                        {
                            "AllocationId": ALLOCATION_ID,
                            "AssociationId": ASSOCIATION_ID,
                            "Tags": lab_tags(),
                        }
                    ]
                }
            ),
        )
        fake.add(starts(verify.REGION, "ec2", "disassociate-address"), aws_json({}))
        fake.add(starts(verify.REGION, "ec2", "release-address"), aws_json({}))
        # The untagged deny probe still matches the first terminate route. Register the
        # authorized terminate after it by making the happy route only match the other id.
        fake.routes[3] = (
            lambda region, args: region == verify.REGION and args[:2] == ["ec2", "terminate-instances"] and OTHER_INSTANCE in args,
            aws_error("UnauthorizedOperation", "explicit deny"),
        )
        fake.add(
            lambda region, args: region == verify.REGION and args[:2] == ["ec2", "terminate-instances"] and LAB_INSTANCE in args,
            aws_json({"TerminatingInstances": [{"InstanceId": LAB_INSTANCE, "CurrentState": {"Name": "shutting-down"}}]}),
        )
        report = verify.run_checks(
            fake,
            context(
                run_destructive=True,
                fixture_instance_id=LAB_INSTANCE,
                fixture_volume_id=VOLUME_ID,
                fixture_security_group_id=GROUP_ID,
                fixture_keypair_name=verify.AUTHORIZED_KEY_PAIR,
                fixture_eip_allocation_id=ALLOCATION_ID,
            ),
            sleep=lambda _seconds: None,
        )
        self.assertEqual(report["overall"], "PASS")
        self.assertEqual(statuses(report)[9], "PASS")
        self.assertEqual(statuses(report)[10], "PASS")
        self.assertEqual(statuses(report)[11], "PASS")
        self.assertEqual(statuses(report)[12], "PASS")
        self.assertEqual(statuses(report)[13], "PASS")
        destructive_ops = []
        for region, args in fake.calls:
            if region != verify.REGION:
                continue
            if args[:2] == ["ec2", "release-address"]:
                destructive_ops.append("release")
            elif args[:2] == ["ec2", "terminate-instances"] and LAB_INSTANCE in args:
                destructive_ops.append("terminate-lab")
            elif args[:2] == ["ec2", "delete-volume"]:
                destructive_ops.append("delete-volume")
            elif args[:2] == ["ec2", "delete-security-group"] and GROUP_ID in args:
                destructive_ops.append("delete-sg")
            elif args[:2] == ["ec2", "delete-key-pair"]:
                destructive_ops.append("delete-key")
        self.assertEqual(
            destructive_ops,
            ["release", "terminate-lab", "delete-volume", "delete-sg", "delete-key"],
        )
        self.assertEqual(volume_calls["n"], 2)

    def test_wrong_key_pair_is_refused(self) -> None:
        fake = happy_aws()
        report = verify.run_checks(
            fake,
            context(run_destructive=True, fixture_keypair_name="other-key"),
            sleep=lambda _seconds: None,
        )
        self.assertEqual(statuses(report)[12], "FAIL")
        self.assertEqual(calls_named(fake, "ec2", "delete-key-pair"), [])

    def test_missing_destructive_ids_stay_not_run(self) -> None:
        report = verify.run_checks(happy_aws(), context(run_destructive=True), sleep=lambda _seconds: None)
        self.assertEqual(report["overall"], "PASS")
        for check_id in range(9, 14):
            self.assertEqual(statuses(report)[check_id], "NOT_RUN_AWAITING_FIXTURES")

    def test_volume_tag_mismatch_does_not_detach(self) -> None:
        fake = happy_aws()
        fake.add(
            starts(verify.REGION, "ec2", "describe-volumes"),
            aws_json({"Volumes": [{"VolumeId": VOLUME_ID, "State": "available", "Attachments": [], "Tags": lab_tags()}]}),
        )
        report = verify.run_checks(
            fake,
            context(run_destructive=True, fixture_volume_id=VOLUME_ID),
            sleep=lambda _seconds: None,
        )
        self.assertEqual(statuses(report)[10], "FAIL")
        self.assertEqual(calls_named(fake, "ec2", "delete-volume"), [])
        self.assertEqual(calls_named(fake, "ec2", "detach-volume"), [])

    def test_source_does_not_call_provision_or_admin_attach(self) -> None:
        text = (ROOT / "scripts" / "aws" / "verify_w3_lab_teardown.py").read_text(encoding="utf-8")
        for banned in ("run-instances", "attach-role-policy", "create-access-key", "allocate-address", "create-key-pair"):
            self.assertNotIn(banned, text)

    def test_main_writes_artifact_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result_path = str(Path(tmp) / "result.json")
            summary_path = str(Path(tmp) / "summary.md")
            expiration = (datetime.now(timezone.utc) + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
            env = {
                "PATH": os.environ.get("PATH", ""),
                "REQUESTED_ROLE_DURATION_SECONDS": "3600",
                "RUN_DESTRUCTIVE_FIXTURES": "false",
                "W3_AWS_EXPIRATION": expiration,
                "AWS_CONFIGURE_OUTCOME": "success",
                "W3_ACTION_ACCOUNT_ID": verify.ACCOUNT_ID,
                "W3_ACTION_ARN": caller_payload()["Arn"],
                "AWS_ACCESS_KEY_ID": CANARY_KEY,
                "ROLE_SESSION_NAME": "w3-lab-teardown-verify-1",
                "VERIFY_RESULT_PATH": result_path,
                "GITHUB_STEP_SUMMARY": summary_path,
                "GITHUB_REPOSITORY": verify.REPOSITORY,
                "GITHUB_RUN_ID": "99",
            }
            with mock.patch.dict(os.environ, env, clear=True):
                code = verify.main([], aws=happy_aws())
            self.assertEqual(code, 0)
            payload = json.loads(Path(result_path).read_text(encoding="utf-8"))
            self.assertEqual(payload["overall"], "PASS")
            self.assertNotIn(CANARY_KEY, Path(result_path).read_text(encoding="utf-8"))
            summary = Path(summary_path).read_text(encoding="utf-8")
            self.assertIn("Overall: **PASS**", summary)
            self.assertIn("09 close_instance", summary)
            self.assertNotIn(CANARY_KEY, summary)

    def test_main_rejects_non_dispatch_on_actions(self) -> None:
        env = {
            "PATH": os.environ.get("PATH", ""),
            "GITHUB_ACTIONS": "true",
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_REPOSITORY": verify.REPOSITORY,
            "GITHUB_REF": "refs/heads/main",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(SystemExit) as raised:
                verify.main([])
        self.assertIn("workflow identity", str(raised.exception))

    def test_cli_builder_uses_region_and_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            log = Path(tmp) / "log"
            script = bin_dir / "aws"
            script.write_text(
                textwrap.dedent(
                    """\
                    #!/bin/sh
                    printf '%s\\n' "$*" > "$AWS_FAKE_LOG"
                    printf '%s\\n' '{"Account":"960577828987","Arn":"arn:aws:sts::960577828987:assumed-role/vantio-w3-lab-teardown/s","UserId":"A:s"}'
                    """
                ),
                encoding="utf-8",
            )
            script.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
            env["AWS_FAKE_LOG"] = str(log)
            with mock.patch.dict(os.environ, env, clear=True):
                result = verify.aws_cli(["sts", "get-caller-identity"], verify.REGION)
            self.assertEqual(result.returncode, 0)
            logged = log.read_text(encoding="utf-8")
            self.assertIn("--region us-east-2", logged)
            self.assertIn("--output json", logged)
            self.assertIn("sts get-caller-identity", logged)


class SubprocessCliTests(unittest.TestCase):
    def test_module_exits_nonzero_on_failed_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result_path = str(Path(tmp) / "result.json")
            env = os.environ.copy()
            for key in list(env):
                if key.startswith("GITHUB_") or key.startswith("AWS_") or key.startswith("W3_") or key.startswith("FIXTURE"):
                    env.pop(key, None)
            env.update(
                {
                    "REQUESTED_ROLE_DURATION_SECONDS": "3600",
                    "RUN_DESTRUCTIVE_FIXTURES": "false",
                    "AWS_CONFIGURE_OUTCOME": "failure",
                    "VERIFY_RESULT_PATH": result_path,
                    "GITHUB_STEP_SUMMARY": "",
                }
            )
            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "aws" / "verify_w3_lab_teardown.py")],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("CHECK 01 FAIL assume_session", completed.stdout)
        self.assertIn("OVERALL FAIL", completed.stdout)

    def test_module_exits_nonzero_when_actions_event_is_not_dispatch(self) -> None:
        env = os.environ.copy()
        env.update(
            {
                "GITHUB_ACTIONS": "true",
                "GITHUB_EVENT_NAME": "push",
                "GITHUB_REPOSITORY": verify.REPOSITORY,
                "GITHUB_REF": "refs/heads/main",
            }
        )
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "aws" / "verify_w3_lab_teardown.py")],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(completed.returncode, 1)
        self.assertIn("workflow identity", completed.stderr)


if __name__ == "__main__":
    unittest.main()
