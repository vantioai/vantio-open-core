#!/usr/bin/env python3
"""Clean-host phase batteries on the working seal.

The runner has already loaded the seal and extracted the contract. This
script starts the loader the same way the descendant battery does, measures
one phase, and writes /tmp/enterprise-pe-rows.json. It does not fetch, and
it does not treat a same-seal reload as an upgrade.

Audience: INTERNAL_RESTRICTED
"""

from __future__ import annotations

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

import guest_rows as rows  # noqa: E402
import phase2_grade as grade  # noqa: E402
from vantio_enterprise_protocol.control import ControlPlane  # noqa: E402
from vantio_enterprise_protocol.host_adapter import LocalHostVerifier  # noqa: E402
from vantio_enterprise_protocol.pe_adapter import PeHostAdapter  # noqa: E402
from vantio_enterprise_protocol.trust import load_packaged_test_trust  # noqa: E402

OUT_PATH = Path("/tmp/enterprise-pe-rows.json")
SUBJECT = 65534
LAB_UDP = ("192.0.2.2", 9)


def publish(body: dict) -> None:
    text = json.dumps(body, indent=2) + "\n"
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


def attributed(pid: int, action: str) -> bool:
    for item in events():
        raw = item.get("Pid")
        if raw == pid and item.get("ActionTaken") == action:
            return True
    return False


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
    (rows.LAB / "d").mkdir(parents=True, exist_ok=True)
    rows.DENY.write_text("lab-deny-marker\n", encoding="utf-8")
    os.chmod(rows.DENY, 0o644)
    rows.sudo(["mkdir", "-p", rows.ANCHOR])
    started = rows.start_loader(adapter)
    if started["rc"] != 0:
        raise SystemExit(f"loader {started['rc']}")
    banner = rows.wait_banner("AUDIT (log only)")
    if "AUDIT (log only)" not in banner:
        raise SystemExit("loader banner missing")
    revoked = plane.submit_governance(rows.load("revoke.json"), rows.sig("revoke.sig.json"), now=meta["now"])
    adapter.on_governance(revoked, "revoke")
    digest = adapter.state.policy_digest or ""
    blocked = rows.start_loader(adapter)
    if blocked["rc"] != 0:
        raise SystemExit(f"enforce loader {blocked['rc']}")
    scoped = rows.wait_banner("SCOPED (drop enrolled)")
    if "SCOPED (drop enrolled)" not in scoped:
        raise SystemExit("scoped banner missing")
    return adapter, digest


def child_open(enroll: bool) -> dict:
    report_r, report_w = os.pipe()
    child = os.fork()
    if child == 0:
        os.close(report_r)
        try:
            if enroll:
                (Path(rows.ANCHOR) / "cgroup.procs").write_text(f"{os.getpid()}\n", encoding="utf-8")
            os.setresuid(SUBJECT, SUBJECT, 0)
            try:
                fd = os.open(str(rows.DENY), os.O_RDONLY)
                os.close(fd)
                errno = 0
            except OSError as exc:
                errno = exc.errno or 1
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.sendto(b"x", LAB_UDP)
                net = 0
            except OSError as exc:
                net = exc.errno or 1
            finally:
                sock.close()
        except OSError as exc:
            errno = exc.errno or 1
            net = exc.errno or 1
        os.write(report_w, f"file {errno} net {net} pid {os.getpid()}\n".encode())
        os._exit(0)
    os.close(report_w)
    os.waitpid(child, 0)
    text = os.read(report_r, 200).decode(errors="replace")
    os.close(report_r)
    body = {"file_errno": None, "net_errno": None, "pid": None}
    parts = text.split()
    if len(parts) == 6 and parts[0] == "file" and parts[2] == "net" and parts[4] == "pid":
        body["file_errno"] = int(parts[1])
        body["net_errno"] = int(parts[3])
        body["pid"] = int(parts[5])
    return body


def kill_loader() -> int:
    proc = rows.sudo(["pkill", "-9", "-x", "vantio-loader"])
    time.sleep(1.0)
    return proc.returncode


def loader_running() -> bool:
    return rows.run(["pgrep", "-x", "vantio-loader"]).returncode == 0


def image_id() -> str:
    proc = rows.sudo(["docker", "image", "inspect", "--format", "{{.Id}}", rows.IMAGE])
    return (proc.stdout or "").strip()


