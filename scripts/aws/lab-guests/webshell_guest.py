"""Run the sealed web-shell battery on a lab guest.

The script scripts/lab_webshell_battery.py has to be inside the seal tar.
A seal that does not carry it writes SEAL_LACKS_WEBSHELL and does not invent
a result. VANTIO_LAB_WEBSHELL=1 is required before the sealed script starts.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Mapping

import webshell_grade

SCRIPT_SUFFIX = "lab_webshell_battery.py"
MAX_SCRIPT_BYTES = 2_000_000
MAX_NEST_BYTES = 80_000_000
ROWS_TMP = Path("/tmp/enterprise-pe-rows.json")
ROWS_DURABLE = Path("/var/lib/vantio-lab/enterprise-pe-rows.json")
PRE_SNAPSHOT = Path("/var/lib/vantio-lab/webshell-pre.json")


def _safe_name(name: str) -> bool:
    if name.startswith("/") or name.startswith("\\"):
        return False
    parts = name.replace("\\", "/").split("/")
    return bool(name) and ".." not in parts


def _looks_like_tar(blob: bytes) -> bool:
    if blob.startswith(b"\x1f\x8b"):
        return True
    return len(blob) > 262 and blob[257:262] == b"ustar"


def extract_webshell_script(bundle: Path, dest_dir: Path) -> Path | None:
    """Copy lab_webshell_battery.py out of a seal tar. None when it is absent."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / SCRIPT_SUFFIX
    if target.exists():
        target.unlink()
    found = _search_tar(bundle, depth=0)
    if found is None:
        return None
    target.write_bytes(found)
    target.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
    return target


def _search_tar(path: Path, depth: int) -> bytes | None:
    if depth > 2 or not path.is_file():
        return None
    try:
        archive = tarfile.open(path, "r:*")
    except (tarfile.TarError, OSError):
        return None
    with archive:
        for member in archive.getmembers():
            if not member.isfile() or member.size <= 0 or member.size > MAX_NEST_BYTES:
                continue
            if not _safe_name(member.name):
                continue
            name = member.name.replace("\\", "/")
            if name.endswith(SCRIPT_SUFFIX):
                if member.size > MAX_SCRIPT_BYTES:
                    continue
                handle = archive.extractfile(member)
                if handle is None:
                    continue
                return handle.read()
            if depth >= 2:
                continue
            handle = archive.extractfile(member)
            if handle is None:
                continue
            blob = handle.read()
            if not _looks_like_tar(blob):
                continue
            with tempfile.TemporaryDirectory() as tmp:
                nested = Path(tmp) / "nested.tar"
                nested.write_bytes(blob)
                found = _search_tar(nested, depth + 1)
            if found is not None:
                return found
    return None


def _parse_stdout(text: str) -> dict[str, Any] | None:
    raw = text.strip()
    if not raw:
        return None
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            body = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return None
    if not isinstance(body, dict):
        return None
    return body


def _extend(into: dict[str, Any], key: str, value: object) -> None:
    if isinstance(value, list):
        current = into.get(key)
        if not isinstance(current, list):
            current = []
        current.extend(item for item in value if isinstance(item, dict))
        into[key] = current
        return
    if isinstance(value, dict) and isinstance(value.get("checks"), list):
        _extend(into, key, value["checks"])
        rest = {name: item for name, item in value.items() if name != "checks"}
        if rest and key in {"file_write", "loader_kill", "reboot"}:
            current = into.get(key)
            if not isinstance(current, dict):
                current = {}
            current.update(rest)
            into[key] = current
        return
    if isinstance(value, dict) and key in {"file_write", "loader_kill", "reboot"}:
        current = into.get(key)
        if not isinstance(current, dict):
            current = {}
        current.update(value)
        into[key] = current


def absorb_pe(into: dict[str, Any], body: Mapping[str, Any] | None, reboot_step: str | None) -> None:
    """Merge one sealed-script JSON object into the open-core row."""
    if body is None:
        into["pe_rows_unreadable"] = True
        return
    if body.get("reason") == "SEAL_LACKS_WEBSHELL":
        into["reason"] = "SEAL_LACKS_WEBSHELL"
    phases = body.get("phases") if isinstance(body.get("phases"), dict) else {}
    alias = {
        "file-write": "file_write",
        "shell-spawn": "exec",
        "child-evasion": "child_evasion",
        "loader-kill": "loader_kill",
        "reboot": "reboot",
    }
    for key in ("exec", "file_write", "loader_kill", "child_evasion", "reboot"):
        if key in body:
            _extend(into, key, body[key])
    for phase_name, key in alias.items():
        if phase_name in phases:
            _extend(into, key, phases[phase_name])
    boot = body.get("boot_id")
    if isinstance(boot, str) and boot:
        reboot = into.get("reboot")
        if not isinstance(reboot, dict):
            reboot = {}
        if reboot_step == "post":
            reboot["boot_id_after"] = boot
        elif reboot_step in {None, "pre"} and "boot_id_before" not in reboot:
            reboot["boot_id_before"] = boot
        into["reboot"] = reboot


