"""Point-in-time procfs snapshot. Command lines and environ values are not kept."""

from __future__ import annotations

import errno
import os
from dataclasses import dataclass, field
from pathlib import Path

from optics_agent_inventory.catalog import CREDENTIAL_NAMES, extra_hosts_from_env, is_lab_hostname
from optics_agent_inventory.containers import parse_cgroup
from optics_agent_inventory.endpoints import (
    argv_endpoints,
    hosts_catalog_names,
    parse_proc_net,
)
from optics_agent_inventory.endpoints import Observed
from optics_agent_inventory.mcp import parse_mcp, relative_paths

MAX_PROCESSES = 20000
MAX_CMDLINE = 4096
MAX_ENVIRON = 262144
MAX_FD = 512
PF_KTHREAD = 0x00200000
_HIDING = frozenset(
    {
        "hidepid=2",
        "hidepid=invisible",
        "hidepid=noaccess",
        "hidepid=ptraceable",
        "hidepid=4",
    }
)


@dataclass
class ProcessRecord:
    pid: int
    ppid: int = 0
    comm: str = ""
    exe_basename: str | None = None
    binary_missing: bool = False
    status_unreadable: bool = False
    argv_observed: list[Observed] = field(default_factory=list)
    socket_rows: list[tuple[str, str, int]] = field(default_factory=list)
    listens_11434: bool = False
    endpoints_missing: bool = False
    fd_unreadable: bool = False
    environ_unreadable: bool = False
    credentials: frozenset[str] = frozenset()
    cgroup_text: str | None = None
    container_signal: str = "missing"
    container_id: str | None = None
    hostname_label: str | None = None
    hosts_names: dict[str, set[str]] = field(default_factory=dict)
    start_unix: float | None = None
    nspid_count: int = 1
    kernel_flag: bool = False
    is_kernel: bool = False
    mcp_blocked: bool = False
    mcp_rows: list[dict[str, object]] = field(default_factory=list)
    raced: bool = False


@dataclass
class Snapshot:
    processes: dict[int, ProcessRecord]
    proc_unreadable: bool = False
    scan_cap: bool = False
    proc_restricted: bool = False
    scanner_nspid_count: int = 1
    raced_pids: int = 0


def proc_is_restricted(mountinfo: str, euid: int) -> bool:
    if euid == 0:
        return False
    for line in mountinfo.splitlines():
        parts = line.split()
        if len(parts) < 6 or parts[4] != "/proc":
            continue
        options = set(parts[5].split(","))
        if "-" in parts:
            dash = parts.index("-")
            if dash + 3 < len(parts):
                options.update(parts[dash + 3].split(","))
        if options & _HIDING:
            return True
    return False


def read_snapshot(proc_root: Path, mountinfo_path: Path | None, euid: int, extra: tuple[str, ...]) -> Snapshot:
    snap = Snapshot(processes={})
    if mountinfo_path is not None and mountinfo_path.is_file():
        try:
            text = mountinfo_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        snap.proc_restricted = proc_is_restricted(text, euid)
    try:
        entries = list(os.scandir(proc_root))
    except OSError:
        snap.proc_unreadable = True
        return snap
    pids = [entry.name for entry in entries if entry.name.isdigit()]
    if len(pids) > MAX_PROCESSES:
        snap.scan_cap = True
        pids = pids[:MAX_PROCESSES]
    btime = _btime(proc_root)
    clk = os.sysconf("SC_CLK_TCK")
    snap.scanner_nspid_count = _scanner_nspid(proc_root)
    for name in pids:
        record = _read_pid(proc_root, int(name), btime, clk, extra)
        if record is None:
            continue
        if record.raced:
            snap.raced_pids += 1
            continue
        snap.processes[record.pid] = record
    _mark_kernel_threads(snap.processes)
    return snap


def _scanner_nspid(proc_root: Path) -> int:
    path = proc_root / "self" / "status"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 1
    for line in text.splitlines():
        if line.startswith("NSpid:"):
            return max(1, len(line.split()) - 1)
    return 1


def _btime(proc_root: Path) -> int:
    try:
        text = (proc_root / "stat").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    for line in text.splitlines():
        if line.startswith("btime "):
            try:
                return int(line.split()[1])
            except (IndexError, ValueError):
                return 0
    return 0


