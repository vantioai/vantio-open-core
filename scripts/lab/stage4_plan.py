#!/usr/bin/env python3
"""Plan for the stage 4 GCP lab. This module does not call gcloud.

live_enforcement from this file is NOT_PROVEN. A unit test does not boot a VM.
The harness that exists in this repo is scripts/gcp/enforcement_proof.py.
scripts/gcp/guest_phases.sh and scripts/gcp/proof_grade.py are not in this tree.
DS-01, DS-02, and DS-03 are not invented and are not executed.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ALLOWED_PROJECT = "vantio-lab-oct08"
ZONE = "us-central1-a"
MACHINE_TYPE = "e2-standard-2"
# The loader is built on the runner. The boot disk stays at the 10 GB
# image minimum used by the existing lab plan.
DISK_GB = "10"
DISK_TYPE = "pd-standard"
NETWORK = "vantio-lab-offline"
SUBNET = "vantio-lab-offline-usc1"
# Same tag the existing lab uses so IAP can reach a VM on that network.
NETWORK_TAG = "vantio-gcp-lab"
# GitHub's job cap. The guest schedules its own shutdown at this delay.
JOB_TIMEOUT_MINUTES = 360
LABEL_LAB_KEY = "vantio-lab"
LABEL_LAB_VALUE = "stage4"
LABEL_RUN_KEY = "run-id"
LIVE_ENFORCEMENT = "NOT_PROVEN"
# Exact status for the unwired deep-sweep step. Not a pass. Not exit 2.
DS_HOLD = "DS NOT WIRED — waiting on #85 run 26"
WIF_REUSE = (
    "vantioai/vantio-open-core/.github/workflows/"
    "gcp-lab-cost-gate.yml@main # oidc-trust"
)
AUTH_ACTION = "google-github-actions/auth@"
DS_REF_RE = re.compile(r"[A-Za-z0-9._/-]{1,200}")

# Family names were read from the public catalog on 2026-11-12:
# https://gcloud-compute.com/images.html
# debian-cloud / debian-13 -> debian-13-trixie-v20261102
# ubuntu-os-cloud / ubuntu-2604-lts-amd64 -> ubuntu-2604-resolute-amd64-v20261107
# This run did not call the Compute Engine API and did not boot either image.
DEBIAN_IMAGE_PROJECT = "debian-cloud"
DEBIAN_IMAGE = "debian-13-trixie-v20261102"
DEBIAN_FAMILY = "debian-13"
# trixie-security metapackage linux-image-cloud-amd64 6.12.116-1, as listed
# by https://openfactory.tech/packages/debian-13/linux-image-cloud-amd64
# (synced 2026-11-11). uname -r for that package is the string below.
# The image above was built on 20261102. These are package-page strings.
# Neither pin was booted. Replace them with the observed uname -r from one
# boot of each pin before a lab dispatch treats them as guest fact.
# A mismatch after create deletes that instance.
DEBIAN_UNAME = "6.12.116+deb13-cloud-amd64"

UBUNTU_IMAGE_PROJECT = "ubuntu-os-cloud"
UBUNTU_IMAGE = "ubuntu-2604-resolute-amd64-v20261107"
UBUNTU_FAMILY = "ubuntu-2604-lts-amd64"
# packages.ubuntu.com/resolute/linux-image-gcp 7.0.0-1016.18 depends on
# linux-image-7.0.0-1016-gcp. Fetched 2026-11-12. uname -r is that ABI.
UBUNTU_UNAME = "7.0.0-1016-gcp"
# fetch_offline_debs.sh is an Ubuntu 24.04 snapshot. It is not green phase
# evidence on Debian 13 or Ubuntu 26.04 until both guests have booted it.
# Nothing in this tree sets STAGE4_DEB_BOOT to this token.
# Every role, including refuse, stays behind this token. The uname
# strings below are still the package-page values. A boot has to
# replace them before a dispatch treats them as guest fact.
DEB_BOOT_TOKEN = "debian13-and-ubuntu2604"

SOAK_DEFAULT = 60
SOAK_MAX = 240
HOST_RE = re.compile(r"^[a-z][a-z0-9-]{2,39}$")
RUN_ID_RE = re.compile(r"^[0-9]{1,20}$")
ALLOWED_EVENTS = frozenset({"workflow_dispatch", "workflow_call"})

# The only harness file in this repo. guest_phases.sh and proof_grade.py
# are not required and are not in this tree.
HARNESS_FILES = ("scripts/gcp/enforcement_proof.py",)
# No caller-selected checkout. An empty ref means this repo's checkout.
HARNESS_REF_ALLOWLIST = frozenset({""})

REFUSAL_FIELDS = (
    "INSTALL_ENFORCEMENT_READINESS_BLOCKED",
    "bpf_lsm_inactive",
)
REFUSAL_PHRASE = ("NOT", "ENFORCING")

STATIC_CREDENTIAL_KEYS = (
    "GOOGLE_APPLICATION_CREDENTIALS",
    "GCP_SA_KEY",
    "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE",
)
# google-github-actions/auth exports these two. They are workload-identity
# files, not a caller-supplied key, once that action has run.
AUTH_EXPORTED_KEYS = (
    "GOOGLE_APPLICATION_CREDENTIALS",
    "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE",
)


class PlanError(Exception):
    """Fail closed. reason is a short token, not a secret."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def bpf_lsm_active(list_text: str) -> bool:
    """True when bpf is its own comma-separated LSM token."""
    return any(token.strip() == "bpf" for token in list_text.split(","))


