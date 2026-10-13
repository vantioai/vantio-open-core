"""Record why a ceiling open returned errno 13 with no deny row.

The collector runs on the lab host, as root, while the loader is up. It does
not grade the battery. classify() is pure: the unit test names a cause from
the same fields the host fills in.

Audience: INTERNAL_RESTRICTED
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

SUBJECT = 65534
DENY_PIN = "/sys/fs/bpf/vantio_deny_attr"
DECISION_PIN = "/sys/fs/bpf/vantio_decision"
CEIL_PIN = "/sys/fs/bpf/vantio_ceil_key"
DECISION_SLOTS = 8
HOOK_NAMES = ("path", "file")
SLOT_NAMES = (
    "hits",
    "cgroup_enrolled",
    "ceiling_path",
    "ceiling_inode",
    "anchor_found",
    "anchor_lazy",
    "deny",
    "allow_reason",
)
ALLOW_REASONS = {
    0: "none",
    1: "not_enrolled",
    2: "path_miss",
    3: "inode_miss",
    4: "root",
    5: "self",
    6: "anchor_missing",
}
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


def bpf_lsm_active(text: str) -> bool:
    """True when bpf is its own entry in the active LSM list."""
    return any(part.strip() == "bpf" for part in text.split(","))


def cgroup_enroll_keys(inode: int, handle_id: int) -> list[int]:
    """Directory inode and kernfs id, plus a low 32-bit form when it differs."""
    keys: list[int] = []
    for key in (inode, handle_id, inode & 0xFFFFFFFF, handle_id & 0xFFFFFFFF):
        if key and key not in keys:
            keys.append(key)
    return keys


READINESS_BLOCKED = "INSTALL_ENFORCEMENT_READINESS_BLOCKED"
READINESS_REASON = "bpf_lsm_inactive"
LSM_STOCK_PATH = Path("/var/lib/vantio-lab/lsm-stock.json")
LSM_ROWS_PATH = Path("/tmp/enterprise-pe-rows.json")


def lsm_list_with_bpf(current: str) -> str:
    """Active LSM list with bpf appended. This does not edit a bootloader."""
    tokens = [part.strip() for part in current.split(",") if part.strip()]
    if "bpf" not in tokens:
        tokens.append("bpf")
    return ",".join(tokens)


def classify_readiness_log(text: str) -> dict:
    """The enforce generation refused, and it did not claim tc enforce."""
    status = READINESS_BLOCKED in text and f"reason={READINESS_REASON}" in text
    not_enforcing = "NOT ENFORCING" in text
    reports = "tc enforce :" in text
    return {
        "blocked": status and not_enforcing and not reports,
        "status_present": status,
        "not_enforcing": not_enforcing,
        "reports_enforcing": reports,
    }


def _rewrite_grub_text(text: str, lsm_value: str, *, own_the_value: bool) -> tuple[str, str | None]:
    """Return the grub file with one lsm= assignment, or an error name."""
    saw_linux = False
    lines: list[str] = []
    for raw in text.splitlines():
        if "GRUB_CMDLINE_LINUX" in raw and "+=" in raw and "lsm=" in raw:
            return text, "grub_append"
        matched = re.match(r"^(\s*)(GRUB_CMDLINE_LINUX(?:_DEFAULT)?)(\s*=\s*)(.*)$", raw)
        if matched is None:
            lines.append(raw)
            continue
        var = matched.group(2)
        quoted = matched.group(4).strip()
        if len(quoted) >= 2 and quoted[0] == quoted[-1] and quoted[0] in {'"', "'"}:
            value = quoted[1:-1]
        else:
            value = quoted
        tokens = [token for token in value.split() if token and not token.startswith("lsm=")]
        if own_the_value and var == "GRUB_CMDLINE_LINUX":
            tokens.append(f"lsm={lsm_value}")
            saw_linux = True
        indent = matched.group(1)
        lines.append(f'{indent}{var}="{" ".join(tokens)}"')
    if own_the_value and not saw_linux:
        if lines and lines[-1] != "":
            lines.append(f'GRUB_CMDLINE_LINUX="lsm={lsm_value}"')
        else:
            lines.append(f'GRUB_CMDLINE_LINUX="lsm={lsm_value}"')
    body = "\n".join(lines)
    if text.endswith("\n") or not text:
        body += "\n"
    return body, None


def lsm_dropin_text(lsm_value: str) -> str:
    """Drop-in sourced after the Ubuntu cloud image grub files.

    40-force-partuuid.cfg and 50-cloudimg-settings.cfg set
    GRUB_CMDLINE_LINUX_DEFAULT. A later 99-vantio-lsm.cfg replaces that
    value and keeps a single lsm= list. The file has to be executable or
    grub-mkconfig skips it.
    """
    if not re.fullmatch(r"[A-Za-z0-9_,.-]+", lsm_value) or not bpf_lsm_active(lsm_value):
        raise ValueError("lsm_value")
    return (
        "# Lab host. Sourced after the cloud image grub drop-ins.\n"
        '_vantio_bits=""\n'
        "for _vantio_tok in $GRUB_CMDLINE_LINUX_DEFAULT $GRUB_CMDLINE_LINUX; do\n"
        "  case $_vantio_tok in\n"
        "    lsm=*) ;;\n"
        '    *) _vantio_bits="$_vantio_bits $_vantio_tok" ;;\n'
        "  esac\n"
        "done\n"
        f'GRUB_CMDLINE_LINUX_DEFAULT="${{_vantio_bits# }} lsm={lsm_value}"\n'
        'GRUB_CMDLINE_LINUX=""\n'
        "unset _vantio_tok _vantio_bits\n"
    )


def plan_grub_lsm(main: str, extras: list[str], lsm_value: str) -> dict:
    """Put lsm=<value> on GRUB_CMDLINE_LINUX and drop other lsm= tokens."""
    if not re.fullmatch(r"[A-Za-z0-9_,.-]+", lsm_value) or not bpf_lsm_active(lsm_value):
        return {"error": "lsm_value"}
    new_main, err = _rewrite_grub_text(main, lsm_value, own_the_value=True)
    if err:
        return {"error": err}
    new_extras: list[str] = []
    for extra in extras:
        rewritten, err = _rewrite_grub_text(extra, lsm_value, own_the_value=False)
        if err:
            return {"error": err}
        new_extras.append(rewritten)
    return {"main": new_main, "extras": new_extras}


def lsm_status_body(
    stock: str,
    cmdline: str,
    prior: dict | None,
    *,
    distro: str = "",
    kernel: str = "",
    image_id: str = "",
) -> dict:
    """Confirm bpf is listed. A requested reboot still has to show it on the cmdline."""
    cmdline_has = False
    for token in cmdline.split():
        if token.startswith("lsm=") and bpf_lsm_active(token.split("=", 1)[1]):
            cmdline_has = True
    requested = isinstance(prior, dict) and prior.get("reboot_requested") is True
    if requested:
        result = "LSM_ENABLED" if cmdline_has else "FAIL"
        reason = "bpf_listed" if cmdline_has else "cmdline_missing_bpf"
    else:
        result = "LSM_ALREADY_ACTIVE"
        reason = "stock_bpf_lsm"
    return {
        "battery": "lsm-guard",
        "host_result": result,
        "reason": reason,
        "stock_lsm": stock,
        "stock_bpf_lsm": True,
        "cmdline": cmdline,
        "bpf_listed": True,
        "cmdline_has_bpf": cmdline_has,
        "prior_guard": prior if isinstance(prior, dict) else None,
        "distro": distro,
        "kernel": kernel,
        "image_id": image_id,
        "reboot_requested": False,
        "lab_pass": False,
        "customer_claim": False,
    }


def _pretty_distro() -> str:
    path = Path("/etc/os-release")
    if not path.is_file():
        return ""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("PRETTY_NAME="):
            return line.split("=", 1)[1].strip().strip('"')
    return ""


def write_lsm_status() -> int:
    """0 when bpf is already an active LSM. 1 when the loader proof still has to run."""
    lsm_path = Path("/sys/kernel/security/lsm")
    stock = lsm_path.read_text(encoding="utf-8").strip() if lsm_path.is_file() else ""
    cmdline_path = Path("/proc/cmdline")
    cmdline = cmdline_path.read_text(encoding="utf-8").strip() if cmdline_path.is_file() else ""
    if not bpf_lsm_active(stock):
        return 1
    prior = None
    if LSM_STOCK_PATH.is_file():
        try:
            loaded = json.loads(LSM_STOCK_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = None
        prior = loaded if isinstance(loaded, dict) else None
    body = lsm_status_body(
        stock,
        cmdline,
        prior,
        distro=_pretty_distro(),
        kernel=os.uname().release,
        image_id=os.environ.get("VANTIO_IMAGE_ID", ""),
    )
    text = json.dumps(body, indent=2) + "\n"
    LSM_ROWS_PATH.write_text(text, encoding="utf-8")
    try:
        os.chmod(LSM_ROWS_PATH, 0o644)
    except OSError:
        pass
    print(text, flush=True)
    return 0 if body["host_result"] != "FAIL" else 2


def _le_int(value: object) -> int | None:
    """Integer, or little-endian bytes from bpftool's hex dump."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value[2:] if value.lower().startswith("0x") else value
        try:
            return int(text, 16)
        except ValueError:
            return None
    if isinstance(value, list) and value:
        raw = bytearray()
        for item in value:
            if isinstance(item, str):
                text = item[2:] if item.lower().startswith("0x") else item
                try:
                    number = int(text, 16)
                except ValueError:
                    return None
            elif isinstance(item, int) and not isinstance(item, bool):
                number = item
            else:
                return None
            if number < 0 or number > 255:
                return None
            raw.append(number)
        return int.from_bytes(raw, "little")
    return None


