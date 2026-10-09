#!/usr/bin/env python3
"""Descendant deny on the working seal, then the same deny after reboot.

Each topology must deny uid 65534 on the protected file and produce a block
event that names that pid and the policy digest. An unenrolled control and a
cgroup nine levels below the anchor must be allowed. Anything that does not
run is a failure of this battery, not a pass.

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
import traceback
from pathlib import Path

STAGE = Path(sys.argv[1] if len(sys.argv) > 1 else "/opt/vantio-enterprise")
PHASE = sys.argv[2] if len(sys.argv) > 2 else "pre"
sys.argv = [sys.argv[0], str(STAGE)]
sys.path.insert(0, str(STAGE))

import guest_rows as rows  # noqa: E402
from vantio_enterprise_protocol.control import ControlPlane  # noqa: E402
from vantio_enterprise_protocol.host_adapter import LocalHostVerifier  # noqa: E402
from vantio_enterprise_protocol.pe_adapter import (  # noqa: E402
    PeHostAdapter,
    revoke_deny_event_links_digest,
)
from vantio_enterprise_protocol.trust import load_packaged_test_trust  # noqa: E402

PRE_PATH = Path("/var/lib/vantio-lab/b1-pre.json")
OUT_PATH = Path("/tmp/enterprise-pe-rows.json")
SUBJECT = 65534
REPEATS = 3
PROBE = Path(os.environ.get("VANTIO_PROBE", "/var/lib/vantio-lab/guest/descendant_probe"))
OUTSIDE = Path("/sys/fs/cgroup/vantio-pe-outside")
CLONE_INTO_CGROUP = 0x200000000
CLONE_NEWUSER = 0x10000000
CLONE_NEWNS = 0x00020000


def boot_id() -> str:
    return Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()


def nested(depth: int) -> Path:
    path = Path(rows.ANCHOR)
    for name in ("l1", "l2", "l3", "l4", "l5", "l6", "l7", "l8", "l9")[:depth]:
        path = path / name
    return path


def ensure_net() -> None:
    if rows.run(["ip", "link", "show", "vlab-host"]).returncode == 0:
        return
    rows.sudo(["ip", "link", "add", "vlab-host", "type", "veth", "peer", "name", "vlab-peer"])
    rows.sudo(["ip", "addr", "add", "192.0.2.1/30", "dev", "vlab-host"])
    rows.sudo(["ip", "link", "set", "vlab-host", "up"])
    rows.sudo(["ip", "netns", "add", "pelab-ns"])
    rows.sudo(["ip", "link", "set", "vlab-peer", "netns", "pelab-ns"])
    rows.sudo(["ip", "netns", "exec", "pelab-ns", "ip", "link", "set", "lo", "up"])
    rows.sudo(["ip", "netns", "exec", "pelab-ns", "ip", "addr", "add", "192.0.2.2/30", "dev", "vlab-peer"])
    rows.sudo(["ip", "netns", "exec", "pelab-ns", "ip", "link", "set", "vlab-peer", "up"])


def move_pid(pid: int, cgroup: Path) -> int:
    try:
        (cgroup / "cgroup.procs").write_text(f"{pid}\n")
    except OSError as exc:
        return exc.errno or 1
    return 0


def child_act(path: Path, *, setsid: bool, unshare: bool) -> None:
    if unshare:
        libc = ctypes.CDLL(None, use_errno=True)
        libc.unshare(CLONE_NEWNS)
        libc.unshare(CLONE_NEWUSER)
    if setsid:
        os.setsid()
    try:
        os.setresuid(SUBJECT, SUBJECT, 0)
    except OSError as exc:
        os.write(1, f"setuid {exc.errno}\n".encode())
        os._exit(0)
    file_errno = 0
    try:
        with path.open("rb") as handle:
            handle.read(1)
    except OSError as exc:
        file_errno = exc.errno or 1
    net_errno = 0
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(b"x", ("192.0.2.2", 9))
        sock.close()
    except OSError as exc:
        net_errno = exc.errno or 1
    os.write(1, f"file {file_errno} net {net_errno} pid {os.getpid()}\n".encode())
    os._exit(0)


def read_result(report_r: int) -> dict:
    text = os.read(report_r, 400).decode(errors="replace").strip()
    body = {"detail": text, "file_errno": None, "net_errno": None, "pid": None}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 6 and parts[0] == "file" and parts[2] == "net" and parts[4] == "pid":
            body["file_errno"] = int(parts[1])
            body["net_errno"] = int(parts[3])
            body["pid"] = int(parts[5])
        elif parts and parts[0] in ("setuid", "spawn", "clone3", "unshare_mnt", "unshare_user", "setsid"):
            body["setup"] = line
    return body


def fork_case(place, *, setsid: bool = False, unshare: bool = False) -> dict:
    report_r, report_w = os.pipe()
    go_r, go_w = os.pipe()
    child = os.fork()
    if child == 0:
        os.close(report_r)
        os.close(go_w)
        os.dup2(report_w, 1)
        os.close(report_w)
        os.read(go_r, 1)
        os.close(go_r)
        child_act(rows.DENY, setsid=setsid, unshare=unshare)
    os.close(report_w)
    os.close(go_r)
    move_errno = place(child)
    os.write(go_w, b"x")
    os.close(go_w)
    os.waitpid(child, 0)
    body = read_result(report_r)
    os.close(report_r)
    body["move_errno"] = move_errno
    return body


def clone3_case() -> dict:
    report_r, report_w = os.pipe()
    go_r, go_w = os.pipe()
    cgroup_fd = os.open(rows.ANCHOR, os.O_RDONLY | os.O_DIRECTORY)

    class CloneArgs(ctypes.Structure):
        _fields_ = [
            ("flags", ctypes.c_uint64),
            ("pidfd", ctypes.c_uint64),
            ("child_tid", ctypes.c_uint64),
            ("parent_tid", ctypes.c_uint64),
            ("exit_signal", ctypes.c_uint64),
            ("stack", ctypes.c_uint64),
            ("stack_size", ctypes.c_uint64),
            ("tls", ctypes.c_uint64),
            ("set_tid", ctypes.c_uint64),
            ("set_tid_size", ctypes.c_uint64),
            ("cgroup", ctypes.c_uint64),
        ]

    args = CloneArgs()
    args.flags = CLONE_INTO_CGROUP
    args.exit_signal = 17
    args.cgroup = cgroup_fd
    libc = ctypes.CDLL(None, use_errno=True)
    pid = libc.syscall(435, ctypes.byref(args), ctypes.sizeof(args))
    err = ctypes.get_errno()
    os.close(cgroup_fd)
    if pid < 0:
        os.close(report_w)
        os.close(go_w)
        os.close(go_r)
        os.close(report_r)
        return {"detail": f"clone3 {err}", "file_errno": None, "net_errno": None, "pid": None, "move_errno": err}
    if pid == 0:
        os.close(report_r)
        os.close(go_w)
        os.dup2(report_w, 1)
        os.close(report_w)
        os.read(go_r, 1)
        os.close(go_r)
        child_act(rows.DENY, setsid=False, unshare=False)
    os.close(report_w)
    os.close(go_r)
    os.write(go_w, b"x")
    os.close(go_w)
    os.waitpid(pid, 0)
    body = read_result(report_r)
    os.close(report_r)
    body["move_errno"] = 0
    return body


def double_fork_case(*, reparent: bool) -> dict:
    report_r, report_w = os.pipe()
    mid = os.fork()
    if mid == 0:
        move_pid(os.getpid(), Path(rows.ANCHOR))
        child = os.fork()
        if child == 0:
            grand = os.fork()
            if grand == 0:
                os.dup2(report_w, 1)
                os.close(report_w)
                os.close(report_r)
                if reparent:
                    # Let the intermediate parent exit before the open.
                    time.sleep(0.2)
                child_act(rows.DENY, setsid=False, unshare=False)
            os.close(report_w)
            os.close(report_r)
            if reparent:
                os._exit(0)
            os.waitpid(grand, 0)
            os._exit(0)
        os.waitpid(child, 0)
        os._exit(0)
    os.close(report_w)
    os.waitpid(mid, 0)
    body = read_result(report_r)
    os.close(report_r)
    body["move_errno"] = 0
    return body


def vfork_case() -> dict:
    if not PROBE.is_file():
        return {"detail": "probe_missing", "file_errno": None, "net_errno": None, "pid": None, "move_errno": 1}
    held_r, held_w = os.pipe()
    parent = os.fork()
    if parent == 0:
        os.close(held_r)
        move_pid(os.getpid(), Path(rows.ANCHOR))
        proc = subprocess.run([str(PROBE), str(rows.DENY)], text=True, capture_output=True)
        os.write(held_w, (proc.stdout or proc.stderr or "").encode())
        os.close(held_w)
        os._exit(0)
    os.close(held_w)
    os.waitpid(parent, 0)
    body = read_result(held_r)
    os.close(held_r)
    body["move_errno"] = 0
    return body


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


def file_denied(digest: str, pid: int) -> bool:
    for item in events():
        if item.get("Pid") != pid:
            continue
        if revoke_deny_event_links_digest(
            item,
            policy_digest=digest,
            subject_uid=SUBJECT,
            blocked_path=str(rows.DENY),
        ):
            return True
    return False


def egress_denied(digest: str, pid: int) -> bool:
    for item in events():
        if item.get("Pid") != pid:
            continue
        if item.get("ActionTaken") != "BLOCKED":
            continue
        if item.get("EventType") not in ("NETWORK_BLOCK", "CGROUP_BLOCK"):
            continue
        if item.get("policy_digest") == digest:
            return True
    return False


def file_allowed(pid: int) -> bool:
    for item in events():
        if item.get("Pid") == pid and item.get("ActionTaken") in ("DENIED", "BLOCKED"):
            if item.get("EventType") in ("SYSCALL_OPENAT", "NETWORK_BLOCK", "CGROUP_BLOCK"):
                return False
    return True


def score(name: str, observed: dict, digest: str, *, expect_deny: bool) -> dict:
    pid = observed.get("pid")
    file_errno = observed.get("file_errno")
    if pid is None or file_errno is None:
        return {"name": name, "pass": False, "expect_deny": expect_deny, "observed": observed, "reason": "no_sample"}
    if expect_deny:
        ok = file_errno == 13 and file_denied(digest, pid) and egress_denied(digest, pid)
    else:
        ok = file_errno == 0 and file_allowed(pid)
    return {
        "name": name,
        "pass": ok,
        "expect_deny": expect_deny,
        "file_errno": file_errno,
        "net_errno": observed.get("net_errno"),
        "pid": pid,
        "file_event": file_denied(digest, pid) if expect_deny else None,
        "egress_event": egress_denied(digest, pid) if expect_deny else None,
        "observed": observed,
    }


def one_round(digest: str) -> list[dict]:
    anchor = Path(rows.ANCHOR)
    outside = OUTSIDE
    outside.mkdir(parents=True, exist_ok=True)
    cases = [
        ("moved", lambda: fork_case(lambda pid: move_pid(pid, anchor)), True),
        ("clone3", clone3_case, True),
        ("reparent", lambda: double_fork_case(reparent=True), True),
        ("double_fork", lambda: double_fork_case(reparent=False), True),
        ("setsid", lambda: fork_case(lambda pid: move_pid(pid, anchor), setsid=True), True),
        ("unshare", lambda: fork_case(lambda pid: move_pid(pid, anchor), unshare=True), True),
        ("vfork", vfork_case, True),
        ("ancestor_8", lambda: fork_case(lambda pid: move_pid(pid, nested(8))), True),
        ("ancestor_9", lambda: fork_case(lambda pid: move_pid(pid, nested(9))), False),
        ("unenrolled", lambda: fork_case(lambda pid: 0), False),
    ]
    scored = []
    for name, fn, expect_deny in cases:
        observed = fn()
        # Give the ring a moment to flush.
        time.sleep(0.3)
        scored.append(score(name, observed, digest, expect_deny=expect_deny))
    return scored


def uid0_open() -> dict:
    try:
        with rows.DENY.open("rb") as handle:
            handle.read(1)
        return {"errno": 0}
    except OSError as exc:
        return {"errno": exc.errno}


def prepare_enforce() -> tuple[PeHostAdapter, str]:
    rows.ensure_cgroups()
    ensure_net()
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
    rows.DENY.write_text("lab-deny-marker\n")
    os.chmod(rows.LAB, 0o755)
    os.chmod(rows.LAB / "d", 0o755)
    os.chmod(rows.DENY, 0o644)
    rows.sudo(["mkdir", "-p", rows.ANCHOR])
    started = rows.start_loader(adapter)
    if started["rc"] != 0:
        raise SystemExit(f"loader {started['rc']}")
    rows.wait_banner("AUDIT (log only)")
    revoked = plane.submit_governance(rows.load("revoke.json"), rows.sig("revoke.sig.json"), now=meta["now"])
    adapter.on_governance(revoked, "revoke")
    digest = adapter.state.policy_digest or ""
    blocked = rows.start_loader(adapter)
    if blocked["rc"] != 0:
        raise SystemExit(f"enforce loader {blocked['rc']}")
    rows.wait_banner("SCOPED (drop enrolled)")
    return adapter, digest


def measure(phase: str) -> dict:
    node = os.uname().nodename
    if node == "phantom-box":
        raise SystemExit(f"refusing host {node}")
    _adapter, digest = prepare_enforce()
    rounds = []
    for _ in range(REPEATS):
        rounds.append(one_round(digest))
    names = [item["name"] for item in rounds[0]]
    stable = []
    for name in names:
        samples = []
        for rnd in rounds:
            samples.extend(item for item in rnd if item["name"] == name)
        stable.append({
            "name": name,
            "pass": all(item["pass"] for item in samples),
            "runs": len(samples),
            "samples": samples,
        })
    root_open = uid0_open()
    return {
        "phase": phase,
        "hostname": node,
        "image": rows.IMAGE,
        "boot_id": boot_id(),
        "policy_digest": digest,
        "repeats": REPEATS,
        "cases": stable,
        "uid0_open": root_open,
        "descendant_pass": all(item["pass"] for item in stable) and root_open.get("errno") == 0,
    }


def _publish(body: dict) -> None:
    text = json.dumps(body, indent=2) + "\n"
    OUT_PATH.write_text(text, encoding="utf-8")
    try:
        os.chmod(OUT_PATH, 0o644)
    except OSError:
        pass
    print(text, flush=True)


def main() -> int:
    try:
        code = _main()
    except SystemExit as exc:
        _publish({"harness_error": f"SystemExit {exc.code}", "detail": str(exc)})
        raise
    except Exception:
        _publish({"harness_error": traceback.format_exc()})
        return 1
    print(f"DESCENDANT_EXIT {code}", flush=True)
    return code


def _main() -> int:
    if PHASE == "pre":
        body = measure("pre")
        PRE_PATH.parent.mkdir(parents=True, exist_ok=True)
        PRE_PATH.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
        _publish({"pre": body, "reboot_requested": True})
        os.sync()
        return 0 if body["descendant_pass"] else 1
    pre = {}
    if PRE_PATH.is_file():
        pre = json.loads(PRE_PATH.read_text(encoding="utf-8"))
    post = measure("post")
    same_boot = pre.get("boot_id") == post.get("boot_id")
    result = {
        "battery": "descendant-b1",
        "pre": pre,
        "post": post,
        "reboot_observed": bool(pre) and not same_boot,
        "descendant_pass": bool(pre.get("descendant_pass")) and bool(post.get("descendant_pass")),
        "b1_pass": bool(pre.get("descendant_pass")) and bool(post.get("descendant_pass")) and not same_boot,
        "coverage_note": "A case with pass false is a failure. A topology absent from cases was not run.",
    }
    _publish(result)
    return 0 if result["b1_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