def _read_pid(proc_root: Path, pid: int, btime: int, clk: int, extra: tuple[str, ...]) -> ProcessRecord | None:
    try:
        dirfd = os.open(os.fspath(proc_root / str(pid)), os.O_RDONLY | os.O_DIRECTORY)
    except FileNotFoundError:
        return None
    except OSError:
        record = ProcessRecord(pid=pid, status_unreadable=True)
        return record
    try:
        start_one = _start_ticks(dirfd)
        record = ProcessRecord(pid=pid)
        status, status_err = _read_at(dirfd, "status", 65536)
        if status_err == errno.EACCES:
            record.status_unreadable = True
            return record
        if status is None:
            record.raced = True
            return record
        _apply_status(record, status.decode("utf-8", errors="replace"))
        stat_blob, stat_err = _read_at(dirfd, "stat", 65536)
        if stat_blob is not None:
            flags, start_ticks, ppid = _parse_stat(stat_blob.decode("utf-8", errors="replace"))
            record.kernel_flag = bool(flags & PF_KTHREAD)
            record.ppid = ppid or record.ppid
            if start_ticks is not None and clk:
                record.start_unix = btime + (start_ticks / clk)
        elif stat_err == errno.EACCES:
            record.status_unreadable = True
            return record
        record.argv_observed = _cmdline(dirfd, extra)
        record.exe_basename, record.binary_missing = _exe_basename(dirfd)
        _cgroup(record, dirfd)
        _environ(record, dirfd)
        _sockets(record, dirfd)
        _hosts(record, dirfd, extra)
        _hostname(record, dirfd)
        _mcp(record, dirfd, extra)
        start_two = _start_ticks(dirfd)
        if start_one is None or start_two is None or start_one != start_two:
            record.raced = True
        return record
    finally:
        os.close(dirfd)


def _apply_status(record: ProcessRecord, text: str) -> None:
    for line in text.splitlines():
        if line.startswith("Name:"):
            record.comm = line.split(":", 1)[1].strip()[:15]
        elif line.startswith("PPid:"):
            try:
                record.ppid = int(line.split(":", 1)[1].strip())
            except ValueError:
                record.ppid = 0
        elif line.startswith("NSpid:"):
            record.nspid_count = max(1, len(line.split()) - 1)


def _parse_stat(text: str) -> tuple[int, int | None, int | None]:
    mark = text.rfind(")")
    if mark < 0:
        return 0, None, None
    fields = text[mark + 2 :].split()
    try:
        ppid = int(fields[1])
        flags = int(fields[6])
        start = int(fields[19])
    except (IndexError, ValueError):
        return 0, None, None
    return flags, start, ppid


def _start_ticks(dirfd: int) -> int | None:
    blob, _err = _read_at(dirfd, "stat", 65536)
    if blob is None:
        return None
    _flags, start, _ppid = _parse_stat(blob.decode("utf-8", errors="replace"))
    return start


def _cmdline(dirfd: int, extra: tuple[str, ...]) -> list[Observed]:
    blob, _err = _read_at(dirfd, "cmdline", MAX_CMDLINE)
    if not blob:
        return []
    tokens = [part.decode("utf-8", errors="replace") for part in blob.split(b"\0") if part]
    observed = argv_endpoints(tokens, extra)
    del tokens
    del blob
    return observed


def _exe_basename(dirfd: int) -> tuple[str | None, bool]:
    try:
        target = os.readlink("exe", dir_fd=dirfd)
    except OSError as err:
        if err.errno in {errno.ENOENT, errno.EACCES, errno.EPERM}:
            return None, True
        return None, True
    if target.endswith(" (deleted)"):
        target = target[: -len(" (deleted)")]
    name = target.rsplit("/", 1)[-1]
    return (name or None), False


def _cgroup(record: ProcessRecord, dirfd: int) -> None:
    blob, err = _read_at(dirfd, "cgroup", 65536)
    if blob is None:
        record.container_signal = "missing"
        record.container_id = None
        return
    record.cgroup_text = blob.decode("utf-8", errors="replace")
    signal, container_id = parse_cgroup(record.cgroup_text)
    record.container_signal = signal
    record.container_id = container_id
    del err


def _environ(record: ProcessRecord, dirfd: int) -> None:
    blob, err = _read_at(dirfd, "environ", MAX_ENVIRON)
    if err in {errno.EACCES, errno.EPERM}:
        record.environ_unreadable = True
        return
    if blob is None:
        return
    found: set[str] = set()
    for item in blob.split(b"\0"):
        key, sep, _value = item.partition(b"=")
        if not sep:
            continue
        try:
            name = key.decode("utf-8")
        except UnicodeError:
            continue
        if name in CREDENTIAL_NAMES:
            found.add(name)
    record.credentials = frozenset(found)
    del blob


