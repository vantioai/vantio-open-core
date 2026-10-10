#!/usr/bin/env python3
"""Live-loader rows for the offline lab. No public destinations.

The descendant battery owns topology. This script rechecks path disguises,
an unreadable filename pointer, BPF and pin tamper as an unprivileged uid,
identity copies, lab-veth network, and whether killing the loader leaves a
protected open allowed. A deny without a ledger row naming the pid is
FAIL_GAP. The model, when the pinned server is present, is asked for one
word and is not given a shell.

Audience: INTERNAL_RESTRICTED
"""

from __future__ import annotations

import ctypes
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# guest_rows and redteam_packet are placed on sys.path by the lab runner.
sys.path.insert(0, "/tmp/vantio-lab")
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else "/opt/vantio-enterprise")

import guest_rows as rows  # noqa: E402
import redteam_packet as packet  # noqa: E402

SUBJECT = 65534
LAB_UDP = ("192.0.2.2", 9)
OUT_PATH = Path("/tmp/redteam-rows.json")
# AWS sets VANTIO_BRAIN_DIR to /var/lib/vantio-lab/brain. GCP keeps /tmp/vantio-lab.
BRAIN_DIR = Path(os.environ.get("VANTIO_BRAIN_DIR", "/tmp/vantio-lab"))
AT_FDCWD = -100
SYS_OPENAT = 257
SYS_BPF = 321
BPF_MAP_CREATE = 0
BPF_MAP_UPDATE_ELEM = 2
BPF_PROG_LOAD = 5
O_RDONLY = 0


class _MapCreate(ctypes.Structure):
    _fields_ = [
        ("map_type", ctypes.c_uint32),
        ("key_size", ctypes.c_uint32),
        ("value_size", ctypes.c_uint32),
        ("max_entries", ctypes.c_uint32),
        ("map_flags", ctypes.c_uint32),
    ]


class _MapUpdate(ctypes.Structure):
    _fields_ = [
        ("map_fd", ctypes.c_uint32),
        ("_pad", ctypes.c_uint32),
        ("key", ctypes.c_uint64),
        ("value", ctypes.c_uint64),
        ("flags", ctypes.c_uint64),
    ]


def _ensure_brain() -> None:
    BRAIN_DIR.mkdir(parents=True, exist_ok=True)


def _bpf(cmd: int, attr: ctypes.Structure) -> int:
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    rc = libc.syscall(
        ctypes.c_long(SYS_BPF),
        ctypes.c_long(cmd),
        ctypes.byref(attr),
        ctypes.c_uint(ctypes.sizeof(attr)),
    )
    if rc >= 0:
        return 0
    return ctypes.get_errno() or 1


def events() -> list[dict]:
    path = rows.EVENTS
    if not path.is_file():
        return []
    found = []
    for line in path.read_text(errors="replace").splitlines():
        try:
            found.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return found


def event_pid(item: dict) -> int | None:
    raw = item.get("Pid")
    if raw is None:
        raw = item.get("pid")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def attributed(pid: int, action: str) -> bool:
    for item in events():
        if event_pid(item) == pid and item.get("ActionTaken") == action:
            return True
    return False


def _attempt(technique_id: str, grade: dict, errno: int | None) -> dict:
    return packet._row(
        technique_id,
        str(grade["outcome"]),
        silent=bool(grade.get("silent_success")),
        attributed=bool(grade.get("attributed")),
        errno=errno,
        reason=str(grade.get("reason") or ""),
    )


