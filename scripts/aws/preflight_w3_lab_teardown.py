#!/usr/bin/env python3
"""Fail closed unless the w3-lab-teardown GitHub environment is already protected.

This script does not create or delete the environment. GitHub auto-creates an
unprotected environment when a job that sets environment: is scheduled and the
name is missing. The workflow preflight job has no environment key and calls
this script before the assume job.

Audience: INTERNAL_RESTRICTED
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ENVIRONMENT_NAME = "w3-lab-teardown"
REPOSITORY = "vantioai/vantio-open-core"
ALLOWED_BRANCH = "main"
FOUNDER_INSTRUCTION = (
    "The environment w3-lab-teardown must already exist BEFORE any dispatch. "
    "GitHub auto-creates an unprotected environment when a job with environment: is scheduled and the name is missing. "
    "If an unprotected w3-lab-teardown environment was created, delete it, then create the environment "
    f"with no required reviewers and a deployment branch policy of only {ALLOWED_BRANCH}."
)


def load_object(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {"message": f"{path.name} is empty"}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return {"message": f"{path.name} is not JSON: {exc}"}
    if not isinstance(payload, dict):
        return {"message": f"{path.name} is not a JSON object"}
    return payload


def required_reviewers_configured(environment: dict[str, Any]) -> bool:
    """True when a required-reviewer rule is present or its reviewer list is unreadable.

    An empty reviewer list, or no required-reviewer rule at all, is the
    Founder state: the teardown proof runs without a person approving it.
    A malformed reviewer list fails closed.
    """
    rules = environment.get("protection_rules")
    if not isinstance(rules, list):
        return False
    for rule in rules:
        if not isinstance(rule, dict) or rule.get("type") != "required_reviewers":
            continue
        reviewers = rule.get("reviewers")
        if not isinstance(reviewers, list) or len(reviewers) > 0:
            return True
    return False


def branch_policy_only_main(environment: dict[str, Any], policies: dict[str, Any]) -> tuple[bool, str]:
    policy = environment.get("deployment_branch_policy")
    if not isinstance(policy, dict):
        return False, "deployment_branch_policy is missing, so any branch could deploy"
    if policy.get("protected_branches") is True:
        return False, "protected_branches allows every protected branch, not only main"
    if policy.get("custom_branch_policies") is not True:
        return False, "custom_branch_policies is not enabled"
    items = policies.get("branch_policies")
    if not isinstance(items, list) or len(items) != 1:
        return False, "deployment branch policy must contain only main"
    item = items[0]
    if not isinstance(item, dict) or item.get("name") != ALLOWED_BRANCH or item.get("type") != "branch":
        return False, "deployment branch policy is not the main branch"
    total = policies.get("total_count")
    if total is not None and total != 1:
        return False, "deployment branch policy total_count is not 1"
    return True, "only main"


def evaluate(environment: dict[str, Any], policies: dict[str, Any]) -> tuple[bool, str]:
    if environment.get("name") != ENVIRONMENT_NAME:
        message = environment.get("message")
        if message == "Not Found":
            return False, "environment w3-lab-teardown does not exist. " + FOUNDER_INSTRUCTION
        if isinstance(message, str) and message:
            return False, f"environment lookup failed: {message}. " + FOUNDER_INSTRUCTION
        return False, "environment w3-lab-teardown does not exist. " + FOUNDER_INSTRUCTION
    if required_reviewers_configured(environment):
        return False, (
            "a required reviewer is still set on w3-lab-teardown. "
            "Remove the reviewer and keep the deployment branch policy on main only. " + FOUNDER_INSTRUCTION
        )
    ok, detail = branch_policy_only_main(environment, policies)
    if not ok:
        return False, detail + ". " + FOUNDER_INSTRUCTION
    return True, (
        f"environment {ENVIRONMENT_NAME} on {REPOSITORY} has no required reviewers "
        f"and allows only branch {ALLOWED_BRANCH}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the w3-lab-teardown GitHub environment protection.")
    parser.add_argument("--environment", required=True)
    parser.add_argument("--branch-policies", required=True)
    args = parser.parse_args(argv)
    environment = load_object(Path(args.environment))
    policies = load_object(Path(args.branch_policies))
    ok, detail = evaluate(environment, policies)
    status = "PASS" if ok else "FAIL"
    print(f"PREFLIGHT {status} w3-lab-teardown: {detail}", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
