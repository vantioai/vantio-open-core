#!/usr/bin/env python3
"""Arm, collect, teardown, and long-soak decisions for the Free lab.

Launch of a host that lives past seven hours, and SSH from a runner, stay
off until scripts/aws/lab_iam_capabilities.json says the console change is
recorded. This file does not call AWS in that default state.

Collect, teardown, and verify-removed do call AWS when invoked. They refuse
resources that do not carry the owned lab tags. A private key is never
written into the evidence JSON.

Audience: INTERNAL_RESTRICTED
"""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import w3_lab_auto as lab

HEX64 = re.compile(r"^[0-9a-f]{64}$")
MARKER_LINE = re.compile(r"^vantio-lab-marker seal=[0-9a-f]{64} pin=[0-9a-f]{64}$")
CHECK_LINE = re.compile(
    r"^vantio-lab-check seq=([0-9]{1,6}) name=([A-Za-z0-9_-]{1,40}) result=(pass|fail|skip) sha256=([0-9a-f]{64})$"
)
SECRET = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----"
    r"|AKIA[0-9A-Z]{16}"
    r"|ghp_[A-Za-z0-9]{20,}",
    re.S,
)
DEFAULT_MARKER = Path(__file__).resolve().with_name("lab-guests") / "marker.sh"
DEFAULT_ENTERPRISE_GUEST = Path(__file__).resolve().with_name("lab-guests") / "enterprise-rows.sh"
DEFAULT_DESCENDANT_GUEST = Path(__file__).resolve().with_name("lab-guests") / "descendant_b1.py"
GUEST_BUNDLE = "/var/lib/vantio-lab/enterprise-bundle"
Runner = lab.Runner
SshRunner = Callable[[list[str], str], subprocess.CompletedProcess[str]]
Keygen = Callable[[Path], tuple[Path, str]]


def require_instance_id(value: str) -> str:
    if lab.ID_SHAPES["instance"].match(value) is None or value in lab.DENYLIST_IDS:
        raise lab.GuardAbort("instance_id")
    return value


def require_hex64(value: str, field: str) -> str:
    if HEX64.fullmatch(value) is None:
        raise lab.GuardAbort(field)
    return value


def require_global_32(cidr: str) -> str:
    try:
        network = ipaddress.ip_network(cidr, strict=True)
    except ValueError:
        raise lab.GuardAbort("cidr") from None
    if network.version != 4 or network.prefixlen != 32:
        raise lab.GuardAbort("cidr")
    address = network.network_address
    if not isinstance(address, ipaddress.IPv4Address) or not address.is_global:
        raise lab.GuardAbort("cidr")
    return str(network)


def parse_check_lines(text: str, *, source: str) -> list[dict[str, Any]]:
    """Pull check records out of console or guest text. Other lines are ignored."""
    found: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    for raw in text.splitlines():
        match = CHECK_LINE.fullmatch(raw.strip())
        if match is None:
            continue
        seq = int(match.group(1))
        digest = match.group(4)
        if (seq, digest) in seen:
            continue
        seen.add((seq, digest))
        found.append(
            {
                "name": match.group(2),
                "result": match.group(3),
                "seq": seq,
                "sha256": digest,
                "source": source,
            }
        )
    found.sort(key=lambda item: int(item["seq"]))
    return found


def redact(text: str) -> tuple[str, bool]:
    cleaned, count = SECRET.subn("[redacted]", text)
    return cleaned, count > 0


def github_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT", "").strip()
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def evidence_path(default: str) -> Path:
    return Path(os.environ.get("EVIDENCE_PATH", default))


def base_evidence(step: str) -> dict[str, Any]:
    return {
        "account_id": lab.ACCOUNT_ID,
        "mutated": False,
        "noninteractive_teardown_ready": False,
        "region": lab.REGION,
        "step": step,
    }


def dry_run(runner: Runner, args: list[str]) -> str:
    probe = [*args, "--dry-run"]
    lab.refuse_forbidden_command(probe)
    proc = runner(probe)
    text = f"{proc.stderr or ''}{proc.stdout or ''}"
    if "DryRunOperation" in text:
        return "allowed"
    if "UnauthorizedOperation" in text or "AccessDenied" in text:
        return "denied"
    code = ""
    matched = re.search(r"\(([A-Za-z0-9.]+)\)", text)
    if matched:
        code = matched.group(1)
    raise lab.GuardAbort("dry_run" if not code else f"dry_run_{code}")


