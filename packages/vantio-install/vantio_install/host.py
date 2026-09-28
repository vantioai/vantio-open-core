"""Host facts. Live probing is read-only. Fixture files drive the tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


def empty_runtime_state() -> dict:
    return {
        "processes": [],
        "bpf_pins": [],
        "clsact_ifaces": [],
        "images": [],
        "containers": [],
        "product_files": [],
        "probe_errors": [],
        "optics_cli_version": None,
        "enforce_flag": False,
    }


def ready_host(**overrides: object) -> dict:
    host = {
        "uname_m": "x86_64",
        "os_id": "ubuntu",
        "os_version_id": "24.04",
        "os_pretty_name": "Ubuntu 24.04.4 LTS",
        "kernel": "fixture",
        "btf_vmlinux_exists": True,
        "cgroup_version": "cgroup2",
        "bpffs_mounted": True,
        "bpffs_writable": True,
        "tracefs_mounted": True,
        "docker_binary": True,
        "docker_version": "27.0.0",
        "docker_sock_path": "/var/run/docker.sock",
        "apparmor_enabled": True,
        "apparmor_parser": True,
        "principal_can_talk_to_docker": False,
        "privilege_mode": "sudo",
        "sudo_available": True,
        "mem_total_kib": 16 * 1024 * 1024,
        "ifaces": {"ens5": "up"},
        "node_version": "v20.11.0",
    }
    host.update(empty_runtime_state())
    host.update(overrides)
    return host


def load_fixture(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("fixture host must be a JSON object")
    base = empty_runtime_state()
    base.update(data)
    return base


def probe_live() -> dict:
    """Read-only host facts. Missing probes stay UNKNOWN rather than a fake pass."""
    host = empty_runtime_state()
    host["uname_m"] = _read_text(["uname", "-m"]) or "UNKNOWN"
    host["kernel"] = _read_text(["uname", "-r"]) or "UNKNOWN"
    os_release = _parse_os_release(Path("/etc/os-release"))
    host["os_id"] = os_release.get("ID", "UNKNOWN")
    host["os_version_id"] = os_release.get("VERSION_ID", "UNKNOWN")
    host["os_pretty_name"] = os_release.get("PRETTY_NAME", "UNKNOWN")
    host["btf_vmlinux_exists"] = Path("/sys/kernel/btf/vmlinux").is_file()
    host["cgroup_version"] = (
        "cgroup2" if Path("/sys/fs/cgroup/cgroup.controllers").exists() else "UNKNOWN"
    )
    mounts = ""
    if Path("/proc/mounts").is_file():
        mounts = Path("/proc/mounts").read_text(encoding="utf-8", errors="replace")
    host["bpffs_mounted"] = " bpf " in f" {mounts} " or "bpf" in mounts
    bpf = Path("/sys/fs/bpf")
    host["bpffs_writable"] = bpf.is_dir() and os.access(bpf, os.W_OK)
    host["tracefs_mounted"] = _tracefs_mounted(mounts, Path("/sys/kernel/tracing"))
    host["docker_binary"] = shutil.which("docker") is not None
    host["docker_version"] = "UNKNOWN"
    host["apparmor_enabled"] = _apparmor_enabled()
    host["apparmor_parser"] = shutil.which("apparmor_parser") is not None
    sock = Path("/var/run/docker.sock")
    host["docker_sock_path"] = str(sock) if sock.exists() else None
    host["principal_can_talk_to_docker"] = bool(sock.exists() and os.access(sock, os.W_OK))
    host["sudo_available"] = shutil.which("sudo") is not None
    if host["principal_can_talk_to_docker"]:
        host["privilege_mode"] = "docker_group"
    elif host["sudo_available"]:
        host["privilege_mode"] = "sudo"
    else:
        host["privilege_mode"] = "UNKNOWN"
    host["mem_total_kib"] = _mem_total_kib()
    host["ifaces"] = _ifaces()
    host["node_version"] = _node_version()
    host["probe_note"] = "LIVE_READ_ONLY"
    return host


def probe_tracefs_mounted() -> bool:
    """Read the live host. A missing fact in an old snapshot is not this probe."""
    mounts = ""
    mount_table = Path("/proc/mounts")
    if mount_table.is_file():
        try:
            mounts = mount_table.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
    return _tracefs_mounted(mounts, Path("/sys/kernel/tracing"))


def tracefs_present(mounts: str, entry_names: list[str] | None) -> bool:
    """True when tracefs is mounted at /sys/kernel/tracing and that directory has an entry.

    The sealed loader treats an empty /sys/kernel/tracing as missing and then
    tries /sys/kernel/debug/tracing. This contract uses the first path.
    """
    mounted = False
    for line in mounts.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[1] == "/sys/kernel/tracing" and parts[2] == "tracefs":
            mounted = True
            break
    if not mounted:
        return False
    return bool(entry_names)


def _tracefs_mounted(mounts: str, tracing: Path) -> bool:
    try:
        names = [entry.name for entry in tracing.iterdir()] if tracing.is_dir() else []
    except OSError:
        return False
    return tracefs_present(mounts, names)


def _apparmor_enabled() -> bool | str:
    path = Path("/sys/module/apparmor/parameters/enabled")
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return "UNKNOWN"
    if not text:
        return "UNKNOWN"
    return text[0].upper() == "Y"


def _mem_total_kib() -> int | None:
    meminfo = Path("/proc/meminfo")
    if not meminfo.is_file():
        return None
    for line in meminfo.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("MemTotal:"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                return int(parts[1])
    return None


def _ifaces() -> dict[str, str]:
    root = Path("/sys/class/net")
    found: dict[str, str] = {}
    if not root.is_dir():
        return found
    for entry in sorted(root.iterdir()):
        state_path = entry / "operstate"
        state = "UNKNOWN"
        if state_path.is_file():
            state = state_path.read_text(encoding="utf-8", errors="replace").strip() or "UNKNOWN"
        found[entry.name] = state
    return found


def _node_version() -> str | None:
    node = shutil.which("node")
    if not node:
        return None
    return _read_text([node, "--version"])


def _read_text(argv: list[str]) -> str | None:
    try:
        completed = subprocess.run(argv, check=False, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _parse_os_release(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.is_file():
        return data
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key] = value.strip().strip('"')
    return data
