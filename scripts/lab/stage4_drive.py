#!/usr/bin/env python3
"""Runner for the stage 4 workflow.

gcloud runs only when GCP_LAB_EXECUTE=1. The phase list, the phase command,
the reboot command, and the grade come from scripts/gcp/enforcement_proof.py
in this checkout. This file does not call that module's run function, because
that function creates its own VM. DS checks are not invented and are not run.
live_enforcement stays NOT_PROVEN.
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from stage4_plan import (  # noqa: E402
    ALLOWED_PROJECT,
    HARNESS_FILES,
    MACHINE_TYPE,
    ZONE,
    PlanError,
    create_argv,
    delete_argv,
    disk_by_name_argv,
    disk_label_argv,
    ds_hold_text,
    ds_is_hold,
    enforcement_claim,
    guard_problems,
    harness_root,
    image_describe_argv,
    instance_name,
    list_argv,
    parse_soak_minutes,
    remaining_names,
    require_project,
    stop_script,
    target,
)

GUEST_DIR = "/var/lib/vantio-lab/guest"
# The harness refuses a stop shorter than 90 minutes and longer than its
# own 120 minute cap. That cap is not this job's 360 minute timeout.
HARNESS_STOP_MINUTES = "120"


def _candidates(raw: str) -> list[Path]:
    if raw.strip() == "":
        return []
    return [Path(part) for part in raw.split(":") if part]


def _guard_from_env(*, after_auth: bool = False) -> list[str]:
    return guard_problems(
        project=os.environ.get("GCP_LAB_PROJECT", ""),
        event=os.environ.get("GITHUB_EVENT_NAME"),
        env=dict(os.environ),
        soak=os.environ.get("SOAK_MINUTES"),
        run_go=os.environ.get("RUN_GO", ""),
        host_name=os.environ.get("HOST_NAME", ""),
        harness_candidates=_candidates(os.environ.get("HARNESS_CANDIDATES", "")),
        harness_ref=os.environ.get("HARNESS_REF", ""),
        after_auth=after_auth,
    )


def _print_guard(problems: list[str]) -> int:
    if "harness_entrypoint_missing" in problems:
        print("harness_entrypoint_missing", file=sys.stderr)
        for rel in HARNESS_FILES:
            print(f"searched {rel}", file=sys.stderr)
    for reason in problems:
        if reason != "harness_entrypoint_missing":
            print(reason, file=sys.stderr)
    if problems:
        print(f"live_enforcement={enforcement_claim()}")
        return 2
    print(f"guard=pass live_enforcement={enforcement_claim()}")
    return 0


def _execute() -> bool:
    return os.environ.get("GCP_LAB_EXECUTE") == "1"


def _run(argv: list[str], check: bool) -> subprocess.CompletedProcess[str]:
    if not _execute():
        print(" ".join(argv))
        return subprocess.CompletedProcess(argv, 0, "", "")
    completed = subprocess.run(argv, check=False, text=True, capture_output=True)
    sys.stdout.write(_redact(completed.stdout))
    sys.stderr.write(_redact(completed.stderr))
    if check and completed.returncode != 0:
        raise PlanError(f"gcloud_{completed.returncode}")
    return completed


def _redact(text: str) -> str:
    redacted = text
    for key in ("RUN_GO", "HOST_NAME"):
        value = os.environ.get(key, "")
        if value:
            redacted = redacted.replace(value, "[redacted]")
    return redacted


def _log_dir() -> Path:
    path = Path(os.environ.get("STAGE4_LOG_DIR", "stage4-logs"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _append_log(name: str, text: str) -> None:
    handle = _log_dir() / name
    with handle.open("a", encoding="utf-8") as stream:
        stream.write(_redact(text))


def _record_ds() -> str:
    text = ds_hold_text(os.environ.get("DS_REF", ""), os.environ.get("RUN_GO", "")) + "\n"
    if not ds_is_hold(0, text):
        raise PlanError("ds_hold")
    sys.stdout.write(text)
    _append_log("ds-hold.txt", text)
    return text


def _ssh(name: str, command: str) -> subprocess.CompletedProcess[str]:
    argv = [
        "gcloud",
        "compute",
        "ssh",
        name,
        f"--project={ALLOWED_PROJECT}",
        f"--zone={ZONE}",
        "--tunnel-through-iap",
        "--quiet",
        "--command",
        command,
    ]
    completed = _run(argv, check=False)
    _append_log("ssh.txt", completed.stdout + completed.stderr)
    return completed


def _scp(sources: list[str], destination: str) -> None:
    argv = [
        "gcloud",
        "compute",
        "scp",
        f"--project={ALLOWED_PROJECT}",
        f"--zone={ZONE}",
        "--tunnel-through-iap",
        "--quiet",
        *sources,
        destination,
    ]
    _run(argv, check=True)


def _boot_id(name: str) -> str:
    completed = _ssh(name, "cat /proc/sys/kernel/random/boot_id")
    boot = (completed.stdout or "").strip()
    if completed.returncode != 0 or not boot or "\n" in boot:
        raise PlanError("ssh")
    return boot


def _wait_ssh(name: str) -> str:
    deadline = time.time() + 300
    while time.time() < deadline:
        completed = _ssh(name, "cat /proc/sys/kernel/random/boot_id")
        boot = (completed.stdout or "").strip()
        if completed.returncode == 0 and boot and "\n" not in boot:
            return boot
        time.sleep(10)
    raise PlanError("ssh")


def _wait_boot(name: str, before: str) -> str:
    deadline = time.time() + 480
    while time.time() < deadline:
        completed = _ssh(name, "cat /proc/sys/kernel/random/boot_id")
        boot = (completed.stdout or "").strip()
        if completed.returncode == 0 and boot and boot != before and "\n" not in boot:
            return boot
        time.sleep(10)
    raise PlanError("reboot")


def _startup_file() -> Path:
    path = _log_dir() / "startup.sh"
    path.write_text(stop_script(), encoding="utf-8")
    return path


def _create(role: str) -> str:
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    argv = create_argv(run_id, role, str(_startup_file()))
    _run(argv, check=True)
    _run(disk_label_argv(run_id, role), check=True)
    return argv[4]


def _open_vm(role: str) -> str:
    """Describe the image, then create. A miss does not create."""
    spec = target(role)
    described = _run(image_describe_argv(role), check=False)
    if described.returncode != 0 or described.stdout.strip() != spec["image"]:
        raise PlanError("image")
    return _create(role)


def phase_commands(harness: object) -> list[tuple[str, str]]:
    """Commands for one full slice. The harness owns the text of each command."""
    phases = tuple(harness.phases_for("full"))  # type: ignore[attr-defined]
    if phases.count("compare") != 2 or "reboot" not in phases:
        raise PlanError("harness_phase_count")
    commands: list[tuple[str, str]] = []
    compares = 0
    for phase in phases:
        if phase == "reboot":
            commands.append((phase, harness.REBOOT_COMMAND))  # type: ignore[attr-defined]
            continue
        if phase == "compare":
            compares += 1
            if compares == 2:
                commands.append(("archive", harness.ARCHIVE_COMMAND))  # type: ignore[attr-defined]
        try:
            command = harness.ssh_phase_command(phase)  # type: ignore[attr-defined]
        except SystemExit as exc:
            raise PlanError("phase") from exc
        commands.append((phase, command))
    if compares != 2:
        raise PlanError("harness_phase_count")
    return commands


def _load_harness(root: Path) -> object:
    """Load this repo's harness. No second checkout."""
    gcp = root / "scripts" / "gcp"
    if str(gcp) not in sys.path:
        sys.path.insert(0, str(gcp))
    return importlib.import_module("enforcement_proof")


