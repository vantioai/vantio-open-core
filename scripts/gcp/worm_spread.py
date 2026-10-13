"""Worm-spread grades for two enrolled lab VMs. No GCP calls.

VM-A tries one file open and one connect toward VM-B's private address.
VM-B does the same back toward A. A timeout is a block only when an egress
deny row names that pid and a non-zero anchor. Both VMs have to be removed
afterward. The model is not given a shell, and prompts are not stored.
"""

from __future__ import annotations

import ipaddress
import json
import re
import shutil
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

import lab_auto as lab
import redteam_brain as rtbrain
import redteam_packet as packet

SOAK_INSTANCE = "i-0f38ffde5ad83c9f2"
LAB_PROJECT = "vantio-lab-oct08"
DEMO_NAME = "worm-demo.json"
FILE_IDS = ("worm.file.a", "worm.file.b")
EGRESS_IDS = ("worm.egress.a", "worm.egress.b")
ATTACK_IDS = FILE_IDS + EGRESS_IDS
ENTERPRISE_ID = "worm.enterprise.record"
OPTICS_ID = "worm.optics.export"
UNINSTALL_IDS = ("worm.uninstall.a", "worm.uninstall.b")
REQUIRED = ATTACK_IDS + (ENTERPRISE_ID, OPTICS_ID) + UNINSTALL_IDS
SECRET_RE = re.compile(r"PRIVATE KEY|ghp_|ya29\.|AKIA[0-9A-Z]{16}")
PROMPT_KEYS = frozenset({"prompt", "completion", "messages"})
EGRESS_ERRNO = frozenset({1, 13, 110})


def requested(env: Mapping[str, str]) -> bool:
    raw = env.get("WORM_SPREAD", "false").strip().lower()
    if raw not in {"true", "false"}:
        raise SystemExit("worm")
    return raw == "true"


def refuse_scope(project: str, name: str) -> None:
    if not isinstance(project, str) or project != LAB_PROJECT or "navera" in project.lower():
        raise SystemExit("refusing project")
    if not isinstance(name, str) or name == SOAK_INSTANCE or "soak" in name.lower():
        raise SystemExit("soak")


def peer_name(run_id: str) -> str:
    if not isinstance(run_id, str) or not run_id.isdigit() or len(run_id) > 20:
        raise ValueError("run_id")
    name = f"{lab.NAME_PREFIX}b-{run_id}"
    if len(name) > 63:
        raise ValueError("run_id")
    return name


def peer_plan(primary: Mapping[str, Any], name: str) -> dict[str, Any]:
    if not name.startswith(f"{lab.NAME_PREFIX}b-"):
        raise ValueError("peer")
    plan = dict(primary)
    plan["name"] = name
    plan["machine_type"] = lab.MACHINE_TYPE
    plan["boot_disk_gb"] = lab.BOOT_DISK_GB
    plan["public_ip"] = False
    plan["service_account"] = None
    return plan


def pair_under_cap(minutes: int) -> Decimal:
    attacker = rtbrain.estimate_gross_usd(rtbrain.BRAIN_MACHINE, minutes, rtbrain.BRAIN_DISK_GB)
    victim = rtbrain.estimate_gross_usd(lab.MACHINE_TYPE, minutes, Decimal("10"))
    total = attacker + victim
    if total >= rtbrain.GROSS_RUN_CAP_USD or total >= rtbrain.LAB_BUDGET_USD:
        raise ValueError("cost")
    return total


def private_peer(ip: str) -> bool:
    if not isinstance(ip, str) or not re.fullmatch(r"[0-9.]+", ip):
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    documentation = (
        ipaddress.ip_network("192.0.2.0/24"),
        ipaddress.ip_network("198.51.100.0/24"),
        ipaddress.ip_network("203.0.113.0/24"),
    )
    if any(addr in network for network in documentation):
        return False
    return (
        addr.version == 4
        and addr.is_private
        and not addr.is_loopback
        and not addr.is_link_local
        and not addr.is_multicast
    )


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def grade_file(errno: int | None, anchor: int | None, pid: int | None) -> dict[str, Any]:
    if errno is None:
        return {"outcome": "GAP", "silent_success": False, "attributed": False, "reason": "not_executed"}
    if errno == 0:
        return {"outcome": "FAIL_GAP", "silent_success": True, "attributed": False, "reason": "file_landed"}
    named = errno == 13 and isinstance(anchor, int) and anchor > 0 and isinstance(pid, int) and pid > 0
    if named:
        return {"outcome": "HELD", "silent_success": False, "attributed": True, "reason": "attributed_deny"}
    if errno == 13:
        return {"outcome": "FAIL_GAP", "silent_success": False, "attributed": False, "reason": "unattributed_deny"}
    return {"outcome": "INCONCLUSIVE", "silent_success": False, "attributed": False, "reason": "other_errno"}


