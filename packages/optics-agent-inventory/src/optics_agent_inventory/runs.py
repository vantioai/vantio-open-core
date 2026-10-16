"""Run-log annotation. Logs never create a workload and never keep path or error text."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from optics_agent_inventory.catalog import catalog_in_scope, guess_provider
from optics_agent_inventory.endpoints import Observed
from optics_agent_inventory.procfs import ProcessRecord

MAX_RUN_BYTES = 1_000_000


def annotate_runs(
    directory: Path | None,
    processes: dict[int, ProcessRecord],
    scanner_nspid_count: int,
    extra: tuple[str, ...],
) -> tuple[dict[int, list[Observed]], bool]:
    notes: dict[int, list[Observed]] = {}
    if directory is None or not directory.exists():
        return notes, False
    unreadable = False
    try:
        names = list(os.scandir(directory))
    except OSError:
        return notes, True
    for entry in names:
        if not entry.name.endswith(".json"):
            continue
        parsed, failed = _read_run(Path(entry.path))
        if failed or parsed is None:
            unreadable = True
            continue
        pid = parsed.get("pid")
        if not isinstance(pid, int):
            continue
        proc = processes.get(pid)
        if proc is None or proc.start_unix is None:
            continue
        if proc.nspid_count != scanner_nspid_count:
            continue
        started = _unix(parsed.get("started_at"))
        if started is None or proc.start_unix > started + 2:
            continue
        generated = _unix(parsed.get("generated_at"))
        if generated is not None and proc.start_unix > generated:
            continue
        calls = parsed.get("calls")
        if not isinstance(calls, list):
            continue
        for call in calls:
            if not isinstance(call, dict):
                continue
            host = call.get("hostname")
            if not isinstance(host, str):
                continue
            lowered = host.lower()
            if not catalog_in_scope(lowered, None, extra):
                continue
            notes.setdefault(pid, []).append(
                Observed(lowered, None, guess_provider(lowered, None), "run_log")
            )
        del parsed
    return notes, unreadable


def _read_run(path: Path) -> tuple[dict | None, bool]:
    try:
        fd = os.open(os.fspath(path), os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return None, True
    try:
        blob = os.read(fd, MAX_RUN_BYTES + 1)
    except OSError:
        return None, True
    finally:
        os.close(fd)
    if len(blob) > MAX_RUN_BYTES:
        return None, True
    try:
        parsed = json.loads(blob.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return None, True
    if not isinstance(parsed, dict) or parsed.get("vantio_run_log") != "1":
        return None, False
    return parsed, False


def _unix(value: object) -> float | None:
    if not isinstance(value, str):
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()
