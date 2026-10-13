#!/usr/bin/env python3
"""One soak observation. This does not reboot the host and it does not uninstall.

Pass the stage directory, then the word start, to load the engine when it is
down. The hourly timer omits start, so a loader that has died stays a failure.

Audience: INTERNAL_RESTRICTED
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DETAIL = re.compile(r"^[A-Za-z0-9_.:-]*$")
CPU = re.compile(r"^[0-9]+(?:\.[0-9]+)?$")
ROWS = Path("/tmp/enterprise-pe-rows.json")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _flag(value: object) -> str:
    return "1" if value is True else "0"


def _num(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, int):
        return "na"
    return str(value)


def detail_for(facts: dict, reasons: list[str]) -> str:
    parts: list[str] = []
    if reasons:
        parts.append("reason:" + ".".join(reasons))
    began = str(facts.get("began") or "")
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", began):
        parts.append("began:" + began)
    parts.extend(
        [
            "engine:" + _flag(facts.get("engine_loaded")),
            "progs:" + _flag(facts.get("programs_attached")),
            "enrolled:" + _flag(facts.get("enrollment_intact")),
            "file:" + _num(facts.get("file_errno")),
            "fanchor:" + _num(facts.get("file_anchor")),
            "egress:" + _num(facts.get("egress_errno")),
            "eanchor:" + _num(facts.get("egress_anchor")),
            "control:" + _num(facts.get("control_errno")),
            "allow:" + _num(facts.get("allow_errno")),
            "mem_kb:" + _num(facts.get("mem_kb")),
            "rss_kb:" + _num(facts.get("rss_kb")),
            "drops:" + _num(facts.get("drops")),
        ]
    )
    cpu = str(facts.get("cpu") or "")
    parts.append("cpu:" + cpu if CPU.fullmatch(cpu) else "cpu:na")
    if facts.get("started") is True:
        parts.append("started:1")
    text = ".".join(parts)
    if DETAIL.fullmatch(text) is None:
        return "reason:detail_charset"
    return text


def decide(facts: dict) -> tuple[str, str]:
    """Return pass, fail, or skip, and a detail token record-check.sh accepts."""
    if facts.get("waiting") is True:
        return "skip", detail_for({"began": facts.get("began")}, ["engine_not_loaded"])
    reasons: list[str] = []
    if facts.get("import_failed") is True:
        reasons.append("probe_import")
    if not facts.get("engine_loaded"):
        start_error = str(facts.get("start_error") or "")
        reasons.append("bpf_lsm_inactive" if start_error == "bpf_lsm_inactive" else "engine_down")
    else:
        if not facts.get("programs_attached"):
            reasons.append("programs_missing")
        if not facts.get("enrollment_intact"):
            reasons.append("enrollment_missing")
        file_anchor = facts.get("file_anchor")
        if (
            facts.get("file_errno") != 13
            or facts.get("file_attributed") is not True
            or isinstance(file_anchor, bool)
            or not isinstance(file_anchor, int)
            or file_anchor <= 0
        ):
            reasons.append("file_deny")
        if facts.get("control_errno") != 0:
            reasons.append("control")
        egress = facts.get("egress_errno")
        egress_anchor = facts.get("egress_anchor")
        attributed_egress = (
            not isinstance(egress, bool)
            and egress in (1, 13, 110, 111)
            and not isinstance(egress_anchor, bool)
            and isinstance(egress_anchor, int)
            and egress_anchor > 0
        )
        if not attributed_egress:
            reasons.append("egress_deny")
        if facts.get("allow_errno") != 0:
            reasons.append("overblock")
    if not isinstance(facts.get("mem_kb"), int) or isinstance(facts.get("mem_kb"), bool):
        reasons.append("memory")
    cpu = str(facts.get("cpu") or "")
    if CPU.fullmatch(cpu) is None:
        reasons.append("cpu")
    drops = facts.get("drops")
    if isinstance(drops, bool) or not isinstance(drops, int) or drops < 0:
        reasons.append("drops")
    result = "fail" if reasons else "pass"
    return result, detail_for(facts, reasons)


def _pgrep_loader() -> bool:
    proc = subprocess.run(["pgrep", "-x", "vantio-loader"], capture_output=True, text=True, check=False)
    return proc.returncode == 0


def _mem_kb() -> int | None:
    try:
        text = Path("/proc/meminfo").read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        if line.startswith("MemAvailable:"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                return int(parts[1])
    return None


def _loader_rss_cpu() -> tuple[int | None, str]:
    proc = subprocess.run(
        ["ps", "-C", "vantio-loader", "-o", "rss=", "-o", "pcpu="],
        capture_output=True,
        text=True,
        check=False,
    )
    line = (proc.stdout or "").strip().splitlines()
    if not line:
        try:
            load = Path("/proc/loadavg").read_text(encoding="utf-8").split()[0]
        except OSError:
            return None, ""
        return None, load if CPU.fullmatch(load) else ""
    parts = line[0].split()
    rss = int(parts[0]) if parts and parts[0].isdigit() else None
    cpu = parts[1] if len(parts) > 1 and CPU.fullmatch(parts[1]) else ""
    if not cpu:
        try:
            cpu = Path("/proc/loadavg").read_text(encoding="utf-8").split()[0]
        except OSError:
            cpu = ""
        if CPU.fullmatch(cpu) is None:
            cpu = ""
    return rss, cpu


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    if (
        isinstance(value, list)
        and value
        and all(isinstance(item, int) and not isinstance(item, bool) and 0 <= item <= 255 for item in value)
    ):
        return int.from_bytes(bytes(value[:8]), "little")
    return None


def _counter(body: object) -> int | None:
    if isinstance(body, dict):
        if "value" in body:
            parsed = _as_int(body["value"])
            if parsed is not None:
                return parsed
        for child in body.values():
            if isinstance(child, (dict, list)):
                found = _counter(child)
                if found is not None:
                    return found
    elif isinstance(body, list):
        for item in body:
            found = _counter(item)
            if found is not None:
                return found
    return None


def _drops() -> int | None:
    for pin in ("/sys/fs/bpf/vantio_deny_attr_drops", "/sys/fs/bpf/vantio_deny_overflow"):
        if not Path(pin).exists():
            continue
        proc = subprocess.run(
            ["bpftool", "-j", "map", "dump", "pinned", pin],
            capture_output=True,
            text=True,
            check=False,
        )
        try:
            body = json.loads(proc.stdout or "null")
        except json.JSONDecodeError:
            continue
        found = _counter(body)
        if found is not None:
            return found
    return None


def _programs_attached() -> bool:
    if not Path("/sys/fs/bpf/vantio_deny_attr").exists():
        return False
    proc = subprocess.run(["bpftool", "prog", "show"], capture_output=True, text=True, check=False)
    text = proc.stdout or ""
    return "kprobe_open" in text or "openat_deny" in text or "vantio_" in text


def _resources(facts: dict) -> None:
    facts["mem_kb"] = _mem_kb()
    rss, cpu = _loader_rss_cpu()
    facts["rss_kb"] = rss
    facts["cpu"] = cpu
    facts["drops"] = _drops()


def _bpf_active() -> bool:
    try:
        text = Path("/sys/kernel/security/lsm").read_text(encoding="utf-8")
    except OSError:
        return False
    return "bpf" in [part.strip() for part in text.split(",")]


def _enrollment_intact(host: object) -> bool:
    import baseline_diag

    anchor = Path(str(host.rows.ANCHOR))
    try:
        inode = anchor.stat().st_ino
    except OSError:
        return False
    handle = host._kernfs_handle_id(str(anchor)) or 0
    keys = baseline_diag.cgroup_enroll_keys(inode, handle)
    return any(host.enrolled_has(key) for key in keys)


def _probe(host: object, facts: dict) -> None:
    facts["control_errno"] = host.control_handshake()
    sample = host.stamp_deny(host.child_open(True))
    pid = sample.get("pid") if isinstance(sample.get("pid"), int) and not isinstance(sample.get("pid"), bool) else 0
    event = sample.get("deny_event") if isinstance(sample.get("deny_event"), dict) else {}
    file_anchor = event.get("lineage_anchor") if isinstance(event.get("lineage_anchor"), int) else 0
    if isinstance(file_anchor, bool) or file_anchor <= 0:
        file_anchor = host.pinned_deny_anchor(pid) if pid else 0
    facts["file_errno"] = sample.get("file_errno")
    facts["file_anchor"] = file_anchor
    facts["file_attributed"] = (
        sample.get("file_errno") == 13
        and pid > 0
        and isinstance(file_anchor, int)
        and not isinstance(file_anchor, bool)
        and file_anchor > 0
        and (
            (event.get("pid") == pid and isinstance(event.get("lineage_anchor"), int) and event.get("lineage_anchor") > 0)
            or host.pinned_deny_anchor(pid) > 0
        )
    )
    facts["egress_errno"] = sample.get("net_errno")
    facts["egress_anchor"] = host.egress_block_anchor(pid) if pid else 0
    try:
        host.ensure_allowlist_peer()
        facts["allow_errno"] = host.enrolled_connect_errno(host.ALLOW_HOST, host.ALLOW_PORT)
    except SystemExit:
        facts["allow_errno"] = None


def collect_facts(host: object, *, start: bool) -> dict:
    facts: dict = {"began": _now(), "started": False}
    _resources(facts)
    if not host.loader_running():
        if not start:
            facts["engine_loaded"] = False
            facts["start_error"] = "engine_down"
            return facts
        if not _bpf_active():
            facts["engine_loaded"] = False
            facts["start_error"] = "bpf_lsm_inactive"
            return facts
        try:
            host.prepare_enforce()
        except SystemExit as exc:
            text = str(exc)
            facts["engine_loaded"] = False
            facts["start_error"] = "bpf_lsm_inactive" if "bpf_lsm_inactive" in text else "engine_down"
            return facts
        facts["started"] = True
    facts["engine_loaded"] = bool(host.loader_running())
    if not facts["engine_loaded"]:
        facts["start_error"] = "engine_down"
        return facts
    facts["programs_attached"] = _programs_attached()
    facts["enrollment_intact"] = _enrollment_intact(host)
    _probe(host, facts)
    _resources(facts)
    return facts


def _emit(result: str, detail: str, facts: dict | None = None) -> None:
    print(f"result={result}")
    print(f"detail={detail}")
    body = {
        "battery": "soak-hourly",
        "check_result": result,
        "detail": detail,
        "host_result": "SOAK_CHECK",
        "lab_pass": False,
        "reboot_requested": False,
    }
    if facts:
        for key in (
            "allow_errno",
            "control_errno",
            "cpu",
            "drops",
            "egress_anchor",
            "egress_errno",
            "engine_loaded",
            "enrollment_intact",
            "file_anchor",
            "file_attributed",
            "file_errno",
            "mem_kb",
            "programs_attached",
            "rss_kb",
            "started",
            "start_error",
        ):
            if key in facts:
                body[key] = facts[key]
    ROWS.write_text(json.dumps(body, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    stage = Path(argv[1] if len(argv) > 1 else "/opt/vantio-enterprise")
    start = len(argv) > 2 and argv[2] == "start"
    began = _now()
    if not (stage / "guest_rows.py").is_file() and not _pgrep_loader():
        result, detail = decide({"waiting": True, "began": began})
        _emit(result, detail)
        return 0
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.path.insert(0, str(stage))
    try:
        import phase2_host as host
    except Exception:
        result, detail = decide({"import_failed": True, "engine_loaded": _pgrep_loader(), "began": began})
        _emit(result, detail)
        return 1
    facts = collect_facts(host, start=start)
    result, detail = decide(facts)
    _emit(result, detail, facts)
    return 0 if result != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