def run_sealed_script(script: Path, reboot_step: str | None) -> dict[str, Any] | None:
    if os.environ.get("VANTIO_LAB_WEBSHELL") != "1":
        return None
    command = [sys.executable, str(script)]
    if reboot_step:
        command.extend(["--reboot-step", reboot_step])
    env = os.environ.copy()
    env["VANTIO_LAB_WEBSHELL"] = "1"
    completed = subprocess.run(
        command,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    return _parse_stdout(completed.stdout)


def _boot_id() -> str:
    path = Path("/proc/sys/kernel/random/boot_id")
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _write_rows(body: Mapping[str, Any]) -> None:
    text = json.dumps(body) + "\n"
    ROWS_TMP.parent.mkdir(parents=True, exist_ok=True)
    ROWS_TMP.write_text(text, encoding="utf-8")
    try:
        ROWS_DURABLE.parent.mkdir(parents=True, exist_ok=True)
        ROWS_DURABLE.write_text(text, encoding="utf-8")
    except OSError:
        return


def _load_pre() -> dict[str, Any]:
    if not PRE_SNAPSHOT.is_file():
        return {}
    try:
        body = json.loads(PRE_SNAPSHOT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(body, dict):
        return {}
    return body


def build_row(bundle: Path, phase: str, seal: str, work: Path) -> dict[str, Any]:
    """Run one phase and return the row that the grader reads."""
    script = extract_webshell_script(bundle, work)
    if script is None:
        return {
            "battery": "webshell",
            "phase": phase,
            "seal": seal,
            "reason": "SEAL_LACKS_WEBSHELL",
            "result": "FAIL",
            "boot_id": _boot_id(),
        }
    if phase == "pre":
        row: dict[str, Any] = {"battery": "webshell", "phase": "pre", "seal": seal}
        absorb_pe(row, run_sealed_script(script, None), None)
        absorb_pe(row, run_sealed_script(script, "pre"), "pre")
        reboot = row.get("reboot")
        if not isinstance(reboot, dict):
            reboot = {}
        reboot.setdefault("boot_id_before", _boot_id())
        row["reboot"] = reboot
        row["boot_id"] = reboot.get("boot_id_before") or _boot_id()
        try:
            PRE_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
            PRE_SNAPSHOT.write_text(json.dumps(row) + "\n", encoding="utf-8")
        except OSError:
            row["pe_rows_unreadable"] = True
        return row
    row = _load_pre()
    row["battery"] = "webshell"
    row["phase"] = "post"
    row["seal"] = seal
    absorb_pe(row, run_sealed_script(script, "post"), "post")
    reboot = row.get("reboot")
    if not isinstance(reboot, dict):
        reboot = {}
    reboot["boot_id_after"] = _boot_id() or reboot.get("boot_id_after") or ""
    row["reboot"] = reboot
    row["boot_id"] = reboot.get("boot_id_after") or ""
    graded = webshell_grade.grade_webshell(row)
    row["result"] = graded["result"]
    if graded["result"] != "PASS":
        row["reason"] = graded["reason"]
    else:
        row["reason"] = "pass"
    return row


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print("usage: webshell_guest.py BUNDLE_DIR pre|post SEAL", file=sys.stderr)
        return 2
    bundle_dir = Path(argv[1])
    phase = argv[2]
    seal = argv[3]
    if phase not in {"pre", "post"}:
        print("phase", file=sys.stderr)
        return 2
    bundle = bundle_dir / "seal.oci.tar"
    if not bundle.is_file():
        row = {
            "battery": "webshell",
            "phase": phase,
            "seal": seal,
            "reason": "SEAL_LACKS_WEBSHELL",
            "result": "FAIL",
            "boot_id": _boot_id(),
        }
        _write_rows(row)
        print(json.dumps(row))
        return 2
    work = bundle_dir / "webshell-pe"
    row = build_row(bundle, phase, seal, work)
    _write_rows(row)
    print(json.dumps({"battery": "webshell", "phase": phase, "reason": row.get("reason"), "result": row.get("result")}))
    if row.get("reason") == "SEAL_LACKS_WEBSHELL":
        return 2
    if phase == "post" and row.get("result") != "PASS":
        return 1
    if row.get("pe_rows_unreadable") is True:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
