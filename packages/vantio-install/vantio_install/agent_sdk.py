"""Agent SDK presence on an install prefix.

The host check and residual scan read the npm package tree and the Python
module under the prefix from disk. A saved snapshot that says the SDKs are
absent does not override those trees.

``npm install --global --prefix`` writes ``lib/node_modules/@vantio/agent-sdk``.
``pip install --prefix`` writes the ``vantio`` module and ``vantio_agent_sdk``
dist-info. On Debian and Ubuntu that tree is
``local/lib/python3.X/dist-packages``. Upstream prefix installs use
``lib/python3.X/site-packages``. Both layouts are accepted.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from vantio_install.errors import InstallError

_VERSION = re.compile(r"v?(\d+\.\d+\.\d+)\Z")
_ASSIGNED = re.compile(r"""(?m)^__version__\s*=\s*['"]v?(\d+\.\d+\.\d+)['"]\s*$""")
_METADATA_VERSION = re.compile(r"(?m)^Version:\s*(\S+)\s*$")
_NPM_PACKAGE = Path("lib") / "node_modules" / "@vantio" / "agent-sdk"
_NPM_MANIFEST = _NPM_PACKAGE / "package.json"
_RECEIPT = Path("agent-sdk-receipt.json")
_LIB_BASES = (
    Path("lib"),
    Path("lib64"),
    Path("local") / "lib",
    Path("local") / "lib64",
)
_SITE_LEAVES = ("dist-packages", "site-packages")
_DIST_PREFIXES = ("vantio_agent_sdk-", "vantio-agent-sdk-")
_MAX_VERSION_BYTES = 262144


def agent_sdk_present(prefix: Path) -> bool:
    """True when the prefix still has an SDK tree or the installer receipt."""
    if _npm_present(prefix) or _receipt_present(prefix):
        return True
    return bool(_py_artifacts(prefix))


def agent_sdk_residual_items(prefix: Path) -> list[dict]:
    items: list[dict] = []
    if _npm_present(prefix):
        items.append({"kind": "agent_sdk_npm", "path": _NPM_PACKAGE.as_posix()})
    for artifact in _py_artifacts(prefix):
        try:
            relative = artifact.relative_to(prefix).as_posix()
        except ValueError:
            continue
        items.append({"kind": "agent_sdk_py", "path": relative})
    if _receipt_present(prefix):
        items.append({"kind": "optics_receipt", "name": _RECEIPT.name})
    return items


def observed_agent_sdk_npm_version(prefix: Path) -> str | None:
    """Version declared by the installed ``@vantio/agent-sdk`` manifest."""
    path = prefix / _NPM_MANIFEST
    try:
        if not path.is_file() or not _resolved_inside(path, prefix):
            return None
        if path.stat().st_size > _MAX_VERSION_BYTES:
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


def observed_agent_sdk_py_version(prefix: Path) -> str | None:
    """Version from ``vantio/__init__.py`` when it declares one, otherwise dist-info.

    Disagreeing copies under the prefix have no single observed version.
    """
    declared = [version for version in (_assigned_version(path) for path in _module_inits(prefix)) if version]
    if declared:
        unique = set(declared)
        if len(unique) == 1:
            return declared[0]
        return None
    recorded = [version for version in (_metadata_version(path) for path in _metadata_files(prefix)) if version]
    if recorded and len(set(recorded)) == 1:
        return recorded[0]
    return None


def agent_sdk_npm_verified(prefix: Path, expected: str) -> bool:
    """Package tree exists inside the prefix and the manifest version matches the pin."""
    package = prefix / _NPM_PACKAGE
    try:
        if not (package.is_symlink() or package.is_dir()):
            return False
        if not _resolved_inside(package, prefix):
            return False
    except OSError:
        return False
    return observed_agent_sdk_npm_version(prefix) == expected


def agent_sdk_py_verified(prefix: Path, expected: str) -> bool:
    """``vantio`` module exists inside the prefix and the observed version matches the pin."""
    if not _module_inits(prefix):
        return False
    return observed_agent_sdk_py_version(prefix) == expected


