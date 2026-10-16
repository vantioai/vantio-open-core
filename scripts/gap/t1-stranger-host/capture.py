"""Read boot and uninstall evidence without calling a cloud API."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from constants import MAX_BYTES
from errors import PackageError


def _bounded(text: str, reason: str) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) > MAX_BYTES:
        raise PackageError(reason)
    return text


def capture_boot(root: Path, serial_text: str) -> dict[str, object]:
    serial = _bounded(serial_text, "serial_too_large")
    boot_path = root / "proc/sys/kernel/random/boot_id"
    cmdline_path = root / "proc/cmdline"
    lsm_path = root / "sys/kernel/security/lsm"
    try:
        boot_id = boot_path.read_text(encoding="utf-8", errors="replace").strip()
        cmdline = cmdline_path.read_text(encoding="utf-8", errors="replace").strip()
        enabled = lsm_path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError as exc:
        raise PackageError("boot_id") from exc
    encoded = serial.encode("utf-8")
    return {
        "boot_id": boot_id,
        "cmdline": cmdline,
        "enabled_lsm": enabled,
        "serial_boot_id": boot_id,
        "serial_bytes": len(encoded),
        "serial_log": serial,
        "serial_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def uninstall_line_present(text: str) -> bool:
    return any(line == "UNINSTALL_VERIFIED" for line in text.splitlines())


def vantio_bpftool_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if "vantio" in line.casefold()]


def vantio_pin_names(listing: str) -> list[str]:
    names: list[str] = []
    for line in listing.splitlines():
        name = line.strip().split("/")[-1]
        if name.casefold().startswith("vantio"):
            names.append(name)
    return names


def list_bpffs_pins(root: Path) -> list[str]:
    if not root.is_dir():
        raise PackageError("bpffs_pins_missing")
    found: list[str] = []
    try:
        children = list(root.iterdir())
    except OSError as exc:
        raise PackageError("bpffs_pins_missing") from exc
    for child in children:
        if child.name.casefold().startswith("vantio"):
            found.append(child.name)
        if child.is_symlink() or not child.is_dir():
            continue
        try:
            grandchildren = list(child.iterdir())
        except OSError as exc:
            raise PackageError("bpffs_pins_missing") from exc
        for grand in grandchildren:
            if grand.name.casefold().startswith("vantio"):
                found.append(grand.name)
    return found


def live_bpftool_text() -> str:
    try:
        proc = subprocess.run(
            ["bpftool", "prog", "show"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PackageError("bpftool_missing") from exc
    if proc.returncode != 0:
        raise PackageError("bpftool_missing")
    return proc.stdout or ""


def capture_uninstall(
    *,
    uninstall_text: str,
    bpftool_text: str | None,
    pin_listing: str | None,
    fail_reasons: list[str] | None = None,
) -> dict[str, object]:
    uninstall_text = _bounded(uninstall_text, "uninstall_output_missing")
    body: dict[str, object] = {
        "fail_reasons": list(fail_reasons or []),
        "uninstall_verified_line": uninstall_line_present(uninstall_text),
    }
    if bpftool_text is None:
        body["bpftool_vantio_lines"] = None
    else:
        body["bpftool_vantio_lines"] = vantio_bpftool_lines(_bounded(bpftool_text, "bpftool_missing"))
    if pin_listing is None:
        body["bpffs_vantio_names"] = None
    else:
        body["bpffs_vantio_names"] = vantio_pin_names(_bounded(pin_listing, "bpffs_pins_missing"))
    return body
