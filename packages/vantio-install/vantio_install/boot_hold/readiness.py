"""Enforce-ready probe. Unknown facts are not ready."""

from __future__ import annotations

import subprocess
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from vantio_install.boot_hold.constants import BPF_PINS, ENFORCE_PROGRAM, SLICE
from vantio_install.boot_hold.probe_link import open_local_probe


def _attachment(facts: dict) -> dict:
    raw = facts.get("enforcement_attachment")
    return raw if isinstance(raw, dict) else {}


def _self_check(facts: dict) -> dict:
    raw = facts.get("deny_self_check")
    return raw if isinstance(raw, dict) else {}


def evaluate_ready(facts: dict) -> dict:
    """Ready only when enforcement is attached and a live deny check passed.

    A running loader is not enough. A loaded program that is not attached to
    the enrolled cgroup keeps the hold.
    """

    pins = list(facts.get("bpf_pins") or [])
    missing = [name for name in BPF_PINS if name not in pins]
    cmdline = str(facts.get("loader_cmdline") or "")
    tokens = cmdline.split()
    loader_up = "vantio-loader" in cmdline and "--enforce" in tokens
    programs = str(facts.get("bpf_programs") or "")
    program_loaded = ENFORCE_PROGRAM in programs
    attachment = _attachment(facts)
    cgroup = str(attachment.get("cgroup") or "").rstrip("/")
    attached = (
        attachment.get("attached") is True
        and attachment.get("program") == ENFORCE_PROGRAM
        and cgroup.endswith(SLICE)
    )
    policy_loaded = facts.get("policy_loaded") is True and not missing
    health_ok = str(facts.get("loader_health") or "") == "OK"
    mode = str(facts.get("enforce_mode") or "")
    pins_current = facts.get("pins_current") is True
    expected_policy = str(facts.get("expected_policy_id") or "")
    loaded_policy = str(facts.get("loaded_policy_id") or "")
    policy_version_ok = bool(expected_policy) and expected_policy == loaded_policy
    check = _self_check(facts)
    live_deny = (
        check.get("attempted") is True
        and check.get("enrolled_denied") is True
        and check.get("unenrolled_allowed") is True
        and check.get("mechanism") == "phantom-engine"
        and check.get("hold_bypassed") is True
        and int(check.get("block_events") or 0) >= 1
        and int(check.get("control_block_events") or 0) == 0
        and check.get("exception_removed") is True
        and check.get("enrolled_in_slice") is True
        and check.get("unenrolled_outside_slice") is True
    )
    ready = bool(
        loader_up
        and program_loaded
        and attached
        and policy_loaded
        and health_ok
        and live_deny
        and pins_current
        and policy_version_ok
        and mode in {"scoped", "node-wide"}
    )
    if ready:
        reason = "enforce-ready"
    elif mode == "audit":
        reason = "audit-not-enforce"
    elif loader_up and (not expected_policy or not loaded_policy or expected_policy != loaded_policy):
        reason = "policy-version-mismatch"
    elif loader_up and not pins_current:
        reason = "pins-stale"
    elif loader_up and program_loaded and not attached:
        reason = "loader-running-not-attached"
    elif loader_up and not live_deny:
        reason = "deny-self-check-failed"
    else:
        reason = "not-enforce-ready"
    return {
        "enforce_ready": ready,
        "missing_pins": missing,
        "loader_up": loader_up,
        "program_loaded": program_loaded,
        "program_attached": attached,
        "policy_loaded": policy_loaded,
        "policy_version_ok": policy_version_ok,
        "pins_current": pins_current,
        "enforce_mode": mode,
        "loader_health_ok": health_ok,
        "live_deny": live_deny,
        "deny_mechanism": str(check.get("mechanism") or ""),
        "probe_detail": str(check.get("probe_detail") or ""),
        "reason": reason,
    }


