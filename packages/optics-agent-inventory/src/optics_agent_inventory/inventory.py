"""Group a proc snapshot into workloads and a fail-closed host coverage state."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from optics_agent_inventory.catalog import (
    AGENT_BINARIES,
    INTERACTIVE_BINARIES,
    MODEL_BINARIES,
    PROVIDERS,
    SIDECAR_ROLES,
    basename_matches,
    is_mcp_basename,
    is_mcp_server_name,
)
from optics_agent_inventory.coverage import COVERED, PARTIAL, UNENROLLED, UNKNOWN, coverage_name, host_coverage
from optics_agent_inventory.endpoints import EndpointMap, Observed, load_endpoint_map, resolve_socket
from optics_agent_inventory.enrollment import Enrollment, load_enrollment
from optics_agent_inventory.procfs import ProcessRecord, Snapshot, load_extra, read_snapshot
from optics_agent_inventory.runs import annotate_runs

SCHEMA = "vantio.optics.agent_inventory.v1"
RECOGNITION_LIMIT = "catalog_process_endpoint_mcp_container"
SCOPE_NOTE = "procfs_view_only"


@dataclass
class ScanConfig:
    proc_root: Path
    host_id: str
    euid: int
    enrollment_path: Path | None = None
    endpoint_map_path: Path | None = None
    mountinfo_path: Path | None = None
    runs_dir: Path | None = None
    extra_hosts: tuple[str, ...] = ()
    now: datetime | None = None


@dataclass
class _Member:
    proc: ProcessRecord
    role: str | None
    strong: bool
    reach: list[Observed] = field(default_factory=list)


def scan(config: ScanConfig) -> tuple[dict, int]:
    extra = config.extra_hosts or load_extra()
    endpoint_map = _load_map(config, extra)
    snapshot = read_snapshot(config.proc_root, config.mountinfo_path, config.euid, extra)
    enrollment = load_enrollment(config.enrollment_path)
    host_matches = bool(enrollment.status == "ok" and enrollment.host_id == config.host_id)
    members = _classify(snapshot, endpoint_map, extra)
    workloads = _workloads(members, enrollment, host_matches, config.host_id)
    notes, runs_bad = annotate_runs(config.runs_dir, snapshot.processes, snapshot.scanner_nspid_count, extra)
    _apply_notes(workloads, notes)
    reasons = _host_reasons(snapshot, enrollment, host_matches, workloads, runs_bad, endpoint_map)
    if not workloads and host_coverage(reasons) == COVERED:
        reasons.append("no_ai_workloads_observed")
    observed = config.now or datetime.now(timezone.utc)
    report = {
        "schema": SCHEMA,
        "schema_status": "unstable-pre-1.0",
        "label": "lab-only",
        "content_stored": False,
        "observed_at": observed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "recognition_limit": RECOGNITION_LIMIT,
        "host": {
            "host_id": config.host_id,
            "coverage": host_coverage(reasons),
            "reasons": _unique(reasons),
            "proc_view": "restricted" if snapshot.proc_restricted else "listed",
            "scope_note": SCOPE_NOTE,
        },
        "workloads": workloads,
    }
    code = 3 if snapshot.proc_unreadable else 0
    return report, code


def _load_map(config: ScanConfig, extra: tuple[str, ...]) -> EndpointMap:
    if config.endpoint_map_path is None:
        return EndpointMap({}, None)
    return load_endpoint_map(config.endpoint_map_path, extra)


def _classify(snapshot: Snapshot, endpoint_map: EndpointMap, extra: tuple[str, ...]) -> dict[int, _Member]:
    found: dict[int, _Member] = {}
    for proc in snapshot.processes.values():
        reach = _reach_for(proc, endpoint_map, extra)
        role, strong = _role(proc, reach)
        if role is None:
            found[proc.pid] = _Member(proc, None, False, reach)
            continue
        found[proc.pid] = _Member(proc, role, strong, reach)
    return found


def _reach_for(proc: ProcessRecord, endpoint_map: EndpointMap, extra: tuple[str, ...]) -> list[Observed]:
    reach = list(proc.argv_observed)
    if proc.endpoints_missing:
        return _dedupe(reach)
    for state, ip, port in proc.socket_rows:
        observed = resolve_socket(ip, port, state, proc.hosts_names, endpoint_map, extra)
        if observed is not None:
            reach.append(observed)
    return _dedupe(reach)


def _role(proc: ProcessRecord, reach: list[Observed]) -> tuple[str | None, bool]:
    if proc.is_kernel or proc.status_unreadable or proc.raced:
        return None, False
    names = (proc.comm, proc.exe_basename)
    if proc.listens_11434 or any(basename_matches(name, MODEL_BINARIES) for name in names):
        return "local_model_server", True
    if any(is_mcp_basename(name) for name in names):
        return "mcp_server", True
    if any(basename_matches(name, AGENT_BINARIES) for name in names):
        return "agent_runtime", True
    interactive = any(basename_matches(name, INTERACTIVE_BINARIES) for name in names)
    if reach and interactive:
        return "api_client", False
    if reach:
        return "api_client", True
    if proc.credentials:
        return "credential_only", False
    return None, False


def _workloads(members: dict[int, _Member], enrollment: Enrollment, host_matches: bool, host_id: str) -> list[dict]:
    roles = {pid: member.role for pid, member in members.items() if member.role}
    children: dict[int, list[ProcessRecord]] = {}
    for member in members.values():
        children.setdefault(member.proc.ppid, []).append(member.proc)
    roots: dict[int, list[_Member]] = {}
    for pid, role in roles.items():
        root = _root(members[pid].proc, role, members)
        roots.setdefault(root.pid, []).append(members[pid])
    grouped: dict[tuple[str, str, str, str], dict] = {}
    for root_pid, seeds in roots.items():
        root_proc = members[root_pid].proc
        role = members[root_pid].role or seeds[0].role or ""
        strong = members[root_pid].strong
        group = _members_of(root_proc, members, children)
        container_id = root_proc.container_id or ""
        key = (container_id, role, root_proc.comm, root_proc.exe_basename or "")
        bucket = grouped.get(key)
        if bucket is None:
            bucket = {
                "role": role,
                "strong": strong,
                "root": root_proc,
                "members": [],
            }
            grouped[key] = bucket
        bucket["strong"] = bucket["strong"] and strong
        bucket["members"].extend(group)
    rendered: list[dict] = []
    for bucket in grouped.values():
        rendered.append(_render_workload(bucket, enrollment, host_matches, host_id, members))
    rendered.sort(key=lambda row: (row["where"]["container_id"] or "", row["role"], row["workload_id"]))
    return rendered


def _root(proc: ProcessRecord, role: str, members: dict[int, _Member]) -> ProcessRecord:
    if role in SIDECAR_ROLES:
        return proc
    chosen = proc
    seen: set[int] = set()
    current = proc
    while current.ppid and current.ppid not in seen and len(seen) < 64:
        seen.add(current.pid)
        parent = members.get(current.ppid)
        if parent is None or _key(parent.proc) != _key(proc):
            break
        if parent.role in SIDECAR_ROLES:
            break
        if parent.role:
            chosen = parent.proc
        current = parent.proc
    return chosen


def _members_of(root: ProcessRecord, members: dict[int, _Member], children: dict[int, list[ProcessRecord]]) -> list[_Member]:
    found: list[_Member] = []
    stack = [root]
    seen: set[int] = set()
    while stack:
        proc = stack.pop()
        if proc.pid in seen:
            continue
        seen.add(proc.pid)
        member = members.get(proc.pid)
        if member is None:
            continue
        found.append(member)
        for child in children.get(proc.pid, []):
            if _key(child) != _key(root):
                continue
            child_member = members.get(child.pid)
            if child_member and (child_member.proc.is_kernel or child_member.role in SIDECAR_ROLES):
                continue
            stack.append(child)
    return found


def _render_workload(bucket: dict, enrollment: Enrollment, host_matches: bool, host_id: str, members: dict[int, _Member]) -> dict:
    root: ProcessRecord = bucket["root"]
    role = bucket["role"]
    group: list[_Member] = bucket["members"]
    seen_pids: set[int] = set()
    ordered: list[_Member] = []
    for member in group:
        if member.proc.pid in seen_pids:
            continue
        seen_pids.add(member.proc.pid)
        ordered.append(member)
    reach: list[Observed] = []
    credentials = False
    binary_missing = False
    endpoints_missing = False
    mcp_blocked = False
    mcp_rows: list[dict[str, object]] = []
    relevant_mcp = False
    for member in ordered:
        reach.extend(member.reach)
        credentials = credentials or bool(member.proc.credentials)
        if member.role and member.proc.binary_missing:
            binary_missing = True
        if member.proc.endpoints_missing:
            endpoints_missing = True
        if member.role in {"agent_runtime", "mcp_server"} or is_mcp_basename(member.proc.comm) or is_mcp_basename(member.proc.exe_basename):
            relevant_mcp = True
            if member.proc.mcp_blocked:
                mcp_blocked = True
        mcp_rows.extend(member.proc.mcp_rows)
    if role == "mcp_server":
        mcp_rows.append(_process_mcp(root))
        relevant_mcp = True
    lineage, lineage_missing = _lineage(root, {pid: member.proc for pid, member in members.items()})
    mcp_signal = "missing" if relevant_mcp and mcp_blocked else ("present" if mcp_rows else "absent")
    missing = binary_missing or endpoints_missing or lineage_missing or mcp_signal == "missing"
    enrolled = _enrolled(root, enrollment, host_matches)
    if enrolled == "unknown":
        state = UNKNOWN
    elif enrolled == "unenrolled":
        state = UNENROLLED
    elif not bucket["strong"]:
        state = UNKNOWN
    elif missing:
        state = PARTIAL
    else:
        state = COVERED
    workload_id = hashlib.sha256(
        f"{root.container_id or ''}|{role}|{root.comm}|{root.exe_basename or ''}".encode()
    ).hexdigest()[:16]
    return {
        "workload_id": workload_id,
        "role": role,
        "coverage": coverage_name(state),
        "reasons": _workload_reasons(enrolled, bucket["strong"], missing),
        "where": {
            "host_id": host_id,
            "container_id": root.container_id,
            "container_name": root.hostname_label,
            "pids": sorted(seen_pids),
            "lineage": lineage,
        },
        "observed_reach": [_reach_dict(item) for item in _dedupe(reach)],
        "can_do": _can_do(role, _dedupe(reach), credentials),
        "signals": {
            "lineage": "missing" if lineage_missing else "present",
            "binary": "missing" if binary_missing else "present",
            "endpoints": "missing" if endpoints_missing else "present",
            "mcp": mcp_signal,
            "container": root.container_signal,
        },
        "mcp_servers": mcp_rows,
    }


def _process_mcp(root: ProcessRecord) -> dict[str, object]:
    name = root.comm if is_mcp_server_name(root.comm) else "mcp-server"
    command = root.exe_basename or root.comm
    return {"name": name, "command_basename": command, "args": [], "basis": "process"}


def _lineage(root: ProcessRecord, procs: dict[int, ProcessRecord]) -> tuple[list[dict], bool]:
    hops: list[dict] = []
    current: ProcessRecord | None = root
    seen: set[int] = set()
    while current is not None and len(hops) < 64:
        if current.pid in seen:
            break
        seen.add(current.pid)
        hops.append(
            {
                "pid": current.pid,
                "ppid": current.ppid,
                "comm": current.comm,
                "exe_basename": current.exe_basename,
            }
        )
        parent = procs.get(current.ppid)
        if parent is None or _key(parent) != _key(root):
            return hops, False
        if parent.status_unreadable:
            return hops, True
        current = parent
    return hops, True


def _enrolled(proc: ProcessRecord, enrollment: Enrollment, host_matches: bool) -> str:
    if enrollment.status != "ok":
        return "unknown"
    if not host_matches:
        return "unenrolled"
    if proc.container_signal == "present" and proc.container_id in enrollment.containers:
        return "enrolled"
    if proc.container_signal == "host_process" and enrollment.host_processes:
        return "enrolled"
    return "unenrolled"


def _workload_reasons(enrolled: str, strong: bool, missing: bool) -> list[str]:
    if enrolled == "unknown":
        return ["enrollment_unknown"]
    if enrolled == "unenrolled":
        return ["not_enrolled"]
    if not strong:
        return ["weak_identity"]
    if missing:
        return ["signal_missing"]
    return []


def _can_do(role: str, reach: list[Observed], credentials: bool) -> list[str]:
    items: list[str] = []
    if role == "agent_runtime":
        items.append("agent_runtime")
    if role == "local_model_server":
        items.append("serve_local_model")
    if role == "mcp_server":
        items.append("serve_mcp")
    calls = [item for item in reach if not (role == "local_model_server" and item.source == "socket" and item.port == 11434)]
    if calls:
        items.append("call_model_api")
    if credentials:
        items.append("hold_provider_credential_name")
    providers = []
    for item in reach:
        if item.provider in PROVIDERS and item.provider not in {"unknown"} and item.provider not in providers:
            providers.append(item.provider)
    items.extend(f"reach:{provider}" for provider in providers)
    return items


def _reach_dict(item: Observed) -> dict:
    return {"host": item.host, "port": item.port, "provider": item.provider, "source": item.source}


def _apply_notes(workloads: list[dict], notes: dict[int, list[Observed]]) -> None:
    for workload in workloads:
        extra: list[Observed] = []
        for pid in workload["where"]["pids"]:
            extra.extend(notes.get(pid, []))
        if not extra:
            continue
        merged = [Observed(item["host"], item["port"], item["provider"], item["source"]) for item in workload["observed_reach"]]
        merged.extend(extra)
        workload["observed_reach"] = [_reach_dict(item) for item in _dedupe(merged)]
        workload["can_do"] = _can_do(workload["role"], _dedupe(merged), "hold_provider_credential_name" in workload["can_do"])


def _host_reasons(snapshot: Snapshot, enrollment: Enrollment, host_matches: bool, workloads: list[dict], runs_bad: bool, endpoint_map: EndpointMap) -> list[str]:
    reasons: list[str] = []
    if snapshot.proc_unreadable:
        reasons.append("proc_unreadable")
    if snapshot.scan_cap:
        reasons.append("scan_cap")
    if snapshot.proc_restricted:
        reasons.append("proc_restricted")
    if enrollment.status != "ok" and enrollment.reason:
        reasons.append(enrollment.reason)
    if enrollment.status == "ok" and not host_matches:
        reasons.append("host_id_mismatch")
    if any(proc.status_unreadable for proc in snapshot.processes.values()):
        reasons.append("unreadable_identity")
    if any(row["coverage"] == UNKNOWN and _row_enrolled(row) for row in workloads):
        reasons.append("enrolled_workload_unknown")
    if any(row["coverage"] == PARTIAL and _row_enrolled(row) for row in workloads):
        reasons.append("enrolled_workload_partial")
    if runs_bad:
        reasons.append("runs_unreadable")
    if endpoint_map.reason:
        reasons.append(endpoint_map.reason)
    if _scope_unreadable(snapshot, enrollment, host_matches):
        reasons.append("enrolled_scope_unreadable")
    return reasons


def _row_enrolled(row: dict) -> bool:
    return "not_enrolled" not in row["reasons"] and "enrollment_unknown" not in row["reasons"]


def _scope_unreadable(snapshot: Snapshot, enrollment: Enrollment, host_matches: bool) -> bool:
    if enrollment.status != "ok" or not host_matches:
        return False
    for proc in snapshot.processes.values():
        if proc.is_kernel or proc.raced:
            continue
        in_scope = False
        if proc.container_signal == "present" and proc.container_id in enrollment.containers:
            in_scope = True
        if proc.container_signal == "host_process" and enrollment.host_processes:
            in_scope = True
        if in_scope and (proc.fd_unreadable or proc.environ_unreadable):
            return True
    return False


def _key(proc: ProcessRecord) -> str:
    if proc.container_signal == "present" and proc.container_id:
        return proc.container_id
    if proc.container_signal == "host_process":
        return "host"
    return f"missing:{proc.cgroup_text or proc.pid}"


def _dedupe(items: list[Observed]) -> list[Observed]:
    seen: set[tuple[str, int | None, str, str]] = set()
    kept: list[Observed] = []
    for item in items:
        key = (item.host, item.port, item.provider, item.source)
        if key in seen:
            continue
        seen.add(key)
        kept.append(item)
    return kept


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    kept: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        kept.append(item)
    return kept
