#!/usr/bin/env python3
"""Dispatch, watch, and download Free-lab workflows from phantom-box.

This process uses gh. It does not call the AWS CLI, and it removes AWS
credential variables from the environment it passes to gh. Launch stays a
plan until both --execute and --confirm-slot-clear are present. The workflow
itself still refuses to start a second instance.

Audience: INTERNAL_RESTRICTED
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Mapping, Sequence

REPO = "vantioai/vantio-open-core"
REF = "main"
AWS_ENV = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_PROFILE",
    "AWS_DEFAULT_PROFILE",
    "AWS_CONFIG_FILE",
    "AWS_SHARED_CREDENTIALS_FILE",
    "AWS_LOGIN_CACHE_DIRECTORY",
)
INSTANCE_ID = re.compile(r"^i-[0-9a-f]{8,17}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
STEPS: dict[str, dict[str, object]] = {
    "credit": {
        "workflow": "w3-lab-auto-cost-gate.yml",
        "launches": False,
        "inputs": (),
    },
    "launch": {
        "workflow": "w3-lab-auto-provision.yml",
        "launches": True,
        "inputs": (
            "instance_type",
            "stop_after_minutes",
            "associate_public_ipv4",
            "purpose",
            "expires_in_minutes",
            "image_id",
            "describe_only",
        ),
    },
    "arm": {
        "workflow": "w3-lab-auto-arm.yml",
        "launches": False,
        "inputs": ("instance_id", "seal", "public_pin", "enterprise_rows", "bundle_tag", "battery"),
    },
    "collect": {
        "workflow": "w3-lab-auto-collect.yml",
        "launches": False,
        "inputs": ("instance_id",),
    },
    "teardown": {
        "workflow": "w3-lab-auto-teardown.yml",
        "launches": False,
        "inputs": ("instance_id",),
    },
    "sweep": {
        "workflow": "w3-lab-auto-sweeper.yml",
        "launches": False,
        "inputs": (),
    },
    "verify-removed": {
        "workflow": "w3-lab-auto-verify-removed.yml",
        "launches": False,
        "inputs": ("instance_id", "lab_name"),
    },
    "long-soak": {
        "workflow": "w3-lab-auto-long-soak.yml",
        "launches": True,
        "inputs": ("soak_hours", "instance_type", "associate_public_ipv4", "execute", "image_id"),
    },
}


class TriggerError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def clean_env(source: Mapping[str, str]) -> tuple[dict[str, str], bool]:
    cleaned = dict(source)
    found = False
    for name in AWS_ENV:
        if name in cleaned:
            cleaned.pop(name, None)
            found = True
    return cleaned, found


def parse_fields(items: Sequence[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for item in items:
        if "=" not in item or "\n" in item or "\r" in item:
            raise TriggerError("field")
        key, value = item.split("=", 1)
        if not key or key in fields:
            raise TriggerError("field")
        fields[key] = value
    return fields


def validate_fields(step: str, fields: Mapping[str, str]) -> None:
    allowed = STEPS[step]["inputs"]
    if not isinstance(allowed, tuple):
        raise TriggerError("step")
    for key, value in fields.items():
        if key not in allowed:
            raise TriggerError("field")
        if key == "instance_id" and INSTANCE_ID.fullmatch(value) is None:
            raise TriggerError("instance_id")
        if key in ("seal", "public_pin") and HEX64.fullmatch(value) is None:
            raise TriggerError(key)
        if key == "execute" and value not in ("true", "false"):
            raise TriggerError("execute")
        if key == "enterprise_rows" and value not in ("true", "false"):
            raise TriggerError("enterprise_rows")
        if key == "bundle_tag" and re.fullmatch(r"lab-bundle/[A-Za-z0-9._-]{1,64}", value) is None:
            raise TriggerError("bundle_tag")
        if key == "battery" and value not in ("enterprise", "descendant-b1"):
            raise TriggerError("battery")
        if key == "instance_type" and value not in ("t3.micro", "t3.small"):
            raise TriggerError("instance_type")
        if key == "associate_public_ipv4" and value not in ("true", "false"):
            raise TriggerError("associate_public_ipv4")
        if key == "describe_only" and value not in ("true", "false"):
            raise TriggerError("describe_only")
        if key == "image_id" and re.fullmatch(r"ami-[0-9a-f]{8,17}", value) is None:
            raise TriggerError("image_id")


def dispatch_argv(step: str, fields: Mapping[str, str]) -> list[str]:
    if step not in STEPS:
        raise TriggerError("step")
    validate_fields(step, fields)
    workflow = STEPS[step]["workflow"]
    if not isinstance(workflow, str):
        raise TriggerError("step")
    argv = ["gh", "workflow", "run", workflow, "--repo", REPO, "--ref", REF]
    for key in sorted(fields):
        argv.extend(["-f", f"{key}={fields[key]}"])
    return argv


def needs_slot_ack(step: str, fields: Mapping[str, str]) -> bool:
    if step == "launch" and fields.get("describe_only") != "true":
        return True
    if step == "long-soak" and fields.get("execute") == "true":
        return True
    return False


def plan_payload(step: str, fields: Mapping[str, str], source_env: Mapping[str, str]) -> dict[str, object]:
    _env, stripped = clean_env(source_env)
    return {
        "argv": dispatch_argv(step, fields),
        "aws_env_stripped": stripped,
        "executed": False,
        "launches_ec2": bool(STEPS[step]["launches"]) and not (step == "launch" and fields.get("describe_only") == "true"),
        "ref": REF,
        "repo": REPO,
        "step": step,
    }


def run_gh(argv: Sequence[str], env: Mapping[str, str]) -> subprocess.CompletedProcess[str]:
    if not argv or argv[0] != "gh":
        raise TriggerError("argv")
    return subprocess.run(list(argv), env=dict(env), text=True, check=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Trigger Free-lab workflows with gh. No AWS credentials.")
    parser.add_argument("command", choices=("plan", "dispatch", "watch", "download"))
    parser.add_argument("step", nargs="?", choices=tuple(STEPS))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-slot-clear", action="store_true")
    parser.add_argument("--field", action="append", default=[])
    parser.add_argument("--run-id", default="")
    parser.add_argument("--dir", default="")
    return parser


def main(argv: list[str], environ: Mapping[str, str] | None = None, gh_runner=run_gh) -> int:
    source = os.environ if environ is None else environ
    args = build_parser().parse_args(argv)
    if args.command in ("watch", "download"):
        if not re.fullmatch(r"[0-9]{1,12}", args.run_id):
            raise TriggerError("run_id")
        if args.command == "watch":
            command = ["gh", "run", "watch", args.run_id, "--repo", REPO, "--exit-status"]
        else:
            if not args.dir or args.dir.startswith("-"):
                raise TriggerError("dir")
            command = ["gh", "run", "download", args.run_id, "--repo", REPO, "--dir", args.dir]
        if not args.execute:
            json.dump({"argv": command, "executed": False, "aws_env_stripped": clean_env(source)[1]}, sys.stdout)
            sys.stdout.write("\n")
            return 0
        env, _stripped = clean_env(source)
        proc = gh_runner(command, env)
        return proc.returncode
    if args.step is None:
        raise TriggerError("step")
    fields = parse_fields(args.field)
    payload = plan_payload(args.step, fields, source)
    launching = needs_slot_ack(args.step, fields)
    if not args.execute or (launching and not args.confirm_slot_clear):
        payload["executed"] = False
        if launching and args.execute and not args.confirm_slot_clear:
            payload["reason"] = "confirm_slot_clear"
        json.dump(payload, sys.stdout)
        sys.stdout.write("\n")
        return 2 if launching and args.execute and not args.confirm_slot_clear else 0
    env, stripped = clean_env(source)
    payload["aws_env_stripped"] = stripped
    payload["executed"] = True
    proc = gh_runner(list(payload["argv"]), env)
    payload["returncode"] = proc.returncode
    json.dump(payload, sys.stdout)
    sys.stdout.write("\n")
    return proc.returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except TriggerError as exc:
        print(exc.reason, file=sys.stderr)
        raise SystemExit(2) from exc