def interpret_self_check(
    *,
    attached: bool,
    enrolled_rc: int | None,
    unenrolled_rc: int | None,
    hold_bypassed: bool,
    block_events: int = 0,
    control_block_events: int = 0,
    exception_removed: bool = False,
    enrolled_cgroup: str = "",
    unenrolled_cgroup: str = "",
    mechanism: str = "",
) -> dict:
    """Turn probe results into a deny-check record. A timeout alone is not a deny."""

    enrolled_in_slice = SLICE in enrolled_cgroup
    unenrolled_outside_slice = bool(unenrolled_cgroup) and SLICE not in unenrolled_cgroup
    enrolled_denied = enrolled_rc not in (None, 0)
    unenrolled_allowed = unenrolled_rc == 0
    if mechanism:
        named = mechanism
    elif not attached or enrolled_rc is None or unenrolled_rc is None or not hold_bypassed:
        named = "not-run"
    elif not enrolled_cgroup or not unenrolled_cgroup:
        named = "probe-cgroup-unknown"
    elif not enrolled_in_slice:
        named = "probe-outside-enrolled"
    elif not unenrolled_outside_slice:
        named = "control-inside-enrolled"
    elif not unenrolled_allowed:
        named = "control-unreachable"
    elif not enrolled_denied:
        named = "enrolled-allowed"
    elif block_events < 1:
        named = "unattributed-timeout"
    elif control_block_events > 0:
        named = "control-blocked"
    elif not exception_removed:
        named = "exception-left-installed"
    else:
        named = "phantom-engine"
    return {
        "attempted": bool(attached and hold_bypassed and enrolled_rc is not None and unenrolled_rc is not None),
        "enrolled_denied": enrolled_denied if attached and hold_bypassed else False,
        "unenrolled_allowed": unenrolled_allowed if attached and hold_bypassed else False,
        "mechanism": named,
        "hold_bypassed": bool(hold_bypassed),
        "block_events": int(block_events),
        "control_block_events": int(control_block_events),
        "exception_removed": bool(exception_removed),
        "enrolled_in_slice": enrolled_in_slice,
        "unenrolled_outside_slice": unenrolled_outside_slice,
    }


def probe_pins(root: Path) -> list[str]:
    base = root / "sys/fs/bpf"
    found: list[str] = []
    if not base.is_dir():
        return found
    for name in BPF_PINS:
        path = base / name
        if not path.exists() or path.is_symlink() or path.is_dir():
            continue
        found.append(name)
    return found


def probe_loader(root: Path) -> tuple[str, str]:
    proc = root / "proc"
    if not proc.is_dir():
        return "", ""
    cmdline = ""
    health = ""
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        raw_path = entry / "cmdline"
        try:
            raw = raw_path.read_bytes()
        except OSError:
            continue
        text = raw.replace(b"\x00", b" ").decode("utf-8", errors="replace")
        if "vantio-loader" not in text:
            continue
        cmdline = text.strip()
        health = _proc_health(entry / "stat")
        break
    return cmdline, health


def _proc_health(stat_path: Path) -> str:
    try:
        text = stat_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    # comm is inside parentheses; state is the next field.
    end = text.rfind(")")
    if end < 0 or end + 2 >= len(text):
        return ""
    state = text[end + 2 :].split()
    if not state:
        return ""
    if state[0] in {"R", "S", "D"}:
        return "OK"
    return state[0]


def probe_programs(bpftool) -> str:
    if bpftool is None:
        return ""
    try:
        return bpftool()
    except OSError:
        return ""


def attachment_from_show(text: str) -> dict:
    attached = ENFORCE_PROGRAM in text
    return {
        "attached": attached,
        "program": ENFORCE_PROGRAM if attached else "",
        "cgroup": f"/sys/fs/cgroup/{SLICE}" if attached else "",
    }


def attachment_from_log(text: str) -> dict:
    """Sealed loader line used when bpftool is not installed.

    A scoped banner by itself is not attachment. The line has to name the
    enrolled slice and say the cgroup program attached.
    """

    for line in text.splitlines():
        if SLICE in line and "cgroup_skb" in line and "attached" in line:
            return {
                "attached": True,
                "program": ENFORCE_PROGRAM,
                "cgroup": f"/sys/fs/cgroup/{SLICE}",
            }
    return {"attached": False, "program": "", "cgroup": ""}


def policy_from_maps(text: str, pins_complete: bool) -> bool:
    return bool(pins_complete and "vantio_enforce" in text)


def _connect_script(host: str, port: int, marker: str) -> str:
    return (
        "import os, socket, sys\n"
        "from pathlib import Path\n"
        "Path('/run/vantio').mkdir(parents=True, exist_ok=True)\n"
        f"Path('/run/vantio/deny-probe-{marker}.cgroup').write_text(Path('/proc/self/cgroup').read_text())\n"
        f"Path('/run/vantio/deny-probe-{marker}.pid').write_text(str(os.getpid()))\n"
        "s=socket.socket()\n"
        "s.settimeout(2)\n"
        "try:\n"
        f"    s.connect(({host!r}, {int(port)}))\n"
        "except OSError:\n"
        "    sys.exit(1)\n"
        "s.close()\n"
    )