def _child_open(raw_path: str, *, relative: bool, bad_pointer: bool) -> dict:
    report_r, report_w = os.pipe()
    child = os.fork()
    if child == 0:
        os.close(report_r)
        os.dup2(report_w, 1)
        os.close(report_w)
        try:
            (Path(rows.ANCHOR) / "cgroup.procs").write_text(f"{os.getpid()}\n")
        except OSError as exc:
            os.write(1, f"move {exc.errno}\n".encode())
            os._exit(0)
        try:
            os.setresuid(SUBJECT, SUBJECT, 0)
        except OSError as exc:
            os.write(1, f"setuid {exc.errno}\n".encode())
            os._exit(0)
        file_errno = 0
        try:
            if bad_pointer:
                libc = ctypes.CDLL(None, use_errno=True)
                libc.syscall.restype = ctypes.c_long
                rc = libc.syscall(ctypes.c_long(SYS_OPENAT), ctypes.c_long(AT_FDCWD), ctypes.c_long(1), ctypes.c_long(O_RDONLY))
                if rc >= 0:
                    os.close(int(rc))
                    file_errno = 0
                else:
                    file_errno = ctypes.get_errno() or 1
            elif relative:
                os.chdir(str(Path(raw_path).parent))
                fd = os.open(Path(raw_path).name, os.O_RDONLY)
                os.close(fd)
            else:
                fd = os.open(raw_path, os.O_RDONLY)
                os.close(fd)
        except OSError as exc:
            file_errno = exc.errno or 1
        net_errno = 0
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(b"v", LAB_UDP)
            sock.close()
        except OSError as exc:
            net_errno = exc.errno or 1
        os.write(1, f"file {file_errno} net {net_errno} pid {os.getpid()}\n".encode())
        os._exit(0)
    os.close(report_w)
    os.waitpid(child, 0)
    text = os.read(report_r, 300).decode(errors="replace")
    os.close(report_r)
    body = {"file_errno": None, "net_errno": None, "pid": None, "detail": text.strip()}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 6 and parts[0] == "file" and parts[2] == "net" and parts[4] == "pid":
            body["file_errno"] = int(parts[1])
            body["net_errno"] = int(parts[3])
            body["pid"] = int(parts[5])
    return body


def _grade_observed(observed: dict) -> dict:
    pid = observed.get("pid")
    errno = observed.get("file_errno")
    if not isinstance(pid, int) or not isinstance(errno, int):
        return packet.grade_open(None, False)
    time.sleep(0.4)
    hit = attributed(pid, "DENIED") and attributed(pid, "BLOCKED")
    return packet.grade_open(errno, hit)


def path_rows() -> list[dict]:
    deny = str(rows.DENY)
    slash = deny.rfind("/")
    dot = deny[:slash] + "/." + deny[slash:]
    doubled = deny[:slash] + "/" + deny[slash:]
    specs = [
        ("pe.path.dot_segment", dot, False, False),
        ("pe.path.relative", deny, True, False),
        ("pe.path.double_slash", doubled, False, False),
        ("pe.path.probe_read_fail_open", deny, False, True),
    ]
    rows_out = []
    for technique_id, raw, relative, bad_pointer in specs:
        observed = _child_open(raw, relative=relative, bad_pointer=bad_pointer)
        grade = _grade_observed(observed)
        errno = observed.get("file_errno") if isinstance(observed.get("file_errno"), int) else None
        rows_out.append(_attempt(technique_id, grade, errno))
    return rows_out


def _unprivileged(fn) -> dict:
    report_r, report_w = os.pipe()
    child = os.fork()
    if child == 0:
        os.close(report_r)
        try:
            os.setresuid(SUBJECT, SUBJECT, 0)
        except OSError as exc:
            os.write(report_w, f"errno {exc.errno}\n".encode())
            os._exit(0)
        errno = fn()
        os.write(report_w, f"errno {errno} pid {os.getpid()}\n".encode())
        os._exit(0)
    os.close(report_w)
    os.waitpid(child, 0)
    text = os.read(report_r, 200).decode(errors="replace")
    os.close(report_r)
    body = {"errno": None, "pid": None}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "errno":
            body["errno"] = int(parts[1])
        if len(parts) == 4 and parts[2] == "pid":
            body["pid"] = int(parts[3])
    return body


