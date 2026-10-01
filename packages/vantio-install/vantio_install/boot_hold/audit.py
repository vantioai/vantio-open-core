"""Append-only audit log for hold changes."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vantio_install.boot_hold.constants import AUDIT_REL
from vantio_install.boot_hold.identity import Caller


def append_audit(root: Path, caller: Caller, action: str, result: str, detail: dict[str, Any] | None = None) -> None:
    path = root / AUDIT_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "action": action,
        "result": result,
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "euid": caller.euid,
        "pid": caller.pid,
        "comm": caller.comm,
        "pid1_comm": caller.pid1_comm,
        "cgroup": caller.cgroup_text.strip().replace("\n", " | "),
        "detail": detail or {},
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    os.chmod(path, 0o600)
    if root == Path("/"):
        os.chown(path, 0, 0)
