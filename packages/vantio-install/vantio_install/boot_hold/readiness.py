"""Enforce-ready probe. Unknown facts are not ready."""

from __future__ import annotations

import subprocess
from pathlib import Path

from vantio_install.boot_hold.constants import BPF_PINS, ENFORCE_PROGRAM, SLICE


def _attachment(facts: dict) -> dict:
    raw = facts.get("enforcement_attachment")
    return raw if isinstance(raw, dict) else {}


def _self_check(facts: dict) -> dict:
    raw = facts.get("deny_self_check")
    return raw if isinstance(raw, dict) else {}


def evaluate_ready(facts: dict) -> dict:
    """Ready only when enforcement is attached and a live deny check passed.

    A running loader is not enough. A loaded program that is not attached to
    the enrolled cgroup keeps the hold.
    """

    pins = list(facts.get("bpf_pins") or [])
    missing = [name for name in BPF_PINS if name not in pins]
    cmdline = str(facts.get("loader_cmdline") or "")
    tokens = cmdline.split()
    loader_up = "vantio-loader" in cmdline and "--enforce" in tokens
    programs = str(facts.get("bpf_programs") or "")
    program_loaded = ENFORCE_PROGRAM in programs
    attachment = _attachment(facts)
    cgroup = str(attachment.get("cgroup") or "").rstrip("/")
    attached = (
        attachment.get("attached") is True
        and attachment.get("program") == ENFORCE_PROGRAM
        and cgroup.endswith(SLICE)
    )
    policy_loaded = facts.get("policy_loaded") is True and not missing
    health_ok = str(facts.get("loader_health") or "") == "OK"
    check = _self_check(facts)
    live_deny = (
        check.get("attempted") is True
        and check.get("enrolled_denied") is True
        and check.get("unenrolled_allowed") is True
        and check.get("mechanism") == "phantom-engine"
        and check.get("hold_bypassed") is True
    )
    ready = bool(loader_up and program_loaded and attached and policy_loaded and health_ok and live_deny)
    if ready:
        reason = "enforce-ready"
    elif loader_up and program_loaded and not attached:
        reason = "loader-running-not-attached"
    elif loader_up and not live_deny:
        reason = "deny-self-check-failed"
    else:
        reason = "not-enforce-ready"
    return {
        "enforce_ready": ready,
        "missing_pins": missing,
        "loader_up": loader_up,
        "program_loaded": program_loaded,
        "program_attached": attached,
        "policy_loaded": policy_loaded,
        "loader_health_ok": health_ok,
        "live_deny": live_deny,
        "reason": reason,
    }


def interpret_self_check(*, attached: bool, enrolled_rc: int | None, unenrolled_rc: int | None, hold_bypassed: bool) -> dict:
    """Turn probe exit codes into a deny-check record. Unknown stays not-ready."""

    if not attached or enrolled_rc is None or unenrolled_rc is None or not hold_bypassed:
        return {
            "attempted": bool(attached and hold_bypassed and enrolled_rc is not None),
            "enrolled_denied": False,
            "unenrolled_allowed": False,
            "mechanism": "phantom-engine",
            "hold_bypassed": bool(hold_bypassed),
        }
    return {
        "attempted": True,
        "enrolled_denied": enrolled_rc != 0,
        "unenrolled_allowed": unenrolled_rc == 0,
        "mechanism": "phantom-engine",
        "hold_bypassed": True,
    }


def probe_pins(root: Path) -> list[str]:
    base = root / "sys/fs/bpf"
    found: list[str] = []
    if not base.is_dir():
        return found
    for name in BPF_PINS:
        path = base / name
        if not path.exists() or path.is_symlink() or path.is_dir():
            continue
        found.append(name)
    return found


def probe_loader(root: Path) -> tuple[str, str]:
    proc = root / "proc"
    if not proc.is_dir():
        return "", ""
    cmdline = ""
    health = ""
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        raw_path = entry / "cmdline"
        try:
            raw = raw_path.read_bytes()
        except OSError:
            continue
        text = raw.replace(b"\x00", b" ").decode("utf-8", errors="replace")
        if "vantio-loader" not in text:
            continue
        cmdline = text.strip()
        health = _proc_health(entry / "stat")
        break
    return cmdline, health


def _proc_health(stat_path: Path) -> str:
    try:
        text = stat_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    # comm is inside parentheses; state is the next field.
    end = text.rfind(")")
    if end < 0 or end + 2 >= len(text):
        return ""
    state = text[end + 2 :].split()
    if not state:
        return ""
    if state[0] in {"R", "S", "D"}:
        return "OK"
    return state[0]


