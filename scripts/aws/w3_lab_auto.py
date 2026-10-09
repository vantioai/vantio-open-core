#!/usr/bin/env python3
"""Free-plan lab decisions for account 960577828987.

Launch and sweep call AWS only after the Free-plan gate, the account check,
and the tag checks pass. Cost Explorer is never called. Account
934814114565 is never used. NONINTERACTIVE_TEARDOWN_READY stays false here.
A live fixture archives that token outside this script.

Audience: INTERNAL_RESTRICTED
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Mapping

ACCOUNT_ID = "960577828987"
REGION = "us-east-2"
BILLING_REGION = "us-east-1"
ROLE_PROVISION = "vantio-w3-lab-provision"
ENVIRONMENT = "w3-lab-auto"
MAX_SESSION_SECONDS = 3600
MAX_LIFE_MINUTES = 420
LONG_MAX_LIFE_MINUTES = 36 * 60
MAX_LIFE = timedelta(hours=7)
ALLOWED_MAX_LIFE_HOURS = frozenset({"7", "36"})
OCCUPYING_STATES = frozenset({"pending", "running", "stopping", "stopped", "shutting-down"})
EXPIRY_BUFFER = timedelta(hours=8)
WORST_CASE_RUN_USD = Decimal("2.00")
ALLOWED_INSTANCE_TYPES = ("t3.micro", "t3.small")
CANONICAL_OWNER = "099720109477"
# Last OIDC launch that RunInstances allowed. Run 36831748889, 2026-10-01.
PINNED_IMAGE_ID = "ami-0fa99aa8f97f9e30b"
IMAGE_ID_RE = re.compile(r"^ami-[0-9a-f]{8,17}$")
FORBIDDEN_ACCOUNT_ID = "934814114565"
LAB_SUBNET_ID = "subnet-04b16afe18c8e3895"
LAB_VPC_ID = "vpc-0a139b3db139e7430"
AMI_NAME_FILTER = "ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"
NAME_PREFIX = "vantio-w3-lab-auto-"
C8_STATUS = "OPEN_STATIC_PASS_LIVE_NOT_RUN"
NONINTERACTIVE_TEARDOWN_READY = False

EXACT_TAGS = {
    "vantio:program": "w3-clean-host-lab",
    "vantio:lifecycle": "lab",
    "vantio:destroyable": "true",
    "vantio:environment": "lab",
    "vantio:owner-role": ROLE_PROVISION,
    "vantio:cost-class": "free-plan-credit",
    "vantio:shutdown-behavior": "terminate",
    "vantio:max-life-hours": "7",
    "vantio:created-by": ENVIRONMENT,
}
PURPOSE_TAG = "vantio:purpose"
PURPOSE_VALUE = "c8-noninteractive-teardown"

DENYLIST_IDS = frozenset(
    {
        "i-098363f4e84d43cee",
        "i-0c44b967e420db4cc",
        "snap-0c0b75ac7588d9f5e",
        "vol-054f3d970536da612",
        "sg-086553397f779f025",
        "eipalloc-02c0662a37c39d74d",
        "vantio-w3-class-b-lab-01",
    }
)
ALLOWED_RESOURCE_TYPES = frozenset({"instance", "volume", "security-group", "key-pair"})
ID_SHAPES = {
    "instance": re.compile(r"^i-[0-9a-f]{8,17}$"),
    "volume": re.compile(r"^vol-[0-9a-f]{8,17}$"),
    "security-group": re.compile(r"^sg-[0-9a-f]{8,17}$"),
    "key-pair": re.compile(r"^vantio-w3-lab-auto-[A-Za-z0-9-]{1,40}$"),
}

DELETE_ACTIONS = frozenset(
    {
        "delete_missing_expiry",
        "delete_launch_age",
        "delete_expired",
        "delete_missing_launch_time",
    }
)


def format_expiry(moment: datetime) -> str:
    if moment.tzinfo is None:
        raise ValueError("expiry must be timezone-aware")
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(value: Any) -> datetime:
    if isinstance(value, bool) or value is None:
        raise ValueError("missing time")
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return datetime.fromtimestamp(int(text), tz=timezone.utc)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            raise ValueError("naive time")
        return parsed.astimezone(timezone.utc)
    raise ValueError("unsupported time")


def _credit_amount(payload: Mapping[str, Any]) -> Decimal:
    credits = payload.get("accountPlanRemainingCredits")
    if not isinstance(credits, Mapping):
        raise ValueError("credits")
    if credits.get("unit") != "USD":
        raise ValueError("credit unit")
    amount = Decimal(str(credits.get("amount")))
    if not amount.is_finite():
        raise ValueError("credit amount")
    return amount


def evaluate_cost_gate(payload: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    """Return expected_oop_usd of '0' only when the Free plan can cover the ceiling.

    Cost Explorer is not consulted. A missing field, a Paid plan, or credits at
    or below the ceiling abort. Abort does not invent a dollar out-of-pocket
    figure; that figure would require a priced API.
    """
    reasons: list[str] = []
    if now.tzinfo is None:
        reasons.append("naive_now")
    if payload.get("accountId") != ACCOUNT_ID:
        reasons.append("account_id")
    if payload.get("accountPlanType") != "FREE":
        reasons.append("plan_type")
    if payload.get("accountPlanStatus") != "ACTIVE":
        reasons.append("plan_status")
    try:
        amount = _credit_amount(payload)
    except (InvalidOperation, ValueError):
        reasons.append("credits")
        amount = None
    if amount is not None and amount <= WORST_CASE_RUN_USD:
        reasons.append("credits_not_above_ceiling")
    try:
        expiration = parse_time(payload.get("accountPlanExpirationDate"))
        if now.tzinfo is not None and expiration <= now + EXPIRY_BUFFER:
            reasons.append("expiration")
    except ValueError:
        reasons.append("expiration")
    passed = not reasons
    return {
        "expected_oop_usd": "0" if passed else "UNKNOWN",
        "abort": not passed,
        "reasons": reasons,
        "worst_case_run_usd": format(WORST_CASE_RUN_USD, "f"),
        "account_id": ACCOUNT_ID,
        "billing_api": "freetier:GetAccountPlanState",
        "billing_region": BILLING_REGION,
        "cost_explorer": "not_called",
    }


def parse_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    raise ValueError("boolean")


def bounded_minutes(value: Any, field: str, *, limit: int = MAX_LIFE_MINUTES) -> int:
    if isinstance(value, bool) or isinstance(value, str) and value.strip().lstrip("-").isdigit():
        if isinstance(value, str):
            value = int(value.strip())
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(field)
    if value < 1 or value > limit:
        raise ValueError(field)
    return value


def build_user_data(stop_after_minutes: int) -> str:
    if isinstance(stop_after_minutes, bool) or not isinstance(stop_after_minutes, int):
        raise ValueError("stop_after_minutes must be an int")
    if stop_after_minutes < 1 or stop_after_minutes > LONG_MAX_LIFE_MINUTES:
        raise ValueError("stop_after_minutes must be from 1 through 2160")
    return (
        "#!/bin/bash\n"
        f"shutdown -h +{stop_after_minutes} || "
        f"systemd-run --on-active={stop_after_minutes}min --unit=vantio-lab-stop /sbin/shutdown -h now\n"
    )


def _tags(spec_purpose: str | None, expiry: str, name: str, max_life_hours: str = "7") -> dict[str, str]:
    if max_life_hours not in ALLOWED_MAX_LIFE_HOURS:
        raise ValueError("max_life_hours")
    tags = dict(EXACT_TAGS)
    tags["Name"] = name
    tags["vantio:expires-at"] = expiry
    tags["vantio:max-life-hours"] = max_life_hours
    if spec_purpose is not None:
        if spec_purpose != PURPOSE_VALUE:
            raise ValueError("purpose")
        tags[PURPOSE_TAG] = spec_purpose
    return tags


def lab_tags_owned(tags: Mapping[str, Any] | None) -> bool:
    """True when the tags are the sweeper's lab, including a 36-hour life tag."""
    if not isinstance(tags, Mapping):
        return False
    for key, expected in EXACT_TAGS.items():
        if key == "vantio:max-life-hours":
            if str(tags.get(key)) not in ALLOWED_MAX_LIFE_HOURS:
                return False
            continue
        if tags.get(key) != expected:
            return False
    name = tags.get("Name")
    return isinstance(name, str) and name.startswith(NAME_PREFIX)


