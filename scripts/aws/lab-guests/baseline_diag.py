"""Record why a ceiling open returned errno 13 with no deny row.

The collector runs on the lab host, as root, while the loader is up. It does
not grade the battery. classify() is pure: the unit test names a cause from
the same fields the host fills in.

Audience: INTERNAL_RESTRICTED
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
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
LSM_BOOT_MARK = Path("/boot/vantio-lsm-stock.json")
LSM_ROWS_PATH = Path("/tmp/enterprise-pe-rows.json")
LAB_ROWS_PATH = Path("/var/lib/vantio-lab/enterprise-pe-rows.json")


def lsm_list_with_bpf(current: str) -> str:
    """Active LSM list with bpf appended. This does not edit a bootloader."""
    tokens = [part.strip() for part in current.split(",") if part.strip()]
    if "bpf" not in tokens:
        tokens.append("bpf")
    return ",".join(tokens)


def _loader_needs_bpf_lsm(text: str) -> bool:
    """True when the loader refused because bpf is not an active LSM."""
    return "bpf is not in the active lsm list" in text.lower()


def classify_readiness_log(text: str) -> dict:
    """The enforce generation refused, and it did not claim tc enforce.

    A stock loader logs that bpf is not in the active LSM list instead of
    INSTALL_ENFORCEMENT_READINESS_BLOCKED. That sentence is a block when
    enforcement needs the BPF LSM. A later `tc enforce :` line is the loader
    claiming it enforced anyway, and that claim is not this block.
    """
    legacy = READINESS_BLOCKED in text and f"reason={READINESS_REASON}" in text
    inactive = _loader_needs_bpf_lsm(text)
    not_enforcing = "not enforcing" in text.lower()
    reports = "tc enforce :" in text
    blocked = not reports and ((legacy and not_enforcing) or inactive)
    if inactive and blocked:
        reason = "lsm_bpf_inactive"
    elif blocked:
        reason = READINESS_REASON
    else:
        reason = ""
    return {
        "blocked": blocked,
        "status_present": legacy or inactive,
        "not_enforcing": not_enforcing,
        "reports_enforcing": reports,
        "reason": reason,
    }


def lsm_guard_action(
    verdict: dict,
    *,
    stock_lsm: str,
    bpf_pins: list[str],
    egress_present: bool,
) -> dict:
    """Decide whether lsm-guard writes the consented cmdline.

    The stock loader exits on the inactive BPF LSM before it can report the
    lab iface. That report is not required for this refusal. Pins left behind
    still stop the write. The caller sets reboot_requested only after the
    generated menu contains the token.
    """
    if bpf_lsm_active(stock_lsm):
        return {
            "write_grub": False,
            "host_result": "LSM_ALREADY_ACTIVE",
            "reason": "stock_bpf_lsm",
            "lsm_value": "",
        }
    if not verdict.get("blocked"):
        return {
            "write_grub": False,
            "host_result": "FAIL",
            "reason": "readiness_not_blocked",
            "lsm_value": "",
        }
    if bpf_pins:
        return {
            "write_grub": False,
            "host_result": "FAIL",
            "reason": "pins_left",
            "lsm_value": "",
        }
    reason = verdict.get("reason") if isinstance(verdict.get("reason"), str) else ""
    if not egress_present and reason not in {"lsm_bpf_inactive", READINESS_REASON}:
        return {
            "write_grub": False,
            "host_result": "FAIL",
            "reason": "egress_iface_missing",
            "lsm_value": "",
        }
    return {
        "write_grub": True,
        "host_result": "",
        "reason": reason or "lsm_bpf_inactive",
        "lsm_value": lsm_list_with_bpf(stock_lsm),
    }


def reboot_after_grub(action: dict, grub_updated: bool) -> bool:
    """True only after the generated menu was checked and the write is allowed."""
    lsm_value = action.get("lsm_value") if isinstance(action, dict) else ""
    return (
        isinstance(action, dict)
        and action.get("write_grub") is True
        and grub_updated is True
        and isinstance(lsm_value, str)
        and bpf_lsm_active(lsm_value)
    )


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

    40-force-partuuid.cfg and 50-cloudimg-settings.cfg assign
    GRUB_CMDLINE_LINUX_DEFAULT. The booted tokens on a cloud image often
    live on GRUB_CMDLINE_LINUX instead. A later 99-vantio-lsm.cfg puts the
    same lsm= list on both. Clearing LINUX drops the token the guest
    actually boots. The file has to be executable or grub-mkconfig skips it.
    """
    if not re.fullmatch(r"[A-Za-z0-9_,.-]+", lsm_value) or not bpf_lsm_active(lsm_value):
        raise ValueError("lsm_value")
    return (
        "# Lab host. Sourced after the cloud image grub files.\n"
        '_vantio_default=""\n'
        '_vantio_linux=""\n'
        "for _vantio_tok in $GRUB_CMDLINE_LINUX_DEFAULT; do\n"
        "  case $_vantio_tok in\n"
        "    lsm=*) ;;\n"
        '    *) _vantio_default="$_vantio_default $_vantio_tok" ;;\n'
        "  esac\n"
        "done\n"
        "for _vantio_tok in $GRUB_CMDLINE_LINUX; do\n"
        "  case $_vantio_tok in\n"
        "    lsm=*) ;;\n"
        '    *) _vantio_linux="$_vantio_linux $_vantio_tok" ;;\n'
        "  esac\n"
        "done\n"
        f'GRUB_CMDLINE_LINUX_DEFAULT="${{_vantio_default# }} lsm={lsm_value}"\n'
        f'GRUB_CMDLINE_LINUX="${{_vantio_linux# }} lsm={lsm_value}"\n'
        "unset _vantio_tok _vantio_default _vantio_linux\n"
    )


def linux_lines(text: str) -> list[str]:
    """Every generated linux line. The default entry is not always the first."""
    return [raw.strip() for raw in text.splitlines() if raw.strip().startswith("linux")]


def boot_linux_lines(text: str) -> list[str]:
    """The linux lines a FORCE_PARTUUID cloud image actually boots.

    /etc/grub.d/10_linux emits two linux lines when GRUB_FORCE_PARTUUID is
    set. The first sits in the initrd fallback. The else branch is the one
    that boots, and it hardcodes panic=-1 after the variable arguments.
    """
    lines = linux_lines(text)
    boot = [line for line in lines if "panic=-1" in line.split()]
    return boot or lines


def first_linux_line(text: str) -> str:
    """The linux line a cloud image boots, not the initrd fallback."""
    lines = boot_linux_lines(text)
    return lines[0] if lines else ""


def last_lsm_token(line: str) -> str:
    """The last lsm= word. The kernel keeps that one and ignores earlier copies."""
    found = ""
    for part in line.split():
        if part.startswith("lsm="):
            found = part
    return found


def grub_cfg_has_lsm(text: str, lsm_value: str) -> bool:
    """True when every boot line keeps this lsm= list and panic=-1 last.

    /etc/grub.d/10_linux, when GRUB_FORCE_PARTUUID is set, writes the line
    that boots as `ro ${args} panic=-1`. The cloud-image args come from
    GRUB_CMDLINE_LINUX and GRUB_CMDLINE_LINUX_DEFAULT. panic=-1 stays the
    last word. Run 38669912999 appended lsm= after that word and the kernel
    still recorded the stock else branch, with panic=-1 last and no lsm=.
    A last lsm= token that sits after panic=-1 is not this list.
    """
    lines = boot_linux_lines(text)
    return bool(lines) and all(firmware_cmdline_ok(line, lsm_value) for line in lines)


