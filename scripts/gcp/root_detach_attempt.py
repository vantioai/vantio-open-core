#!/usr/bin/env python3
"""Try root detach, link detach, and bpffs unlink of Vantio objects.

The caller is a process other than the loader. A syscall that returns 0 is
recorded as result=ok. This file does not undo that detach. Tip 864289cb
lets uid 0 detach, so the phase that reads these lines fails. That failure
is the result. live_enforcement is not set here.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from pathlib import Path

# linux/bpf.h command numbers. x86_64 syscall 321.
BPF_OBJ_GET = 7
BPF_PROG_DETACH = 9
BPF_PROG_QUERY = 16
BPF_PROG_GET_FD_BY_ID = 13
BPF_OBJ_GET_INFO_BY_FD = 15
BPF_LINK_DETACH = 34
BPF_CGROUP_INET_EGRESS = 1
REFUSED = frozenset({1, 13})  # EPERM, EACCES


def classify(errno: int, *, issued: bool) -> str:
    """Map one attempt to refused, ok, other, or skipped."""
    if not issued:
        return "skipped"
    if errno == 0:
        return "ok"
    if errno in REFUSED:
        return "refused"
    return "other"


def _libc() -> ctypes.CDLL:
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    return libc


def _bpf(cmd: int, attr: ctypes.Structure) -> tuple[int, int]:
    """Return (return_code, errno). errno is 0 when the call returns >= 0."""
    libc = _libc()
    ctypes.set_errno(0)
    rc = libc.syscall(321, cmd, ctypes.byref(attr), ctypes.sizeof(attr))
    if rc >= 0:
        return int(rc), 0
    return int(rc), ctypes.get_errno()


class _ObjGet(ctypes.Structure):
    _fields_ = [
        ("pathname", ctypes.c_uint64),
        ("bpf_fd", ctypes.c_uint32),
        ("file_flags", ctypes.c_uint32),
    ]


class _Detach(ctypes.Structure):
    _fields_ = [
        ("target_fd", ctypes.c_uint32),
        ("attach_bpf_fd", ctypes.c_uint32),
        ("attach_type", ctypes.c_uint32),
        ("attach_flags", ctypes.c_uint32),
    ]


class _LinkDetach(ctypes.Structure):
    _fields_ = [("link_fd", ctypes.c_uint32)]


class _GetFd(ctypes.Structure):
    _fields_ = [
        ("id", ctypes.c_uint32),
        ("next_id", ctypes.c_uint32),
        ("open_flags", ctypes.c_uint32),
    ]


class _Info(ctypes.Structure):
    _fields_ = [
        ("bpf_fd", ctypes.c_uint32),
        ("info_len", ctypes.c_uint32),
        ("info", ctypes.c_uint64),
    ]


class _Query(ctypes.Structure):
    _fields_ = [
        ("target_fd", ctypes.c_uint32),
        ("attach_type", ctypes.c_uint32),
        ("query_flags", ctypes.c_uint32),
        ("attach_flags", ctypes.c_uint32),
        ("prog_ids", ctypes.c_uint64),
        ("prog_cnt", ctypes.c_uint32),
    ]


def _obj_get(path: str) -> tuple[int, int]:
    raw = ctypes.create_string_buffer(path.encode())
    attr = _ObjGet(pathname=ctypes.addressof(raw), bpf_fd=0, file_flags=os.O_RDONLY)
    return _bpf(BPF_OBJ_GET, attr)


def _kind(fd: int) -> str:
    info = ctypes.create_string_buffer(256)
    attr = _Info(bpf_fd=fd, info_len=len(info), info=ctypes.addressof(info))
    rc, _err = _bpf(BPF_OBJ_GET_INFO_BY_FD, attr)
    if rc == 0:
        return "prog"
    # A link and a map both fail a program-info read. Probe link detach shape
    # by asking for a short link info; a program fd already returned above.
    return "other"


def _query_ids(cgroup_fd: int) -> list[int]:
    attr = _Query(
        target_fd=cgroup_fd,
        attach_type=BPF_CGROUP_INET_EGRESS,
        query_flags=0,
        attach_flags=0,
        prog_ids=0,
        prog_cnt=0,
    )
    _rc, _err = _bpf(BPF_PROG_QUERY, attr)
    # The kernel writes the attached count even when the buffer was too small.
    if attr.prog_cnt == 0:
        return []
    ids = (ctypes.c_uint32 * attr.prog_cnt)()
    attr.prog_ids = ctypes.addressof(ids)
    attr.prog_cnt = len(ids)
    rc, _err = _bpf(BPF_PROG_QUERY, attr)
    if rc < 0:
        return []
    return [int(item) for item in ids[: attr.prog_cnt]]


def _line(kind: str, target: str, errno: int, *, issued: bool) -> str:
    result = classify(errno, issued=issued)
    return f"root_detach_attempt={kind} target={target} result={result} errno={errno}"


def vantio_pins(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    found: list[Path] = []
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if "vantio" in path.name or "vantio" in str(path):
            found.append(path)
    return sorted(found)


def attempt(cgroup: str, bpffs: str, loader_pid: int) -> list[str]:
    """Issue the three attempts and report what remains. Does not undo a detach."""
    lines: list[str] = []
    actor = "outside_loader" if os.getpid() != loader_pid and os.getuid() == 0 else "loader"
    lines.append(f"root_detach_actor={actor}")
    pin_root = Path(bpffs)
    pins = vantio_pins(pin_root)
    before = [str(path) for path in pins]
    cgroup_fd = -1
    try:
        cgroup_fd = os.open(cgroup, os.O_RDONLY)
    except OSError as exc:
        lines.append(_line("prog_detach", "cgroup_egress", exc.errno or 0, issued=True))
    else:
        ids = _query_ids(cgroup_fd)
        if not ids:
            lines.append(_line("prog_detach", "cgroup_egress", 0, issued=False))
        for prog_id in ids:
            got, err = _bpf(BPF_PROG_GET_FD_BY_ID, _GetFd(id=prog_id, next_id=0, open_flags=0))
            if got < 0:
                lines.append(_line("prog_detach", f"id-{prog_id}", err, issued=True))
                continue
            detach = _Detach(
                target_fd=cgroup_fd,
                attach_bpf_fd=got,
                attach_type=BPF_CGROUP_INET_EGRESS,
                attach_flags=0,
            )
            _rc, detach_err = _bpf(BPF_PROG_DETACH, detach)
            lines.append(_line("prog_detach", f"id-{prog_id}", detach_err, issued=True))
            os.close(got)
        os.close(cgroup_fd)
    link_issued = False
    for path in pins:
        got, err = _obj_get(str(path))
        if got < 0:
            continue
        if _kind(got) == "other":
            # OBJ_GET succeeded and program-info did not. Treat it as a link
            # candidate. EINVAL stays result=other and fails the phase.
            _rc, detach_err = _bpf(BPF_LINK_DETACH, _LinkDetach(link_fd=got))
            lines.append(_line("link_detach", path.name, detach_err, issued=True))
            link_issued = True
        os.close(got)
    if not link_issued:
        lines.append(_line("link_detach", "none", 0, issued=False))
    if not pins:
        lines.append(_line("unlink", "none", 0, issued=False))
    for path in pins:
        try:
            path.unlink()
            lines.append(_line("unlink", path.name, 0, issued=True))
        except OSError as exc:
            lines.append(_line("unlink", path.name, exc.errno or 0, issued=True))
    after_ids: list[int] = []
    try:
        again = os.open(cgroup, os.O_RDONLY)
    except OSError:
        again = -1
    if again >= 0:
        after_ids = _query_ids(again)
        os.close(again)
    programs_remain = "yes" if after_ids else "no"
    pins_remain = "yes" if before and all(Path(path).exists() for path in before) else "no"
    lines.append(f"root_detach_programs_remain={programs_remain}")
    lines.append(f"root_detach_pins_remain={pins_remain}")
    return lines


def _prog_id_named(prefix: bytes) -> int:
    """Program id whose name starts with prefix, or 0 when none is visible."""
    start = 0
    for _ in range(256):
        attr = _GetFd(id=start, next_id=0, open_flags=0)
        rc, _err = _bpf(11, attr)
        if rc != 0 or attr.next_id == 0:
            return 0
        start = int(attr.next_id)
        got, err = _bpf(BPF_PROG_GET_FD_BY_ID, _GetFd(id=start, next_id=0, open_flags=0))
        if got < 0 or err:
            continue
        info = ctypes.create_string_buffer(256)
        info_attr = _Info()
        info_attr.bpf_fd = got
        info_attr.info_len = 256
        info_attr.info = ctypes.addressof(info)
        _bpf(BPF_OBJ_GET_INFO_BY_FD, info_attr)
        os.close(got)
        name = info.raw[64:80]
        if name.startswith(prefix):
            return start
    return 0


def canary_lines(loader: str, cgroup: str, pin: str) -> list[str]:
    """Run the loader's root canaries. Each child exits with the errno."""
    prog_id = _prog_id_named(b"cgroup_skb")
    commands = [
        (
            "prog_detach",
            f"id-{prog_id}",
            [loader, "--root-detach-canary", cgroup, "--root-detach-type", "1", "--root-detach-prog-id", str(prog_id)],
        ),
        ("link_detach", "vantio_link", [loader, "--root-link-canary"]),
        ("map_update", pin, [loader, "--root-map-canary", pin]),
        ("unlink", pin, [loader, "--root-unlink-canary", pin]),
        ("rename", pin, [loader, "--root-rename-canary", pin]),
    ]
    lines = ["root_detach_actor=outside_loader"]
    for kind, target, cmd in commands:
        done = subprocess.run(cmd, check=False)
        code = done.returncode
        errno = code if code is not None and code > 0 else (0 if code == 0 else 128)
        result = "ok" if errno == 0 else classify(errno, issued=True)
        lines.append(f"root_detach_attempt={kind} target={target} result={result} errno={errno}")
    return lines


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) == 3 and Path(args[0]).is_file() and os.access(args[0], os.X_OK):
        for line in canary_lines(args[0], args[1], args[2]):
            print(line)
        return 0
    if len(args) != 3:
        print("usage: root_detach_attempt.py LOADER CGROUP PIN", file=sys.stderr)
        return 2
    cgroup, bpffs, raw_pid = args
    try:
        loader_pid = int(raw_pid)
    except ValueError:
        return 2
    for line in attempt(cgroup, bpffs, loader_pid):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