def authorize_args(group_id: str, cidr: str, *, revoke: bool) -> list[str]:
    if lab.ID_SHAPES["security-group"].match(group_id) is None:
        raise lab.GuardAbort("security_group")
    action = "revoke-security-group-ingress" if revoke else "authorize-security-group-ingress"
    permissions = [
        {
            "FromPort": 22,
            "IpProtocol": "tcp",
            "IpRanges": [{"CidrIp": require_global_32(cidr), "Description": "runner-ssh"}],
            "ToPort": 22,
        }
    ]
    return [
        "aws",
        "ec2",
        action,
        "--region",
        lab.REGION,
        "--group-id",
        group_id,
        "--ip-permissions",
        json.dumps(permissions, separators=(",", ":")),
    ]


def first_instance(payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
    reservations = payload.get("Reservations") or []
    if not isinstance(reservations, list):
        return None
    for reservation in reservations:
        if not isinstance(reservation, Mapping):
            continue
        instances = reservation.get("Instances") or []
        if not isinstance(instances, list):
            continue
        for instance in instances:
            if isinstance(instance, Mapping):
                return instance
    return None


def describe_instance(runner: Runner, instance_id: str) -> Mapping[str, Any] | None:
    args = [
        "aws",
        "ec2",
        "describe-instances",
        "--region",
        lab.REGION,
        "--instance-ids",
        instance_id,
        "--output",
        "json",
    ]
    lab.refuse_forbidden_command(args)
    proc = runner(args)
    text = f"{proc.stderr or ''}{proc.stdout or ''}"
    if proc.returncode != 0:
        if "InvalidInstanceID.NotFound" in text:
            return None
        raise lab.GuardAbort("describe_instance")
    payload = json.loads(proc.stdout or "{}")
    if not isinstance(payload, dict):
        raise lab.GuardAbort("describe_instance")
    return first_instance(payload)


def instance_state(instance: Mapping[str, Any]) -> str:
    state = instance.get("State")
    if isinstance(state, Mapping) and isinstance(state.get("Name"), str):
        return str(state["Name"])
    return ""


def public_ipv4(instance: Mapping[str, Any]) -> str:
    value = instance.get("PublicIpAddress")
    if isinstance(value, str) and value:
        return value
    return ""


def security_group_id(instance: Mapping[str, Any]) -> str:
    groups = instance.get("SecurityGroups")
    if not isinstance(groups, list) or len(groups) != 1 or not isinstance(groups[0], Mapping):
        raise lab.GuardAbort("security_group")
    group_id = groups[0].get("GroupId")
    if not isinstance(group_id, str) or lab.ID_SHAPES["security-group"].match(group_id) is None:
        raise lab.GuardAbort("security_group")
    return group_id


def availability_zone(instance: Mapping[str, Any]) -> str:
    placement = instance.get("Placement")
    if not isinstance(placement, Mapping):
        raise lab.GuardAbort("availability_zone")
    zone = placement.get("AvailabilityZone")
    if not isinstance(zone, str) or not zone.startswith("us-east-2"):
        raise lab.GuardAbort("availability_zone")
    return zone


def console_text(payload: Mapping[str, Any]) -> str:
    raw = payload.get("Output")
    if not isinstance(raw, str) or raw == "":
        return ""
    try:
        return base64.b64decode(raw, validate=True).decode("utf-8", "replace")
    except ValueError:
        return raw


def default_keygen(directory: Path) -> tuple[Path, str]:
    private = directory / "lab-ed25519"
    proc = subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "vantio-lab", "-f", str(private)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 or not private.exists():
        raise lab.GuardAbort("keygen")
    public = private.with_suffix(private.suffix + ".pub").read_text(encoding="utf-8").strip()
    return private, public


def default_ssh(args: list[str], script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, input=script, capture_output=True, text=True, check=False)


def shred_file(path: Path) -> None:
    if not path.exists():
        return
    subprocess.run(["shred", "-u", str(path)], capture_output=True, check=False)
    if path.exists():
        path.write_bytes(b"\0" * max(path.stat().st_size, 1))
        path.unlink()


def write_stamp(path: Path, stamp: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(stamp, sort_keys=True) + "\n", encoding="utf-8")


def revoke_quietly(runner: Runner, group_id: str, cidr: str) -> None:
    args = authorize_args(group_id, cidr, revoke=True)
    lab.refuse_forbidden_command(args)
    proc = runner(args)
    if proc.returncode == 0:
        return
    text = f"{proc.stderr or ''}{proc.stdout or ''}"
    if "InvalidPermission.NotFound" in text:
        return
    raise lab.GuardAbort("revoke_ssh")


def open_ssh(
    runner: Runner,
    instance: Mapping[str, Any],
    cidr: str,
    stamp_path: Path,
    keygen: Keygen,
    ssh_runner: SshRunner,
    remote_argv: list[str],
    script: str,
) -> dict[str, Any]:
    """Authorize one /32, push a one-minute key, run the command, then close."""
    group_id = security_group_id(instance)
    instance_id = str(instance.get("InstanceId"))
    zone = availability_zone(instance)
    host = public_ipv4(instance)
    if not host:
        raise lab.GuardAbort("no_public_ipv4")
    require_global_32(cidr)
    authorize = authorize_args(group_id, cidr, revoke=False)
    revoke = authorize_args(group_id, cidr, revoke=True)
    connect = [
        "aws",
        "ec2-instance-connect",
        "send-ssh-public-key",
        "--region",
        lab.REGION,
        "--instance-id",
        instance_id,
        "--availability-zone",
        zone,
        "--instance-os-user",
        "ubuntu",
        "--ssh-public-key",
    ]
    # Revoke must dry-run as allowed before any ingress is opened.
    # send-ssh-public-key rejects --dry-run in the AWS CLI, so that call is
    # not probed. A denied send still hits the finally block that revokes.
    if dry_run(runner, revoke) == "denied" or dry_run(runner, authorize) == "denied":
        return {"opened": False, "reason": "ssh_permission_denied"}
    directory = stamp_path.parent
    private, public = keygen(directory)
    stamp = {"authorized": True, "cidr": cidr, "group_id": group_id, "instance_id": instance_id}
    write_stamp(stamp_path, stamp)
    try:
        lab.aws_json(runner, authorize)
        send = connect + [public]
        lab.aws_json(runner, send)
        known = directory / "known_hosts"
        ssh_args = [
            "ssh",
            "-i",
            str(private),
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            f"UserKnownHostsFile={known}",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            f"ubuntu@{host}",
            *remote_argv,
        ]
        proc = ssh_runner(ssh_args, script)
        if proc.returncode != 0:
            raise lab.GuardAbort("ssh")
        return {"opened": True, "stdout": proc.stdout or ""}
    finally:
        revoke_quietly(runner, group_id, cidr)
        stamp["authorized"] = False
        write_stamp(stamp_path, stamp)
        shred_file(private)
        shred_file(private.with_suffix(private.suffix + ".pub"))


def preflight_arm() -> int:
    caps = lab.load_lab_capabilities()
    proceed = caps["ssh_instance_connect"]
    payload = base_evidence("arm")
    payload.update(
        {
            "proceed": proceed,
            "reason": None if proceed else "ssh_instance_connect_not_enabled",
            "ssm": "not_enabled" if not caps["ssm"] else "not_implemented",
            "status": "READY" if proceed else "BLOCKED_IAM",
        }
    )
    lab.write_json_with_hash(evidence_path("w3-lab-arm.json"), payload)
    github_output("proceed", "true" if proceed else "false")
    return 0 if proceed else 2


def preflight_long_soak() -> int:
    raw_hours = os.environ.get("SOAK_HOURS", "36").strip()
    execute = lab.parse_bool(os.environ.get("EXECUTE", "false"))
    try:
        hours = int(raw_hours)
    except ValueError:
        hours = 0
    caps = lab.load_lab_capabilities()
    reason = None
    if hours < 1 or hours > 36:
        reason = "soak_hours"
    elif hours <= 7:
        reason = "use_provision_workflow"
    elif not caps["max_life_hours_36"]:
        reason = "max_life_hours_36_not_enabled"
    elif not execute:
        reason = "execute_not_requested"
    proceed = reason is None
    payload = base_evidence("long-soak")
    payload.update(
        {
            "execute": execute,
            "proceed": proceed,
            "reason": reason,
            "soak_hours": hours,
            "status": "READY" if proceed else "BLOCKED_IAM",
        }
    )
    lab.write_json_with_hash(evidence_path("w3-lab-long-soak.json"), payload)
    github_output("proceed", "true" if proceed else "false")
    return 0 if proceed else 2


def execute_arm(
    runner: Runner,
    *,
    keygen: Keygen = default_keygen,
    ssh_runner: SshRunner = default_ssh,
) -> dict[str, Any]:
    payload = base_evidence("arm")
    try:
        if not lab.load_lab_capabilities()["ssh_instance_connect"]:
            raise lab.GuardAbort("ssh_instance_connect_not_enabled")
        instance_id = require_instance_id(os.environ.get("INSTANCE_ID", "").strip())
        seal = require_hex64(os.environ.get("SEAL", "").strip(), "seal")
        pin = require_hex64(os.environ.get("PUBLIC_PIN", "").strip(), "public_pin")
        cidr = require_global_32(os.environ.get("W3_RUNNER_CIDR", "").strip())
        payload.update({"instance_id": instance_id, "public_pin": pin, "seal": seal})
        identity = lab.aws_json(runner, ["aws", "sts", "get-caller-identity"])
        lab.require_identity(identity)
        instance = describe_instance(runner, instance_id)
        if instance is None:
            raise lab.GuardAbort("instance_absent")
        tags = lab._tag_list(instance.get("Tags"))
        if not lab.lab_tags_owned(tags):
            raise lab.GuardAbort("not_owned")
        if instance_state(instance) != "running":
            raise lab.GuardAbort("instance_state")
        if not public_ipv4(instance):
            raise lab.GuardAbort("no_public_ipv4")
        script_path = Path(os.environ.get("W3_MARKER_SCRIPT", str(DEFAULT_MARKER)))
        script = script_path.read_text(encoding="utf-8")
        stamp_path = Path(os.environ.get("W3_STAMP", "w3-lab-ssh-stamp.json"))
        result = open_ssh(
            runner,
            instance,
            cidr,
            stamp_path,
            keygen,
            ssh_runner,
            ["bash", "-s", "--", seal, pin],
            script,
        )
        payload.update(
            {
                "mutated": bool(result.get("opened")),
                "reason": result.get("reason"),
                "status": "ARMED" if result.get("opened") else "BLOCKED_IAM",
            }
        )
        if not result.get("opened"):
            raise lab.GuardAbort(str(result.get("reason") or "ssh"))
    except lab.GuardAbort as exc:
        payload.update({"reason": exc.reason, "status": payload.get("status") or "FAILED"})
        lab.write_json_with_hash(evidence_path("w3-lab-arm.json"), payload)
        raise
    lab.write_json_with_hash(evidence_path("w3-lab-arm.json"), payload)
    return payload


def execute_collect(runner: Runner, *, ssh_runner: SshRunner = default_ssh, keygen: Keygen = default_keygen) -> dict[str, Any]:
    instance_id = require_instance_id(os.environ.get("INSTANCE_ID", "").strip())
    identity = lab.aws_json(runner, ["aws", "sts", "get-caller-identity"])
    lab.require_identity(identity)
    instance = describe_instance(runner, instance_id)
    payload = base_evidence("collect")
    payload["instance_id"] = instance_id
    caps = lab.load_lab_capabilities()
    payload["ssm"] = "not_enabled" if not caps["ssm"] else "not_implemented"
    if instance is None:
        payload.update({"reason": "instance_absent", "status": "NOT_FOUND"})
        lab.write_json_with_hash(evidence_path("w3-lab-collect.json"), payload)
        raise lab.GuardAbort("instance_absent")
    tags = lab._tag_list(instance.get("Tags"))
    if not lab.lab_tags_owned(tags):
        payload.update({"reason": "not_owned", "status": "NOT_OWNED"})
        lab.write_json_with_hash(evidence_path("w3-lab-collect.json"), payload)
        raise lab.GuardAbort("not_owned")
    console = lab.aws_json(
        runner,
        ["aws", "ec2", "get-console-output", "--region", lab.REGION, "--instance-id", instance_id, "--latest"],
    )
    text, redacted = redact(console_text(console))
    marker = next((line for line in text.splitlines() if MARKER_LINE.fullmatch(line)), None)
    checks = parse_check_lines(text, source="console")
    payload.update(
        {
            "checks": checks,
            "collect_channel": "console",
            "console_redacted": redacted,
            "console_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "marker_line": marker,
            "marker_found": marker is not None,
            "status": "COLLECTED",
        }
    )
    if caps["ssh_instance_connect"] and public_ipv4(instance) and os.environ.get("W3_RUNNER_CIDR", "").strip():
        script = (
            "cat /var/lib/vantio-lab/marker.json 2>/dev/null || true\n"
            "printf '%s\\n' '---CHECKS---'\n"
            "cat /var/lib/vantio-lab/checks.ndjson 2>/dev/null || true\n"
        )
        stamp_path = Path(os.environ.get("W3_STAMP", "w3-lab-ssh-stamp.json"))
        opened = open_ssh(
            runner,
            instance,
            os.environ["W3_RUNNER_CIDR"].strip(),
            stamp_path,
            keygen,
            ssh_runner,
            ["bash", "-s"],
            script,
        )
        payload["mutated"] = bool(opened.get("opened"))
        payload["collect_channel"] = "console+ssh" if opened.get("opened") else "console"
        guest = redact(str(opened.get("stdout") or ""))[0]
        marker_part, _, check_part = guest.partition("---CHECKS---")
        marker_part = marker_part.strip()
        if marker_part.startswith("{") and "PRIVATE" not in marker_part:
            payload["guest_marker_sha256"] = hashlib.sha256(marker_part.encode("utf-8")).hexdigest()
        pulled = parse_check_lines(check_part, source="guest-file")
        by_key = {(item["seq"], item["sha256"]): item for item in checks}
        for item in pulled:
            by_key[(item["seq"], item["sha256"])] = item
        payload["checks"] = sorted(by_key.values(), key=lambda item: int(item["seq"]))
    lab.write_json_with_hash(evidence_path("w3-lab-collect.json"), payload)
    return payload


def due_instance_ids(described: Mapping[str, Any], now: datetime) -> list[str]:
    found: list[str] = []
    reservations = described.get("Reservations") or []
    if not isinstance(reservations, list):
        return found
    for reservation in reservations:
        if not isinstance(reservation, Mapping):
            continue
        instances = reservation.get("Instances") or []
        if not isinstance(instances, list):
            continue
        for instance in instances:
            if not isinstance(instance, Mapping):
                continue
            tags = lab._tag_list(instance.get("Tags"))
            if not lab.lab_tags_owned(tags):
                continue
            launch = instance.get("LaunchTime")
            try:
                started = lab.parse_time(launch)
            except (TypeError, ValueError):
                continue
            if now - started > timedelta(hours=48):
                continue
            instance_id = instance.get("InstanceId")
            if isinstance(instance_id, str) and lab.ID_SHAPES["instance"].match(instance_id):
                found.append(instance_id)
    return found


def execute_collect_due(runner: Runner, now: datetime, *, ssh_runner: SshRunner = default_ssh, keygen: Keygen = default_keygen) -> dict[str, Any]:
    """Copy check lines off every recent owned lab. Idle is a valid result."""
    identity = lab.aws_json(runner, ["aws", "sts", "get-caller-identity"])
    lab.require_identity(identity)
    described = lab.aws_json(runner, ["aws", "ec2", "describe-instances", "--region", lab.REGION])
    rows: list[dict[str, Any]] = []
    previous = os.environ.get("INSTANCE_ID")
    try:
        for instance_id in due_instance_ids(described, now):
            os.environ["INSTANCE_ID"] = instance_id
            try:
                one = execute_collect(runner, ssh_runner=ssh_runner, keygen=keygen)
            except lab.GuardAbort as exc:
                one = {"checks": [], "instance_id": instance_id, "reason": exc.reason, "status": "FAILED"}
            rows.append(
                {
                    "checks": one.get("checks") or [],
                    "instance_id": instance_id,
                    "status": one.get("status"),
                }
            )
    finally:
        if previous is None:
            os.environ.pop("INSTANCE_ID", None)
        else:
            os.environ["INSTANCE_ID"] = previous
    checks = [item for row in rows for item in row["checks"]]
    payload = base_evidence("collect-due")
    payload.update(
        {
            "check_count": len(checks),
            "checks": checks,
            "instances": rows,
            "status": "COLLECTED" if rows else "IDLE",
        }
    )
    lab.write_json_with_hash(evidence_path("w3-lab-collect.json"), payload)
    return payload


def related_owned(resources: list[Mapping[str, Any]], name: str) -> list[Mapping[str, Any]]:
    chosen: list[Mapping[str, Any]] = []
    for resource in resources:
        tags = resource.get("tags")
        if not isinstance(tags, Mapping) or not lab.lab_tags_owned(tags):
            continue
        if tags.get("Name") == name:
            chosen.append(resource)
    return chosen


def execute_teardown(runner: Runner, now: datetime) -> dict[str, Any]:
    instance_id = require_instance_id(os.environ.get("INSTANCE_ID", "").strip())
    identity = lab.aws_json(runner, ["aws", "sts", "get-caller-identity"])
    lab.require_identity(identity)
    instance = describe_instance(runner, instance_id)
    payload = base_evidence("teardown")
    payload["instance_id"] = instance_id
    if instance is None:
        payload.update({"reason": "instance_absent", "status": "NOT_FOUND"})
        lab.write_json_with_hash(evidence_path("w3-lab-teardown.json"), payload)
        raise lab.GuardAbort("instance_absent")
    tags = lab._tag_list(instance.get("Tags"))
    if not lab.lab_tags_owned(tags):
        payload.update({"reason": "not_owned", "status": "NOT_OWNED"})
        lab.write_json_with_hash(evidence_path("w3-lab-teardown.json"), payload)
        raise lab.GuardAbort("not_owned")
    name = str(tags.get("Name"))
    state = instance_state(instance)
    called: list[str] = []
    if state in lab.OCCUPYING_STATES:
        called.extend(
            lab._delete_resource(
                {"type": "instance", "id": instance_id, "region": lab.REGION, "tags": tags},
                runner,
            )
        )
    census = lab.census_from_aws(runner)
    for resource in related_owned(census, name):
        if resource.get("type") == "instance":
            continue
        called.extend(lab._delete_resource(resource, runner))
    check = execute_verify(runner, now, write=False)
    payload.update(
        {
            "called": called,
            "mutated": bool(called),
            "name": name,
            "slot_clear": check["slot_clear"],
            "status": check["status"],
        }
    )
    lab.write_json_with_hash(evidence_path("w3-lab-teardown.json"), payload)
    return payload


def execute_verify(runner: Runner, now: datetime, *, write: bool = True) -> dict[str, Any]:
    del now
    instance_id = require_instance_id(os.environ.get("INSTANCE_ID", "").strip())
    identity = lab.aws_json(runner, ["aws", "sts", "get-caller-identity"])
    lab.require_identity(identity)
    instance = describe_instance(runner, instance_id)
    census = lab.census_from_aws(runner)
    occupying = lab.occupying_instance_ids(lab.aws_json(runner, lab.describe_occupying_args()))
    name = None
    owned = False
    state = "absent"
    if instance is not None:
        tags = lab._tag_list(instance.get("Tags"))
        owned = lab.lab_tags_owned(tags)
        name = tags.get("Name") if owned else None
        state = instance_state(instance)
    leftovers = []
    if isinstance(name, str):
        leftovers = [
            {"id": item.get("id"), "type": item.get("type")}
            for item in related_owned(census, name)
            if not (item.get("type") == "instance" and item.get("id") == instance_id and state == "terminated")
        ]
    name_hint = os.environ.get("LAB_NAME", "").strip()
    if instance is None and name_hint.startswith(lab.NAME_PREFIX):
        leftovers = [
            {"id": item.get("id"), "type": item.get("type")}
            for item in related_owned(census, name_hint)
        ]
        owned = True
    if instance is not None and not owned:
        status = "NOT_OWNED"
    elif instance is not None and state == "terminated" and owned and not leftovers:
        status = "VERIFIED_REMOVED"
    elif instance is None and name_hint.startswith(lab.NAME_PREFIX) and not leftovers and instance_id not in occupying:
        status = "VERIFIED_REMOVED"
    elif instance is None:
        status = "INSTANCE_ABSENT"
    else:
        status = "NOT_REMOVED"
    payload = base_evidence("verify-removed")
    payload.update(
        {
            "instance_id": instance_id,
            "instance_state": state,
            "leftovers": leftovers,
            "other_occupying_instance_ids": [item for item in occupying if item != instance_id],
            "owned": owned,
            "slot_clear": occupying == [],
            "status": status,
        }
    )
    if write:
        lab.write_json_with_hash(evidence_path("w3-lab-verify-removed.json"), payload)
    return payload


def _ssh_failure(proc: subprocess.CompletedProcess[str]) -> None:
    raw = (proc.stderr or "") + "\n" + (proc.stdout or "")
    redacted, _changed = redact(raw)
    flat = " ".join(redacted.split())[-180:]
    raise lab.GuardAbort("ssh" if not flat else f"ssh {flat}")


def _store_guest_rows(path: Path, text: str) -> None:
    token = os.environ.get("W3_LAB_PRIVATE_BUNDLE_TOKEN", "")
    redacted, _changed = redact(text)
    if token and token in redacted:
        raise lab.GuardAbort("token_in_evidence")
    if "PRIVATE KEY" in redacted:
        raise lab.GuardAbort("token_in_evidence")
    try:
        parsed = json.loads(redacted)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        lab.write_json_with_hash(path, parsed)
        return
    path.write_text(redacted if redacted.endswith("\n") else redacted + "\n", encoding="utf-8")


def _ssh_base(private: Path, known: Path, host: str) -> list[str]:
    return [
        "-i",
        str(private),
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        f"UserKnownHostsFile={known}",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=15",
        "-o",
        "ServerAliveInterval=30",
        "-o",
        "ServerAliveCountMax=40",
        f"ubuntu@{host}",
    ]


def _wait_for_reboot(
    runner: Runner,
    instance_id: str,
    remote: Callable[[list[str], str], subprocess.CompletedProcess[str]],
    connect_with_key: list[str],
) -> None:
    """Wait until SSH drops for the reboot, then comes back with a new key."""
    deadline = time.time() + 300
    dropped = False
    while time.time() < deadline:
        probe = remote(["true"], "")
        if probe.returncode != 0:
            dropped = True
            break
        time.sleep(2)
    if not dropped:
        raise lab.GuardAbort("reboot_timeout")
    while time.time() < deadline:
        instance = describe_instance(runner, instance_id)
        if instance is not None and instance_state(instance) == "running":
            try:
                lab.aws_json(runner, connect_with_key)
            except lab.GuardAbort:
                time.sleep(5)
                continue
            if remote(["true"], "").returncode == 0:
                return
        time.sleep(5)
    raise lab.GuardAbort("reboot_timeout")


def execute_enterprise_rows(
    runner: Runner,
    *,
    keygen: Keygen = default_keygen,
    ssh_runner: SshRunner = default_ssh,
    checker: Callable[[Path], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Copy a checked bundle to one owned host and run the row script.

    prepare-bundle must already have accepted the directory. This command
    still re-checks the seal and the trust file before it opens SSH.
    """
    payload = base_evidence("arm-enterprise")
    stamp_path = Path(os.environ.get("W3_STAMP", "w3-lab-ssh-stamp.json"))
    private: Path | None = None
    try:
        if not lab.load_lab_capabilities()["ssh_instance_connect"]:
            raise lab.GuardAbort("ssh_instance_connect_not_enabled")
        instance_id = require_instance_id(os.environ.get("INSTANCE_ID", "").strip())
        seal = require_hex64(os.environ.get("SEAL", "").strip(), "seal")
        pin = require_hex64(os.environ.get("PUBLIC_PIN", "").strip(), "public_pin")
        import enterprise_bundle

        if seal != enterprise_bundle.POLICY_ALLOW_SEAL or pin != enterprise_bundle.PUBLIC_INSTALLER_PIN:
            raise lab.GuardAbort("bundle_wrong_seal")
        cidr = require_global_32(os.environ.get("W3_RUNNER_CIDR", "").strip())
        bundle_dir = Path(os.environ.get("W3_BUNDLE_DIR", ""))
        if not bundle_dir.is_dir():
            raise lab.GuardAbort("bundle_layout")
        check = checker or enterprise_bundle.inspect_bundle
        inspected = dict(check(bundle_dir))
        payload.update(inspected)
        payload.update({"instance_id": instance_id, "public_pin": pin, "seal": seal})
        identity = lab.aws_json(runner, ["aws", "sts", "get-caller-identity"])
        lab.require_identity(identity)
        instance = describe_instance(runner, instance_id)
        if instance is None:
            raise lab.GuardAbort("instance_absent")
        tags = lab._tag_list(instance.get("Tags"))
        if not lab.lab_tags_owned(tags):
            raise lab.GuardAbort("not_owned")
        if instance_state(instance) != "running":
            raise lab.GuardAbort("instance_state")
        host = public_ipv4(instance)
        if not host:
            raise lab.GuardAbort("no_public_ipv4")
        group_id = security_group_id(instance)
        zone = availability_zone(instance)
        authorize = authorize_args(group_id, cidr, revoke=False)
        revoke = authorize_args(group_id, cidr, revoke=True)
        connect = [
            "aws",
            "ec2-instance-connect",
            "send-ssh-public-key",
            "--region",
            lab.REGION,
            "--instance-id",
            instance_id,
            "--availability-zone",
            zone,
            "--instance-os-user",
            "ubuntu",
            "--ssh-public-key",
        ]
        if dry_run(runner, revoke) == "denied" or dry_run(runner, authorize) == "denied":
            payload.update({"reason": "ssh_permission_denied", "status": "BLOCKED_IAM"})
            raise lab.GuardAbort("ssh_permission_denied")
        directory = stamp_path.parent
        private, public = keygen(directory)
        known = directory / "known_hosts"
        stamp = {"authorized": True, "cidr": cidr, "group_id": group_id, "instance_id": instance_id}
        try:
            write_stamp(stamp_path, stamp)
            lab.aws_json(runner, authorize)
            lab.aws_json(runner, connect + [public])
            base = _ssh_base(private, known, host)

            def remote(argv: list[str], script: str) -> subprocess.CompletedProcess[str]:
                return ssh_runner(["ssh", *base, *argv], script)

            def copy_to(local: Path, name: str) -> None:
                if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
                    raise lab.GuardAbort("bundle_layout")
                proc = ssh_runner(
                    ["scp", *base[:-1], str(local), f"ubuntu@{host}:{GUEST_BUNDLE}/{name}"],
                    "",
                )
                if proc.returncode != 0:
                    _ssh_failure(proc)

            made = remote(["sudo", "mkdir", "-p", GUEST_BUNDLE], "")
            if made.returncode != 0:
                _ssh_failure(made)
            owned = remote(["sudo", "chown", "-R", "ubuntu:ubuntu", "/var/lib/vantio-lab"], "")
            if owned.returncode != 0:
                _ssh_failure(owned)
            copy_to(bundle_dir / "seal.oci.tar", "seal.oci.tar")
            copy_to(bundle_dir / "contract.tar", "contract.tar")
            script_path = Path(os.environ.get("W3_ENTERPRISE_SCRIPT", str(DEFAULT_ENTERPRISE_GUEST)))
            copy_to(script_path, "enterprise-rows.sh")
            battery = os.environ.get("W3_BATTERY", "enterprise").strip() or "enterprise"
            if battery not in ("enterprise", "descendant-b1"):
                raise lab.GuardAbort("battery")
            payload["battery"] = battery
            if battery == "descendant-b1":
                descendant = Path(os.environ.get("W3_DESCENDANT_SCRIPT", str(DEFAULT_DESCENDANT_GUEST)))
                copy_to(descendant, "descendant_b1.py")
                probe_c = descendant.with_name("descendant_probe.c")
                copy_to(probe_c, "descendant_probe.c")
                pre = remote(["bash", f"{GUEST_BUNDLE}/enterprise-rows.sh", seal, "descendant-b1", "pre"], "")
                if pre.returncode != 0:
                    ran = pre
                else:
                    _wait_for_reboot(runner, instance_id, remote, connect + [public])
                    ran = remote(["bash", f"{GUEST_BUNDLE}/enterprise-rows.sh", seal, "descendant-b1", "post"], "")
            else:
                ran = remote(["bash", f"{GUEST_BUNDLE}/enterprise-rows.sh", seal], "")
            rows_local = Path(os.environ.get("W3_ROWS_PATH", "w3-lab-enterprise-rows.json"))
            # Instance Connect keys last 60 seconds. The guest script can run longer.
            # A new scp is a new connection, so send the key again before the pull.
            lab.aws_json(runner, connect + [public])
            pulled = ssh_runner(
                ["scp", *base[:-1], f"ubuntu@{host}:/tmp/enterprise-pe-rows.json", str(rows_local)],
                "",
            )
            if pulled.returncode == 0 and rows_local.is_file():
                guest_text = rows_local.read_text(encoding="utf-8", errors="replace")
            else:
                guest_text = (ran.stdout or "") + (ran.stderr or "")
            _store_guest_rows(rows_local, guest_text)
            payload["rows_sha256"] = hashlib.sha256(rows_local.read_bytes()).hexdigest()
            payload["guest_rc"] = ran.returncode
            payload["mutated"] = True
            if ran.returncode != 0:
                payload.update({"reason": "guest", "status": "FAILED"})
                raise lab.GuardAbort("guest")
            payload["status"] = "DESCENDANT_B1" if battery == "descendant-b1" else "ENTERPRISE_ROWS"
        finally:
            if private is not None:
                shred_file(private)
                shred_file(private.with_suffix(private.suffix + ".pub"))
                private = None
            if stamp_path.is_file():
                revoke_quietly(runner, group_id, cidr)
                stamp["authorized"] = False
                write_stamp(stamp_path, stamp)
    except lab.GuardAbort as exc:
        if not payload.get("reason"):
            payload["reason"] = exc.reason
        if not payload.get("status"):
            payload["status"] = "FAILED"
        lab.write_json_with_hash(evidence_path("w3-lab-arm.json"), payload)
        raise
    lab.write_json_with_hash(evidence_path("w3-lab-arm.json"), payload)
    return payload


def close_ssh(runner: Runner) -> int:
    stamp_path = Path(os.environ.get("W3_STAMP", "w3-lab-ssh-stamp.json"))
    if not stamp_path.exists():
        return 0
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    if not isinstance(stamp, dict) or stamp.get("authorized") is not True:
        return 0
    group_id = stamp.get("group_id")
    cidr = stamp.get("cidr")
    if not isinstance(group_id, str) or not isinstance(cidr, str):
        raise lab.GuardAbort("stamp")
    revoke_quietly(runner, group_id, cidr)
    stamp["authorized"] = False
    write_stamp(stamp_path, stamp)
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(
            "usage: w3_lab_steps.py preflight-arm|preflight-long-soak|arm|arm-enterprise|prepare-bundle|close-ssh|collect|collect-due|teardown|verify-removed",
            file=sys.stderr,
        )
        return 1
    command = argv[1]
    now = datetime.now(timezone.utc)
    try:
        if command == "preflight-arm":
            return preflight_arm()
        if command == "preflight-long-soak":
            return preflight_long_soak()
        if command == "arm":
            execute_arm(lab.default_runner, keygen=default_keygen, ssh_runner=default_ssh)
            return 0
        if command == "prepare-bundle":
            import enterprise_bundle

            enterprise_bundle.prepare_bundle()
            return 0
        if command == "arm-enterprise":
            execute_enterprise_rows(lab.default_runner, keygen=default_keygen, ssh_runner=default_ssh)
            return 0
        if command == "close-ssh":
            return close_ssh(lab.default_runner)
        if command == "collect":
            execute_collect(lab.default_runner)
            return 0
        if command == "collect-due":
            execute_collect_due(lab.default_runner, now)
            return 0
        if command == "teardown":
            execute_teardown(lab.default_runner, now)
            return 0
        if command == "verify-removed":
            result = execute_verify(lab.default_runner, now)
            return 0 if result["status"] == "VERIFIED_REMOVED" else 2
    except lab.GuardAbort as exc:
        print(exc.reason, file=sys.stderr)
        return 2
    print(f"unknown command {command}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
