#!/usr/bin/env python3
"""Verify the W3 lab teardown role from a short-lived OIDC session.

The workflow in .github/workflows/w3-lab-teardown-verify.yml is the only
supported caller. This module does not provision a lab, create access keys,
or change billing. Checks 4, 5, 6, and 8 are non-mutating deny probes.
Checks 4 and 8 use CreateSecurityGroup --dry-run. A NotFound error is not an
authorization pass. Checks 9-13 delete fixtures only when
RUN_DESTRUCTIVE_FIXTURES=true and an id was passed.

Destructive order is settle-first: terminate the instance, wait until it is
terminated, delete the volume once it is available without calling
DetachVolume, release the EIP once AssociationId is gone without calling
DisassociateAddress, retry DeleteSecurityGroup on DependencyViolation, then
delete the key pair. Class B is not authorized. This module does not record
NONINTERACTIVE_TEARDOWN_READY.

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
# GAP-C8-VER-002. TerminateInstances drops the data-volume attachment and the
# EIP association as the instance reaches terminated. The locked policy allows
# DetachVolume on volume/* and DisassociateAddress on elastic-ip/* only.
# Run 36506523073 denied DetachVolume on an instance ARN and DisassociateAddress
# on a network-interface ARN. Those calls are not the primary close path.
# Budgets stay inside the verify job's 20 minute timeout.
SETTLE_POLL_SECONDS = 5.0
INSTANCE_TERMINATED_POLLS = 60
VOLUME_AVAILABLE_POLLS = 24
POST_DETACH_POLLS = 12
EIP_FREE_POLLS = 24
SG_DEPENDENCY_ATTEMPTS = 12
DESTRUCTIVE_EXECUTION_ORDER = ["instance", "volume", "eip", "security_group", "keypair"]
VolumePoll = Literal["ready", "pending", "not_found", "missing", "error"]
AddressPoll = Literal["free", "associated", "not_found", "missing", "error"]

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


def _not_found_code(code: str) -> bool:
    if code == "NotFound" or code.endswith("NotFound"):
        return True
    return code.endswith("NotFoundException")


def is_denied(result: AwsResult) -> bool:
    if result.returncode == 0:
        return False
    code = error_code(result)
    # Existence errors are not authorization, even when the text says
    # "explicit deny" or "not authorized".
    if _not_found_code(code):
        return False
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
    """One JSON object for --tag-specifications.

    AWS CLI v2 treats a value that does not start with '{' or '[' as
    shorthand. A shorthand prefix plus a JSON Tags array fails in
    ShorthandParser (Expected: '=', received: '"') before the API call.
    A value that starts with '{' is parsed as JSON and sent to EC2.
    """
    payload = {
        "ResourceType": "security-group",
        "Tags": [{"Key": key, "Value": value} for key, value in LAB_TAGS.items()],
    }
    return json.dumps(payload, separators=(",", ":"))


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


def _sg_backoff_seconds(failed_attempt: int) -> float:
    schedule = (5.0, 10.0, 15.0, 20.0)
    if failed_attempt < len(schedule):
        return schedule[failed_attempt]
    return 20.0


def _is_dependency_violation(result: AwsResult) -> bool:
    if result.returncode == 0:
        return False
    # The EC2 error code decides. A DependencyViolation is a residual attachment,
    # even when the message text contains words the deny heuristic recognizes.
    if error_code(result) == "DependencyViolation":
        return True
    if is_denied(result) or _not_found_code(error_code(result)):
        return False
    return "DependencyViolation" in f"{result.stderr}\n{result.stdout}"


def _instance_state_name(payload: dict[str, Any]) -> str:
    found = instances_from_describe(payload)
    if not found:
        return ""
    state = found[0].get("State")
    if isinstance(state, dict) and isinstance(state.get("Name"), str):
        return state["Name"]
    return ""


def _wait_instance_terminated(aws: AwsCaller, instance_id: str, sleep: Callable[[float], None]) -> str:
    """Poll until the instance reports terminated.

    An empty return means terminated was observed. "not-found" means describe
    returned NotFound. NotFound does not pass a check. Any other return is a
    short reason the budget ended first.
    """
    last = "unset"
    last_error = ""
    for _ in range(INSTANCE_TERMINATED_POLLS):
        sleep(SETTLE_POLL_SECONDS)
        described = aws(["ec2", "describe-instances", "--instance-ids", instance_id], REGION)
        if described.returncode != 0 or is_denied(described):
            if _not_found_code(error_code(described)):
                return "not-found"
            last_error = failure_detail(described)
            continue
        try:
            payload = parse_json(described)
        except ValueError as exc:
            last_error = str(exc)
            continue
        last = _instance_state_name(payload) or "missing"
        if last == "terminated":
            return ""
    if last == "unset" and last_error:
        return last_error
    return f"state stayed {last}"


def _annotate_instance_settle(item: dict[str, Any], outcome: str) -> None:
    if outcome == "":
        note = "waited until state=terminated before volume, EIP, and security group close"
    elif outcome == "not-found":
        note = "settle describe returned NotFound; NotFound is not a pass and did not authorize the close"
    else:
        note = (
            "settle wait did not observe state=terminated "
            f"({outcome}). Later closes still wait on their own resource state"
        )
    item["detail"] = f"{item['detail']}; {note}"


def _volume_attachments(volume: dict[str, Any]) -> list[Any]:
    attachments = volume.get("Attachments")
    if isinstance(attachments, list):
        return attachments
    return []


def _volume_is_free(volume: dict[str, Any]) -> bool:
    return volume.get("State") == "available" and not _volume_attachments(volume)


def _describe_volume(aws: AwsCaller, volume_id: str) -> tuple[dict[str, Any] | None, str, str]:
    described = aws(["ec2", "describe-volumes", "--volume-ids", volume_id], REGION)
    if described.returncode != 0 or is_denied(described):
        if _not_found_code(error_code(described)):
            return None, "not_found", failure_detail(described)
        return None, "error", failure_detail(described)
    try:
        payload = parse_json(described)
    except ValueError as exc:
        return None, "error", str(exc)
    volumes = payload.get("Volumes")
    if not isinstance(volumes, list) or not volumes or not isinstance(volumes[0], dict):
        return None, "missing", f"{volume_id} was not returned"
    return volumes[0], "ok", ""


def _poll_volume_free(
    aws: AwsCaller,
    volume_id: str,
    sleep: Callable[[float], None],
    polls: int,
) -> tuple[VolumePoll, str]:
    last_state = "unset"
    last_error = ""
    for _ in range(polls):
        sleep(SETTLE_POLL_SECONDS)
        volume, kind, detail = _describe_volume(aws, volume_id)
        if kind == "ok" and volume is not None:
            last_state = str(volume.get("State") or "unset")
            if _volume_is_free(volume):
                return "ready", last_state
            continue
        if kind == "not_found":
            return "not_found", detail
        if kind == "missing":
            return "missing", detail
        last_error = detail
    if last_error and last_state == "unset":
        return "error", last_error
    return "pending", last_state


def _delete_volume(aws: AwsCaller, volume_id: str, note: str) -> dict[str, Any]:
    deleted = aws(["ec2", "delete-volume", "--volume-id", volume_id], REGION)
    if is_denied(deleted) or deleted.returncode != 0:
        return check(10, "close_volume", "FAIL", f"delete failed: {failure_detail(deleted)}")
    return check(10, "close_volume", "PASS", f"DeleteVolume accepted for {volume_id}. {note}")


def _volume_poll_failure(status: VolumePoll, detail: str) -> dict[str, Any] | None:
    if status == "not_found":
        return check(
            10,
            "close_volume",
            "FAIL",
            f"describe during settle returned NotFound, which is not a pass; delete was not called: {detail}",
        )
    if status == "missing":
        return check(10, "close_volume", "FAIL", f"{detail}; delete was not called")
    if status == "error":
        return check(10, "close_volume", "FAIL", f"describe during settle failed; delete was not called: {detail}")
    if status == "ready" or status == "pending":
        return None
    remaining: Never = status
    raise RuntimeError(remaining)


def _detach_volume_last_resort(
    aws: AwsCaller,
    volume_id: str,
    sleep: Callable[[float], None],
    last_state: str,
) -> dict[str, Any]:
    """Call DetachVolume only after the settle wait left the volume attached.

    The locked policy allows DetachVolume on volume/* only. EC2 also authorizes
    the instance ARN, and that resource is outside the Allow. UnauthorizedOperation
    on instance/* is the expected denial when the volume has not become available.
    """
    detached = aws(["ec2", "detach-volume", "--volume-id", volume_id], REGION)
    if is_denied(detached) or detached.returncode != 0:
        return check(
            10,
            "close_volume",
            "FAIL",
            (
                f"volume stayed {last_state} after the settle wait. "
                "DetachVolume was called only after that wait and it failed. "
                "DeleteVolume was not called. "
                "The locked policy allows DetachVolume on volume/* only. "
                "EC2 also authorizes the attached instance ARN, so UnauthorizedOperation "
                "on instance/* is outside that Allow. "
                "This verifier does not widen the policy to Resource:*. "
                f"{failure_detail(detached)}"
            ),
        )
    after, after_detail = _poll_volume_free(aws, volume_id, sleep, POST_DETACH_POLLS)
    failed = _volume_poll_failure(after, after_detail)
    if failed is not None:
        return failed
    if after == "ready":
        return _delete_volume(
            aws,
            volume_id,
            "DetachVolume was required after the settle wait. "
            "The locked policy may deny DetachVolume on the instance ARN.",
        )
    return check(
        10,
        "close_volume",
        "FAIL",
        f"volume stayed {after_detail} after DetachVolume; delete was not called",
    )


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
    volume, kind, detail = _describe_volume(aws, volume_id)
    if kind == "missing":
        return check(10, "close_volume", "FAIL", f"{detail}; delete was not called")
    if kind == "not_found":
        return check(
            10,
            "close_volume",
            "FAIL",
            f"describe returned NotFound, which is not a pass; delete was not called: {detail}",
        )
    if kind != "ok" or volume is None:
        return check(10, "close_volume", "FAIL", f"describe failed; delete was not called: {detail}")
    if not has_tags(tag_map(volume.get("Tags")), VOLUME_TAGS):
        return check(10, "close_volume", "FAIL", f"refused: {volume_id} tags do not match the authorized fixture; delete was not called")
    if _volume_is_free(volume):
        return _delete_volume(
            aws,
            volume_id,
            "DetachVolume was not called because the volume was available with no attachments",
        )
    polled, polled_detail = _poll_volume_free(aws, volume_id, sleep, VOLUME_AVAILABLE_POLLS)
    if polled == "ready":
        return _delete_volume(
            aws,
            volume_id,
            "DetachVolume was not called; the volume became available with no attachments after the settle wait",
        )
    if polled == "pending":
        # DetachVolume is the last resort, and only while an attachment can still
        # be named. Other terminal states (deleting, error, missing) are not detach.
        if polled_detail in {"in-use", "available"}:
            return _detach_volume_last_resort(aws, volume_id, sleep, polled_detail)
        return check(
            10,
            "close_volume",
            "FAIL",
            (
                f"volume stayed {polled_detail} after the settle wait. "
                "DetachVolume was not called. DeleteVolume was not called."
            ),
        )
    held = _volume_poll_failure(polled, polled_detail)
    if held is None:
        raise RuntimeError(f"unhandled volume poll status {polled}")
    return held


def _close_security_group(aws: AwsCaller, group_id: str, sleep: Callable[[float], None]) -> dict[str, Any]:
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
    for attempt in range(SG_DEPENDENCY_ATTEMPTS):
        deleted = aws(["ec2", "delete-security-group", "--group-id", group_id], REGION)
        if deleted.returncode == 0 and not is_denied(deleted):
            if attempt == 0:
                return check(11, "close_security_group", "PASS", f"DeleteSecurityGroup accepted for {group_id}")
            return check(
                11,
                "close_security_group",
                "PASS",
                f"DeleteSecurityGroup accepted for {group_id} after {attempt} DependencyViolation retries",
            )
        if _is_dependency_violation(deleted) and attempt + 1 < SG_DEPENDENCY_ATTEMPTS:
            sleep(_sg_backoff_seconds(attempt))
            continue
        if _is_dependency_violation(deleted):
            return check(
                11,
                "close_security_group",
                "FAIL",
                (
                    f"DeleteSecurityGroup returned DependencyViolation after {SG_DEPENDENCY_ATTEMPTS} attempts. "
                    "That is a residual dependency, not a missing DeleteSecurityGroup IAM grant. "
                    f"{failure_detail(deleted)}"
                ),
            )
        if _not_found_code(error_code(deleted)):
            return check(
                11,
                "close_security_group",
                "FAIL",
                f"delete returned NotFound, which is not a pass: {failure_detail(deleted)}",
            )
        return check(11, "close_security_group", "FAIL", f"delete failed: {failure_detail(deleted)}")
    return check(11, "close_security_group", "FAIL", "delete failed: retry budget ended without a result")


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


def _association_id(address: dict[str, Any]) -> str:
    value = address.get("AssociationId")
    if isinstance(value, str):
        return value.strip()
    return ""


def _describe_address(aws: AwsCaller, allocation_id: str) -> tuple[dict[str, Any] | None, str, str]:
    described = aws(["ec2", "describe-addresses", "--allocation-ids", allocation_id], REGION)
    if described.returncode != 0 or is_denied(described):
        if _not_found_code(error_code(described)):
            return None, "not_found", failure_detail(described)
        return None, "error", failure_detail(described)
    try:
        payload = parse_json(described)
    except ValueError as exc:
        return None, "error", str(exc)
    addresses = payload.get("Addresses")
    if not isinstance(addresses, list) or not addresses or not isinstance(addresses[0], dict):
        return None, "missing", f"{allocation_id} was not returned"
    return addresses[0], "ok", ""


def _poll_eip_free(
    aws: AwsCaller,
    allocation_id: str,
    sleep: Callable[[float], None],
) -> tuple[AddressPoll, str]:
    last_association = "unset"
    last_error = ""
    for _ in range(EIP_FREE_POLLS):
        sleep(SETTLE_POLL_SECONDS)
        address, kind, detail = _describe_address(aws, allocation_id)
        if kind == "ok" and address is not None:
            last_association = _association_id(address)
            if not last_association:
                return "free", ""
            continue
        if kind == "not_found":
            return "not_found", detail
        if kind == "missing":
            return "missing", detail
        last_error = detail
    if last_error and last_association == "unset":
        return "error", last_error
    return "associated", last_association


def _release_address(aws: AwsCaller, allocation_id: str, note: str) -> dict[str, Any]:
    released = aws(["ec2", "release-address", "--allocation-id", allocation_id], REGION)
    if is_denied(released) or released.returncode != 0:
        return check(13, "close_eip", "FAIL", f"release failed: {failure_detail(released)}")
    return check(13, "close_eip", "PASS", f"ReleaseAddress accepted for {allocation_id}. {note}")


def _close_eip(aws: AwsCaller, allocation_id: str, sleep: Callable[[float], None]) -> dict[str, Any]:
    if ALLOCATION_ID.fullmatch(allocation_id) is None:
        return check(13, "close_eip", "FAIL", "refused: allocation id format is invalid; release was not called")
    address, kind, detail = _describe_address(aws, allocation_id)
    if kind == "missing":
        return check(13, "close_eip", "FAIL", f"{detail}; release was not called")
    if kind == "not_found":
        return check(
            13,
            "close_eip",
            "FAIL",
            f"describe returned NotFound, which is not a pass; release was not called: {detail}",
        )
    if kind != "ok" or address is None:
        return check(13, "close_eip", "FAIL", f"describe failed; release was not called: {detail}")
    if not has_tags(tag_map(address.get("Tags")), LAB_TAGS):
        return check(13, "close_eip", "FAIL", f"refused: {allocation_id} tags do not match the authorized fixture; release was not called")
    association = _association_id(address)
    if not association:
        return _release_address(
            aws,
            allocation_id,
            "DisassociateAddress was not called because AssociationId was absent",
        )
    # The locked policy does not allow DisassociateAddress on network-interface/*.
    # Wait for TerminateInstances to drop the association instead of calling it.
    polled, polled_detail = _poll_eip_free(aws, allocation_id, sleep)
    if polled == "free":
        return _release_address(
            aws,
            allocation_id,
            "DisassociateAddress was not called; the association cleared after terminate",
        )
    if polled == "not_found":
        return check(
            13,
            "close_eip",
            "FAIL",
            f"describe during settle returned NotFound, which is not a pass; release was not called: {polled_detail}",
        )
    if polled == "missing":
        return check(13, "close_eip", "FAIL", f"{polled_detail}; release was not called")
    if polled == "error":
        return check(13, "close_eip", "FAIL", f"describe during settle failed; release was not called: {polled_detail}")
    if polled == "associated":
        shown = polled_detail or association
        return check(
            13,
            "close_eip",
            "FAIL",
            (
                f"AssociationId {shown} was still present after the settle wait. "
                "DisassociateAddress was not called. "
                "The locked policy allows DisassociateAddress on elastic-ip/* only. "
                "EC2 also authorizes the network-interface ARN, which this role does not allow. "
                "This verifier does not widen the policy to Resource:*. "
                "ReleaseAddress was not called."
            ),
        )
    remaining: Never = polled
    raise RuntimeError(remaining)


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
    if not ctx.fixture_instance_id:
        instance = _not_run(9, "close_instance", "fixture instance id was not passed")
    else:
        instance = _close_instance(aws, ctx.fixture_instance_id)
        if instance["status"] == "PASS":
            _annotate_instance_settle(
                instance,
                _wait_instance_terminated(aws, ctx.fixture_instance_id, sleep),
            )
    volume = (
        _not_run(10, "close_volume", "fixture volume id was not passed")
        if not ctx.fixture_volume_id
        else _close_volume(aws, ctx.fixture_volume_id, sleep)
    )
    eip = (
        _not_run(13, "close_eip", "fixture allocation id was not passed")
        if not ctx.fixture_eip_allocation_id
        else _close_eip(aws, ctx.fixture_eip_allocation_id, sleep)
    )
    group = (
        _not_run(11, "close_security_group", "fixture security group id was not passed")
        if not ctx.fixture_security_group_id
        else _close_security_group(aws, ctx.fixture_security_group_id, sleep)
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
        "destructive_execution_order": list(DESTRUCTIVE_EXECUTION_ORDER),
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
        "Destructive execution order when fixture ids are passed: instance, volume, EIP, security group, key pair.",
        "Class B is not authorized. This run does not record NONINTERACTIVE_TEARDOWN_READY.",
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