def remove_agent_sdks(prefix: Path) -> None:
    """Delete SDK trees and the installer receipt under prefix."""
    try:
        exists = prefix.exists() or prefix.is_symlink()
    except OSError as exc:
        raise InstallError(
            "The Agent SDK prefix could not be read during removal.",
            exit_code=4,
            state="FAILED_SAFE",
            failure_class="FAILED_SAFE",
        ) from exc
    if not exists:
        return
    _remove_entry(prefix / _NPM_PACKAGE, prefix)
    parent = prefix / _NPM_PACKAGE.parent
    try:
        empty = parent.is_dir() and not parent.is_symlink() and not any(parent.iterdir())
    except OSError:
        empty = False
    if empty and _resolved_inside(parent, prefix):
        parent.rmdir()
    for artifact in _py_artifacts(prefix):
        _remove_entry(artifact, prefix)
    _remove_entry(prefix / _RECEIPT, prefix)


def _npm_present(prefix: Path) -> bool:
    return _node_present(prefix / _NPM_PACKAGE)


def _receipt_present(prefix: Path) -> bool:
    path = prefix / _RECEIPT
    try:
        return path.is_symlink() or path.is_file()
    except OSError:
        return False


def _node_present(path: Path) -> bool:
    try:
        return path.is_symlink() or path.is_dir()
    except OSError:
        return False


def _is_python_dir(name: str) -> bool:
    if name == "python3":
        return True
    if not name.startswith("python3."):
        return False
    return name[len("python3.") :].isdigit()


def _is_sdk_metadata_dir(name: str) -> bool:
    if not (name.endswith(".dist-info") or name.endswith(".egg-info")):
        return False
    return name.startswith(_DIST_PREFIXES)


def _site_dirs(prefix: Path) -> list[Path]:
    found: list[Path] = []
    for relative in _LIB_BASES:
        base = prefix / relative
        try:
            if not base.is_dir() or not _resolved_inside(base, prefix):
                continue
            children = sorted(base.iterdir(), key=lambda item: item.name)
        except OSError:
            continue
        for child in children:
            if not _is_python_dir(child.name):
                continue
            for leaf in _SITE_LEAVES:
                site = child / leaf
                try:
                    if site.is_dir() and _resolved_inside(site, prefix):
                        found.append(site)
                except OSError:
                    continue
    return found


def _py_artifacts(prefix: Path) -> list[Path]:
    found: list[Path] = []
    for site in _site_dirs(prefix):
        try:
            children = sorted(site.iterdir(), key=lambda item: item.name)
        except OSError:
            continue
        for child in children:
            if child.name == "vantio" or _is_sdk_metadata_dir(child.name):
                if _node_present(child):
                    found.append(child)
    return found


def _module_inits(prefix: Path) -> list[Path]:
    found: list[Path] = []
    for artifact in _py_artifacts(prefix):
        if artifact.name != "vantio":
            continue
        init = artifact / "__init__.py"
        try:
            if init.is_file() and _resolved_inside(init, prefix) and init.stat().st_size <= _MAX_VERSION_BYTES:
                found.append(init)
        except OSError:
            continue
    return found


def _metadata_files(prefix: Path) -> list[Path]:
    found: list[Path] = []
    for artifact in _py_artifacts(prefix):
        if not _is_sdk_metadata_dir(artifact.name):
            continue
        for name in ("METADATA", "PKG-INFO"):
            path = artifact / name
            try:
                if path.is_file() and _resolved_inside(path, prefix) and path.stat().st_size <= _MAX_VERSION_BYTES:
                    found.append(path)
            except OSError:
                continue
    return found


def _assigned_version(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    match = _ASSIGNED.search(text)
    if match is None:
        return None
    return match.group(1)


def _metadata_version(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    match = _METADATA_VERSION.search(text)
    if match is None:
        return None
    return _parse_version(match.group(1))


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
            "The Agent SDK prefix could not be read during removal.",
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