def max_life_delta(tags: Mapping[str, Any]) -> timedelta:
    raw = str(tags.get("vantio:max-life-hours"))
    if raw not in ALLOWED_MAX_LIFE_HOURS:
        raise ValueError("max_life_hours")
    return timedelta(hours=int(raw))


def plan_launch(spec: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    """Build the launch plan. This function does not call AWS."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    instance_type = spec.get("instance_type", "t3.micro")
    if instance_type not in ALLOWED_INSTANCE_TYPES:
        raise ValueError("instance_type")
    max_life_hours = spec.get("max_life_hours", "7")
    if isinstance(max_life_hours, int) and not isinstance(max_life_hours, bool):
        max_life_hours = str(max_life_hours)
    if not isinstance(max_life_hours, str) or max_life_hours not in ALLOWED_MAX_LIFE_HOURS:
        raise ValueError("max_life_hours")
    life_limit = LONG_MAX_LIFE_MINUTES if max_life_hours == "36" else MAX_LIFE_MINUTES
    default_stop = life_limit
    minutes = bounded_minutes(spec.get("stop_after_minutes", default_stop), "stop_after_minutes", limit=life_limit)
    expires_in = bounded_minutes(spec.get("expires_in_minutes", minutes), "expires_in_minutes", limit=life_limit)
    user_data = build_user_data(minutes)
    name = spec.get("name", f"{NAME_PREFIX}plan")
    if not isinstance(name, str) or not name.startswith(NAME_PREFIX):
        raise ValueError("name")
    purpose = spec.get("purpose")
    if purpose is not None and not isinstance(purpose, str):
        raise ValueError("purpose")
    expiry = format_expiry(now + timedelta(minutes=expires_in))
    public_ip = parse_bool(spec.get("associate_public_ipv4", False))
    tags = _tags(purpose, expiry, name, max_life_hours)
    block_device = {
        "DeviceName": "/dev/sda1",
        "Ebs": {
            "VolumeSize": 8,
            "VolumeType": "gp3",
            "DeleteOnTermination": True,
            "Iops": 3000,
            "Throughput": 125,
        },
    }
    return {
        "account_id": ACCOUNT_ID,
        "region": REGION,
        "instance_type": instance_type,
        "min_count": 1,
        "max_count": 1,
        "instance_initiated_shutdown_behavior": "terminate",
        "credit_specification": "standard",
        "monitoring_enabled": False,
        "ebs_optimized": False,
        "associate_public_ipv4": public_ip,
        "metadata_http_tokens": "required",
        "metadata_hop_limit": 1,
        "iam_instance_profile": None,
        "disable_api_termination": False,
        "image_owner": CANONICAL_OWNER,
        "image_name_filter": AMI_NAME_FILTER,
        "image_architecture": "x86_64",
        "image_root_device_type": "ebs",
        "image_product_code_allowed": False,
        "key_pair": None,
        "security_group_ingress": [],
        "block_device": block_device,
        "user_data": user_data,
        "tags": tags,
        "expires_at": expiry,
        "stop_after_minutes": minutes,
        "worst_case_run_usd": format(WORST_CASE_RUN_USD, "f"),
        "elastic_ip": False,
    }


def sweeper_action(resource: Mapping[str, Any], now: datetime) -> str:
    """Decide keep or delete for one already-described resource.

    Delete is a plan. This function does not call AWS.
    """
    if now.tzinfo is None:
        return "skip_bad_clock"
    resource_type = resource.get("type")
    if resource_type not in ALLOWED_RESOURCE_TYPES:
        return "skip_unsupported_type"
    if resource.get("region") != REGION:
        return "skip_wrong_region"
    resource_id = resource.get("id")
    if not isinstance(resource_id, str) or resource_id in DENYLIST_IDS:
        return "skip_denylist"
    shape = ID_SHAPES[str(resource_type)]
    if shape.match(resource_id) is None:
        return "skip_bad_id"
    tags = resource.get("tags")
    if not isinstance(tags, Mapping) or not lab_tags_owned(tags):
        return "skip_not_owned"
    purpose = tags.get(PURPOSE_TAG)
    if purpose is not None and purpose != PURPOSE_VALUE:
        return "skip_bad_purpose"
    if str(tags.get("vantio:max-life-hours")) == "36":
        try:
            long_life_enabled = load_lab_capabilities()["max_life_hours_36"]
        except GuardAbort:
            long_life_enabled = False
        if not long_life_enabled:
            return "skip_life_not_enabled"
    if resource_type == "instance" and not resource.get("launch_time"):
        return "delete_missing_launch_time"
    created = resource.get("launch_time") or resource.get("created_at")
    if created:
        try:
            started = parse_time(created)
        except ValueError:
            return "delete_missing_expiry"
        if now - started >= max_life_delta(tags):
            return "delete_launch_age"
    raw_expiry = tags.get("vantio:expires-at")
    if not isinstance(raw_expiry, str) or raw_expiry == "":
        return "delete_missing_expiry"
    try:
        expiry = parse_time(raw_expiry)
    except ValueError:
        return "delete_missing_expiry"
    if expiry <= now:
        return "delete_expired"
    return "keep"


def select_image(describe_images_payload: Mapping[str, Any]) -> str:
    images = describe_images_payload.get("Images")
    if not isinstance(images, list):
        raise ValueError("images")
    candidates: list[Mapping[str, Any]] = []
    for image in images:
        if not isinstance(image, Mapping):
            continue
        if image.get("OwnerId") != CANONICAL_OWNER:
            continue
        if image.get("ProductCodes"):
            continue
        if image.get("Architecture") != "x86_64":
            continue
        if image.get("RootDeviceType") != "ebs":
            continue
        if image.get("Public") is not True:
            continue
        name = image.get("Name")
        if not isinstance(name, str) or "ubuntu-noble-24.04-amd64-server" not in name:
            continue
        if "pro" in name.lower():
            continue
        image_id = image.get("ImageId")
        if not isinstance(image_id, str) or not image_id.startswith("ami-"):
            continue
        candidates.append(image)
    if not candidates:
        raise ValueError("no eligible image")
    candidates.sort(key=lambda item: str(item.get("CreationDate") or ""))
    return str(candidates[-1]["ImageId"])


def _tag_specifications(resource_type: str, tags: Mapping[str, str]) -> dict[str, Any]:
    return {
        "ResourceType": resource_type,
        "Tags": [{"Key": key, "Value": value} for key, value in tags.items()],
    }


def create_security_group_args(plan: Mapping[str, Any], vpc_id: str) -> list[str]:
    name = str(plan["tags"]["Name"])
    spec = _tag_specifications("security-group", plan["tags"])
    return [
        "aws",
        "ec2",
        "create-security-group",
        "--region",
        REGION,
        "--group-name",
        name,
        "--description",
        "vantio w3 lab auto",
        "--vpc-id",
        vpc_id,
        "--tag-specifications",
        json.dumps([spec], separators=(",", ":")),
    ]


def run_instances_args(
    plan: Mapping[str, Any],
    *,
    image_id: str,
    security_group_id: str,
    subnet_id: str,
) -> list[str]:
    if plan["min_count"] != 1 or plan["max_count"] != 1:
        raise ValueError("count")
    if plan["iam_instance_profile"] is not None:
        raise ValueError("instance profile")
    if plan["elastic_ip"] is not False:
        raise ValueError("elastic ip")
    tags = plan["tags"]
    if not isinstance(tags, Mapping):
        raise ValueError("tags")
    network = {
        "DeviceIndex": 0,
        "SubnetId": subnet_id,
        "Groups": [security_group_id],
        "AssociatePublicIpAddress": bool(plan["associate_public_ipv4"]),
    }
    tag_specs = [
        _tag_specifications(resource_type, tags)
        for resource_type in ("instance", "volume", "network-interface")
    ]
    return [
        "aws",
        "ec2",
        "run-instances",
        "--region",
        REGION,
        "--image-id",
        image_id,
        "--instance-type",
        str(plan["instance_type"]),
        "--count",
        "1",
        "--instance-initiated-shutdown-behavior",
        "terminate",
        "--credit-specification",
        "CpuCredits=standard",
        "--no-ebs-optimized",
        "--metadata-options",
        "HttpTokens=required,HttpPutResponseHopLimit=1,HttpEndpoint=enabled",
        "--network-interfaces",
        json.dumps([network], separators=(",", ":")),
        "--block-device-mappings",
        json.dumps([plan["block_device"]], separators=(",", ":")),
        "--user-data",
        "file://user-data.sh",
        "--tag-specifications",
        json.dumps(tag_specs, separators=(",", ":")),
    ]


def describe_image_id_args(image_id: str) -> list[str]:
    if IMAGE_ID_RE.fullmatch(image_id) is None:
        raise GuardAbort("image_id")
    return [
        "aws",
        "ec2",
        "describe-images",
        "--region",
        REGION,
        "--image-ids",
        image_id,
    ]


def require_available_image(payload: Mapping[str, Any], image_id: str) -> str:
    """Accept one available Canonical Ubuntu 24.04 image. This does not launch."""
    images = payload.get("Images")
    if not isinstance(images, list) or len(images) != 1 or not isinstance(images[0], Mapping):
        raise GuardAbort("image_unavailable")
    image = images[0]
    if image.get("ImageId") != image_id or image.get("State") != "available":
        raise GuardAbort("image_unavailable")
    if image.get("OwnerId") != CANONICAL_OWNER:
        raise GuardAbort("image_owner")
    if image.get("Architecture") != "x86_64" or image.get("RootDeviceType") != "ebs" or image.get("Public") is not True:
        raise GuardAbort("image_rejected")
    name = image.get("Name")
    if not isinstance(name, str) or "ubuntu-noble-24.04-amd64-server" not in name or "pro" in name.lower():
        raise GuardAbort("image_rejected")
    if image.get("ProductCodes"):
        raise GuardAbort("image_rejected")
    return image_id


def resolve_pinned_image(runner: Runner, image_id: str) -> str:
    if IMAGE_ID_RE.fullmatch(image_id) is None:
        raise GuardAbort("image_id")
    try:
        described = aws_json(runner, describe_image_id_args(image_id))
    except GuardAbort as exc:
        if "InvalidAMIID.NotFound" in exc.reason or "InvalidAMIID.Unavailable" in exc.reason:
            raise GuardAbort("image_unavailable") from None
        raise
    return require_available_image(described, image_id)


def describe_images_args() -> list[str]:
    return [
        "aws",
        "ec2",
        "describe-images",
        "--region",
        REGION,
        "--owners",
        CANONICAL_OWNER,
        "--filters",
        f"Name=name,Values={AMI_NAME_FILTER}",
        "Name=architecture,Values=x86_64",
        "Name=root-device-type,Values=ebs",
        "Name=virtualization-type,Values=hvm",
        "Name=state,Values=available",
    ]


def terminate_args(instance_id: str) -> list[str]:
    if ID_SHAPES["instance"].match(instance_id) is None or instance_id in DENYLIST_IDS:
        raise ValueError("instance id")
    return ["aws", "ec2", "terminate-instances", "--region", REGION, "--instance-ids", instance_id]


def _load_json_stdin() -> dict[str, Any]:
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict):
        raise ValueError("stdin must be a JSON object")
    return payload


class GuardAbort(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]


def refuse_forbidden_command(args: list[str]) -> None:
    text = " ".join(args)
    lowered = text.lower()
    if FORBIDDEN_ACCOUNT_ID in text:
        raise GuardAbort("forbidden_account")
    if args[:2] == ["aws", "ce"] or "getcostandusage" in lowered or "cost-explorer" in lowered:
        raise GuardAbort("cost_explorer")
    if "upgrade-account-plan" in lowered or "upgradeaccountplan" in lowered:
        raise GuardAbort("paid_upgrade")
    if "allocate-address" in lowered or "associate-address" in lowered:
        raise GuardAbort("elastic_ip")
    if "--region" in args:
        region = args[args.index("--region") + 1]
        if region != REGION:
            raise GuardAbort("region")


def default_runner(args: list[str]) -> subprocess.CompletedProcess[str]:
    refuse_forbidden_command(args)
    return subprocess.run(args, capture_output=True, text=True, check=False)


def aws_json(runner: Runner, args: list[str]) -> dict[str, Any]:
    refuse_forbidden_command(args)
    if "--output" not in args:
        args = [*args, "--output", "json"]
    proc = runner(args)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise GuardAbort(detail[0] if detail else "aws_failed")
    if not proc.stdout.strip():
        return {}
    payload = json.loads(proc.stdout)
    if not isinstance(payload, dict):
        raise GuardAbort("aws_payload")
    return payload


def resolve_gate(document: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    if "expected_oop_usd" in document and "accountPlanType" not in document:
        return dict(document)
    return evaluate_cost_gate(document, now)


def gate_failure(document: Mapping[str, Any]) -> str | None:
    if document.get("cost_explorer") not in (None, "not_called"):
        return "cost_explorer"
    if document.get("billing_api") not in (None, "freetier:GetAccountPlanState"):
        return "billing_api"
    if document.get("account_id") not in (None, ACCOUNT_ID):
        return "account_id"
    oop = document.get("expected_oop_usd")
    if oop != "0":
        if oop in (None, "", "UNKNOWN"):
            return "unknown_billing"
        return "oop"
    if document.get("abort") is not False:
        return "unknown_billing"
    reasons = document.get("reasons")
    if reasons not in (None, []):
        return "unknown_billing"
    return None


def require_identity(identity: Mapping[str, Any]) -> None:
    account = str(identity.get("Account") or "")
    if account == FORBIDDEN_ACCOUNT_ID:
        raise GuardAbort("forbidden_account")
    if account != ACCOUNT_ID:
        raise GuardAbort("account_id")


def _passing_gate(now: datetime | None = None) -> dict[str, Any]:
    moment = now or datetime.now(timezone.utc)
    return evaluate_cost_gate(
        {
            "accountId": ACCOUNT_ID,
            "accountPlanType": "FREE",
            "accountPlanStatus": "ACTIVE",
            "accountPlanRemainingCredits": {"amount": "3.00", "unit": "USD"},
            "accountPlanExpirationDate": format_expiry(moment + timedelta(hours=24)),
        },
        moment,
    )


def execute_launch(
    spec: Mapping[str, Any],
    gate_document: Mapping[str, Any],
    identity: Mapping[str, Any],
    runner: Runner,
    now: datetime,
    *,
    user_data_path: Path,
) -> dict[str, Any]:
    if spec.get("region", REGION) != REGION:
        raise GuardAbort("region")
    if spec.get("subnet_id", LAB_SUBNET_ID) != LAB_SUBNET_ID:
        raise GuardAbort("subnet")
    if spec.get("vpc_id", LAB_VPC_ID) != LAB_VPC_ID:
        raise GuardAbort("vpc")
    gate = resolve_gate(gate_document, now)
    failure = gate_failure(gate)
    if failure:
        raise GuardAbort(failure)
    require_identity(identity)
    plan = plan_launch(spec, now)
    if plan["elastic_ip"] is not False or plan["iam_instance_profile"] is not None:
        raise GuardAbort("launch_shape")
    if plan["instance_initiated_shutdown_behavior"] != "terminate":
        raise GuardAbort("shutdown")
    if plan["tags"].get("vantio:destroyable") != "true":
        raise GuardAbort("untagged")
    user_data_path.write_text(plan["user_data"], encoding="utf-8")
    requested = str(spec.get("image_id") or PINNED_IMAGE_ID)
    image_id = resolve_pinned_image(runner, requested)
    created = aws_json(runner, create_security_group_args(plan, LAB_VPC_ID))
    group_id = created.get("GroupId")
    if not isinstance(group_id, str) or not group_id.startswith("sg-"):
        raise GuardAbort("security_group")
    launch_args = run_instances_args(
        plan,
        image_id=image_id,
        security_group_id=group_id,
        subnet_id=LAB_SUBNET_ID,
    )
    launch_args[launch_args.index("file://user-data.sh")] = f"file://{user_data_path}"
    try:
        launched = aws_json(runner, launch_args)
    except GuardAbort:
        rollback_security_group(runner, group_id)
        raise
    instances = launched.get("Instances")
    if not isinstance(instances, list) or not instances:
        rollback_security_group(runner, group_id)
        raise GuardAbort("instance")
    instance_id = instances[0].get("InstanceId")
    if not isinstance(instance_id, str) or ID_SHAPES["instance"].match(instance_id) is None:
        raise GuardAbort("instance")
    if instance_id in DENYLIST_IDS:
        raise GuardAbort("denylist")
    return {
        "account_id": ACCOUNT_ID,
        "region": REGION,
        "instance_id": instance_id,
        "security_group_id": group_id,
        "image_id": image_id,
        "instance_type": plan["instance_type"],
        "stop_after_minutes": plan["stop_after_minutes"],
        "expires_at": plan["expires_at"],
        "associate_public_ipv4": plan["associate_public_ipv4"],
        "shutdown_behavior": "terminate",
        "expected_oop_usd": "0",
        "cost_explorer_called": False,
        "paid_upgrade_called": False,
        "noninteractive_teardown_ready": False,
        "tags": plan["tags"],
    }


def _delete_resource(resource: Mapping[str, Any], runner: Runner) -> list[str]:
    resource_type = resource.get("type")
    resource_id = str(resource.get("id"))
    if resource_type == "instance":
        aws_json(runner, terminate_args(resource_id))
        wait = [
            "aws",
            "ec2",
            "wait",
            "instance-terminated",
            "--region",
            REGION,
            "--instance-ids",
            resource_id,
        ]
        refuse_forbidden_command(wait)
        proc = runner(wait)
        if proc.returncode != 0:
            raise GuardAbort("wait_terminated")
        return ["terminate-instances", "wait-instance-terminated"]
    if resource_type == "volume":
        wait = ["aws", "ec2", "wait", "volume-available", "--region", REGION, "--volume-ids", resource_id]
        refuse_forbidden_command(wait)
        proc = runner(wait)
        if proc.returncode != 0:
            raise GuardAbort("wait_volume")
        aws_json(runner, ["aws", "ec2", "delete-volume", "--region", REGION, "--volume-id", resource_id])
        return ["wait-volume-available", "delete-volume"]
    if resource_type == "security-group":
        args = ["aws", "ec2", "delete-security-group", "--region", REGION, "--group-id", resource_id]
        for _attempt in range(5):
            refuse_forbidden_command(args)
            proc = runner(args)
            if proc.returncode == 0:
                return ["delete-security-group"]
            text = f"{proc.stderr or ''}{proc.stdout or ''}"
            if "DependencyViolation" not in text:
                raise GuardAbort("delete_security_group")
            time.sleep(float(os.environ.get("W3_LAB_RETRY_SECONDS", "1")))
        raise GuardAbort("delete_security_group")
    if resource_type == "key-pair":
        aws_json(runner, ["aws", "ec2", "delete-key-pair", "--region", REGION, "--key-name", resource_id])
        return ["delete-key-pair"]
    raise GuardAbort("unsupported_type")


def execute_sweep(
    identity: Mapping[str, Any],
    resources: list[Mapping[str, Any]],
    runner: Runner,
    now: datetime,
) -> dict[str, Any]:
    require_identity(identity)
    ordered = sorted(resources, key=lambda item: {"instance": 0, "volume": 1, "security-group": 2, "key-pair": 3}.get(str(item.get("type")), 9))
    actions: list[dict[str, Any]] = []
    for resource in ordered:
        if resource.get("region", REGION) != REGION:
            actions.append(
                {
                    "id": resource.get("id"),
                    "type": resource.get("type"),
                    "action": "skip_wrong_region",
                    "called": False,
                }
            )
            continue
        decision = sweeper_action(resource, now)
        tags = resource.get("tags") if isinstance(resource.get("tags"), Mapping) else {}
        if decision in DELETE_ACTIONS and tags.get("vantio:destroyable") != "true":
            decision = "skip_not_owned"
        called: list[str] = []
        if decision in DELETE_ACTIONS:
            called = _delete_resource(resource, runner)
        actions.append(
            {
                "id": resource.get("id"),
                "type": resource.get("type"),
                "action": decision,
                "called": called,
            }
        )
    return {"actions": actions, "noninteractive_teardown_ready": False, "account_id": ACCOUNT_ID, "region": REGION}


def _tag_list(tags: Any) -> dict[str, str]:
    if isinstance(tags, dict):
        return {str(key): str(value) for key, value in tags.items()}
    found: dict[str, str] = {}
    if isinstance(tags, list):
        for item in tags:
            if isinstance(item, Mapping) and item.get("Key") is not None:
                found[str(item["Key"])] = str(item.get("Value") or "")
    return found


def census_from_aws(runner: Runner) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    described = aws_json(runner, ["aws", "ec2", "describe-instances", "--region", REGION])
    for reservation in described.get("Reservations") or []:
        if not isinstance(reservation, Mapping):
            continue
        for instance in reservation.get("Instances") or []:
            if not isinstance(instance, Mapping):
                continue
            resources.append(
                {
                    "type": "instance",
                    "id": instance.get("InstanceId"),
                    "region": REGION,
                    "launch_time": instance.get("LaunchTime"),
                    "tags": _tag_list(instance.get("Tags")),
                }
            )
    volumes = aws_json(runner, ["aws", "ec2", "describe-volumes", "--region", REGION])
    for volume in volumes.get("Volumes") or []:
        if not isinstance(volume, Mapping):
            continue
        resources.append(
            {
                "type": "volume",
                "id": volume.get("VolumeId"),
                "region": REGION,
                "created_at": volume.get("CreateTime"),
                "tags": _tag_list(volume.get("Tags")),
            }
        )
    groups = aws_json(runner, ["aws", "ec2", "describe-security-groups", "--region", REGION])
    for group in groups.get("SecurityGroups") or []:
        if not isinstance(group, Mapping):
            continue
        resources.append(
            {
                "type": "security-group",
                "id": group.get("GroupId"),
                "region": REGION,
                "tags": _tag_list(group.get("Tags")),
            }
        )
    keys = aws_json(runner, ["aws", "ec2", "describe-key-pairs", "--region", REGION])
    for key in keys.get("KeyPairs") or []:
        if not isinstance(key, Mapping):
            continue
        resources.append(
            {
                "type": "key-pair",
                "id": key.get("KeyName"),
                "region": REGION,
                "created_at": key.get("CreateTime"),
                "tags": _tag_list(key.get("Tags")),
            }
        )
    return resources


def _read_gate_file(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise GuardAbort("unknown_billing")
    return payload


def write_json_with_hash(path: Path, payload: Mapping[str, Any]) -> str:
    body = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.write_text(body, encoding="utf-8")
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    path.with_name(path.name + ".sha256").write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return digest


def load_lab_capabilities(path: Path | None = None) -> dict[str, bool]:
    """Read the repo switch that stays false until a console IAM change is recorded."""
    file = path or Path(os.environ.get("W3_LAB_CAPABILITIES", str(Path(__file__).with_name("lab_iam_capabilities.json"))))
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise GuardAbort("capabilities") from None
    if not isinstance(data, dict):
        raise GuardAbort("capabilities")
    return {
        "max_life_hours_36": data.get("max_life_hours_36") is True,
        "ssh_instance_connect": data.get("ssh_instance_connect") is True,
        "ssm": data.get("ssm") is True,
    }


def occupying_instance_ids(described: Mapping[str, Any]) -> list[str]:
    found: list[str] = []
    reservations = described.get("Reservations") or []
    if not isinstance(reservations, list):
        raise GuardAbort("slot_check")
    for reservation in reservations:
        if not isinstance(reservation, Mapping):
            continue
        instances = reservation.get("Instances") or []
        if not isinstance(instances, list):
            continue
        for instance in instances:
            if not isinstance(instance, Mapping):
                continue
            state = instance.get("State")
            name = state.get("Name") if isinstance(state, Mapping) else ""
            if name in OCCUPYING_STATES:
                instance_id = instance.get("InstanceId")
                if isinstance(instance_id, str):
                    found.append(instance_id)
    return found


def describe_occupying_args() -> list[str]:
    return [
        "aws",
        "ec2",
        "describe-instances",
        "--region",
        REGION,
        "--filters",
        "Name=instance-state-name,Values=pending,running,stopping,stopped,shutting-down",
    ]


def rollback_security_group(runner: Runner, group_id: str) -> None:
    if not group_id.startswith("sg-"):
        raise GuardAbort("security_group")
    try:
        aws_json(runner, ["aws", "ec2", "delete-security-group", "--region", REGION, "--group-id", group_id])
    except GuardAbort:
        raise GuardAbort("rollback_security_group") from None


def _launch_spec_from_env() -> dict[str, Any]:
    purpose = os.environ.get("PURPOSE", "").strip()
    run_id = os.environ.get("GITHUB_RUN_ID", "local").strip() or "local"
    if not re.fullmatch(r"[A-Za-z0-9-]{1,40}", run_id):
        raise GuardAbort("name")
    max_life_hours = os.environ.get("MAX_LIFE_HOURS", "7").strip() or "7"
    if max_life_hours not in ALLOWED_MAX_LIFE_HOURS:
        raise GuardAbort("max_life_hours")
    if max_life_hours == "36" and not load_lab_capabilities()["max_life_hours_36"]:
        raise GuardAbort("max_life_hours_36_not_enabled")
    default_stop = "2160" if max_life_hours == "36" else "420"
    spec: dict[str, Any] = {
        "instance_type": os.environ.get("INSTANCE_TYPE", "t3.micro"),
        "image_id": os.environ.get("IMAGE_ID", PINNED_IMAGE_ID).strip() or PINNED_IMAGE_ID,
        "stop_after_minutes": os.environ.get("STOP_AFTER_MINUTES", default_stop),
        "associate_public_ipv4": os.environ.get("ASSOCIATE_PUBLIC_IPV4", "false"),
        "name": f"{NAME_PREFIX}{run_id}",
        "region": REGION,
        "subnet_id": LAB_SUBNET_ID,
        "vpc_id": LAB_VPC_ID,
        "max_life_hours": max_life_hours,
    }
    if purpose:
        spec["purpose"] = purpose
    expires = os.environ.get("EXPIRES_IN_MINUTES", "").strip()
    if expires:
        spec["expires_in_minutes"] = expires
    return spec


def launch_from_env(runner: Runner, now: datetime) -> dict[str, Any]:
    evidence_path = Path(os.environ.get("EVIDENCE_PATH", "w3-lab-auto-launch.json"))
    occupying: list[str] = []
    try:
        gate_path = os.environ.get("COST_GATE_FILE", "").strip()
        if not gate_path:
            raise GuardAbort("unknown_billing")
        try:
            gate = _read_gate_file(gate_path)
        except (OSError, json.JSONDecodeError):
            raise GuardAbort("unknown_billing") from None
        failure = gate_failure(resolve_gate(gate, now))
        if failure:
            raise GuardAbort(failure)
        spec = _launch_spec_from_env()
        identity = aws_json(runner, ["aws", "sts", "get-caller-identity"])
        require_identity(identity)
        if os.environ.get("DESCRIBE_ONLY", "false").strip().lower() == "true":
            image_id = resolve_pinned_image(runner, str(spec["image_id"]))
            evidence = {
                "account_id": ACCOUNT_ID,
                "image_id": image_id,
                "image_state": "available",
                "launched": False,
                "noninteractive_teardown_ready": False,
                "region": REGION,
                "describe_only": True,
            }
            write_json_with_hash(evidence_path, evidence)
            return evidence
        described = aws_json(runner, describe_occupying_args())
        occupying = occupying_instance_ids(described)
        if occupying:
            raise GuardAbort("slot_occupied")
        evidence = execute_launch(
            spec,
            gate,
            identity,
            runner,
            now,
            user_data_path=Path(os.environ.get("USER_DATA_PATH", "user-data.sh")),
        )
    except GuardAbort as exc:
        write_json_with_hash(
            evidence_path,
            {
                "account_id": ACCOUNT_ID,
                "error": exc.reason,
                "launched": False,
                "noninteractive_teardown_ready": False,
                "occupying_instance_ids": occupying,
                "region": REGION,
            },
        )
        raise
    write_json_with_hash(evidence_path, evidence)
    return evidence


def sweep_from_env(runner: Runner, now: datetime) -> dict[str, Any]:
    identity = aws_json(runner, ["aws", "sts", "get-caller-identity"])
    require_identity(identity)
    evidence = execute_sweep(identity, census_from_aws(runner), runner, now)
    write_json_with_hash(Path(os.environ.get("EVIDENCE_PATH", "w3-lab-auto-sweep.json")), evidence)
    return evidence


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: w3_lab_auto.py cost-gate|plan-launch|plan-sweep|user-data|launch|sweep", file=sys.stderr)
        return 1
    command = argv[1]
    now = datetime.now(timezone.utc)
    if command == "cost-gate":
        result = evaluate_cost_gate(_load_json_stdin(), now)
        json.dump(result, sys.stdout)
        sys.stdout.write("\n")
        return 0 if result["expected_oop_usd"] == "0" and result["abort"] is False else 2
    if command == "user-data":
        minutes = int(argv[2]) if len(argv) > 2 else MAX_LIFE_MINUTES
        sys.stdout.write(build_user_data(minutes))
        return 0
    if command == "plan-launch":
        spec = _load_json_stdin()
        json.dump(plan_launch(spec, now), sys.stdout)
        sys.stdout.write("\n")
        return 0
    if command == "plan-sweep":
        census = _load_json_stdin()
        moment = parse_time(census["now"]) if "now" in census else now
        resources = census.get("resources")
        if not isinstance(resources, list):
            raise ValueError("resources")
        actions = [
            {"id": item.get("id"), "type": item.get("type"), "action": sweeper_action(item, moment)}
            for item in resources
        ]
        json.dump({"actions": actions, "noninteractive_teardown_ready": False}, sys.stdout)
        sys.stdout.write("\n")
        return 0
    if command == "launch":
        try:
            json.dump(launch_from_env(default_runner, now), sys.stdout)
            sys.stdout.write("\n")
        except GuardAbort as exc:
            print(exc.reason, file=sys.stderr)
            return 2
        return 0
    if command == "sweep":
        try:
            json.dump(sweep_from_env(default_runner, now), sys.stdout)
            sys.stdout.write("\n")
        except GuardAbort as exc:
            print(exc.reason, file=sys.stderr)
            return 2
        return 0
    print(f"unknown command {command}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (GuardAbort, ValueError, json.JSONDecodeError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
