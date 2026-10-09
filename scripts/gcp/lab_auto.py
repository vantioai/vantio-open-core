#!/usr/bin/env python3
"""GCP lab guards for one e2-micro in a Vantio-only project.

This module does not install Phantom Engine and does not call GCP unless
GCP_LAB_EXECUTE=1. launch_enabled and sweeper_enabled ship false.
Evidence from these workflows is the gcp-lab artifact prefix.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

REPO = "vantioai/vantio-open-core"
GIT_REF = "refs/heads/main"
WORKFLOW_DIR = ".github/workflows"
WORKFLOWS = (
    "gcp-lab-cost-gate.yml",
    "gcp-lab-provision.yml",
    "gcp-lab-collect.yml",
    "gcp-lab-teardown.yml",
    "gcp-lab-sweeper.yml",
    "gcp-lab-verify-removed.yml",
)
NAME_PREFIX = "vantio-gcp-lab-"
ZONE = "us-central1-a"
REGION = "us-central1"
MACHINE_TYPE = "e2-micro"
IMAGE_FAMILY = "ubuntu-2404-lts-amd64"
IMAGE_PROJECT = "ubuntu-os-cloud"
BOOT_DISK_GB = "10GB"
MAX_LIFE_MINUTES = 120
WORST_CASE_RUN_USD = Decimal("1.00")
LABEL_LAB = "vantio-lab"
LABEL_OWNER = "vantio-owner"
LABEL_EXPIRES = "vantio-expires-epoch"
LABEL_LIFE = "vantio-max-life-min"
LABEL_CREDIT = "vantio-credit-cents"
OWNED_LABELS = {LABEL_LAB: "gcp", LABEL_OWNER: "gha"}
LAB_PROJECT_RE = re.compile(r"^vantio-lab-[a-z][a-z0-9-]{2,18}$")
HERE = Path(__file__).resolve().parent
CAPABILITIES_PATH = HERE / "lab_capabilities.json"


def load_capabilities(path: Path | None = None) -> dict[str, Any]:
    raw = json.loads((path or CAPABILITIES_PATH).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("capabilities")
    return raw


def flag_enabled(capabilities: Mapping[str, Any], name: str) -> bool:
    return capabilities.get(name) is True


def workflow_ref(name: str) -> str:
    if name not in WORKFLOWS:
        raise ValueError("workflow")
    return f"{REPO}/{WORKFLOW_DIR}/{name}@{GIT_REF}"


def attribute_condition() -> str:
    """OIDC condition: one repo, main, and these workflow files only."""
    clauses = " || ".join(
        f"assertion.job_workflow_ref=='{workflow_ref(name)}'" for name in WORKFLOWS
    )
    return (
        f"assertion.repository=='{REPO}' && assertion.ref=='{GIT_REF}' && ({clauses})"
    )


def _decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(field)
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(field) from exc
    if not amount.is_finite():
        raise ValueError(field)
    return amount


def valid_lab_project(project_id: Any) -> bool:
    return (
        isinstance(project_id, str)
        and LAB_PROJECT_RE.fullmatch(project_id) is not None
        and "navera" not in project_id
    )


def budget_amount_usd(budget: Mapping[str, Any]) -> Decimal | None:
    specified = (budget.get("amount") or {}).get("specifiedAmount") or {}
    units = specified.get("units")
    if units is None:
        return None
    nanos = specified.get("nanos") or 0
    try:
        return _decimal(units, "units") + (_decimal(nanos, "nanos") / Decimal("1000000000"))
    except ValueError:
        return None


def budget_project_ids(budget: Mapping[str, Any]) -> list[str]:
    projects = (budget.get("budgetFilter") or {}).get("projects") or []
    found: list[str] = []
    if not isinstance(projects, list):
        return found
    for item in projects:
        if not isinstance(item, str):
            continue
        found.append(item.split("/", 1)[1] if item.startswith("projects/") else item)
    return found


def iam_has_navera(policy: Mapping[str, Any] | None) -> bool:
    if not isinstance(policy, Mapping):
        return False
    for binding in policy.get("bindings") or []:
        if not isinstance(binding, Mapping):
            continue
        for member in binding.get("members") or []:
            if isinstance(member, str) and "navera.io" in member.lower():
                return True
    return False


def credit_usd_from_labels(labels: Mapping[str, Any] | None) -> Decimal | None:
    if not isinstance(labels, Mapping):
        return None
    raw = labels.get(LABEL_CREDIT)
    if not isinstance(raw, str) or not raw.isdigit():
        return None
    return Decimal(raw) / Decimal("100")


def evaluate_cost_gate(payload: Mapping[str, Any]) -> dict[str, Any]:
    """expected_oop_usd is 0 only when the lab cap can cover a $1 ceiling.

    A missing credit, a Navera identity, a budget that is not the lab project,
    or an unarmed cap returns UNKNOWN. This does not invent an out-of-pocket
    dollar figure.
    """
    reasons: list[str] = []
    project = payload.get("lab_project_id")
    if not valid_lab_project(project):
        reasons.append("lab_project")
    if payload.get("billing_account_open") is not True:
        reasons.append("billing_closed")
    if payload.get("navera_identity_present") is not False:
        reasons.append("navera_identity")
    if payload.get("cap_armed") is not True:
        reasons.append("cap_not_armed")
    if payload.get("budget_present") is not True:
        reasons.append("budget_missing")
    budget_projects = payload.get("budget_project_ids")
    if budget_projects != [project]:
        reasons.append("budget_scope")
    credit = None
    budget = None
    spend = None
    try:
        credit = _decimal(payload.get("credit_remaining_usd"), "credit")
    except ValueError:
        reasons.append("credits_unreadable")
    try:
        budget = _decimal(payload.get("budget_amount_usd"), "budget")
    except ValueError:
        reasons.append("budget_amount")
    if credit is not None and budget is not None:
        if budget <= WORST_CASE_RUN_USD:
            reasons.append("budget_not_above_ceiling")
        if credit <= budget:
            reasons.append("credit_not_above_budget")
    spend_source = payload.get("spend_source")
    if payload.get("spend_month_usd") is None:
        empty = (
            payload.get("instance_count") == 0
            and payload.get("disk_count") == 0
            and payload.get("cap_armed") is True
        )
        if empty and "credits_unreadable" not in reasons and "budget_amount" not in reasons:
            spend = Decimal("0")
            spend_source = "empty_project_no_vms_or_disks"
        else:
            reasons.append("spend_unreadable")
    else:
        try:
            spend = _decimal(payload.get("spend_month_usd"), "spend")
            spend_source = spend_source or "supplied"
        except ValueError:
            reasons.append("spend_unreadable")
    if spend is not None and budget is not None and spend + WORST_CASE_RUN_USD >= budget:
        reasons.append("spend_plus_ceiling_reaches_budget")
    passed = not reasons
    return {
        "expected_oop_usd": "0" if passed else "UNKNOWN",
        "abort": not passed,
        "reasons": reasons,
        "worst_case_run_usd": format(WORST_CASE_RUN_USD, "f"),
        "spend_source": spend_source if passed else payload.get("spend_source"),
        "lab_project_id": project,
        "pe_installed": False,
        "cloud": "gcp",
    }


def bounded_minutes(value: Any) -> int:
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("minutes")
    if value < 1 or value > MAX_LIFE_MINUTES:
        raise ValueError("minutes")
    return value


def startup_script(stop_after_minutes: int) -> str:
    minutes = bounded_minutes(stop_after_minutes)
    return "\n".join(
        [
            "#!/bin/bash",
            "set -u",
            "echo VANTIO_GCP_LAB_PROBE_BEGIN",
            "echo KERNEL=$(uname -r)",
            "echo CGROUP=$(stat -fc %T /sys/fs/cgroup 2>/dev/null || echo missing)",
            "if compgen -G /sys/firmware/efi/efivars/SecureBoot-* >/dev/null; then echo SECUREBOOT_EFIVAR=present; else echo SECUREBOOT_EFIVAR=absent; fi",
            "if [ -e /sys/kernel/btf/vmlinux ]; then echo BTF=present; else echo BTF=absent; fi",
            "if [ -d /sys/fs/bpf ]; then echo BPFFS=present; else echo BPFFS=absent; fi",
            "if command -v docker >/dev/null 2>&1; then echo DOCKER=present; else echo DOCKER=absent; fi",
            "echo PE_INSTALLED=false",
            "echo VANTIO_GCP_LAB_PROBE_END",
            f"shutdown -h +{minutes} || systemd-run --on-active={minutes}min --unit=vantio-gcp-lab-stop /sbin/shutdown -h now",
            "",
        ]
    )


def plan_launch(spec: Mapping[str, Any], now_epoch: int) -> dict[str, Any]:
    """Build a create plan. This function does not call GCP."""
    if not isinstance(now_epoch, int) or isinstance(now_epoch, bool) or now_epoch < 1_700_000_000:
        raise ValueError("now")
    project = spec.get("project_id")
    if not valid_lab_project(project):
        raise ValueError("project_id")
    if spec.get("machine_type", MACHINE_TYPE) != MACHINE_TYPE:
        raise ValueError("machine_type")
    if spec.get("zone", ZONE) != ZONE:
        raise ValueError("zone")
    minutes = bounded_minutes(spec.get("stop_after_minutes", MAX_LIFE_MINUTES))
    name = spec.get("name")
    if not isinstance(name, str) or not name.startswith(NAME_PREFIX) or len(name) > 63:
        raise ValueError("name")
    expires = now_epoch + minutes * 60
    labels = {
        LABEL_LAB: "gcp",
        LABEL_OWNER: "gha",
        LABEL_EXPIRES: str(expires),
        LABEL_LIFE: str(minutes),
    }
    return {
        "project_id": project,
        "name": name,
        "zone": ZONE,
        "machine_type": MACHINE_TYPE,
        "image_family": IMAGE_FAMILY,
        "image_project": IMAGE_PROJECT,
        "public_ip": False,
        "service_account": None,
        "shielded_secure_boot": True,
        "shielded_vtpm": True,
        "shielded_integrity_monitoring": True,
        "labels": labels,
        "stop_after_minutes": minutes,
        "pe_installed": False,
    }


def provision_argv(plan: Mapping[str, Any], script_path: str) -> list[str]:
    labels = plan["labels"]
    label_arg = ",".join(f"{key}={labels[key]}" for key in sorted(labels))
    return [
        "gcloud",
        "compute",
        "instances",
        "create",
        plan["name"],
        f"--project={plan['project_id']}",
        f"--zone={plan['zone']}",
        f"--machine-type={plan['machine_type']}",
        f"--image-family={plan['image_family']}",
        f"--image-project={plan['image_project']}",
        f"--boot-disk-size={BOOT_DISK_GB}",
        "--boot-disk-type=pd-balanced",
        "--no-address",
        "--no-service-account",
        "--no-scopes",
        "--shielded-secure-boot",
        "--shielded-vtpm",
        "--shielded-integrity-monitoring",
        f"--labels={label_arg}",
        f"--metadata-from-file=startup-script={script_path}",
    ]


def provision_decision(
    capabilities: Mapping[str, Any],
    gate: Mapping[str, Any],
    instances: Sequence[Mapping[str, Any]],
) -> str:
    if not flag_enabled(capabilities, "launch_enabled"):
        return "launch_disabled"
    if gate.get("expected_oop_usd") != "0" or gate.get("abort") is not False:
        return "cost_gate"
    if slot_occupied(instances):
        return "slot_occupied"
    return "provision"


def slot_occupied(instances: Sequence[Mapping[str, Any]]) -> bool:
    for item in instances:
        status = str(item.get("status") or "").upper()
        if status and status != "TERMINATED":
            return True
    return False


def labels_owned(labels: Mapping[str, Any] | None, name: Any) -> bool:
    if not isinstance(labels, Mapping) or not isinstance(name, str):
        return False
    if not name.startswith(NAME_PREFIX):
        return False
    for key, expected in OWNED_LABELS.items():
        if labels.get(key) != expected:
            return False
    return LABEL_EXPIRES in labels


def sweeper_action(resource: Mapping[str, Any], now_epoch: int) -> str:
    name = resource.get("name")
    labels = resource.get("labels") if isinstance(resource.get("labels"), Mapping) else {}
    if not labels_owned(labels, name):
        return "skip_not_owned"
    raw = labels.get(LABEL_EXPIRES)
    if not isinstance(raw, str) or not raw.isdigit():
        return "skip_no_expiry"
    if now_epoch >= int(raw):
        return "delete"
    return "keep"


def apply_sweeper(action: str, capabilities: Mapping[str, Any]) -> str:
    if action == "delete" and not flag_enabled(capabilities, "sweeper_enabled"):
        return "would_delete"
    return action


def probe_from_serial(text: str) -> dict[str, Any]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in {"KERNEL", "CGROUP", "BTF", "BPFFS", "DOCKER", "PE_INSTALLED", "SECUREBOOT_EFIVAR"}:
            values[key] = value.strip()
    return {
        "markers_complete": (
            "VANTIO_GCP_LAB_PROBE_BEGIN" in text and "VANTIO_GCP_LAB_PROBE_END" in text
        ),
        "kernel": values.get("KERNEL"),
        "cgroup": values.get("CGROUP"),
        "btf": values.get("BTF"),
        "bpffs": values.get("BPFFS"),
        "docker": values.get("DOCKER"),
        "secureboot_efivar": values.get("SECUREBOOT_EFIVAR"),
        "pe_installed": values.get("PE_INSTALLED") == "true",
        "cloud": "gcp",
    }


def removal_status(instances: Sequence[Mapping[str, Any]], disks: Sequence[Mapping[str, Any]], name: str) -> str:
    for item in instances:
        if item.get("name") == name and str(item.get("status") or "").upper() != "TERMINATED":
            return "NOT_REMOVED"
    for disk in disks:
        if isinstance(disk.get("name"), str) and name in disk["name"]:
            return "NOT_REMOVED"
    return "VERIFIED_REMOVED"


def _run_checked(argv: list[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(argv, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        if completed.stderr:
            print(completed.stderr, file=sys.stderr, end="" if completed.stderr.endswith("\n") else "\n")
        raise subprocess.CalledProcessError(
            completed.returncode, argv, output=completed.stdout, stderr=completed.stderr
        )
    return completed


def _run_json(argv: list[str]) -> Any:
    completed = _run_checked(argv)
    text = completed.stdout.strip()
    if not text:
        return []
    return json.loads(text)


def _cents_label(labels: Mapping[str, Any] | None, key: str) -> Decimal | None:
    if not isinstance(labels, Mapping):
        return None
    raw = labels.get(key)
    if not isinstance(raw, str) or not raw.isdigit():
        return None
    return Decimal(raw) / Decimal("100")


def payload_from_project_reads(
    project: Mapping[str, Any],
    billing: Mapping[str, Any],
    policy: Mapping[str, Any] | None,
    instances: Sequence[Mapping[str, Any]],
    disks: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the cost-gate payload from one project's own reads.

    Does not list billing-account budgets and does not describe any other project.
    """
    labels = project.get("labels") if isinstance(project.get("labels"), Mapping) else {}
    project_id = project.get("projectId")
    credit = _cents_label(labels, LABEL_CREDIT)
    budget = _cents_label(labels, "vantio-budget-cents")
    active = [
        item
        for item in instances
        if str(item.get("status") or "").upper() != "TERMINATED"
    ]
    return {
        "lab_project_id": project_id,
        "billing_account_open": billing.get("billingEnabled") is True,
        "navera_identity_present": iam_has_navera(policy),
        "credit_remaining_usd": format(credit, "f") if credit is not None else None,
        "budget_present": budget is not None,
        "budget_project_ids": [project_id] if budget is not None and valid_lab_project(project_id) else [],
        "budget_amount_usd": format(budget, "f") if budget is not None else None,
        "cap_armed": labels.get("vantio-cap") == "alerts-only",
        "spend_month_usd": None,
        "instance_count": len(active),
        "disk_count": len(list(disks)),
    }


