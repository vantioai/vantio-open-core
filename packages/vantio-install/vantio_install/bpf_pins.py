"""Known Phantom Engine pins on bpffs.

Rollback and uninstall unlink these names after the container stops.
verify-removal and vantio-verify read the directory. A host snapshot
that lists no pins does not override a name that is still present.
An unreadable directory is a probe error, not an empty result.
"""

from __future__ import annotations

from pathlib import Path

from vantio_install import constants

DEFAULT_BPFFS = Path("/sys/fs/bpf")


def default_bpffs() -> Path:
    return DEFAULT_BPFFS


def scan_known_pins(root: Path) -> tuple[list[str], list[str]]:
    """Return ``(present names, probe errors)``.

    A missing directory means those names are absent. Any other failure
    to inspect the directory or a known name is a probe error.
    """
    try:
        root.lstat()
    except FileNotFoundError:
        return [], []
    except OSError:
        return [], ["bpf"]
    try:
        is_dir = root.is_dir()
    except OSError:
        return [], ["bpf"]
    if not is_dir:
        return [], ["bpf"]
    found: list[str] = []
    for name in constants.BPF_PINS:
        if not _bare_name(name):
            return [], ["bpf"]
        path = root / name
        try:
            path.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            return [], ["bpf"]
        found.append(name)
    return found, []


def unlink_known_pins(root: Path) -> tuple[list[str], list[str]]:
    """Unlink known pin names and return the scan after that attempt.

    ``unlink`` removes the directory entry. A symlink is removed without
    following it. Names outside the known list are left in place.
    """
    try:
        root.lstat()
    except FileNotFoundError:
        return [], []
    except OSError:
        return [], ["bpf"]
    for name in constants.BPF_PINS:
        if not _bare_name(name):
            return [], ["bpf"]
        path = root / name
        try:
            path.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            continue
        try:
            path.unlink()
        except OSError:
            continue
    return scan_known_pins(root)


def _bare_name(name: str) -> bool:
    return bool(name) and name not in {".", ".."} and "/" not in name and "\\" not in name
