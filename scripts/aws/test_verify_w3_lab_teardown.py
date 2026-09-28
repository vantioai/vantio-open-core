#!/usr/bin/env python3
"""Behavior tests for the W3 lab teardown OIDC verifier.

These tests never call AWS. A fake client returns canned CLI results.
"""

from __future__ import annotations

import json
import os
import string
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


def create_sg(region: str, group_name: str):
    def predicate(got_region: str, args: list[str]) -> bool:
        return got_region == region and args[:2] == ["ec2", "create-security-group"] and group_name in args

    return predicate


def happy_aws() -> FakeAws:
    lab = instance(LAB_INSTANCE, lab_tags())
    fake = FakeAws()
    fake.add(starts(verify.REGION, "sts", "get-caller-identity"), aws_json(caller_payload()))
    fake.add(describe_instances(verify.REGION, filtered=True), aws_json(reservations(lab)))
    fake.add(create_sg(verify.REGION, verify.PROBE_TAGGED_SECURITY_GROUP), aws_error("UnauthorizedOperation", "explicit deny"))
    fake.add(create_sg(verify.REGION, verify.PROBE_SECURITY_GROUP), aws_error("UnauthorizedOperation", "explicit deny"))
    fake.add(starts(verify.REGION, "iam", "get-user"), aws_error("AccessDenied", "explicit deny"))
    fake.add(starts(verify.OTHER_REGION, "ce", "get-cost-and-usage"), aws_error("AccessDeniedException", "explicit deny"))
    fake.add(describe_instances(verify.OTHER_REGION), aws_error("UnauthorizedOperation", "not authorized"))
    fake.add(create_sg(verify.OTHER_REGION, verify.PROBE_REGION_SECURITY_GROUP), aws_error("UnauthorizedOperation", "explicit deny"))
    fake.add(starts(verify.REGION, "cloudtrail", "lookup-events"), aws_json({"Events": []}))
    return fake


def statuses(report: dict) -> dict[int, str]:
    return {int(item["id"]): item["status"] for item in report["checks"]}


def calls_named(fake: FakeAws, service: str, action: str) -> list[tuple[str, list[str]]]:
    return [item for item in fake.calls if item[1][:2] == [service, action]]


class CliShorthandError(Exception):
    """Same failure AWS CLI v2 ShorthandParser raises for a bad hash literal."""


_SHORTHAND_KEY_CHARS = set(string.ascii_letters + string.digits + "-_.#/:")


class _ShorthandCursor:
    """Subset of awscli.shorthand.ShorthandParser for --tag-specifications.

    AWS CLI v2 skips this parser when the value starts with '{' or '['
    (ParamShorthandParser._should_parse_as_shorthand). Otherwise a '{'
    starts a hash literal, and the next token must be a key then '='.
    A quote there raises Expected: '=', received: '"'.
    """

    def __init__(self, value: str) -> None:
        self.value = value
        self.index = 0

    def current(self) -> str:
        if self.index >= len(self.value):
            return ""
        return self.value[self.index]

    def _skip_ws(self) -> None:
        while self.current() and self.current() in string.whitespace:
            self.index += 1

    def expect(self, char: str) -> None:
        self._skip_ws()
        actual = self.current() or "EOF"
        if actual != char:
            raise CliShorthandError(f"Expected: '{char}', received: '{actual}'")
        self.index += 1

    def key(self) -> str:
        self._skip_ws()
        start = self.index
        while self.current() in _SHORTHAND_KEY_CHARS:
            self.index += 1
        return self.value[start : self.index]

    def scalar(self) -> str:
        self._skip_ws()
        start = self.index
        while self.current() and self.current() not in ",}]":
            self.index += 1
        return self.value[start : self.index].rstrip()

    def explicit_value(self):
        self._skip_ws()
        if self.current() == "[":
            return self.explicit_list()
        if self.current() == "{":
            return self.hash_literal()
        return self.scalar()

    def hash_literal(self) -> dict:
        self.expect("{")
        found: dict = {}
        self._skip_ws()
        while self.current() != "}":
            key = self.key()
            self.expect("=")
            found[key] = self.explicit_value()
            self._skip_ws()
            if self.current() != "}":
                self.expect(",")
                self._skip_ws()
        self.expect("}")
        return found

    def explicit_list(self) -> list:
        self.expect("[")
        values = []
        self._skip_ws()
        while self.current() != "]":
            values.append(self.explicit_value())
            self._skip_ws()
            if self.current() != "]":
                self.expect(",")
                self._skip_ws()
        self.expect("]")
        return values

    def parameter(self) -> dict:
        params: dict = {}
        while True:
            key = self.key()
            self.expect("=")
            params[key] = self.explicit_value()
            self._skip_ws()
            if not self.current():
                return params
            self.expect(",")