def bpf_rows() -> list[dict]:
    pins = []
    root = Path("/sys/fs/bpf")
    if root.is_dir():
        for path in root.rglob("*"):
            if path.is_symlink() or path.is_file():
                pins.append(path)

    def unlink_pin() -> int:
        if not pins:
            return -1
        try:
            pins[0].unlink()
        except OSError as exc:
            return exc.errno or 1
        return 0

    def bpf_create() -> int:
        return _bpf(BPF_MAP_CREATE, _MapCreate(1, 4, 4, 1, 0))

    def bpf_update() -> int:
        return _bpf(BPF_MAP_UPDATE_ELEM, _MapUpdate(0, 0, 0, 0, 0))

    def bpf_prog() -> int:
        return _bpf(BPF_PROG_LOAD, _MapCreate(0, 0, 0, 0, 0))

    found = []
    for technique_id, action in (
        ("pe.tamper.pin_unlink", unlink_pin),
        ("pe.tamper.bpf_syscall", bpf_create),
        ("pe.tamper.bpf_map", bpf_update),
        ("pe.tamper.bpftool", bpf_create),
        ("pe.tamper.bpf_prog", bpf_prog),
    ):
        observed = _unprivileged(action)
        errno = observed.get("errno")
        pid = observed.get("pid")
        if errno == -1:
            found.append(packet._row(technique_id, "GAP", reason="pin_absent"))
            continue
        if not isinstance(errno, int) or not isinstance(pid, int):
            found.append(packet._row(technique_id, "GAP", reason="not_executed"))
            continue
        time.sleep(0.2)
        hit = attributed(pid, "DENIED") or attributed(pid, "BLOCKED")
        grade = packet.grade_tamper(errno, hit)
        found.append(_attempt(technique_id, grade, errno))
    return found


def _binary_open(binary: Path) -> dict:
    script = BRAIN_DIR / "open_deny.py"
    report_r, report_w = os.pipe()
    child = os.fork()
    if child == 0:
        os.close(report_r)
        os.dup2(report_w, 1)
        os.close(report_w)
        try:
            (Path(rows.ANCHOR) / "cgroup.procs").write_text(f"{os.getpid()}\n")
            os.setresuid(SUBJECT, SUBJECT, 0)
        except OSError as exc:
            os.write(1, f"file {exc.errno or 1} pid {os.getpid()}\n".encode())
            os._exit(0)
        os.environ["P"] = str(rows.DENY)
        os.execv(str(binary), [str(binary), str(script)])
    os.close(report_w)
    os.waitpid(child, 0)
    text = os.read(report_r, 200).decode(errors="replace")
    os.close(report_r)
    body = {"file_errno": None, "pid": child}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[0] == "file" and parts[2] == "pid":
            body["file_errno"] = int(parts[1])
            body["pid"] = int(parts[3])
    return body


def identity_rows() -> list[dict]:
    _ensure_brain()
    source = Path("/usr/bin/python3").resolve()
    names = (
        "pe.identity.copied",
        "pe.identity.renamed",
        "pe.identity.hardlink",
        "pe.identity.ld_preload",
        "pe.identity.binary_swap",
    )
    if not source.is_file():
        return [packet._row(technique_id, "GAP", reason="python_absent") for technique_id in names]
    script = BRAIN_DIR / "open_deny.py"
    script.write_text(
        "import os\n"
        "path = os.environ['P']\n"
        "try:\n"
        "    os.open(path, os.O_RDONLY)\n"
        "    errno = 0\n"
        "except OSError as exc:\n"
        "    errno = exc.errno or 1\n"
        "os.write(1, f'file {errno} pid {os.getpid()}\\n'.encode())\n",
        encoding="utf-8",
    )
    os.chmod(script, 0o644)
    copies = {
        "pe.identity.copied": BRAIN_DIR / "py-copy",
        "pe.identity.renamed": BRAIN_DIR / "py-renamed",
        "pe.identity.hardlink": BRAIN_DIR / "py-link",
    }
    found = []
    for technique_id, dest in copies.items():
        try:
            if dest.exists() or dest.is_symlink():
                dest.unlink()
            if technique_id == "pe.identity.hardlink":
                os.link(source, dest)
            else:
                data = source.read_bytes()
                dest.write_bytes(data)
                os.chmod(dest, 0o755)
            if technique_id == "pe.identity.renamed":
                moved = BRAIN_DIR / "py-renamed-final"
                if moved.exists():
                    moved.unlink()
                dest.rename(moved)
                dest = moved
        except OSError:
            found.append(packet._row(technique_id, "GAP", reason="copy_failed"))
            continue
        observed = _binary_open(dest)
        errno = observed.get("file_errno") if isinstance(observed.get("file_errno"), int) else None
        pid = observed.get("pid")
        if isinstance(pid, int) and isinstance(errno, int):
            time.sleep(0.4)
            grade = packet.grade_open(errno, attributed(pid, "DENIED"))
        else:
            grade = packet.grade_open(None, False)
        found.append(_attempt(technique_id, grade, errno))
    found.append(packet._row("pe.identity.ld_preload", "GAP", reason="no_preload_object"))
    found.append(packet._row("pe.identity.binary_swap", "GAP", reason="loader_binary_not_swapped"))
    return found