def parse_soak_minutes(value: str | None) -> int:
    raw = str(SOAK_DEFAULT) if value is None or value.strip() == "" else value.strip()
    if not raw.isascii() or not raw.isdigit():
        raise PlanError("soak_minutes")
    minutes = int(raw, 10)
    if minutes < 1 or minutes > SOAK_MAX:
        raise PlanError("soak_minutes")
    return minutes


def require_project(project: str) -> None:
    folded = project.lower()
    if "navera" in folded or project != ALLOWED_PROJECT:
        raise PlanError("project")


def require_event(name: str | None) -> None:
    if name is None or name == "":
        raise PlanError("event")
    if name not in ALLOWED_EVENTS:
        raise PlanError("event")


def require_run_go(value: str) -> None:
    if len(value) < 8 or len(value) > 400:
        raise PlanError("run_go")
    if any(char in value for char in ("\n", "\r", "\x00")):
        raise PlanError("run_go")


def require_host_name(value: str) -> None:
    if HOST_RE.fullmatch(value) is None:
        raise PlanError("host_name")


def require_no_static_creds(env: dict[str, str], *, after_auth: bool = False) -> None:
    skipped = AUTH_EXPORTED_KEYS if after_auth else ()
    for key in STATIC_CREDENTIAL_KEYS:
        if key in skipped:
            continue
        if env.get(key, "").strip():
            raise PlanError("static_credentials")


def require_harness_ref(ref: str) -> None:
    """Reject a caller-selected harness checkout. Empty is the allowlist."""
    if ref not in HARNESS_REF_ALLOWLIST:
        raise PlanError("harness_ref")


def image_matches(metadata_image: str, image_name: str) -> bool:
    name = metadata_image.rstrip("/").split("/")[-1]
    return name == image_name


def uname_matches(actual: str, expected: str) -> bool:
    return actual == expected


def log_fields(text: str) -> list[str]:
    return text.split()


def phrase_in_fields(fields: list[str], phrase: tuple[str, ...]) -> bool:
    width = len(phrase)
    return any(tuple(fields[index : index + width]) == phrase for index in range(len(fields) - width + 1))


def new_vantio_programs(before: list[str], after: list[str]) -> list[str]:
    """Lines that appeared after the loader and name a vantio program."""
    if any(line.strip() == "listing=unavailable" for line in before + after):
        return ["listing=unavailable"]
    fresh = [line for line in after if line not in before]
    return [line for line in fresh if "vantio" in line]


def refusal_holds(text: str, loader_rc: int, before: list[str], after: list[str]) -> bool:
    """Non-zero loader, whole-field tokens, and no new vantio program."""
    if loader_rc == 0 or not text.strip():
        return False
    fields = log_fields(text)
    if any(token not in fields for token in REFUSAL_FIELDS):
        return False
    if not phrase_in_fields(fields, REFUSAL_PHRASE):
        return False
    return not new_vantio_programs(before, after)


