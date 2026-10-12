"""Record why a ceiling open returned errno 13 with no deny row.

The collector runs on the lab host, as root, while the loader is up. It does
not grade the battery. classify() is pure: the unit test names a cause from
the same fields the host fills in.

Audience: INTERNAL_RESTRICTED
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

SUBJECT = 65534
DENY_PIN = "/sys/fs/bpf/vantio_deny_attr"
FILE_KIND = 1

_PROBE = """\
import os
import sys

path, cgroup, uid_text = sys.argv[1], sys.argv[2], sys.argv[3]
uid = int(uid_text)
if cgroup:
    try:
        with open(cgroup, "w", encoding="utf-8") as handle:
            handle.write(f"{os.getpid()}\\n")
        print("JOINED", os.getpid())
    except OSError as exc:
        print("JOIN", exc.errno or 1)
try:
    print("CGROUP", open("/proc/self/cgroup", encoding="utf-8").read().replace("\\n", " ").strip())
except OSError as exc:
    print("CGROUP", f"errno {exc.errno}")
status = open("/proc/self/status", encoding="utf-8").read().splitlines()
print("BEFORE", " | ".join(line for line in status if line.startswith(("Uid:", "NSpid:"))))
os.setresuid(uid, uid, 0)
status = open("/proc/self/status", encoding="utf-8").read().splitlines()
print("AFTER", " | ".join(line for line in status if line.startswith(("Uid:", "NSpid:"))))
try:
    fd = os.open(path, os.O_RDONLY)
    os.close(fd)
    print("OPEN", 0)
except OSError as exc:
    print("OPEN", exc.errno or 1)
"""

_WALK = """\
import os
import sys

path = sys.argv[1]
parts = [part for part in path.split("/") if part]
cur = "/"
print(f"{cur} kind=dir mode={oct(os.stat(cur).st_mode & 0o777)} x={int(os.access(cur, os.X_OK))}")
for index, part in enumerate(parts):
    cur = "/" + part if cur == "/" else cur + "/" + part
    kind = "file" if index == len(parts) - 1 else "dir"
    try:
        mode = oct(os.stat(cur).st_mode & 0o777)
    except OSError as exc:
        print(f"{cur} kind={kind} stat={exc.errno or 1}")
        break
    print(
        f"{cur} kind={kind} mode={mode} x={int(os.access(cur, os.X_OK))} r={int(os.access(cur, os.R_OK))}"
    )
