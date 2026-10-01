"""Enforce-ready probe. Unknown facts are not ready."""

from __future__ import annotations

import subprocess
from pathlib import Path

from vantio_install.boot_hold.constants import BPF_PINS, ENFORCE_PROGRAM


def evaluate_ready(facts: dict) -> dict:
    pins = list(facts.get("bpf_pins") or [])
    missing = [name for name in BPF_PINS if name not in pins]
    cmdline = str(facts.get("loader_cmdline") or "")
    tokens = cmdline.split()
    loader_up = "vantio-loader" in cmdline and "--enforce" in tokens
    programs = str(facts.get("bpf_programs") or "")
    attached = ENFORCE_PROGRAM in programs
    health = str(facts.get("loader_health") or "")
    health_ok = health == "OK"
    ready = not missing and loader_up and attached and health_ok
    return {
        "enforce_ready": ready,
        "missing_pins": missing,
        "loader_up": loader_up,
        "program_attached": attached,
        "loader_health_ok": health_ok,
        "reason": "enforce-ready" if ready else "not-enforce-ready",
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