def _sockets(record: ProcessRecord, dirfd: int) -> None:
    try:
        fd_dir = os.open("fd", os.O_RDONLY | os.O_DIRECTORY, dir_fd=dirfd)
    except OSError as err:
        record.endpoints_missing = True
        if err.errno in {errno.EACCES, errno.EPERM}:
            record.fd_unreadable = True
        return
    inodes: set[str] = set()
    try:
        names = _list_dir(fd_dir)
    except OSError as err:
        record.endpoints_missing = True
        if err.errno in {errno.EACCES, errno.EPERM}:
            record.fd_unreadable = True
        os.close(fd_dir)
        return
    if len(names) > MAX_FD:
        record.endpoints_missing = True
        os.close(fd_dir)
        return
    try:
        for name in names:
            try:
                link = os.readlink(name, dir_fd=fd_dir)
            except OSError:
                continue
            if link.startswith("socket:[") and link.endswith("]"):
                inodes.add(link[8:-1])
    finally:
        os.close(fd_dir)
    tables: list[tuple[str, str, int, str]] = []
    readable = False
    for net_name in ("net/tcp", "net/tcp6"):
        blob, err = _read_at(dirfd, net_name, 8_000_000, nofollow=False)
        if blob is None:
            if err not in {errno.ENOENT}:
                record.endpoints_missing = True
            continue
        readable = True
        tables.extend(parse_proc_net(blob.decode("utf-8", errors="replace")))
        del blob
    if not readable:
        record.endpoints_missing = True
        return
    for state, ip, port, inode in tables:
        if inode not in inodes:
            continue
        record.socket_rows.append((state, ip, port))
        if state == "0A" and port == 11434:
            record.listens_11434 = True
    del inodes


def _hosts(record: ProcessRecord, dirfd: int, extra: tuple[str, ...]) -> None:
    blob, _err = _read_at(dirfd, "root/etc/hosts", 1_000_000, nofollow=True)
    if not blob:
        return
    record.hosts_names = hosts_catalog_names(blob.decode("utf-8", errors="replace"), extra)
    del blob


def _hostname(record: ProcessRecord, dirfd: int) -> None:
    blob, _err = _read_at(dirfd, "root/etc/hostname", 256, nofollow=True)
    if not blob:
        return
    name = blob.decode("utf-8", errors="replace").strip().splitlines()[0].strip()
    if is_lab_hostname(name):
        record.hostname_label = name
    del blob


def _mcp(record: ProcessRecord, dirfd: int, extra: tuple[str, ...]) -> None:
    bases = []
    for base in ("cwd", "root"):
        try:
            base_fd = os.open(base, os.O_RDONLY | os.O_DIRECTORY, dir_fd=dirfd)
        except OSError as err:
            if err.errno in {errno.EACCES, errno.EPERM}:
                record.mcp_blocked = True
            continue
        bases.append(base_fd)
    try:
        for base_fd in bases:
            for relative in relative_paths():
                blob, err = _read_at(base_fd, relative, 65536, nofollow=True)
                if err == errno.ENOENT or err == errno.ENOTDIR:
                    continue
                if blob is None:
                    record.mcp_blocked = True
                    continue
                if len(blob) > 65536:
                    record.mcp_blocked = True
                    continue
                try:
                    record.mcp_rows.extend(parse_mcp(blob, extra, "config"))
                except ValueError:
                    record.mcp_blocked = True
                del blob
    finally:
        for base_fd in bases:
            os.close(base_fd)


def _list_dir(dirfd: int) -> list[str]:
    duplicate = os.dup(dirfd)
    try:
        return os.listdir(f"/proc/self/fd/{duplicate}")
    finally:
        os.close(duplicate)


def _read_at(dirfd: int, name: str, limit: int, nofollow: bool = True) -> tuple[bytes | None, int | None]:
    flags = os.O_RDONLY
    if nofollow:
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(name, flags, dir_fd=dirfd)
    except OSError as err:
        return None, err.errno
    try:
        return os.read(fd, limit), None
    except OSError as err:
        return None, err.errno
    finally:
        os.close(fd)


def _mark_kernel_threads(processes: dict[int, ProcessRecord]) -> None:
    for record in processes.values():
        if record.pid == 2 or record.kernel_flag or _ancestor_is_kthreadd(record, processes):
            record.is_kernel = True


def _ancestor_is_kthreadd(record: ProcessRecord, processes: dict[int, ProcessRecord]) -> bool:
    seen: set[int] = set()
    pid = record.ppid
    while pid and pid not in seen and len(seen) < 64:
        if pid == 2:
            return True
        seen.add(pid)
        parent = processes.get(pid)
        if parent is None:
            return False
        if parent.kernel_flag:
            return True
        pid = parent.ppid
    return False


def load_extra(env: dict[str, str] | None = None) -> tuple[str, ...]:
    source = os.environ if env is None else env
    return extra_hosts_from_env(source.get("VANTIO_EXTRA_LLM_HOSTS"))