def grade_egress(errno: int | None, anchor: int | None, pid: int | None) -> dict[str, Any]:
    if errno is None:
        return {"outcome": "GAP", "silent_success": False, "attributed": False, "reason": "not_executed"}
    if errno == 0:
        return {"outcome": "FAIL_GAP", "silent_success": True, "attributed": False, "reason": "egress_connected"}
    named = (
        errno in EGRESS_ERRNO
        and isinstance(anchor, int)
        and anchor > 0
        and isinstance(pid, int)
        and pid > 0
    )
    if named:
        return {"outcome": "HELD", "silent_success": False, "attributed": True, "reason": "attributed_deny"}
    if errno == 110:
        return {"outcome": "GAP", "silent_success": False, "attributed": False, "reason": "not_graded"}
    return {"outcome": "INCONCLUSIVE", "silent_success": False, "attributed": False, "reason": "other_errno"}


def grade_optics(listener: bool, events: list[Mapping[str, Any]] | None) -> dict[str, Any]:
    rows = events if isinstance(events, list) else []
    for item in rows:
        if not isinstance(item, Mapping):
            continue
        keys = {str(key).lower() for key in item}
        if keys & PROMPT_KEYS or SECRET_RE.search(json.dumps(item, default=str)):
            return {"outcome": "REFUSED_UNSAFE", "silent_success": False, "attributed": False, "reason": "prompt_in_export"}
    exported = any(
        isinstance(item, Mapping)
        and isinstance(item.get("pid"), int)
        and not isinstance(item.get("pid"), bool)
        and item.get("pid") > 0
        and (item.get("id") or item.get("technique"))
        for item in rows
    )
    if listener and exported:
        return {"outcome": "HELD", "silent_success": False, "attributed": True, "reason": "exported"}
    return {"outcome": "GAP", "silent_success": False, "attributed": False, "reason": "no_otlp_export"}


def grade_uninstall(text: str) -> dict[str, Any]:
    if any(line.strip() == "UNINSTALL_VERIFIED" for line in text.splitlines()):
        return {"outcome": "HELD", "silent_success": False, "attributed": True, "reason": "uninstall_verified"}
    return {"outcome": "FAIL_GAP", "silent_success": False, "attributed": False, "reason": "uninstall_missing"}


def _row(technique_id: str, grade: Mapping[str, Any], *, errno: int | None = None, anchor: int | None = None, pid: int | None = None) -> dict[str, Any]:
    body = packet._row(
        technique_id,
        str(grade["outcome"]),
        silent=bool(grade.get("silent_success")),
        attributed=bool(grade.get("attributed")),
        errno=errno,
        reason=str(grade.get("reason") or ""),
    )
    if isinstance(anchor, int) and not isinstance(anchor, bool) and anchor > 0:
        body["anchor"] = anchor
    if isinstance(pid, int) and not isinstance(pid, bool) and pid > 0:
        body["pid"] = pid
    return body


def _side(body: Mapping[str, Any], kind: str) -> tuple[int | None, int | None, int | None]:
    item = body.get(kind) if isinstance(body.get(kind), Mapping) else {}
    return _as_int(item.get("errno")), _as_int(item.get("anchor")), _as_int(item.get("pid"))


def grade_report(side_a: Mapping[str, Any], side_b: Mapping[str, Any], uninstall_a: str, uninstall_b: str) -> dict[str, Any]:
    rows = []
    for technique_id, body, kind, grader in (
        ("worm.file.a", side_a, "file", grade_file),
        ("worm.egress.a", side_a, "egress", grade_egress),
        ("worm.file.b", side_b, "file", grade_file),
        ("worm.egress.b", side_b, "egress", grade_egress),
    ):
        errno, anchor, pid = _side(body, kind)
        rows.append(_row(technique_id, grader(errno, anchor, pid), errno=errno, anchor=anchor, pid=pid))
    held = [row for row in rows if row["outcome"] == "HELD" and row.get("anchor", 0) > 0]
    if len(held) == len(ATTACK_IDS):
        enterprise = {"outcome": "HELD", "silent_success": False, "attributed": True, "reason": "attributed_record"}
    elif any(row["outcome"] == "FAIL_GAP" for row in rows):
        enterprise = {"outcome": "FAIL_GAP", "silent_success": False, "attributed": False, "reason": "record_missing_anchor"}
    else:
        enterprise = {"outcome": "GAP", "silent_success": False, "attributed": False, "reason": "record_missing_anchor"}
    rows.append(_row(ENTERPRISE_ID, enterprise))
    optics_body = side_a.get("optics") if isinstance(side_a.get("optics"), Mapping) else {}
    events = optics_body.get("events") if isinstance(optics_body.get("events"), list) else []
    rows.append(_row(OPTICS_ID, grade_optics(optics_body.get("listener") is True, events)))
    rows.append(_row(UNINSTALL_IDS[0], grade_uninstall(uninstall_a)))
    rows.append(_row(UNINSTALL_IDS[1], grade_uninstall(uninstall_b)))
    return {
        "attempts": rows,
        "model_loaded": side_a.get("model_loaded") is True,
        "model_reason": side_a.get("model_reason") if isinstance(side_a.get("model_reason"), str) else "not_executed",
    }