def run_2c() -> dict:
    tar = HERE / "seal.oci.tar"
    seal_sha = hashlib.sha256(tar.read_bytes()).hexdigest()
    before = image_id()
    loaded = rows.sudo(["docker", "load", "-i", str(tar)])
    if loaded.returncode != 0:
        raise SystemExit("reload")
    after = image_id()
    adapter, digest = prepare_enforce()
    first = child_open(True)
    kill_loader()
    restarted = rows.start_loader(adapter)
    if restarted["rc"] != 0:
        raise SystemExit(f"restart loader {restarted['rc']}")
    scoped = rows.wait_banner("SCOPED (drop enrolled)")
    if "SCOPED (drop enrolled)" not in scoped:
        raise SystemExit("restart banner missing")
    second = child_open(True)
    graded = grade.grade_upgrade(
        seal_sha256=seal_sha,
        image_before=before,
        image_after=after,
        deny_before=first.get("file_errno"),
        deny_after=second.get("file_errno"),
    )
    graded["policy_digest"] = digest
    graded["deny_before"] = first
    graded["deny_after"] = second
    graded["attributed_before"] = isinstance(first.get("pid"), int) and attributed(first["pid"], "DENIED")
    return graded


def run_2d() -> dict:
    _adapter, digest = prepare_enforce()
    up = child_open(True)
    kill_loader()
    if loader_running():
        raise SystemExit("loader_still_up")
    enrolled = child_open(True)
    unenrolled = child_open(False)
    graded = grade.grade_crash(
        enrolled_errno=enrolled.get("net_errno"),
        unenrolled_errno=unenrolled.get("net_errno"),
    )
    graded["policy_digest"] = digest
    graded["while_loader_up"] = up
    graded["enrolled_after"] = enrolled
    graded["unenrolled_after"] = unenrolled
    graded["file_after_enrolled"] = enrolled.get("file_errno")
    return graded


def run_2e() -> dict:
    _adapter, digest = prepare_enforce()
    started = time.monotonic()
    samples = [child_open(True) for _ in range(100)]
    runtime = time.monotonic() - started
    graded = grade.grade_performance(runtime_seconds=runtime, host_count=1, sample_count=len(samples))
    denied = sum(1 for item in samples if item.get("file_errno") == 13)
    graded["policy_digest"] = digest
    graded["denied_samples"] = denied
    return graded


def run_2f() -> dict:
    _adapter, digest = prepare_enforce()
    kill_loader()
    still = loader_running()
    enrolled = child_open(True)
    unenrolled = child_open(False)
    pins = []
    root = Path("/sys/fs/bpf")
    if root.is_dir():
        pins = [str(path) for path in root.rglob("*") if path.is_file()][:5]
    graded = grade.grade_tamper(
        enrolled_errno=enrolled.get("net_errno"),
        unenrolled_errno=unenrolled.get("net_errno"),
        loader_up=still,
    )
    graded["policy_digest"] = digest
    graded["enrolled_after"] = enrolled
    graded["unenrolled_after"] = unenrolled
    graded["bpf_pin_sample"] = pins
    graded["policy_malformed"] = False
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
        "cgroup_v2": Path("/sys/fs/cgroup/cgroup.controllers").is_file(),
        "bpffs": "bpf" in Path("/proc/mounts").read_text(encoding="utf-8", errors="replace"),
    }


def remove_loader() -> bool:
    kill_loader()
    rows.sudo(["docker", "rm", "-f", "vantio-pe-lab"])
    rows.sudo(["docker", "rmi", rows.IMAGE])
    time.sleep(0.5)
    return not loader_running()


def run_2g() -> dict:
    facts = kernel_facts()
    _adapter, digest = prepare_enforce()
    enrolled = child_open(True)
    time.sleep(0.4)
    unenrolled = child_open(False)
    removed = remove_loader()
    pid = enrolled.get("pid")
    measured = {
        "live_probe": True,
        "distro": facts["distro"],
        "kernel": facts["kernel"],
        "btf": facts["btf"],
        "lsm": facts["lsm"],
        "seal": grade.WORKING_SEAL,
        "enrolled_errno": enrolled.get("file_errno"),
        "unenrolled_errno": unenrolled.get("file_errno"),
        "removed": removed,
        "descendant_pass": False,
        "docker_child_pass": False,
        "ami": os.environ.get("VANTIO_IMAGE_ID", ""),
    }
    graded = grade.grade_distro(measured)
    graded["kernel_facts"] = facts
    graded["policy_digest"] = digest
    graded["enrolled"] = enrolled
    graded["unenrolled"] = unenrolled
    graded["attributed"] = isinstance(pid, int) and attributed(pid, "DENIED")
    return graded


RUNNERS = {
    "2c-upgrade-rollback": run_2c,
    "2d-crash-recovery": run_2d,
    "2e-performance": run_2e,
    "2f-tamper": run_2f,
    "2g-distro": run_2g,
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
