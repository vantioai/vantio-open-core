"""Boot-hold operations. Filesystem edits stay under the layout root."""

from __future__ import annotations

import json
import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from vantio_install.boot_hold.audit import append_audit
from vantio_install.boot_hold.constants import (
    DROPIN_NAME,
    HEALTH_REL,
    HELD_MESSAGE,
    HOLD_STATE_REL,
    LOADER_ARGV_REL,
    NETWORK_NAME,
    PROFILE_REL,
    PROOF_CEILING,
    PROOF_STATE,
    REBOOT_ROW,
    SLICE,
    SLICE_PATH,
)
from vantio_install.boot_hold.errors import BootHoldError
from vantio_install.boot_hold.files import allow_profile, deny_profile, dropin_text
from vantio_install.boot_hold.identity import Caller, require_operator
from vantio_install.boot_hold.net import install_hold, remove_hold
from vantio_install.boot_hold.policy import (
    config_path,
    load_policy,
    mechanisms_active,
    require_explicit_matrix,
    save_policy,
)
from vantio_install.boot_hold.readiness import evaluate_ready
from vantio_install.boot_hold.registry import (
    compose_text_gated,
    empty_registry,
    find_workload,
    load_registry,
    restart_is_gated,
    save_registry,
    upsert,
    validate_docker_name,
    validate_protected_path,
    validate_unit_name,
)
from vantio_install.boot_hold.units import compose_service, enrolled_docker_service, static_units, wants_links

Runner = Callable[[list[str]], int]


def envelope(command: str, state: str, message: str, **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "command": command,
        "state": state,
        "message": message,
        "proof_state": PROOF_STATE,
        "proof_ceiling": PROOF_CEILING,
        "reboot_row": REBOOT_ROW,
        "host_wide_default_route_hold": False,
    }
    body.update(extra)
    return body


