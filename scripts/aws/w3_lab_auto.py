#!/usr/bin/env python3
"""Free-plan lab decisions for account 960577828987.

This module plans a lab and decides the cost gate and the sweeper. It does
not create AWS resources. The launch and sweep subcommands refuse to run
unless W3_LAB_AUTO_APPLY=1, and nothing in this packet sets that variable.

Audience: INTERNAL_RESTRICTED
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

ACCOUNT_ID = "960577828987"
REGION = "us-east-2"
BILLING_REGION = "us-east-1"
ROLE_PROVISION = "vantio-w3-lab-provision"
ENVIRONMENT = "w3-lab-auto"
MAX_SESSION_SECONDS = 3600
MAX_LIFE_MINUTES = 420
MAX_LIFE = timedelta(hours=7)
EXPIRY_BUFFER = timedelta(hours=8)
WORST_CASE_RUN_USD = Decimal("2.00")
ALLOWED_INSTANCE_TYPES = ("t3.micro", "t3.small")
CANONICAL_OWNER = "099720109477"
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


def build_user_data(stop_after_minutes: int) -> str:
    if isinstance(stop_after_minutes, bool) or not isinstance(stop_after_minutes, int):
        raise ValueError("stop_after_minutes must be an int")
    if stop_after_minutes < 1 or stop_after_minutes > MAX_LIFE_MINUTES:
        raise ValueError("stop_after_minutes must be from 1 through 420")
    return (
        "#!/bin/bash\n"
        f"shutdown -h +{stop_after_minutes} || "
        f"systemd-run --on-active={stop_after_minutes}min --unit=vantio-lab-stop /sbin/shutdown -h now\n"
    )


def _tags(spec_purpose: str | None, expiry: str, name: str) -> dict[str, str]:
    tags = dict(EXACT_TAGS)
    tags["Name"] = name
    tags["vantio:expires-at"] = expiry
    if spec_purpose is not None:
        if spec_purpose != PURPOSE_VALUE:
            raise ValueError("purpose")
        tags[PURPOSE_TAG] = spec_purpose
    return tags


def plan_launch(spec: Mapping[str, Any], now: datetime) -> dict[str, Any]:
    """Build the launch plan. This function does not call AWS."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    instance_type = spec.get("instance_type", "t3.micro")
    if instance_type not in ALLOWED_INSTANCE_TYPES:
        raise ValueError("instance_type")
    minutes = spec.get("stop_after_minutes", MAX_LIFE_MINUTES)
    if isinstance(minutes, bool) or not isinstance(minutes, int):
        raise ValueError("stop_after_minutes")
    user_data = build_user_data(minutes)
    name = spec.get("name", f"{NAME_PREFIX}plan")
    if not isinstance(name, str) or not name.startswith(NAME_PREFIX):
        raise ValueError("name")
    purpose = spec.get("purpose")
    if purpose is not None and not isinstance(purpose, str):
        raise ValueError("purpose")
    expiry = format_expiry(now + timedelta(minutes=minutes))
    public_ip = bool(spec.get("associate_public_ipv4", False))
    tags = _tags(purpose, expiry, name)
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
    if not isinstance(tags, Mapping):
        return "skip_not_owned"
    for key, expected in EXACT_TAGS.items():
        if tags.get(key) != expected:
            return "skip_not_owned"
    name = tags.get("Name")
    if not isinstance(name, str) or not name.startswith(NAME_PREFIX):
        return "skip_not_owned"
    purpose = tags.get(PURPOSE_TAG)
    if purpose is not None and purpose != PURPOSE_VALUE:
        return "skip_bad_purpose"
    if resource_type == "instance" and not resource.get("launch_time"):
        return "delete_missing_launch_time"
    created = resource.get("launch_time") or resource.get("created_at")
    if created:
        try:
            started = parse_time(created)
        except ValueError:
            return "delete_missing_expiry"
        if now - started >= MAX_LIFE:
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


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: w3_lab_auto.py cost-gate|plan-launch|plan-sweep|user-data", file=sys.stderr)
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
    if command in {"launch", "sweep"}:
        print(
            "HELD: this packet does not call AWS. Live launch and live sweep stay closed.",
            file=sys.stderr,
        )
        return 3
    print(f"unknown command {command}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except (ValueError, json.JSONDecodeError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