def parse_tag_specifications_like_aws_cli_v2(value: str) -> list[dict]:
    """Parse one --tag-specifications argument the way AWS CLI v2 does.

    A value that starts with '{' or '[' is JSON. Anything else is shorthand.
    """
    text = value.strip()
    if text.startswith(("{", "[")):
        parsed = json.loads(text)
        specs = parsed if isinstance(parsed, list) else [parsed]
        if not isinstance(specs, list) or not all(isinstance(item, dict) for item in specs):
            raise ValueError("tag specifications JSON was not an object or a list of objects")
        return specs
    return [_ShorthandCursor(text).parameter()]


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
        self.assertEqual(report["policy_sha256_label"], "prepared_digest")
        self.assertEqual(calls_named(fake, "ec2", "terminate-instances"), [])
        create = calls_named(fake, "ec2", "create-security-group")
        self.assertEqual(
            [(region, args[3]) for region, args in create],
            [
                (verify.REGION, verify.PROBE_TAGGED_SECURITY_GROUP),
                (verify.REGION, verify.PROBE_SECURITY_GROUP),
                (verify.OTHER_REGION, verify.PROBE_REGION_SECURITY_GROUP),
            ],
        )
        for _region, args in create:
            self.assertEqual(args[-1], "--dry-run")
            self.assertNotIn(LAB_INSTANCE, args)
            self.assertNotIn(OTHER_INSTANCE, args)
            self.assertNotIn("i-0deadbeef0deadbee", args)
        tagged = create[0][1]
        self.assertIn("--tag-specifications", tagged)
        self.assertIn("vantio:program", " ".join(tagged))
        self.assertIn("w3-clean-host-lab", " ".join(tagged))
        self.assertNotIn("--tag-specifications", create[1][1])
        self.assertNotIn("--tag-specifications", create[2][1])
        self.assertIn("TerminateInstances was not called", report["checks"][3]["detail"])
        self.assertIn("TerminateInstances was not called", report["checks"][7]["detail"])
        self.assertEqual(calls_named(fake, "iam", "get-user")[0][1][3], verify.PROBE_IAM_USER)
        self.assertEqual(calls_named(fake, "iam", "create-user"), [])
        rendered = json.dumps(report)
        self.assertNotIn(CANARY_KEY, rendered)
        self.assertNotIn("run-instances", rendered)
        self.assertNotIn("live-measured", rendered)

    def test_zero_lab_instances_still_pass_describe(self) -> None:
        fake = happy_aws()
        fake.routes[1] = (describe_instances(verify.REGION, filtered=True), aws_json(reservations()))
        report = verify.run_checks(fake, context())
        self.assertEqual(statuses(report)[3], "PASS")
        self.assertIn("count=0", report["checks"][2]["detail"])

    def test_tagged_create_dry_run_runs_with_no_instances_in_the_account(self) -> None:
        fake = happy_aws()
        fake.routes[1] = (describe_instances(verify.REGION, filtered=True), aws_json(reservations()))
        report = verify.run_checks(fake, context())
        self.assertEqual(report["overall"], "PASS")
        self.assertEqual(statuses(report)[4], "PASS")
        self.assertEqual(calls_named(fake, "ec2", "terminate-instances"), [])
        self.assertTrue(all(args[-1] == "--dry-run" for _region, args in calls_named(fake, "ec2", "create-security-group")))
        self.assertNotIn("SKIP", statuses(report).values())

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

    def test_tagged_create_dry_run_allowed_fails(self) -> None:
        fake = happy_aws()
        fake.routes[2] = (
            create_sg(verify.REGION, verify.PROBE_TAGGED_SECURITY_GROUP),
            aws_error("DryRunOperation", "Request would have succeeded"),
        )
        report = verify.run_checks(fake, context())
        self.assertEqual(statuses(report)[4], "FAIL")
        self.assertIn("would have been allowed", report["checks"][3]["detail"])
        self.assertIn("DryRunOperation", report["checks"][3]["detail"])
        self.assertEqual(calls_named(fake, "ec2", "terminate-instances"), [])

    def test_other_region_create_dry_run_allowed_fails(self) -> None:
        fake = happy_aws()
        fake.routes[7] = (
            create_sg(verify.OTHER_REGION, verify.PROBE_REGION_SECURITY_GROUP),
            aws_error("DryRunOperation", "Request would have succeeded"),
        )
        report = verify.run_checks(fake, context())
        self.assertEqual(statuses(report)[8], "FAIL")
        self.assertIn("would have been allowed", report["checks"][7]["detail"])
        self.assertEqual(calls_named(fake, "ec2", "terminate-instances"), [])

    def test_tag_specification_is_cli_json_not_broken_shorthand(self) -> None:
        spec = verify.security_group_tag_specification()
        args = verify.create_security_group_dry_run_args(
            verify.PROBE_TAGGED_SECURITY_GROUP,
            with_lab_tags=True,
        )
        self.assertEqual(args[-1], "--dry-run")
        self.assertEqual(args[args.index("--tag-specifications") + 1], spec)
        self.assertTrue(spec.startswith("{"))
        self.assertFalse(spec.startswith("ResourceType="))
        self.assertNotIn('Tags=[{"', spec)
        parsed = parse_tag_specifications_like_aws_cli_v2(spec)
        self.assertEqual(
            parsed,
            [
                {
                    "ResourceType": "security-group",
                    "Tags": [{"Key": key, "Value": value} for key, value in verify.LAB_TAGS.items()],
                }
            ],
        )
        shorthand = "ResourceType=security-group,Tags=[" + ",".join(
            f"{{Key={key},Value={value}}}" for key, value in verify.LAB_TAGS.items()
        ) + "]"
        self.assertEqual(parse_tag_specifications_like_aws_cli_v2(shorthand), parsed)
        broken = 'ResourceType=security-group,Tags=[{"Key":"vantio:program","Value":"w3-clean-host-lab"}]'
        with self.assertRaises(CliShorthandError) as raised:
            parse_tag_specifications_like_aws_cli_v2(broken)
        message = str(raised.exception)
        self.assertIn("Expected: '='", message)
        self.assertIn("received: '\"'", message)

    def test_not_found_does_not_pass_checks_4_or_8(self) -> None:
        not_found = aws_error(
            "InvalidInstanceID.NotFound",
            "The instance ID 'i-0deadbeef0deadbee' does not exist",
        )
        self.assertFalse(verify.is_denied(not_found))
        self.assertEqual(verify.classify_dry_run(not_found), "not_found")
        poisoned = aws_error(
            "InvalidInstanceID.NotFound",
            "not authorized explicit deny The instance ID 'i-0deadbeef0deadbee' does not exist",
        )
        self.assertEqual(verify.classify_dry_run(poisoned), "not_found")
        self.assertFalse(verify.is_denied(poisoned))

        fake = happy_aws()
        fake.routes[2] = (create_sg(verify.REGION, verify.PROBE_TAGGED_SECURITY_GROUP), not_found)
        report = verify.run_checks(fake, context())
        self.assertEqual(statuses(report)[4], "FAIL")
        self.assertEqual(report["overall"], "FAIL")
        detail = report["checks"][3]["detail"]
        self.assertIn("InvalidInstanceID.NotFound", detail)
        self.assertIn("does not pass", detail)
        self.assertNotIn("was denied", detail)
        self.assertEqual(calls_named(fake, "ec2", "terminate-instances"), [])

        fake = happy_aws()
        fake.routes[7] = (create_sg(verify.OTHER_REGION, verify.PROBE_REGION_SECURITY_GROUP), not_found)
        report = verify.run_checks(fake, context())
        self.assertEqual(statuses(report)[8], "FAIL")
        self.assertEqual(report["overall"], "FAIL")
        detail = report["checks"][7]["detail"]
        self.assertIn("InvalidInstanceID.NotFound", detail)
        self.assertIn("does not pass", detail)
        self.assertNotIn("was denied", detail)
        self.assertEqual(calls_named(fake, "ec2", "terminate-instances"), [])

    def test_describe_not_found_with_deny_wording_fails_check_8(self) -> None:
        fake = happy_aws()
        fake.routes[6] = (
            describe_instances(verify.OTHER_REGION),
            aws_error(
                "InvalidInstanceID.NotFound",
                "explicit deny not authorized The instance ID does not exist",
            ),
        )
        report = verify.run_checks(fake, context())
        self.assertEqual(statuses(report)[8], "FAIL")
        detail = report["checks"][7]["detail"]
        self.assertIn("InvalidInstanceID.NotFound", detail)
        self.assertNotIn("describe was denied", detail)
        self.assertEqual(report["overall"], "FAIL")

    def test_not_found_exception_codes_are_not_denied(self) -> None:
        wording = "explicit deny not authorized"
        for code in ("NotFound", "NotFoundException", "ResourceNotFoundException", "InvalidInstanceID.NotFound"):
            result = aws_error(code, wording)
            self.assertFalse(verify.is_denied(result), code)
            self.assertEqual(verify.classify_dry_run(result), "not_found", code)
        bare_deny = verify.AwsResult(254, "", "User is not authorized to perform this operation")
        self.assertTrue(verify.is_denied(bare_deny))
        for code in ("NotFoundException", "ResourceNotFoundException"):
            fake = happy_aws()
            fake.routes[6] = (
                describe_instances(verify.OTHER_REGION),
                aws_error(code, wording),
            )
            report = verify.run_checks(fake, context())
            self.assertEqual(statuses(report)[8], "FAIL", code)
            self.assertNotIn("describe was denied", report["checks"][7]["detail"])

    def test_access_denied_passes_checks_4_and_8(self) -> None:
        fake = happy_aws()
        fake.routes[2] = (
            create_sg(verify.REGION, verify.PROBE_TAGGED_SECURITY_GROUP),
            aws_error("AccessDenied", "explicit deny"),
        )
        fake.routes[7] = (
            create_sg(verify.OTHER_REGION, verify.PROBE_REGION_SECURITY_GROUP),
            aws_error("AccessDenied", "explicit deny"),
        )
        report = verify.run_checks(fake, context())
        self.assertEqual(statuses(report)[4], "PASS")
        self.assertEqual(statuses(report)[8], "PASS")
        self.assertIn("AccessDenied", report["checks"][3]["detail"])
        self.assertIn("AccessDenied", report["checks"][7]["detail"])

    def test_tagged_create_that_returns_a_group_fails_without_delete(self) -> None:
        fake = happy_aws()
        fake.routes[2] = (
            create_sg(verify.REGION, verify.PROBE_TAGGED_SECURITY_GROUP),
            aws_json({"GroupId": "sg-09999999999999999"}),
        )
        report = verify.run_checks(fake, context())
        self.assertEqual(statuses(report)[4], "FAIL")
        self.assertIn("delete was not called", report["checks"][3]["detail"])
        self.assertEqual(calls_named(fake, "ec2", "delete-security-group"), [])
        self.assertEqual(calls_named(fake, "ec2", "terminate-instances"), [])

    def test_other_region_create_not_found_variant_does_not_pass(self) -> None:
        fake = happy_aws()
        fake.routes[7] = (
            create_sg(verify.OTHER_REGION, verify.PROBE_REGION_SECURITY_GROUP),
            aws_error("InvalidGroup.NotFound", "The security group does not exist"),
        )
        report = verify.run_checks(fake, context())
        self.assertEqual(statuses(report)[8], "FAIL")
        self.assertIn("InvalidGroup.NotFound", report["checks"][7]["detail"])
        self.assertIn("does not pass", report["checks"][7]["detail"])

    def test_dry_run_success_fails_create_check(self) -> None:
        fake = happy_aws()
        fake.routes[3] = (
            starts(verify.REGION, "ec2", "create-security-group"),
            aws_error("DryRunOperation", "Request would have succeeded"),
        )
        report = verify.run_checks(fake, context())
        self.assertEqual(statuses(report)[5], "FAIL")
        self.assertIn("DryRunOperation", report["checks"][4]["detail"])

    def test_created_security_group_fails_without_a_delete(self) -> None:
        fake = happy_aws()
        fake.routes[3] = (
            starts(verify.REGION, "ec2", "create-security-group"),
            aws_json({"GroupId": "sg-09999999999999999"}),
        )
        report = verify.run_checks(fake, context())
        self.assertEqual(statuses(report)[5], "FAIL")
        self.assertEqual(calls_named(fake, "ec2", "delete-security-group"), [])
        self.assertIn("delete was not called", report["checks"][4]["detail"])

    def test_authorized_get_user_fails_without_create_user(self) -> None:
        fake = happy_aws()
        fake.routes[4] = (starts(verify.REGION, "iam", "get-user"), aws_error("NoSuchEntity", "cannot be found"))
        report = verify.run_checks(fake, context())
        self.assertEqual(statuses(report)[6], "FAIL")
        self.assertIn("CreateUser was not called", report["checks"][5]["detail"])
        self.assertEqual(calls_named(fake, "iam", "create-user"), [])
        self.assertEqual(calls_named(fake, "iam", "delete-user"), [])

    def test_billing_success_fails(self) -> None:
        fake = happy_aws()
        fake.routes[5] = (starts(verify.OTHER_REGION, "ce", "get-cost-and-usage"), aws_json({"ResultsByTime": []}))
        report = verify.run_checks(fake, context())
        self.assertEqual(statuses(report)[7], "FAIL")

    def test_other_region_describe_success_fails(self) -> None:
        fake = happy_aws()
        fake.routes[6] = (describe_instances(verify.OTHER_REGION), aws_json(reservations()))
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
        fake.routes[8] = (starts(verify.REGION, "cloudtrail", "lookup-events"), aws_error("AccessDeniedException"))
        report = verify.run_checks(fake, context())
        self.assertEqual(statuses(report)[14], "FAIL")

    def test_session_longer_than_one_hour_fails(self) -> None:
        report = verify.run_checks(happy_aws(), context(expiration="2026-09-28T20:37:16Z"))
        self.assertEqual(statuses(report)[2], "FAIL")
        report = verify.run_checks(happy_aws(), context(requested_duration_seconds=7200))
        self.assertEqual(statuses(report)[2], "FAIL")

    def test_missing_expiration_fails(self) -> None:
        report = verify.run_checks(happy_aws(), context(expiration=""))
        self.assertEqual(statuses(report)[2], "FAIL")
        self.assertEqual(report["overall"], "FAIL")
        self.assertIn("Expiration was not returned", report["checks"][1]["detail"])

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
        self.assertEqual(calls_named(fake, "ec2", "terminate-instances"), [])

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
        fake.add(
            lambda region, args: (
                region == verify.REGION
                and args[:2] == ["ec2", "terminate-instances"]
                and "--dry-run" not in args
                and LAB_INSTANCE in args
            ),
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
        for banned in (
            "run-instances",
            "attach-role-policy",
            "create-access-key",
            "allocate-address",
            "create-key-pair",
            "create-user",
            "delete-user",
            "simulate-principal-policy",
            "i-0deadbeef0deadbee",
        ):
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
            self.assertIn("Prepared policy digest SHA-256 (not a live-measured hash)", summary)
            self.assertEqual(payload["policy_sha256_label"], "prepared_digest")
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
