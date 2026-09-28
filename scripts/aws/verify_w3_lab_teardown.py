#!/usr/bin/env python3
"""Verify the W3 lab teardown role from a short-lived OIDC session.

The workflow in .github/workflows/w3-lab-teardown-verify.yml is the only
supported caller. This module does not provision a lab, create access keys,
or change billing. Checks 4, 5, 6, and 8 are non-mutating deny probes.
Checks 4 and 8 use CreateSecurityGroup --dry-run. A NotFound error is not an
authorization pass. Checks 9-13 delete fixtures only when
RUN_DESTRUCTIVE_FIXTURES=true and an id was passed.

Audience: INTERNAL_RESTRICTED
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Never

ROLE_ARN = "arn:aws:iam::960577828987:role/vantio-w3-lab-teardown"
ROLE_NAME = "vantio-w3-lab-teardown"
ACCOUNT_ID = "960577828987"
REGION = "us-east-2"
OTHER_REGION = "us-east-1"
MAX_SESSION_SECONDS = 3600
SESSION_SKEW_SECONDS = 120
POLICY_SHA256 = "2fd3909fe84cbe93b15c5525ece0d247d0f4f4a91e333346001d512e1efc5215"
AUTHORIZED_KEY_PAIR = "vantio-w3-class-b-lab-01"
REPOSITORY = "vantioai/vantio-open-core"
WORKFLOW_REF = "vantioai/vantio-open-core/.github/workflows/w3-lab-teardown-verify.yml@refs/heads/main"
POLICY_SHA256_LABEL = "prepared_digest"
PROBE_SECURITY_GROUP = "vantio-w3-teardown-verify-deny-probe"
PROBE_TAGGED_SECURITY_GROUP = "vantio-w3-teardown-verify-tagged-deny-probe"
PROBE_REGION_SECURITY_GROUP = "vantio-w3-teardown-verify-region-deny-probe"
PROBE_IAM_USER = "vantio-w3-teardown-verify-deny-probe"
DryRunClass = Literal["denied", "allowed", "not_found", "unexpected"]
SCHEMA = "vantio.w3-lab-teardown-verify.v1"

LAB_TAGS = {
    "vantio:program": "w3-clean-host-lab",
    "vantio:lifecycle": "lab",
    "vantio:destroyable": "true",
    "vantio:environment": "lab",
}
VOLUME_TAGS = {
    **LAB_TAGS,
    "vantio:owned-by": "transaction",
}
STATUSES = {"PASS", "FAIL", "SKIP", "NOT_RUN_AWAITING_FIXTURES", "DOCUMENTED"}
DENY_CODES = {
    "AccessDenied",
    "AccessDeniedException",
    "UnauthorizedOperation",
    "UnauthorizedException",
    "NotAuthorized",
    "AuthFailure",
}
INSTANCE_ID = re.compile(r"^i-[0-9a-f]{8,17}$")
VOLUME_ID = re.compile(r"^vol-[0-9a-f]{8,17}$")
SECURITY_GROUP_ID = re.compile(r"^sg-[0-9a-f]{8,17}$")
ALLOCATION_ID = re.compile(r"^eipalloc-[0-9a-f]{8,17}$")
_ERROR_CODE = re.compile(r"\(([A-Za-z0-9.]+)\)")
_ACCESS_KEY = re.compile(r"\b(?:ASIA|AKIA)[A-Z0-9]{16}\b")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(aws_secret_access_key|aws_session_token|sessionToken)(['\"]?\s*[:=]\s*['\"]?)[^\s'\"]+"
)

AwsCaller = Callable[[list[str], str], "AwsResult"]


@dataclass
class AwsResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class Context:
    now: datetime
    expiration: str
    requested_duration_seconds: int | None
    run_destructive: bool
    fixture_instance_id: str
    fixture_volume_id: str
    fixture_security_group_id: str
    fixture_keypair_name: str
    fixture_eip_allocation_id: str
    role_session_name: str
    repository: str
    run_id: str
    run_attempt: str
    assume_outcome: str
    action_account_id: str
    action_arn: str
    access_key_id: str


def redact(text: str) -> str:
    redacted = _ACCESS_KEY.sub(lambda match: match.group(0)[:4] + "****************", text)
    return _SECRET_ASSIGNMENT.sub(r"\1\2<redacted>", redacted)


def brief(text: str, limit: int = 500) -> str:
    collapsed = redact(" ".join(text.split()))
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3] + "..."


def check(check_id: int, name: str, status: str, detail: str) -> dict[str, Any]:
    if status not in STATUSES:
        raise ValueError(f"unknown status {status}")
    return {"id": check_id, "name": name, "status": status, "detail": brief(detail)}


def error_code(result: AwsResult) -> str:
    match = _ERROR_CODE.search(f"{result.stderr}\n{result.stdout}")
    if match is None:
        return ""
    return match.group(1)


def is_denied(result: AwsResult) -> bool:
    if result.returncode == 0:
        return False
    code = error_code(result)
    if code in DENY_CODES:
        return True
    lowered = f"{result.stderr}\n{result.stdout}".lower()
    return "explicit deny" in lowered or "not authorized" in lowered


def failure_detail(result: AwsResult) -> str:
    code = error_code(result)
    body = brief(result.stderr or result.stdout or "aws returned no output")
    if code:
        return f"{code}: {body}"
    return f"exit {result.returncode}: {body}"


def parse_json(result: AwsResult) -> dict[str, Any]:
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"aws output was not JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("aws output was not a JSON object")
    return payload


def tag_map(tags: Any) -> dict[str, str]:
    found: dict[str, str] = {}
    if not isinstance(tags, list):
        return found
    for item in tags:
        if isinstance(item, dict) and isinstance(item.get("Key"), str):
            value = item.get("Value")
            found[item["Key"]] = value if isinstance(value, str) else ""
    return found


def has_tags(tags: dict[str, str], required: dict[str, str]) -> bool:
    return all(tags.get(key) == value for key, value in required.items())


def instances_from_describe(payload: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    reservations = payload.get("Reservations")
    if not isinstance(reservations, list):
        return found
    for reservation in reservations:
        if not isinstance(reservation, dict):
            continue
        instances = reservation.get("Instances")
        if not isinstance(instances, list):
            continue
        for instance in instances:
            if isinstance(instance, dict):
                found.append(instance)
    return found


def is_authorized_instance(instance: dict[str, Any]) -> bool:
    return has_tags(tag_map(instance.get("Tags")), LAB_TAGS)


def _not_found_code(code: str) -> bool:
    return code.endswith("NotFound")


def classify_dry_run(result: AwsResult) -> DryRunClass:
    """Classify a non-mutating dry-run.

    NotFound is decided before the deny text search. A missing id is not
    AccessDenied, UnauthorizedOperation, or DryRunOperation, even when the
    error text contains words like "not authorized".
    """
    code = error_code(result)
    if _not_found_code(code):
        return "not_found"
    if is_denied(result):
        return "denied"
    if result.returncode == 0 or code == "DryRunOperation":
        return "allowed"
    return "unexpected"


def security_group_tag_specification() -> str:
    tags = ",".join(f'{{"Key":"{key}","Value":"{value}"}}' for key, value in LAB_TAGS.items())
    return f"ResourceType=security-group,Tags=[{tags}]"


def create_security_group_dry_run_args(group_name: str, *, with_lab_tags: bool) -> list[str]:
    args = [
        "ec2",
        "create-security-group",
        "--group-name",
        group_name,
        "--description",
        "OIDC verify probe; must be denied",
    ]
    if with_lab_tags:
        args.extend(["--tag-specifications", security_group_tag_specification()])
    args.append("--dry-run")
    return args


def _created_group_suffix(result: AwsResult) -> str:
    if result.returncode != 0:
        return ""
    group_id = ""
    try:
        payload = parse_json(result)
    except ValueError:
        payload = {}
    if isinstance(payload.get("GroupId"), str):
        group_id = payload["GroupId"]
    if not group_id:
        return ""
    return f"; GroupId={group_id}; delete was not called"


def finish_create_dry_run(
    check_id: int,
    name: str,
    result: AwsResult,
    label: str,
    *,
    nonmutation_note: str = "",
) -> dict[str, Any]:
    outcome = classify_dry_run(result)
    note = f" {nonmutation_note}" if nonmutation_note else ""
    if outcome == "denied":
        if nonmutation_note:
            denied = f"{label} was denied. {nonmutation_note} {failure_detail(result)}"
        else:
            denied = f"{label} was denied: {failure_detail(result)}"
        return check(check_id, name, "PASS", denied)
    if outcome == "allowed":
        code = error_code(result) or "success"
        return check(
            check_id,
            name,
            "FAIL",
            f"{label} would have been allowed ({code}){note}{_created_group_suffix(result)}",
        )
    if outcome == "not_found":
        found = error_code(result) or "NotFound"
        return check(
            check_id,
            name,
            "FAIL",
            (
                f"{label} returned {found}, which is not an authorization result and does not pass."
                f"{note} {failure_detail(result)}"
            ),
        )
    if outcome == "unexpected":
        return check(
            check_id,
            name,
            "FAIL",
            f"{label} was not an access denial.{note} {failure_detail(result)}",
        )
    remaining: Never = outcome
    raise RuntimeError(remaining)


def parse_time(value: str) -> datetime:
    text = value.strip().strip('"').strip("'")
    text = re.sub(r"\s*\([^)]*\)$", "", text).strip()
    iso = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(iso)
    except ValueError:
        cleaned = text.replace("GMT", "")
        parsed = datetime.strptime(cleaned, "%a %b %d %Y %H:%M:%S %z")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def identity_matches(arn: str, account: str) -> bool:
    if account != ACCOUNT_ID:
        return False
    assumed = f":assumed-role/{ROLE_NAME}/"
    role = f":role/{ROLE_NAME}"
    return assumed in arn or arn.endswith(role)


def format_line(item: dict[str, Any]) -> str:
    return f"CHECK {int(item['id']):02d} {item['status']} {item['name']}: {item['detail']}"


def aws_cli(args: list[str], region: str) -> AwsResult:
    command = ["aws", "--region", region, "--output", "json", "--no-cli-pager", *args]
    env = os.environ.copy()
    env["AWS_PAGER"] = ""
    env["AWS_CLI_AUTO_PROMPT"] = "off"
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        return AwsResult(124, stdout, "aws cli timed out after 60s")
    except FileNotFoundError:
        return AwsResult(127, "", "aws cli is not installed on this runner")
    return AwsResult(completed.returncode, completed.stdout, completed.stderr)


def enforce_github_identity() -> None:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    ref = os.environ.get("GITHUB_REF", "")
    workflow_ref = os.environ.get("GITHUB_WORKFLOW_REF", "")
    if (
        repository != REPOSITORY
        or event != "workflow_dispatch"
        or ref != "refs/heads/main"
        or workflow_ref != WORKFLOW_REF
    ):
        raise SystemExit(
            "CHECK 01 FAIL assume_session: workflow identity is "
            f"repo={repository or 'unset'} event={event or 'unset'} ref={ref or 'unset'} "
            f"workflow_ref={workflow_ref or 'unset'}"
        )


def context_from_environ(now: datetime | None = None) -> Context:
    raw_duration = os.environ.get("REQUESTED_ROLE_DURATION_SECONDS", "").strip()
    try:
        duration: int | None = int(raw_duration)
    except ValueError:
        duration = None
    moment = now if now is not None else datetime.now(timezone.utc)
    return Context(
        now=moment,
        expiration=os.environ.get("W3_AWS_EXPIRATION", "").strip(),
        requested_duration_seconds=duration,
        run_destructive=os.environ.get("RUN_DESTRUCTIVE_FIXTURES", "").strip() == "true",
        fixture_instance_id=os.environ.get("FIXTURE_INSTANCE_ID", "").strip(),
        fixture_volume_id=os.environ.get("FIXTURE_VOLUME_ID", "").strip(),
        fixture_security_group_id=os.environ.get("FIXTURE_SECURITY_GROUP_ID", "").strip(),
        fixture_keypair_name=os.environ.get("FIXTURE_KEYPAIR_NAME", "").strip(),
        fixture_eip_allocation_id=os.environ.get("FIXTURE_EIP_ALLOCATION_ID", "").strip(),
        role_session_name=os.environ.get("ROLE_SESSION_NAME", "").strip(),
        repository=os.environ.get("GITHUB_REPOSITORY", ""),
        run_id=os.environ.get("GITHUB_RUN_ID", ""),
        run_attempt=os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        assume_outcome=os.environ.get("AWS_CONFIGURE_OUTCOME", "").strip(),
        action_account_id=os.environ.get("W3_ACTION_ACCOUNT_ID", "").strip(),
        action_arn=os.environ.get("W3_ACTION_ARN", "").strip(),
        access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "").strip(),
    )


def check_identity(aws: AwsCaller, ctx: Context) -> tuple[bool, dict[str, Any], dict[str, str] | None]:
    if ctx.assume_outcome and ctx.assume_outcome != "success":
        return False, check(
            1,
            "assume_session",
            "FAIL",
            f"configure-aws-credentials outcome was {ctx.assume_outcome}; no teardown session was used",
        ), None
    result = aws(["sts", "get-caller-identity"], REGION)
    if result.returncode != 0:
        return False, check(1, "assume_session", "FAIL", f"sts get-caller-identity failed: {failure_detail(result)}"), None
    try:
        payload = parse_json(result)
    except ValueError as exc:
        return False, check(1, "assume_session", "FAIL", str(exc)), None
    account = payload.get("Account") if isinstance(payload.get("Account"), str) else ""
    arn = payload.get("Arn") if isinstance(payload.get("Arn"), str) else ""
    user_id = payload.get("UserId") if isinstance(payload.get("UserId"), str) else ""
    caller = {"account": account, "arn": arn, "user_id": user_id}
    if not identity_matches(arn, account):
        return False, check(
            1,
            "assume_session",
            "FAIL",
            f"caller account={account or 'unset'} arn={arn or 'unset'} is not {ROLE_NAME} in {ACCOUNT_ID}",
        ), caller
    if ctx.action_account_id and ctx.action_account_id != account:
        return False, check(
            1,
            "assume_session",
            "FAIL",
            f"credentials action account {ctx.action_account_id} disagrees with sts account {account}",
        ), caller
    if ctx.action_arn and ctx.action_arn != arn:
        return False, check(
            1,
            "assume_session",
            "FAIL",
            f"credentials action arn {ctx.action_arn} disagrees with sts arn {arn}",
        ), caller
    return True, check(
        1,
        "assume_session",
        "PASS",
        f"account={account} arn={arn} session={ctx.role_session_name or 'unset'}",
    ), caller


def check_duration(ctx: Context) -> dict[str, Any]:
    note = (
        f"requested role-duration-seconds={ctx.requested_duration_seconds}; "
        f"role MaxSessionDuration recorded as {MAX_SESSION_SECONDS} "
        "(not read via iam:GetRole; that API is outside this role)"
    )
    requested = ctx.requested_duration_seconds
    if requested is None or requested <= 0 or requested > MAX_SESSION_SECONDS:
        return check(2, "session_duration", "FAIL", note)
    if not ctx.expiration:
        return check(2, "session_duration", "FAIL", note + "; Expiration was not returned by the assume step")
    try:
        expires = parse_time(ctx.expiration)
    except ValueError:
        return check(2, "session_duration", "FAIL", note + f"; Expiration {ctx.expiration!r} could not be parsed")
    remaining = (expires - ctx.now).total_seconds()
    if remaining <= 0:
        return check(2, "session_duration", "FAIL", note + f"; Expiration {ctx.expiration} is not in the future")
    if remaining > MAX_SESSION_SECONDS + SESSION_SKEW_SECONDS:
        return check(
            2,
            "session_duration",
            "FAIL",
            note + f"; Expiration is {int(remaining)}s ahead, above {MAX_SESSION_SECONDS}s",
        )
    return check(
        2,
        "session_duration",
        "PASS",
        note + f"; Expiration={ctx.expiration}; seconds_remaining={int(remaining)}",
    )


def check_describe_lab(aws: AwsCaller) -> dict[str, Any]:
    result = aws(
        [
            "ec2",
            "describe-instances",
            "--filters",
            "Name=tag:vantio:program,Values=w3-clean-host-lab",
            "Name=tag:vantio:lifecycle,Values=lab",
            "Name=tag:vantio:destroyable,Values=true",
            "Name=tag:vantio:environment,Values=lab",
        ],
        REGION,
    )
    if is_denied(result):
        return check(3, "describe_lab_instances", "FAIL", f"DescribeInstances was denied: {failure_detail(result)}")
    if result.returncode != 0:
        return check(3, "describe_lab_instances", "FAIL", f"DescribeInstances failed: {failure_detail(result)}")
    try:
        instances = instances_from_describe(parse_json(result))
    except ValueError as exc:
        return check(3, "describe_lab_instances", "FAIL", str(exc))
    ids = [item.get("InstanceId") for item in instances if isinstance(item.get("InstanceId"), str)]
    shown = ", ".join(str(item) for item in ids[:20]) or "none"
    return check(
        3,
        "describe_lab_instances",
        "PASS",
        f"DescribeInstances in {REGION} succeeded; authorized lab-tagged instance count={len(ids)}; ids={shown}",
    )


def check_deny_tagged_create(aws: AwsCaller) -> dict[str, Any]:
    result = aws(
        create_security_group_dry_run_args(PROBE_TAGGED_SECURITY_GROUP, with_lab_tags=True),
        REGION,
    )
    return finish_create_dry_run(
        4,
        "deny_tagged_create",
        result,
        (
            f"CreateSecurityGroup --dry-run for {PROBE_TAGGED_SECURITY_GROUP} "
            f"with lab tags in {REGION}"
        ),
        nonmutation_note="TerminateInstances was not called.",
    )


def check_deny_create(aws: AwsCaller) -> dict[str, Any]:
    result = aws(create_security_group_dry_run_args(PROBE_SECURITY_GROUP, with_lab_tags=False), REGION)
    return finish_create_dry_run(5, "deny_create_ec2", result, "CreateSecurityGroup --dry-run")


def check_deny_iam(aws: AwsCaller) -> dict[str, Any]:
    result = aws(["iam", "get-user", "--user-name", PROBE_IAM_USER], REGION)
    if is_denied(result):
        return check(6, "deny_iam_mutation", "PASS", f"iam:GetUser on {PROBE_IAM_USER} was denied: {failure_detail(result)}")
    if error_code(result) == "NoSuchEntity" or result.returncode == 0:
        return check(
            6,
            "deny_iam_mutation",
            "FAIL",
            f"iam:GetUser on {PROBE_IAM_USER} was authorized; CreateUser was not called",
        )
    return check(6, "deny_iam_mutation", "FAIL", f"iam:GetUser was not an access denial: {failure_detail(result)}")


def check_deny_billing(aws: AwsCaller) -> dict[str, Any]:
    result = aws(
        [
            "ce",
            "get-cost-and-usage",
            "--time-period",
            "Start=2026-09-01,End=2026-09-02",
            "--granularity",
            "MONTHLY",
            "--metrics",
            "UnblendedCost",
        ],
        OTHER_REGION,
    )
    if is_denied(result):
        return check(
            7,
            "deny_billing",
            "PASS",
            "ce:GetCostAndUsage was denied. This probe is a non-mutating billing read. "
            f"No support plan or payment method was changed. {failure_detail(result)}",
        )
    if result.returncode == 0:
        return check(7, "deny_billing", "FAIL", "ce:GetCostAndUsage returned success; billing read was allowed")
    return check(7, "deny_billing", "FAIL", f"ce:GetCostAndUsage was not an access denial: {failure_detail(result)}")


def check_deny_other_region(aws: AwsCaller) -> dict[str, Any]:
    describe = aws(["ec2", "describe-instances"], OTHER_REGION)
    create = aws(
        create_security_group_dry_run_args(PROBE_REGION_SECURITY_GROUP, with_lab_tags=False),
        OTHER_REGION,
    )
    describe_denied = is_denied(describe)
    outcome = classify_dry_run(create)
    if describe_denied and outcome == "denied":
        return check(
            8,
            "deny_outside_us_east_2",
            "PASS",
            f"{OTHER_REGION} describe was denied ({error_code(describe) or 'denied'}) and "
            f"CreateSecurityGroup --dry-run was denied ({error_code(create) or 'denied'}). "
            "TerminateInstances was not called.",
        )
    parts: list[str] = []
    if not describe_denied:
        if describe.returncode == 0:
            parts.append(f"{OTHER_REGION} describe-instances was allowed")
        else:
            parts.append(f"{OTHER_REGION} describe-instances was not an access denial: {failure_detail(describe)}")
    if outcome == "allowed":
        code = error_code(create) or "success"
        parts.append(
            f"{OTHER_REGION} CreateSecurityGroup --dry-run would have been allowed ({code}){_created_group_suffix(create)}"
        )
    elif outcome == "not_found":
        found = error_code(create) or "NotFound"
        parts.append(
            f"{OTHER_REGION} CreateSecurityGroup --dry-run returned {found}, "
            "which is not an authorization result and does not pass: "
            f"{failure_detail(create)}"
        )
    elif outcome == "unexpected":
        parts.append(f"{OTHER_REGION} CreateSecurityGroup --dry-run was not an access denial: {failure_detail(create)}")
    elif outcome == "denied":
        pass
    else:
        remaining: Never = outcome
        raise RuntimeError(remaining)
    return check(8, "deny_outside_us_east_2", "FAIL", "; ".join(parts))


def _not_run(check_id: int, name: str, detail: str) -> dict[str, Any]:
    return check(check_id, name, "NOT_RUN_AWAITING_FIXTURES", detail)


def _close_instance(aws: AwsCaller, instance_id: str) -> dict[str, Any]:
    if INSTANCE_ID.fullmatch(instance_id) is None:
        return check(9, "close_instance", "FAIL", "refused: instance id format is invalid; terminate was not called")
    described = aws(["ec2", "describe-instances", "--instance-ids", instance_id], REGION)
    if is_denied(described) or described.returncode != 0:
        return check(9, "close_instance", "FAIL", f"describe failed; terminate was not called: {failure_detail(described)}")
    try:
        instances = instances_from_describe(parse_json(described))
    except ValueError as exc:
        return check(9, "close_instance", "FAIL", f"{exc}; terminate was not called")
    if not instances:
        return check(9, "close_instance", "FAIL", f"{instance_id} was not returned; terminate was not called")
    instance = instances[0]
    if not is_authorized_instance(instance):
        return check(9, "close_instance", "FAIL", f"refused: {instance_id} tags do not match the authorized fixture; terminate was not called")
    terminated = aws(["ec2", "terminate-instances", "--instance-ids", instance_id], REGION)
    if is_denied(terminated) or terminated.returncode != 0:
        return check(9, "close_instance", "FAIL", f"terminate failed: {failure_detail(terminated)}")
    return check(9, "close_instance", "PASS", f"TerminateInstances accepted for {instance_id}")


def _close_volume(aws: AwsCaller, volume_id: str, sleep: Callable[[float], None]) -> dict[str, Any]:
    if VOLUME_ID.fullmatch(volume_id) is None:
        return check(10, "close_volume", "FAIL", "refused: volume id format is invalid; delete was not called")
    described = aws(["ec2", "describe-volumes", "--volume-ids", volume_id], REGION)
    if is_denied(described) or described.returncode != 0:
        return check(10, "close_volume", "FAIL", f"describe failed; delete was not called: {failure_detail(described)}")
    try:
        payload = parse_json(described)
    except ValueError as exc:
        return check(10, "close_volume", "FAIL", f"{exc}; delete was not called")
    volumes = payload.get("Volumes")
    if not isinstance(volumes, list) or not volumes or not isinstance(volumes[0], dict):
        return check(10, "close_volume", "FAIL", f"{volume_id} was not returned; delete was not called")
    volume = volumes[0]
    if not has_tags(tag_map(volume.get("Tags")), VOLUME_TAGS):
        return check(10, "close_volume", "FAIL", f"refused: {volume_id} tags do not match the authorized fixture; delete was not called")
    attachments = volume.get("Attachments") if isinstance(volume.get("Attachments"), list) else []
    if volume.get("State") != "available" or attachments:
        detached = aws(["ec2", "detach-volume", "--volume-id", volume_id], REGION)
        if is_denied(detached) or detached.returncode != 0:
            return check(10, "close_volume", "FAIL", f"detach failed; delete was not called: {failure_detail(detached)}")
        ready = False
        last_state = str(volume.get("State") or "unset")
        for _ in range(12):
            sleep(5)
            again = aws(["ec2", "describe-volumes", "--volume-ids", volume_id], REGION)
            if is_denied(again) or again.returncode != 0:
                return check(10, "close_volume", "FAIL", f"describe after detach failed: {failure_detail(again)}")
            try:
                follow = parse_json(again)
            except ValueError as exc:
                return check(10, "close_volume", "FAIL", str(exc))
            found = follow.get("Volumes")
            if not isinstance(found, list) or not found or not isinstance(found[0], dict):
                return check(10, "close_volume", "FAIL", f"{volume_id} disappeared after detach; delete was not called")
            last_state = str(found[0].get("State") or "unset")
            still_attached = found[0].get("Attachments") if isinstance(found[0].get("Attachments"), list) else []
            if last_state == "available" and not still_attached:
                ready = True
                break
        if not ready:
            return check(10, "close_volume", "FAIL", f"volume stayed {last_state}; delete was not called")
    deleted = aws(["ec2", "delete-volume", "--volume-id", volume_id], REGION)
    if is_denied(deleted) or deleted.returncode != 0:
        return check(10, "close_volume", "FAIL", f"delete failed: {failure_detail(deleted)}")
    return check(10, "close_volume", "PASS", f"DeleteVolume accepted for {volume_id}")


def _close_security_group(aws: AwsCaller, group_id: str) -> dict[str, Any]:
    if SECURITY_GROUP_ID.fullmatch(group_id) is None:
        return check(11, "close_security_group", "FAIL", "refused: security group id format is invalid; delete was not called")
    described = aws(["ec2", "describe-security-groups", "--group-ids", group_id], REGION)
    if is_denied(described) or described.returncode != 0:
        return check(11, "close_security_group", "FAIL", f"describe failed; delete was not called: {failure_detail(described)}")
    try:
        payload = parse_json(described)
    except ValueError as exc:
        return check(11, "close_security_group", "FAIL", f"{exc}; delete was not called")
    groups = payload.get("SecurityGroups")
    if not isinstance(groups, list) or not groups or not isinstance(groups[0], dict):
        return check(11, "close_security_group", "FAIL", f"{group_id} was not returned; delete was not called")
    group = groups[0]
    if group.get("GroupName") == "default":
        return check(11, "close_security_group", "FAIL", "refused: default security group; delete was not called")
    if not has_tags(tag_map(group.get("Tags")), LAB_TAGS):
        return check(11, "close_security_group", "FAIL", f"refused: {group_id} tags do not match the authorized fixture; delete was not called")
    deleted = aws(["ec2", "delete-security-group", "--group-id", group_id], REGION)
    if is_denied(deleted) or deleted.returncode != 0:
        return check(11, "close_security_group", "FAIL", f"delete failed: {failure_detail(deleted)}")
    return check(11, "close_security_group", "PASS", f"DeleteSecurityGroup accepted for {group_id}")


def _close_keypair(aws: AwsCaller, key_name: str) -> dict[str, Any]:
    if key_name != AUTHORIZED_KEY_PAIR:
        return check(
            12,
            "close_keypair",
            "FAIL",
            f"refused: key pair name is not {AUTHORIZED_KEY_PAIR}; delete was not called",
        )
    described = aws(["ec2", "describe-key-pairs", "--key-names", key_name], REGION)
    if is_denied(described) or described.returncode != 0:
        return check(12, "close_keypair", "FAIL", f"describe failed; delete was not called: {failure_detail(described)}")
    deleted = aws(["ec2", "delete-key-pair", "--key-name", key_name], REGION)
    if is_denied(deleted) or deleted.returncode != 0:
        return check(12, "close_keypair", "FAIL", f"delete failed: {failure_detail(deleted)}")
    return check(12, "close_keypair", "PASS", f"DeleteKeyPair accepted for {key_name}")


def _close_eip(aws: AwsCaller, allocation_id: str) -> dict[str, Any]:
    if ALLOCATION_ID.fullmatch(allocation_id) is None:
        return check(13, "close_eip", "FAIL", "refused: allocation id format is invalid; release was not called")
    described = aws(["ec2", "describe-addresses", "--allocation-ids", allocation_id], REGION)
    if is_denied(described) or described.returncode != 0:
        return check(13, "close_eip", "FAIL", f"describe failed; release was not called: {failure_detail(described)}")
    try:
        payload = parse_json(described)
    except ValueError as exc:
        return check(13, "close_eip", "FAIL", f"{exc}; release was not called")
    addresses = payload.get("Addresses")
    if not isinstance(addresses, list) or not addresses or not isinstance(addresses[0], dict):
        return check(13, "close_eip", "FAIL", f"{allocation_id} was not returned; release was not called")
    address = addresses[0]
    if not has_tags(tag_map(address.get("Tags")), LAB_TAGS):
        return check(13, "close_eip", "FAIL", f"refused: {allocation_id} tags do not match the authorized fixture; release was not called")
    association_id = address.get("AssociationId")
    if isinstance(association_id, str) and association_id:
        disassociated = aws(["ec2", "disassociate-address", "--association-id", association_id], REGION)
        if is_denied(disassociated) or disassociated.returncode != 0:
            return check(13, "close_eip", "FAIL", f"disassociate failed; release was not called: {failure_detail(disassociated)}")
    released = aws(["ec2", "release-address", "--allocation-id", allocation_id], REGION)
    if is_denied(released) or released.returncode != 0:
        return check(13, "close_eip", "FAIL", f"release failed: {failure_detail(released)}")
    return check(13, "close_eip", "PASS", f"ReleaseAddress accepted for {allocation_id}")


def check_destructive(aws: AwsCaller, ctx: Context, sleep: Callable[[float], None]) -> list[dict[str, Any]]:
    waiting = "RUN_DESTRUCTIVE_FIXTURES is not true"
    if not ctx.run_destructive:
        return [
            _not_run(9, "close_instance", waiting),
            _not_run(10, "close_volume", waiting),
            _not_run(11, "close_security_group", waiting),
            _not_run(12, "close_keypair", waiting),
            _not_run(13, "close_eip", waiting),
        ]
    eip = (
        _not_run(13, "close_eip", "fixture allocation id was not passed")
        if not ctx.fixture_eip_allocation_id
        else _close_eip(aws, ctx.fixture_eip_allocation_id)
    )
    instance = (
        _not_run(9, "close_instance", "fixture instance id was not passed")
        if not ctx.fixture_instance_id
        else _close_instance(aws, ctx.fixture_instance_id)
    )
    volume = (
        _not_run(10, "close_volume", "fixture volume id was not passed")
        if not ctx.fixture_volume_id
        else _close_volume(aws, ctx.fixture_volume_id, sleep)
    )
    group = (
        _not_run(11, "close_security_group", "fixture security group id was not passed")
        if not ctx.fixture_security_group_id
        else _close_security_group(aws, ctx.fixture_security_group_id)
    )
    keypair = (
        _not_run(12, "close_keypair", "fixture key pair name was not passed")
        if not ctx.fixture_keypair_name
        else _close_keypair(aws, ctx.fixture_keypair_name)
    )
    return [instance, volume, group, keypair, eip]


def check_cloudtrail(aws: AwsCaller, ctx: Context) -> dict[str, Any]:
    if not ctx.access_key_id:
        return check(14, "cloudtrail_lookup", "FAIL", "session access key id was not in the environment; LookupEvents was not called")
    result = aws(
        [
            "cloudtrail",
            "lookup-events",
            "--lookup-attributes",
            f"AttributeKey=AccessKeyId,AttributeValue={ctx.access_key_id}",
            "--max-results",
            "50",
        ],
        REGION,
    )
    if is_denied(result):
        return check(14, "cloudtrail_lookup", "FAIL", f"cloudtrail:LookupEvents was denied: {failure_detail(result)}")
    if result.returncode != 0:
        return check(14, "cloudtrail_lookup", "FAIL", f"cloudtrail:LookupEvents failed: {failure_detail(result)}")
    try:
        payload = parse_json(result)
    except ValueError as exc:
        return check(14, "cloudtrail_lookup", "FAIL", str(exc))
    events = payload.get("Events")
    count = len(events) if isinstance(events, list) else 0
    note = "empty is expected when CloudTrail has not ingested this session yet" if count == 0 else "events were returned"
    return check(
        14,
        "cloudtrail_lookup",
        "PASS",
        f"LookupEvents in {REGION} succeeded by session access key (redacted); event_count={count}; {note}",
    )


def check_expiry_note(ctx: Context) -> dict[str, Any]:
    expiration = ctx.expiration or "not recorded"
    return check(
        15,
        "session_expiry_note",
        "DOCUMENTED",
        "STS session credentials are temporary. "
        f"Expiration={expiration}. "
        "This job cannot prove the credentials are unusable after it ends, because they remain valid until Expiration. "
        "configure-aws-credentials clears the environment variables in its post step. "
        "This workflow does not create a long-lived access key.",
    )


def blocked_after_identity(ctx: Context) -> list[dict[str, Any]]:
    reason = "not attempted; caller identity did not match the teardown role"
    blocked = [
        check(3, "describe_lab_instances", "FAIL", reason),
        check(4, "deny_tagged_create", "FAIL", reason),
        check(5, "deny_create_ec2", "FAIL", reason),
        check(6, "deny_iam_mutation", "FAIL", reason),
        check(7, "deny_billing", "FAIL", reason),
        check(8, "deny_outside_us_east_2", "FAIL", reason),
        check(14, "cloudtrail_lookup", "FAIL", reason),
    ]
    if ctx.run_destructive:
        blocked.extend(
            [
                check(9, "close_instance", "FAIL", reason),
                check(10, "close_volume", "FAIL", reason),
                check(11, "close_security_group", "FAIL", reason),
                check(12, "close_keypair", "FAIL", reason),
                check(13, "close_eip", "FAIL", reason),
            ]
        )
    else:
        waiting = "RUN_DESTRUCTIVE_FIXTURES is not true"
        blocked.extend(
            [
                _not_run(9, "close_instance", waiting),
                _not_run(10, "close_volume", waiting),
                _not_run(11, "close_security_group", waiting),
                _not_run(12, "close_keypair", waiting),
                _not_run(13, "close_eip", waiting),
            ]
        )
    return blocked


def run_checks(aws: AwsCaller, ctx: Context, *, sleep: Callable[[float], None] = time.sleep) -> dict[str, Any]:
    identity_ok, identity_check, caller = check_identity(aws, ctx)
    items = [identity_check, check_duration(ctx)]
    if identity_ok:
        items.append(check_describe_lab(aws))
        items.append(check_deny_tagged_create(aws))
        items.append(check_deny_create(aws))
        items.append(check_deny_iam(aws))
        items.append(check_deny_billing(aws))
        items.append(check_deny_other_region(aws))
        items.extend(check_destructive(aws, ctx, sleep))
        items.append(check_cloudtrail(aws, ctx))
    else:
        items.extend(blocked_after_identity(ctx))
    items.append(check_expiry_note(ctx))
    items.sort(key=lambda item: int(item["id"]))
    if [int(item["id"]) for item in items] != list(range(1, 16)):
        raise RuntimeError("verification report did not contain checks 1 through 15")
    overall = "FAIL" if any(item["status"] == "FAIL" for item in items) else "PASS"
    return {
        "schema": SCHEMA,
        "generated_at": ctx.now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repository": ctx.repository,
        "run_id": ctx.run_id,
        "run_attempt": ctx.run_attempt,
        "role_arn": ROLE_ARN,
        "role_session_name": ctx.role_session_name,
        "account_id": ACCOUNT_ID,
        "region": REGION,
        "requested_duration_seconds": ctx.requested_duration_seconds,
        "role_max_session_duration_seconds": MAX_SESSION_SECONDS,
        "session_expiration": ctx.expiration or None,
        "policy_sha256": POLICY_SHA256,
        "policy_sha256_label": POLICY_SHA256_LABEL,
        "authorized_key_pair": AUTHORIZED_KEY_PAIR,
        "run_destructive_fixtures": ctx.run_destructive,
        "destructive_execution_order": ["eip", "instance", "volume", "security_group", "keypair"],
        "caller": caller,
        "checks": items,
        "overall": overall,
    }


def summary_markdown(report: dict[str, Any]) -> str:
    lines = [
        "## W3 lab teardown role verification",
        "",
        f"Overall: **{report['overall']}**",
        "",
        f"Role `{report['role_arn']}` in `{report['region']}`.",
        f"Prepared policy digest SHA-256 (not a live-measured hash) `{report['policy_sha256']}`.",
        f"Session expiration: `{report['session_expiration'] or 'not recorded'}`.",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for item in report["checks"]:
        detail = str(item["detail"]).replace("|", "/")
        lines.append(f"| {int(item['id']):02d} {item['name']} | {item['status']} | {detail} |")
    lines.append("")
    return "\n".join(lines)


def emit(report: dict[str, Any], path: str, summary_path: str | None) -> None:
    rendered = json.dumps(report, indent=2) + "\n"
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(rendered)
    for item in report["checks"]:
        print(format_line(item), flush=True)
    print(f"OVERALL {report['overall']}", flush=True)
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write(summary_markdown(report))


def main(argv: list[str] | None = None, aws: AwsCaller | None = None) -> int:
    del argv
    enforce_github_identity()
    ctx = context_from_environ()
    report = run_checks(aws or aws_cli, ctx)
    result_path = os.environ.get("VERIFY_RESULT_PATH", "w3-lab-teardown-verify.json")
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip() or None
    emit(report, result_path, summary_path)
    if report["overall"] == "PASS":
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
