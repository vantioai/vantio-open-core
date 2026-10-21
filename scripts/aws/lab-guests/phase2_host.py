#!/usr/bin/env python3
"""Clean-host phase batteries on the working seal.

The runner has already loaded the seal and extracted the contract. This
script starts the loader the same way the descendant battery does, measures
one phase, and writes /var/lib/vantio-lab/enterprise-pe-rows.json. It does not fetch.
The upgrade battery loads the public pin tar and the working seal tar that
the runner already copied, and it does not treat one of those tars as the other.

Audience: INTERNAL_RESTRICTED
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = Path(sys.argv[1] if len(sys.argv) > 1 else "/opt/vantio-enterprise")
MODE = sys.argv[2] if len(sys.argv) > 2 else ""
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(STAGE))

import baseline_diag  # noqa: E402
import guest_rows as rows  # noqa: E402
import phase2_grade as grade  # noqa: E402
from vantio_enterprise_protocol.control import ControlPlane  # noqa: E402
from vantio_enterprise_protocol.host_adapter import LocalHostVerifier  # noqa: E402
from vantio_enterprise_protocol.pe_adapter import (  # noqa: E402
    PeHostAdapter,
    revoke_deny_event_links_digest,
)
from vantio_enterprise_protocol.trust import load_packaged_test_trust  # noqa: E402

OUT_PATH = Path("/var/lib/vantio-lab/enterprise-pe-rows.json")
SUBJECT = 65534
ALLOW_HOST = "10.254.254.10"
ALLOW_PORT = 4880
_LISTENER_SRC = """\
import os
import socket
host = os.environ["VANTIO_EGRESS_HOST"]
port = int(os.environ["VANTIO_EGRESS_PORT"])
server = socket.socket()
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((host, port))
server.listen(64)
server.settimeout(1)
while True:
    try:
        client, _addr = server.accept()
    except (TimeoutError, OSError):
        continue
    client.close()
"""
_ENDPOINT_READY = False
_ENDPOINT: tuple[str, int] | None = None


def publish(body: dict) -> None:
    text = json.dumps(body, indent=2) + "\n"
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(text, encoding="utf-8")
    try:
        os.chmod(OUT_PATH, 0o644)
    except OSError:
        pass
    print(text, flush=True)


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


DENY_PIN = "/sys/fs/bpf/vantio_deny_attr"
SYS_BPF = 321
BPF_OBJ_GET = 7
BPF_MAP_LOOKUP_ELEM = 1


class _ObjGet(ctypes.Structure):
    _fields_ = [
        ("pathname", ctypes.c_uint64),
        ("bpf_fd", ctypes.c_uint32),
        ("file_flags", ctypes.c_uint32),
    ]


class _Lookup(ctypes.Structure):
    _fields_ = [
        ("map_fd", ctypes.c_uint32),
        ("_pad", ctypes.c_uint32),
        ("key", ctypes.c_uint64),
        ("value", ctypes.c_uint64),
        ("flags", ctypes.c_uint64),
    ]


def pinned_deny_anchor(pid: int) -> int:
    """Lineage anchor from the pinned deny map, or 0 when the row does not name both."""
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return 0
    if not Path(DENY_PIN).exists():
        return 0
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    path = ctypes.create_string_buffer(DENY_PIN.encode("ascii") + b"\0")
    attr = _ObjGet(ctypes.addressof(path), 0, 0)
    fd = libc.syscall(
        ctypes.c_long(SYS_BPF),
        ctypes.c_long(BPF_OBJ_GET),
        ctypes.byref(attr),
        ctypes.c_uint(ctypes.sizeof(attr)),
    )
    if fd < 0:
        return 0
    try:
        for kind in (grade.DENY_KIND_FILE, grade.DENY_KIND_SELF):
            key = ctypes.c_uint64((pid << 8) | kind)
            value = ctypes.create_string_buffer(grade.DENY_ATTR_SIZE)
            lookup = _Lookup(int(fd), 0, ctypes.addressof(key), ctypes.addressof(value), 0)
            rc = libc.syscall(
                ctypes.c_long(SYS_BPF),
                ctypes.c_long(BPF_MAP_LOOKUP_ELEM),
                ctypes.byref(lookup),
                ctypes.c_uint(ctypes.sizeof(lookup)),
            )
            if rc == 0:
                anchor = grade.deny_record_anchor(value.raw, pid)
                if anchor > 0:
                    return anchor
    finally:
        os.close(int(fd))
    return 0


def pinned_deny_names(pid: int) -> bool:
    """The deny map stays after the loader process is gone. A pid without an anchor does not count."""
    return pinned_deny_anchor(pid) > 0


def egress_block_anchor(pid: int) -> int:
    """Anchor from an egress deny-attr row for this pid, or 0.

    Dropping the SYN leaves connect at a timeout. The row is what makes that
    timeout a block. A file row is not read here.
    """
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return 0
    if not Path(DENY_PIN).exists():
        return 0
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    path = ctypes.create_string_buffer(DENY_PIN.encode("ascii") + b"\0")
    attr = _ObjGet(ctypes.addressof(path), 0, 0)
    fd = libc.syscall(
        ctypes.c_long(SYS_BPF),
        ctypes.c_long(BPF_OBJ_GET),
        ctypes.byref(attr),
        ctypes.c_uint(ctypes.sizeof(attr)),
    )
    if fd < 0:
        return 0
    try:
        for kind in (grade.DENY_KIND_EGRESS_CGROUP, grade.DENY_KIND_EGRESS_TC):
            key = ctypes.c_uint64((pid << 8) | kind)
            value = ctypes.create_string_buffer(grade.DENY_ATTR_SIZE)
            lookup = _Lookup(int(fd), 0, ctypes.addressof(key), ctypes.addressof(value), 0)
            rc = libc.syscall(
                ctypes.c_long(SYS_BPF),
                ctypes.c_long(BPF_MAP_LOOKUP_ELEM),
                ctypes.byref(lookup),
                ctypes.c_uint(ctypes.sizeof(lookup)),
            )
            if rc == 0:
                anchor = grade.egress_record_anchor(value.raw, pid)
                if anchor > 0:
                    return anchor
    finally:
        os.close(int(fd))
    return 0


def ndjson_denied_pids() -> list[int]:
    """Pids named by a DENIED ledger row. A map hit without this row is not enough."""
    found: list[int] = []
    for item in events():
        if item.get("ActionTaken") != "DENIED":
            continue
        pid = item.get("Pid")
        if isinstance(pid, int) and pid > 0 and pid not in found:
            found.append(pid)
    return found[-8:]


def attributed(pid: int, action: str) -> bool:
    """A post-kill deny names the pid and the lineage anchor.

    The ledger row is enough. A deny-attr row is enough once it carries the
    same anchor. A map slot that names only the pid is not.
    """
    if action == "DENIED":
        if deny_event_for(pid) is not None:
            return True
        return pinned_deny_anchor(pid) > 0
    for item in events():
        raw = item.get("Pid")
        if raw == pid and item.get("ActionTaken") == action:
            return True
    return False


def _configured_target() -> tuple[str | None, int | None]:
    """Arm override. An empty host means discover this machine's own address."""
    host = os.environ.get("VANTIO_EGRESS_HOST", "").strip() or None
    raw = os.environ.get("VANTIO_EGRESS_PORT", "").strip()
    if not raw:
        return host, None
    if not raw.isdigit():
        return host, -1
    return host, int(raw)


def primary_local_ipv4s() -> list[str]:
    """This host's own non-loopback IPv4 addresses, primary source first.

    Docker bridges and the old lab veth stay at the end. A documentation
    address can appear here and is dropped later by the chooser.
    """
    preferred: list[str] = []
    other: list[str] = []
    route = rows.run(["ip", "-4", "route", "get", "1.1.1.1"])
    if route.returncode == 0:
        parts = (route.stdout or "").split()
        if "src" in parts:
            index = parts.index("src")
            if index + 1 < len(parts):
                preferred.append(parts[index + 1])
    listed = rows.run(["ip", "-4", "-o", "addr", "show", "scope", "global"])
    if listed.returncode == 0:
        for line in (listed.stdout or "").splitlines():
            bits = line.split()
            if len(bits) < 4 or bits[2] != "inet":
                continue
            ifname = bits[1]
            addr = bits[3].split("/", 1)[0]
            if addr in preferred or addr in other:
                continue
            if ifname == "lo" or ifname.startswith(("docker", "veth", "br-", "vlab", "cni")):
                other.append(addr)
            else:
                preferred.append(addr)
    return preferred + other


def egress_endpoint() -> tuple[str, int] | None:
    """The reachable listener for this run. None means do not grade."""
    global _ENDPOINT, _ENDPOINT_READY
    if not _ENDPOINT_READY:
        configured, port = _configured_target()
        _ENDPOINT = grade.choose_egress_target(configured, port, primary_local_ipv4s())
        _ENDPOINT_READY = True
    return _ENDPOINT


def _address_is_local(host: str) -> bool:
    return host in primary_local_ipv4s()