def enforcement_claim() -> str:
    return LIVE_ENFORCEMENT


def deb_boot_observed(value: str | None) -> bool:
    """True only for the recorded boot of the offline debs on both guests."""
    return value == DEB_BOOT_TOKEN


def ds_hold_text(ref: str, secret: str = "") -> str:
    """Record the DS input. Do not fetch it and do not print a secret."""
    if ref and (ref == secret or DS_REF_RE.fullmatch(ref) is None):
        shown = "rejected"
    else:
        shown = ref
    return f"{DS_HOLD}\nds_ref={shown}"


def ds_is_hold(exit_code: int, text: str) -> bool:
    """True only for the unwired hold. Exit 2 is not a hold. PASS is not a hold."""
    if exit_code != 0 or "PASS" in text:
        return False
    first = text.strip().splitlines()[0] if text.strip() else ""
    return first == DS_HOLD


TARGETS: dict[str, dict[str, str]] = {
    "debian": {
        "image_project": DEBIAN_IMAGE_PROJECT,
        "image": DEBIAN_IMAGE,
        "family": DEBIAN_FAMILY,
        "uname": DEBIAN_UNAME,
        "bpf": "require",
        "suffix": "deb",
    },
    "ubuntu": {
        "image_project": UBUNTU_IMAGE_PROJECT,
        "image": UBUNTU_IMAGE,
        "family": UBUNTU_FAMILY,
        "uname": UBUNTU_UNAME,
        "bpf": "require",
        "suffix": "ubu",
    },
    "refuse": {
        "image_project": DEBIAN_IMAGE_PROJECT,
        "image": DEBIAN_IMAGE,
        "family": DEBIAN_FAMILY,
        "uname": DEBIAN_UNAME,
        "bpf": "forbid",
        "suffix": "off",
    },
}


def target(role: str) -> dict[str, str]:
    try:
        spec = TARGETS[role]
    except KeyError as exc:
        raise PlanError("role") from exc
    return spec


def instance_name(run_id: str, role: str) -> str:
    spec = target(role)
    if RUN_ID_RE.fullmatch(run_id) is None:
        raise PlanError("run_id")
    name = f"s4-{run_id}-{spec['suffix']}"
    if len(name) > 63 or not re.fullmatch(r"[a-z][a-z0-9-]{0,62}", name):
        raise PlanError("name")
    return name


def labels(run_id: str) -> str:
    if RUN_ID_RE.fullmatch(run_id) is None:
        raise PlanError("run_id")
    return f"{LABEL_LAB_KEY}={LABEL_LAB_VALUE},{LABEL_RUN_KEY}={run_id}"


def stop_script(minutes: int = JOB_TIMEOUT_MINUTES) -> str:
    """Guest backstop. Teardown still deletes the disk after this shutdown."""
    if isinstance(minutes, bool) or not isinstance(minutes, int):
        raise PlanError("stop_minutes")
    if minutes < 1 or minutes > JOB_TIMEOUT_MINUTES:
        raise PlanError("stop_minutes")
    return "\n".join(
        [
            "#!/bin/bash",
            "set -u",
            (
                "systemd-run --on-active="
                f"{minutes}min --unit=vantio-stage4-stop /sbin/shutdown -h now"
            ),
            "",
        ]
    )


def create_argv(run_id: str, role: str, startup_script: str) -> list[str]:
    spec = target(role)
    name = instance_name(run_id, role)
    if not startup_script or "\n" in startup_script or "\x00" in startup_script:
        raise PlanError("startup_script")
    argv = [
        "gcloud",
        "compute",
        "instances",
        "create",
        name,
        f"--project={ALLOWED_PROJECT}",
        f"--zone={ZONE}",
        f"--machine-type={MACHINE_TYPE}",
        f"--image={spec['image']}",
        f"--image-project={spec['image_project']}",
        f"--boot-disk-size={DISK_GB}GB",
        f"--boot-disk-type={DISK_TYPE}",
        f"--boot-disk-name={name}",
        f"--boot-disk-device-name={name}",
        f"--boot-disk-labels={labels(run_id)}",
        f"--network={NETWORK}",
        f"--subnet={SUBNET}",
        "--no-address",
        "--no-service-account",
        "--no-scopes",
        f"--tags={NETWORK_TAG}",
        "--shielded-secure-boot",
        "--shielded-vtpm",
        "--shielded-integrity-monitoring",
        f"--labels={labels(run_id)}",
        "--metadata=enable-oslogin=TRUE,block-project-ssh-keys=TRUE",
        f"--metadata-from-file=startup-script={startup_script}",
        "--maintenance-policy=MIGRATE",
    ]
    flat = " ".join(argv).lower()
    if "preemptible" in flat or "spot" in flat or "accelerator" in flat:
        raise PlanError("create_shape")
    return argv


