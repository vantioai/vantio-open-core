"""Remove an installer stage directory without following symlinks."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import NoReturn

from vantio_install.errors import InstallError

_OPEN_DIR = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def remove_stage_nofollow(stage: Path) -> None:
    """Delete a real stage directory. A symlinked stage is refused.

    The stage path is inspected with ``lstat`` and opened with ``O_NOFOLLOW``.
    Child symlinks are unlinked. Their targets are left in place.
    """
    if stage.name in {"", ".", ".."}:
        _refuse("Refusing to remove a stage path that is not a named directory.")
    parent = stage.parent
    try:
        parent_fd = os.open(parent, _OPEN_DIR)
    except FileNotFoundError:
        return
    except OSError:
        _refuse("Refusing to remove a stage whose parent cannot be opened without following a symlink.")
    try:
        try:
            info = os.lstat(stage.name, dir_fd=parent_fd)
        except FileNotFoundError:
            return
        except OSError:
            _refuse("The stage path could not be inspected without following a symlink.")
        if stat.S_ISLNK(info.st_mode):
            _refuse("Refusing to remove a symlinked stage.")
        if not stat.S_ISDIR(info.st_mode):
            _refuse("Refusing to remove a stage that is not a directory.")
        try:
            stage_fd = os.open(stage.name, _OPEN_DIR, dir_fd=parent_fd)
        except OSError:
            _refuse("Refusing to open the stage directory because the no-follow check failed.")
        try:
            _clear_directory(stage_fd)
        finally:
            os.close(stage_fd)
        try:
            os.rmdir(stage.name, dir_fd=parent_fd)
        except OSError:
            _refuse("The stage directory could not be removed without following a symlink.")
    finally:
        os.close(parent_fd)


def _clear_directory(dir_fd: int) -> None:
    for name in os.listdir(dir_fd):
        try:
            info = os.lstat(name, dir_fd=dir_fd)
        except OSError:
            _refuse("A stage entry could not be inspected without following a symlink.")
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            try:
                os.unlink(name, dir_fd=dir_fd)
            except OSError:
                _refuse("A stage entry could not be unlinked without following a symlink.")
            continue
        try:
            child = os.open(name, _OPEN_DIR, dir_fd=dir_fd)
        except OSError:
            _refuse("Refusing to follow a stage entry that is not a plain directory.")
        try:
            _clear_directory(child)
        finally:
            os.close(child)
        try:
            os.rmdir(name, dir_fd=dir_fd)
        except OSError:
            _refuse("A stage subdirectory could not be removed without following a symlink.")


def _refuse(message: str) -> NoReturn:
    raise InstallError(
        message,
        exit_code=4,
        state="FAILED_SAFE",
        failure_class="FAILED_SAFE",
    )
