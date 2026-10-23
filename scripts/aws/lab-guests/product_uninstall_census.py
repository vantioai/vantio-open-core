#!/usr/bin/env python3
"""Read bpftool and bpffs after the product loader uninstall.

This command does not detach programs and does not unlink pins. The product
binary `vantio-loader --uninstall` is the only removal. A program that is
still listed here stays programs_not_removed.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

# Names of programs in the Phantom Engine object. bpftool prints at most 15
# characters, so the census accepts that truncation as the same program.
ENGINE_PROGRAMS = (
    "cgroup_skb_egress_enforce",
    "kprobe_open_deny",
    "inherit_trace_on_fork",
    "tc_enforce",
)

# The kernel frees a detached program after its last reference drops, so
# bpftool can list it for a moment after the uninstall returns. Read again
# until the census is clean or this many seconds pass. The last read is the
# one recorded. Polling only reads; it never detaches or unlinks.
CENSUS_POLL_TIMEOUT_S = 20.0
CENSUS_POLL_INTERVAL_S = 1.0


def engine_name(name: object) -> str:
    if not isinstance(name, str) or not name:
        return ""
    for program in ENGINE_PROGRAMS:
        if name == program:
            return program
        if len(program) > 15 and name == program[:15]:
            return program
    return ""


def loaded_programs(payload: object, raw: str) -> list[str]:
    """Engine programs and any bpftool name or pin that says vantio."""
    found: list[str] = []
    seen: set[str] = set()

    def add(label: str) -> None:
        if label and label not in seen:
            seen.add(label)
            found.append(label)

    items = payload if isinstance(payload, list) else []
    if items:
        for item in items:
            if not isinstance(item, dict):
                continue
            add(engine_name(item.get("name")))
            name = item.get("name")
            if isinstance(name, str) and "vantio" in name.lower():
                add(name)
            pinned = item.get("pinned")
            if isinstance(pinned, str):
                pinned = [pinned]
            if isinstance(pinned, list):
                for path in pinned:
                    if isinstance(path, str) and "vantio" in path.lower():
                        add(path)
        return found
    for name in ENGINE_PROGRAMS:
        if name in raw:
            add(name)
    if "vantio" in raw.lower():
        add("vantio")
    return found


def bpffs_vantio_paths(text: str) -> list[str]:
    paths: list[str] = []
    for line in text.splitlines():
        path = line.strip()
        if path.startswith("/sys/fs/bpf/") and "vantio" in path.lower() and ".." not in path.split("/"):
            paths.append(path)
    return paths


def classify_bpffs(*, mounted: bool, find_rc: int, text: str) -> list[str]:
    """Pins under bpffs. A missing mount has no pins. A failed find is not clean."""
    if not mounted:
        return []
    if find_rc != 0:
        return ["find_failed"]
    return bpffs_vantio_paths(text)


def removal_census(
    programs: list[str],
    bpffs_paths: list[str],
    containers: str,
    bpftool_rc: int,
) -> dict[str, object]:
    docker = containers.strip()
    clean = bpftool_rc == 0 and programs == [] and bpffs_paths == [] and docker == ""
    return {
        "loader_programs": programs,
        "bpffs_vantio": bpffs_paths,
        "docker_containers": docker,
        "bpftool_rc": bpftool_rc,
        "verified_removed": clean,
    }


def _subject_path(event: object) -> str:
    if not isinstance(event, dict):
        return ""
    payload = event.get("Payload")
    if isinstance(payload, str) and payload.startswith("/") and ".." not in payload.split("/"):
        return payload
    return ""


def regression_still_holds(rows: dict) -> bool:
    """True when the Enterprise checks other than removal still hold.

    guest_rows folds the pre-uninstall program list into its exit code. These
    fields are the rest of that predicate, read back from the rows it wrote.
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
        revoke = rows["revoke"]
        if not isinstance(revoke, dict):
            return False
        digest = revoke.get("policy_digest")
        if not isinstance(digest, str) or not digest.startswith("sha256:"):
            return False
        allow = rows.get("grant_allow_event")
        allowed = _subject_path(allow)
        if (
            not isinstance(allow, dict)
            or allow.get("policy_digest") != digest
            or allow.get("ActionTaken") != "POLICY_ALLOW"
            or allow.get("EventType") != "POLICY_ALLOW"
            or allow.get("Uid") != 65534
            or allow.get("open_result") != "open_ok"
            or not allowed
            or allow.get("PolicyRuleMatched") != f"POLICY_ALLOW:{allowed}"
        ):
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
        probe = revoke.get("probe")
        if not isinstance(probe, dict) or probe.get("nobody_errno") != 13:
            return False
        block = revoke.get("block_event")
        blocked = _subject_path(block)
        if (
            not isinstance(block, dict)
            or block.get("policy_digest") != digest
            or block.get("ActionTaken") != "DENIED"
            or block.get("EventType") != "SYSCALL_OPENAT"
            or block.get("Uid") != 65534
            or block.get("BytesSevered") != 0
            or not blocked
            or block.get("PolicyRuleMatched") != f"ENFORCE_DENIED:{blocked}"
        ):
            return False
    except (AttributeError, KeyError, TypeError):
        return False
    return True