def image_describe_argv(role: str) -> list[str]:
    """Read-only image lookup. Create does not run until this name exists."""
    spec = target(role)
    return [
        "gcloud",
        "compute",
        "images",
        "describe",
        spec["image"],
        f"--project={spec['image_project']}",
        "--format=value(name)",
    ]


def disk_by_name_argv(name: str) -> list[str]:
    if re.fullmatch(r"s4-[0-9]{1,20}-(deb|ubu|off)", name) is None:
        raise PlanError("disk_name")
    return [
        "gcloud",
        "compute",
        "disks",
        "list",
        f"--project={ALLOWED_PROJECT}",
        f"--filter=name={name}",
        "--format=value(name)",
    ]


def disk_label_argv(run_id: str, role: str) -> list[str]:
    name = instance_name(run_id, role)
    return [
        "gcloud",
        "compute",
        "disks",
        "add-labels",
        name,
        f"--project={ALLOWED_PROJECT}",
        f"--zone={ZONE}",
        f"--labels={labels(run_id)}",
    ]


def list_filter(run_id: str) -> str:
    if RUN_ID_RE.fullmatch(run_id) is None:
        raise PlanError("run_id")
    return (
        f"labels.{LABEL_LAB_KEY}={LABEL_LAB_VALUE} "
        f"AND labels.{LABEL_RUN_KEY}={run_id}"
    )


def list_argv(kind: str, run_id: str) -> list[str]:
    listing = list_filter(run_id)
    if kind == "instances":
        return [
            "gcloud",
            "compute",
            "instances",
            "list",
            f"--project={ALLOWED_PROJECT}",
            f"--filter={listing}",
            "--format=value(name,zone)",
        ]
    if kind == "disks":
        return [
            "gcloud",
            "compute",
            "disks",
            "list",
            f"--project={ALLOWED_PROJECT}",
            f"--filter={listing}",
            "--format=value(name,zone)",
        ]
    if kind == "addresses":
        return [
            "gcloud",
            "compute",
            "addresses",
            "list",
            f"--project={ALLOWED_PROJECT}",
            f"--filter={listing}",
            "--format=value(name,region)",
        ]
    raise PlanError("list_kind")


def delete_argv(kind: str, name: str, place: str) -> list[str]:
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,200}", name):
        raise PlanError("delete_name")
    zone = place.rstrip("/").split("/")[-1] or ZONE
    if kind == "instances":
        return [
            "gcloud",
            "compute",
            "instances",
            "delete",
            name,
            f"--project={ALLOWED_PROJECT}",
            f"--zone={zone}",
            "--delete-disks=all",
            "--quiet",
        ]
    if kind == "disks":
        return [
            "gcloud",
            "compute",
            "disks",
            "delete",
            name,
            f"--project={ALLOWED_PROJECT}",
            f"--zone={zone}",
            "--quiet",
        ]
    if kind == "addresses":
        return [
            "gcloud",
            "compute",
            "addresses",
            "delete",
            name,
            f"--project={ALLOWED_PROJECT}",
            f"--region={zone}",
            "--quiet",
        ]
    raise PlanError("list_kind")


def remaining_names(text: str) -> list[str]:
    names: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        names.append(stripped.split()[0])
    return names


def harness_root(candidates: list[Path]) -> Path | None:
    for root in candidates:
        if all((root / rel).is_file() for rel in HARNESS_FILES):
            return root
    return None