def _proof_env(harness: object, loader_dir: Path, deb_dir: Path) -> dict[str, str]:
    """Pass the harness pin. Drop the two paths the auth action exports."""
    pinned = harness.PE_GIT_SHA  # type: ignore[attr-defined]
    supplied = os.environ.get("PE_GIT_SHA", "")
    if supplied not in ("", pinned):
        raise PlanError("pe_git_sha")
    return {
        "GCP_LAB_PROJECT": ALLOWED_PROJECT,
        "PROOF_SLICE": "full",
        "PE_GIT_SHA": pinned,
        "PROOF_RUN_GO": os.environ.get("RUN_GO", ""),
        "PROOF_HOST_NAME": os.environ.get("HOST_NAME", ""),
        "STOP_AFTER_MINUTES": HARNESS_STOP_MINUTES,
        "INSTANCE_NAME": "",
        "LOADER_DIR": str(loader_dir),
        "DEB_DIR": str(deb_dir),
    }


def require_source_sha(loader_dir: Path, pinned: str) -> None:
    path = loader_dir / "SOURCE_SHA"
    text = path.read_text(encoding="utf-8").strip() if path.is_file() else ""
    if text != pinned:
        raise PlanError("pe_git_sha")


def _private_dir() -> Path:
    root = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "stage4-private"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _assert_logs_clean() -> None:
    secret = os.environ.get("RUN_GO", "")
    if not secret:
        return
    for path in _log_dir().rglob("*"):
        if not path.is_file():
            continue
        if secret in path.read_text(encoding="utf-8", errors="replace"):
            raise PlanError("log_redaction")


def _copy_guest_scripts(name: str) -> None:
    _scp(
        [
            str(Path(__file__).resolve().parent / "stage4_plan.py"),
            str(Path(__file__).resolve().parent / "stage4_guest.sh"),
        ],
        f"{name}:/tmp/",
    )


