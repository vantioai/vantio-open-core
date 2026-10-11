"""Known Phantom Engine pins on bpffs.

Rollback and uninstall remove these names after the container stops.
On the real host bpffs that removal is `vantio-loader uninstall`, which
also drops persist links, deny-attr, and fail-closed stand-ins, then
prints UNINSTALL_VERIFIED. A fixture directory is still unlinked here.
verify-removal reads the directory. A host snapshot that lists no pins
does not override a name that is still present. An unreadable directory
is a probe error, not an empty result.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from vantio_install import constants

DEFAULT_BPFFS = Path("/sys/fs/bpf")
STANDIN_RECORD = Path("/run/vantio-failclosed-mounts")
ENGINE_ARGV = ("vantio-loader", "uninstall", "--confirm", "uninstall")


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


def engine_uninstall_argv() -> list[str]:
    """Argv for the authorized engine uninstall.

    An enrolled host passes the enterprise token from the environment.
    The word ``uninstall`` is the confirmation. This is not a signal.
    """
    argv = list(ENGINE_ARGV)
    approval = os.environ.get("VANTIO_ENTERPRISE_UNINSTALL_APPROVAL", "").strip()
    if approval:
        argv.extend(["--enterprise-approval", approval])
    return argv


def engine_output_is_verified(returncode: int, stdout: str) -> bool:
    """True only when the engine printed a clean verification line."""
    if returncode != 0:
        return False
    if "UNINSTALL_RESIDUAL" in stdout or "uninstall refused" in stdout:
        return False
    return "UNINSTALL_VERIFIED" in stdout


def remove_known_pins(root: Path) -> tuple[list[str], list[str]]:
    """Remove pins. The real bpffs calls the engine and checks its result.

    A fixture directory is unlinked locally so tests do not need the binary.
    """
    if root == DEFAULT_BPFFS:
        return _remove_real_bpffs(root)
    return unlink_known_pins(root)


def _remove_real_bpffs(root: Path) -> tuple[list[str], list[str]]:
    argv = engine_uninstall_argv()
    try:
        completed = subprocess.run(
            argv,
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(
            "vantio-loader uninstall did not run. Install the engine binary "
            "that prints UNINSTALL_VERIFIED. Partial pin unlink is not removal."
        ) from exc
    if not engine_output_is_verified(completed.returncode, completed.stdout):
        detail = (completed.stderr or completed.stdout or "no output").strip()
        raise RuntimeError(f"vantio-loader uninstall was not verified: {detail}")
    return scan_known_pins(root)


def standin_record_present(path: Path = STANDIN_RECORD) -> bool | None:
    """True when the fail-closed mount record exists.

    None means the path could not be inspected. A missing file is False.
    """
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        return None
    return True


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