def workflow_on_keys(text: str) -> set[str]:
    """Return the keys directly under a top-level on: block."""
    keys: set[str] = set()
    in_on = False
    for line in text.splitlines():
        if not in_on:
            if re.fullmatch(r"on:\s*", line):
                in_on = True
            continue
        if line.strip() == "" or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent < 2:
            break
        if indent != 2:
            continue
        match = re.match(r"([A-Za-z0-9_-]+):\s*", line.strip())
        if match:
            keys.add(match.group(1))
    return keys


def require_dispatch_only(text: str) -> None:
    if workflow_on_keys(text) != {"workflow_dispatch"}:
        raise PlanError("workflow_trigger")


def require_wif_reuse(text: str) -> None:
    """The caller reuses the cost-gate file. It does not authenticate itself."""
    if AUTH_ACTION in text:
        raise PlanError("wif_auth")
    if WIF_REUSE not in text:
        raise PlanError("wif_reuse")
    if re.search(r"^\s*environment:\s*", text, re.M):
        raise PlanError("environment")


def desired_lsm(list_text: str, mode: str) -> str:
    """LSM list with bpf added or removed. The kernel keeps the last lsm=."""
    if mode not in {"require", "forbid"}:
        raise PlanError("bpf_mode")
    tokens = [
        token.strip()
        for token in list_text.split(",")
        if token.strip() and token.strip() != "bpf"
    ]
    if mode == "require":
        tokens.append("bpf")
    desired = ",".join(tokens)
    if re.fullmatch(r"[a-z0-9_,]*", desired) is None:
        raise PlanError("lsm")
    return desired


def grub_dropin(desired: str) -> str:
    """Shell sourced by grub-mkconfig. lsm= is the last token of DEFAULT."""
    if re.fullmatch(r"[a-z0-9_,]*", desired) is None:
        raise PlanError("lsm")
    return "\n".join(
        [
            "strip_lsm() {",
            "  printf '%s' \"$1\" | sed -E 's/(^|[[:space:]])lsm=[^[:space:]]*//g; s/^[[:space:]]+//; s/[[:space:]]+$//'",
            "}",
            'GRUB_CMDLINE_LINUX="$(strip_lsm "$GRUB_CMDLINE_LINUX")"',
            f'GRUB_CMDLINE_LINUX_DEFAULT="$(strip_lsm "$GRUB_CMDLINE_LINUX_DEFAULT") lsm={desired}"',
            "",
        ]
    )


def last_lsm(cmdline: str) -> str:
    found = ""
    for field in cmdline.split():
        if field.startswith("lsm="):
            found = field[4:]
    return found


def mask_commands(run_go: str, host_name: str) -> str:
    """Workflow mask lines. A newline is rejected before any line is emitted."""
    lines: list[str] = []
    for value in (run_go, host_name):
        if value == "":
            continue
        if any(char in value for char in ("\n", "\r", "\x00")):
            raise PlanError("mask_newline")
        escaped = value.replace("%", "%25")
        lines.append(f"::add-mask::{escaped}")
    return "\n".join(lines)


def guard_problems(
    *,
    project: str,
    event: str | None,
    env: dict[str, str],
    soak: str | None,
    run_go: str,
    host_name: str,
    harness_candidates: list[Path],
    harness_ref: str = "",
    after_auth: bool = False,
) -> list[str]:
    """Problems that must stop the lab before a VM is created."""
    problems: list[str] = []
    checks = (
        lambda: require_project(project),
        lambda: require_event(event),
        lambda: require_no_static_creds(env, after_auth=after_auth),
        lambda: require_harness_ref(harness_ref),
        lambda: parse_soak_minutes(soak),
        lambda: require_run_go(run_go),
        lambda: require_host_name(host_name),
    )
    for check in checks:
        try:
            check()
        except PlanError as exc:
            problems.append(exc.reason)
    if harness_root(harness_candidates) is None:
        problems.append("harness_entrypoint_missing")
    return problems