def _write_json(path: Path, body: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def load_hold_state(root: Path) -> dict:
    return _read_json(root / HOLD_STATE_REL)


def save_hold_state(root: Path, body: dict) -> None:
    path = root / HOLD_STATE_REL
    _write_json(path, body)
    os.chmod(path, 0o600)


def protected_paths(registry: dict) -> list[str]:
    found: list[str] = []
    for row in registry.get("workloads") or []:
        if not row.get("enrolled"):
            continue
        for path in row.get("protected_paths") or []:
            if path not in found:
                found.append(path)
    return found


def _write_profile(root: Path, text: str, runner: Runner) -> str:
    path = root / PROFILE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    os.chmod(path, 0o644)
    binary = "/usr/sbin/apparmor_parser"
    if runner([binary, "-V"]) != 0:
        binary = "apparmor_parser"
        if runner([binary, "-V"]) != 0:
            return "UNAVAILABLE"
    if runner([binary, "-r", "-K", "-T", str(path)]) != 0:
        return "FAILED"
    return "LOADED"


def _unit_dropin_path(root: Path, unit: str) -> Path:
    return root / "etc/systemd/system" / f"{unit}.d" / DROPIN_NAME


def write_workload_dropins(
    root: Path,
    registry: dict,
    policy: dict,
    *,
    file_hold: bool,
    apparmor: bool,
    start_gate: bool = True,
) -> None:
    hold, ordering = mechanisms_active(policy)
    for row in registry.get("workloads") or []:
        if not row.get("enrolled") or row.get("kind") != "systemd":
            continue
        unit = str(row["unit"])
        text = dropin_text(
            hold=hold,
            ordering=ordering,
            protected_paths=list(row.get("protected_paths") or []),
            apparmor=apparmor and file_hold and hold,
            hide_paths=file_hold and hold,
            start_gate=start_gate,
        )
        if not hold and not ordering:
            path = _unit_dropin_path(root, unit)
            if path.exists():
                path.unlink()
            continue
        path = _unit_dropin_path(root, unit)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def install_tree(root: Path, python: str, policy: dict) -> list[str]:
    written: list[str] = []
    for rel, text in static_units(python, policy).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written.append(rel)
    for rel, target in wants_links().items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or path.exists():
            path.unlink()
        path.symlink_to(target)
        written.append(rel)
    cgroup = root / "sys/fs/cgroup" / SLICE
    cgroup.mkdir(parents=True, exist_ok=True)
    return written


def _daemon_reload(runner: Runner) -> None:
    runner(["systemctl", "daemon-reload"])


def _try_restart_active(runner: Runner, unit: str) -> None:
    if runner(["systemctl", "is-active", unit]) == 0:
        runner(["systemctl", "try-restart", unit])


def workload_view(registry: dict, *, held: bool) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in registry.get("workloads") or []:
        if row.get("enrolled"):
            protection = "HELD" if held else "UNPROTECTED"
        else:
            protection = "UNPROTECTED"
        rows.append(
            {
                "id": str(row.get("id", "")),
                "kind": str(row.get("kind", "")),
                "enrolled": "yes" if row.get("enrolled") else "no",
                "protection": protection,
            }
        )
    return rows


def status_body(root: Path, *, lookup: str | None = None) -> dict[str, Any]:
    policy, notes = load_policy(root)
    try:
        registry = load_registry(root)
        registry_state = "READ"
    except BootHoldError as exc:
        registry = empty_registry()
        registry_state = "UNKNOWN"
        notes = notes + [str(exc)]
    hold_on, ordering_on = mechanisms_active(policy)
    state = load_hold_state(root)
    released = bool(state.get("released"))
    network_installed = bool(state.get("network_hold"))
    units_installed = (root / "etc/systemd/system/vantio-boot-hold.service").exists()
    held = False
    if registry_state == "UNKNOWN":
        health = "UNKNOWN"
        message = "Enrollment status is UNKNOWN. Unknown is not a pass."
        overall = "UNKNOWN"
    elif not policy.get("enabled", True):
        health = "OPTED_OUT"
        overall = "OPTED_OUT"
        message = "Boot hold is off because a root admin opted out. Enrolled workloads are not held. The audit log records that opt-out."
    elif network_installed and not released:
        health = "DEGRADED"
        overall = "HELD"
        message = HELD_MESSAGE
        held = True
    elif state.get("last_reason") == "BREAK_GLASS":
        health = "DEGRADED"
        overall = "RELEASED"
        message = (
            "A root operator released the hold with break-glass while Phantom Engine was not enforce-ready. "
            "The reboot row stays NOT_PROVED."
        )
    elif released and state.get("last_reason") == "enforce-ready":
        health = "HANDOFF"
        overall = "RELEASED"
        message = (
            "The hold released after the enforce-ready probe passed. "
            "This status does not mark the reboot exposure row proved."
        )
    elif hold_on and not units_installed:
        health = "DEGRADED"
        overall = "CONFIGURED"
        message = (
            "Boot hold defaults on. The units are not installed yet, so the packet filter is not holding enrolled workloads. "
            "Install them with `vantio-boot-hold install`."
        )
    elif hold_on and not network_installed:
        health = "DEGRADED"
        overall = "CONFIGURED"
        message = (
            "Boot hold is configured on. `vantio-boot-hold.service` applies the enrolled packet hold at boot, before Docker. "
            "Until that service runs, status stays CONFIGURED."
        )
    else:
        health = "DEGRADED"
        overall = "HOLD_OFF"
        message = "The network hold is off because a root admin set hold to off. Ordering may still gate starts. The audit log records that change."
    workloads = workload_view(registry, held=held)
    if lookup:
        match = find_workload(registry, lookup)
        if match is None or not match.get("enrolled"):
            workloads.append(
                {
                    "id": lookup,
                    "kind": "lookup",
                    "enrolled": "no",
                    "protection": "UNPROTECTED",
                }
            )
    return envelope(
        "status",
        overall,
        message,
        health=health,
        enabled=bool(policy.get("enabled", True)),
        hold=hold_on,
        ordering=ordering_on,
        released=released,
        registry=registry_state,
        workloads=workloads,
        notes=notes,
        unprotected_rule="A workload that is absent from the enrollment registry is unprotected.",
        file_profile=state.get("file_profile", "UNKNOWN"),
    )


def _audit_refusal(root: Path, caller: Caller, action: str, exc: BootHoldError) -> None:
    try:
        append_audit(root, caller, action, "REFUSED", {"message": str(exc)})
    except OSError:
        return


def _authorize(root: Path, caller: Caller, action: str) -> None:
    try:
        require_operator(caller)
    except BootHoldError as exc:
        _audit_refusal(root, caller, action, exc)
        raise


def install(root: Path, caller: Caller, python: str) -> dict[str, Any]:
    _authorize(root, caller, "install")
    policy, _notes = load_policy(root)
    if not (root / "etc/vantio/boot-hold.json").exists():
        save_policy(root, policy)
    written = install_tree(root, python, policy)
    registry = load_registry(root) if (root / "var/lib/vantio/boot-hold/registry.json").exists() else empty_registry()
    save_registry(root, registry)
    append_audit(root, caller, "install", "OK", {"units": len(written)})
    return envelope("install", "INSTALLED", "Boot hold units are installed. The hold defaults on.", units=written)


def apply_boot(root: Path, caller: Caller, runner: Runner, python: str) -> dict[str, Any]:
    _authorize(root, caller, "apply-boot")
    policy, notes = load_policy(root)
    hold_on, _ordering = mechanisms_active(policy)
    registry = load_registry(root) if (root / "var/lib/vantio/boot-hold/registry.json").exists() else empty_registry()
    install_tree(root, python, policy)
    if not hold_on:
        remove_hold(runner, policy)
        if protected_paths(registry):
            _write_profile(root, allow_profile(), runner)
        save_hold_state(
            root,
            {"network_hold": False, "file_profile": "off", "released": True, "last_reason": "hold-off"},
        )
        write_workload_dropins(root, registry, policy, file_hold=False, apparmor=False)
        _daemon_reload(runner)
        message = notes[0] if notes else "The boot hold is off by root admin configuration."
        body = envelope("apply-boot", "HOLD_OFF", message, health="OPTED_OUT" if not policy.get("enabled", True) else "DEGRADED")
        _write_json(root / HEALTH_REL, body)
        append_audit(root, caller, "apply-boot", "HOLD_OFF", {})
        return body
    paths = protected_paths(registry)
    profile_state = "NO_PATHS"
    if paths:
        profile_state = _write_profile(root, deny_profile(paths), runner)
    write_workload_dropins(root, registry, policy, file_hold=True, apparmor=profile_state == "LOADED")
    try:
        install_hold(runner, policy)
    except BootHoldError as exc:
        save_hold_state(
            root,
            {"network_hold": False, "file_profile": profile_state, "released": False, "last_reason": "hold-failed"},
        )
        body = envelope("apply-boot", "HELD", HELD_MESSAGE + " " + str(exc), health="DEGRADED")
        _write_json(root / HEALTH_REL, body)
        append_audit(root, caller, "apply-boot", "FAILED", {"message": str(exc)})
        raise
    (root / "sys/fs/cgroup" / "vantio-enrolled.slice").mkdir(parents=True, exist_ok=True)
    _daemon_reload(runner)
    save_hold_state(
        root,
        {
            "network_hold": True,
            "file_profile": "deny" if profile_state == "LOADED" else profile_state,
            "released": False,
            "last_reason": "boot-hold",
        },
    )
    body = envelope(
        "apply-boot",
        "HELD",
        HELD_MESSAGE,
        health="DEGRADED",
        file_profile=profile_state,
        enrolled_slice=SLICE_PATH,
    )
    _write_json(root / HEALTH_REL, body)
    append_audit(root, caller, "apply-boot", "HELD", {"file_profile": profile_state})
    return body


def _wait_ready(facts_probe: Callable[[], dict], wait_seconds: int, sleep: Callable[[float], None]) -> dict:
    facts = facts_probe()
    verdict = evaluate_ready(facts)
    if wait_seconds <= 0 or verdict["enforce_ready"]:
        return verdict
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline and not verdict["enforce_ready"]:
        sleep(1)
        verdict = evaluate_ready(facts_probe())
    return verdict


def release(
    root: Path,
    caller: Caller,
    runner: Runner,
    *,
    require_ready: bool,
    break_glass: bool,
    operator_flag: bool,
    facts_probe: Callable[[], dict],
    wait_seconds: int = 0,
    sleep: Callable[[float], None] = time.sleep,
    python: str = "/usr/bin/python3",
) -> dict[str, Any]:
    _authorize(root, caller, "release")
    if require_ready and break_glass:
        raise BootHoldError("Pass either --require-enforce-ready or --break-glass.", exit_code=10)
    if not require_ready and not break_glass:
        exc = BootHoldError(
            "Release needs --require-enforce-ready after the probe passes, or --break-glass --i-am-root-operator. The hold does not release on its own.",
            exit_code=10,
        )
        _audit_refusal(root, caller, "release", exc)
        raise exc
    if break_glass and not operator_flag:
        exc = BootHoldError(
            "Break-glass release needs --i-am-root-operator on a host root shell.",
            exit_code=10,
        )
        _audit_refusal(root, caller, "release", exc)
        raise exc
    policy, _notes = load_policy(root)
    registry = load_registry(root) if (root / "var/lib/vantio/boot-hold/registry.json").exists() else empty_registry()
    verdict = _wait_ready(facts_probe, wait_seconds if require_ready else 0, sleep)
    if require_ready and not verdict["enforce_ready"]:
        save_hold_state(
            root,
            {
                "network_hold": True,
                "file_profile": load_hold_state(root).get("file_profile", "deny"),
                "released": False,
                "last_reason": verdict.get("reason") or "not-enforce-ready",
            },
        )
        message = HELD_MESSAGE
        if verdict.get("reason") == "loader-running-not-attached":
            message += " The loader is running and enforcement is not attached, so the hold stays."
        elif verdict.get("reason") == "deny-self-check-failed":
            message += " The live deny check did not pass, so the hold stays."
        body = envelope("release", "HELD", message, health="DEGRADED", ready=verdict)
        _write_json(root / HEALTH_REL, body)
        append_audit(root, caller, "release", "REFUSED", {"ready": verdict})
        raise BootHoldError(message, exit_code=4, state="HELD")
    reason = "enforce-ready" if require_ready else "BREAK_GLASS"
    released = _lift_hold(
        root,
        registry,
        policy,
        runner,
        python,
        clear_start_gate=break_glass,
    )
    save_hold_state(root, {"network_hold": False, "file_profile": "allow", "released": True, "last_reason": reason})
    if reason == "BREAK_GLASS":
        released_text = ", ".join(released)
        message = (
            "A root operator released the boot hold in one action. "
            f"Released: {released_text}. "
            "Start gates no longer require enforce-ready. "
            "The audit log records that list. The reboot row stays NOT_PROVED."
        )
        health = "DEGRADED"
        state = "RELEASED"
    else:
        message = (
            "The hold released after the enforce-ready check, including the live deny check. "
            "The reboot row stays NOT_PROVED."
        )
        health = "HANDOFF"
        state = "RELEASED"
    body = envelope(
        "release",
        state,
        message,
        health=health,
        ready=verdict,
        audit_reason=reason,
        released=released,
    )
    _write_json(root / HEALTH_REL, body)
    append_audit(root, caller, "release", reason, {"ready": verdict, "released": released})
    return body


def _lift_hold(
    root: Path,
    registry: dict,
    policy: dict,
    runner: Runner,
    python: str,
    *,
    clear_start_gate: bool,
) -> list[str]:
    """Remove the packet hold and, on break-glass, the start dependencies."""

    released = ["packet-hold-ipv4", "packet-hold-ipv6", "file-hold"]
    if protected_paths(registry):
        _write_profile(root, allow_profile(), runner)
    remove_hold(runner, policy)
    write_workload_dropins(
        root,
        registry,
        policy,
        file_hold=False,
        apparmor=False,
        start_gate=not clear_start_gate,
    )
    for row in registry.get("workloads") or []:
        if not row.get("enrolled"):
            continue
        if row.get("kind") == "systemd":
            unit = str(row["unit"])
            if clear_start_gate:
                released.append(f"start-gate:{unit}")
                runner(["systemctl", "reset-failed", unit])
            else:
                _try_restart_active(runner, unit)
        elif row.get("kind") == "compose" and clear_start_gate:
            directory = Path(str(row.get("project_dir") or ""))
            unit_name = f"vantio-enrolled-compose-{directory.name}.service"
            unit_path = root / "etc/systemd/system" / unit_name
            if directory.name:
                unit_path.write_text(compose_service(directory.name, str(directory), policy, start_gate=False), encoding="utf-8")
                released.append(f"start-gate:{unit_name}")
                runner(["systemctl", "reset-failed", unit_name])
    if clear_start_gate:
        docker_unit = root / "etc/systemd/system/vantio-enrolled-docker@.service"
        docker_unit.parent.mkdir(parents=True, exist_ok=True)
        docker_unit.write_text(enrolled_docker_service(policy, start_gate=False), encoding="utf-8")
        released.append("start-gate:vantio-enrolled-docker@.service")
        for row in registry.get("workloads") or []:
            if row.get("enrolled") and row.get("kind") == "docker":
                unit = f"vantio-enrolled-docker@{row.get('container')}.service"
                released.append(f"start-gate:{unit}")
                runner(["systemctl", "reset-failed", unit])
    else:
        install_tree(root, python, policy)
    _daemon_reload(runner)
    return released


def enable_from_apply(root: Path, caller: Caller, runner: Runner, python: str) -> dict[str, Any]:
    """Install and enable the hold during vantio-install apply.

    A trusted opt-out file is left as the admin wrote it. Apply does not
    turn the hold back on.
    """

    if not config_path(root).exists():
        save_policy(root, {"enabled": True, "hold": True, "ordering": True})
    return apply_boot(root, caller, runner, python)


def live_boot_hold_runner(argv: list[str]) -> int:
    """Run one boot-hold command on the host. Host-wide packet changes are refused."""

    allowed_root = {"iptables", "ip6tables", "apparmor_parser", "/usr/sbin/apparmor_parser", "systemctl", "systemd-run", "bpftool"}
    if not argv or argv[0] not in allowed_root:
        raise BootHoldError("Refusing a boot-hold command outside the enrolled hold.")
    if argv[0] == "systemctl" and (len(argv) < 2 or argv[1] not in {"daemon-reload", "is-active", "try-restart", "reset-failed"}):
        raise BootHoldError("Refusing a systemctl command that is not part of the boot hold.")
    blob = " ".join(argv)
    if "-P" in argv or "0.0.0.0/0" in blob or "::/0" in blob:
        raise BootHoldError("Refusing a host-wide hold command.")
    completed = subprocess.run(argv, check=False)
    return int(completed.returncode)


def remove_from_apply(root: Path, caller: Caller, runner: Runner) -> None:
    """Rollback/uninstall removes units and packet rules. An opt-out file stays."""

    _authorize(root, caller, "remove")
    policy, _notes = load_policy(root)
    remove_hold(runner, policy)
    for rel in list(static_units("/usr/bin/python3", policy)) + list(wants_links()):
        path = root / rel
        if path.is_symlink() or path.is_file():
            path.unlink()
    save_hold_state(root, {"network_hold": False, "file_profile": "off", "released": True, "last_reason": "removed"})
    append_audit(root, caller, "remove", "OK", {"released": ["packet-hold-ipv4", "packet-hold-ipv6", "units"]})


def enroll_systemd(root: Path, caller: Caller, unit: str, paths: list[str], python: str) -> dict[str, Any]:
    _authorize(root, caller, "enroll")
    unit = validate_unit_name(unit)
    clean = [validate_protected_path(path) for path in paths]
    policy, _notes = load_policy(root)
    registry = load_registry(root) if (root / "var/lib/vantio/boot-hold/registry.json").exists() else empty_registry()
    record = {
        "id": unit,
        "kind": "systemd",
        "enrolled": True,
        "unit": unit,
        "protected_paths": clean,
        "cgroup_parent": SLICE,
    }
    registry = upsert(registry, record)
    save_registry(root, registry)
    apparmor = (root / PROFILE_REL).exists()
    write_workload_dropins(root, registry, policy, file_hold=True, apparmor=apparmor)
    install_tree(root, python, policy)
    append_audit(root, caller, "enroll", "OK", {"unit": unit, "paths": clean})
    return envelope(
        "enroll",
        "ENROLLED",
        f"{unit} is enrolled. It joins {SLICE} and waits for the boot gate.",
        unit=unit,
        protected_paths=clean,
    )


def enroll_docker(
    root: Path,
    caller: Caller,
    name: str,
    restart_policy: str,
    cgroup_parent: str,
    paths: list[str],
    python: str,
    *,
    set_restart_no: bool,
    runner: Runner,
) -> dict[str, Any]:
    _authorize(root, caller, "enroll")
    name = validate_docker_name(name)
    clean = [validate_protected_path(path) for path in paths]
    if set_restart_no and restart_policy not in {"", "no", "none"}:
        if runner(["docker", "update", "--restart=no", name]) != 0:
            raise BootHoldError(f"docker update --restart=no {name} failed. The container stays unenrolled.")
        restart_policy = "no"
    restart_is_gated(restart_policy)
    if cgroup_parent.rstrip("/") not in {f"/{SLICE}", SLICE}:
        raise BootHoldError(
            "Create the container with --cgroup-parent=/vantio-enrolled.slice --restart=no "
            "--security-opt apparmor=vantio-boot-hold --network vantio-enrolled.",
            exit_code=10,
        )
    policy, _notes = load_policy(root)
    registry = load_registry(root) if (root / "var/lib/vantio/boot-hold/registry.json").exists() else empty_registry()
    registry = upsert(
        registry,
        {
            "id": name,
            "kind": "docker",
            "enrolled": True,
            "container": name,
            "protected_paths": clean,
            "cgroup_parent": SLICE,
            "restart": "no",
        },
    )
    save_registry(root, registry)
    install_tree(root, python, policy)
    wants = root / "etc/systemd/system/multi-user.target.wants" / f"vantio-enrolled-docker@{name}.service"
    wants.parent.mkdir(parents=True, exist_ok=True)
    if wants.exists() or wants.is_symlink():
        wants.unlink()
    wants.symlink_to(f"../vantio-enrolled-docker@{name}.service")
    append_audit(root, caller, "enroll", "OK", {"container": name})
    return envelope(
        "enroll",
        "ENROLLED",
        f"Container {name} is enrolled. Docker restart stays no. "
        f"vantio-enrolled-docker@{name}.service starts it after the boot gate.",
        container=name,
    )


def enroll_compose(root: Path, caller: Caller, project_dir: str, compose_text: str, python: str) -> dict[str, Any]:
    _authorize(root, caller, "enroll")
    directory = Path(project_dir)
    if not directory.is_absolute() or any(char in project_dir for char in " \n\t;|&$`"):
        raise BootHoldError("The compose project directory must be an absolute path without spaces.", exit_code=10)
    compose_text_gated(compose_text)
    policy, _notes = load_policy(root)
    name = directory.name
    registry = load_registry(root) if (root / "var/lib/vantio/boot-hold/registry.json").exists() else empty_registry()
    registry = upsert(
        registry,
        {
            "id": f"compose-{name}",
            "kind": "compose",
            "enrolled": True,
            "project_dir": str(directory),
            "protected_paths": [],
            "cgroup_parent": SLICE,
        },
    )
    save_registry(root, registry)
    install_tree(root, python, policy)
    unit_name = f"vantio-enrolled-compose-{name}.service"
    unit_path = root / "etc/systemd/system" / unit_name
    unit_path.write_text(compose_service(name, str(directory), policy), encoding="utf-8")
    wants = root / "etc/systemd/system/multi-user.target.wants" / unit_name
    wants.parent.mkdir(parents=True, exist_ok=True)
    if wants.exists() or wants.is_symlink():
        wants.unlink()
    wants.symlink_to(f"../{unit_name}")
    append_audit(root, caller, "enroll", "OK", {"compose": str(directory)})
    return envelope(
        "enroll",
        "ENROLLED",
        f"Compose project {directory} is enrolled. `docker compose start` runs from {unit_name} after the boot gate.",
        unit=unit_name,
    )


def observe_unenrolled(root: Path, caller: Caller, name: str, kind: str) -> dict[str, Any]:
    _authorize(root, caller, "observe-unenrolled")
    if kind not in {"systemd", "docker", "compose", "process"}:
        raise BootHoldError("Kind must be systemd, docker, compose, or process.", exit_code=10)
    registry = load_registry(root) if (root / "var/lib/vantio/boot-hold/registry.json").exists() else empty_registry()
    registry = upsert(
        registry,
        {"id": name, "kind": kind, "enrolled": False, "protected_paths": [], "note": "observed unenrolled"},
    )
    save_registry(root, registry)
    append_audit(root, caller, "observe-unenrolled", "OK", {"id": name})
    return envelope(
        "observe-unenrolled",
        "UNPROTECTED",
        f"{name} is recorded as unenrolled. It is unprotected and the hold does not apply to it.",
        id=name,
        protection="UNPROTECTED",
    )


def opt_out(root: Path, caller: Caller, runner: Runner, reason: str, python: str) -> dict[str, Any]:
    _authorize(root, caller, "opt-out")
    if not reason.strip():
        raise BootHoldError("Opt-out needs a reason.", exit_code=10)
    policy, _notes = load_policy(root)
    policy["enabled"] = False
    save_policy(root, policy)
    registry = load_registry(root) if (root / "var/lib/vantio/boot-hold/registry.json").exists() else empty_registry()
    remove_hold(runner, policy)
    if protected_paths(registry):
        _write_profile(root, allow_profile(), runner)
    write_workload_dropins(root, registry, policy, file_hold=False, apparmor=False)
    install_tree(root, python, policy)
    _daemon_reload(runner)
    save_hold_state(root, {"network_hold": False, "file_profile": "off", "released": True, "last_reason": "OPT_OUT"})
    append_audit(root, caller, "opt-out", "OK", {"reason": reason})
    body = envelope(
        "opt-out",
        "OPTED_OUT",
        "Boot hold is off. A root admin opted out, and the audit log records the reason. Enrolled workloads are not held.",
        health="OPTED_OUT",
        reason=reason,
    )
    _write_json(root / HEALTH_REL, body)
    return body


def opt_in(root: Path, caller: Caller, runner: Runner, python: str) -> dict[str, Any]:
    _authorize(root, caller, "opt-in")
    save_policy(root, {"enabled": True, "hold": True, "ordering": True})
    append_audit(root, caller, "opt-in", "OK", {})
    return apply_boot(root, caller, runner, python)


def configure(root: Path, caller: Caller, runner: Runner, *, hold: bool, ordering: bool, python: str) -> dict[str, Any]:
    _authorize(root, caller, "configure")
    require_explicit_matrix(hold, ordering)
    save_policy(root, {"enabled": True, "hold": hold, "ordering": ordering})
    append_audit(root, caller, "configure", "OK", {"hold": hold, "ordering": ordering})
    return apply_boot(root, caller, runner, python)


def ensure_network(root: Path, caller: Caller, runner: Runner) -> dict[str, Any]:
    _authorize(root, caller, "ensure-network")
    policy, _notes = load_policy(root)
    if runner(["docker", "network", "inspect", NETWORK_NAME]) != 0:
        if runner(["docker", "network", "create", "--subnet", str(policy["enrolled_subnet_v4"]), NETWORK_NAME]) != 0:
            raise BootHoldError(f"Creating Docker network {NETWORK_NAME} failed.")
    append_audit(root, caller, "ensure-network", "OK", {"subnet": policy["enrolled_subnet_v4"]})
    return envelope(
        "ensure-network",
        "NETWORK_READY",
        f"Docker network {NETWORK_NAME} uses {policy['enrolled_subnet_v4']}. Creating the network does not start enrolled containers.",
    )


def loader_argv(root: Path) -> list[str]:
    path = root / LOADER_ARGV_REL
    if not path.exists():
        raise BootHoldError(
            "Phantom Engine loader command is not configured, so the loader unit fails and enrolled workloads stay held. "
            "A root admin writes a JSON list of strings to /etc/vantio/pe-loader.argv.json.",
            state="HELD",
        )
    if path.stat().st_mode & 0o022:
        raise BootHoldError("The loader argv file is writable by group or other. The loader stays stopped and the hold stays on.", state="HELD")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BootHoldError("pe-loader.argv.json is not valid JSON. The loader stays stopped.", state="HELD") from exc
    if not isinstance(data, list) or not data or not all(isinstance(item, str) and item for item in data):
        raise BootHoldError("pe-loader.argv.json must be a JSON list of strings.", state="HELD")
    if not str(data[0]).startswith("/"):
        raise BootHoldError("The loader command must start with an absolute path.", state="HELD")
    return [str(item) for item in data]


def start_loader(root: Path, caller: Caller) -> dict[str, Any]:
    _authorize(root, caller, "start-loader")
    argv = loader_argv(root)
    append_audit(root, caller, "start-loader", "EXEC", {"argv0": argv[0]})
    return envelope("start-loader", "EXEC", "Starting the Phantom Engine loader command.", argv=argv)
