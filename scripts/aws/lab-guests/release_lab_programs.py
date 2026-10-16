#!/usr/bin/env python3
"""Detach lab BPF programs a previous battery left loaded.

guest_rows.py treats these names as still installed when `bpftool prog show`
lists them. That census runs before the shell's loader uninstall. A cgroup
attachment from an earlier battery survives `docker rm`, and the loader's
UNINSTALL_VERIFIED line only checks pins named vantio*. This command detaches
the lab programs and exits 1 while any of them is still loaded.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

LAB_PROGRAMS = (
    "cgroup_skb_egress_enforce",
    "kprobe_open_deny",
    "inherit_trace_on_fork",
    "tc_enforce",
)

DETACH_TYPES = {
    "egress": "egress",
    "cgroup_inet_egress": "egress",
    "ingress": "ingress",
    "cgroup_inet_ingress": "ingress",
}


def is_lab_program(name: object) -> str:
    """Canonical lab name, or empty when this bpftool name is not one of ours."""
    if not isinstance(name, str) or not name:
        return ""
    for lab_name in LAB_PROGRAMS:
        if name == lab_name:
            return lab_name
        # The kernel stores 15 characters. bpftool prints that truncation.
        if len(lab_name) > 15 and name == lab_name[:15]:
            return lab_name
    return ""


def names_in_prog_show(payload: object, raw: str) -> list[str]:
    """Lab programs still listed. JSON names win. The raw text is the fallback."""
    found: list[str] = []
    if isinstance(payload, list):
        seen: set[str] = set()
        for item in payload:
            if not isinstance(item, dict):
                continue
            lab_name = is_lab_program(item.get("name"))
            if lab_name:
                seen.add(lab_name)
        found = [name for name in LAB_PROGRAMS if name in seen]
    if found:
        return found
    return [name for name in LAB_PROGRAMS if name in raw]


def _cgroup_path(value: object) -> str:
    if not isinstance(value, str) or not value.startswith("/sys/fs/cgroup/"):
        return ""
    if ".." in value.split("/"):
        return ""
    return value


def detach_commands(tree: object) -> list[list[str]]:
    """bpftool cgroup detach argv for lab programs only."""
    commands: list[list[str]] = []
    if not isinstance(tree, list):
        return commands
    for item in tree:
        if not isinstance(item, dict):
            continue
        nested = item.get("programs")
        rows = nested if isinstance(nested, list) else [item]
        cgroup = _cgroup_path(item.get("cgroup") or item.get("path"))
        for row in rows:
            if not isinstance(row, dict):
                continue
            row_cgroup = _cgroup_path(row.get("cgroup") or row.get("path")) or cgroup
            if not row_cgroup or not is_lab_program(row.get("name")):
                continue
            kind = DETACH_TYPES.get(str(row.get("attach_type") or ""))
            ident = row.get("id")
            if not kind or isinstance(ident, bool) or not isinstance(ident, int) or ident <= 0:
                continue
            commands.append(
                ["bpftool", "cgroup", "detach", row_cgroup, kind, "id", str(ident)]
            )
    return commands


def pin_paths(prog_show: object) -> list[str]:
    """Pin files under bpffs for lab programs. Other paths stay."""
    paths: list[str] = []
    if not isinstance(prog_show, list):
        return paths
    root = Path("/sys/fs/bpf")
    for item in prog_show:
        if not isinstance(item, dict) or not is_lab_program(item.get("name")):
            continue
        pinned = item.get("pinned")
        if isinstance(pinned, str):
            pinned = [pinned]
        if not isinstance(pinned, list):
            continue
        for raw in pinned:
            if not isinstance(raw, str) or not raw.startswith("/sys/fs/bpf/"):
                continue
            if ".." in raw.split("/"):
                continue
            try:
                resolved = Path(raw).resolve()
            except OSError:
                continue
            if root not in resolved.parents and resolved != root:
                continue
            paths.append(str(resolved))
    return paths


def removal_census(prog_text: str, containers: str, bpftool_rc: int) -> dict[str, object]:
    names = [name for name in LAB_PROGRAMS if name in prog_text]
    docker = containers.strip()
    return {
        "loader_programs": names,
        "docker_containers": docker,
        "bpftool_rc": bpftool_rc,
        "verified_removed": bpftool_rc == 0 and names == [] and docker == "",
    }


def regression_still_holds(rows: dict) -> bool:
    """True when the Enterprise checks other than removal still hold.

    A missing field stays false. This does not invent a pass for a battery
    that failed grant, revoke, freeze, or the unchanged cases.
    """
    try:
        grant = rows["grant_loader"]
        if not isinstance(grant, dict):
            return False
        if (
            grant.get("rc") != 0
            or grant.get("audit") is not True
            or grant.get("scoped") is not False
            or grant.get("path_deny") is not False
            or grant.get("path_observe") is not True
            or grant.get("phantom_deny") is not False
        ):
            return False
        if rows["grant_probe"].get("nobody_errno") != 0:
            return False
        allow = rows.get("grant_allow_event")
        if not isinstance(allow, dict) or allow.get("ActionTaken") != "POLICY_ALLOW":
            return False
        if allow.get("Uid") != 65534:
            return False
        unchanged = rows["unchanged"]
        if (
            unchanged.get("unsigned_changed") is not False
            or unchanged.get("replay_changed") is not False
            or unchanged.get("conflict_changed") is not False
            or unchanged.get("conflict_reason") != "VERSION_CONFLICT"
            or unchanged.get("generation") != unchanged.get("generation_before")
        ):
            return False
        if rows["unchanged_probe"].get("nobody_errno") != 0:
            return False
        freeze = rows["freeze"]
        if freeze.get("widen_changed") is not False or freeze.get("widen_reason") != "FROZEN":
            return False
        unreachable = rows["unreachable"]
        if unreachable.get("changed") is not False or unreachable.get("reason") != "ENTERPRISE_UNREACHABLE":
            return False
        revoke = rows["revoke"]
        probe = revoke.get("probe")
        if not isinstance(probe, dict) or probe.get("nobody_errno") != 13:
            return False
        block = revoke.get("block_event")
        if not isinstance(block, dict) or block.get("ActionTaken") != "DENIED":
            return False
    except (AttributeError, TypeError):
        return False
    return True


def finish_code(*, verified_removed: bool, guest_rc: int, rows: dict) -> int:
    """0 when the programs are gone and the regression itself held."""
    if not verified_removed:
        return 1
    if guest_rc == 0:
        return 0
    if regression_still_holds(rows):
        return 0
    return 1


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, check=False, capture_output=True, text=True, timeout=30)


def _json_stdout(proc: subprocess.CompletedProcess[str]) -> object:
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout or "")
    except json.JSONDecodeError:
        return None


def _live_names() -> tuple[list[str], int, str]:
    shown = _run(["bpftool", "prog", "show", "-j"])
    payload = _json_stdout(shown)
    raw = (shown.stdout or "") + (shown.stderr or "")
    if shown.returncode != 0:
        shown = _run(["bpftool", "prog", "show"])
        raw = (shown.stdout or "") + (shown.stderr or "")
        payload = None
    return names_in_prog_show(payload, raw), shown.returncode, raw


def release_loaded() -> tuple[list[str], int, str]:
    """Detach and unpin lab programs. The returned names are what is still loaded."""
    shown = _run(["bpftool", "prog", "show", "-j"])
    payload = _json_stdout(shown)
    for path in pin_paths(payload):
        try:
            Path(path).unlink()
        except OSError as exc:
            print(f"pin unlink {path}: {exc}", file=sys.stderr)
    tree = _json_stdout(_run(["bpftool", "cgroup", "tree", "-j"]))
    for command in detach_commands(tree):
        detached = _run(command)
        if detached.returncode != 0:
            detail = ((detached.stderr or "") + (detached.stdout or "")).strip()
            print(f"{' '.join(command)}: {detail}", file=sys.stderr)
    names, bpftool_rc, raw = _live_names()
    return names, bpftool_rc, raw


def _write_removal(path: Path, census: dict[str, object]) -> dict:
    if not path.is_file():
        raise SystemExit("rows_missing")
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit("rows_malformed") from exc
    if not isinstance(body, dict):
        raise SystemExit("rows_malformed")
    body["removal"] = census
    path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        path.chmod(0o644)
    except OSError:
        pass
    return body


def main(argv: list[str]) -> int:
    record = ""
    guest_rc = 0
    args = argv[1:]
    while args:
        item = args.pop(0)
        if item == "--record":
            if not args:
                print("rows_missing", file=sys.stderr)
                return 1
            record = args.pop(0)
            continue
        if item == "--guest-rc":
            if not args:
                print("guest", file=sys.stderr)
                return 1
            try:
                guest_rc = int(args.pop(0))
            except ValueError:
                print("guest", file=sys.stderr)
                return 1
            continue
        print(f"unknown {item}", file=sys.stderr)
        return 1
    names, bpftool_rc, raw = release_loaded()
    containers = _run(["docker", "ps", "-aq"])
    container_text = containers.stdout or ""
    if containers.returncode != 0:
        container_text = (containers.stdout or "") + (containers.stderr or "")
    census = removal_census(raw, container_text, bpftool_rc)
    census["loader_programs"] = names or census["loader_programs"]
    dirty = bool(census["loader_programs"]) or containers.returncode != 0 or bool((containers.stdout or "").strip()) or bpftool_rc != 0
    census["verified_removed"] = not dirty
    if record:
        body = _write_removal(Path(record), census)
        code = finish_code(
            verified_removed=census["verified_removed"] is True,
            guest_rc=guest_rc,
            rows=body,
        )
        if code != 0 and census["verified_removed"] is not True:
            print("programs_not_removed " + " ".join(census["loader_programs"]), file=sys.stderr)
        elif code != 0:
            print("guest", file=sys.stderr)
        return code
    if census["verified_removed"] is not True:
        print("programs_not_removed " + " ".join(census["loader_programs"]), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