def _print_error(exc: PlanError) -> int:
    print(exc.reason, file=sys.stderr)
    return 2


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else ""
    if command == "workflow-triggers":
        path = Path(argv[2]) if len(argv) > 2 else Path(".github/workflows/gcp-stage4-lab.yml")
        try:
            require_dispatch_only(path.read_text(encoding="utf-8"))
        except PlanError as exc:
            return _print_error(exc)
        print("workflow_trigger=workflow_dispatch")
        return 0
    if command == "wif-reuse":
        path = Path(argv[2]) if len(argv) > 2 else Path(".github/workflows/gcp-stage4-lab.yml")
        try:
            require_wif_reuse(path.read_text(encoding="utf-8"))
        except PlanError as exc:
            return _print_error(exc)
        print("wif_reuse=gcp-lab-cost-gate")
        return 0
    if command == "soak-minutes":
        try:
            print(parse_soak_minutes(argv[2] if len(argv) > 2 else None))
        except PlanError as exc:
            return _print_error(exc)
        return 0
    if command == "ds-hold":
        sys.stdout.write(
            ds_hold_text(os.environ.get("DS_REF", ""), os.environ.get("RUN_GO", "")) + "\n"
        )
        return 0
    if command == "mask-lines":
        try:
            text = mask_commands(os.environ.get("RUN_GO", ""), os.environ.get("HOST_NAME", ""))
        except PlanError as exc:
            return _print_error(exc)
        if text:
            print(text)
        return 0
    if command == "desired-lsm":
        try:
            print(desired_lsm(os.environ.get("LSM_LIST", ""), os.environ.get("BPF_MODE", "")))
        except PlanError as exc:
            return _print_error(exc)
        return 0
    if command == "grub-dropin":
        try:
            sys.stdout.write(grub_dropin(os.environ.get("DESIRED_LSM", "")))
        except PlanError as exc:
            return _print_error(exc)
        return 0
    if command == "refusal-check":
        log = Path(argv[2]) if len(argv) > 2 else Path("")
        before = Path(argv[3]) if len(argv) > 3 else Path("")
        after = Path(argv[4]) if len(argv) > 4 else Path("")
        raw_rc = argv[5] if len(argv) > 5 else ""
        if not raw_rc.isascii() or not raw_rc.isdigit():
            print("loader_rc", file=sys.stderr)
            return 2
        text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
        before_lines = before.read_text(encoding="utf-8", errors="replace").splitlines() if before.is_file() else []
        after_lines = after.read_text(encoding="utf-8", errors="replace").splitlines() if after.is_file() else []
        fields = log_fields(text)
        for token in REFUSAL_FIELDS:
            print(f"saw={token} {'yes' if token in fields else 'no'}")
        print(f"saw=NOT ENFORCING {'yes' if phrase_in_fields(fields, REFUSAL_PHRASE) else 'no'}")
        if not refusal_holds(text, int(raw_rc, 10), before_lines, after_lines):
            print("refusal", file=sys.stderr)
            return 2
        print("refusal=held")
        print(f"live_enforcement={enforcement_claim()}")
        return 0
    if command != "guest-preflight":
        print("usage", file=sys.stderr)
        return 2
    image = argv[2] if len(argv) > 2 else ""
    uname = argv[3] if len(argv) > 3 else ""
    lsm = argv[4] if len(argv) > 4 else ""
    expected_image = argv[5] if len(argv) > 5 else ""
    expected_uname = argv[6] if len(argv) > 6 else ""
    bpf_mode = argv[7] if len(argv) > 7 else ""
    if not image_matches(image, expected_image):
        print("image", file=sys.stderr)
        return 2
    if not uname_matches(uname, expected_uname):
        print("uname", file=sys.stderr)
        return 2
    active = bpf_lsm_active(lsm)
    if bpf_mode == "require" and not active:
        print("bpf_absent", file=sys.stderr)
        return 10
    if bpf_mode == "forbid" and active:
        print("bpf_present", file=sys.stderr)
        return 10
    if bpf_mode not in {"require", "forbid"}:
        print("bpf_mode", file=sys.stderr)
        return 2
    expected_lsm = argv[8] if len(argv) > 8 else "-"
    cmdline = argv[9] if len(argv) > 9 else ""
    if expected_lsm != "-" and last_lsm(cmdline) != expected_lsm:
        print("cmdline", file=sys.stderr)
        return 2
    print(f"preflight=pass image={expected_image} uname={uname} bpf_mode={bpf_mode}")
    print(f"live_enforcement={enforcement_claim()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