def connect_argv(host: str, port: int, *, enrolled: bool) -> list[str]:
    marker = "enrolled" if enrolled else "unenrolled"
    argv = ["systemd-run", "--quiet", "--wait", "--pipe", "--collect"]
    argv.extend(["--slice", SLICE if enrolled else "system.slice"])
    argv.extend(["python3", "-c", _connect_script(host, port, marker)])
    return argv


def policy_id_from_cmdline(cmdline: str) -> str:
    """Identity of the loaded enforcement command. Flags that do not change policy stay out."""

    tokens = cmdline.split()
    keep: list[str] = []
    interesting = {
        "--enforce",
        "--cgroup-skb-enforce",
        "--node-wide-enforcement",
        "--startup-enroll-cgroup",
        "--iface",
        "--block-port",
        "--enforce-path",
    }
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in interesting:
            keep.append(token)
            if index + 1 < len(tokens) and not tokens[index + 1].startswith("--"):
                keep.append(tokens[index + 1])
                index += 1
        index += 1
    return " ".join(keep)


def enforce_mode_from_log(text: str) -> str:
    """Last startup banner wins. An audit banner does not count as enforce."""

    mode = ""
    for line in text.splitlines():
        if "AUDIT (log only)" in line or '"ActionTaken":"AUDIT"' in line or '"ActionTaken": "AUDIT"' in line:
            mode = "audit"
        if "SCOPED (drop enrolled)" in line or '"ActionTaken":"SCOPED"' in line or '"ActionTaken": "SCOPED"' in line:
            mode = "scoped"
        if "NODE-WIDE DLP" in line or '"ActionTaken":"NODE_WIDE"' in line or '"ActionTaken": "NODE_WIDE"' in line:
            mode = "node-wide"
    return mode


def new_block_count(before: str, after: str) -> int:
    """Count cgroup block lines that were not already in the earlier snapshot."""

    delta = Counter(after.splitlines()) - Counter(before.splitlines())
    total = 0
    for line, count in delta.items():
        json_block = '"EventType": "CGROUP_BLOCK"' in line or '"EventType":"CGROUP_BLOCK"' in line
        json_action = '"ActionTaken": "BLOCKED"' in line or '"ActionTaken":"BLOCKED"' in line
        text_block = "CG/SKB" in line and "BLOCKED" in line
        if text_block or (json_block and json_action):
            total += count
    return total


def read_probe_cgroup(marker: str) -> str:
    path = Path(f"/run/vantio/deny-probe-{marker}.cgroup")
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def clear_probe_markers() -> None:
    directory = Path("/run/vantio")
    for marker in ("enrolled", "unenrolled"):
        for suffix in ("cgroup", "pid"):
            path = directory / f"deny-probe-{marker}.{suffix}"
            try:
                path.unlink()
            except OSError:
                continue


def exception_argv(binary: str, host: str, port: int, *, delete: bool) -> list[str]:
    """One destination inside the hold chain. The chain is already cgroup-scoped.

    A second cgroup match inside that chain is rejected by iptables-nft
    (RULE_INSERT Invalid argument). Packets reach the chain only from the
    enrolled slice or the enrolled subnet.
    """

    action = ["-D", "VANTIO_BOOT_HOLD"] if delete else ["-I", "VANTIO_BOOT_HOLD", "1"]
    return [binary, *action, "-p", "tcp", "-d", host, "--dport", str(port), "-j", "RETURN"]


def perform_deny_self_check(
    runner,
    *,
    host: str,
    port: int,
    attached: bool,
    events: Callable[[], str] | None = None,
    cgroup_reader: Callable[[str], str] | None = None,
    sleeper: Callable[[float], None] | None = None,
) -> dict:
    """Prove a deny on the enrolled path after the boot-hold rule returns for that one flow.

    The exception is one destination and one port, only for the enrolled cgroup,
    and it is removed before this function returns. A connect timeout is not a
    Phantom Engine deny unless a new cgroup block line appears in that window.
    If enforcement is not attached, the exception is not inserted.
    """

    if not attached or not host or not port:
        return interpret_self_check(attached=False, enrolled_rc=None, unenrolled_rc=None, hold_bypassed=False)
    binary = "ip6tables" if ":" in host else "iptables"
    inserted = runner(exception_argv(binary, host, port, delete=False)) == 0
    if not inserted:
        return interpret_self_check(attached=True, enrolled_rc=None, unenrolled_rc=None, hold_bypassed=False)
    enrolled_rc = 1
    unenrolled_rc = 1
    before = events() if events is not None else ""
    mid = before
    after = before
    removed = False
    try:
        enrolled_rc = runner(connect_argv(host, port, enrolled=True))
        mid = events() if events is not None else ""
        if events is not None and sleeper is not None and new_block_count(before, mid) < 1:
            sleeper(0.3)
            mid = events()
        unenrolled_rc = runner(connect_argv(host, port, enrolled=False))
        after = events() if events is not None else ""
    finally:
        removed = runner(exception_argv(binary, host, port, delete=True)) == 0
    enrolled_cgroup = cgroup_reader("enrolled") if cgroup_reader is not None else ""
    unenrolled_cgroup = cgroup_reader("unenrolled") if cgroup_reader is not None else ""
    return interpret_self_check(
        attached=True,
        enrolled_rc=enrolled_rc,
        unenrolled_rc=unenrolled_rc,
        hold_bypassed=True,
        block_events=new_block_count(before, mid),
        control_block_events=new_block_count(mid, after),
        exception_removed=removed,
        enrolled_cgroup=enrolled_cgroup,
        unenrolled_cgroup=unenrolled_cgroup,
    )


