"""Grade webshell lab rows. No AWS, no loader, no sealed bundle.

A PASS requires an enrolled php-fpm lineage and an enrolled nginx lineage
to get EACCES under enforce for sh, bash, python3, and curl; a denied
web-shell file write; the same deny after the loader is killed with signal
9 on that boot; and a restarted loader that denies again after reboot.
Any other shape fails with one named reason. lab_pass is not this result.
"""

from __future__ import annotations

from typing import Any, Mapping

EACCES = 13
LINEAGES = ("php-fpm", "nginx")
SHELLS = frozenset({"sh", "bash"})
INTERPRETERS = frozenset({"python3"})
NETWORK_TOOLS = frozenset({"curl"})
ENFORCE_MODES = frozenset({"enforce", "--enforce"})
REQUIRED_TOOLS = ("sh", "bash", "python3", "curl")


def grade_webshell(row: Mapping[str, Any] | None) -> dict[str, str]:
    """Return result PASS or FAIL and one reason token."""
    reason = _reason(row)
    if reason is None:
        return {"result": "PASS", "reason": "pass"}
    return {"result": "FAIL", "reason": reason}


def _reason(row: Mapping[str, Any] | None) -> str | None:
    if not isinstance(row, Mapping):
        return "pe_rows_unreadable"
    named = row.get("reason")
    if named == "SEAL_LACKS_WEBSHELL":
        return "SEAL_LACKS_WEBSHELL"
    if row.get("pe_rows_unreadable") is True:
        return "pe_rows_unreadable"
    exec_reason = _exec_reason(row.get("exec"), "exec")
    if exec_reason is not None:
        return exec_reason
    file_reason = _file_reason(row.get("file_write"))
    if file_reason is not None:
        return file_reason
    child_reason = _child_reason(row.get("child_evasion"))
    if child_reason is not None:
        return child_reason
    kill_reason = _kill_reason(row.get("loader_kill"))
    if kill_reason is not None:
        return kill_reason
    return _reboot_reason(row.get("reboot"))


def _lineage(value: object) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip().lower()
    if "php-fpm" in text:
        return "php-fpm"
    if text == "nginx" or text.startswith("nginx"):
        return "nginx"
    return ""


def _basename(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().replace("\\", "/").rsplit("/", 1)[-1]


def _checks(value: object) -> list[Mapping[str, Any]] | None:
    if isinstance(value, list):
        rows = value
    elif isinstance(value, Mapping) and isinstance(value.get("checks"), list):
        rows = value["checks"]
    else:
        return None
    if not all(isinstance(item, Mapping) for item in rows):
        return None
    return rows


def _enrolled_enforce(check: Mapping[str, Any]) -> bool:
    if check.get("enrolled") is not True:
        return False
    mode = check.get("mode")
    return isinstance(mode, str) and mode.strip().lower() in ENFORCE_MODES


def _exec_reason(value: object, kind: str) -> str | None:
    checks = _checks(value)
    if checks is None:
        return "exec_missing" if kind == "exec" else "child_evasion_missing"
    seen: dict[str, set[str]] = {lineage: set() for lineage in LINEAGES}
    for check in checks:
        lineage = _lineage(check.get("lineage"))
        tool = _basename(check.get("binary"))
        if not lineage or tool not in {*SHELLS, *INTERPRETERS, *NETWORK_TOOLS}:
            continue
        if not _enrolled_enforce(check):
            if check.get("enrolled") is True and tool in REQUIRED_TOOLS:
                return "exec_not_enforce" if kind == "exec" else "child_evasion_allowed"
            continue
        errno = check.get("errno")
        if errno != EACCES:
            return "exec_not_eacces" if kind == "exec" else "child_evasion_allowed"
        seen[lineage].add(tool)
    if kind == "exec":
        for lineage in LINEAGES:
            if any(tool not in seen[lineage] for tool in REQUIRED_TOOLS):
                return "lineage_missing" if not seen[lineage] else "exec_missing"
    return None


def _child_reason(value: object) -> str | None:
    checks = _checks(value)
    if checks is None or not checks:
        return "child_evasion_missing"
    return _exec_reason(checks, "child")


def _file_reason(value: object) -> str | None:
    if not isinstance(value, Mapping):
        return "file_write_allowed"
    if _lineage(value.get("lineage")) not in LINEAGES:
        return "file_write_allowed"
    if value.get("enrolled") is not True or value.get("denied") is not True or value.get("errno") != EACCES:
        return "file_write_allowed"
    return None


def _kill_reason(value: object) -> str | None:
    if not isinstance(value, Mapping):
        return "kill_not_persistent"
    signal = value.get("signal")
    killed = value.get("killed") is True or signal == 9
    if not killed:
        return "kill_not_persistent"
    if value.get("same_boot") is not True:
        return "kill_other_boot"
    if value.get("eacces_remains") is not True:
        return "kill_not_persistent"
    return None


def _reboot_reason(value: object) -> str | None:
    if not isinstance(value, Mapping):
        return "reboot_boot_unchanged"
    before = value.get("boot_id_before")
    after = value.get("boot_id_after")
    if not isinstance(before, str) or not isinstance(after, str) or not before or not after or before == after:
        return "reboot_boot_unchanged"
    if value.get("loader_restarted") is not True:
        return "loader_not_restarted"
    if value.get("denied_again") is not True:
        return "reboot_not_denied"
    return None
