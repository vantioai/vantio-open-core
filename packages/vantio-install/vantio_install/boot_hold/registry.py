"""Persistent enrollment registry. It survives reboot and does not use BPF pins."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from vantio_install.boot_hold.constants import RECOVERY_UNITS, REGISTRY_REL, SLICE
from vantio_install.boot_hold.errors import BootHoldError

_UNIT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_.@\\-]{0,200}\.service$")
_DOCKER_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,120}$")
_RESTART_BAD = re.compile(r"(?im)^\s*restart\s*:\s*(always|unless-stopped|on-failure\b)")

_BLOCKED_EXACT = frozenset(
    {
        "/",
        "/etc",
        "/usr",
        "/bin",
        "/sbin",
        "/lib",
        "/lib64",
        "/boot",
        "/root",
        "/home",
        "/var",
        "/var/lib",
        "/sys",
        "/proc",
        "/dev",
        "/run",
        "/tmp",
        "/etc/ssh",
        "/root/.ssh",
    }
)
_BLOCKED_PREFIXES = (
    "/etc/",
    "/usr/",
    "/bin/",
    "/sbin/",
    "/lib/",
    "/lib64/",
    "/boot/",
    "/sys/",
    "/proc/",
    "/dev/",
    "/run/",
    "/root/.ssh/",
    "/etc/ssh/",
)


def registry_path(root: Path) -> Path:
    return root / REGISTRY_REL


def empty_registry() -> dict:
    return {"version": 1, "workloads": []}


def load_registry(root: Path) -> dict:
    path = registry_path(root)
    if not path.exists():
        return empty_registry()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BootHoldError("The enrollment registry is not valid JSON. Status is UNKNOWN.", state="UNKNOWN") from exc
    if not isinstance(data, dict) or not isinstance(data.get("workloads"), list):
        raise BootHoldError("The enrollment registry is unreadable. Status is UNKNOWN.", state="UNKNOWN")
    return data


def save_registry(root: Path, registry: dict) -> None:
    path = registry_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)
    if root == Path("/"):
        os.chown(path, 0, 0)
        os.chown(path.parent, 0, 0)
        os.chmod(path.parent, 0o700)


def validate_protected_path(raw: str) -> str:
    if not isinstance(raw, str) or not raw.startswith("/") or "\x00" in raw:
        raise BootHoldError(
            "A protected path is an absolute workload directory, three or more levels deep.",
            exit_code=10,
        )
    if ".." in Path(raw).parts:
        raise BootHoldError("Choose a specific workload directory without dot segments.", exit_code=10)
    path = os.path.normpath(raw)
    if path != raw.rstrip("/"):
        raise BootHoldError("Choose a specific workload directory without dot segments.", exit_code=10)
    parts = [part for part in path.split("/") if part]
    if path in _BLOCKED_EXACT or any(path.startswith(prefix) for prefix in _BLOCKED_PREFIXES):
        raise BootHoldError(
            "Choose a workload directory outside SSH, system, and recovery paths.",
            exit_code=10,
        )
    if ".ssh" in parts:
        raise BootHoldError("Choose a workload directory outside SSH paths.", exit_code=10)
    if len(parts) < 3:
        raise BootHoldError(
            "Choose a specific workload directory at least three levels deep.",
            exit_code=10,
        )
    return path


def validate_unit_name(unit: str) -> str:
    if not _UNIT_NAME.match(unit):
        raise BootHoldError("The systemd unit name is not usable for enrollment.", exit_code=10)
    if unit in RECOVERY_UNITS or unit.startswith("ssh"):
        raise BootHoldError(
            f"{unit} stays outside the enrolled slice so SSH, DNS, DHCP, and host agents keep working.",
            exit_code=10,
        )
    return unit


def validate_docker_name(name: str) -> str:
    if not _DOCKER_NAME.match(name):
        raise BootHoldError("The container name is not usable for enrollment.", exit_code=10)
    return name


def restart_is_gated(policy: str | None) -> None:
    text = (policy or "no").strip()
    if text in {"", "no", "none"}:
        return
    raise BootHoldError(
        "Docker restart policy must be `no` for an enrolled container. "
        "A restart policy of always, unless-stopped, or on-failure starts the container with the daemon, "
        "ahead of enforce-ready. Set it with `docker update --restart=no <name>` "
        "and let `vantio-enrolled-docker@.service` start it.",
        exit_code=10,
    )


def compose_text_gated(text: str) -> None:
    if _RESTART_BAD.search(text):
        raise BootHoldError(
            "Compose restart is `always`, `unless-stopped`, or `on-failure`. "
            "Set `restart: \"no\"` so the systemd unit starts the project after enforce-ready.",
            exit_code=10,
        )
    required = (
        ("cgroup_parent", "Set `cgroup_parent: /vantio-enrolled.slice` on the enrolled service."),
        (SLICE, "Point `cgroup_parent` at /vantio-enrolled.slice."),
        ("vantio-boot-hold", "Set `security_opt: apparmor:vantio-boot-hold` on the enrolled service."),
        ("10.250.250.0/24", "Attach the service to a network whose subnet is 10.250.250.0/24."),
    )
    for token, message in required:
        if token not in text:
            raise BootHoldError(message, exit_code=10)


def upsert(registry: dict, record: dict) -> dict:
    workloads = [row for row in registry.get("workloads", []) if row.get("id") != record["id"]]
    workloads.append(record)
    return {"version": 1, "workloads": workloads}


def find_workload(registry: dict, name: str) -> dict | None:
    for row in registry.get("workloads") or []:
        if row.get("id") == name or row.get("unit") == name or row.get("container") == name:
            return row
    return None
