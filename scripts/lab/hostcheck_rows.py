#!/usr/bin/env python3
"""Read-only E4 / E5 (d) host checks, run by the lab harness (H2).

DRAFT for review. This is the harness form of Block A in the E4/E5 (d)
host-check draft (DRAFT-E4-E5d-READONLY-COMMANDS-v3.md lines 166-232).
Each check is a fixed argv list. There is no shell string and no text typed
by an operator. The only runtime substitution is the PE container name,
which comes from the E4-1 output and must match NAME_RE.

Rows keep names, yes/no facts, small counts and return codes only. No
command output is copied into a row, with one exception: the Q8 IPv6 error
line, which is copied verbatim only when it matches IPV6_ABSENT_RE.

The guest runs this as root (self_service.py runs under sudo), so the argv
lists carry no sudo. Block A's S0-0 (`echo "$BASH_VERSION"`) is a shell
check for a person and has no harness form.

`python3 hostcheck_rows.py --argv-sha256` prints the sha256 of the fixed
argv artifact and runs nothing else. That sha needs an independent re-hash
(Grace or Leo at P3) before it is used as an integrity reference.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from typing import Callable

PLACEHOLDER = "PE_NAME_FROM_E4_1"
HOSTCHECK_ENV = {
    "LC_ALL": "C",
    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "SYSTEMD_PAGER": "",
    "SYSTEMD_PAGERSECURE": "1",
}
TIMEOUT_SECONDS = 30

# E4-3 is a pipe in Block A (`... | grep -c -E PATTERN`). Here the docker
# output is filtered in memory with this pattern and only the count is kept.
E4_3_COUNT_PATTERN = r"^(VANTIO_CLOUD_INGEST_URL|VANTIO_API_KEY)=.*\S"

HOSTCHECK_ARGV: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("S0-a", ("date",)),
    ("S0-b", ("uname", "-n")),
    ("S0-c", ("uptime", "-s")),
    ("S0-d", ("iptables", "--version")),
    ("S0-e", ("ip6tables", "--version")),
    ("E4-1", ("docker", "ps", "-a", "--no-trunc", "--filter", "name=vantio-pe-", "--format", "{{.Names}} {{.Image}} {{.Status}}")),
    ("E4-2", ("docker", "inspect", "--format", '{{range .Config.Env}}{{index (split . "=") 0}}{{println}}{{end}}', PLACEHOLDER)),
    ("E4-3", ("docker", "inspect", "--format", "{{range .Config.Env}}{{println .}}{{end}}", PLACEHOLDER)),
    ("E5-1", (
        "ls", "-l",
        "/etc/systemd/system/vantio-boot-hold.service",
        "/etc/systemd/system/sysinit.target.wants/vantio-boot-hold.service",
        "/usr/local/bin/vantio-boot-hold",
        "/etc/vantio/boot-hold.json",
    )),
    ("E5-2", ("ls", "-l", "/etc/systemd/system/multi-user.target.wants/")),
    ("E5-3", ("systemctl", "show", "--no-pager", "-p", "LoadState,UnitFileState,ActiveState,SubState,Result", "vantio-boot-hold.service")),
    ("E5-4", ("iptables", "-S", "VANTIO_BOOT_HOLD")),
    ("E5-5", ("iptables", "-S", "OUTPUT")),
    ("E5-6", ("iptables", "-S", "FORWARD")),
    ("E5-7", ("ip6tables", "-S", "VANTIO_BOOT_HOLD")),
    ("E5-8", ("ip6tables", "-S", "OUTPUT")),
    ("E5-9", ("ip6tables", "-S", "FORWARD")),
    ("E5-10", ("cat", "/var/lib/vantio/boot-hold/hold-state.json")),
    ("E5-11", ("cat", "/run/vantio/boot-hold-health.json")),
    ("E5-12", ("cat", "/etc/vantio/boot-hold.json")),
    ("E5-13", ("tail", "-n", "20", "/var/lib/vantio/boot-hold/audit.log")),
)
ROW_IDS = tuple(row for row, _ in HOSTCHECK_ARGV)
# Every reason code a row can carry. The evidence allowlist matches these exactly.
REASONS = frozenset(
    {
        "", "NONZERO_RC", "NOT_A_LAB_HOST_NAME", "IPTABLES_MISSING", "IP6TABLES_MISSING", "E4_1_GATE",
        "NONZERO_RC_OR_SPLIT_REJECT", "NON_NAME_LINE_NOT_COPIED", "E4_2_REQUIRED_NAME_MISSING",
        "E4_3_COUNT_NOT_ZERO", "E5_1_NOT_ALL_PRESENT", "E5_2_NOT_ALL_PRESENT", "E5_3_UNEXPECTED_LINE",
        "E5_3_KEYS_MISSING", "E5_3_NOT_FRESH_OR_FAILED", "IPV4_HOLD_NOT_AS_EXPECTED",
        "IPV6_HOLD_NOT_AS_EXPECTED", "RECORD_AND_CONTINUE", "STOP", "NOT_JSON_OR_NONZERO_RC",
        "E5_10_ALREADY_RELEASED", "E5_11_HOLD_OFF_BY_POLICY", "IPV6_NOT_PRESENT",
    }
    | {f"STOPPED_AT_{row.replace('-', '_')}" for row in ROW_IDS}
)

# Named row outcomes. Leo grades from these; the harness grades nothing.
RECORDED = "RECORDED"
NOT_RUN = "NOT_RUN"
STOP = "STOP"
IPV6_NOT_PRESENT = "IPV6_NOT_PRESENT"
IP6TABLES_MISSING = "IP6TABLES_MISSING"
IPV6_OTHER_ERROR = "IPV6_OTHER_ERROR"
OUTCOMES = frozenset({RECORDED, NOT_RUN, STOP, IPV6_NOT_PRESENT, IP6TABLES_MISSING, IPV6_OTHER_ERROR})

IPV6_NOT_READ_NOTE = "IPv6 half not read; E5 (d) cannot be recorded as active"
E5D_NOT_PASS_IPV6 = "NOT_PASS_IPV6_NOT_PRESENT"
E5D_STOPPED = "STOPPED"
E5D_RECORDED = "RECORDED_FOR_GRADING"
E5D_OUTCOMES = frozenset({E5D_NOT_PASS_IPV6, E5D_STOPPED, E5D_RECORDED})
IPV6_STATES = frozenset({"NOT_READ", "READ", "NOT_PRESENT"})

# Q8: only an address-family or table-initialise error counts as "IPv6 not
# present". The legacy "can't initialize ip6tables table `filter': Table does
# not exist" line matches the second alternative. A bare "table does not
# exist" does not match. Exact ip6tables wording is NOT VERIFIED on a host.
IPV6_ABSENT_RE = re.compile(
    r"(address family not supported|can't initiali[sz]e ip6tables table)",
    re.IGNORECASE,
)
NAME_RE = re.compile(r"^vantio-pe-[A-Za-z0-9]{1,64}$")
ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
WORD_RE = re.compile(r"^[A-Za-z0-9_.-]{0,40}$")
# JSON word values (E5-10/E5-11) are kept only if they are letters joined by
# - or _. Anything with a digit or other character is recorded as has_<key>.
JSON_WORD_RE = re.compile(r"^[A-Za-z]{1,32}(?:[-_][A-Za-z]{1,32}){0,3}$")
KEY_RE = re.compile(r"^[A-Za-z0-9_]{1,40}$")
# E5-10..12: only these JSON key names become facts. They are the keys the
# boot-hold code writes (vantio_install/boot_hold/service.py, policy.py).
# Any other key is only counted (unlisted_key_count); its name is not kept.
JSON_KEYS = {
    "E5-10": ("file_profile", "last_reason", "network_hold", "released"),
    "E5-11": (
        "command", "enrolled_slice", "file_profile", "health", "host_wide_default_route_hold",
        "message", "proof_ceiling", "proof_state", "ready", "reboot_row", "state",
    ),
    "E5-12": ("cgroup_slice", "deny_probe", "enabled", "enrolled_subnet_v4", "enrolled_subnet_v6", "hold", "ordering"),
}
LAB_HOST_RE = re.compile(r"^vantio-gcp-lab-[0-9]{1,20}$")
# S0-b: the guest is told its instance name (VANTIO_LAB_EXPECTED_HOST, set by
# offline_deliver from instance_name). `uname -n` must print exactly that name,
# or that name followed by "." and a DNS domain. Nothing else matches.
EXPECTED_HOST_ENV = "VANTIO_LAB_EXPECTED_HOST"
# F3: the domain is pinned, not guessed. offline_deliver passes the lab project
# and zone it already uses for the instance. The only FQDN forms accepted are
# GCE's internal DNS names built from them:
#   <name>.<zone>.c.<project>.internal   (zonal DNS)
#   <name>.c.<project>.internal          (global DNS)
# Any other suffix STOPs. If project or zone is missing or malformed, only the
# exact short name can match. Which form the image prints is NOT VERIFIED.
EXPECTED_PROJECT_ENV = "VANTIO_LAB_EXPECTED_PROJECT"
EXPECTED_ZONE_ENV = "VANTIO_LAB_EXPECTED_ZONE"
LAB_PROJECT_RE = re.compile(r"^vantio-lab-[a-z][a-z0-9-]{2,18}$")
LAB_ZONE_RE = re.compile(r"^[a-z]{2,12}-[a-z]{2,12}[0-9]{1,2}-[a-z]$")
PRINTABLE_RE = re.compile(r"^[ -~]{1,300}$")

E5_1_PATHS = {
    "unit_present": "/etc/systemd/system/vantio-boot-hold.service",
    "wants_present": "/etc/systemd/system/sysinit.target.wants/vantio-boot-hold.service",
    "wrapper_present": "/usr/local/bin/vantio-boot-hold",
    "policy_present": "/etc/vantio/boot-hold.json",
}
E5_2_UNITS = {
    "loader_unit_present": "vantio-pe-loader.service",
    "enforce_ready_unit_present": "vantio-pe-enforce-ready.service",
    "enrolled_network_unit_present": "vantio-enrolled-network.service",
}
E5_3_KEYS = ("LoadState", "UnitFileState", "ActiveState", "SubState", "Result")
# systemd value sets for E5-3. A value outside these sets is a STOP (rule 6).
E5_3_VALUES = {
    "LoadState": frozenset({"loaded", "not-found", "bad-setting", "error", "masked", "stub", "merged"}),
    "UnitFileState": frozenset({
        "enabled", "enabled-runtime", "linked", "linked-runtime", "alias", "masked", "masked-runtime",
        "static", "disabled", "indirect", "generated", "transient", "bad", "",
    }),
    "ActiveState": frozenset({"active", "reloading", "inactive", "failed", "activating", "deactivating", "maintenance", "refreshing"}),
    "SubState": frozenset({
        "dead", "condition", "start-pre", "start", "start-post", "running", "exited", "reload", "stop",
        "stop-watchdog", "stop-sigterm", "stop-sigkill", "stop-post", "final-watchdog", "final-sigterm",
        "final-sigkill", "failed", "auto-restart", "cleaning",
    }),
    "Result": frozenset({
        "success", "protocol", "timeout", "exit-code", "signal", "core-dump", "watchdog",
        "start-limit-hit", "resources", "oom-kill", "exec-condition", "condition", "",
    }),
}
JSON_WORD_KEYS = frozenset({"command", "file_profile", "health", "last_reason", "state"})

Runner = Callable[[list[str], dict], "tuple[int | None, str, str]"]


def argv_artifact() -> dict:
    """The fixed argv list as one canonical object. This is what is hashed."""
    return {
        "argv": [[row, list(argv)] for row, argv in HOSTCHECK_ARGV],
        "e4_3_count_pattern": E4_3_COUNT_PATTERN,
        "env": dict(sorted(HOSTCHECK_ENV.items())),
        "placeholder": PLACEHOLDER,
        "schema": "vantio.lab.hostcheck-argv/v1",
        "timeout_seconds": TIMEOUT_SECONDS,
    }


def argv_artifact_bytes() -> bytes:
    return json.dumps(argv_artifact(), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def argv_sha256() -> str:
    return hashlib.sha256(argv_artifact_bytes()).hexdigest()


def _argv_for(row: str, pe_name: str | None) -> list[str]:
    argv = list(dict(HOSTCHECK_ARGV)[row])
    if PLACEHOLDER in argv:
        if pe_name is None or NAME_RE.fullmatch(pe_name) is None:
            raise ValueError("pe_name")
        argv = [pe_name if part == PLACEHOLDER else part for part in argv]
    return argv


def run_argv(argv: list[str], env: dict) -> tuple[int | None, str, str]:
    """Run one fixed argv. No shell, no stdin. rc None = not runnable or timed out."""
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            check=False,
            env=env,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, "", ""
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _row(row: str, outcome: str, rc: int | None, facts: dict | None = None, reason: str = "") -> dict:
    return {"facts": facts or {}, "outcome": outcome, "reason": reason, "rc": rc, "row": row}


def _lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip()]


def _ls_names(text: str) -> dict[str, bool]:
    """Map each `ls -l` entry name to whether it is a symlink. Targets are dropped."""
    names: dict[str, bool] = {}
    for line in _lines(text):
        fields = line.split(None, 8)
        if len(fields) != 9 or not fields[0][:1] in {"-", "l", "d"}:
            continue
        names[fields[8].split(" -> ", 1)[0]] = fields[0].startswith("l")
    return names


def _backend(text: str) -> str:
    if "(nf_tables)" in text:
        return "nf_tables"
    if "(legacy)" in text:
        return "legacy"
    return "unknown"


def host_name_facts(expected: object, printed: str, project: object = "", zone: object = "") -> dict:
    """Yes/no facts only. The printed host name is never kept."""
    valid = isinstance(expected, str) and LAB_HOST_RE.fullmatch(expected) is not None
    domain_valid = (
        isinstance(project, str) and LAB_PROJECT_RE.fullmatch(project) is not None
        and isinstance(zone, str) and LAB_ZONE_RE.fullmatch(zone) is not None
    )
    line = printed[:-1] if printed.endswith("\n") else printed
    exact = valid and line == expected
    allowed = {f"{expected}.{zone}.c.{project}.internal", f"{expected}.c.{project}.internal"} if valid and domain_valid else set()
    fqdn = line in allowed
    return {
        "expected_name_valid": valid,
        "expected_domain_valid": domain_valid,
        "host_name_match": exact or fqdn,
        "fqdn_form": fqdn,
    }


def _json_facts(text: str, row: str) -> dict | None:
    try:
        body = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(body, dict):
        return None
    listed = JSON_KEYS[row]
    facts: dict = {
        "key_count": len(body),
        "signature_field_present": any("signature" in str(k).lower() for k in body),
        "unlisted_key_count": sum(1 for k in body if k not in listed),
    }
    for key, value in body.items():
        if key not in listed:
            continue
        if isinstance(value, bool):
            facts[f"bool_{key}"] = value
        elif key in JSON_WORD_KEYS and isinstance(value, str) and JSON_WORD_RE.fullmatch(value):
            facts[f"word_{key}"] = value
        else:
            facts[f"has_{key}"] = True
    return facts


def _chain_facts(row: str, out: str) -> dict:
    lines = _lines(out)
    if row in {"E5-4", "E5-7"}:
        return {
            "chain_present": any(line.strip() == "-N VANTIO_BOOT_HOLD" for line in lines),
            "drop_rule_present": any(line.strip() == "-A VANTIO_BOOT_HOLD -j DROP" for line in lines),
            "rule_lines": len(lines),
        }
    return {"jump_to_boot_hold": any(line.endswith("-j VANTIO_BOOT_HOLD") for line in lines), "rule_lines": len(lines)}


def classify_ipv6(version_rc: int | None, rc: int | None, stderr: str) -> tuple[str, str]:
    """Q8 outcome for an ip6tables read. Returns (outcome, verbatim error or "")."""
    if version_rc != 0:
        return IP6TABLES_MISSING, ""
    if rc == 0:
        return RECORDED, ""
    line = next((item.strip() for item in stderr.splitlines() if IPV6_ABSENT_RE.search(item)), "")
    if rc is not None and line and PRINTABLE_RE.fullmatch(line):
        return IPV6_NOT_PRESENT, line
    return IPV6_OTHER_ERROR, ""


def run_hostcheck(
    runner: Runner = run_argv, expected_host: object = None, project: object = None, zone: object = None
) -> dict:
    """Run the fixed argv list in order with Block A's stop gates.

    A stop means the rows after it are NOT_RUN. It never stops the installer
    phases that follow (rollback, uninstall, verify-removal).
    """
    env = dict(HOSTCHECK_ENV)
    if expected_host is None:
        expected_host = os.environ.get(EXPECTED_HOST_ENV, "")
    if project is None:
        project = os.environ.get(EXPECTED_PROJECT_ENV, "")
    if zone is None:
        zone = os.environ.get(EXPECTED_ZONE_ENV, "")
    rows: list[dict] = []
    stopped_at: str | None = None
    pe_name: str | None = None
    ip6_version_rc: int | None = None
    ipv6_state = "NOT_READ"
    ipv6_error = ""

    def stop(row: str, rc: int | None, facts: dict, reason: str) -> None:
        nonlocal stopped_at
        rows.append(_row(row, STOP, rc, facts, reason))
        stopped_at = row

    for row in ROW_IDS:
        if stopped_at is not None:
            rows.append(_row(row, NOT_RUN, None, reason=f"STOPPED_AT_{stopped_at.replace('-', '_')}"))
            continue
        if row in {"E5-8", "E5-9"} and ipv6_state == "NOT_PRESENT":
            rows.append(_row(row, NOT_RUN, None, reason="IPV6_NOT_PRESENT"))
            continue
        rc, out, err = runner(_argv_for(row, pe_name), env)
        if row in {"S0-a", "S0-c"}:
            if rc != 0:
                stop(row, rc, {}, "NONZERO_RC")
            else:
                rows.append(_row(row, RECORDED, rc))
        elif row == "S0-b":
            facts = host_name_facts(expected_host, out if rc == 0 else "", project, zone)
            if rc != 0:
                stop(row, rc, facts, "NONZERO_RC")
            elif not (facts["expected_name_valid"] and facts["host_name_match"]):
                stop(row, rc, facts, "NOT_A_LAB_HOST_NAME")
            else:
                rows.append(_row(row, RECORDED, rc, facts))
        elif row == "S0-d":
            if rc != 0:
                stop(row, rc, {}, "IPTABLES_MISSING")
            else:
                rows.append(_row(row, RECORDED, rc, {"backend": _backend(out)}))
        elif row == "S0-e":
            ip6_version_rc = rc
            if rc != 0:
                rows.append(_row(row, IP6TABLES_MISSING, rc, {}, "IP6TABLES_MISSING"))
                stopped_at = row
            else:
                rows.append(_row(row, RECORDED, rc, {"backend": _backend(out)}))
        elif row == "E4-1":
            lines = _lines(out)
            parts = lines[0].split(" ", 2) if len(lines) == 1 else []
            up = len(parts) == 3 and parts[2].startswith("Up")
            named = len(parts) == 3 and NAME_RE.fullmatch(parts[0]) is not None
            facts = {"line_count": len(lines), "status_up": up, "name_pattern": named}
            if rc != 0 or len(lines) != 1 or not up or not named:
                stop(row, rc, facts, "E4_1_GATE")
            else:
                pe_name = parts[0]
                rows.append(_row(row, RECORDED, rc, facts))
        elif row == "E4-2":
            names = _lines(out)
            if rc != 0:
                stop(row, rc, {}, "NONZERO_RC_OR_SPLIT_REJECT")
            elif any(ENV_NAME_RE.fullmatch(name.strip()) is None for name in names):
                stop(row, rc, {}, "NON_NAME_LINE_NOT_COPIED")
            else:
                found = {name.strip() for name in names}
                facts = {
                    "name_count": len(found),
                    "telemetry_disabled_name": "VANTIO_TELEMETRY_DISABLED" in found,
                    "do_not_track_name": "DO_NOT_TRACK" in found,
                    "ingest_url_name": "VANTIO_CLOUD_INGEST_URL" in found,
                    "api_key_name": "VANTIO_API_KEY" in found,
                }
                if not (facts["telemetry_disabled_name"] and facts["do_not_track_name"]):
                    stop(row, rc, facts, "E4_2_REQUIRED_NAME_MISSING")
                else:
                    rows.append(_row(row, RECORDED, rc, facts))
        elif row == "E4-3":
            count = len(re.findall(E4_3_COUNT_PATTERN, out, flags=re.MULTILINE)) if rc == 0 else 0
            out = ""  # values are never kept
            if rc != 0:
                stop(row, rc, {}, "NONZERO_RC")
            elif count != 0:
                stop(row, rc, {"checkin_nonempty_count": count}, "E4_3_COUNT_NOT_ZERO")
            else:
                rows.append(_row(row, RECORDED, rc, {"checkin_nonempty_count": 0}))
        elif row == "E5-1":
            listed = _ls_names(out)
            facts = {key: path in listed for key, path in E5_1_PATHS.items()}
            facts["wants_is_symlink"] = listed.get(E5_1_PATHS["wants_present"], False)
            if rc != 0 or not all(facts[key] for key in E5_1_PATHS):
                stop(row, rc, facts, "E5_1_NOT_ALL_PRESENT")
            else:
                rows.append(_row(row, RECORDED, rc, facts))
        elif row == "E5-2":
            listed = _ls_names(out)
            facts = {key: unit in listed for key, unit in E5_2_UNITS.items()}
            if rc != 0 or not all(facts.values()):
                stop(row, rc, facts, "E5_2_NOT_ALL_PRESENT")
            else:
                rows.append(_row(row, RECORDED, rc, facts))
        elif row == "E5-3":
            facts = {}
            bad = False
            for line in _lines(out):
                key, _, value = line.partition("=")
                if key in E5_3_KEYS and value in E5_3_VALUES[key] and key not in facts:
                    facts[key] = value
                else:
                    bad = True
            if rc != 0 or bad:
                stop(row, rc, {}, "E5_3_UNEXPECTED_LINE")
            elif set(facts) != set(E5_3_KEYS):
                stop(row, rc, {}, "E5_3_KEYS_MISSING")
            elif facts.get("ActiveState") in {"active", "failed"} or facts.get("Result") not in {None, "success"}:
                stop(row, rc, facts, "E5_3_NOT_FRESH_OR_FAILED")
            else:
                rows.append(_row(row, RECORDED, rc, facts))
        elif row in {"E5-4", "E5-5", "E5-6"}:
            facts = _chain_facts(row, out) if rc == 0 else {}
            want = facts.get("drop_rule_present") if row == "E5-4" else facts.get("jump_to_boot_hold")
            if rc != 0 or not want:
                stop(row, rc, facts, "IPV4_HOLD_NOT_AS_EXPECTED")
            else:
                rows.append(_row(row, RECORDED, rc, facts))
        elif row in {"E5-7", "E5-8", "E5-9"}:
            outcome, line = classify_ipv6(ip6_version_rc, rc, err)
            if outcome == RECORDED:
                facts = _chain_facts(row, out)
                want = facts.get("drop_rule_present") if row == "E5-7" else facts.get("jump_to_boot_hold")
                if not want:
                    stop(row, rc, facts, "IPV6_HOLD_NOT_AS_EXPECTED")
                else:
                    ipv6_state = "READ"
                    rows.append(_row(row, RECORDED, rc, facts))
            elif outcome == IPV6_NOT_PRESENT and row == "E5-7":
                ipv6_state = "NOT_PRESENT"
                ipv6_error = line
                rows.append(_row(row, IPV6_NOT_PRESENT, rc, {"ipv6_error_verbatim": line}, "RECORD_AND_CONTINUE"))
            else:
                rows.append(_row(row, outcome if outcome != IPV6_NOT_PRESENT else IPV6_OTHER_ERROR, rc, {}, "STOP"))
                stopped_at = row
        elif row in {"E5-10", "E5-11", "E5-12"}:
            facts = _json_facts(out, row) if rc == 0 else None
            if facts is None:
                stop(row, rc, {}, "NOT_JSON_OR_NONZERO_RC")
            elif row == "E5-10" and facts.get("bool_released") is True:
                stop(row, rc, facts, "E5_10_ALREADY_RELEASED")
            elif row == "E5-11" and facts.get("word_state") in {"OPTED_OUT", "HOLD_OFF"}:
                stop(row, rc, facts, "E5_11_HOLD_OFF_BY_POLICY")
            else:
                rows.append(_row(row, RECORDED, rc, facts))
        elif row == "E5-13":
            lines = _lines(out)
            facts = {
                "line_count": len(lines),
                "apply_boot_held_seen": any("apply-boot" in line and "HELD" in line for line in lines),
                "apply_boot_failed_seen": any("apply-boot" in line and "FAILED" in line for line in lines),
            }
            if rc != 0:
                stop(row, rc, facts, "NONZERO_RC")
            else:
                rows.append(_row(row, RECORDED, rc, facts))
    # A stop takes precedence over "IPv6 not present" (N6).
    if stopped_at is not None:
        e5d = E5D_STOPPED
    elif ipv6_state == "NOT_PRESENT":
        e5d = E5D_NOT_PASS_IPV6
    else:
        e5d = E5D_RECORDED
    summary = {
        "argv_sha256": argv_sha256(),
        "e5d_outcome": e5d,
        "ipv6": ipv6_state,
        "stopped_at": stopped_at or "",
    }
    if ipv6_state == "NOT_PRESENT":
        summary["e5d_note"] = IPV6_NOT_READ_NOTE
        summary["ipv6_error_verbatim"] = ipv6_error
    return {"rows": rows, "summary": summary}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--argv-sha256"]:
        print(argv_sha256())
        return 0
    if args == ["--argv-json"]:
        print(argv_artifact_bytes().decode("ascii"))
        return 0
    raise SystemExit("usage: hostcheck_rows.py --argv-sha256 | --argv-json")


if __name__ == "__main__":
    raise SystemExit(main())