def collect_live_payload(project_id: str) -> dict[str, Any]:
    """Read-only describes of the lab project only."""
    project = _run_json(["gcloud", "projects", "describe", project_id, "--format=json"])
    billing = _run_json(["gcloud", "billing", "projects", "describe", project_id, "--format=json"])
    policy = _run_json(["gcloud", "projects", "get-iam-policy", project_id, "--format=json"])
    instances = _run_json(
        ["gcloud", "compute", "instances", "list", f"--project={project_id}", "--format=json"]
    )
    disks = _run_json(["gcloud", "compute", "disks", "list", f"--project={project_id}", "--format=json"])
    if not isinstance(project, dict):
        project = {}
    if not isinstance(billing, dict):
        billing = {}
    if not isinstance(policy, dict):
        policy = {}
    if not isinstance(instances, list):
        instances = []
    if not isinstance(disks, list):
        disks = []
    return payload_from_project_reads(project, billing, policy, instances, disks)


def _github_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def instance_zone(item: Mapping[str, Any]) -> str:
    zone = item.get("zone") or ""
    if isinstance(zone, str) and zone:
        return zone.rstrip("/").split("/")[-1]
    return ZONE


Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]


def _default_runner(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return _run_checked(argv)


def execute_provision(env: Mapping[str, str], runner: Runner | None = None) -> int:
    capabilities = load_capabilities()
    if not flag_enabled(capabilities, "launch_enabled"):
        print("launch_disabled", file=sys.stderr)
        return 2
    if env.get("GCP_LAB_EXECUTE") != "1":
        print("refusing to call gcloud", file=sys.stderr)
        return 2
    project = env.get("GCP_LAB_PROJECT", "")
    gate = json.loads(env.get("GCP_LAB_GATE_JSON") or "{}")
    instances = _run_json(["gcloud", "compute", "instances", "list", f"--project={project}", "--format=json"])
    if not isinstance(instances, list):
        instances = []
    decision = provision_decision(capabilities, gate, instances)
    if decision != "provision":
        print(decision, file=sys.stderr)
        return 2
    now = int(env["GCP_LAB_NOW_EPOCH"]) if env.get("GCP_LAB_NOW_EPOCH") else int(time.time())
    run_id = re.sub(r"[^a-z0-9-]", "", env.get("GITHUB_RUN_ID", "manual").lower()) or "manual"
    name = f"{NAME_PREFIX}{run_id}"[:63]
    plan = plan_launch(
        {
            "project_id": project,
            "name": name,
            "stop_after_minutes": env.get("STOP_AFTER_MINUTES", "30"),
        },
        now,
    )
    script_dir = Path(env.get("RUNNER_TEMP") or "/tmp")
    script_path = script_dir / "gcp-lab-startup.sh"
    script_path.write_text(startup_script(plan["stop_after_minutes"]), encoding="utf-8")
    argv = provision_argv(plan, str(script_path))
    (runner or _default_runner)(argv)
    print(json.dumps({"name": name, "zone": ZONE, "project_id": project, "pe_installed": False, "cloud": "gcp"}))
    return 0


def execute_sweep(env: Mapping[str, str], runner: Runner | None = None) -> int:
    if env.get("GCP_LAB_EXECUTE") != "1":
        print("refusing to call gcloud", file=sys.stderr)
        return 2
    capabilities = load_capabilities()
    project = env.get("GCP_LAB_PROJECT", "")
    instances = _run_json(["gcloud", "compute", "instances", "list", f"--project={project}", "--format=json"])
    if not isinstance(instances, list):
        instances = []
    now = int(env["GCP_LAB_NOW_EPOCH"]) if env.get("GCP_LAB_NOW_EPOCH") else int(time.time())
    actions = []
    for item in instances:
        if not isinstance(item, Mapping):
            continue
        action = apply_sweeper(sweeper_action(item, now), capabilities)
        actions.append({"name": item.get("name"), "action": action})
        if action == "delete":
            (runner or _default_runner)(
                [
                    "gcloud",
                    "compute",
                    "instances",
                    "delete",
                    str(item.get("name")),
                    f"--project={project}",
                    f"--zone={instance_zone(item)}",
                    "--delete-disks=all",
                    "--quiet",
                ]
            )
    print(json.dumps({"actions": actions, "cloud": "gcp", "deleted": any(item["action"] == "delete" for item in actions)}))
    return 0


def execute_teardown(env: Mapping[str, str], runner: Runner | None = None) -> int:
    if env.get("GCP_LAB_EXECUTE") != "1":
        print("refusing to call gcloud", file=sys.stderr)
        return 2
    project = env.get("GCP_LAB_PROJECT", "")
    name = env.get("INSTANCE_NAME", "")
    if not name.startswith(NAME_PREFIX):
        print("skip_not_owned", file=sys.stderr)
        return 2
    instances = _run_json(["gcloud", "compute", "instances", "list", f"--project={project}", "--format=json"])
    if not isinstance(instances, list):
        instances = []
    matched = next((item for item in instances if isinstance(item, Mapping) and item.get("name") == name), None)
    if matched is None or not labels_owned(matched.get("labels"), name):
        print("skip_not_owned", file=sys.stderr)
        return 2
    (runner or _default_runner)(
        [
            "gcloud",
            "compute",
            "instances",
            "delete",
            name,
            f"--project={project}",
            f"--zone={instance_zone(matched)}",
            "--delete-disks=all",
            "--quiet",
        ]
    )
    print(json.dumps({"name": name, "deleted": True, "cloud": "gcp", "pe_installed": False}))
    return 0


def execute_collect(env: Mapping[str, str]) -> int:
    if env.get("GCP_LAB_EXECUTE") != "1":
        print("refusing to call gcloud", file=sys.stderr)
        return 2
    project = env.get("GCP_LAB_PROJECT", "")
    name = env.get("INSTANCE_NAME", "")
    zone = env.get("INSTANCE_ZONE") or ZONE
    completed = subprocess.run(
        [
            "gcloud",
            "compute",
            "instances",
            "get-serial-port-output",
            name,
            f"--project={project}",
            f"--zone={zone}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    probe = probe_from_serial(completed.stdout)
    print(json.dumps(probe))
    return 0 if probe["markers_complete"] else 2


def execute_verify(env: Mapping[str, str]) -> int:
    if env.get("GCP_LAB_EXECUTE") != "1":
        print("refusing to call gcloud", file=sys.stderr)
        return 2
    project = env.get("GCP_LAB_PROJECT", "")
    name = env.get("INSTANCE_NAME", "")
    instances = _run_json(["gcloud", "compute", "instances", "list", f"--project={project}", "--format=json"])
    disks = _run_json(["gcloud", "compute", "disks", "list", f"--project={project}", "--format=json"])
    if not isinstance(instances, list):
        instances = []
    if not isinstance(disks, list):
        disks = []
    status = removal_status(instances, disks, name)
    print(json.dumps({"status": status, "name": name, "cloud": "gcp"}))
    return 0 if status == "VERIFIED_REMOVED" else 2


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    command = args[0] if args else ""
    env = os.environ
    if command == "attribute-condition":
        print(attribute_condition())
        return 0
    if command == "cost-gate":
        if env.get("GCP_LAB_EXECUTE") != "1":
            print("refusing to call gcloud", file=sys.stderr)
            return 2
        decision = evaluate_cost_gate(collect_live_payload(env.get("GCP_LAB_PROJECT", "")))
        print(json.dumps(decision))
        _github_output("expected_oop_usd", decision["expected_oop_usd"])
        return 0 if decision["expected_oop_usd"] == "0" else 2
    if command == "provision":
        return execute_provision(env)
    if command == "sweep":
        return execute_sweep(env)
    if command == "teardown":
        return execute_teardown(env)
    if command == "collect":
        return execute_collect(env)
    if command == "verify-removed":
        return execute_verify(env)
    print(
        "usage: lab_auto.py attribute-condition|cost-gate|provision|sweep|teardown|verify-removed|collect",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
