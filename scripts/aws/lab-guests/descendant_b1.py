#!/usr/bin/env python3
"""Moved-child deny on the policy-allow seal, then the same deny after reboot.

A pass is uid 65534 errno 13 on /var/lib/vantio-pe-clean-host/d/secret and a
DENIED event whose Pid is that child. Uid 0 may still open. That open is
recorded and does not count as the descendant pass.

Audience: INTERNAL_RESTRICTED
"""

from __future__ import annotations

import json
import os
import sys
import time
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


def boot_id() -> str:
    return Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()


def moved_child() -> dict:
    """Move a child into the enrolled cgroup, then let it open the ceiling file."""
    report_r, report_w = os.pipe()
    go_r, go_w = os.pipe()
    child = os.fork()
    if child == 0:
        os.close(report_r)
        os.close(go_w)
        os.read(go_r, 1)
        os.close(go_r)
        try:
            os.setresuid(SUBJECT, SUBJECT, 0)
        except OSError as exc:
            os.write(report_w, f"setuid_failed {exc.errno}\n".encode())
            os.close(report_w)
            os._exit(0)
        try:
            with rows.DENY.open("rb") as handle:
                handle.read(1)
            text = f"open_ok 0 {os.getpid()}\n"
        except OSError as exc:
            text = f"open_error {exc.errno} {os.getpid()}\n"
        os.write(report_w, text.encode())
        os.close(report_w)
        os._exit(0)
    os.close(report_w)
    os.close(go_r)
    moved = True
    try:
        (Path(rows.ANCHOR) / "cgroup.procs").write_text(f"{child}\n")
    except OSError as exc:
        moved = False
        move_errno = exc.errno
    else:
        move_errno = 0
    os.write(go_w, b"x")
    os.close(go_w)
    os.waitpid(child, 0)
    text = os.read(report_r, 200).decode().strip()
    os.close(report_r)
    parts = text.split()
    body: dict = {
        "child_pid": child,
        "moved": moved,
        "move_errno": move_errno,
        "detail": text,
    }
    if len(parts) >= 3 and parts[0] in ("open_ok", "open_error") and parts[1].lstrip("-").isdigit():
        body["result"] = parts[0]
        body["errno"] = int(parts[1])
        body["nobody_errno"] = int(parts[1])
    else:
        body["result"] = "probe_failed"
        body["errno"] = None
        body["nobody_errno"] = None
    return body


def linked_deny(digest: str, child_pid: int) -> dict:
    matched = []
    for item in rows.matching_events(digest):
        if not revoke_deny_event_links_digest(
            item,
            policy_digest=digest,
            subject_uid=SUBJECT,
            blocked_path=str(rows.DENY),
        ):
            continue
        if item.get("Pid") == child_pid:
            matched.append(item)
    return matched[-1] if matched else {}


def prepare_enforce() -> tuple[PeHostAdapter, str]:
    rows.ensure_cgroups()
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
    observed = {"result": "not_run", "errno": None, "child_pid": None}
    event: dict = {}
    for _ in range(40):
        observed = moved_child()
        if observed.get("nobody_errno") == 13 and observed.get("child_pid"):
            event = linked_deny(digest, int(observed["child_pid"]))
            if event:
                break
        time.sleep(0.25)
    attributable = bool(event) and event.get("Pid") == observed.get("child_pid")
    return {
        "phase": phase,
        "hostname": node,
        "image": rows.IMAGE,
        "boot_id": boot_id(),
        "seal_path": str(rows.DENY),
        "probe": observed,
        "block_event": event,
        "attributable": attributable,
        "nobody_errno": observed.get("nobody_errno"),
        "uid0_scope": "not_probed",
        "descendant_pass": observed.get("nobody_errno") == 13 and attributable,
    }


def main() -> int:
    if PHASE == "pre":
        body = measure("pre")
        PRE_PATH.parent.mkdir(parents=True, exist_ok=True)
        PRE_PATH.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
        OUT_PATH.write_text(json.dumps({"pre": body, "reboot_requested": True}, indent=2) + "\n", encoding="utf-8")
        os.sync()
        return 0
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
    }
    OUT_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