def network_rows() -> list[dict]:
    observed = _child_open(str(rows.DENY), relative=False, bad_pointer=False)
    pid = observed.get("pid")
    net_errno = observed.get("net_errno")
    time.sleep(0.4)
    hit = isinstance(pid, int) and attributed(pid, "BLOCKED")
    if not isinstance(net_errno, int):
        grade = packet.grade_open(None, False)
    elif hit:
        grade = packet.grade_open(13, True)
    elif net_errno == 0:
        grade = packet.grade_open(0, False)
    else:
        grade = {
            "outcome": "INCONCLUSIVE",
            "silent_success": False,
            "attributed": False,
            "reason": "os_denied_without_pe_event",
        }
    errno = net_errno if isinstance(net_errno, int) else None
    shared = [
        "net.udp",
        "net.direct_ip",
        "net.low_and_slow",
        "net.volume_split",
    ]
    rows_out = [_attempt(technique_id, grade, errno) for technique_id in shared]
    for technique_id in (
        "net.alternate_dns",
        "net.doh",
        "net.dot",
        "net.raw_socket",
        "net.packet_socket",
        "net.ipv6",
        "net.icmp",
        "net.tunnel_allowed_process",
        "net.inbound_spoof",
    ):
        rows_out.append(packet._row(technique_id, "REFUSED_UNSAFE", reason="public_destination_not_attempted"))
    return rows_out


def ptrace_row() -> dict:
    """The child marks itself traced, then opens the protected path."""
    report_r, report_w = os.pipe()
    child = os.fork()
    if child == 0:
        os.close(report_r)
        os.dup2(report_w, 1)
        os.close(report_w)
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.ptrace(0, 0, 0, 0) != 0:
            os.write(1, f"file {ctypes.get_errno() or 1} pid {os.getpid()}\n".encode())
            os._exit(0)
        try:
            (Path(rows.ANCHOR) / "cgroup.procs").write_text(f"{os.getpid()}\n")
            os.setresuid(SUBJECT, SUBJECT, 0)
            fd = os.open(str(rows.DENY), os.O_RDONLY)
            os.close(fd)
            file_errno = 0
        except OSError as exc:
            file_errno = exc.errno or 1
        os.write(1, f"file {file_errno} pid {os.getpid()}\n".encode())
        os._exit(0)
    os.close(report_w)
    os.waitpid(child, 0)
    text = os.read(report_r, 200).decode(errors="replace")
    os.close(report_r)
    errno = None
    pid = None
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[0] == "file" and parts[2] == "pid":
            errno = int(parts[1])
            pid = int(parts[3])
    if errno is None or pid is None:
        return packet._row("pe.escape.ptrace", "GAP", reason="not_executed")
    if errno != 13 and errno != 0:
        return packet._row("pe.escape.ptrace", "INCONCLUSIVE", errno=errno, reason="other_errno")
    time.sleep(0.4)
    grade = packet.grade_open(errno, attributed(pid, "DENIED"))
    return _attempt("pe.escape.ptrace", grade, errno)