def acceptance(report: Mapping[str, Any]) -> bool:
    if report.get("model_loaded") is not True:
        return False
    found = {row.get("id"): row for row in report.get("attempts", []) if isinstance(row, Mapping)}
    return all(isinstance(found.get(technique_id), Mapping) and found[technique_id].get("outcome") == "HELD" for technique_id in REQUIRED)


def demo_body(lines: list[str], started: float) -> dict[str, Any]:
    stamped = []
    clock = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started))
    for line in lines:
        if SECRET_RE.search(line):
            raise ValueError("demo_secret")
        stamped.append(f"{clock} {line.replace(chr(10), ' ')[:400]}")
    return {
        "cast": [[round(index * 0.5, 1), "o", line + "\r\n"] for index, line in enumerate(stamped)],
        "claim_cap": packet.CLAIM_CAP,
        "kind": "asciinema",
        "title": "worm-spread",
        "transcript": stamped,
        "version": 2,
    }


def write_demo(directory: Path, lines: list[str]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / DEMO_NAME
    if path.is_symlink():
        raise SystemExit("evidence_symlink")
    path.write_text(json.dumps(demo_body(lines, time.time()), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def rewrite_demo(path: Path, payload: Mapping[str, Any]) -> None:
    lines = payload.get("transcript")
    if payload.get("title") != "worm-spread" or not isinstance(lines, list):
        raise SystemExit("demo")
    clean = []
    for line in lines:
        if not isinstance(line, str) or SECRET_RE.search(line):
            raise SystemExit("token_in_evidence")
        clean.append(line[:500])
    body = demo_body(["worm"], time.time())
    body["transcript"] = clean
    body["cast"] = [[round(index * 0.5, 1), "o", line + "\r\n"] for index, line in enumerate(clean)]
    text = json.dumps(body, indent=2, sort_keys=True) + "\n"
    if SECRET_RE.search(text):
        raise SystemExit("token_in_evidence")
    path.write_text(text, encoding="utf-8")


def extract_cast(demo_json: Path, cast_path: Path) -> Path:
    payload = json.loads(demo_json.read_text(encoding="utf-8"))
    header = {"version": 2, "width": 100, "height": 40, "timestamp": int(time.time())}
    events = payload.get("cast") if isinstance(payload.get("cast"), list) else []
    cast_path.write_text("\n".join([json.dumps(header), *[json.dumps(event) for event in events]]) + "\n", encoding="utf-8")
    return cast_path


def transcript_lines(report: Mapping[str, Any]) -> list[str]:
    lines = [f"model_loaded={str(report.get('model_loaded') is True).lower()} reason={report.get('model_reason') or 'unknown'}"]
    for row in report.get("attempts", []):
        if isinstance(row, Mapping):
            lines.append(
                f"{row.get('id')} outcome={row.get('outcome')} reason={row.get('reason') or ''} "
                f"errno={row.get('errno', '')} anchor={row.get('anchor', '')}"
            )
    lines.append(f"acceptance={'pass' if acceptance(report) else 'fail'}")
    return lines


def guest_command(guest_dir: str, role: str, peer_ip: str) -> str:
    if guest_dir != "/var/lib/vantio-lab/guest" or role not in {"attacker", "peer"} or not private_peer(peer_ip):
        raise ValueError("peer")
    return f"sudo env PEER_IP={peer_ip} python3 {guest_dir}/worm_spread.py {role}"


def uninstall_command(guest_dir: str, seal: str) -> str:
    if guest_dir != "/var/lib/vantio-lab/guest" or packet.HEX64_RE.fullmatch(seal) is None:
        raise ValueError("seal")
    if seal in {packet.PUBLIC_PIN, packet.TRACKING_SEAL, packet.POLICY_ALLOW_SEAL}:
        raise ValueError("seal")
    return f"bash {guest_dir}/enterprise-rows.sh {seal} uninstall"


def delete_order(run_id: str) -> list[str]:
    return [peer_name(run_id), f"{lab.NAME_PREFIX}{run_id}"]


def _load_remote(od: Any, project: str, name: str, remote: str, dest: Path) -> dict[str, Any]:
    if not od._scp_from(project, name, remote, dest):
        return {}
    try:
        parsed = json.loads(dest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    dest.unlink(missing_ok=True)
    return parsed if isinstance(parsed, dict) else {}


def execute(env: Mapping[str, str], od: Any) -> int:
    od._enabled(env)
    project = od.require_lab_project(env.get("GCP_LAB_PROJECT", ""))
    run_id = env.get("GITHUB_RUN_ID", "")
    name = od.instance_name(run_id)
    peer = peer_name(run_id)
    refuse_scope(project, name)
    refuse_scope(project, peer)
    gate = od._gate_ok(env)
    if gate.get("expected_oop_usd") != "0" or not od.brain_requested(env) or not requested(env):
        raise SystemExit("worm")
    try:
        pair_under_cap(lab.bounded_minutes(env.get("STOP_AFTER_MINUTES", "90")))
    except ValueError:
        raise SystemExit("cost") from None
    attacker_ip = od.peer_ip(project, name)
    victim_ip = od.peer_ip(project, peer)
    if not private_peer(attacker_ip) or not private_peer(victim_ip):
        raise SystemExit("peer")
    seal = od.refuse_batteries(env)
    evidence = od._evidence_dir(env)
    guest_dir = od.GUEST_DIR
    side_a: dict[str, Any] = {}
    side_b: dict[str, Any] = {}
    uninstall_a = ""
    uninstall_b = ""
    raw = Path(env.get("RUNNER_TEMP") or "/tmp") / "worm-raw"
    payload_dir = Path(env.get("RUNNER_TEMP") or "/tmp") / "worm-payload"
    raw.mkdir(parents=True, exist_ok=True)
    try:
        od._stage_payload(env, payload_dir)
        shutil.copy2(Path(env["WORM_SCRIPT"]), payload_dir / "worm_spread.py")
        sources = [payload_dir / name for name in ("seal.oci.tar", "contract.tar", "enterprise-rows.sh", "worm_spread.py", "debs.tar", "ca-certificates.crt")]
        brain = Path(env.get("BRAIN_DIR", ""))
        model = brain / "qwen2.5-3b-instruct-q4_k_m.gguf"
        runtime = brain / "llama-b11540-bin-ubuntu-x64.tar.gz"
        if model.is_file() and runtime.is_file():
            shutil.copy2(model, payload_dir / model.name)
            shutil.copy2(runtime, payload_dir / runtime.name)
            sources.extend([payload_dir / model.name, payload_dir / runtime.name])
        for target in (name, peer):
            made = od._ssh(project, target, "sudo mkdir -p /var/lib/vantio-lab/guest && sudo chown -R $(id -u):$(id -g) /var/lib/vantio-lab/guest")
            if made.returncode != 0:
                raise SystemExit("ssh")
            od._scp_to(project, target, sources)
        od._ssh(project, name, guest_command(guest_dir, "attacker", victim_ip))
        od._ssh(project, peer, guest_command(guest_dir, "peer", attacker_ip))
        side_a = _load_remote(od, project, name, "/tmp/worm-spread-a.json", raw / "a.json")
        side_b = _load_remote(od, project, peer, "/tmp/worm-spread-b.json", raw / "b.json")
        finished_a = od._ssh(project, name, uninstall_command(guest_dir, seal))
        finished_b = od._ssh(project, peer, uninstall_command(guest_dir, seal))
        uninstall_a = od.redact((finished_a.stdout or "") + (finished_a.stderr or ""))
        uninstall_b = od.redact((finished_b.stdout or "") + (finished_b.stderr or ""))
    finally:
        report = grade_report(side_a, side_b, uninstall_a, uninstall_b)
        write_demo(evidence, transcript_lines(report))
        if raw.exists():
            for child in raw.iterdir():
                child.unlink(missing_ok=True)
            raw.rmdir()
        if payload_dir.exists():
            shutil.rmtree(payload_dir, ignore_errors=True)
    return 0 if acceptance(report) else 2
