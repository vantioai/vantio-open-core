"""Enrollment file. Test tenants only. Exact container ids. Not Phantom Engine."""

from __future__ import annotations

import errno
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path

MAX_BYTES = 65536


@dataclass(frozen=True)
class Enrollment:
    status: str
    host_id: str
    host_processes: bool
    containers: frozenset[str]
    reason: str | None


def _bad(reason: str) -> Enrollment:
    return Enrollment("unknown", "", False, frozenset(), reason)


def load_enrollment(path: Path | None) -> Enrollment:
    if path is None:
        return _bad("enrollment_missing")
    try:
        fd = os.open(os.fspath(path), os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return _bad("enrollment_missing")
    except OSError as err:
        if err.errno == errno.ELOOP:
            return _bad("enrollment_symlink")
        return _bad("enrollment_unreadable")
    try:
        info = os.fstat(fd)
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            return _bad("enrollment_unreadable")
        if info.st_size > MAX_BYTES:
            return _bad("enrollment_schema")
        blob = os.read(fd, MAX_BYTES + 1)
    except OSError:
        return _bad("enrollment_unreadable")
    finally:
        os.close(fd)
    if len(blob) > MAX_BYTES:
        return _bad("enrollment_schema")
    try:
        parsed = json.loads(blob.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return _bad("enrollment_schema")
    return _parse(parsed)


def _parse(parsed: object) -> Enrollment:
    if not isinstance(parsed, dict):
        return _bad("enrollment_schema")
    allowed = {"schema", "host_id", "host_processes", "containers"}
    if set(parsed) != allowed:
        return _bad("enrollment_schema")
    if parsed.get("schema") != "vantio.optics.enrollment.v1":
        return _bad("enrollment_schema")
    host_id = parsed.get("host_id")
    if not isinstance(host_id, str) or not host_id or len(host_id) > 128:
        return _bad("enrollment_schema")
    host_processes = parsed.get("host_processes")
    if not isinstance(host_processes, bool):
        return _bad("enrollment_schema")
    containers = parsed.get("containers")
    if not isinstance(containers, list):
        return _bad("enrollment_schema")
    ids: set[str] = set()
    for item in containers:
        if not isinstance(item, str) or len(item) != 64:
            return _bad("enrollment_schema")
        lowered = item.lower()
        if any(ch not in "0123456789abcdef" for ch in lowered):
            return _bad("enrollment_schema")
        ids.add(lowered)
    return Enrollment("ok", host_id, host_processes, frozenset(ids), None)