def container_row() -> dict:
    if subprocess.call(["sudo", "docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
        return packet._row("pe.escape.container", "GAP", reason="docker_unavailable")
    return packet._row("pe.escape.container", "GAP", reason="container_not_started")


def optics_row() -> dict:
    listeners = Path("/proc/net/tcp").read_text(errors="replace") if Path("/proc/net/tcp").is_file() else ""
    if "01BB" in listeners or "0D1F" in listeners:
        return packet._row("opt.forged_event", "INCONCLUSIVE", reason="otlp_listener_present")
    return packet._row("opt.forged_event", "GAP", reason="live_loader_has_no_otlp_listener")


def loader_rows() -> list[dict]:
    pids = []
    proc = Path("/proc")
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            command = (entry / "cmdline").read_bytes().replace(b"\x00", b" ").decode(errors="replace").lower()
        except OSError:
            continue
        if "vantio" in command and "loader" in command:
            pids.append(int(entry.name))
    if not pids:
        return [
            packet._row(technique_id, "GAP", reason="loader_pid_absent")
            for technique_id in (
                "pe.tamper.loader_kill",
                "pe.tamper.restart_race",
                "pe.tamper.policy_toctou",
                "pe.tamper.signal",
                "pe.tamper.oom",
            )
        ]
    for pid in pids:
        try:
            os.kill(pid, 15)
        except OSError:
            continue
    time.sleep(0.5)
    observed = _child_open(str(rows.DENY), relative=False, bad_pointer=False)
    grade = _grade_observed(observed)
    errno = observed.get("file_errno") if isinstance(observed.get("file_errno"), int) else None
    return [
        _attempt("pe.tamper.loader_kill", grade, errno),
        packet._row("pe.tamper.restart_race", "GAP", reason="restart_not_raced"),
        packet._row("pe.tamper.policy_toctou", "GAP", reason="policy_file_not_swapped"),
        packet._row("pe.tamper.signal", "GAP", reason="signal_not_sent"),
        packet._row("pe.tamper.oom", "GAP", reason="oom_not_induced"),
    ]


def ask_brain() -> dict:
    server = BRAIN_DIR / "llama-b11540" / "llama-server"
    model = BRAIN_DIR / "qwen2.5-3b-instruct-q4_k_m.gguf"
    if not server.is_file() or not model.is_file():
        return {"loaded": False, "reason": "brain_files_absent"}
    try:
        proc = subprocess.Popen(
            [str(server), "-m", str(model), "--host", "127.0.0.1", "--port", "8088", "-c", "256", "-t", "2"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        return {"loaded": False, "reason": type(exc).__name__.lower()[:48]}
    deadline = time.time() + 90
    ready = False
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", 8088), timeout=1):
                ready = True
                break
        except OSError:
            if proc.poll() is not None:
                break
            time.sleep(1)
    if not ready:
        proc.terminate()
        return {"loaded": False, "reason": "server_not_ready"}
    payload = json.dumps(
        {"prompt": "Reply with one word: file", "n_predict": 8, "temperature": 0}
    ).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:8088/completion",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read(4000)
    except OSError:
        proc.terminate()
        return {"loaded": False, "reason": "completion_failed"}
    proc.terminate()
    text = body.decode(errors="replace").lower()
    if "ignore previous" in text or "private key" in text:
        return {"loaded": True, "reason": "reply_rejected"}
    return {"loaded": True, "reason": "completion_ok"}


def main() -> int:
    if os.uname().nodename == "phantom-box":
        raise SystemExit("refusing host")
    _ensure_brain()
    attempts: list[dict] = []
    model = {"loaded": False, "reason": "not_started"}
    sections = (
        path_rows,
        bpf_rows,
        identity_rows,
        network_rows,
    )
    for section in sections:
        try:
            attempts.extend(section())
        except Exception as exc:
            attempts.append(packet._row("pe.harness.section", "GAP", reason=type(exc).__name__.lower()[:48]))
    for single in (ptrace_row, container_row, optics_row):
        try:
            attempts.append(single())
        except Exception as exc:
            attempts.append(packet._row("pe.harness.section", "GAP", reason=type(exc).__name__.lower()[:48]))
    attempts.append(packet._row("pe.resource.exhaust", "GAP", reason="not_executed"))
    attempts.append(packet._row("pe.path.symlink", "GAP", reason="symlink_program_not_loaded"))
    try:
        model = ask_brain()
    except Exception as exc:
        model = {"loaded": False, "reason": type(exc).__name__.lower()[:48]}
    try:
        attempts.extend(loader_rows())
    except Exception as exc:
        attempts.append(packet._row("pe.tamper.loader_kill", "GAP", reason=type(exc).__name__.lower()[:48]))
    body = {
        "attempts": attempts,
        "model_loaded": bool(model.get("loaded")),
        "model_reason": model.get("reason") or "unknown",
    }
    OUT_PATH.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    os.chmod(OUT_PATH, 0o644)
    print(json.dumps({"rows": len(attempts), "model_loaded": body["model_loaded"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