def _install_loader(name: str, loader_dir: Path) -> None:
    made = _ssh(
        name,
        "sudo mkdir -p /var/lib/vantio-lab/guest && "
        "sudo chown -R \"$(id -u):$(id -g)\" /var/lib/vantio-lab",
    )
    if made.returncode != 0:
        raise PlanError("guest_dir")
    for filename in (
        "vantio-loader",
        "enforcement_proof_lab.sh",
        "ldd.txt",
        "loader.sha256",
        "script.sha256",
    ):
        _scp([str(loader_dir / filename)], f"{name}:/var/lib/vantio-lab/guest/{filename}")
    mode = _ssh(
        name,
        "chmod 755 /var/lib/vantio-lab/guest/vantio-loader "
        "/var/lib/vantio-lab/guest/enforcement_proof_lab.sh",
    )
    if mode.returncode != 0:
        raise PlanError("loader_mode")


def _guest(name: str, mode: str, role: str) -> subprocess.CompletedProcess[str]:
    spec = target(role)
    minutes = parse_soak_minutes(os.environ.get("SOAK_MINUTES"))
    command = " ".join(
        [
            "sudo",
            "env",
            f"EXPECTED_IMAGE={spec['image']}",
            f"EXPECTED_UNAME={spec['uname']}",
            f"BPF_MODE={spec['bpf']}",
            f"SOAK_MINUTES={minutes}",
            "STAGE4_PLAN=/tmp/stage4_plan.py",
            "bash",
            "/tmp/stage4_guest.sh",
            mode,
        ]
    )
    return _ssh(name, command)


def _preflight(name: str, role: str) -> None:
    before = _boot_id(name)
    completed = _guest(name, "preflight", role)
    if completed.returncode in (10, 255):
        _wait_boot(name, before)
        completed = _guest(name, "preflight", role)
    if completed.returncode != 0:
        raise PlanError("preflight")


def _fetch_debs(root: Path, dest: Path) -> None:
    script = root / "scripts" / "gcp" / "fetch_offline_debs.sh"
    if not script.is_file():
        raise PlanError("offline_debs_missing")
    dest.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        ["bash", str(script), str(dest)],
        check=False,
        text=True,
        capture_output=True,
    )
    _append_log("debs.txt", completed.stdout + completed.stderr)
    if completed.returncode != 0:
        raise PlanError("offline_debs")


def _stage_harness(name: str, harness: object, loader_dir: Path, deb_dir: Path) -> None:
    stage = _private_dir() / "guest-stage"
    env = _proof_env(harness, loader_dir, deb_dir)
    try:
        paths = harness._write_guest_files(env, stage, with_loader=True)  # type: ignore[attr-defined]
    except SystemExit as exc:
        reason = exc.code if isinstance(exc.code, str) else "stage"
        raise PlanError(reason) from exc
    made = _ssh(
        name,
        "sudo mkdir -p /var/lib/vantio-lab && sudo rm -rf "
        f"{GUEST_DIR} && sudo mkdir -p {GUEST_DIR} && "
        "sudo chown -R \"$(id -u):$(id -g)\" /var/lib/vantio-lab "
        f"{GUEST_DIR} && chmod 755 /var/lib/vantio-lab {GUEST_DIR}",
    )
    if made.returncode != 0:
        raise PlanError("guest_dir")
    # The harness copies each staged file to GUEST_DIR/<file name>.
    for path in paths:
        _scp([str(path)], f"{name}:{GUEST_DIR}/{path.name}")
    prepared = _ssh(name, harness.PREPARE_COMMAND)  # type: ignore[attr-defined]
    if prepared.returncode != 0:
        raise PlanError("guest_prepare")


def _run_phases(name: str, harness: object) -> None:
    compares_seen = 0
    observed: dict[str, str] = {}
    for phase, command in phase_commands(harness):
        if phase == "reboot":
            before = _boot_id(name)
            completed = _ssh(name, command)
            after = _wait_boot(name, before)
            observed = {"before": before, "after": after}
            if completed.returncode not in (0, 255):
                raise PlanError("reboot")
            continue
        if phase == "archive":
            archived = _ssh(name, command)
            if archived.returncode != 0:
                raise PlanError("archive")
            continue
        if phase == "compare":
            compares_seen += 1
        completed = _ssh(name, command)
        text = (completed.stdout or "") + (completed.stderr or "")
        lines = harness.kept_lines(text)  # type: ignore[attr-defined]
        if phase == "reboot-post" and observed and observed.get("before") == observed.get("after"):
            raise PlanError("reboot")
        if not harness.phase_accepted(phase, lines, completed.returncode):  # type: ignore[attr-defined]
            raise PlanError(f"phase_{phase}")
        _append_log("phases.txt", f"phase={phase} outcome=accepted\n")
    if compares_seen != 2:
        raise PlanError("harness_phase_count")