def probe_programs(bpftool) -> str:
    if bpftool is None:
        return ""
    try:
        return bpftool()
    except OSError:
        return ""


def attachment_from_show(text: str) -> dict:
    attached = ENFORCE_PROGRAM in text
    return {
        "attached": attached,
        "program": ENFORCE_PROGRAM if attached else "",
        "cgroup": f"/sys/fs/cgroup/{SLICE}" if attached else "",
    }


def policy_from_maps(text: str, pins_complete: bool) -> bool:
    return bool(pins_complete and "vantio_enforce" in text)


def _connect_script(host: str, port: int) -> str:
    return (
        "import socket,sys\n"
        "s=socket.socket()\n"
        "s.settimeout(2)\n"
        "try:\n"
        f"    s.connect(({host!r}, {int(port)}))\n"
        "except OSError:\n"
        "    sys.exit(1)\n"
        "s.close()\n"
    )


def connect_argv(host: str, port: int, *, enrolled: bool) -> list[str]:
    argv = ["systemd-run", "--quiet", "--wait", "--pipe", "--collect"]
    argv.extend(["--slice", SLICE if enrolled else "system.slice"])
    argv.extend(["python3", "-c", _connect_script(host, port)])
    return argv


def exception_argv(binary: str, host: str, port: int, *, delete: bool) -> list[str]:
    action = ["-D", "VANTIO_BOOT_HOLD"] if delete else ["-I", "VANTIO_BOOT_HOLD", "1"]
    return [binary, *action, "-p", "tcp", "-d", host, "--dport", str(port), "-m", "cgroup", "--path", SLICE, "-j", "RETURN"]


def perform_deny_self_check(runner, *, host: str, port: int, attached: bool) -> dict:
    """Prove a deny on the enrolled path after the boot-hold rule returns for that one flow.

    The exception is one destination and one port, only for the enrolled cgroup,
    and it is removed before this function returns. If enforcement is not
    attached, the exception is not inserted.
    """

    if not attached or not host or not port:
        return interpret_self_check(attached=False, enrolled_rc=None, unenrolled_rc=None, hold_bypassed=False)
    binary = "ip6tables" if ":" in host else "iptables"
    inserted = runner(exception_argv(binary, host, port, delete=False)) == 0
    if not inserted:
        return interpret_self_check(attached=True, enrolled_rc=None, unenrolled_rc=None, hold_bypassed=False)
    enrolled_rc = 1
    unenrolled_rc = 1
    try:
        enrolled_rc = runner(connect_argv(host, port, enrolled=True))
        unenrolled_rc = runner(connect_argv(host, port, enrolled=False))
    finally:
        runner(exception_argv(binary, host, port, delete=True))
    return interpret_self_check(
        attached=True,
        enrolled_rc=enrolled_rc,
        unenrolled_rc=unenrolled_rc,
        hold_bypassed=True,
    )


def assemble_host_facts(
    root: Path,
    *,
    prog_show: str,
    cgroup_show: str,
    map_show: str,
    runner=None,
    deny_probe: dict | None = None,
) -> dict:
    pins = probe_pins(root)
    cmdline, health = probe_loader(root)
    attachment = attachment_from_show(cgroup_show)
    pins_complete = all(name in pins for name in BPF_PINS)
    policy_loaded = policy_from_maps(map_show, pins_complete)
    check = interpret_self_check(attached=False, enrolled_rc=None, unenrolled_rc=None, hold_bypassed=False)
    if attachment["attached"] and runner is not None and isinstance(deny_probe, dict):
        check = perform_deny_self_check(
            runner,
            host=str(deny_probe.get("host") or ""),
            port=int(deny_probe.get("port") or 0),
            attached=True,
        )
    return {
        "bpf_pins": pins,
        "loader_cmdline": cmdline,
        "loader_health": health,
        "bpf_programs": prog_show,
        "enforcement_attachment": attachment,
        "policy_loaded": policy_loaded,
        "deny_self_check": check,
    }


def probe_host(root: Path, bpftool=None) -> dict:
    cmdline, health = probe_loader(root)
    return {
        "bpf_pins": probe_pins(root),
        "loader_cmdline": cmdline,
        "loader_health": health,
        "bpf_programs": probe_programs(bpftool),
    }


def default_bpftool() -> str:
    completed = subprocess.run(
        ["bpftool", "prog", "show"],
        check=False,
        capture_output=True,
        text=True,
        timeout=8,
    )
    if completed.returncode != 0:
        return ""
    return completed.stdout or ""
