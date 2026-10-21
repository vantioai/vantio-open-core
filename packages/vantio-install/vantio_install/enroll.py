"""Systemd drop-ins that place a unit in the enrolled slice.

A customer cannot use enforcement without a way to enroll the workload.
``enroll --unit`` writes ``Slice=vantio-enrolled.slice``. ``unenroll`` removes
that drop-in. Units named ``vantio-*``, ``docker``, ``containerd``, ``sshd``,
or ``systemd-*`` are refused.
"""

from __future__ import annotations

import re
from pathlib import Path

from vantio_install import constants

_UNIT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_.@+\-]{0,200}$")
_EXACT = frozenset({"docker", "containerd", "sshd"})
_PREFIXES = ("vantio-", "systemd-")


def normalize_unit(name: str) -> str | None:
    text = name.strip()
    if not text or "/" in text or text.startswith(".") or ".." in text:
        return None
    if text.endswith(".service"):
        unit = text
    elif "." in text:
        return None
    else:
        unit = text + ".service"
    base = unit[: -len(".service")]
    if not _UNIT.fullmatch(unit) or not _UNIT.fullmatch(base):
        return None
    return unit


def refusal_reason(name: str) -> str | None:
    unit = normalize_unit(name)
    if unit is None:
        return "UNIT_REFUSED"
    base = unit[: -len(".service")]
    if base in _EXACT or unit in {item + ".service" for item in _EXACT}:
        return "UNIT_REFUSED"
    if base.startswith(_PREFIXES) or unit.startswith(_PREFIXES):
        return "UNIT_REFUSED"
    return None


def dropin_path(root: Path, unit: str) -> Path:
    return root / "etc/systemd/system" / f"{unit}.d" / constants.ENROLL_DROPIN_NAME


def dropin_text() -> str:
    return f"[Service]\nSlice={constants.ENROLLED_SLICE}\n"


def write_dropin(root: Path, unit: str, reloader) -> dict:
    reason = refusal_reason(unit)
    if reason is not None:
        return {"ok": False, "reason": reason, "unit": unit}
    path = dropin_path(root, unit)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dropin_text(), encoding="utf-8")
    path.chmod(0o644)
    try:
        rc = int(reloader(["systemctl", "daemon-reload"]))
    except (OSError, TypeError, ValueError):
        rc = 1
    if rc != 0:
        path.unlink(missing_ok=True)
        return {"ok": False, "reason": "DAEMON_RELOAD_FAILED", "unit": unit}
    return {"ok": True, "reason": "ENROLLED", "unit": unit, "path": path.relative_to(root).as_posix()}


def remove_dropin(root: Path, unit: str, reloader) -> dict:
    normalized = normalize_unit(unit)
    if normalized is None:
        return {"ok": False, "reason": "UNIT_REFUSED", "unit": unit}
    path = dropin_path(root, normalized)
    if not path.is_file():
        return {"ok": True, "reason": "ABSENT", "unit": normalized, "removed": False}
    path.unlink()
    folder = path.parent
    try:
        folder.rmdir()
    except OSError:
        pass
    try:
        rc = int(reloader(["systemctl", "daemon-reload"]))
    except (OSError, TypeError, ValueError):
        rc = 1
    if rc != 0:
        return {"ok": False, "reason": "DAEMON_RELOAD_FAILED", "unit": normalized, "removed": True}
    return {"ok": True, "reason": "UNENROLLED", "unit": normalized, "removed": True}


def remove_all_dropins(root: Path, reloader) -> dict:
    systemd = root / "etc/systemd/system"
    removed: list[str] = []
    if systemd.is_dir():
        for path in sorted(systemd.rglob(constants.ENROLL_DROPIN_NAME)):
            if not path.is_file():
                continue
            unit = path.parent.name[:-2] if path.parent.name.endswith(".d") else path.parent.name
            path.unlink()
            try:
                path.parent.rmdir()
            except OSError:
                pass
            removed.append(unit)
    if removed:
        try:
            rc = int(reloader(["systemctl", "daemon-reload"]))
        except (OSError, TypeError, ValueError):
            rc = 1
        if rc != 0:
            return {"ok": False, "reason": "DAEMON_RELOAD_FAILED", "removed": removed}
    return {"ok": True, "reason": "UNENROLLED", "removed": removed}


def residual_dropins(root: Path) -> list[dict]:
    systemd = root / "etc/systemd/system"
    if not systemd.is_dir():
        return []
    items = []
    for path in sorted(systemd.rglob(constants.ENROLL_DROPIN_NAME)):
        if path.is_file():
            items.append({"kind": "enroll_dropin", "path": path.relative_to(root).as_posix()})
    return items
