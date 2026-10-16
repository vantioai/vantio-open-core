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
    r"|ASIA[0-9A-Z]{16}"
    r"|ghp_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|(?i:aws_secret_access_key\s*[:=]\s*\S+)"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}",
    re.S,
)
DEFAULT_MARKER = Path(__file__).resolve().with_name("lab-guests") / "marker.sh"
DEFAULT_ENTERPRISE_GUEST = Path(__file__).resolve().with_name("lab-guests") / "enterprise-rows.sh"
DEFAULT_DESCENDANT_GUEST = Path(__file__).resolve().with_name("lab-guests") / "descendant_b1.py"
DEFAULT_REDTEAM_ROWS = Path(__file__).resolve().parents[1] / "gcp" / "lab-guests" / "redteam_rows.py"
DEFAULT_REDTEAM_PACKET = Path(__file__).resolve().parents[1] / "gcp" / "redteam_packet.py"
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


def parse_check_details(text: str) -> list[dict[str, Any]]:
    """Read record-check payloads. A payload with a private key is dropped."""
    found: list[dict[str, Any]] = []
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw.startswith("{") or "PRIVATE" in raw:
            continue
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(body, dict):
            continue
        detail = body.get("detail")
        name = body.get("name")
        result = body.get("result")
        seq = body.get("seq")
        if not isinstance(detail, str) or re.fullmatch(r"[A-Za-z0-9_.:-]*", detail) is None:
            continue
        if not isinstance(name, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,40}", name) is None:
            continue
        if result not in {"pass", "fail", "skip"}:
            continue
        if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
            continue
        found.append({"detail": detail, "name": name, "result": result, "seq": seq})
    found.sort(key=lambda item: int(item["seq"]))
    return found