def finish_code(*, verified_removed: bool, guest_rc: int, rows: dict) -> int:
    """0 when the product uninstall left bpftool and bpffs empty and the regression held."""
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


def read_census() -> dict[str, object]:
    shown = _run(["bpftool", "prog", "show", "-j"])
    payload = _json_stdout(shown)
    raw = (shown.stdout or "") + (shown.stderr or "")
    bpftool_rc = shown.returncode
    if shown.returncode != 0:
        shown = _run(["bpftool", "prog", "show"])
        raw = (shown.stdout or "") + (shown.stderr or "")
        payload = None
        bpftool_rc = shown.returncode
    programs = loaded_programs(payload, raw)
    mounted = Path("/sys/fs/bpf").is_dir()
    if mounted:
        listed = _run(["find", "/sys/fs/bpf", "-name", "*vantio*", "-print"])
        bpffs = classify_bpffs(mounted=True, find_rc=listed.returncode, text=listed.stdout or "")
    else:
        bpffs = classify_bpffs(mounted=False, find_rc=0, text="")
    containers = _run(["docker", "ps", "-aq"])
    container_text = containers.stdout or ""
    if containers.returncode != 0:
        container_text = (containers.stdout or "") + (containers.stderr or "docker_ps_failed")
    return removal_census(programs, bpffs, container_text, bpftool_rc)


def poll_census(
    read: Callable[[], dict[str, object]] | None = None,
    *,
    timeout_s: float = CENSUS_POLL_TIMEOUT_S,
    interval_s: float = CENSUS_POLL_INTERVAL_S,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    """Read the census until it is clean or timeout_s passes. Return the last read.

    The returned census gains census_polls (reads taken) and census_waited_s.
    A census that is still not clean at the timeout stays not clean.
    """
    read = read or read_census
    start = clock()
    polls = 0
    while True:
        census = dict(read())
        polls += 1
        waited = clock() - start
        if census.get("verified_removed") is True or waited >= timeout_s:
            break
        sleep(min(interval_s, max(timeout_s - waited, 0.0)))
    census["census_polls"] = polls
    census["census_waited_s"] = round(waited, 3)
    return census


def _write(path: Path, census: dict[str, object]) -> dict:
    if not path.is_file():
        raise SystemExit("rows_missing")
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit("rows_malformed") from exc
    if not isinstance(body, dict):
        raise SystemExit("rows_malformed")
    prior = body.get("removal")
    if isinstance(prior, dict):
        # The guest census runs after the container stops and before uninstall.
        # Keep it. The graded removal below is the product uninstall result.
        body["after_container_exit"] = prior
    body["removal"] = census
    # guest_rows.py owns this file. Path.write_text recreates it, and a
    # sticky /tmp refuses that when the owner and the caller differ.
    from sticky_write import write_replacing

    write_replacing(path, json.dumps(body, indent=2, sort_keys=True) + "\n")
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
    census = poll_census()
    if not record:
        if census["verified_removed"] is not True:
            print("programs_not_removed " + " ".join(census["loader_programs"]), file=sys.stderr)
            return 1
        return 0
    body = _write(Path(record), census)
    code = finish_code(
        verified_removed=census["verified_removed"] is True,
        guest_rc=guest_rc,
        rows=body,
    )
    if code != 0 and census["verified_removed"] is not True:
        print("programs_not_removed " + " ".join(str(name) for name in census["loader_programs"]), file=sys.stderr)
    elif code != 0:
        print("guest", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
