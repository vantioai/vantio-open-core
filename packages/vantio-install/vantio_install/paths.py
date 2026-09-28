"""Refuse relative paths and dangerous filesystem roots before any write."""

from __future__ import annotations

from pathlib import Path

from vantio_install.constants import DISCLOSURE_FORBIDDEN
from vantio_install.errors import InstallError

_EXACT_DENY = {
    "/",
    "/var",
    "/usr",
    "/tmp",
    "/opt",
    "/home",
    "/etc",
    "/root",
    "/var/tmp",
    "/var/lib",
    "/usr/local",
    "/usr/bin",
}

_PREFIX_DENY = (
    "/home",
    "/root",
    "/proc",
    "/sys",
    "/dev",
    "/boot",
    "/etc",
    "/bin",
    "/sbin",
    "/lib",
    "/lib64",
    "/usr",
)


def assert_safe_root(value: str, *, label: str) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value or value.startswith("~"):
        raise InstallError(
            f"{label} must be an absolute path.",
            exit_code=10,
            state="FAILED_SAFE",
        )
    raw = Path(value)
    if not raw.is_absolute() or ".." in raw.parts:
        raise InstallError(
            f"{label} must be an absolute path with no parent segments.",
            exit_code=10,
            state="FAILED_SAFE",
        )
    resolved = raw.resolve(strict=False)
    text = resolved.as_posix()
    pieces = [part for part in resolved.parts if part != "/"]
    if text in _EXACT_DENY or len(pieces) < 3:
        raise InstallError(
            f"{label} is a dangerous root and cannot be used as an install path.",
            exit_code=10,
            state="FAILED_SAFE",
        )
    for prefix in _PREFIX_DENY:
        if text == prefix or text.startswith(prefix + "/"):
            raise InstallError(
                f"{label} is under a protected system path and cannot be used.",
                exit_code=10,
                state="FAILED_SAFE",
            )
    for needle in DISCLOSURE_FORBIDDEN:
        if needle in text:
            raise InstallError(
                f"{label} contains a path the disclosure gate refuses.",
                exit_code=10,
                state="FAILED_SAFE",
            )
    return resolved