def tcp_handshake_errno(timeout: float = 2.0, host: str | None = None, port: int | None = None) -> int:
    """Complete a TCP handshake with the lab listener, or return the errno.

    0 means the handshake finished. 110 is a timeout and is not a grade.
    This process must not be in the enrolled cgroup when it is the control.
    """
    if host is None or port is None:
        target = egress_endpoint()
        if target is None:
            return 110
        host, port = target
    sock = socket.socket()
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        return 0
    except TimeoutError:
        return 110
    except OSError as exc:
        return exc.errno or 1
    finally:
        sock.close()


def _listener_up() -> bool:
    """An unenrolled handshake. This process is not in the enrolled cgroup."""
    return tcp_handshake_errno(0.5) == 0


def ensure_egress_listener() -> bool:
    """Start the listener on this host's own address, then complete a handshake.

    A paired address is not started here. The arm has to listen on that
    instance and allow the port. If that handshake does not finish, the
    caller leaves the case ungraded.
    """
    target = egress_endpoint()
    if target is None:
        return False
    host, port = target
    if not _address_is_local(host):
        return _listener_up()
    if _listener_up():
        return True
    path = Path("/tmp/vantio-egress-listen.py")
    path.write_text(_LISTENER_SRC, encoding="utf-8")
    env = os.environ.copy()
    env["VANTIO_EGRESS_HOST"] = host
    env["VANTIO_EGRESS_PORT"] = str(port)
    subprocess.Popen(
        ["python3", str(path)],
        env=env,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(25):
        if _listener_up():
            return True
        time.sleep(0.1)
    return False


def _egress_errno() -> int:
    """TCP handshake from the caller. 0 is allowed. 1 or 111 is blocked. 110 is not a grade."""
    return tcp_handshake_errno()


def control_handshake() -> int:
    """Unenrolled handshake to the peer listener, before any enrolled connect.

    0 means the handshake finished. Anything else means the lab network is
    the problem and the enrolled connect must not run.
    """
    if not ensure_egress_listener():
        return tcp_handshake_errno()
    return tcp_handshake_errno()


def egress_observation() -> dict:
    """The address this run actually used, so a timeout names its target."""
    target = egress_endpoint()
    if target is None:
        return {"egress_target": None, "egress_port": None}
    host, port = target
    return {"egress_target": host, "egress_port": port}


def _docker_host_ip(args: list[str]):
    """Run ip in the netns Docker uses for --network=host.

    The loader container uses that flag. A veth created by the host ip
    command was not visible there, so tc returned ENODEV.
    """
    image = os.environ.get("VANTIO_IMAGE") or rows.IMAGE
    if not image:
        raise SystemExit("lab_iface_image")
    return rows.sudo(
        [
            "docker",
            "run",
            "--rm",
            "--network=host",
            "--privileged",
            "--entrypoint",
            "/usr/bin/ip",
            "-v",
            "/usr/bin/ip:/usr/bin/ip:ro",
            "-v",
            "/lib:/lib:ro",
            "-v",
            "/lib64:/lib64:ro",
            "-v",
            "/usr/lib:/usr/lib:ro",
            image,
            *args,
        ],
        timeout=40,
    )


def _lo_ip(args: list[str]):
    """Run ip on the host. The allow listener is a host process, not a container.

    Docker is only the fallback. The hourly timer does not have VANTIO_IMAGE,
    and guest_rows.IMAGE is that same variable, so a docker run cannot name
    an image there.
    """
    try:
        completed = subprocess.run(
            ["ip", *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        completed = None
    if completed is not None:
        if completed.returncode == 0:
            return completed
        detail = ((completed.stderr or "") + (completed.stdout or "")).lower()
        if "exists" in detail:
            return completed
    return _docker_host_ip(args)


def ensure_allowlist_peer() -> None:
    """Listen on one private address and tell the loader to allow only that one.

    The enrolled deny target stays the host's own primary address, which is
    not on this list. An enrolled handshake here has to complete.
    """
    os.environ["VANTIO_LAB_ALLOWLIST"] = ALLOW_HOST
    show = _lo_ip(["addr", "show", "dev", "lo"])
    if ALLOW_HOST not in (show.stdout or ""):
        added = _lo_ip(["addr", "add", f"{ALLOW_HOST}/32", "dev", "lo"])
        detail = (added.stderr or "") + (added.stdout or "")
        if added.returncode != 0 and "File exists" not in detail and "exists" not in detail.lower():
            raise SystemExit(f"allowlist_addr {added.returncode} {detail[-180:]}")
    if tcp_handshake_errno(0.3, ALLOW_HOST, ALLOW_PORT) == 0:
        return
    path = Path("/tmp/vantio-allow-listen.py")
    path.write_text(_LISTENER_SRC, encoding="utf-8")
    env = os.environ.copy()
    env["VANTIO_EGRESS_HOST"] = ALLOW_HOST
    env["VANTIO_EGRESS_PORT"] = str(ALLOW_PORT)
    subprocess.Popen(
        ["python3", str(path)],
        env=env,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(25):
        if tcp_handshake_errno(0.3, ALLOW_HOST, ALLOW_PORT) == 0:
            return
        time.sleep(0.1)
    raise SystemExit("allowlist_listener")


def enrolled_connect_errno(host: str, port: int) -> int:
    """Handshake from a child born in the anchor. 0 connected. Other values did not."""
    report_r, report_w = os.pipe()
    helper = os.fork()
    if helper == 0:
        os.close(report_r)
        try:
            (Path(rows.ANCHOR) / "cgroup.procs").write_text(f"{os.getpid()}\n", encoding="utf-8")
            child = os.fork()
        except OSError as exc:
            os.write(report_w, f"net {exc.errno or 1}\n".encode())
            os.close(report_w)
            os._exit(0)
        if child == 0:
            try:
                os.setresuid(SUBJECT, SUBJECT, 0)
                errno = tcp_handshake_errno(host=host, port=port)
            except OSError as exc:
                errno = exc.errno or 1
            os.write(report_w, f"net {errno}\n".encode())
            os.close(report_w)
            os._exit(0)
        os.close(report_w)
        os.waitpid(child, 0)
        os._exit(0)
    os.close(report_w)
    os.waitpid(helper, 0)
    text = os.read(report_r, 80).decode(errors="replace")
    os.close(report_r)
    parts = text.split()
    if len(parts) >= 2 and parts[0] == "net" and parts[1].lstrip("-").isdigit():
        return int(parts[1])
    return 110


def ensure_lab_iface() -> None:
    """Create vlab-host in the loader's network namespace."""
    show = _docker_host_ip(["link", "show", "vlab-host"])
    if show.returncode != 0:
        added = _docker_host_ip(
            ["link", "add", "vlab-host", "type", "veth", "peer", "name", "vlab-peer"]
        )
        if added.returncode != 0:
            detail = ((added.stderr or "") + (added.stdout or ""))[-240:]
            raise SystemExit(f"lab_iface {added.returncode} {detail}")
        peer = _docker_host_ip(["link", "set", "vlab-peer", "up"])
        if peer.returncode != 0:
            raise SystemExit("lab_iface_peer")
    up = _docker_host_ip(["link", "set", "vlab-host", "up"])
    if up.returncode != 0:
        raise SystemExit("lab_iface_up")


def vantio_bpf_pins() -> list[str]:
    """Pinned map and program names the loader left under bpffs."""
    root = Path("/sys/fs/bpf")
    if not root.is_dir():
        return []
    return sorted(path.name for path in root.iterdir() if path.name.startswith("vantio"))


REVOKE_CONVERGENCE: dict = {}


def prepare_enforce(*, time_revoke: bool = False) -> tuple[PeHostAdapter, str]:
    rows.ensure_cgroups()
    ensure_lab_iface()
    ensure_allowlist_peer()
    meta = rows.load("meta.json")
    plane = ControlPlane(LocalHostVerifier(load_packaged_test_trust()), root_ids=("cust-root", "cust-b"))
    adapter = PeHostAdapter(plane)
    opened = plane.submit_activation(rows.load("activation.json"), rows.sig("activation.sig.json"))
    adapter.on_activation(opened, plane.policy)
    granted = plane.submit_governance(rows.load("grant.json"), rows.sig("grant.sig.json"), now=meta["now"])
    adapter.on_governance(granted, "grant")
    rows.LAB.mkdir(parents=True, exist_ok=True)
    (rows.LAB / "evidence").mkdir(parents=True, exist_ok=True)
    (rows.LAB / "d").mkdir(parents=True, exist_ok=True)
    rows.DENY.write_text("lab-deny-marker\n", encoding="utf-8")
    os.chmod(rows.DENY, 0o644)
    rows.sudo(["mkdir", "-p", rows.ANCHOR])
    started = rows.start_loader(adapter)
    if started["rc"] != 0:
        raise SystemExit(f"loader {started['rc']}")
    banner = rows.wait_banner("AUDIT")
    if "AUDIT" not in banner and "observe-only" not in banner:
        raise SystemExit(f"loader banner missing: {banner[-400:]}")
    revoke_started = time.monotonic()
    revoked = plane.submit_governance(rows.load("revoke.json"), rows.sig("revoke.sig.json"), now=meta["now"])
    adapter.on_governance(revoked, "revoke")
    digest = adapter.state.policy_digest or ""
    blocked = rows.start_loader(adapter)
    if blocked["rc"] != 0:
        raise SystemExit(f"enforce loader {blocked['rc']}")
    # Docker logs for this container only. A SCOPED line left in the events
    # file by an earlier battery is not this loader. A missing banner is not
    # a measured fail-open: the probe has not seen a deny yet.
    banner = _wait_scoped_banner()
    if not _banner_ready(banner):
        tail = " ".join(banner.split())[-800:]
        raise SystemExit(f"loader banner missing: SCOPED (drop enrolled) tail={tail}")
    # Enroll the lab cgroup and clear a mode-0 stand-in before any probe.
    # The 2D battery asserts the anchor is non-zero before its first open.
    anchor_before_first_open()
    if time_revoke:
        deadline = time.monotonic() + 30
        last: dict = {}
        while time.monotonic() < deadline:
            last = child_open(True)
            if last.get("file_errno") == 13:
                break
            time.sleep(0.05)
        REVOKE_CONVERGENCE.clear()
        REVOKE_CONVERGENCE.update(
            {
                "ms": round((time.monotonic() - revoke_started) * 1000, 3),
                "errno": last.get("file_errno"),
                "fail_open": last.get("file_errno") == 0,
            }
        )
    return adapter, digest


ENROLLED_PIN = "/sys/fs/bpf/vantio_enrolled_cgroups"
BPF_MAP_UPDATE_ELEM = 2
BPF_ANY = 0


class _Update(ctypes.Structure):
    _fields_ = [
        ("map_fd", ctypes.c_uint32),
        ("_pad", ctypes.c_uint32),
        ("key", ctypes.c_uint64),
        ("value", ctypes.c_uint64),
        ("flags", ctypes.c_uint64),
    ]


def _pin_fd(path: str) -> int:
    if not Path(path).exists():
        return -1
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    raw = ctypes.create_string_buffer(path.encode("ascii") + b"\0")
    attr = _ObjGet(ctypes.addressof(raw), 0, 0)
    fd = libc.syscall(
        ctypes.c_long(SYS_BPF),
        ctypes.c_long(BPF_OBJ_GET),
        ctypes.byref(attr),
        ctypes.c_uint(ctypes.sizeof(attr)),
    )
    return int(fd)


def enrolled_has(cgid: int) -> bool:
    """The pinned enrolled map names this cgroup id. A missing pin is not enrolled."""
    if isinstance(cgid, bool) or not isinstance(cgid, int) or cgid <= 0:
        return False
    fd = _pin_fd(ENROLLED_PIN)
    if fd < 0:
        return False
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    try:
        key = ctypes.c_uint64(cgid)
        value = ctypes.c_uint8(0)
        lookup = _Lookup(fd, 0, ctypes.addressof(key), ctypes.addressof(value), 0)
        rc = libc.syscall(
            ctypes.c_long(SYS_BPF),
            ctypes.c_long(BPF_MAP_LOOKUP_ELEM),
            ctypes.byref(lookup),
            ctypes.c_uint(ctypes.sizeof(lookup)),
        )
        return rc == 0
    finally:
        os.close(fd)


def _kernfs_handle_id(path: str) -> int | None:
    """Kernfs id from name_to_handle_at. None unless the handle type is FILEID_KERNFS (254)."""
    class _Handle(ctypes.Structure):
        _fields_ = [
            ("handle_bytes", ctypes.c_uint),
            ("handle_type", ctypes.c_int),
            ("f_handle", ctypes.c_ubyte * 8),
        ]

    handle = _Handle(8, 0, (ctypes.c_ubyte * 8)())
    mount_id = ctypes.c_int(0)
    libc = ctypes.CDLL(None, use_errno=True)
    libc.name_to_handle_at.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.POINTER(_Handle),
        ctypes.POINTER(ctypes.c_int),
        ctypes.c_int,
    ]
    libc.name_to_handle_at.restype = ctypes.c_int
    rc = libc.name_to_handle_at(-100, path.encode(), ctypes.byref(handle), ctypes.byref(mount_id), 0)
    if rc != 0 or handle.handle_type != 254 or handle.handle_bytes < 8:
        return None
    return int.from_bytes(bytes(handle.f_handle), "little")


def enroll_cgroup_id(cgid: int) -> bool:
    """Write the lab cgroup into the map the live programs use."""
    if isinstance(cgid, bool) or not isinstance(cgid, int) or cgid <= 0:
        return False
    fd = _pin_fd(ENROLLED_PIN)
    if fd < 0:
        return False
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    try:
        key = ctypes.c_uint64(cgid)
        value = ctypes.c_uint8(1)
        update = _Update(fd, 0, ctypes.addressof(key), ctypes.addressof(value), BPF_ANY)
        rc = libc.syscall(
            ctypes.c_long(SYS_BPF),
            ctypes.c_long(BPF_MAP_UPDATE_ELEM),
            ctypes.byref(update),
            ctypes.c_uint(ctypes.sizeof(update)),
        )
        return rc == 0
    finally:
        os.close(fd)


def anchor_before_first_open() -> tuple[int, dict]:
    """Make the ceiling path traversable, drop a stand-in, and enroll the lab cgroup.

    The open kprobe writes no row when the anchor is 0. Errno 13 in that case
    is the directory mode or a mode-0 bind mount, which root can still open.
    """
    path = Path(str(rows.DENY))
    facts: dict = {"path": str(path)}
    for directory in (path.parent.parent, path.parent):
        if not directory.exists():
            continue
        mode = directory.stat().st_mode & 0o777
        facts[str(directory)] = oct(mode)
        if mode & 0o111 != 0o111:
            os.chmod(directory, mode | 0o755)
    if path.exists():
        facts["file_mode"] = oct(path.stat().st_mode & 0o777)
        os.chmod(path, 0o644)
    mounted = rows.sudo(["findmnt", "-n", "-T", str(path)])
    mount = (mounted.stdout or "").strip()
    facts["mount"] = mount
    if "vantio" in mount:
        rows.sudo(["umount", str(path)])
        facts["standin_umount"] = True
    try:
        anchor = os.stat(str(rows.ANCHOR)).st_ino
    except OSError:
        anchor = 0
    facts["cgroup_id"] = anchor
    if anchor > 0:
        handle = _kernfs_handle_id(str(rows.ANCHOR))
        keys = baseline_diag.cgroup_enroll_keys(anchor, handle or 0)
        facts["enroll_keys"] = keys
        facts["enroll_write"] = [key for key in keys if enroll_cgroup_id(key) or enrolled_has(key)]
    if not enrolled_has(anchor):
        anchor = 0
    facts["anchor_before_open"] = anchor
    return anchor, facts


def deny_event_for(pid: int) -> dict | None:
    """The DENIED ledger row for this open. A row for some other pid does not count."""
    path = str(rows.DENY)
    for item in reversed(events()):
        if item.get("Pid") != pid or item.get("ActionTaken") != "DENIED":
            continue
        attempted = item.get("PathAttempted") or item.get("Payload")
        if attempted != path:
            continue
        anchor = item.get("lineage_anchor")
        if isinstance(anchor, bool) or not isinstance(anchor, int) or anchor <= 0:
            continue
        return {
            "action": "DENIED",
            "lineage_anchor": anchor,
            "path": path,
            "pid": pid,
            "uid": item.get("Uid"),
        }
    return None


def _banner_ready(text: str) -> bool:
    """Path deny has attached. Map load alone is earlier and is not a deny.

    The plain banner says "enforcing" and does not repeat the verbose SCOPED
    line. The pin lines are on stderr as soon as open and openat attach.
    """
    pins = (
        "Path DENY pinned: kprobe_open_deny" in text
        and "Path DENY pinned: kprobe_openat_deny" in text
    )
    scoped = "SCOPED (drop enrolled)" in text and (
        "Path DENY pinned" in text or "Path DENY attached" in text
    )
    return pins or scoped


def _wait_scoped_banner(timeout: float = 120) -> str:
    """Wait until this container logs the enforce banner. Do not read a stale file."""
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        proc = rows.sudo(["docker", "logs", rows.LOADER], timeout=20)
        last = (proc.stdout or "") + (proc.stderr or "")
        if _banner_ready(last):
            return last
        time.sleep(2)
    return last


def baseline_ready(sample: dict) -> bool:
    """The enterprise revoke shape: errno 13, a pid, and a non-zero lineage anchor."""
    event = sample.get("deny_event")
    pid = sample.get("pid")
    anchor = sample.get("lineage_anchor")
    return (
        sample.get("file_errno") == 13
        and isinstance(pid, int)
        and not isinstance(pid, bool)
        and pid > 0
        and isinstance(anchor, int)
        and not isinstance(anchor, bool)
        and anchor > 0
        and isinstance(event, dict)
        and event.get("pid") == pid
        and event.get("lineage_anchor") == anchor
    )


def _probe_pid(sample: dict) -> int:
    detail = str(sample.get("detail") or "")
    marker = " pid "
    if marker not in detail:
        return 0
    token = detail.rsplit(marker, 1)[1].split(" ", 1)[0]
    if token.isdigit():
        return int(token)
    return 0


def enterprise_open(digest: str) -> dict:
    """The enterprise probe. The child is born in the anchor, then it opens the ceiling.

    Anchor 0 means the loader has no enrollment record for that task. Errno 0
    on that task is the unenrolled result, so it is not a kill or restart grade.
    """
    path = str(rows.DENY)
    last: dict = {
        "cgroup": "",
        "deny_event": None,
        "enrolled": False,
        "file_errno": None,
        "lineage_anchor": 0,
        "net_errno": None,
        "path": path,
        "pid": 0,
        "uid": SUBJECT,
    }
    for _ in range(40):
        before = len(events())
        sample = rows.probe()
        time.sleep(0.4)
        event = None
        for item in reversed(events()[before:]):
            if not revoke_deny_event_links_digest(
                item,
                policy_digest=digest or "",
                subject_uid=SUBJECT,
                blocked_path=path,
            ):
                continue
            anchor = item.get("lineage_anchor")
            pid = item.get("Pid")
            if isinstance(anchor, bool) or not isinstance(anchor, int) or anchor <= 0:
                continue
            if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
                continue
            event = {
                "action": "DENIED",
                "lineage_anchor": anchor,
                "path": path,
                "pid": pid,
                "uid": item.get("Uid"),
            }
            break
        probe_pid = _probe_pid(sample)
        map_anchor = pinned_deny_anchor(probe_pid) if probe_pid else 0
        map_named = map_anchor > 0
        if event is None and map_anchor > 0:
            # The userspace ring stops when the loader is dead. The pinned map
            # counts only when it names this pid and the lineage anchor.
            event = {
                "action": "DENIED",
                "lineage_anchor": map_anchor,
                "path": path,
                "pid": probe_pid,
                "source": "deny_attr",
                "uid": SUBJECT,
            }
        last = {
            "cgroup": sample.get("cgroup") or "",
            "deny_event": event,
            "enrolled": event is not None and (event.get("lineage_anchor") or 0) > 0,
            "file_errno": sample.get("nobody_errno"),
            "lineage_anchor": event["lineage_anchor"] if event else 0,
            "map_named": map_named,
            "net_errno": None,
            "path": path,
            "pid": event["pid"] if event else probe_pid,
            "probe_detail": sample.get("detail"),
            "uid": SUBJECT,
            "uid0_result": sample.get("uid0_result"),
        }
        if baseline_ready(last):
            return last
        time.sleep(0.25)
    return last


def _setup_invalid(sample: dict, digest: str, **extra: object) -> dict:
    body = {
        "enforcement_drop": False,
        "policy_digest": digest,
        "reason": "baseline_not_enrolled",
        "setup_invalid": True,
    }
    body.update(extra)
    return body


def child_open(enroll: bool) -> dict:
    """Enrolled open is born inside the anchor, the same way the enterprise probe is.

    The network half connects to the local listener. Errno 0 means the
    handshake completed. Errno 1 or 111 means the connect was blocked. A
    timeout stays 110 and is not graded as either.

    A child that is forked outside the cgroup and then moves itself is not the
    enrolled ceiling workload. The parent joins the anchor first, then the
    child is born there, drops to uid 65534, and opens the signed path.
    """
    listener_ready = ensure_egress_listener()
    report_r, report_w = os.pipe()
    helper = os.fork()
    if helper == 0:
        os.close(report_r)
        try:
            if enroll:
                (Path(rows.ANCHOR) / "cgroup.procs").write_text(f"{os.getpid()}\n", encoding="utf-8")
            child = os.fork()
        except OSError as exc:
            os.write(report_w, f"setup {exc.errno or 1}\n".encode())
            os.close(report_w)
            os._exit(0)
        if child == 0:
            try:
                here = Path("/proc/self/cgroup").read_text(encoding="utf-8").strip().replace("\n", " ")
            except OSError:
                here = ""
            try:
                os.setresuid(SUBJECT, SUBJECT, 0)
                try:
                    fd = os.open(str(rows.DENY), os.O_RDONLY)
                    os.close(fd)
                    errno = 0
                except OSError as exc:
                    errno = exc.errno or 1
                net = _egress_errno() if listener_ready else 110
            except OSError as exc:
                errno = exc.errno or 1
                net = exc.errno or 1
            os.write(
                report_w,
                f"file {errno} net {net} pid {os.getpid()} cgroup {here}\n".encode(),
            )
            os.close(report_w)
            os._exit(0)
        os.close(report_w)
        os.waitpid(child, 0)
        os._exit(0)
    os.close(report_w)
    os.waitpid(helper, 0)
    text = os.read(report_r, 400).decode(errors="replace")
    os.close(report_r)
    body = {
        "cgroup": "",
        "enrolled": enroll,
        "file_errno": None,
        "net_errno": None,
        "path": str(rows.DENY),
        "pid": None,
        "uid": SUBJECT,
    }
    parts = text.split()
    if len(parts) >= 6 and parts[0] == "file" and parts[2] == "net" and parts[4] == "pid":
        body["file_errno"] = int(parts[1])
        body["net_errno"] = int(parts[3])
        body["pid"] = int(parts[5])
        if "cgroup" in parts:
            body["cgroup"] = text.split("cgroup", 1)[1].strip()
    return body


def stamp_deny(sample: dict) -> dict:
    """Attach the ledger row for this probe after the ring has flushed."""
    time.sleep(0.4)
    pid = sample.get("pid")
    event = deny_event_for(pid) if isinstance(pid, int) else None
    sample["deny_event"] = event
    sample["lineage_anchor"] = event["lineage_anchor"] if event else 0
    return sample


def _deny_count(pid: int) -> int:
    """DENIED rows for this pid and the ceiling path that carry an anchor."""
    path = str(rows.DENY)
    count = 0
    for item in events():
        if item.get("Pid") != pid or item.get("ActionTaken") != "DENIED":
            continue
        attempted = item.get("PathAttempted") or item.get("Payload")
        if attempted != path:
            continue
        anchor = item.get("lineage_anchor")
        if isinstance(anchor, bool) or not isinstance(anchor, int) or anchor <= 0:
            continue
        count += 1
    return count


def same_process_across_restart(adapter) -> dict:
    """One enrolled process opens, the loader restarts, and that same pid opens again.

    The anchor on the second deny has to match the first. A restart that
    drops the cgroup id leaves errno 13 with no new row, or errno 0.
    """
    report_r, report_w = os.pipe()
    cmd_r, cmd_w = os.pipe()
    child = os.fork()
    if child == 0:
        os.close(report_r)
        os.close(cmd_w)
        try:
            (Path(rows.ANCHOR) / "cgroup.procs").write_text(f"{os.getpid()}\n", encoding="utf-8")
            os.setresuid(SUBJECT, SUBJECT, 0)

            def open_errno() -> int:
                try:
                    fd = os.open(str(rows.DENY), os.O_RDONLY)
                    os.close(fd)
                    return 0
                except OSError as exc:
                    return exc.errno or 1

            os.write(report_w, f"first {open_errno()} {os.getpid()}\n".encode())
            if os.read(cmd_r, 1) == b"x":
                os.write(report_w, f"second {open_errno()} {os.getpid()}\n".encode())
        except OSError as exc:
            try:
                os.write(report_w, f"setup {exc.errno or 1}\n".encode())
            except OSError:
                pass
        os._exit(0)
    os.close(report_w)
    os.close(cmd_r)
    body: dict = {"held": False, "reason": "probe_failed", "pid": None}
    try:
        first = os.read(report_r, 80).decode(errors="replace").split()
        if len(first) != 3 or first[0] != "first":
            body["detail"] = " ".join(first)
            return body
        errno_before = int(first[1])
        pid = int(first[2])
        time.sleep(0.5)
        event = deny_event_for(pid)
        before_anchor = event["lineage_anchor"] if event else 0
        before_count = _deny_count(pid)
        body.update(
            {
                "pid": pid,
                "before_errno": errno_before,
                "before_anchor": before_anchor,
                "before_count": before_count,
            }
        )
        if errno_before != 13 or before_anchor <= 0:
            body["reason"] = "not_enrolled_before_restart"
            return body
        kill_loader()
        started = rows.start_loader(adapter)
        if started.get("rc") != 0:
            body["reason"] = "loader_restart_failed"
            return body
        banner = _wait_scoped_banner()
        if not _banner_ready(banner):
            body["reason"] = "banner_missing"
            return body
        os.write(cmd_w, b"x")
        second = os.read(report_r, 80).decode(errors="replace").split()
        if len(second) != 3 or second[0] != "second" or int(second[2]) != pid:
            body["detail"] = " ".join(second)
            return body
        errno_after = int(second[1])
        time.sleep(0.5)
        after = deny_event_for(pid)
        after_anchor = after["lineage_anchor"] if after else 0
        after_count = _deny_count(pid)
        body.update(
            {
                "after_errno": errno_after,
                "after_anchor": after_anchor,
                "after_count": after_count,
            }
        )
        body.update(
            grade.restart_keeps_the_same_anchor(
                pid=pid,
                before_errno=errno_before,
                before_anchor=before_anchor,
                after_errno=errno_after,
                after_anchor=after_anchor,
                before_count=before_count,
                after_count=after_count,
            )
        )
        return body
    finally:
        try:
            os.write(cmd_w, b"q")
        except OSError:
            pass
        os.close(cmd_w)
        os.close(report_r)
        os.waitpid(child, 0)


def kill_loader() -> int:
    proc = rows.sudo(["pkill", "-9", "-x", "vantio-loader"])
    time.sleep(1.0)
    return proc.returncode


def standin_after_sigkill() -> dict:
    """SIGKILL does not remove the mode-0 fail-closed bind mount. That is acceptable."""
    record = Path("/run/vantio-failclosed-mounts")
    text = ""
    if record.is_file():
        try:
            text = record.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
    proc = rows.sudo(["findmnt", "-n", "-T", "/var/lib/vantio-pe-clean-host/d/secret"])
    mount = (proc.stdout or "").strip()
    remains = bool(text.strip()) or "vantio-sealed" in mount
    return {
        "standin_mount_remains": remains,
        "standin_record_present": bool(text.strip()),
        "note": "SIGKILL leaves the mode-0 stand-in bind mount in place. That is acceptable.",
    }


def loader_running() -> bool:
    return rows.run(["pgrep", "-x", "vantio-loader"]).returncode == 0


def scoped_started(timeout: float = 120) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        for item in events():
            if item.get("ActionTaken") == "SCOPED" and item.get("EventType") == "ENGINE_STARTED":
                return True
        time.sleep(2)
    return False


def image_id() -> str:
    proc = rows.sudo(["docker", "image", "inspect", "--format", "{{.Id}}", rows.IMAGE])
    return (proc.stdout or "").strip()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_oci(path: Path) -> str:
    proc = rows.sudo(["docker", "load", "-i", str(path)], timeout=180)
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.returncode != 0:
        raise SystemExit(f"docker_load {proc.returncode}")
    loaded = ""
    for line in text.splitlines():
        if line.startswith("Loaded image: "):
            loaded = line.split("Loaded image: ", 1)[1].strip()
    if not loaded or len(loaded) > 180 or any(char in loaded for char in "\n\r"):
        raise SystemExit("loaded_image")
    return loaded


def _image_id(ref: str) -> str:
    proc = rows.sudo(["docker", "image", "inspect", "--format", "{{.Id}}", ref], timeout=30)
    return (proc.stdout or "").strip()


def _use_image(ref: str) -> None:
    os.environ["VANTIO_IMAGE"] = ref
    rows.IMAGE = ref


def _measure_loaded(ref: str) -> dict:
    """Start this image and record one attributed enrolled open. No detach."""
    _use_image(ref)
    try:
        _adapter, digest = prepare_enforce()
    except SystemExit as exc:
        return {
            "attributed": False,
            "file_errno": None,
            "image_id": _image_id(ref),
            "policy_digest": "",
            "setup_error": str(exc.code)[:180],
        }
    sample = enterprise_open(digest)
    errno = sample.get("file_errno")
    return {
        "attributed": baseline_ready(sample),
        "file_errno": errno if isinstance(errno, int) and not isinstance(errno, bool) else None,
        "image_id": _image_id(ref),
        "policy_digest": digest,
        "setup_error": "",
    }


def _product_uninstall(image: str) -> dict:
    """Run this image's vantio-loader --uninstall, then read bpftool and bpffs.

    Stopping the loader container is what the shell already does before the
    product binary. This does not detach a program and does not unlink a pin.
    """
    import product_uninstall_census as census

    rows.sudo(["docker", "update", "--restart=no", rows.LOADER], timeout=20)
    rows.sudo(["docker", "stop", "--signal", "SIGINT", "--time", "20", rows.LOADER], timeout=40)
    rows.sudo(["docker", "rm", "-f", rows.LOADER], timeout=40)
    rows.sudo(["docker", "update", "--restart=no", "vantio-pe-lab"], timeout=20)
    rows.sudo(["docker", "rm", "-f", "vantio-pe-lab"], timeout=40)
    record = Path("/run/vantio-failclosed-mounts")
    if record.is_file():
        for path in record.read_text(encoding="utf-8", errors="replace").splitlines():
            if path.startswith("/") and ".." not in path.split("/"):
                rows.sudo(["umount", path], timeout=20)
    rows.sudo(["mkdir", "-p", "/var/lib/vantio", "/var/log/vantio", "/var/lib/vantio-lab"], timeout=20)
    token_path = "/var/lib/vantio/enterprise-uninstall.token"
    if rows.sudo(["test", "-s", token_path], timeout=10).returncode != 0:
        rows.sudo(
            ["bash", "-c", "printf '%s\\n' lab-nonprod-uninstall > /var/lib/vantio/enterprise-uninstall.token"],
            timeout=10,
        )
    token = (rows.sudo(["cat", token_path], timeout=10).stdout or "").strip()
    created = rows.sudo(["docker", "create", image], timeout=60)
    cid = (created.stdout or "").strip()
    if created.returncode != 0 or not cid or "\n" in cid:
        return {"tail": "", "verified_removed": False, "reason": "create_failed"}
    copied = rows.sudo(["docker", "cp", f"{cid}:/vantio-loader", "/var/lib/vantio/vantio-loader"], timeout=60)
    rows.sudo(["docker", "rm", cid], timeout=30)
    if copied.returncode != 0:
        return {"tail": "", "verified_removed": False, "reason": "loader_copy_failed"}
    rows.sudo(["chmod", "755", "/var/lib/vantio/vantio-loader"], timeout=10)
    proc = rows.sudo(
        [
            "/var/lib/vantio/vantio-loader",
            "--uninstall",
            "--confirm",
            "uninstall",
            "--enterprise-approval",
            token,
        ],
        timeout=180,
    )
    text = ((proc.stdout or "") + "\n" + (proc.stderr or "")).replace(token, "[token]")
    show = rows.sudo(["bpftool", "-j", "prog", "show"], timeout=30)
    raw = (show.stdout or "") + "\n" + (show.stderr or "")
    try:
        payload = json.loads(show.stdout or "")
    except json.JSONDecodeError:
        payload = raw
    programs = census.loaded_programs(payload, raw)
    find = rows.sudo(["find", "/sys/fs/bpf", "-maxdepth", "2", "-name", "vantio*"], timeout=20)
    mounted = "bpf" in Path("/proc/mounts").read_text(encoding="utf-8", errors="replace")
    paths = census.classify_bpffs(mounted=mounted, find_rc=find.returncode, text=find.stdout or "")
    ps = rows.sudo(["docker", "ps", "-q"], timeout=20)
    removed = census.removal_census(programs, paths, ps.stdout or "", show.returncode)
    tail = text[-400:]
    removed["tail"] = tail
    removed["uninstall_rc"] = proc.returncode
    removed["verified_removed"] = bool(removed.get("verified_removed")) and "UNINSTALL_VERIFIED" in text
    return removed


def _cycle_step(name: str, ref: str, archive_sha256: str) -> dict:
    measured = _measure_loaded(ref)
    uninstall = _product_uninstall(ref)
    return {
        "archive_sha256": archive_sha256,
        "attributed": measured["attributed"],
        "file_errno": measured["file_errno"],
        "image_id": measured["image_id"],
        "image_ref": ref,
        "name": name,
        "policy_digest": measured["policy_digest"],
        "setup_error": measured["setup_error"],
        "uninstall": {
            "loader_programs": uninstall.get("loader_programs"),
            "reason": uninstall.get("reason", ""),
            "tail": uninstall.get("tail", ""),
            "verified_removed": uninstall.get("verified_removed") is True,
        },
    }


def run_2c() -> dict:
    """Load the public pin, upgrade to the working seal, roll back, and upgrade again.

    The runner copied both tars. This function checks their digests, then
    measures enforcement and the product uninstall on each image. It does
    not fetch, and it does not call a missing image a finished rollback.
    """
    pin_tar = HERE / "public-pin.oci.tar"
    seal_tar = HERE / "seal.oci.tar"
    pin_sha = _sha256_file(pin_tar) if pin_tar.is_file() else ""
    seal_sha = _sha256_file(seal_tar) if seal_tar.is_file() else ""
    if pin_sha != grade.PUBLIC_INSTALLER_PIN or seal_sha != grade.WORKING_SEAL:
        graded = grade.grade_image_cycle([])
        graded["loaded_seal"] = seal_sha
        graded["public_pin_sha256"] = pin_sha
        graded["working_seal_match"] = seal_sha == grade.WORKING_SEAL
        if pin_sha != grade.PUBLIC_INSTALLER_PIN:
            graded["reason"] = "public_pin_absent" if not pin_sha else "public_pin_digest"
        elif seal_sha != grade.WORKING_SEAL:
            graded["reason"] = "seal_absent" if not seal_sha else "seal"
        graded["host_result"] = "FAIL"
        graded["action"] = "FAIL"
        graded["upgrade_pass"] = False
        return graded
    pin_image = _load_oci(pin_tar)
    seal_image = _load_oci(seal_tar)
    steps = [
        _cycle_step("baseline", pin_image, pin_sha),
        _cycle_step("upgrade", seal_image, seal_sha),
        _cycle_step("rollback", pin_image, pin_sha),
        _cycle_step("reupgrade", seal_image, seal_sha),
    ]
    graded = grade.grade_image_cycle(steps)
    graded["loaded_seal"] = seal_sha
    graded["public_pin_sha256"] = pin_sha
    graded["working_seal_match"] = True
    return graded


def run_2d() -> dict:
    adapter, digest = prepare_enforce()
    anchor, path_facts = anchor_before_first_open()
    if not grade.anchor_before_open_ok(anchor):
        return _setup_invalid(
            {},
            digest,
            reason="anchor_missing_before_open",
            anchor_before_open=anchor,
            path_facts=path_facts,
        )
    up = enterprise_open(digest)
    if not baseline_ready(up):
        try:
            diag = baseline_diag.collect(
                str(rows.DENY),
                anchor,
                str(Path(rows.ANCHOR) / "cgroup.procs"),
            )
        except Exception as exc:
            diag = {"cause": "diag_failed", "error": type(exc).__name__}
        return _setup_invalid(
            up,
            digest,
            while_loader_up=up,
            anchor_before_open=anchor,
            path_facts=path_facts,
            baseline_diag=diag,
        )
    carried = same_process_across_restart(adapter)
    if not carried.get("held"):
        return {
            "anchor_before_open": anchor,
            "battery": "2d-crash-recovery",
            "claim_ceiling": grade.CLAIM_CEILING,
            "customer_claim": False,
            "enroll_restart": carried,
            "host_result": "FAIL",
            "lab_pass": False,
            "policy_digest": digest,
            "reason": carried.get("reason") or "enrollment_dropped",
            "setup_invalid": False,
            "while_loader_up": up,
        }
    kill_loader()
    standin = standin_after_sigkill()
    if loader_running():
        raise SystemExit("loader_still_up")
    enrolled = enterprise_open(digest)
    # The file probe does not open a socket. The unenrolled control has to
    # finish a TCP handshake with the same listener before any enrolled connect.
    # A control timeout is the lab network, so this case is not graded.
    control_errno = control_handshake()
    control = {"enrolled": False, "net_errno": control_errno, "role": "control", "file_errno": None}
    observed = egress_observation()
    if control_errno != 0:
        refused = grade.ungraded_egress("2d-crash-recovery", "lab_network")
        refused["policy_digest"] = digest
        refused["while_loader_up"] = up
        refused["enrolled_after"] = enrolled
        refused["unenrolled_after"] = control
        refused["control_errno"] = control_errno
        refused["standin_after_sigkill"] = standin
        refused.update(observed)
        return refused
    egress = child_open(True)
    enrolled["net_errno"] = egress.get("net_errno")
    net_pid = egress.get("pid") if isinstance(egress.get("pid"), int) else 0
    net_anchor = egress_block_anchor(net_pid)
    block = grade.egress_grade_block(control_errno, egress.get("net_errno"))
    if block is not None and not (block == "enrolled_egress_timeout" and net_anchor > 0):
        refused = grade.ungraded_egress("2d-crash-recovery", block)
        refused["policy_digest"] = digest
        refused["while_loader_up"] = up
        refused["enrolled_after"] = enrolled
        refused["unenrolled_after"] = control
        refused["control_errno"] = control_errno
        refused["standin_after_sigkill"] = standin
        refused.update(observed)
        return refused
    file_open = child_open(False)
    unenrolled = {
        "cgroup": file_open.get("cgroup") or "",
        "enrolled": False,
        "file_errno": file_open.get("file_errno"),
        "net_errno": control_errno,
        "path": file_open.get("path"),
        "pid": file_open.get("pid"),
        "role": "control",
        "uid": SUBJECT,
    }
    event = enrolled.get("deny_event")
    file_attributed = (
        isinstance(event, dict)
        and event.get("pid") == enrolled.get("pid")
        and isinstance(event.get("lineage_anchor"), int)
        and not isinstance(event.get("lineage_anchor"), bool)
        and event.get("lineage_anchor") > 0
    )
    graded = grade.grade_crash(
        enrolled_errno=enrolled.get("net_errno"),
        unenrolled_errno=unenrolled.get("net_errno"),
        file_errno=enrolled.get("file_errno") if isinstance(enrolled.get("file_errno"), int) else None,
        file_attributed=file_attributed,
        enrolled_block_anchor=net_anchor,
    )
    graded["policy_digest"] = digest
    graded["anchor_before_open"] = anchor
    graded["enroll_restart"] = carried
    graded["while_loader_up"] = up
    graded["enrolled_after"] = enrolled
    graded["unenrolled_after"] = unenrolled
    graded["control_errno"] = control_errno
    graded.update(observed)
    graded["file_after_enrolled"] = enrolled.get("file_errno")
    graded["file_attributed"] = file_attributed
    graded["allowlist_host"] = ALLOW_HOST
    grade.apply_allowlisted_private(graded, enrolled_connect_errno(ALLOW_HOST, ALLOW_PORT))
    graded["standin_after_sigkill"] = standin
    graded["ndjson_denied_pids"] = [
        item["pid"]
        for item in (up, enrolled)
        if isinstance(item.get("pid"), int) and item.get("deny_event") is not None
    ]
    graded["enforcement_drop"] = (
        up.get("file_errno") == 13
        and up.get("deny_event") is not None
        and enrolled.get("file_errno") == 0
    )
    return graded


def run_2e() -> dict:
    _adapter, digest = prepare_enforce(time_revoke=True)
    started = time.monotonic()
    samples = [child_open(True) for _ in range(100)]
    runtime = time.monotonic() - started
    graded = grade.grade_performance(runtime_seconds=runtime, host_count=1, sample_count=len(samples))
    denied = sum(1 for item in samples if item.get("file_errno") == 13)
    graded["policy_digest"] = digest
    graded["denied_samples"] = denied
    graded["revoke_convergence_ms"] = REVOKE_CONVERGENCE.get("ms")
    graded["revoke_errno"] = REVOKE_CONVERGENCE.get("errno")
    graded["revoke_fail_open"] = REVOKE_CONVERGENCE.get("fail_open") is True
    return graded


def run_2f() -> dict:
    _adapter, digest = prepare_enforce()
    kill_loader()
    standin = standin_after_sigkill()
    still = loader_running()
    control_errno = control_handshake()
    control = {"enrolled": False, "net_errno": control_errno, "role": "control"}
    observed = egress_observation()
    if control_errno != 0:
        refused = grade.ungraded_egress("2f-tamper", "lab_network")
        refused["policy_digest"] = digest
        refused["unenrolled_after"] = control
        refused["control_errno"] = control_errno
        refused["standin_after_sigkill"] = standin
        refused["loader_up"] = still
        refused.update(observed)
        return refused
    enrolled = child_open(True)
    net_pid = enrolled.get("pid") if isinstance(enrolled.get("pid"), int) else 0
    net_anchor = egress_block_anchor(net_pid)
    block = grade.egress_grade_block(control_errno, enrolled.get("net_errno"))
    if block is not None and not (block == "enrolled_egress_timeout" and net_anchor > 0):
        refused = grade.ungraded_egress("2f-tamper", block)
        refused["policy_digest"] = digest
        refused["enrolled_after"] = enrolled
        refused["unenrolled_after"] = control
        refused["control_errno"] = control_errno
        refused["standin_after_sigkill"] = standin
        refused["loader_up"] = still
        refused.update(observed)
        return refused
    unenrolled = control
    file_attributed = isinstance(enrolled.get("pid"), int) and attributed(enrolled["pid"], "DENIED")
    pins = []
    root = Path("/sys/fs/bpf")
    if root.is_dir():
        pins = [str(path) for path in root.rglob("*") if path.is_file()][:5]
    graded = grade.grade_tamper(
        enrolled_errno=enrolled.get("net_errno"),
        unenrolled_errno=unenrolled.get("net_errno"),
        loader_up=still,
        file_errno=enrolled.get("file_errno") if isinstance(enrolled.get("file_errno"), int) else None,
        file_attributed=file_attributed,
        enrolled_block_anchor=net_anchor,
    )
    graded["policy_digest"] = digest
    graded["enrolled_after"] = enrolled
    graded["unenrolled_after"] = unenrolled
    graded["control_errno"] = control_errno
    graded.update(observed)
    graded["file_attributed"] = file_attributed
    graded["standin_after_sigkill"] = standin
    graded["bpf_pin_sample"] = pins
    graded["policy_malformed"] = False
    graded["ndjson_denied_pids"] = ndjson_denied_pids()
    graded["allowlist_host"] = ALLOW_HOST
    grade.apply_allowlisted_private(graded, enrolled_connect_errno(ALLOW_HOST, ALLOW_PORT))
    return graded


def kernel_facts() -> dict:
    os_release = Path("/etc/os-release").read_text(encoding="utf-8", errors="replace") if Path("/etc/os-release").is_file() else ""
    pretty = ""
    for line in os_release.splitlines():
        if line.startswith("PRETTY_NAME="):
            pretty = line.split("=", 1)[1].strip().strip('"')
    lsm_path = Path("/sys/kernel/security/lsm")
    return {
        "distro": pretty,
        "kernel": os.uname().release,
        "btf": Path("/sys/kernel/btf/vmlinux").is_file(),
        "lsm": lsm_path.read_text(encoding="utf-8").strip() if lsm_path.is_file() else "",
        "lockdown": baseline_diag.read_lockdown(),
        "image_name": baseline_diag.read_image_name(),
        "cgroup_v2": Path("/sys/fs/cgroup/cgroup.controllers").is_file(),
        "bpffs": "bpf" in Path("/proc/mounts").read_text(encoding="utf-8", errors="replace"),
    }


def remove_loader() -> bool:
    kill_loader()
    rows.sudo(["docker", "rm", "-f", "vantio-pe-lab"])
    rows.sudo(["docker", "rmi", rows.IMAGE])
    time.sleep(0.5)
    return not loader_running()


def engine_programs_listed() -> dict:
    """Read bpftool. This does not detach, unpin, or uninstall."""
    proc = rows.sudo(["bpftool", "prog", "show"], timeout=30)
    text = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    names: list[str] = []
    for line in text.splitlines():
        if " name " not in line:
            continue
        parts = line.split(" name ", 1)[1].split()
        if parts:
            names.append(parts[0])
    if proc.returncode != 0:
        listed = None
    else:
        listed = any(name == "cgroup_skb_egress_enforce" or name.startswith("cgroup_skb_egre") for name in names)
    return {"bpftool_rc": proc.returncode, "names": names, "program_listed": listed}


def run_r15() -> dict:
    """Stop the loader container, leave the cgroup, probe, then return.

    Uninstall runs later in the shell. This function does not detach the
    program and does not remove the cgroup the probe has to join.
    """
    _adapter, digest = prepare_enforce()
    while_up = child_open(True)
    if while_up.get("file_errno") != 13:
        # The container is still up and the secret opened. That is not a
        # container-exit fail-open. Leave the loader for uninstall.
        body = grade.grade_container_exit(
            file_errno=None,
            egress_errno=None,
            program_listed=None,
            while_up_file_errno=while_up.get("file_errno") if isinstance(while_up.get("file_errno"), int) else None,
        )
        body["policy_digest"] = digest
        body["while_loader_up"] = while_up
        body["detached_by_lab"] = False
        body["measured_before_uninstall"] = False
        return body
    stopped = rows.sudo(["docker", "stop", "--time", "20", rows.LOADER], timeout=40)
    removed = rows.sudo(["docker", "rm", "-f", rows.LOADER], timeout=40)
    cgroup_present = Path(str(rows.ANCHOR)).is_dir()
    after = child_open(True)
    listing = engine_programs_listed()
    pid = after.get("pid") if isinstance(after.get("pid"), int) else 0
    graded = grade.grade_container_exit(
        file_errno=after.get("file_errno") if isinstance(after.get("file_errno"), int) else None,
        egress_errno=after.get("net_errno") if isinstance(after.get("net_errno"), int) else None,
        program_listed=listing.get("program_listed") if isinstance(listing.get("program_listed"), bool) else None,
        egress_anchor=egress_block_anchor(pid),
        while_up_file_errno=13,
    )
    graded["policy_digest"] = digest
    graded["while_loader_up"] = while_up
    graded["after_container_exit"] = after
    graded["cgroup_present"] = cgroup_present
    graded["docker_stop_rc"] = stopped.returncode
    graded["docker_rm_rc"] = removed.returncode
    graded["bpftool_rc"] = listing.get("bpftool_rc")
    graded["bpftool_names"] = listing.get("names")
    graded["detached_by_lab"] = False
    return graded


def run_2g() -> dict:
    facts = kernel_facts()
    _adapter, digest = prepare_enforce()
    enrolled = child_open(True)
    time.sleep(0.4)
    unenrolled = child_open(False)
    removed = remove_loader()
    pid = enrolled.get("pid")
    tar = HERE / "seal.oci.tar"
    seal_sha = hashlib.sha256(tar.read_bytes()).hexdigest() if tar.is_file() else ""
    measured = {
        "live_probe": True,
        "distro": facts["distro"],
        "kernel": facts["kernel"],
        "btf": facts["btf"],
        "lsm": facts["lsm"],
        "seal": seal_sha,
        "enrolled_errno": enrolled.get("file_errno"),
        "unenrolled_errno": unenrolled.get("file_errno"),
        "removed": removed,
        "descendant_pass": False,
        "docker_child_pass": False,
        "ami": os.environ.get("VANTIO_IMAGE_ID", ""),
        "image_name": facts.get("image_name") or "",
        "lockdown": facts.get("lockdown") or "",
    }
    graded = grade.grade_distro(measured)
    graded["kernel_facts"] = facts
    graded["policy_digest"] = digest
    graded["enrolled"] = enrolled
    graded["unenrolled"] = unenrolled
    graded["attributed"] = isinstance(pid, int) and attributed(pid, "DENIED")
    return graded


def _wait_readiness_log(timeout: float = 45) -> str:
    """The enforce container's own log, once it has stated the claim."""
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        proc = rows.sudo(["docker", "logs", rows.LOADER], timeout=20)
        last = (proc.stdout or "") + (proc.stderr or "")
        if (
            "INSTALL_ENFORCEMENT_READINESS_BLOCKED" in last
            or "tc enforce :" in last
            or "bpf is not in the active lsm list" in last.lower()
        ):
            time.sleep(1)
            proc = rows.sudo(["docker", "logs", rows.LOADER], timeout=20)
            return (proc.stdout or "") + (proc.stderr or "")
        time.sleep(2)
    return last


def _enforce_generation_log() -> str:
    """Grant, then revoke, and return the enforce container log."""
    rows.ensure_cgroups()
    ensure_lab_iface()
    meta = rows.load("meta.json")
    plane = ControlPlane(LocalHostVerifier(load_packaged_test_trust()), root_ids=("cust-root", "cust-b"))
    adapter = PeHostAdapter(plane)
    opened = plane.submit_activation(rows.load("activation.json"), rows.sig("activation.sig.json"))
    adapter.on_activation(opened, plane.policy)
    granted = plane.submit_governance(rows.load("grant.json"), rows.sig("grant.sig.json"), now=meta["now"])
    adapter.on_governance(granted, "grant")
    rows.LAB.mkdir(parents=True, exist_ok=True)
    (rows.LAB / "evidence").mkdir(parents=True, exist_ok=True)
    (rows.LAB / "d").mkdir(parents=True, exist_ok=True)
    rows.DENY.write_text("lab-deny-marker\n", encoding="utf-8")
    os.chmod(rows.DENY, 0o644)
    rows.sudo(["mkdir", "-p", rows.ANCHOR])
    started = rows.start_loader(adapter)
    if started["rc"] != 0:
        raise SystemExit(f"loader {started['rc']}")
    banner = rows.wait_banner("AUDIT")
    if "AUDIT" not in banner and "observe-only" not in banner:
        raise SystemExit(f"loader banner missing: {banner[-400:]}")
    revoked = plane.submit_governance(rows.load("revoke.json"), rows.sig("revoke.sig.json"), now=meta["now"])
    adapter.on_governance(revoked, "revoke")
    blocked = rows.start_loader(adapter)
    if blocked["rc"] != 0:
        raise SystemExit(f"enforce loader {blocked['rc']}")
    return _wait_readiness_log()


def _grub_cfg_paths() -> list[Path]:
    found: list[Path] = []
    for root in (Path("/boot/grub"), Path("/boot/efi")):
        if root.is_dir():
            found.extend(sorted(path for path in root.rglob("grub.cfg") if path.is_file()))
    return found


def _cfg_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _cloud_init_wait() -> str:
    """Finish cloud-init before editing grub. A late module rewrites the cloud image line."""
    try:
        proc = subprocess.run(
            ["cloud-init", "status", "--wait"],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return type(exc).__name__
    return ((proc.stdout or "") + (proc.stderr or "")).strip()[-200:]


def _run_update_grub() -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(["update-grub"], capture_output=True, text=True)
    if proc.returncode != 0:
        proc = subprocess.run(["grub-mkconfig", "-o", "/boot/grub/grub.cfg"], capture_output=True, text=True)
    return proc


def apply_consented_lsm(lsm_value: str) -> dict:
    """Write the consented lsm= list into grub. Restore the files if update-grub fails."""
    cloud_init = _cloud_init_wait()
    main_path = Path("/etc/default/grub")
    if not main_path.is_file():
        return {"updated": False, "error": "grub_missing"}
    extra_dir = Path("/etc/default/grub.d")
    extra_paths = sorted(extra_dir.glob("*.cfg")) if extra_dir.is_dir() else []
    main = main_path.read_text(encoding="utf-8")
    extras = [path.read_text(encoding="utf-8") for path in extra_paths]
    planned = baseline_diag.plan_grub_lsm(main, extras, lsm_value)
    if planned.get("error"):
        return {"updated": False, "error": planned["error"]}
    backup = Path("/var/lib/vantio-lab")
    backup.mkdir(parents=True, exist_ok=True)
    (backup / "grub-default.bak").write_text(main, encoding="utf-8")
    main_path.write_text(planned["main"], encoding="utf-8")
    for path, text in zip(extra_paths, planned["extras"]):
        path.write_text(baseline_diag.assignments_with_lsm(text, lsm_value), encoding="utf-8")
    extra_dir.mkdir(parents=True, exist_ok=True)
    dropin = extra_dir / "99-vantio-lsm.cfg"
    prior_dropin = dropin.read_text(encoding="utf-8") if dropin.is_file() else None
    dropin.write_text(baseline_diag.lsm_dropin_text(lsm_value), encoding="utf-8")
    dropin.chmod(0o755)
    reboot_script = backup / "reboot-with-grub.sh"
    reboot_script.write_text(baseline_diag.reboot_with_grub_script(lsm_value), encoding="utf-8")
    reboot_script.chmod(0o755)

    def restore() -> None:
        main_path.write_text(main, encoding="utf-8")
        for path, text in zip(extra_paths, extras):
            path.write_text(text, encoding="utf-8")
        if prior_dropin is None:
            dropin.unlink(missing_ok=True)
        else:
            dropin.write_text(prior_dropin, encoding="utf-8")
            dropin.chmod(0o755)

    proc = _run_update_grub()
    if proc.returncode != 0:
        restore()
        tail = ((proc.stdout or "") + (proc.stderr or ""))[-500:]
        return {"updated": False, "error": "update_grub", "tail": tail, "cloud_init": cloud_init}
    sealed = baseline_diag.seal_firmware_tree(Path("/"), lsm_value, mount=True)
    bootchain = sealed.get("bootchain") if isinstance(sealed.get("bootchain"), dict) else {}
    if not sealed.get("ok"):
        restore()
        _run_update_grub()
        return {
            "updated": False,
            "error": sealed.get("error") or "firmware_seal",
            "dropin": "99-vantio-lsm.cfg",
            "efi_grub": str(bootchain.get("efi_head") or "")[:400],
            "linux_lines": [],
            "bootchain": bootchain,
            "cloud_init": cloud_init,
            "update_grub_tail": ((proc.stdout or "") + (proc.stderr or ""))[-400:],
        }
    linux_lines: list[str] = []
    efi_stub = ""
    saw_linux = False
    missing = False
    for path in _grub_cfg_paths():
        text = _cfg_text(path)
        line = baseline_diag.first_linux_line(text)
        if "efi" in path.as_posix() and not line:
            efi_stub = text[:400]
            continue
        if not line:
            continue
        saw_linux = True
        linux_lines.append(f"{path}: {line[:480]}")
        if not baseline_diag.grub_cfg_has_lsm(text, lsm_value):
            missing = True
    if not saw_linux or missing:
        restore()
        _run_update_grub()
        return {
            "updated": False,
            "error": "grub_cfg_missing_lsm",
            "dropin": "99-vantio-lsm.cfg",
            "efi_grub": efi_stub or str(bootchain.get("efi_head") or "")[:400],
            "linux_lines": linux_lines[:4],
            "bootchain": bootchain,
            "cloud_init": cloud_init,
            "update_grub_tail": ((proc.stdout or "") + (proc.stderr or ""))[-400:],
        }
    return {
        "updated": True,
        "error": "",
        "dropin": "99-vantio-lsm.cfg",
        "efi_grub": efi_stub or str(bootchain.get("efi_head") or "")[:400],
        "linux_lines": linux_lines[:4],
        "bootchain": bootchain,
        "cloud_init": cloud_init,
        "update_grub_tail": ((proc.stdout or "") + (proc.stderr or ""))[-400:],
    }


def _refusal_log() -> str:
    """One enforce start. On a stock image this exits before any program is pinned."""
    rows.ensure_cgroups()
    ensure_lab_iface()
    meta = rows.load("meta.json")
    plane = ControlPlane(LocalHostVerifier(load_packaged_test_trust()), root_ids=("cust-root", "cust-b"))
    adapter = PeHostAdapter(plane)
    opened = plane.submit_activation(rows.load("activation.json"), rows.sig("activation.sig.json"))
    adapter.on_activation(opened, plane.policy)
    granted = plane.submit_governance(rows.load("grant.json"), rows.sig("grant.sig.json"), now=meta["now"])
    adapter.on_governance(granted, "grant")
    rows.LAB.mkdir(parents=True, exist_ok=True)
    (rows.LAB / "evidence").mkdir(parents=True, exist_ok=True)
    (rows.LAB / "d").mkdir(parents=True, exist_ok=True)
    rows.DENY.write_text("lab-deny-marker\n", encoding="utf-8")
    os.chmod(rows.DENY, 0o644)
    rows.sudo(["mkdir", "-p", rows.ANCHOR])
    revoked = plane.submit_governance(rows.load("revoke.json"), rows.sig("revoke.sig.json"), now=meta["now"])
    adapter.on_governance(revoked, "revoke")
    ensure_lab_iface()
    blocked = rows.start_loader(adapter)
    if blocked["rc"] != 0:
        raise SystemExit(f"enforce loader {blocked['rc']}")
    return _wait_readiness_log()


def run_lsm_guard() -> dict:
    """Prove the stock host refuses, then write the consented lab cmdline."""
    facts = kernel_facts()
    stock = facts["lsm"]
    body = {
        "battery": "lsm-guard",
        "stock_lsm": stock,
        "stock_bpf_lsm": baseline_diag.bpf_lsm_active(stock),
        "distro": facts["distro"],
        "kernel": facts["kernel"],
        "image_id": os.environ.get("VANTIO_IMAGE_ID", ""),
        "image_name": facts.get("image_name") or "",
        "lockdown": facts.get("lockdown") or "",
        "cmdline": Path("/proc/cmdline").read_text(encoding="utf-8").strip() if Path("/proc/cmdline").is_file() else "",
        "boot_id": baseline_diag.read_boot_id(),
        "kernel_command_lines": baseline_diag.read_kernel_command_lines(),
        "grubenv": baseline_diag.read_grubenv_assignments(),
        "reboot_requested": False,
        "lab_pass": False,
        "customer_claim": False,
    }
    if body["stock_bpf_lsm"]:
        body["host_result"] = "LSM_ALREADY_ACTIVE"
        body["reason"] = "stock_bpf_lsm"
        return body
    log = _refusal_log()
    verdict = baseline_diag.classify_readiness_log(log)
    body["readiness"] = verdict
    body["loader_log_tail"] = log[-2000:]
    body["egress_present"] = "status=present" in log
    body["bpf_pins"] = vantio_bpf_pins()
    rows.sudo(["docker", "rm", "-f", rows.LOADER], timeout=40)
    action = baseline_diag.lsm_guard_action(
        verdict,
        stock_lsm=stock,
        bpf_pins=body["bpf_pins"],
        egress_present=body["egress_present"],
    )
    if not action["write_grub"]:
        body["host_result"] = action["host_result"]
        body["reason"] = action["reason"]
        return body
    lsm_value = action["lsm_value"]
    applied = apply_consented_lsm(lsm_value)
    applied["boot_files"] = baseline_diag.boot_file_manifest(Path("/"))
    body["lsm_value"] = lsm_value
    body["grub"] = {
        key: applied[key]
        for key in (
            "updated",
            "error",
            "linux_lines",
            "efi_grub",
            "bootchain",
            "cloud_init",
            "update_grub_tail",
            "boot_files",
        )
        if key in applied
    }
    if not applied.get("updated"):
        body["host_result"] = "FAIL"
        body["reason"] = applied.get("error") or "update_grub"
        return body
    requested = baseline_diag.reboot_after_grub(action, True)
    if not requested:
        body["host_result"] = "FAIL"
        body["reason"] = "grub_cfg_missing_lsm"
        body["reboot_requested"] = False
        return body
    stock_path = baseline_diag.LSM_STOCK_PATH
    stock_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "stock_lsm": stock,
        "stock_bpf_lsm": False,
        "lsm_value": lsm_value,
        "image_id": body["image_id"],
        "image_name": body.get("image_name") or "",
        "lockdown": body.get("lockdown") or "",
        "distro": facts["distro"],
        "kernel": facts["kernel"],
        "reboot_requested": True,
        "guard_proved": True,
    }
    record_text = json.dumps(record, indent=2) + "\n"
    stock_path.write_text(record_text, encoding="utf-8")
    try:
        baseline_diag.LSM_BOOT_MARK.write_text(record_text, encoding="utf-8")
    except OSError:
        pass
    body["reboot_requested"] = requested
    body["host_result"] = "GUARD_PROVED"
    body["reason"] = action["reason"]
    return body


RUNNERS = {
    "r15-container-exit": run_r15,
    "2c-upgrade-rollback": run_2c,
    "2d-crash-recovery": run_2d,
    "2e-performance": run_2e,
    "2f-tamper": run_2f,
    "2g-distro": run_2g,
    "lsm-guard": run_lsm_guard,
}


def main() -> int:
    if os.uname().nodename == "phantom-box":
        raise SystemExit("refusing host")
    runner = RUNNERS.get(MODE)
    if runner is None:
        publish({"battery": MODE, "host_result": "FAIL", "reason": "unknown_battery", "lab_pass": False})
        return 1
    try:
        body = runner()
    except SystemExit as exc:
        publish({"battery": MODE, "harness_error": f"SystemExit {exc.code}", "lab_pass": False, "host_result": "FAIL"})
        return 1
    except Exception:
        publish({"battery": MODE, "harness_error": traceback.format_exc(), "lab_pass": False, "host_result": "FAIL"})
        return 1
    publish(body)
    if body.get("host_result") == "NOT_GRADED":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
