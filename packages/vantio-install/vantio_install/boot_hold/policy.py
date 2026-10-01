"""Boot-hold configuration. Missing config means the hold is on."""

from __future__ import annotations

import json
import os
from pathlib import Path

from vantio_install.boot_hold.constants import CONFIG_REL, SLICE, SUBNET_V4, SUBNET_V6
from vantio_install.boot_hold.errors import BootHoldError


def default_policy() -> dict:
    return {
        "enabled": True,
        "hold": True,
        "ordering": True,
        "cgroup_slice": SLICE,
        "enrolled_subnet_v4": SUBNET_V4,
        "enrolled_subnet_v6": SUBNET_V6,
    }


def config_path(root: Path) -> Path:
    return root / CONFIG_REL


def _trusted(root: Path, path: Path) -> bool:
    mode = path.stat().st_mode
    if mode & 0o022:
        return False
    if root == Path("/"):
        return path.stat().st_uid == 0
    return True


def load_policy(root: Path) -> tuple[dict, list[str]]:
    """Return the policy and operator notes.

    A missing file, an unreadable file, or a file that is not a trusted
    root-owned config keeps the hold on. Opt-out is honored only from a
    trusted file that sets ``enabled`` to false.
    """

    path = config_path(root)
    if not path.exists():
        return default_policy(), ["Boot hold config is absent, so the hold stays on."]
    if not _trusted(root, path):
        return default_policy(), [
            "Boot hold config is not a root-owned file with mode 0644 or stricter. Opt-out is ignored and the hold stays on."
        ]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default_policy(), ["Boot hold config is not valid JSON. Opt-out is ignored and the hold stays on."]
    if not isinstance(data, dict):
        return default_policy(), ["Boot hold config must be a JSON object. The hold stays on."]
    policy = default_policy()
    if data.get("enabled") is False:
        policy["enabled"] = False
    if data.get("hold") is False:
        policy["hold"] = False
    if data.get("ordering") is False:
        policy["ordering"] = False
    probe = data.get("deny_probe")
    if isinstance(probe, dict) and isinstance(probe.get("host"), str) and probe.get("host") and isinstance(probe.get("port"), int):
        if probe["host"] not in {"0.0.0.0", "::", "0.0.0.0/0", "::/0"} and 0 < int(probe["port"]) < 65536:
            policy["deny_probe"] = {"host": probe["host"], "port": int(probe["port"])}
    notes: list[str] = []
    if policy["enabled"] is False:
        notes.append("A root admin opted out of the boot hold.")
    elif policy["hold"] is False or policy["ordering"] is False:
        notes.append("A root admin changed hold or ordering. The change is explicit.")
    return policy, notes


def save_policy(root: Path, policy: dict) -> None:
    path = config_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = default_policy()
    body["enabled"] = bool(policy.get("enabled", True))
    body["hold"] = bool(policy.get("hold", True))
    body["ordering"] = bool(policy.get("ordering", True))
    if isinstance(policy.get("deny_probe"), dict):
        body["deny_probe"] = policy["deny_probe"]
    path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(path, 0o644)
    if root == Path("/"):
        os.chown(path, 0, 0)


def mechanisms_active(policy: dict) -> tuple[bool, bool]:
    """Return (hold_on, ordering_on) after the opt-out switch."""

    if not policy.get("enabled", True):
        return False, False
    return bool(policy.get("hold", True)), bool(policy.get("ordering", True))


def require_explicit_matrix(hold: bool, ordering: bool) -> None:
    if not hold and not ordering:
        raise BootHoldError(
            "Turning the hold and ordering off together is an opt-out. Use `vantio-boot-hold opt-out --reason ...`.",
            exit_code=10,
            state="FAILED_SAFE",
        )