def _require_loader(harness: object, loader_dir: Path) -> None:
    require_source_sha(loader_dir, harness.PE_GIT_SHA)  # type: ignore[attr-defined]
    try:
        harness.check_loader_dir(loader_dir)  # type: ignore[attr-defined]
    except SystemExit as exc:
        reason = exc.code if isinstance(exc.code, str) else "loader_missing"
        raise PlanError(str(reason)) from exc


def _target(role: str) -> int:
    after_auth = os.environ.get("STAGE4_AFTER_AUTH") == "1"
    problems = _guard_from_env(after_auth=after_auth)
    if problems:
        return _print_guard(problems)
    spec = target(role)
    print(
        " ".join(
            [
                f"role={role}",
                f"image={spec['image']}",
                f"uname={spec['uname']}",
                f"machine={MACHINE_TYPE}",
                f"live_enforcement={enforcement_claim()}",
            ]
        )
    )
    if not _execute():
        print("execute=0")
        _record_ds()
        return 0
    root = harness_root(_candidates(os.environ.get("HARNESS_CANDIDATES", "")))
    if root is None:
        raise PlanError("harness_entrypoint_missing")
    try:
        harness = _load_harness(root)
    except (ImportError, OSError, RuntimeError) as exc:
        print(type(exc).__name__, file=sys.stderr)
        raise PlanError("harness_import") from exc
    private = _private_dir()
    loader_dir = Path(os.environ.get("LOADER_DIR", ""))
    deb_dir = private / "debs"
    _require_loader(harness, loader_dir)
    if harness.precheck(_proof_env(harness, loader_dir, deb_dir)) != 0:  # type: ignore[attr-defined]
        raise PlanError("precheck")
    if role != "refuse":
        phase_commands(harness)
        _fetch_debs(root, deb_dir)
    name = _open_vm(role)
    _wait_ssh(name)
    _copy_guest_scripts(name)
    _preflight(name, role)
    if role == "refuse":
        _install_loader(name, loader_dir)
        refused = _guest(name, "refuse", role)
        if refused.returncode != 0:
            raise PlanError("refusal")
        _assert_logs_clean()
        _record_ds()
        return 0
    _stage_harness(name, harness, loader_dir, deb_dir)
    _run_phases(name, harness)
    soaked = _guest(name, "soak", role)
    if soaked.returncode != 0:
        raise PlanError("soak")
    _assert_logs_clean()
    _record_ds()
    print(f"live_enforcement={enforcement_claim()}")
    return 0


def _rows(kind: str, run_id: str) -> list[tuple[str, str]]:
    completed = _run(list_argv(kind, run_id), check=True)
    rows: list[tuple[str, str]] = []
    for line in completed.stdout.splitlines():
        parts = line.split()
        if not parts:
            continue
        place = parts[1] if len(parts) > 1 else ""
        rows.append((parts[0], place))
    return rows


def _require_project() -> int | None:
    try:
        require_project(os.environ.get("GCP_LAB_PROJECT", ""))
    except PlanError as exc:
        print(exc.reason, file=sys.stderr)
        return 2
    return None


def _teardown() -> int:
    failed = _require_project()
    if failed is not None:
        return failed
    if not _execute():
        print("execute=0")
        return 0
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    for kind in ("instances", "disks", "addresses"):
        for name, place in _rows(kind, run_id):
            _run(delete_argv(kind, name, place), check=True)
    return 0


def _verify() -> int:
    failed = _require_project()
    if failed is not None:
        return failed
    if not _execute():
        print("execute=0")
        return 0
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    left: list[str] = []
    for kind in ("instances", "disks", "addresses"):
        for name, _place in _rows(kind, run_id):
            left.append(f"{kind}:{name}")
    for role in ("debian", "ubuntu", "refuse"):
        disk_name = instance_name(run_id, role)
        completed = _run(disk_by_name_argv(disk_name), check=True)
        for name in remaining_names(completed.stdout):
            left.append(f"disks:{name}")
    if left:
        print("resources_remain", file=sys.stderr)
        for item in left:
            print(item, file=sys.stderr)
        return 1
    print("verified_removed=yes")
    print(f"live_enforcement={enforcement_claim()}")
    return 0


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else ""
    try:
        if command == "guard":
            return _print_guard(_guard_from_env())
        if command == "target":
            return _target(os.environ.get("ROLE", ""))
        if command == "teardown":
            return _teardown()
        if command == "verify":
            return _verify()
        if command == "ds-hold":
            text = _record_ds()
            if not ds_is_hold(0, text):
                return 2
            return 0
    except PlanError as exc:
        print(exc.reason, file=sys.stderr)
        print(f"live_enforcement={enforcement_claim()}")
        return 2
    print("usage", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