"""


def clip(text: str, limit: int = 3500) -> str:
    cleaned = text.replace("\x00", "")
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit] + "\n...truncated\n"


def clip_tail(text: str, limit: int = 3500) -> str:
    cleaned = text.replace("\x00", "")
    if len(cleaned) <= limit:
        return cleaned
    return "...truncated\n" + cleaned[-limit:]


def _run(argv: list[str], timeout: float = 20) -> dict:
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"error": type(exc).__name__, "detail": clip(str(exc), 300)}
    return {
        "rc": proc.returncode,
        "stdout": clip(proc.stdout or ""),
        "stderr": clip(proc.stderr or ""),
    }


def sysctls() -> dict[str, str]:
    found: dict[str, str] = {}
    for name in (
        "fs.protected_regular",
        "fs.protected_fifos",
        "fs.protected_symlinks",
        "fs.protected_hardlinks",
    ):
        path = Path("/proc/sys") / name.replace(".", "/")
        try:
            found[name] = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            found[name] = f"errno {exc.errno}"
    return found


def _as_subject(argv: list[str]) -> dict:
    if os.geteuid() != 0:
        return _run(argv)
    return _run(
        [
            "setpriv",
            f"--reuid={SUBJECT}",
            f"--regid={SUBJECT}",
            "--clear-groups",
            "--inh-caps=-all",
            *argv,
        ]
    )


def _parent_blocked(walk: str) -> bool:
    for line in walk.splitlines():
        if " kind=dir " in line and " x=0" in line:
            return True
    return False


def _file_unreadable(walk: str) -> bool:
    for line in walk.splitlines():
        if " kind=file " in line and " r=0" in line:
            return True
    return False


def _parse_probe(stdout: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for line in stdout.splitlines():
        parts = line.split(" ", 1)
        if parts and parts[0] in {"JOINED", "JOIN", "OPEN", "CGROUP", "BEFORE", "AFTER"}:
            found[parts[0].lower()] = parts[1] if len(parts) > 1 else ""
    return found


def _cgroup_inode(proc_text: str) -> dict:
    path = proc_text.strip().split(":")[-1] if proc_text.strip() else ""
    host = Path("/sys/fs/cgroup") / path.lstrip("/")
    inode = 0
    if path.startswith("/") and host.exists():
        try:
            inode = host.stat().st_ino
        except OSError:
            inode = 0
    return {"proc": proc_text.strip(), "host_path": str(host), "inode": inode}


def _deny_key(pid: int) -> list[str]:
    key = (pid << 8) | FILE_KIND
    return [f"{byte:02x}" for byte in key.to_bytes(8, "little")]


def _lookup_deny(pid: int) -> dict:
    if pid <= 0 or not Path(DENY_PIN).exists():
        return {"present": False, "reason": "no_pin" if pid > 0 else "no_pid"}
    looked = _run(["bpftool", "map", "lookup", "pinned", DENY_PIN, "key", "hex", *_deny_key(pid)])
    text = (looked.get("stdout") or "") + (looked.get("stderr") or "")
    return {
        "present": looked.get("rc") == 0 and "not found" not in text.lower(),
        "text": clip(text, 500),
    }


def _map_count(pin: str) -> int | None:
    if not Path(pin).exists():
        return None
    dumped = _run(["bpftool", "-j", "map", "dump", "pinned", pin])
    try:
        body = json.loads(dumped.get("stdout") or "null")
    except json.JSONDecodeError:
        return None
    if isinstance(body, list):
        return len(body)
    return None


def _overflow() -> int | None:
    shown = _run(["bpftool", "-j", "map", "show"])
    try:
        rows = json.loads(shown.get("stdout") or "null")
    except json.JSONDecodeError:
        return None
    if not isinstance(rows, list):
        return None
    map_id = 0
    for item in rows:
        if isinstance(item, dict) and item.get("name") == "DENY_OVERFLOW":
            found = item.get("id")
            if isinstance(found, int):
                map_id = found
    if map_id <= 0:
        return None
    dumped = _run(["bpftool", "-j", "map", "dump", "id", str(map_id)])
    try:
        body = json.loads(dumped.get("stdout") or "null")
    except json.JSONDecodeError:
        return None
    if isinstance(body, list):
        for item in body:
            if isinstance(item, dict) and item.get("key") in (0, "0"):
                value = item.get("value")
                if isinstance(value, int):
                    return value
    return None


def relevant_apparmor(lines: list[str], path: str, pid: int) -> list[str]:
    """AppArmor DENIED lines that name this path or this pid. Other lines do not count."""
    matched: list[str] = []
    pid_mark = f"pid={pid}" if pid > 0 else ""
    for line in lines:
        lowered = line.lower()
        if "apparmor" not in lowered or "denied" not in lowered:
            continue
        if path and path in line:
            matched.append(line)
        elif pid_mark and pid_mark in line:
            matched.append(line)
    return matched


def _apparmor(path: str, pid: int) -> dict:
    kernel = _run(["dmesg"])
    journal = _run(["journalctl", "-k", "-n", "300", "--no-pager"])
    blob = (kernel.get("stdout") or "") + "\n" + (journal.get("stdout") or "")
    denied = relevant_apparmor(blob.splitlines(), path, pid)
    return {"denied": denied[:20], "denied_count": len(denied)}


def _tracelog_around(probe: list[str]) -> dict:
    if shutil.which("bpftool") is None:
        return {"tracelog": "bpftool_missing", "probe": _run(probe)}
    trace = subprocess.Popen(
        ["bpftool", "prog", "tracelog"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        probed = _run(probe)
    finally:
        trace.terminate()
        try:
            out, err = trace.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            trace.kill()
            out, err = trace.communicate(timeout=2)
    return {
        "tracelog": clip((out or "") + (err or "")),
        "probe": probed,
    }


def collect(path: str, anchor: int, cgroup_procs: str) -> dict:
    """One open of path as uid 65534, plus the checks around it."""
    outside = _as_subject(["namei", "-l", path])
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as handle:
        handle.write(_WALK)
        walk_path = handle.name
    os.chmod(walk_path, 0o644)
    try:
        walked = _as_subject(["python3", walk_path, path])
    finally:
        os.unlink(walk_path)
    walk_text = walked.get("stdout") or ""
    before_count = _map_count(DENY_PIN)
    before_overflow = _overflow()
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as handle:
        handle.write(_PROBE)
        probe_path = handle.name
    os.chmod(probe_path, 0o755)
    probe_argv = ["python3", probe_path, path, cgroup_procs, str(SUBJECT)]
    if shutil.which("strace"):
        probe_argv = ["strace", "-f", "-e", "trace=openat,open", "-s", "160", *probe_argv]
    try:
        traced = _tracelog_around(probe_argv)
    finally:
        os.unlink(probe_path)
    probed = traced.get("probe") if isinstance(traced.get("probe"), dict) else {}
    parsed = _parse_probe(probed.get("stdout") or "")
    probe_pid = int(parsed["joined"]) if parsed.get("joined", "").isdigit() else 0
    open_errno = int(parsed["open"]) if parsed.get("open", "").lstrip("-").isdigit() else None
    cgroup = _cgroup_inode(parsed.get("cgroup") or "")
    strace_text = probed.get("stderr") or ""
    lookup = _lookup_deny(probe_pid)
    after_count = _map_count(DENY_PIN)
    after_overflow = _overflow()
    apparmor = _apparmor(path, probe_pid)
    facts = {
        "anchor": anchor,
        "after_uid": parsed.get("after") or "",
        "apparmor_denied": apparmor["denied_count"] > 0,
        "apparmor_lines": apparmor["denied"],
        "before_uid": parsed.get("before") or "",
        "cgroup": cgroup,
        "cgroup_matches_enrolled": cgroup["inode"] == anchor and anchor > 0,
        "deny_count_after": after_count,
        "deny_count_before": before_count,
        "deny_lookup": lookup,
        "deny_row_for_probe": lookup.get("present") is True,
        "deny_row_other_pid": (
            isinstance(before_count, int)
            and isinstance(after_count, int)
            and after_count > before_count
            and lookup.get("present") is not True
        ),
        "file_unreadable_outside": _file_unreadable(walk_text),
        "namei_outside": outside.get("stdout") or outside.get("error") or "",
        "namei_outside_blocked": _parent_blocked(walk_text),
        "open_errno": open_errno,
        "open_uses_o_creat": "O_CREAT" in strace_text and path in strace_text,
        "overflow_after": after_overflow,
        "overflow_before": before_overflow,
        "overflow_increased": (
            isinstance(before_overflow, int)
            and isinstance(after_overflow, int)
            and after_overflow > before_overflow
        ),
        "probe_pid": probe_pid,
        "sticky_parent": bool(Path(path).parent.stat().st_mode & 0o1000) if Path(path).parent.exists() else False,
        "strace": clip_tail(strace_text),
        "strace_eacces": open_errno == 13 or "EACCES" in strace_text,
        "strace_present": shutil.which("strace") is not None,
        "sysctls": sysctls(),
        "tracelog": traced.get("tracelog") or "",
        "walk": walk_text,
    }
    facts["cause"] = classify(facts)
    return facts


def classify(facts: dict) -> str:
    """Name the errno 13 source from host facts. Unknown stays unclassified."""
    if facts.get("namei_outside_blocked") is True:
        return "parent_traverse"
    if facts.get("file_unreadable_outside") is True:
        return "file_mode"
    if facts.get("open_errno") != 13:
        return "open_not_eacces"
    if facts.get("open_uses_o_creat") is True and facts.get("sticky_parent") is True:
        return "protected_regular"
    if facts.get("deny_row_for_probe") is True:
        return "attributed_deny"
    if facts.get("deny_row_other_pid") is True:
        return "deny_row_other_pid"
    if facts.get("overflow_increased") is True:
        return "silent_deny_overflow"
    if facts.get("apparmor_denied") is True:
        return "apparmor"
    if facts.get("strace_eacces") is True and facts.get("cgroup_matches_enrolled") is True:
        return "eacces_unaccounted"
    if facts.get("strace_eacces") is True:
        return "eacces_cgroup_mismatch"
    return "unclassified"