def perform_live_deny_self_check(runner, *, attached: bool, events: Callable[[], str]) -> dict:
    """Run the deny check against a local listener this process creates and removes."""

    if not attached:
        return interpret_self_check(attached=False, enrolled_rc=None, unenrolled_rc=None, hold_bypassed=False)
    probe = open_local_probe()
    try:
        if not probe.ready:
            failed = interpret_self_check(
                attached=True,
                enrolled_rc=None,
                unenrolled_rc=None,
                hold_bypassed=False,
                mechanism="probe-setup-failed",
            )
            failed["probe_detail"] = probe.detail
            return failed
        clear_probe_markers()
        result = perform_deny_self_check(
            runner,
            host=probe.host,
            port=probe.port,
            attached=True,
            events=events,
            cgroup_reader=read_probe_cgroup,
            sleeper=time.sleep,
        )
        result["probe_host"] = probe.host
        result["probe_port"] = probe.port
        result["probe_kind"] = "local"
        return result
    finally:
        probe.close()


def assemble_host_facts(
    root: Path,
    *,
    prog_show: str,
    cgroup_show: str,
    map_show: str,
    runner=None,
    deny_probe: dict | None = None,
    loader_log: str = "",
    events: Callable[[], str] | None = None,
    pins_current: bool = False,
    expected_policy_id: str = "",
) -> dict:
    del deny_probe
    pins = probe_pins(root)
    cmdline, health = probe_loader(root)
    # Docker keeps the previous container log, and events.ndjson stays on disk
    # after the process is gone. Those lines are not a live attachment.
    loader_live = "vantio-loader" in cmdline
    live_log = loader_log if loader_live else ""
    attachment = attachment_from_show(cgroup_show)
    if not attachment["attached"]:
        attachment = attachment_from_log(live_log)
    pins_complete = all(name in pins for name in BPF_PINS)
    mode = enforce_mode_from_log(live_log)
    policy_loaded = policy_from_maps(map_show, pins_complete) or (
        loader_live
        and pins_complete
        and mode in {"scoped", "node-wide"}
        and "Path enforce maps loaded:" in live_log
    )
    loaded_policy_id = policy_id_from_cmdline(cmdline)
    programs = prog_show
    if attachment["attached"] and ENFORCE_PROGRAM not in programs:
        programs = f"{programs}\n{ENFORCE_PROGRAM}".strip()
    check = interpret_self_check(attached=False, enrolled_rc=None, unenrolled_rc=None, hold_bypassed=False)
    if attachment["attached"] and runner is not None and events is not None:
        check = perform_live_deny_self_check(runner, attached=True, events=events)
    return {
        "bpf_pins": pins,
        "loader_cmdline": cmdline,
        "loader_health": health,
        "bpf_programs": programs,
        "enforcement_attachment": attachment,
        "policy_loaded": policy_loaded,
        "deny_self_check": check,
        "enforce_mode": mode,
        "pins_current": pins_current,
        "expected_policy_id": expected_policy_id,
        "loaded_policy_id": loaded_policy_id,
    }


def probe_host(root: Path, bpftool=None) -> dict:
    cmdline, health = probe_loader(root)
    return {
        "bpf_pins": probe_pins(root),
        "loader_cmdline": cmdline,
        "loader_health": health,
        "bpf_programs": probe_programs(bpftool),
    }


def default_bpftool() -> str:
    completed = subprocess.run(
        ["bpftool", "prog", "show"],
        check=False,
        capture_output=True,
        text=True,
        timeout=8,
    )
    if completed.returncode != 0:
        return ""
    return completed.stdout or ""
