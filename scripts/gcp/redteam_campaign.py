"""One offline red-team pass. GCP calls stay in offline_deliver.

The descendant battery runs first. Its JSON is graded and then removed.
Path, BPF, identity, and lab-veth rows run while the loader is up. The
packet is the only guest result that stays in the evidence directory.
"""

from __future__ import annotations

import json
import shutil
import time
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Mapping

import redteam_brain as rtbrain
import redteam_packet as packet


def _money(amount: Decimal) -> str:
    return format(amount.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP), "f")


def _read_remote(od: Any, project: str, name: str, remote: str, dest: Path) -> Any:
    if not od._scp_from(project, name, remote, dest):
        return None
    body = od._load_json_file(dest)
    dest.unlink(missing_ok=True)
    return body


def _boot_changed(od: Any, project: str, name: str, before: str) -> str:
    deadline = time.time() + od.SSH_WAIT_SECONDS
    while time.time() < deadline:
        probe = od._ssh(project, name, "cat /proc/sys/kernel/random/boot_id")
        boot = (probe.stdout or "").strip()
        if probe.returncode == 0 and od.reboot_ready(before, boot):
            return boot
        time.sleep(10)
    return ""


def execute(env: Mapping[str, str], od: Any) -> int:
    od._enabled(env)
    project = od.require_lab_project(env.get("GCP_LAB_PROJECT", ""))
    od._gate_ok(env)
    if not od.brain_requested(env):
        raise SystemExit("brain")
    seal = od.refuse_batteries(env)
    minutes = od.lab.bounded_minutes(env.get("STOP_AFTER_MINUTES", "90"))
    try:
        gross = rtbrain.assert_under_cap(rtbrain.BRAIN_MACHINE, minutes, rtbrain.BRAIN_DISK_GB)
        rtbrain.verify_files(Path(env.get("BRAIN_DIR", "")))
    except ValueError as exc:
        raise SystemExit("cost" if str(exc) == "cost" else "model_sha") from None
    name = od.instance_name(env.get("GITHUB_RUN_ID", ""))
    evidence = od._evidence_dir(env)
    brain_dir = Path(env.get("BRAIN_DIR", ""))
    payload_dir = Path(env.get("RUNNER_TEMP") or "/tmp") / "gcp-guest-payload"
    debs = od._stage_payload(env, payload_dir)
    shutil.copy2(brain_dir / rtbrain.MODEL_NAME, payload_dir / rtbrain.MODEL_NAME)
    shutil.copy2(brain_dir / rtbrain.RUNTIME_NAME, payload_dir / rtbrain.RUNTIME_NAME)
    shutil.copy2(Path(env["REDTEAM_ROWS"]), payload_dir / "redteam_rows.py")
    shutil.copy2(Path(env["REDTEAM_PACKET"]), payload_dir / "redteam_packet.py")
    raw_dir = Path(env.get("RUNNER_TEMP") or "/tmp") / "redteam-raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    descendant: Any = None
    guest: Any = None
    rebooted = False
    try:
        od._wait_until_running(project, name)
        made = od._ssh(project, name, f"rm -rf {od.GUEST_DIR} && mkdir -p {od.GUEST_DIR}")
        if made.returncode != 0:
            raise SystemExit("ssh")
        sources = [
            payload_dir / "seal.oci.tar",
            payload_dir / "contract.tar",
            payload_dir / "enterprise-rows.sh",
            payload_dir / "descendant_b1.py",
            payload_dir / "debs.tar",
            payload_dir / rtbrain.MODEL_NAME,
            payload_dir / rtbrain.RUNTIME_NAME,
            payload_dir / "redteam_rows.py",
            payload_dir / "redteam_packet.py",
        ]
        od._scp_to(project, name, sources)
        for local_name in ("seal.oci.tar", "contract.tar"):
            (payload_dir / local_name).unlink(missing_ok=True)
        before = od._wait_ssh(project, name, od.SSH_WAIT_SECONDS)
        pre = od._ssh(project, name, od.guest_command(seal, "descendant-b1", "pre"))
        pre_text = od.redact((pre.stdout or "") + (pre.stderr or ""))
        descendant = _read_remote(od, project, name, "/tmp/enterprise-pe-rows.json", raw_dir / "descendant.json")
        if "PY_RC=0" in pre_text:
            rebooted = bool(_boot_changed(od, project, name, before))
            if rebooted:
                od._ssh(project, name, od.guest_command(seal, "descendant-b1", "post"))
                descendant = _read_remote(
                    od, project, name, "/tmp/enterprise-pe-rows.json", raw_dir / "descendant.json"
                ) or descendant
        guest_cmd = f"python3 {od.GUEST_DIR}/redteam_rows.py /opt/vantio-enterprise"
        od._ssh(project, name, guest_cmd)
        guest = _read_remote(od, project, name, "/tmp/redteam-rows.json", raw_dir / "rows.json")
    finally:
        attempts: list[dict] = []
        if isinstance(descendant, dict):
            attempts.extend(packet.rows_from_descendant(descendant))
        if isinstance(guest, dict) and isinstance(guest.get("attempts"), list):
            attempts.extend(item for item in guest["attempts"] if isinstance(item, dict))
        attempts.extend(packet.installer_and_supply_rows(seal))
        if not rebooted:
            attempts.append(packet._row("pe.control.reboot", "GAP", reason="reboot_not_observed"))
        model_loaded = isinstance(guest, dict) and guest.get("model_loaded") is True
        model_reason = guest.get("model_reason") if isinstance(guest, dict) else "guest_absent"
        body = packet.packet_body(
            attempts,
            seal=seal,
            bundle_commit=env.get("W3_BUNDLE_COMMIT", "").strip(),
            model_loaded=model_loaded,
            model_sha256=rtbrain.MODEL_SHA256,
            machine_type=rtbrain.BRAIN_MACHINE,
            gross_usd=_money(gross),
        )
        if isinstance(model_reason, str):
            body["model_reason"] = model_reason
        body["campaign_complete"] = any(
            str(item.get("id", "")).startswith(("pe.escape.", "pe.path.", "pe.tamper.", "pe.identity.", "net."))
            for item in attempts
        )
        body["bundle_commit"] = (
            env.get("BUNDLE_COMMIT", "").strip() or env.get("W3_BUNDLE_COMMIT", "").strip()
        )
        try:
            packet.write_packet(evidence / "redteam-packet.json", body)
            print(json.dumps(packet.allow_packet(body)["counts"]))
        finally:
            od.drop_guest_copies(evidence)
            if payload_dir.exists():
                shutil.rmtree(payload_dir, ignore_errors=True)
            if raw_dir.exists():
                shutil.rmtree(raw_dir, ignore_errors=True)
            od.remove_os_login_key()
    return 0