def rewrite_linux_lines(text: str, lsm_value: str) -> str:
    """Put one lab lsm= token at the end of every linux line."""
    if not re.fullmatch(r"[A-Za-z0-9_,.-]+", lsm_value) or not bpf_lsm_active(lsm_value):
        raise ValueError("lsm_value")
    token = f"lsm={lsm_value}"
    out: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped.startswith("linux"):
            out.append(raw)
            continue
        indent = raw[: len(raw) - len(raw.lstrip())]
        parts = [part for part in stripped.split() if not part.startswith("lsm=")]
        parts.append(token)
        out.append(f"{indent}{' '.join(parts)}")
    body = "\n".join(out)
    if text.endswith("\n") or not text:
        body += "\n"
    return body


EFI_PARTTYPE = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b"
BOOTCHAIN_PATH = Path("/var/lib/vantio-lab/bootchain.json")
_UUID_RE = re.compile(
    r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}|[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}"
)
_GRUB_PACKAGES = (
    "grub-efi-amd64",
    "grub-efi-amd64-signed",
    "grub-pc",
    "grub-pc-bin",
    "shim-signed",
)


def _valid_lsm(lsm_value: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_,.-]+", lsm_value) or not bpf_lsm_active(lsm_value):
        raise ValueError("lsm_value")


def place_lsm_before_panic(raw: str, lsm_value: str) -> str:
    """Insert lsm= immediately before the last panic=-1.

    Run 38669912999 appended the token after panic=-1. The kernel recorded
    the stock line, with panic=-1 last and no lsm=.
    """
    _valid_lsm(lsm_value)
    token = f"lsm={lsm_value}"
    indent = raw[: len(raw) - len(raw.lstrip())]
    parts = raw.strip().split()
    if not parts:
        return raw
    head = parts[0]
    rest = [part for part in parts[1:] if not part.startswith("lsm=")]
    if "panic=-1" in rest:
        index = len(rest) - 1 - rest[::-1].index("panic=-1")
        rest.insert(index, token)
    else:
        rest.append(token)
    return f"{indent}{head} {' '.join(rest)}"


def _linux_command(stripped: str) -> bool:
    head = stripped.split(None, 1)[0] if stripped else ""
    return head in {"linux", "linuxefi"}


def _loader_options(stripped: str) -> bool:
    return stripped.startswith("options ") or stripped.startswith("options\t")


def rewrite_firmware_text(text: str, lsm_value: str) -> str:
    """Patch linux lines and systemd-boot options. Leave an EFI stub alone."""
    out: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if _linux_command(stripped) or _loader_options(stripped):
            out.append(place_lsm_before_panic(raw, lsm_value))
        else:
            out.append(raw)
    body = "\n".join(out)
    if text.endswith("\n") or not text:
        body += "\n"
    return body


def firmware_cmdline_ok(line: str, lsm_value: str) -> bool:
    """True when the last lsm= word is the lab list and panic=-1 is still last."""
    parts = line.strip().split()
    if not parts:
        return False
    words = parts[1:] if parts[0] in {"linux", "linuxefi", "options"} else parts
    last = ""
    for word in words:
        if word.startswith("lsm="):
            last = word
    if last != f"lsm={lsm_value}":
        return False
    if "panic=-1" in words and words[-1] != "panic=-1":
        return False
    return True


def cmdline_has_bpf_lsm(cmdline: str) -> bool:
    for token in cmdline.split():
        if token.startswith("lsm=") and bpf_lsm_active(token.split("=", 1)[1]):
            return True
    return False


def efi_stub_facts(text: str) -> dict:
    """Classify an EFI grub.cfg as a stub, a menu, or neither.

    Ubuntu's EFI file is often three lines: search.fs_uuid, set prefix, and
    configfile. update-grub does not rewrite that stub. A copied full menu
    in the same path does boot, and update-grub does not rewrite that either.
    """
    has_linux = any(_linux_command(line.strip()) for line in text.splitlines())
    uuid = ""
    prefix = ""
    configfile = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not uuid and ("search.fs_uuid" in line or "--fs-uuid" in line):
            found = _UUID_RE.search(line)
            if found:
                uuid = found.group(0)
        if not prefix and line.startswith("set ") and "prefix=" in line:
            prefix = line.split("prefix=", 1)[1].strip()
        if not configfile and line.startswith("configfile "):
            configfile = line.split(None, 1)[1].strip()
    if has_linux:
        kind = "menu"
    elif not text.strip():
        kind = "absent"
    elif configfile and ("search.fs_uuid" in text or "--fs-uuid" in text):
        kind = "stub"
    else:
        kind = "other"
    return {
        "kind": kind,
        "uuid": uuid,
        "prefix": prefix,
        "configfile": configfile,
        "head": " ".join(text.split())[:180],
    }


def config_relpath(facts: dict) -> str:
    """Path of the grub.cfg a stub's configfile line loads, relative to that filesystem."""
    prefix = str(facts.get("prefix") or "")
    configfile = str(facts.get("configfile") or "")
    quoted = re.search(r"'([^']*)'", prefix)
    if quoted:
        rel = quoted.group(1).strip("/")
    else:
        rel = prefix
        if rel.startswith("($root)"):
            rel = rel[len("($root)") :]
        rel = rel.strip("/'\"")
    if not configfile or "$prefix" in configfile:
        return f"{rel}/grub.cfg" if rel else "grub.cfg"
    if configfile.startswith("($root)"):
        return configfile.split(")", 1)[-1].strip("'\"").lstrip("/")
    if configfile.startswith("/"):
        return configfile.lstrip("/")
    return configfile.lstrip("/")


def stub_boot_decision(stub_uuid: str, mounted_uuid: str, *, target_sealed: bool) -> str:
    """Name the filesystem the stub searches when it is not the mounted /boot."""
    if not stub_uuid:
        return "no_stub_uuid"
    if target_sealed and mounted_uuid and stub_uuid.lower() != mounted_uuid.lower():
        return "sealed_other"
    if not mounted_uuid:
        return "unknown"
    if stub_uuid.lower() == mounted_uuid.lower():
        return "match"
    return f"boot_uuid_mismatch:{stub_uuid}"


def resolve_stub_target(
    root: Path,
    facts: dict,
    *,
    boot_uuid: str = "",
    root_uuid: str = "",
    esp_uuid: str = "",
) -> Path | None:
    """Linux path of the configfile target when the stub UUID is one we have mounted."""
    rel = config_relpath(facts)
    if not rel:
        return None
    uuid = str(facts.get("uuid") or "").lower()
    if not uuid:
        return None
    if esp_uuid and uuid == esp_uuid.lower():
        return root / "boot/efi" / rel
    if boot_uuid and uuid == boot_uuid.lower():
        if rel == "grub/grub.cfg" or rel.startswith("grub/"):
            return root / "boot" / rel
        return root / rel.lstrip("/")
    if root_uuid and uuid == root_uuid.lower():
        return root / rel.lstrip("/")
    return None