def _cpu_values(row: dict) -> list[int]:
    values = row.get("values")
    found: list[int] = []
    if isinstance(values, list):
        for item in values:
            number = _le_int(item.get("value") if isinstance(item, dict) else item)
            if number is not None:
                found.append(number)
        return found
    number = _le_int(row.get("value"))
    return [number] if number is not None else []


def summarize_decision(dump: object) -> dict:
    """Sum per-CPU counters. Slot 7 is the last allow reason, not a sum."""
    hooks: dict[str, dict] = {}
    if not isinstance(dump, list):
        return {"hooks": hooks}
    for row in dump:
        if not isinstance(row, dict):
            continue
        key = _le_int(row.get("key"))
        if key is None:
            continue
        hook = key // DECISION_SLOTS
        slot = key % DECISION_SLOTS
        if hook >= len(HOOK_NAMES) or slot >= len(SLOT_NAMES):
            continue
        name = HOOK_NAMES[hook]
        body = hooks.setdefault(name, {})
        cpus = _cpu_values(row)
        if slot == DECISION_SLOTS - 1:
            reason = next((item for item in cpus if item), 0)
            body["allow_reason"] = reason
            body["allow_reason_name"] = ALLOW_REASONS.get(reason, "unknown")
        else:
            body[SLOT_NAMES[slot]] = sum(cpus)
    return {"hooks": hooks}


