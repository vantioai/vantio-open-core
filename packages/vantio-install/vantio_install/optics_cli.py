"""Optics CLI presence on an install prefix.

The host check and residual scan read ``<prefix>/bin/vantio`` from disk.
A saved snapshot that says the CLI is absent does not override that file.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from vantio_install.errors import InstallError

_VERSION = re.compile(r"v?(\d+\.\d+\.\d+)\Z")
_BIN = Path("bin") / "vantio"
_PACKAGE = Path("lib") / "node_modules" / "@vantio" / "cli"
_PACKAGE_JSON = _PACKAGE / "package.json"
_RECEIPT = Path("optics-cli-receipt.json")


def optics_cli_present(prefix: Path) -> bool:
    """True when the prefix still has the CLI binary or its package tree."""
    binary = prefix / _BIN
    package = prefix / _PACKAGE
    try:
        return binary.is_symlink() or binary.is_file() or package.is_dir()
    except OSError:
        return False


def optics_cli_residual_items(prefix: Path) -> list[dict]:
    items: list[dict] = []
    binary = prefix / _BIN
    package = prefix / _PACKAGE
    try:
        if binary.is_symlink() or binary.is_file():
            items.append({"kind": "optics_cli", "path": "bin/vantio"})
        if package.is_dir():
            items.append({"kind": "optics_cli", "path": "lib/node_modules/@vantio/cli"})
    except OSError:
        return items
    return items


def observed_optics_cli_version(prefix: Path) -> str | None:
    """Version from ``vantio --version`` when it runs, otherwise the package manifest."""
    binary = prefix / _BIN
    try:
        executable = (binary.is_symlink() or binary.is_file()) and _resolved_inside(binary, prefix)
    except OSError:
        executable = False
    if executable:
        probed = _probe_version(binary)
        if probed is not None:
            return probed
    return _declared_version(prefix)


def optics_cli_verified(prefix: Path, expected: str) -> bool:
    """Binary path exists inside the prefix and the observed version matches the pin."""
    binary = prefix / _BIN
    try:
        if not (binary.is_symlink() or binary.is_file()):
            return False
        if not _resolved_inside(binary, prefix):
            return False
    except OSError:
        return False
    return observed_optics_cli_version(prefix) == expected


def remove_optics_prefix(prefix: Path) -> None:
    """Delete the CLI binary, package tree, and installer receipt under prefix."""
    if not prefix.exists() and not prefix.is_symlink():
        return
    for relative in (_BIN, _PACKAGE, _RECEIPT):
        _remove_entry(prefix / relative, prefix)
    parent = prefix / _PACKAGE.parent
    try:
        empty = parent.is_dir() and not parent.is_symlink() and not any(parent.iterdir())
    except OSError:
        empty = False
    if empty and _resolved_inside(parent, prefix):
        parent.rmdir()


def _probe_version(binary: Path) -> str | None:
    if not os.access(binary, os.X_OK):
        return None
    try:
        completed = subprocess.run(
            [str(binary), "--version"],
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return _parse_version(completed.stdout)


def _declared_version(prefix: Path) -> str | None:
    path = prefix / _PACKAGE_JSON
    try:
        if not path.is_file() or not _resolved_inside(path, prefix):
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    version = data.get("version")
    if not isinstance(version, str):
        return None
    return _parse_version(version)


def _parse_version(text: str | None) -> str | None:
    if not text:
        return None
    line = text.strip().splitlines()[0].strip()
    match = _VERSION.fullmatch(line)
    if match is None:
        return None
    return match.group(1)


def _resolved_inside(path: Path, prefix: Path) -> bool:
    base = prefix.resolve(strict=False)
    resolved = path.resolve(strict=False)
    return resolved == base or base in resolved.parents


def _parent_inside(path: Path, prefix: Path) -> bool:
    base = prefix.resolve(strict=False)
    parent = path.parent.resolve(strict=False)
    return parent == base or base in parent.parents


def _escape() -> None:
    raise InstallError(
        "A live path escapes the transaction roots.",
        exit_code=4,
        state="FAILED_SAFE",
        failure_class="FAILED_SAFE",
    )


def _remove_entry(path: Path, prefix: Path) -> None:
    try:
        present = path.is_symlink() or path.exists()
    except OSError as exc:
        raise InstallError(
            "The Optics prefix could not be read during removal.",
            exit_code=4,
            state="FAILED_SAFE",
            failure_class="FAILED_SAFE",
        ) from exc
    if not present:
        return
    if not _parent_inside(path, prefix):
        _escape()
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    if path.is_dir():
        if not _resolved_inside(path, prefix):
            _escape()
        shutil.rmtree(path)
        return
    _escape()