def _boot_lines_ok(text: str, lsm_value: str) -> bool:
    saw = False
    for raw in text.splitlines():
        stripped = raw.strip()
        if not (_linux_command(stripped) or _loader_options(stripped)):
            continue
        saw = True
        if not firmware_cmdline_ok(stripped, lsm_value):
            return False
    return saw


def _find_named(root: Path, base: str, name: str) -> list[Path]:
    folder = root / base
    if not folder.is_dir():
        return []
    return sorted(path for path in folder.rglob(name) if path.is_file())


def _loader_entries(root: Path) -> list[Path]:
    found: list[Path] = []
    for base in ("boot/loader/entries", "boot/efi/loader/entries"):
        folder = root / base
        if folder.is_dir():
            found.extend(sorted(path for path in folder.glob("*.conf") if path.is_file()))
    return found


def _findmnt_uuid(mountpoint: str) -> str:
    try:
        proc = subprocess.run(
            ["findmnt", "-n", "-o", "UUID", mountpoint],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    line = (proc.stdout or "").strip().splitlines()
    return line[0].strip() if line else ""


def _lsblk_rows() -> list[dict]:
    try:
        proc = subprocess.run(
            ["lsblk", "-J", "-o", "NAME,LABEL,UUID,FSTYPE,PARTTYPE,MOUNTPOINT,PATH"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return []
    rows: list[dict] = []

    def walk(nodes: object) -> None:
        if not isinstance(nodes, list):
            return
        for node in nodes:
            if isinstance(node, dict):
                rows.append(node)
                walk(node.get("children"))

    walk(payload.get("blockdevices") if isinstance(payload, dict) else None)
    return rows


def ensure_esp_mounted() -> str:
    """Mount the image's UEFI partition at /boot/efi when it is not already there.

    Ubuntu CPC labels that vfat UEFI. The lab only mounts that label, or a
    vfat partition whose type is the EFI system GUID. It does not mount an
    arbitrary disk.
    """
    if Path("/boot/efi/EFI").is_dir() or Path("/boot/efi/efi").is_dir():
        return "already"
    rows = _lsblk_rows()
    for row in rows:
        label = str(row.get("label") or "")
        part = str(row.get("parttype") or "").lower()
        fstype = str(row.get("fstype") or "").lower()
        mountpoint = str(row.get("mountpoint") or "")
        if fstype != "vfat":
            continue
        if label.upper() != "UEFI" and part != EFI_PARTTYPE:
            continue
        if mountpoint and (Path(mountpoint) / "EFI").is_dir():
            Path("/boot/efi").mkdir(parents=True, exist_ok=True)
            try:
                proc = subprocess.run(
                    ["mount", "--bind", mountpoint, "/boot/efi"],
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
            except (OSError, subprocess.TimeoutExpired):
                return "absent"
            if proc.returncode == 0:
                return "mounted"
    device = ""
    for row in rows:
        label = str(row.get("label") or "")
        part = str(row.get("parttype") or "").lower()
        fstype = str(row.get("fstype") or "").lower()
        path = str(row.get("path") or "")
        mountpoint = str(row.get("mountpoint") or "")
        if fstype != "vfat" or mountpoint or not path.startswith("/dev/"):
            continue
        if label.upper() == "UEFI" or part == EFI_PARTTYPE:
            device = path
            break
    if not device:
        return "absent"
    Path("/boot/efi").mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            ["mount", "-o", "umask=0077", device, "/boot/efi"],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "absent"
    if proc.returncode != 0:
        return "absent"
    return "mounted"


def _mount_uuid(uuid: str) -> Path | None:
    if _UUID_RE.fullmatch(uuid) is None:
        return None
    target = Path("/run/vantio-lsm-boot")
    if target.is_mount():
        return target
    target.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            ["mount", "-U", uuid, str(target)],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return target


def grub_package_lines() -> list[str]:
    """Installed grub-efi and grub-pc package names. Missing packages are omitted."""
    try:
        proc = subprocess.run(
            ["dpkg-query", "-W", "-f", "${Package} ${Version}\\n", *_GRUB_PACKAGES],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    lines = []
    for raw in (proc.stdout or "").splitlines():
        text = raw.strip()
        if text and not text.endswith(" "):
            lines.append(text)
    return lines


def _read_bootchain() -> dict:
    if not BOOTCHAIN_PATH.is_file():
        return {}
    try:
        loaded = json.loads(BOOTCHAIN_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _grub_alias_state(alias: Path, menu: Path, rewritten: list[Path]) -> str:
    """How /grub/grub.cfg relates to the menu update-grub writes.

    The EFI stub's prefix ($root)'/grub' opens this path when the searched
    filesystem is mounted at /. A separate /boot filesystem opens
    /boot/grub/grub.cfg instead, and this file is then absent or a different
    inode.
    """
    if not alias.is_file():
        return "absent"
    try:
        if menu.is_file() and alias.resolve() == menu.resolve():
            return "same-file"
    except OSError:
        pass
    if alias in rewritten:
        return "sealed"
    return "present"


def seal_firmware_tree(
    root: Path,
    lsm_value: str,
    *,
    mount: bool = False,
    boot_uuid: str = "",
    root_uuid: str = "",
    esp_uuid: str = "",
) -> dict:
    """Put the lab lsm= list on the boot file the firmware actually reads.

    update-grub rewrites /boot/grub/grub.cfg. On the Ubuntu CPC image that file
    is not always the one GRUB executes: the EFI stub search.fs_uuid's another
    filesystem, or the EFI path holds a full menu. A stub is not overwritten.
    Linux lines gain lsm= before panic=-1. mount is honored only for the real
    root, and only for the UEFI label or the stub UUID.
    """
    _valid_lsm(lsm_value)
    live = root == Path("/")
    esp_state = "absent"
    if mount and live:
        esp_state = ensure_esp_mounted()
        boot_uuid = boot_uuid or _findmnt_uuid("/boot")
        root_uuid = root_uuid or _findmnt_uuid("/")
        esp_uuid = esp_uuid or _findmnt_uuid("/boot/efi")
    elif (root / "boot/efi/EFI").is_dir() or (root / "boot/efi/efi").is_dir():
        esp_state = "already"
    bios = _find_named(root, "boot/grub", "grub.cfg")
    efi_cfgs = _find_named(root, "boot/efi", "grub.cfg")
    originals: dict[Path, str] = {}
    for path in bios + efi_cfgs + _loader_entries(root):
        originals[path] = path.read_text(encoding="utf-8", errors="replace")
    stub_facts = {"kind": "absent", "uuid": "", "prefix": "", "configfile": "", "head": ""}
    for path in efi_cfgs:
        info = efi_stub_facts(originals[path])
        if info["kind"] != "stub":
            continue
        stub_facts = info
        if path.as_posix().lower().endswith("/efi/ubuntu/grub.cfg"):
            break
    if stub_facts["kind"] == "absent":
        for path in efi_cfgs:
            info = efi_stub_facts(originals[path])
            if info["kind"] == "menu":
                stub_facts = info
                break
    written: list[tuple[Path, str | None]] = []

    def commit(path: Path, new: str, old: str | None) -> None:
        if old is not None and new == old:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new, encoding="utf-8")
        written.append((path, old))

    def rollback() -> None:
        for path, old in written:
            if old is None:
                path.unlink(missing_ok=True)
            else:
                path.write_text(old, encoding="utf-8")

    error = ""
    rewritten: list[Path] = []
    for path, old in originals.items():
        if efi_stub_facts(old)["kind"] == "stub":
            continue
        if not any(_linux_command(line.strip()) or _loader_options(line.strip()) for line in old.splitlines()):
            continue
        new = rewrite_firmware_text(old, lsm_value)
        if not _boot_lines_ok(new, lsm_value):
            error = "firmware_line"
            break
        commit(path, new, old)
        rewritten.append(path)
    side_target: Path | None = None
    if not error and stub_facts["kind"] == "stub":
        target = resolve_stub_target(
            root,
            stub_facts,
            boot_uuid=boot_uuid,
            root_uuid=root_uuid,
            esp_uuid=esp_uuid,
        )
        sealed = target is not None and target in rewritten
        if target is not None and target.is_file() and not sealed:
            old = originals.get(target, target.read_text(encoding="utf-8", errors="replace"))
            if efi_stub_facts(old)["kind"] != "stub":
                new = rewrite_firmware_text(old, lsm_value)
                if _boot_lines_ok(new, lsm_value):
                    commit(target, new, old)
                    rewritten.append(target)
                    sealed = True
                else:
                    error = "firmware_line"
        if not sealed and not error and mount and live and stub_facts["uuid"]:
            mounted_at = _mount_uuid(stub_facts["uuid"])
            rel = config_relpath(stub_facts)
            side_target = mounted_at / rel if mounted_at is not None and rel else None
            if side_target is not None and side_target.is_file():
                old = side_target.read_text(encoding="utf-8", errors="replace")
                if efi_stub_facts(old)["kind"] == "stub":
                    error = "stub_target_is_stub"
                else:
                    new = rewrite_firmware_text(old, lsm_value)
                    if _boot_lines_ok(new, lsm_value):
                        commit(side_target, new, old)
                        rewritten.append(side_target)
                        sealed = True
                    else:
                        error = "firmware_line"
            elif not sealed:
                error = f"boot_uuid_mismatch:{stub_facts['uuid']}"
        elif not sealed and not error:
            uuid = stub_facts["uuid"].lower()
            on_mounted = bool(uuid) and (
                (boot_uuid and uuid == boot_uuid.lower())
                or (root_uuid and uuid == root_uuid.lower())
                or (esp_uuid and uuid == esp_uuid.lower())
            )
            if on_mounted or not stub_facts["uuid"]:
                error = "stub_target_missing"
            else:
                error = f"boot_uuid_mismatch:{stub_facts['uuid']}"
    alias = root / "grub" / "grub.cfg"
    same_fs = bool(
        boot_uuid
        and root_uuid
        and stub_facts.get("uuid")
        and boot_uuid.lower() == root_uuid.lower() == str(stub_facts.get("uuid")).lower()
    )
    if not error and same_fs:
        menu_path = next((path for path in rewritten if path.as_posix().endswith("/boot/grub/grub.cfg")), None)
        if menu_path is not None:
            same_file = False
            if alias.is_file():
                try:
                    same_file = alias.resolve() == menu_path.resolve()
                except OSError:
                    same_file = False
            if not same_file:
                menu = menu_path.read_text(encoding="utf-8")
                if _boot_lines_ok(menu, lsm_value) and efi_stub_facts(menu)["kind"] != "stub":
                    old = alias.read_text(encoding="utf-8", errors="replace") if alias.is_file() else None
                    commit(alias, menu, old)
                    if alias not in rewritten:
                        rewritten.append(alias)
    if error:
        rollback()
        rewritten = []
    elif live:
        try:
            os.sync()
        except OSError:
            pass
    compared = ""
    uuid = str(stub_facts.get("uuid") or "").lower()
    if boot_uuid and uuid == boot_uuid.lower():
        compared = boot_uuid
    elif root_uuid and uuid == root_uuid.lower():
        compared = root_uuid
    elif esp_uuid and uuid == esp_uuid.lower():
        compared = esp_uuid
    if stub_facts["kind"] == "stub":
        decision = stub_boot_decision(
            str(stub_facts.get("uuid") or ""),
            compared or boot_uuid or root_uuid,
            target_sealed=bool(rewritten) and not error,
        )
        if error.startswith("boot_uuid_mismatch:"):
            decision = error
    elif stub_facts["kind"] == "menu":
        decision = "menu"
    elif stub_facts["kind"] == "absent":
        decision = "no_efi"
    else:
        decision = str(stub_facts["kind"])
    bios_ok = True
    for path in bios:
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        if any(_linux_command(line.strip()) for line in text.splitlines()) and not _boot_lines_ok(text, lsm_value):
            bios_ok = False
    if not bios_ok and not error:
        error = "bios_grub_cfg"
        rollback()
        rewritten = []
    grub_d: list[str] = []
    extra = root / "etc/default/grub.d"
    if extra.is_dir():
        grub_d = sorted(path.name for path in extra.glob("*.cfg"))[:12]
    stock_line = ""
    firmware_paths = [path for path in efi_cfgs + _loader_entries(root) if path in originals]
    for path in firmware_paths:
        old = originals[path]
        if efi_stub_facts(old)["kind"] == "stub":
            continue
        for raw in old.splitlines():
            stripped = raw.strip()
            if _linux_command(stripped) or _loader_options(stripped):
                stock_line = stripped[:240]
                break
        if stock_line:
            break
    relative: list[str] = []
    for path in rewritten:
        try:
            relative.append(str(path.resolve().relative_to(root.resolve())))
        except (OSError, ValueError):
            relative.append(str(path))
    bootchain = {
        "efi_kind": stub_facts["kind"],
        "efi_head": stub_facts["head"],
        "stub_uuid": stub_facts["uuid"],
        "stub_prefix": stub_facts["prefix"],
        "configfile": stub_facts["configfile"],
        "esp": esp_state,
        "decision": decision,
        "uuid_mount": (
            "same"
            if boot_uuid
            and root_uuid
            and uuid
            and boot_uuid.lower() == root_uuid.lower() == uuid
            else "boot"
            if boot_uuid and uuid == boot_uuid.lower()
            else "root"
            if root_uuid and uuid == root_uuid.lower()
            else "esp"
            if esp_uuid and uuid == esp_uuid.lower()
            else ""
        ),
        "boot_uuid": boot_uuid,
        "root_uuid": root_uuid,
        "esp_uuid": esp_uuid,
        "grub_alias": _grub_alias_state(alias, root / "boot/grub/grub.cfg", rewritten),
        "stock_line": stock_line,
        "rewritten": relative[:6],
        "grub_d": grub_d,
        "packages": grub_package_lines() if live else [],
        "kernel": os.uname().release if live else "",
        "error": error,
    }
    if live:
        try:
            BOOTCHAIN_PATH.parent.mkdir(parents=True, exist_ok=True)
            BOOTCHAIN_PATH.write_text(json.dumps(bootchain, indent=2) + "\n", encoding="utf-8")
        except OSError:
            pass
    ok = not error
    if ok and not bios and not efi_cfgs and not any(
        _loader_options(line.strip())
        for path in _loader_entries(root)
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
    ):
        ok = False
        bootchain["error"] = "no_boot_config"
    return {"ok": ok, "error": bootchain.get("error") or "", "bootchain": bootchain}


def grubenv_assignments(data: bytes) -> list[str]:
    """Assignment lines in a grubenv block. Hash padding and the warning are not keys.

    Run 38800477282 hashed boot/grub/grubenv as
    f64122858064885ef0733e42c6a3d2d3fd642671f714db0d974b880c0f087430.
    That is the empty grub-editenv block: no saved_entry, next_entry,
    recordfail, or initrdfail. The keys have to be in the evidence, not
    recovered from the hash after the instance is gone.
    """
    text = data.decode("utf-8", "replace")
    found: list[str] = []
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        found.append(line[:200])
        if len(found) >= 12:
            break
    return found


def read_grubenv_assignments(root: Path | None = None) -> list[str]:
    tree = root if root is not None else Path("/")
    path = tree / "boot/grub/grubenv"
    if not path.is_file():
        return []
    try:
        return grubenv_assignments(path.read_bytes())
    except OSError:
        return []


def kernel_command_lines(text: str) -> list[str]:
    """The command lines the kernel logged. /proc/cmdline is a separate read."""
    found: list[str] = []
    for line in text.splitlines():
        for marker in ("Kernel command line:", "Command line:"):
            index = line.find(marker)
            if index == -1:
                continue
            found.append(line[index + len(marker) :].strip()[:1200])
            break
        if len(found) >= 4:
            break
    return found


def read_kernel_command_lines() -> list[str]:
    try:
        proc = subprocess.run(["dmesg"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return kernel_command_lines((proc.stdout or "") + "\n" + (proc.stderr or ""))


def read_boot_id() -> str:
    path = Path("/proc/sys/kernel/random/boot_id")
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if "\n" in text or len(text) > 80:
        return ""
    return text


def boot_file_manifest(root: Path) -> list[dict]:
    """Hash every grub.cfg and grubenv under /boot, /efi, and /grub.

    The EFI stub loads ($root)/grub/grub.cfg. update-grub writes
    /boot/grub/grub.cfg. Both are listed, with the linux line each one would
    boot, so a later cmdline can be matched to a hash.
    """
    names = {"grub.cfg", "grubenv"}
    found: list[Path] = []
    seen: set[str] = set()
    bases = [root / "boot", root / "efi", root / "grub", root / "grub" / "grub.cfg"]
    for base in bases:
        if base.is_file() and base.name in names:
            paths = [base]
        elif base.is_dir():
            paths = [path for path in base.rglob("*") if path.is_file() and path.name in names]
        else:
            continue
        for path in paths:
            try:
                key = str(path.resolve())
            except OSError:
                key = path.as_posix()
            if key in seen:
                continue
            seen.add(key)
            found.append(path)
    records: list[dict] = []
    for path in sorted(found, key=lambda item: item.as_posix()):
        try:
            data = path.read_bytes()
        except OSError:
            continue
        text = data.decode("utf-8", "replace")
        kind = "env" if path.name == "grubenv" else str(efi_stub_facts(text).get("kind") or "")
        try:
            rel = str(path.resolve().relative_to(root.resolve()))
        except (OSError, ValueError):
            rel = path.as_posix()
        record = {
            "path": rel,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
            "kind": kind,
            "boot_line": first_linux_line(text)[:240],
        }
        if kind == "env":
            record["variables"] = grubenv_assignments(data)
        records.append(record)
        if len(records) >= 16:
            break
    return records


def _command_text(argv: list[str]) -> str:
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return type(exc).__name__
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        text = f"rc={proc.returncode}\n{text}"
    return text[:4000]


def boot_evidence_snapshot(root: Path | None = None) -> dict:
    """Files the stub can load, plus efibootmgr on the live root."""
    tree = root if root is not None else Path("/")
    body: dict = {"files": boot_file_manifest(tree)}
    if tree == Path("/"):
        body["uuid"] = {
            "root": _findmnt_uuid("/"),
            "boot": _findmnt_uuid("/boot"),
            "esp": _findmnt_uuid("/boot/efi"),
        }
        body["efibootmgr"] = _command_text(["efibootmgr", "-v"])
        cmdline = Path("/proc/cmdline")
        body["cmdline"] = cmdline.read_text(encoding="utf-8").strip()[:400] if cmdline.is_file() else ""
    return body


def reboot_with_grub_script(lsm_value: str = "") -> str:
    """Regenerate grub from the drop-in and reboot only if that menuentry has lsm=.

    10_linux appends panic=-1 after the variables. A token pasted after that
    word is not the line update-grub will write again, and it is not the line
    the GCP guest recorded in /proc/cmdline. The drop-in is sourced after
    50-cloudimg-settings.cfg, so a later package trigger keeps the same args.
    """
    if lsm_value and (not re.fullmatch(r"[A-Za-z0-9_,.-]+", lsm_value) or not bpf_lsm_active(lsm_value)):
        raise ValueError("lsm_value")
    if not lsm_value:
        return (
            "#!/bin/bash\n"
            "set -euo pipefail\n"
            "mkdir -p /var/lib/vantio-lab\n"
            "echo 'refusing reboot: no lab lsm token' >>/var/lib/vantio-lab/grub-mkconfig.txt\n"
            "exit 1\n"
        )
    token = f"lsm={lsm_value}"
    return f"""#!/bin/bash
# Boot the panic=-1 line that already carries the lab lsm= list. Run
# 38789348650 regenerated that file after the seal and the kernel came back
# on the stock else line. Do not append past panic=-1.
set -euo pipefail
token='{token}'
log=/var/lib/vantio-lab/grub-mkconfig.txt
dropin=/etc/default/grub.d/99-vantio-lsm.cfg
mkdir -p /var/lib/vantio-lab
: >"$log"
updater=update-grub
is_linux() {{
  case "$1" in
    linux|linux[[:space:]]*|linuxefi|linuxefi[[:space:]]*) return 0 ;;
    *) return 1 ;;
  esac
}}
has_panic() {{
  for part in $1; do
    if [ "$part" = "panic=-1" ]; then
      return 0
    fi
  done
  return 1
}}
line_ok() {{
  last=""
  end=""
  saw_panic=0
  for part in $1; do
    end=$part
    case "$part" in
      lsm=*) last=$part ;;
      panic=-1) saw_panic=1 ;;
    esac
  done
  [ "$last" = "$token" ] || return 1
  if [ "$saw_panic" -eq 1 ] && [ "$end" != "panic=-1" ]; then
    return 1
  fi
  return 0
}}
verify() {{
  path="$1"
  if [ ! -f "$path" ]; then
    if [ "$path" = /boot/grub/grub.cfg ]; then
      echo "refusing reboot: missing $path" >>"$log"
      exit 1
    fi
    return 0
  fi
  panic_lines=0
  while IFS= read -r line || [ -n "$line" ]; do
    stripped=$(printf '%s\\n' "$line" | sed 's/^[[:space:]]*//')
    is_linux "$stripped" || continue
    if has_panic "$stripped"; then
      panic_lines=1
    fi
  done <"$path"
  saw=0
  while IFS= read -r line || [ -n "$line" ]; do
    stripped=$(printf '%s\\n' "$line" | sed 's/^[[:space:]]*//')
    is_linux "$stripped" || continue
    if [ "$panic_lines" -eq 1 ] && ! has_panic "$stripped"; then
      continue
    fi
    saw=1
    if ! line_ok "$stripped"; then
      echo "refusing reboot: $path: $stripped" >>"$log"
      exit 1
    fi
    echo "boot line $path: $stripped" >>"$log"
  done <"$path"
  if [ "$path" = /boot/grub/grub.cfg ] && [ "$saw" -eq 0 ]; then
    echo "refusing reboot: no linux line in $path" >>"$log"
    exit 1
  fi
}}
holds() {{
  path="$1"
  if [ ! -f "$path" ]; then
    return 1
  fi
  panic_lines=0
  while IFS= read -r line || [ -n "$line" ]; do
    stripped=$(printf '%s\\n' "$line" | sed 's/^[[:space:]]*//')
    is_linux "$stripped" || continue
    if has_panic "$stripped"; then
      panic_lines=1
    fi
  done <"$path"
  saw=0
  while IFS= read -r line || [ -n "$line" ]; do
    stripped=$(printf '%s\\n' "$line" | sed 's/^[[:space:]]*//')
    is_linux "$stripped" || continue
    if [ "$panic_lines" -eq 1 ] && ! has_panic "$stripped"; then
      continue
    fi
    saw=1
    line_ok "$stripped" || return 1
  done <"$path"
  if [ "$path" = /boot/grub/grub.cfg ] && [ "$saw" -eq 0 ]; then
    return 1
  fi
  return 0
}}
if holds /boot/grub/grub.cfg; then
  echo "keeping sealed boot line" >>"$log"
else
  if [ ! -f "$dropin" ]; then
    echo "refusing reboot: missing $dropin" >>"$log"
    exit 1
  fi
  chmod 755 "$dropin"
  if ! command -v "$updater" >/dev/null 2>&1; then
    echo "refusing reboot: update-grub missing" >>"$log"
    exit 1
  fi
  if ! "$updater" >>"$log" 2>&1; then
    echo "refusing reboot: update-grub failed" >>"$log"
    exit 1
  fi
  if [ "$dropin" = /etc/default/grub.d/99-vantio-lsm.cfg ] && [ -f /var/lib/vantio-lab/guest/baseline_diag.py ]; then
    if ! python3 - /var/lib/vantio-lab/guest "$token" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import baseline_diag
token = sys.argv[2]
value = token.split("=", 1)[1]
result = baseline_diag.seal_firmware_tree(baseline_diag.Path("/"), value, mount=True)
print(result.get("bootchain") or {{}})
if not result.get("ok"):
    raise SystemExit(result.get("error") or "seal")
PY
    then
      echo "refusing reboot: firmware seal failed" >>"$log"
      exit 1
    fi
  fi
fi
verify /boot/grub/grub.cfg
if [ -d /boot/efi ]; then
  while IFS= read -r path; do
    [ -n "$path" ] || continue
    verify "$path"
  done < <(find /boot/efi -type f -name grub.cfg 2>/dev/null || true)
fi
if command -v sync >/dev/null 2>&1; then
  sync -f /boot/grub/grub.cfg >>"$log" 2>&1 || sync >>"$log" 2>&1 || true
fi
verify /boot/grub/grub.cfg
if [ -f /var/lib/vantio-lab/guest/baseline_diag.py ]; then
  python3 - /var/lib/vantio-lab/guest <<'PY' >>"$log" 2>&1 || echo "boot-evidence failed" >>"$log"
import json, sys
sys.path.insert(0, sys.argv[1])
import baseline_diag
body = baseline_diag.boot_evidence_snapshot()
baseline_diag.Path("/var/lib/vantio-lab/boot-evidence.json").write_text(json.dumps(body) + "\\n", encoding="utf-8")
print("boot-evidence", len(body.get("files") or []))
PY
fi
echo "reboot boot line ok" >>"$log"
systemctl reboot --force
"""


def assignments_with_lsm(text: str, lsm_value: str) -> str:
    """Put lsm= on every grub assignment in a cloud image drop-in file."""
    token = f"lsm={lsm_value}"
    lines: list[str] = []
    for raw in text.splitlines():
        matched = re.match(r"^(\s*)(GRUB_CMDLINE_LINUX(?:_DEFAULT)?)(\s*=\s*)(.*)$", raw)
        if matched is None:
            lines.append(raw)
            continue
        quoted = matched.group(4).strip()
        quote = '"'
        if len(quoted) >= 2 and quoted[0] == quoted[-1] and quoted[0] in {'"', "'"}:
            value = quoted[1:-1]
            quote = quoted[0]
        else:
            value = quoted
        tokens = [part for part in value.split() if part and not part.startswith("lsm=")]
        tokens.append(token)
        lines.append(f"{matched.group(1)}{matched.group(2)}={quote}{' '.join(tokens)}{quote}")
    body = "\n".join(lines)
    if text.endswith("\n") or not text:
        body += "\n"
    return body


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


def render_cloudimg_linux_line(main: str, cloud: str, lsm_value: str) -> str:
    """Linux line after /etc/default/grub, 50-cloudimg-settings.cfg, and the lab drop-in.

    The cloud file is sourced later and can clear GRUB_CMDLINE_LINUX. The
    drop-in is sourced last, twice, because a package trigger sources grub.d
    again. The emitted line is the one 10_linux writes: variable args, then
    panic=-1.
    """
    planned = plan_grub_lsm(main, [cloud], lsm_value)
    if planned.get("error"):
        raise ValueError(str(planned["error"]))
    extras = planned.get("extras")
    if not isinstance(extras, list) or len(extras) != 1 or not isinstance(planned.get("main"), str):
        raise ValueError("grub_plan")
    written_cloud = assignments_with_lsm(extras[0], lsm_value)
    dropin = lsm_dropin_text(lsm_value)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        main_path = root / "grub"
        cloud_path = root / "50-cloudimg-settings.cfg"
        drop_path = root / "99-vantio-lsm.cfg"
        main_path.write_text(planned["main"], encoding="utf-8")
        cloud_path.write_text(written_cloud, encoding="utf-8")
        drop_path.write_text(dropin, encoding="utf-8")
        emit = (
            "linux /vmlinuz-7.0.0-1013-aws "
            "root=PARTUUID=1feb5770-cc6a-4240-8c18-3b802f140518 "
            "ro $GRUB_CMDLINE_LINUX $GRUB_CMDLINE_LINUX_DEFAULT panic=-1"
        )
        script = "\n".join(
            [
                "set -eu",
                f'. "{main_path}"',
                f'. "{cloud_path}"',
                f'. "{drop_path}"',
                f'. "{drop_path}"',
                f'printf "%s\\n" "{emit}"',
            ]
        )
        ran = subprocess.run(["dash", "-c", script], capture_output=True, text=True)
    if ran.returncode != 0:
        raise RuntimeError((ran.stderr or "dash").strip())
    return (ran.stdout or "").strip()


def lsm_value_from_dropin(text: str) -> str:
    """The bpf lsm= list named by the lab drop-in, or empty."""
    found = ""
    for match in re.finditer(r"lsm=([A-Za-z0-9_,.-]+)", text):
        value = match.group(1)
        if bpf_lsm_active(value):
            found = value
    return found


def boot_lines_carry_lsm(text: str, lsm_value: str) -> bool:
    """True when any generated linux line still has this lsm= word."""
    needle = f"lsm={lsm_value}"
    return any(needle in line.split() for line in linux_lines(text))


def strip_lsm_assignments(text: str, lsm_value: str) -> str:
    """Drop one lab lsm= word from GRUB_CMDLINE assignments. Other lines stay."""
    needle = f"lsm={lsm_value}"
    lines: list[str] = []
    for raw in text.splitlines():
        matched = re.match(r"^(\s*)(GRUB_CMDLINE_LINUX(?:_DEFAULT)?)(\s*=\s*)(.*)$", raw)
        if matched is None:
            lines.append(raw)
            continue
        quoted = matched.group(4).strip()
        quote = '"'
        if len(quoted) >= 2 and quoted[0] == quoted[-1] and quoted[0] in {'"', "'"}:
            value = quoted[1:-1]
            quote = quoted[0]
        else:
            value = quoted
        tokens = [part for part in value.split() if part != needle]
        lines.append(f"{matched.group(1)}{matched.group(2)}={quote}{' '.join(tokens)}{quote}")
    body = "\n".join(lines)
    if text.endswith("\n") or not text:
        body += "\n"
    return body


def _grub_cfg_paths(root: Path) -> list[Path]:
    found: list[Path] = []
    for base in ("boot/grub", "boot/efi"):
        folder = root / base
        if folder.is_dir():
            found.extend(sorted(path for path in folder.rglob("grub.cfg") if path.is_file()))
    return found


def uninstall_keeps_boot_token(body: dict) -> bool:
    """The guard proved the refusal and the next boot still needs the drop-in."""
    return (
        isinstance(body, dict)
        and body.get("host_result") == "GUARD_PROVED"
        and body.get("reboot_requested") is True
    )


def remove_consented_lsm(root: Path, updater) -> dict:
    """Remove the lab lsm= token from grub and regenerate.

    apply_consented_lsm writes the token into /etc/default/grub, into
    grub.d snippets such as 50-cloudimg-settings.cfg, and into
    99-vantio-lsm.cfg. Deleting only the drop-in leaves the token in the
    files update-grub sources. This strips that word, deletes the drop-in,
    regenerates, and checks every grub.cfg under /boot/grub and /boot/efi.
    No drop-in is a no-op. A failed regenerate or a boot line that still
    carries the token restores the edited files and fails closed.
    """
    dropin = root / "etc/default/grub.d/99-vantio-lsm.cfg"
    if not dropin.is_file():
        return {"ok": True, "removed": False, "error": ""}
    prior_dropin = dropin.read_text(encoding="utf-8")
    token = lsm_value_from_dropin(prior_dropin)
    if not token:
        return {"ok": False, "removed": False, "error": "lsm_value"}
    edited: list[tuple[Path, str]] = []
    main = root / "etc/default/grub"
    if main.is_file():
        edited.append((main, main.read_text(encoding="utf-8")))
    extra_dir = root / "etc/default/grub.d"
    if extra_dir.is_dir():
        for path in sorted(extra_dir.glob("*.cfg")):
            if path == dropin:
                continue
            edited.append((path, path.read_text(encoding="utf-8")))
    for path, text in edited:
        path.write_text(strip_lsm_assignments(text, token), encoding="utf-8")
    dropin.unlink()

    def restore() -> None:
        for path, text in edited:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        dropin.parent.mkdir(parents=True, exist_ok=True)
        dropin.write_text(prior_dropin, encoding="utf-8")
        dropin.chmod(0o755)

    try:
        rc = int(updater())
    except (OSError, TypeError, ValueError):
        rc = 1
    configs = _grub_cfg_paths(root)
    remains = False
    for path in configs:
        text = path.read_text(encoding="utf-8", errors="replace")
        if boot_lines_carry_lsm(text, token):
            remains = True
            break
    if rc != 0 or remains or not configs:
        restore()
        if rc != 0:
            error = "update_grub"
        elif not configs:
            error = "grub_cfg_missing"
        else:
            error = "grub_cfg_still_has_lsm"
        return {"ok": False, "removed": False, "error": error}
    return {"ok": True, "removed": True, "error": ""}


def remove_consented_lsm_live() -> int:
    """0 when the lab token is gone from the generated grub menus."""

    def updater() -> int:
        try:
            proc = subprocess.run(["update-grub"], capture_output=True, text=True)
        except OSError:
            return 1
        if proc.returncode == 0:
            return 0
        try:
            proc = subprocess.run(
                ["grub-mkconfig", "-o", "/boot/grub/grub.cfg"],
                capture_output=True,
                text=True,
            )
        except OSError:
            return 1
        return proc.returncode

    result = remove_consented_lsm(Path("/"), updater)
    return 0 if result.get("ok") is True else 1


LOCKDOWN_PATH = Path("/sys/kernel/security/lockdown")
LOCKDOWN_MODES = frozenset({"none", "integrity", "confidentiality"})
EXACT_IMAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+/-]{0,159}$")
IMAGE_FAMILIES = frozenset(
    {
        "ubuntu-2404-lts-amd64",
        "ubuntu-os-cloud/ubuntu-2404-lts-amd64",
    }
)


def exact_image_name(value: object) -> str:
    """The image that booted. A family name or a filter with a star is not it."""
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text or "\n" in text or "*" in text or text in IMAGE_FAMILIES:
        return ""
    if EXACT_IMAGE_RE.fullmatch(text) is None:
        return ""
    return text


def accept_lockdown(text: str) -> str:
    """The live lockdown file, or empty when the text is not that file."""
    cleaned = text.strip()
    if not cleaned or "\n" in cleaned or len(cleaned) > 80:
        return ""
    parts = cleaned.split(" ")
    if not parts or len(parts) > 4:
        return ""
    for part in parts:
        if not part:
            return ""
        bare = part[1:-1] if part.startswith("[") and part.endswith("]") and len(part) > 2 else part
        if bare not in LOCKDOWN_MODES or part.count("[") > 1:
            return ""
    return cleaned


def read_lockdown(path: Path | None = None) -> str:
    """Live /sys/kernel/security/lockdown. The bracket marks the active mode."""
    source = LOCKDOWN_PATH if path is None else path
    try:
        text = source.read_text(encoding="utf-8")
    except OSError:
        return ""
    return accept_lockdown(text)


def stock_reboot_script() -> str:
    """Reboot the menu already installed on a fresh host.

    The LSM guard writes a different script at the same path after it seals
    grub. This one does not call update-grub and does not invent an lsm= line.
    The last command is the systemctl reboot that sealed script uses.
    """
    return """#!/bin/bash
# Fresh host. The sealed reboot script is not on disk yet. Reboot the
# menu that is already installed. Do not regenerate the menu.
set -euo pipefail
log=/var/lib/vantio-lab/grub-mkconfig.txt
mkdir -p /var/lib/vantio-lab
: >"$log"
echo "stock reboot" >>"$log"
if [ -r /proc/cmdline ]; then
  echo "cmdline $(tr -d '\\n' </proc/cmdline)" >>"$log"
fi
if command -v sync >/dev/null 2>&1; then
  sync >>"$log" 2>&1 || true
fi
echo "reboot boot line ok" >>"$log"
systemctl reboot --force
"""


def install_stock_reboot_script(path: Path | None = None) -> str:
    """Write the fresh-host reboot script when the sealed one is not already there."""
    target = Path("/var/lib/vantio-lab/reboot-with-grub.sh") if path is None else path
    if target.is_file() and os.access(target, os.X_OK) and target.stat().st_size > 0:
        return "present"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(stock_reboot_script(), encoding="utf-8")
    target.chmod(0o755)
    if not target.is_file() or not os.access(target, os.X_OK):
        raise OSError("reboot_script_missing")
    return "installed"


def _gcp_guest() -> bool:
    vendor = Path("/sys/class/dmi/id/sys_vendor")
    try:
        return "google" in vendor.read_text(encoding="utf-8", errors="replace").lower()
    except OSError:
        return False


def _gcp_metadata_image() -> str:
    request = urllib.request.Request(
        "http://metadata.google.internal/computeMetadata/v1/instance/image",
        headers={"Metadata-Flavor": "Google"},
    )
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            raw = response.read(512).decode("utf-8", "replace").strip()
    except (OSError, ValueError):
        return ""
    if "\n" in raw or len(raw) > 300:
        return ""
    return raw.rstrip("/").rsplit("/", 1)[-1]


def read_image_name() -> str:
    """Exact image name. The runner passes it; a GCP guest can also read metadata."""
    named = exact_image_name(os.environ.get("VANTIO_IMAGE_NAME", ""))
    if named:
        return named
    if not _gcp_guest():
        return ""
    return exact_image_name(_gcp_metadata_image())


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
    active = bpf_lsm_active(stock)
    if requested:
        if cmdline_has and active:
            result = "LSM_ENABLED"
            reason = "bpf_listed"
        elif not cmdline_has:
            result = "FAIL"
            reason = "cmdline_missing_bpf"
        else:
            result = "FAIL"
            reason = "bpf_not_active"
    else:
        result = "LSM_ALREADY_ACTIVE"
        reason = "stock_bpf_lsm"
    return {
        "battery": "lsm-guard",
        "host_result": result,
        "reason": reason,
        "stock_lsm": stock,
        "stock_bpf_lsm": bpf_lsm_active(stock),
        "cmdline": cmdline,
        "bpf_listed": bpf_lsm_active(stock),
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


def lsm_boot_decision(
    stock: str,
    cmdline: str,
    prior: dict | None,
    *,
    distro: str = "",
    kernel: str = "",
    image_id: str = "",
) -> tuple[dict | None, int]:
    """Confirm a requested reboot. 1 means the loader proof still has to run."""
    requested = isinstance(prior, dict) and prior.get("reboot_requested") is True
    if not bpf_lsm_active(stock) and not requested:
        return None, 1
    body = lsm_status_body(
        stock,
        cmdline,
        prior,
        distro=distro,
        kernel=kernel,
        image_id=image_id,
    )
    if body["host_result"] == "FAIL":
        return body, 2
    return body, 0


def lsm_row_paths() -> tuple[Path, Path]:
    return (LSM_ROWS_PATH, LAB_ROWS_PATH)


def write_lsm_rows(body: dict) -> dict:
    """Write this boot's LSM result to the durable file and the /tmp mirror.

    The runner reads /var/lib/vantio-lab/enterprise-pe-rows.json. A second
    boot that only refreshes /tmp would leave the previous boot's file
    in place, so this writes that durable path too.
    """
    stamped = dict(body)
    boot = stamped.get("boot_id")
    if not isinstance(boot, str) or not boot or "\n" in boot or len(boot) > 80:
        stamped["boot_id"] = read_boot_id()
    lockdown = read_lockdown()
    if lockdown:
        stamped["lockdown"] = lockdown
    image_name = exact_image_name(stamped.get("image_name")) or read_image_name()
    if image_name:
        stamped["image_name"] = image_name
    text = json.dumps(stamped, indent=2) + "\n"
    for path in lsm_row_paths():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        try:
            os.chmod(path, 0o644)
        except OSError:
            pass
    print(text, flush=True)
    return stamped


def write_lsm_status() -> int:
    """0 when bpf is already an active LSM. 1 when the loader proof still has to run."""
    lsm_path = Path("/sys/kernel/security/lsm")
    stock = lsm_path.read_text(encoding="utf-8").strip() if lsm_path.is_file() else ""
    cmdline_path = Path("/proc/cmdline")
    cmdline = cmdline_path.read_text(encoding="utf-8").strip() if cmdline_path.is_file() else ""
    prior = None
    for mark in (LSM_STOCK_PATH, LSM_BOOT_MARK):
        if not mark.is_file():
            continue
        try:
            loaded = json.loads(mark.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(loaded, dict):
            prior = loaded
            break
    body, code = lsm_boot_decision(
        stock,
        cmdline,
        prior,
        distro=_pretty_distro(),
        kernel=os.uname().release,
        image_id=os.environ.get("VANTIO_IMAGE_ID", ""),
    )
    if body is None:
        chain = _read_bootchain()
        if chain and not cmdline_has_bpf_lsm(cmdline):
            mismatch = {
                "battery": "lsm-guard",
                "host_result": "FAIL",
                "reason": "firmware_not_booted",
                "cmdline": cmdline,
                "bootchain": chain,
                "lab_pass": False,
                "customer_claim": False,
                "reboot_requested": False,
            }
            write_lsm_rows(mismatch)
            return 2
        cfg = Path("/boot/grub/grub.cfg")
        disk = first_linux_line(cfg.read_text(encoding="utf-8", errors="replace")) if cfg.is_file() else ""
        if "lsm=" in disk and "bpf" in disk and not any(
            token.startswith("lsm=") and "bpf" in token.split("=", 1)[-1] for token in cmdline.split()
        ):
            mismatch = {
                "battery": "lsm-guard",
                "host_result": "FAIL",
                "reason": "grub_cfg_not_booted",
                "cmdline": cmdline,
                "grub_first_linux": disk[:500],
                "lab_pass": False,
                "customer_claim": False,
                "reboot_requested": False,
            }
            write_lsm_rows(mismatch)
            return 2
        return code
    if body.get("host_result") == "FAIL":
        cfg = Path("/boot/grub/grub.cfg")
        if cfg.is_file():
            body["grub_first_linux"] = first_linux_line(cfg.read_text(encoding="utf-8", errors="replace"))[:500]
        dropin = Path("/etc/default/grub.d/99-vantio-lsm.cfg")
        body["lsm_dropin_present"] = dropin.is_file()
    chain = _read_bootchain()
    if chain and "bootchain" not in body:
        body["bootchain"] = chain
    write_lsm_rows(body)
    return code


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
