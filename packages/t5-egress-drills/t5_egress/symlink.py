"""openat2 RESOLVE_BENEATH. No second open without those flags."""

from __future__ import annotations

import ctypes
import errno
import os
import stat

from t5_egress.decision import Decision, allow, deny_eval

SYS_OPENAT2 = 437
RESOLVE_NO_XDEV = 0x01
RESOLVE_NO_MAGICLINKS = 0x02
RESOLVE_BENEATH = 0x08
RESOLVE_MASK = RESOLVE_NO_XDEV | RESOLVE_NO_MAGICLINKS | RESOLVE_BENEATH

_ERRNO = {
    errno.EXDEV: "symlink_escape",
    errno.ELOOP: "symlink_escape",
    errno.EAGAIN: "symlink_race_unresolved",
    errno.ENOENT: "path_absent",
    errno.EACCES: "open_denied",
    errno.EPERM: "open_denied",
    errno.ENOTDIR: "path_not_directory",
    errno.ENOSYS: "openat2_unavailable",
    errno.EINVAL: "openat2_rejected",
}


class OpenHow(ctypes.Structure):
    _fields_ = (
        ("flags", ctypes.c_uint64),
        ("mode", ctypes.c_uint64),
        ("resolve", ctypes.c_uint64),
    )


def resolve_mask() -> int:
    return RESOLVE_MASK


def open_workload_root(path: str) -> int | Decision:
    flags = os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        fd = os.open(path, flags)
    except OSError:
        return deny_eval("symlink_root")
    try:
        info = os.fstat(fd)
    except OSError:
        os.close(fd)
        return deny_eval("symlink_root")
    if not stat.S_ISDIR(info.st_mode):
        os.close(fd)
        return deny_eval("symlink_root")
    return fd


def _relative(path: str) -> bool:
    if not path or "\x00" in path or path.startswith("/"):
        return False
    return True


def open_beneath(root_fd: int, relative: str) -> int | Decision:
    if not _relative(relative):
        return deny_eval("path_not_relative")
    how = OpenHow(os.O_RDONLY | os.O_CLOEXEC, 0, RESOLVE_MASK)
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    fd = libc.syscall(
        ctypes.c_long(SYS_OPENAT2),
        ctypes.c_int(root_fd),
        ctypes.c_char_p(relative.encode("utf-8")),
        ctypes.byref(how),
        ctypes.c_size_t(ctypes.sizeof(how)),
    )
    if fd >= 0:
        return int(fd)
    err = ctypes.get_errno()
    return deny_eval(_ERRNO.get(err, "open_failed"))


def read_beneath(root_fd: int, relative: str, limit: int = 64) -> tuple[Decision, bytes]:
    opened = open_beneath(root_fd, relative)
    if isinstance(opened, Decision):
        return opened, b""
    try:
        return allow(), os.read(opened, limit)
    finally:
        os.close(opened)
