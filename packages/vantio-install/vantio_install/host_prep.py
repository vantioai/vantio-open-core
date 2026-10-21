"""Consented BPF LSM boot entry.

``host-prep --write-lsm --i-accept-reboot`` writes
``/etc/default/grub.d/99-vantio-lsm.cfg`` when ``bpf`` is not already its own
token in ``/sys/kernel/security/lsm``. The drop-in appends that token. It
runs ``update-grub`` and does not reboot. A Linux server that already lists
``bpf`` is ``NO_CHANGE_NEEDED`` and is left unchanged. That is the usual
case for a stock GCP image.

Removal deletes the drop-in, strips the same ``lsm=`` word from the other
grub assignment files, and runs ``update-grub`` again. A failed regenerate
restores the files.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from vantio_install import constants
from vantio_install.health import bpf_lsm_active

_TOKEN = re.compile(r"lsm=([A-Za-z0-9_,.\-]+)")
_ASSIGN = re.compile(r"^(\s*)(GRUB_CMDLINE_LINUX(?:_DEFAULT)?)(\s*=\s*)(.*)$")
_SAFE = re.compile(r"[A-Za-z0-9_,.\-]+")


def read_lsm(root: Path) -> str | None:
    path = root / "sys/kernel/security/lsm"
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text


def read_boot_id(root: Path) -> str:
    path = root / "proc/sys/kernel/random/boot_id"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def dropin_text(current: str) -> str:
    if not _SAFE.fullmatch(current) or bpf_lsm_active(current):
        raise ValueError("lsm")
    listed = current + ",bpf"
    return f'GRUB_CMDLINE_LINUX="$GRUB_CMDLINE_LINUX lsm={listed}"\n'


def prepare(root: Path, updater) -> dict:
    """Write the drop-in or record that bpf is already active. Never reboots."""
    current = read_lsm(root)
    boot_id = read_boot_id(root)
    if current is None or not current or not _SAFE.fullmatch(current):
        return _record("LSM_UNREADABLE", current or "", boot_id, "", ok=False)
    if bpf_lsm_active(current):
        return _record("NO_CHANGE_NEEDED", current, boot_id, "", ok=True, message="NO_CHANGE_NEEDED")
    text = dropin_text(current)
    path = root / constants.GRUB_DROPIN_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    try:
        rc = int(updater(["update-grub"]))
    except (OSError, TypeError, ValueError):
        rc = 1
    if rc != 0:
        path.unlink(missing_ok=True)
        return _record("UPDATE_GRUB_FAILED", current, boot_id, "", ok=False)
    return _record(
        "REBOOT_REQUIRED",
        current,
        boot_id,
        digest,
        ok=True,
        message="reboot required",
    )


def remove_grub_dropin(root: Path, updater, *, require_grub_cfg: bool = False) -> dict:
    """Delete the drop-in and regenerate grub. Restore the files if that fails."""
    dropin = root / constants.GRUB_DROPIN_RELATIVE
    if not dropin.is_file():
        return {"ok": True, "removed": False, "error": ""}
    try:
        prior = dropin.read_text(encoding="utf-8")
    except OSError:
        return {"ok": False, "removed": False, "error": "lsm_value"}
    token = lsm_value_from_dropin(prior)
    if not token:
        return {"ok": False, "removed": False, "error": "lsm_value"}
    edited: list[tuple[Path, str]] = []
    main = root / "etc/default/grub"
    if main.is_file():
        edited.append((main, main.read_text(encoding="utf-8")))
    extra = root / "etc/default/grub.d"
    if extra.is_dir():
        for path in sorted(extra.glob("*.cfg")):
            if path.resolve() == dropin.resolve():
                continue
            edited.append((path, path.read_text(encoding="utf-8")))
    for path, text in edited:
        path.write_text(strip_lsm_token(text, token), encoding="utf-8")
    dropin.unlink()

    def restore() -> None:
        for path, text in edited:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        dropin.parent.mkdir(parents=True, exist_ok=True)
        dropin.write_text(prior, encoding="utf-8")
        dropin.chmod(0o755)

    try:
        rc = int(updater(["update-grub"]))
    except (OSError, TypeError, ValueError):
        rc = 1
    configs = grub_cfg_paths(root)
    remains = any(cfg_has_token(path, token) for path in configs)
    if rc != 0 or remains or (require_grub_cfg and not configs):
        restore()
        if rc != 0:
            error = "update_grub"
        elif remains:
            error = "grub_cfg_still_has_lsm"
        else:
            error = "grub_cfg_missing"
        return {"ok": False, "removed": False, "error": error}
    return {"ok": True, "removed": True, "error": ""}


def lsm_value_from_dropin(text: str) -> str:
    found = ""
    for match in _TOKEN.finditer(text):
        found = match.group(1)
    return found


def strip_lsm_token(text: str, token: str) -> str:
    needle = "lsm=" + token
    lines: list[str] = []
    for raw in text.splitlines():
        matched = _ASSIGN.match(raw)
        if matched is None:
            lines.append(raw)
            continue
        quoted = matched.group(4).strip()
        quote = '"'
        if len(quoted) >= 2 and quoted[0] == quoted[-1] and quoted[0] in {'"', "'"}:
            value = quoted[1:-1]
            quote = quoted[0]
        else:
            value = quoted
        tokens = [part for part in value.split() if part != needle]
        lines.append(f"{matched.group(1)}{matched.group(2)}={quote}{' '.join(tokens)}{quote}")
    body = "\n".join(lines)
    if text.endswith("\n") or not text:
        body += "\n"
    return body


def grub_cfg_paths(root: Path) -> list[Path]:
    found: list[Path] = []
    for base in ("boot/grub", "boot/efi"):
        folder = root / base
        if folder.is_dir():
            found.extend(sorted(path for path in folder.rglob("grub.cfg") if path.is_file()))
    return found


def cfg_has_token(path: Path, token: str) -> bool:
    needle = "lsm=" + token
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return any(part == needle for line in text.splitlines() for part in line.split())


def customer_grub_present(root: Path) -> bool:
    return (root / constants.GRUB_DROPIN_RELATIVE).is_file()


def _record(result: str, pre_lsm: str, boot_id: str, digest: str, *, ok: bool, message: str = "") -> dict:
    return {
        "ok": ok,
        "result": result,
        "pre_lsm": pre_lsm,
        "boot_id": boot_id,
        "dropin_sha256": digest,
        "message": message or result,
    }
