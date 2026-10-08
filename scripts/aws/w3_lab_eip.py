#!/usr/bin/env python3
"""Release one named Elastic IP, or refuse.

The only address this command will release is 3.131.219.111 in account
960577828987. It releases that address only when describe shows it is
unattached and it does not carry lab tags. Any other result is recorded
and the address is left in place.

Audience: INTERNAL_RESTRICTED
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping

import w3_lab_auto as lab

PUBLIC_IP = "3.131.219.111"
LAB_TAG_VALUES = {
    "vantio:program": "w3-clean-host-lab",
    "vantio:lifecycle": "lab",
    "vantio:environment": "lab",
    "vantio:destroyable": "true",
}


def address_tags(address: Mapping[str, Any]) -> dict[str, str]:
    return lab._tag_list(address.get("Tags"))


def attachment_ids(address: Mapping[str, Any]) -> dict[str, str]:
    found: dict[str, str] = {}
    for key in ("AssociationId", "InstanceId", "NetworkInterfaceId"):
        value = address.get(key)
        if isinstance(value, str) and value:
            found[key] = value
    association = address.get("Association")
    if isinstance(association, Mapping):
        for key in ("AssociationId", "InstanceId", "NetworkInterfaceId"):
            value = association.get(key)
            if isinstance(value, str) and value:
                found[key] = value
    return found


def lab_tagged(tags: Mapping[str, str]) -> list[str]:
    reasons: list[str] = []
    for key, expected in LAB_TAG_VALUES.items():
        if tags.get(key) == expected:
            reasons.append(key)
    name = tags.get("Name", "")
    if name.startswith("vantio-w3-lab-"):
        reasons.append("Name")
    purpose = tags.get("vantio:purpose", "")
    if purpose:
        reasons.append("vantio:purpose")
    return reasons


def decide(address: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return the release decision. This function does not call AWS."""
    if address is None:
        return {"release": False, "status": "NOT_FOUND", "reasons": ["absent"]}
    public_ip = address.get("PublicIp")
    if public_ip != PUBLIC_IP:
        return {"release": False, "status": "WRONG_ADDRESS", "reasons": ["public_ip"]}
    attached = attachment_ids(address)
    if attached:
        return {"release": False, "status": "ATTACHED", "reasons": sorted(attached)}
    tags = address_tags(address)
    lab_reasons = lab_tagged(tags)
    if lab_reasons:
        return {"release": False, "status": "LAB_TAGGED", "reasons": lab_reasons}
    allocation_id = address.get("AllocationId")
    if not isinstance(allocation_id, str) or not allocation_id.startswith("eipalloc-"):
        return {"release": False, "status": "NO_ALLOCATION", "reasons": ["allocation_id"]}
    return {"release": True, "status": "UNATTACHED_NOT_LAB", "reasons": [], "allocation_id": allocation_id}


def public_view(address: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if address is None:
        return None
    return {
        "allocation_id": address.get("AllocationId"),
        "association": attachment_ids(address),
        "domain": address.get("Domain"),
        "public_ip": address.get("PublicIp"),
        "tags": address_tags(address),
    }


def describe_args() -> list[str]:
    return [
        "aws",
        "ec2",
        "describe-addresses",
        "--region",
        lab.REGION,
        "--public-ips",
        PUBLIC_IP,
    ]


def release_args(allocation_id: str) -> list[str]:
    if not allocation_id.startswith("eipalloc-"):
        raise lab.GuardAbort("allocation_id")
    return [
        "aws",
        "ec2",
        "release-address",
        "--region",
        lab.REGION,
        "--allocation-id",
        allocation_id,
    ]


def _denied(text: str) -> bool:
    return "AccessDenied" in text or "UnauthorizedOperation" in text or "explicit deny" in text.lower()


def describe_address(runner: lab.Runner) -> tuple[Mapping[str, Any] | None, str | None]:
    args = [*describe_args(), "--output", "json"]
    lab.refuse_forbidden_command(args)
    proc = runner(args)
    text = f"{proc.stderr or ''}{proc.stdout or ''}"
    if proc.returncode != 0:
        if _denied(text):
            return None, "describe_denied"
        if "InvalidAddress.NotFound" in text:
            return None, None
        raise lab.GuardAbort("describe_addresses")
    payload = json.loads(proc.stdout or "{}")
    addresses = payload.get("Addresses") if isinstance(payload, dict) else None
    if not isinstance(addresses, list) or not addresses:
        return None, None
    first = addresses[0]
    if not isinstance(first, dict):
        raise lab.GuardAbort("describe_addresses")
    return first, None


def execute(runner: lab.Runner) -> dict[str, Any]:
    identity = lab.aws_json(runner, ["aws", "sts", "get-caller-identity"])
    lab.require_identity(identity)
    before, describe_error = describe_address(runner)
    decision = decide(before)
    payload: dict[str, Any] = {
        "account_id": lab.ACCOUNT_ID,
        "after": None,
        "before": public_view(before),
        "decision": decision,
        "mutated": False,
        "public_ip": PUBLIC_IP,
        "region": lab.REGION,
        "released": False,
        "status": decision["status"],
    }
    if describe_error:
        payload["status"] = "DESCRIBE_DENIED"
        payload["reason"] = describe_error
        lab.write_json_with_hash(Path(os.environ.get("EVIDENCE_PATH", "w3-lab-eip.json")), payload)
        raise lab.GuardAbort(describe_error)
    if not decision["release"]:
        lab.write_json_with_hash(Path(os.environ.get("EVIDENCE_PATH", "w3-lab-eip.json")), payload)
        return payload
    allocation_id = str(decision["allocation_id"])
    args = release_args(allocation_id)
    lab.refuse_forbidden_command(args)
    proc = runner(args)
    text = f"{proc.stderr or ''}{proc.stdout or ''}"
    if proc.returncode != 0:
        payload["status"] = "RELEASE_DENIED" if _denied(text) else "RELEASE_FAILED"
        payload["reason"] = payload["status"].lower()
        lab.write_json_with_hash(Path(os.environ.get("EVIDENCE_PATH", "w3-lab-eip.json")), payload)
        raise lab.GuardAbort(payload["status"].lower())
    after, after_error = describe_address(runner)
    payload["after"] = public_view(after)
    payload["mutated"] = True
    payload["released"] = after is None and after_error is None
    payload["status"] = "RELEASED" if payload["released"] else "RELEASE_UNCONFIRMED"
    if after_error:
        payload["reason"] = after_error
    lab.write_json_with_hash(Path(os.environ.get("EVIDENCE_PATH", "w3-lab-eip.json")), payload)
    if not payload["released"]:
        raise lab.GuardAbort("release_unconfirmed")
    return payload


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] != "release-if-clear":
        print("usage: w3_lab_eip.py release-if-clear", file=sys.stderr)
        return 1
    try:
        execute(lab.default_runner)
    except lab.GuardAbort as exc:
        print(exc.reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
