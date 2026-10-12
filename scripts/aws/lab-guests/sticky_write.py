"""Replace a file without O_CREAT on an inode another uid already owns.

Ubuntu sets fs.protected_regular to 2. /tmp is sticky and world-writable, and
its owner is root. open(O_CREAT) of an existing file owned by a different uid
returns EACCES there. Root is not exempt: the check is the file owner, the
directory owner, and the caller's fsuid. Path.write_text uses that open, so a
root trap rewriting a file the lab user created in /tmp fails after the
uninstall has already verified.

O_WRONLY|O_TRUNC does not take that check. Root's DAC override lets the
truncate succeed. A brand-new inode (O_EXCL) is also allowed.
"""

from __future__ import annotations

import errno
import os
from pathlib import Path


def write_replacing(path: Path, text: str) -> None:
    """Write text to path. An existing foreign inode is truncated, not recreated."""
    data = text.encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        try:
            fd = os.open(path, os.O_WRONLY | os.O_TRUNC)
        except OSError as exc:
            if exc.errno not in (errno.EACCES, errno.EPERM):
                raise
        else:
            try:
                _write_all(fd, data)
            finally:
                os.close(fd)
            return
        os.unlink(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        _write_all(fd, data)
    finally:
        os.close(fd)


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        wrote = os.write(fd, view)
        if wrote <= 0:
            raise OSError(errno.EIO, "short write")
        view = view[wrote:]