def decision_counters() -> dict:
    """Pinned decision counters and the ceiling key the kernel last saw."""
    report: dict = {}
    for name, pin in (("decision", DECISION_PIN), ("ceiling_key", CEIL_PIN)):
        if not Path(pin).exists():
            report[name] = {"present": False, "pin": pin}
            continue
        dumped = _run(["bpftool", "-j", "map", "dump", "pinned", pin])
        text = (dumped.get("stdout") or "") + (dumped.get("stderr") or "")
        try:
            body = json.loads(dumped.get("stdout") or "null")
        except json.JSONDecodeError:
            body = None
        report[name] = {
            "present": True,
            "pin": pin,
            "dump": body,
            "text": clip(text, 4000),
        }
    report["summary"] = summarize_decision(report["decision"].get("dump"))
    report["ceiling"] = decode_ceiling_dump(report["ceiling_key"].get("dump"))
    return report


def _byte_blob(value: object) -> bytes | None:
    if not isinstance(value, list) or not value:
        return None
    blob = bytearray()
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, str)):
            return None
        parsed = _le_int(item)
        if parsed is None or parsed > 255:
            return None
        blob.append(parsed)
    return bytes(blob)


def decode_ceiling_dump(dump: object) -> list[dict]:
    """One record per ceiling-key row. bpftool hex values are little-endian."""
    if not isinstance(dump, list):
        return []
    rows: list[dict] = []
    for row in dump:
        if not isinstance(row, dict):
            continue
        blob = _byte_blob(row.get("value"))
        if blob is None or len(blob) < 56:
            continue
        rows.append(
            {
                "index": _le_int(row.get("key")),
                "kernel_dev": int.from_bytes(blob[0:8], "little"),
                "kernel_ino": int.from_bytes(blob[8:16], "little"),
                "loaded_dev": int.from_bytes(blob[16:24], "little"),
                "loaded_ino": int.from_bytes(blob[24:32], "little"),
                "loaded_encoded": int.from_bytes(blob[32:40], "little"),
                "major": int.from_bytes(blob[40:44], "little"),
                "minor": int.from_bytes(blob[44:48], "little"),
                "allow_reason": int.from_bytes(blob[48:52], "little"),
                "hook": int.from_bytes(blob[52:56], "little"),
                "seen_cgroup": int.from_bytes(blob[56:64], "little") if len(blob) >= 64 else 0,
            }
        )
    return rows


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
        "decision": decision_counters(),
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