def redact(text: str) -> tuple[str, bool]:
    """Strip secrets. A key block cut off by the console tail is removed too."""
    cleaned, count = SECRET.subn("[redacted]", text)
    if re.search(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", cleaned):
        cleaned, extra = re.subn(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*\Z",
            "[redacted]",
            cleaned,
            count=1,
        )
        count += extra
    if re.search(r"-----END [A-Z ]*PRIVATE KEY-----", cleaned):
        cleaned, extra = re.subn(
            r"\A[\s\S]*-----END [A-Z ]*PRIVATE KEY-----",
            "[redacted]",
            cleaned,
            count=1,
        )
        count += extra
    token = os.environ.get("W3_LAB_PRIVATE_BUNDLE_TOKEN", "")
    if token and token in cleaned:
        cleaned = cleaned.replace(token, "[redacted]")
        count += 1
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


def private_ipv4(instance: Mapping[str, Any]) -> str:
    value = instance.get("PrivateIpAddress")
    if isinstance(value, str) and value:
        return value.strip()
    return ""


def phase_egress_env(private_ip: str) -> list[str]:
    """Env for the guest listener. A documentation address is not passed through."""
    guest_dir = Path(__file__).resolve().with_name("lab-guests")
    if str(guest_dir) not in sys.path:
        sys.path.insert(0, str(guest_dir))
    import phase2_grade as phase_grade

    chosen = phase_grade.choose_egress_target(private_ip.strip() or None, None, [])
    if chosen is None:
        return []
    return [f"VANTIO_EGRESS_HOST={chosen[0]}", f"VANTIO_EGRESS_PORT={chosen[1]}"]


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
        # Ubuntu 24.04 on the pinned AMI accepts the ubuntu user. The key
        # push can land before sshd will use it, so the first connection retries.
        proc = _run_with_fresh_key(runner, connect, public, ssh_runner, ssh_args, script)
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
        payload["cloudtrail"] = {"recorded": False, "reason": "admin_soak_release"}
        payload.update({"reason": "instance_absent", "status": "NOT_FOUND"})
        lab.write_json_with_hash(evidence_path("w3-lab-collect.json"), payload)
        raise lab.GuardAbort("instance_absent", payload)
    tags = lab._tag_list(instance.get("Tags"))
    if not lab.lab_tags_owned(tags):
        payload.update({"reason": "not_owned", "status": "NOT_OWNED"})
        lab.write_json_with_hash(evidence_path("w3-lab-collect.json"), payload)
        raise lab.GuardAbort("not_owned", payload)
    state = instance_state(instance)
    payload["instance_state"] = state
    payload["soak_active"] = lab.soak_active(tags)
    if payload["soak_active"] and state in {"terminated", "shutting-down", "stopped", "stopping"}:
        payload["cloudtrail"] = {"recorded": False, "reason": "admin_soak_release"}
    try:
        _collect_console(
            runner,
            payload,
            instance,
            instance_id,
            caps,
            ssh_runner=ssh_runner,
            keygen=keygen,
        )
    except lab.GuardAbort as exc:
        payload.update({"reason": exc.reason, "status": payload.get("status") or "FAILED"})
        lab.write_json_with_hash(evidence_path("w3-lab-collect.json"), payload)
        raise lab.GuardAbort(exc.reason, payload) from None
    lab.write_json_with_hash(evidence_path("w3-lab-collect.json"), payload)
    return payload


def _collect_console(
    runner: Runner,
    payload: dict[str, Any],
    instance: Mapping[str, Any],
    instance_id: str,
    caps: Mapping[str, Any],
    *,
    ssh_runner: SshRunner = default_ssh,
    keygen: Keygen = default_keygen,
) -> None:
    console = lab.aws_json(
        runner,
        ["aws", "ec2", "get-console-output", "--region", lab.REGION, "--instance-id", instance_id, "--latest"],
    )
    text, redacted = redact(console_text(console))
    if "PRIVATE KEY" in text:
        raise lab.GuardAbort("token_in_evidence")
    if text and not text.endswith("\n"):
        text += "\n"
    override = os.environ.get("W3_CONSOLE_PATH", "").strip()
    console_name = f"w3-lab-console-{instance_id}.txt"
    console_path = Path(override) if override else evidence_path("w3-lab-collect.json").with_name(console_name)
    console_path.write_text(text, encoding="utf-8")
    marker = next((line for line in text.splitlines() if MARKER_LINE.fullmatch(line)), None)
    checks = parse_check_lines(text, source="console")
    payload.update(
        {
            "checks": checks,
            "collect_channel": "console",
            "console_bytes": len(text.encode("utf-8")),
            "console_file": console_path.name,
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
            "printf '%s\\n' '---DETAILS---'\n"
            "cat /var/lib/vantio-lab/checks/*.json 2>/dev/null || true\n"
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
        check_part, _, detail_part = check_part.partition("---DETAILS---")
        marker_part = marker_part.strip()
        payload["check_details"] = parse_check_details(detail_part)
        if marker_part.startswith("{") and "PRIVATE" not in marker_part:
            payload["guest_marker_sha256"] = hashlib.sha256(marker_part.encode("utf-8")).hexdigest()
        pulled = parse_check_lines(check_part, source="guest-file")
        by_key = {(item["seq"], item["sha256"]): item for item in checks}
        for item in pulled:
            by_key[(item["seq"], item["sha256"])] = item
        payload["checks"] = sorted(by_key.values(), key=lambda item: int(item["seq"]))


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
                extra = exc.payload if isinstance(exc.payload, dict) else {}
                one = {
                    "checks": extra.get("checks") or [],
                    "cloudtrail": extra.get("cloudtrail"),
                    "console_bytes": extra.get("console_bytes"),
                    "console_file": extra.get("console_file"),
                    "console_redacted": extra.get("console_redacted") is True,
                    "console_sha256": extra.get("console_sha256"),
                    "instance_id": instance_id,
                    "instance_state": extra.get("instance_state"),
                    "reason": exc.reason,
                    "soak_active": extra.get("soak_active") is True,
                    "status": extra.get("status") or "FAILED",
                }
            rows.append(
                {
                    "check_count": len(one.get("checks") or []),
                    "checks": one.get("checks") or [],
                    "cloudtrail": one.get("cloudtrail"),
                    "console_bytes": one.get("console_bytes"),
                    "console_file": one.get("console_file"),
                    "console_redacted": one.get("console_redacted") is True,
                    "console_sha256": one.get("console_sha256"),
                    "instance_id": instance_id,
                    "instance_state": one.get("instance_state"),
                    "reason": one.get("reason"),
                    "soak_active": one.get("soak_active") is True,
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


FOUNDER_CLOSE_PATH = Path(__file__).resolve().with_name("founder-soak-close.json")
FOUNDER_CLOSE_REQUIRED = {
    "status": "CLOSED_BY_FOUNDER",
    "closed_by": "Zachary Balicki (Founder)",
    "instance_id": "i-0f38ffde5ad83c9f2",
    "decision_time": "2026-10-15T21:10:00-04:00",
    "decision_time_spoken": "2026-10-15 ~9:10 PM ET",
    "note": "26.9h was accepted",
    "evidence_ref": "SOAK-HASH-COMPARE.json",
}
# Name tag on the leftovers of that one instance. Teardown uses this constant
# when DescribeInstances no longer returns the instance. It is not a workflow input.
FOUNDER_CLOSE_LAB_NAME = "vantio-w3-lab-auto-38371704891"


def founder_close_record(path: Path | None = None) -> dict[str, Any] | None:
    chosen = FOUNDER_CLOSE_PATH if path is None else path
    try:
        payload = json.loads(chosen.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def termination_protected(reason: str) -> bool:
    """True when TerminateInstances was refused because the instance is locked.

    The sweeper role cannot clear disableApiTermination. A matching error
    records TERMINATION_LOCK and stops. It does not call ModifyInstanceAttribute.
    """
    text = reason or ""
    return "OperationNotPermitted" in text and (
        "disableApiTermination" in text or "may not be terminated" in text
    )


def founder_close_honored(instance_id: str, record: Mapping[str, Any] | None) -> bool:
    """True only for the Founder close of i-0f38ffde5ad83c9f2.

    Every other soak stays refused. A record that changes the closed-by line,
    the decision time, the 26.9h note, or the SOAK-HASH-COMPARE.json reference
    stays refused too.
    """
    if instance_id != FOUNDER_CLOSE_REQUIRED["instance_id"]:
        return False
    if not isinstance(record, Mapping):
        return False
    return all(record.get(key) == expected for key, expected in FOUNDER_CLOSE_REQUIRED.items())


def _teardown_absent_founder_leftovers(
    runner: Runner,
    now: datetime,
    payload: dict[str, Any],
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Delete Name-tagged leftovers after the Founder-closed instance is gone.

    sweeper_action still returns keep_soak for vantio-soak=active. This path
    does not call it. It runs only when founder_close_honored is true, and it
    deletes only resources whose Name is FOUNDER_CLOSE_LAB_NAME.
    """
    name = FOUNDER_CLOSE_LAB_NAME
    if not name.startswith(lab.NAME_PREFIX):
        raise lab.GuardAbort("founder_close_name")
    census = lab.census_from_aws(runner)
    called: list[str] = []
    for resource in related_owned(census, name):
        if resource.get("type") == "instance":
            continue
        called.extend(lab._delete_resource(resource, runner))
    previous_name = os.environ.get("LAB_NAME")
    os.environ["LAB_NAME"] = name
    try:
        check = execute_verify(runner, now, write=False)
    finally:
        if previous_name is None:
            os.environ.pop("LAB_NAME", None)
        else:
            os.environ["LAB_NAME"] = previous_name
    payload.update(
        {
            "called": called,
            "founder_close": {key: record[key] for key in FOUNDER_CLOSE_REQUIRED},
            "mutated": bool(called),
            "name": name,
            "slot_clear": check["slot_clear"],
            "status": check["status"],
        }
    )
    lab.write_json_with_hash(evidence_path("w3-lab-teardown.json"), payload)
    return payload


def execute_teardown(runner: Runner, now: datetime) -> dict[str, Any]:
    instance_id = require_instance_id(os.environ.get("INSTANCE_ID", "").strip())
    identity = lab.aws_json(runner, ["aws", "sts", "get-caller-identity"])
    lab.require_identity(identity)
    instance = describe_instance(runner, instance_id)
    payload = base_evidence("teardown")
    payload["instance_id"] = instance_id
    if instance is None:
        record = founder_close_record()
        if founder_close_honored(instance_id, record):
            assert record is not None
            return _teardown_absent_founder_leftovers(runner, now, payload, record)
        payload.update({"reason": "instance_absent", "status": "NOT_FOUND"})
        lab.write_json_with_hash(evidence_path("w3-lab-teardown.json"), payload)
        raise lab.GuardAbort("instance_absent")
    tags = lab._tag_list(instance.get("Tags"))
    if not lab.lab_tags_owned(tags):
        payload.update({"reason": "not_owned", "status": "NOT_OWNED"})
        lab.write_json_with_hash(evidence_path("w3-lab-teardown.json"), payload)
        raise lab.GuardAbort("not_owned")
    called: list[str] = []
    if lab.soak_active(tags):
        record = founder_close_record()
        if not founder_close_honored(instance_id, record):
            payload.update({"called": [], "mutated": False, "reason": "soak_active", "status": "REFUSED_SOAK"})
            lab.write_json_with_hash(evidence_path("w3-lab-teardown.json"), payload)
            raise lab.GuardAbort("soak_active")
        assert record is not None
        payload["founder_close"] = {key: record[key] for key in FOUNDER_CLOSE_REQUIRED}
    name = str(tags.get("Name"))
    state = instance_state(instance)
    if state in lab.OCCUPYING_STATES:
        try:
            called.extend(
                lab._delete_resource(
                    {"type": "instance", "id": instance_id, "region": lab.REGION, "tags": tags},
                    runner,
                )
            )
        except lab.GuardAbort as exc:
            if lab.soak_active(tags) and termination_protected(exc.reason):
                payload.update(
                    {
                        "called": ["terminate-instances"],
                        "mutated": False,
                        "reason": exc.reason,
                        "status": "TERMINATION_LOCK",
                    }
                )
                lab.write_json_with_hash(evidence_path("w3-lab-teardown.json"), payload)
                raise
            raise
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


def _ssh_retryable(proc: subprocess.CompletedProcess[str]) -> bool:
    """True when a new connection was rejected or the host was not ready.

    Instance Connect installs the pushed key for about 60 seconds. A later
    ssh or scp is a new connection. Permission denied (publickey) is that
    window, or the key not being visible yet. A guest script failure does
    not match these strings, so a real battery exit is not run again.
    """
    # OpenSSH ssh and scp return 255 when the connection itself fails.
    # A guest script that prints one of these phrases keeps its own exit code.
    if proc.returncode != 255:
        return False
    text = f"{proc.stderr or ''}\n{proc.stdout or ''}"
    return any(
        needle in text
        for needle in (
            "Permission denied (publickey)",
            "Connection refused",
            "Connection timed out",
            "Operation timed out",
            "Connection closed",
            "kex_exchange_identification",
            "No route to host",
        )
    )


def _run_with_fresh_key(
    runner: Runner,
    connect: list[str],
    public: str,
    ssh_runner: SshRunner,
    argv: list[str],
    script: str,
    *,
    attempts: int = 4,
) -> subprocess.CompletedProcess[str]:
    """Push the same ed25519 key, then connect. Each push resets the 60s window."""
    last: subprocess.CompletedProcess[str] | None = None
    for attempt in range(attempts):
        lab.aws_json(runner, connect + [public])
        last = ssh_runner(argv, script)
        if last.returncode == 0 or not _ssh_retryable(last):
            return last
        if attempt + 1 < attempts:
            time.sleep(2)
    assert last is not None
    return last


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


def _remote_boot_id(remote: Callable[[list[str], str], subprocess.CompletedProcess[str]]) -> str:
    proc = remote(["cat", "/proc/sys/kernel/random/boot_id"], "")
    if proc.returncode != 0:
        return ""
    text = (proc.stdout or "").strip()
    if not text or "\n" in text or len(text) > 80:
        return ""
    return text


def _boot_ids_in_rows(body: Mapping[str, Any]) -> set[str]:
    found: set[str] = set()

    def take(value: object) -> None:
        if isinstance(value, str) and value and "\n" not in value and len(value) <= 80:
            found.add(value)

    take(body.get("boot_id"))
    for key in ("pre", "post"):
        nested = body.get(key)
        if isinstance(nested, Mapping):
            take(nested.get("boot_id"))
    return found


def _rows_disagree_with_boot(body: Mapping[str, Any], live_boot: str) -> bool:
    """True when the file names a boot and the live boot is not among them."""
    if not live_boot:
        return False
    named = _boot_ids_in_rows(body)
    if not named:
        return False
    return live_boot not in named


def _guest_failure_reason(body: Mapping[str, Any] | None) -> str:
    """Name the uninstall line the guest recorded. A missing tail stays guest."""
    if not isinstance(body, Mapping):
        return "guest"
    if body.get("reason") in {"reboot_script_missing", "reboot_not_scheduled"}:
        return str(body["reason"])
    removal = body.get("removal")
    if isinstance(removal, Mapping) and removal.get("verified_removed") is False:
        return "programs_not_removed"
    tail = body.get("uninstall_tail")
    if isinstance(tail, str):
        if "bpftool missing" in tail:
            return "uninstall_bpftool"
        if "UNINSTALL_RESIDUAL" in tail:
            return "uninstall_residual"
        if "UNINSTALL_NOT_VERIFIED" in tail or "uninstall refused" in tail:
            return "uninstall_not_verified"
    return "guest"


def _baseline_diag():
    """Guest helpers. Imported here so arm tests do not load them at import."""
    root = Path(__file__).resolve().parent / "lab-guests"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    import baseline_diag

    return baseline_diag


def _remote_line(remote: Callable[[list[str], str], subprocess.CompletedProcess[str]], path: str, limit: int) -> str:
    """One live file after the new boot. A second line or a long read is empty."""
    proc = remote(["cat", path], "")
    if proc.returncode != 0:
        return ""
    text = (proc.stdout or "").replace("\r", "").strip()
    if not text or "\n" in text or len(text) > limit:
        return ""
    return text


def _post_boot_evidence(
    remote: Callable[[list[str], str], subprocess.CompletedProcess[str]],
    *,
    image_name: str,
    image_id: str,
) -> dict[str, str]:
    """Cmdline, LSM list, lockdown, and image name read after the boot id changed."""
    diag = _baseline_diag()
    lsm = _remote_line(remote, "/sys/kernel/security/lsm", 200)
    if lsm and re.fullmatch(r"[A-Za-z0-9_,.-]+", lsm) is None:
        lsm = ""
    named = diag.exact_image_name(image_name)
    accepted_id = image_id if lab.IMAGE_ID_RE.fullmatch(image_id) else ""
    return {
        "cmdline": _remote_line(remote, "/proc/cmdline", 400),
        "lsm": lsm,
        "lockdown": diag.accept_lockdown(_remote_line(remote, "/sys/kernel/security/lockdown", 80)),
        "image_name": named,
        "image_id": accepted_id,
    }


def _store_serial_log(runner: Runner, instance_id: str, payload: dict[str, Any]) -> None:
    """Write the EC2 serial log next to the arm JSON. An empty log is a failure."""
    console = lab.aws_json(
        runner,
        ["aws", "ec2", "get-console-output", "--region", lab.REGION, "--instance-id", instance_id, "--latest"],
    )
    text, redacted = redact(console_text(console))
    if "PRIVATE KEY" in text:
        raise lab.GuardAbort("token_in_evidence")
    if not text.strip():
        raise lab.GuardAbort("console_missing")
    if not text.endswith("\n"):
        text += "\n"
    console_path = evidence_path("w3-lab-arm.json").with_name(f"w3-lab-console-{instance_id}.txt")
    console_path.write_text(text, encoding="utf-8")
    payload["console_file"] = console_path.name
    payload["console_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    payload["console_bytes"] = len(text.encode("utf-8"))
    payload["console_redacted"] = redacted


LAB_ROWS_REMOTE = "/var/lib/vantio-lab/enterprise-pe-rows.json"
REDTEAM_ROWS_REMOTE = "/var/lib/vantio-lab/redteam-rows.json"


def _read_lab_rows(text: str) -> dict[str, Any]:
    """The durable guest record. A log line is not that record."""
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError as exc:
        raise lab.GuardAbort("rows_malformed") from exc
    if not isinstance(loaded, dict):
        raise lab.GuardAbort("rows_malformed")
    return loaded


def _pull_lab_rows(
    runner: Runner,
    connect: list[str],
    public: str,
    ssh_runner: SshRunner,
    base: list[str],
    ssh_user: str,
    host: str,
    rows_local: Path,
) -> tuple[str, dict[str, Any]]:
    """Copy the durable rows. /tmp is not a substitute."""
    # Instance Connect keys last 60 seconds. The guest script can run longer.
    # A new scp is a new connection, so send the key again before the pull.
    if rows_local.exists():
        rows_local.unlink()
    pulled = _run_with_fresh_key(
        runner,
        connect,
        public,
        ssh_runner,
        ["scp", *base[:-1], f"{ssh_user}@{host}:{LAB_ROWS_REMOTE}", str(rows_local)],
        "",
    )
    if pulled.returncode != 0 or not rows_local.is_file() or rows_local.stat().st_size == 0:
        raise lab.GuardAbort("rows_missing")
    text = rows_local.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        raise lab.GuardAbort("rows_missing")
    return text, _read_lab_rows(text)


def _reboot_log_tail(remote: Callable[[list[str], str], subprocess.CompletedProcess[str]]) -> str:
    """Last lines of the grub reboot script, redacted. Empty when SSH cannot read it."""
    proc = remote(["tail", "-n", "40", "/var/lib/vantio-lab/grub-mkconfig.txt"], "")
    if proc.returncode != 0:
        return ""
    text, _redacted = redact(proc.stdout or "")
    return text[-800:]


def _wait_for_reboot(
    runner: Runner,
    instance_id: str,
    remote: Callable[[list[str], str], subprocess.CompletedProcess[str]],
    connect_with_key: list[str],
    *,
    quiet_budget: float = 70,
    return_budget: float = 240,
    clock: Callable[[], float] = time.time,
    pause: Callable[[float], None] = time.sleep,
    describe: Callable[[Runner, str], Mapping[str, Any] | None] | None = None,
    release: Callable[[], None] | None = None,
    reopen: Callable[[], None] | None = None,
    note: dict[str, str] | None = None,
) -> str:
    """Leave the host, then read the boot id on a new connection.

    The lab reboot is the system timer the LSM guard uses, 45s out. That
    timer changed the boot when the runner had already dropped its session.
    Polling SSH through those 45s is a different path, and it is the path
    that stayed on the old boot. release() drops the runner rule. No SSH
    runs until quiet_budget has elapsed. The returned value is the new boot id.
    """
    lookup = describe_instance if describe is None else describe
    before = _remote_boot_id(remote)
    if note is not None:
        note["before"] = before
    if release is not None:
        release()
    quiet_deadline = clock() + quiet_budget
    while clock() < quiet_deadline:
        instance = lookup(runner, instance_id)
        if instance is not None and instance_state(instance) in {"stopped", "stopping", "shutting-down", "terminated"}:
            raise lab.GuardAbort("instance_state")
        pause(5)
    return_deadline = clock() + return_budget
    opened = reopen is None
    while clock() < return_deadline:
        instance = lookup(runner, instance_id)
        if instance is not None and instance_state(instance) == "running":
            if not opened:
                if reopen is not None:
                    reopen()
                opened = True
            try:
                lab.aws_json(runner, connect_with_key)
            except lab.GuardAbort:
                pause(5)
                continue
            if remote(["true"], "").returncode == 0:
                current = _remote_boot_id(remote)
                if current and (not before or current != before):
                    if note is not None:
                        note["after"] = current
                    return current
        pause(5)
    raise lab.GuardAbort("reboot_timeout")


def _self_service_shell(root: str, rows_path: str) -> str:
    """One remote command. It does not pass --artifact-trust or --fixture-host."""
    if not re.fullmatch(r"/[A-Za-z0-9_./-]{1,160}", root):
        raise lab.GuardAbort("self_service_layout")
    if rows_path != LAB_ROWS_REMOTE and not re.fullmatch(r"/tmp/[A-Za-z0-9_./-]{1,80}", rows_path):
        raise lab.GuardAbort("self_service_layout")
    script = (
        "set -euo pipefail; "
        f"tar -xf {root}/self-service.tar -C {root}; "
        f"if [ -f {root}/debs.tar ]; then mkdir -p {root}/debs; tar -xf {root}/debs.tar -C {root}/debs; fi; "
        "sudo env "
        f"PYTHONPATH={root} "
        "VANTIO_LAB_SCOPE=lab-nonprod "
        f"VANTIO_LAB_ARTIFACT_TRUST={root}/lab-artifact-trust.json "
        f"VANTIO_LAB_DEV_TRUST={root}/lab-dev-trust.json "
        f"VANTIO_LAB_ROOT={root} "
        f"VANTIO_INSTALL_BUNDLE={root}/bundle "
        f"VANTIO_POLICY_FILE={root}/policy.json "
        f"VANTIO_SIGNATURE_FILE={root}/signature.json "
        "VANTIO_STATE_DIR=/var/lib/vantio/install "
        f"VANTIO_SELF_SERVICE_OUT={rows_path} "
        f"python3 {root}/self_service.py"
    )
    if "--artifact-trust" in script or "--fixture-host" in script:
        raise lab.GuardAbort("self_service_layout")
    return script


def _scan_self_service(directory: Path) -> None:
    """Refuse a staged tree that carries a private key or the enterprise contract."""
    if not directory.is_dir():
        raise lab.GuardAbort("self_service_layout")
    for name in (
        "self_service.py",
        "self-service.tar",
        "lab-artifact-trust.json",
        "lab-dev-trust.json",
        "policy.json",
        "signature.json",
    ):
        if not (directory / name).is_file():
            raise lab.GuardAbort("self_service_layout")
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(directory).as_posix()
        if ".." in rel.split("/") or path.name in {"contract.tar", "private-key.pem"} or path.suffix == ".pem":
            raise lab.GuardAbort("self_service_layout")
        try:
            blob = path.read_bytes()
        except OSError:
            raise lab.GuardAbort("self_service_layout") from None
        if re.search(br"-----BEGIN [A-Z ]*PRIVATE KEY-----", blob):
            raise lab.GuardAbort("token_in_evidence")


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

        if pin != enterprise_bundle.PUBLIC_INSTALLER_PIN:
            raise lab.GuardAbort("bundle_wrong_seal")
        battery = os.environ.get("W3_BATTERY", "enterprise").strip() or "enterprise"
        phase_batteries = {
            "r15-container-exit",
            "2c-upgrade-rollback",
            "2d-crash-recovery",
            "2e-performance",
            "2f-tamper",
            "2g-distro",
            "lsm-guard",
            "soak-hourly",
        }
        if battery not in {"enterprise", "descendant-b1", "reboot-check", "self-service", *phase_batteries}:
            raise lab.GuardAbort("battery")
        payload["battery"] = battery
        if battery == "self-service" and os.environ.get("W3_BRAIN_DIR", "").strip():
            raise lab.GuardAbort("battery")
        cidr = require_global_32(os.environ.get("W3_RUNNER_CIDR", "").strip())
        bundle_dir = Path(os.environ.get("W3_BUNDLE_DIR", ""))
        staged = Path(os.environ.get("W3_SELF_SERVICE_DIR", ""))
        if battery == "self-service":
            if seal != enterprise_bundle.POLICY_ALLOW_SEAL:
                raise lab.GuardAbort("bundle_wrong_seal")
            _scan_self_service(staged)
        else:
            if not bundle_dir.is_dir():
                raise lab.GuardAbort("bundle_layout")
            if checker is None:
                inspected = dict(enterprise_bundle.inspect_bundle(bundle_dir, expected_seal=seal))
            else:
                inspected = dict(checker(bundle_dir))
            if inspected.get("seal_sha256") != seal:
                raise lab.GuardAbort("bundle_wrong_seal")
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
        image_id = str(instance.get("ImageId") or "")
        if image_id and lab.IMAGE_ID_RE.fullmatch(image_id) is None:
            raise lab.GuardAbort("image_id")
        image_name = ""
        image_owner = ""
        if image_id:
            _accepted, facts = lab.described_image(runner, image_id)
            image_name = lab.exact_image_name(facts.get("image_name"))
            image_owner = str(facts.get("image_owner") or "")
        ssh_user = lab.ssh_user_for_image(image_name, image_owner, image_id)
        payload["image_id"] = image_id
        payload["image_name"] = image_name
        payload["ssh_user"] = ssh_user
        image_env = ["env", f"VANTIO_IMAGE_ID={image_id}", f"VANTIO_IMAGE_NAME={image_name}"]
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
            ssh_user,
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
            base = _ssh_base(private, known, host)

            def remote(argv: list[str], script: str) -> subprocess.CompletedProcess[str]:
                # Each ssh is a new connection. Push again so a copy that
                # took the previous 60 seconds does not expire the key.
                return _run_with_fresh_key(
                    runner,
                    connect,
                    public,
                    ssh_runner,
                    ["ssh", *base, *argv],
                    script,
                )

            def release_ssh() -> None:
                revoke_quietly(runner, group_id, cidr)
                stamp["authorized"] = False
                write_stamp(stamp_path, stamp)

            def reopen_ssh() -> None:
                lab.aws_json(runner, authorize)
                stamp["authorized"] = True
                write_stamp(stamp_path, stamp)

            reboot_note: dict[str, str] = {}

            def copy_to(local: Path, name: str) -> None:
                if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
                    raise lab.GuardAbort("bundle_layout")
                proc = _run_with_fresh_key(
                    runner,
                    connect,
                    public,
                    ssh_runner,
                    ["scp", *base[:-1], str(local), f"{ssh_user}@{host}:{GUEST_BUNDLE}/{name}"],
                    "",
                )
                if proc.returncode != 0:
                    _ssh_failure(proc)

            made = remote(["sudo", "mkdir", "-p", GUEST_BUNDLE], "")
            if made.returncode != 0:
                _ssh_failure(made)
            owned = remote(["sudo", "chown", "-R", f"{ssh_user}:{ssh_user}", "/var/lib/vantio-lab"], "")
            if owned.returncode != 0:
                _ssh_failure(owned)
            if battery != "self-service":
                copy_to(bundle_dir / "seal.oci.tar", "seal.oci.tar")
                copy_to(bundle_dir / "contract.tar", "contract.tar")
            debs_env = os.environ.get("W3_OFFLINE_DEBS", "").strip()
            if debs_env:
                debs_dir = Path(debs_env)
                deb_files = sorted(path for path in debs_dir.glob("*.deb") if path.is_file())
                if not deb_files:
                    raise lab.GuardAbort("offline_debs")
                made_debs = remote(["mkdir", "-p", f"{GUEST_BUNDLE}/debs"], "")
                if made_debs.returncode != 0:
                    _ssh_failure(made_debs)
                copied = _run_with_fresh_key(
                    runner,
                    connect,
                    public,
                    ssh_runner,
                    ["scp", *base[:-1], *[str(path) for path in deb_files], f"{ssh_user}@{host}:{GUEST_BUNDLE}/debs/"],
                    "",
                )
                if copied.returncode != 0:
                    _ssh_failure(copied)
            brain_env = os.environ.get("W3_BRAIN_DIR", "").strip()
            if brain_env:
                if str(instance.get("InstanceType") or "") != lab.BRAIN_INSTANCE_TYPE:
                    raise lab.GuardAbort("brain_instance_type")
                brain_dir = Path(brain_env)
                model = brain_dir / "qwen2.5-3b-instruct-q4_k_m.gguf"
                runtime = brain_dir / "llama-b11540"
                server = runtime / "llama-server"
                library = runtime / "libllama-server-impl.so"
                if not model.is_file() or not server.is_file() or not library.is_file():
                    raise lab.GuardAbort("brain_files")
                guest_brain = lab.BRAIN_GUEST_DIR
                made_brain = remote(["sudo", "mkdir", "-p", f"{guest_brain}/llama-b11540"], "")
                if made_brain.returncode != 0:
                    _ssh_failure(made_brain)
                owned_brain = remote(["sudo", "chown", "-R", f"{ssh_user}:{ssh_user}", "/var/lib/vantio-lab"], "")
                if owned_brain.returncode != 0:
                    _ssh_failure(owned_brain)
                copied_model = _run_with_fresh_key(
                    runner,
                    connect,
                    public,
                    ssh_runner,
                    ["scp", *base[:-1], str(model), f"{ssh_user}@{host}:{guest_brain}/qwen2.5-3b-instruct-q4_k_m.gguf"],
                    "",
                )
                if copied_model.returncode != 0:
                    _ssh_failure(copied_model)
                copied_runtime = _run_with_fresh_key(
                    runner,
                    connect,
                    public,
                    ssh_runner,
                    ["scp", "-r", *base[:-1], f"{runtime}/.", f"{ssh_user}@{host}:{guest_brain}/llama-b11540/"],
                    "",
                )
                if copied_runtime.returncode != 0:
                    _ssh_failure(copied_runtime)
                marked = remote(["chmod", "-R", "a+rX", guest_brain], "")
                if marked.returncode != 0:
                    _ssh_failure(marked)
                executable = remote(["chmod", "a+rx", f"{guest_brain}/llama-b11540/llama-server"], "")
                if executable.returncode != 0:
                    _ssh_failure(executable)
                for required in (
                    f"{guest_brain}/qwen2.5-3b-instruct-q4_k_m.gguf",
                    f"{guest_brain}/llama-b11540/llama-server",
                    f"{guest_brain}/llama-b11540/libllama-server-impl.so",
                ):
                    landed = remote(["test", "-s", required], "")
                    if landed.returncode != 0:
                        raise lab.GuardAbort("brain_not_landed")
                sized = remote(["stat", "-c", "%s", f"{guest_brain}/qwen2.5-3b-instruct-q4_k_m.gguf"], "")
                if sized.returncode != 0 or (sized.stdout or "").strip() != "2104932768":
                    raise lab.GuardAbort("brain_not_landed")
            if battery == "self-service":
                deb_env = os.environ.get("W3_OFFLINE_DEBS", "").strip()
                if deb_env:
                    ca_bundle = Path(deb_env) / "ca-certificates.crt"
                    if ca_bundle.is_file():
                        copy_to(ca_bundle, "ca-certificates.crt")
                copy_to(staged / "self-service.tar", "self-service.tar")
                ran = remote(["bash", "-c", _self_service_shell(GUEST_BUNDLE, LAB_ROWS_REMOTE)], "")
            elif battery in phase_batteries:
                script_path = Path(os.environ.get("W3_ENTERPRISE_SCRIPT", str(DEFAULT_ENTERPRISE_GUEST)))
                copy_to(script_path, "enterprise-rows.sh")
                guest_dir = Path(__file__).resolve().with_name("lab-guests")
                copy_to(guest_dir / "phase2_host.py", "phase2_host.py")
                copy_to(guest_dir / "phase2_grade.py", "phase2_grade.py")
                copy_to(guest_dir / "baseline_diag.py", "baseline_diag.py")
                copy_to(guest_dir / "sticky_write.py", "sticky_write.py")
                if battery == "soak-hourly":
                    copy_to(guest_dir / "soak_check.py", "soak_check.py")
                    copy_to(guest_dir / "soak-hourly.sh", "soak-hourly.sh")
                    copy_to(guest_dir / "record-check.sh", "record-check.sh")
                ran = remote(
                    [
                        "env",
                        f"VANTIO_IMAGE_ID={image_id}",
                        f"VANTIO_IMAGE_NAME={image_name}",
                        *phase_egress_env(private_ipv4(instance)),
                        "bash",
                        f"{GUEST_BUNDLE}/enterprise-rows.sh",
                        seal,
                        battery,
                    ],
                    "",
                )
            elif battery == "descendant-b1":
                script_path = Path(os.environ.get("W3_ENTERPRISE_SCRIPT", str(DEFAULT_ENTERPRISE_GUEST)))
                copy_to(script_path, "enterprise-rows.sh")
                copy_to(script_path.with_name("baseline_diag.py"), "baseline_diag.py")
                copy_to(script_path.with_name("sticky_write.py"), "sticky_write.py")
                descendant = Path(os.environ.get("W3_DESCENDANT_SCRIPT", str(DEFAULT_DESCENDANT_GUEST)))
                copy_to(descendant, "descendant_b1.py")
                probe_c = descendant.with_name("descendant_probe.c")
                copy_to(probe_c, "descendant_probe.c")
                probe_bin = descendant.with_name("descendant_probe")
                if probe_bin.is_file():
                    copy_to(probe_bin, "descendant_probe")
                rows_py = Path(os.environ.get("W3_REDTEAM_ROWS", str(DEFAULT_REDTEAM_ROWS)))
                packet_py = Path(os.environ.get("W3_REDTEAM_PACKET", str(DEFAULT_REDTEAM_PACKET)))
                if rows_py.is_file() and packet_py.is_file():
                    copy_to(rows_py, "redteam_rows.py")
                    copy_to(packet_py, "redteam_packet.py")
                pre = remote([*image_env, "bash", f"{GUEST_BUNDLE}/enterprise-rows.sh", seal, "descendant-b1", "pre"], "")
                ran = pre
                if pre.returncode == 0:
                    try:
                        payload["boot_id"] = _wait_for_reboot(
                            runner,
                            instance_id,
                            remote,
                            connect + [public],
                            release=release_ssh,
                            reopen=reopen_ssh,
                            note=reboot_note,
                        )
                    except lab.GuardAbort as exc:
                        if exc.reason != "reboot_timeout":
                            raise
                        tail = _reboot_log_tail(remote)
                        if tail:
                            payload["reboot_log_tail"] = tail
                        payload["guest_rc"] = pre.returncode
                        payload["mutated"] = True
                        rows_local = Path(os.environ.get("W3_ROWS_PATH", "w3-lab-enterprise-rows.json"))
                        try:
                            pre_text, _pre_body = _pull_lab_rows(
                                runner,
                                connect,
                                public,
                                ssh_runner,
                                base,
                                ssh_user,
                                host,
                                rows_local,
                            )
                        except lab.GuardAbort as rows_exc:
                            if rows_exc.reason not in {"rows_missing", "rows_malformed"}:
                                raise
                            payload["rows_reason"] = rows_exc.reason
                        else:
                            _store_guest_rows(rows_local, pre_text)
                            payload["rows_sha256"] = hashlib.sha256(rows_local.read_bytes()).hexdigest()
                        raise exc
                    ran = remote([*image_env, "bash", f"{GUEST_BUNDLE}/enterprise-rows.sh", seal, "descendant-b1", "post"], "")
            elif battery == "reboot-check":
                script_path = Path(os.environ.get("W3_ENTERPRISE_SCRIPT", str(DEFAULT_ENTERPRISE_GUEST)))
                copy_to(script_path, "enterprise-rows.sh")
                copy_to(script_path.with_name("baseline_diag.py"), "baseline_diag.py")
                copy_to(script_path.with_name("sticky_write.py"), "sticky_write.py")
                pre = remote([*image_env, "bash", f"{GUEST_BUNDLE}/enterprise-rows.sh", seal, "reboot-check"], "")
                ran = pre
                if pre.returncode == 0:
                    try:
                        payload["boot_id"] = _wait_for_reboot(
                            runner,
                            instance_id,
                            remote,
                            connect + [public],
                            release=release_ssh,
                            reopen=reopen_ssh,
                            note=reboot_note,
                        )
                    except lab.GuardAbort as exc:
                        if exc.reason != "reboot_timeout":
                            raise
                        tail = _reboot_log_tail(remote)
                        if tail:
                            payload["reboot_log_tail"] = tail
                        payload["guest_rc"] = pre.returncode
                        payload["mutated"] = True
                        raise
                if reboot_note.get("before"):
                    payload["scheduled_boot_id"] = reboot_note["before"]
            else:
                script_path = Path(os.environ.get("W3_ENTERPRISE_SCRIPT", str(DEFAULT_ENTERPRISE_GUEST)))
                copy_to(script_path, "enterprise-rows.sh")
                copy_to(script_path.with_name("sticky_write.py"), "sticky_write.py")
                copy_to(script_path.with_name("baseline_diag.py"), "baseline_diag.py")
                copy_to(script_path.with_name("product_uninstall_census.py"), "product_uninstall_census.py")
                ran = remote([*image_env, "bash", f"{GUEST_BUNDLE}/enterprise-rows.sh", seal], "")
            rows_local = Path(os.environ.get("W3_ROWS_PATH", "w3-lab-enterprise-rows.json"))
            try:
                guest_text, parsed = _pull_lab_rows(
                    runner,
                    connect,
                    public,
                    ssh_runner,
                    base,
                    ssh_user,
                    host,
                    rows_local,
                )
            except lab.GuardAbort as exc:
                if exc.reason not in {"rows_missing", "rows_malformed"}:
                    raise
                payload.update(
                    {
                        "reason": exc.reason,
                        "status": "FAILED",
                        "guest_rc": ran.returncode,
                        "mutated": True,
                    }
                )
                raise
            _store_guest_rows(rows_local, guest_text)
            payload["rows_sha256"] = hashlib.sha256(rows_local.read_bytes()).hexdigest()
            redteam_local = Path(os.environ.get("W3_REDTEAM_PATH", "w3-lab-redteam-rows.json"))
            pulled_redteam = _run_with_fresh_key(
                runner,
                connect,
                public,
                ssh_runner,
                ["scp", *base[:-1], f"{ssh_user}@{host}:{REDTEAM_ROWS_REMOTE}", str(redteam_local)],
                "",
            )
            if battery == "descendant-b1":
                redteam_text = ""
                if pulled_redteam.returncode == 0 and redteam_local.is_file():
                    redteam_text = redteam_local.read_text(encoding="utf-8", errors="replace")
                try:
                    redteam_body = json.loads(redteam_text) if redteam_text else None
                except json.JSONDecodeError:
                    redteam_body = None
                if not isinstance(redteam_body, dict) or not isinstance(redteam_body.get("attempts"), list):
                    payload.update(
                        {
                            "reason": "redteam_rows_missing" if not redteam_text else "redteam_rows_malformed",
                            "status": "FAILED",
                            "guest_rc": ran.returncode,
                            "mutated": True,
                        }
                    )
                    raise lab.GuardAbort(payload["reason"])
                _store_guest_rows(redteam_local, redteam_text)
                payload["redteam_rows_sha256"] = hashlib.sha256(redteam_local.read_bytes()).hexdigest()
            elif pulled_redteam.returncode == 0 and redteam_local.is_file():
                _store_guest_rows(redteam_local, redteam_local.read_text(encoding="utf-8", errors="replace"))
                payload["redteam_rows_sha256"] = hashlib.sha256(redteam_local.read_bytes()).hexdigest()
            live_boot = _remote_boot_id(remote)
            if live_boot:
                payload["boot_id"] = live_boot
            # reboot-check writes the boot id before the timer fires. A later
            # live boot is the result of that schedule, not a stale file.
            if battery != "reboot-check" and parsed is not None and _rows_disagree_with_boot(parsed, live_boot):
                payload.update({"reason": "stale_rows", "status": "FAILED", "guest_rc": ran.returncode, "mutated": True})
                raise lab.GuardAbort("stale_rows")
            payload["guest_rc"] = ran.returncode
            payload["mutated"] = True
            if ran.returncode != 0:
                reason = _guest_failure_reason(parsed)
                payload.update({"reason": reason, "status": "FAILED"})
                raise lab.GuardAbort(reason)
            if battery == "self-service":
                payload["status"] = "SELF_SERVICE"
            elif battery == "descendant-b1":
                post_body = parsed.get("post") if isinstance(parsed, dict) and isinstance(parsed.get("post"), dict) else {}
                pre_body = parsed.get("pre") if isinstance(parsed, dict) and isinstance(parsed.get("pre"), dict) else {}
                observed = isinstance(parsed, dict) and parsed.get("reboot_observed") is True
                post_boot = post_body.get("boot_id")
                pre_boot = pre_body.get("boot_id")
                if (
                    not observed
                    or not isinstance(post_boot, str)
                    or not isinstance(pre_boot, str)
                    or post_boot == pre_boot
                    or (live_boot and post_boot != live_boot)
                ):
                    payload.update({"reason": "reboot_not_observed", "status": "FAILED"})
                    raise lab.GuardAbort("reboot_not_observed")
                payload["status"] = "DESCENDANT_B1"
            elif battery == "reboot-check":
                scheduled = parsed.get("boot_id") if isinstance(parsed, dict) else None
                armed = isinstance(parsed, dict) and parsed.get("reboot_requested") is True
                before = str(payload.get("scheduled_boot_id") or "")
                if (
                    not armed
                    or not isinstance(scheduled, str)
                    or not scheduled
                    or scheduled != before
                    or not live_boot
                    or live_boot == scheduled
                ):
                    payload.update({"reason": "reboot_not_observed", "status": "FAILED"})
                    raise lab.GuardAbort("reboot_not_observed")
                post = _post_boot_evidence(
                    remote,
                    image_name=str(payload.get("image_name") or ""),
                    image_id=str(payload.get("image_id") or ""),
                )
                post["boot_id"] = live_boot
                payload["post_boot"] = post
                missing = [key for key in ("cmdline", "lsm", "lockdown", "image_name") if not post.get(key)]
                if isinstance(parsed, dict):
                    parsed["post"] = post
                    rows_local.write_text(json.dumps(parsed) + "\n", encoding="utf-8")
                    payload["rows_sha256"] = hashlib.sha256(rows_local.read_bytes()).hexdigest()
                if missing:
                    payload.update({"reason": "post_boot_incomplete", "status": "FAILED", "post_boot_missing": missing})
                    raise lab.GuardAbort("post_boot_incomplete")
                try:
                    _store_serial_log(runner, instance_id, payload)
                except lab.GuardAbort as exc:
                    payload.update({"reason": exc.reason, "status": "FAILED"})
                    raise
                payload["status"] = "REBOOT_CHECKED"
            elif battery == "enterprise":
                payload["status"] = "ENTERPRISE_ROWS"
            elif battery == "soak-hourly":
                payload["status"] = "SOAK_HOURLY"
            else:
                payload["status"] = "PHASE2"
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
            "usage: w3_lab_steps.py preflight-arm|preflight-long-soak|arm|arm-enterprise|arm-self-service|prepare-bundle|close-ssh|collect|collect-due|teardown|verify-removed",
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
            if (os.environ.get("W3_BATTERY", "enterprise").strip() or "enterprise") == "self-service":
                raise lab.GuardAbort("battery")
            execute_enterprise_rows(lab.default_runner, keygen=default_keygen, ssh_runner=default_ssh)
            return 0
        if command == "arm-self-service":
            os.environ["W3_BATTERY"] = "self-service"
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
