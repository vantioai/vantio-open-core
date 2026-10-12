#!/usr/bin/env python3
"""Write the soak status file on this host.

The collect workflow stores the same facts as a GitHub artifact every 15
minutes. extract_soak_status turns one of those payloads into the scratch
file so phantom-box can read instance state, the last check time, and counts
without opening AWS. SOAK_STATUS_IDLE=1 writes the not-started document.

Audience: INTERNAL_RESTRICTED
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

STATUS_PATH = Path(
    os.environ.get(
        "SOAK_STATUS_PATH",
        "/home/vantioai/scratch/honesty-2026-10-06/evidence/soak-status.json",
    )
)


def extract_soak_status(collect: Mapping[str, Any], *, checked_at: str) -> dict[str, Any]:
    """One status document from a collect payload. No AWS call."""
    instances = collect.get("instances")
    rows = instances if isinstance(instances, list) else []
    soak = [row for row in rows if isinstance(row, Mapping) and row.get("soak_active") is True]
    checks = int(collect.get("check_count") or 0)
    if not soak:
        return {
            "check_count": 0,
            "cloudtrail": None,
            "counts": {"checks": checks, "instances": len(rows)},
            "instance_id": None,
            "instance_state": "not_started",
            "last_check_time": checked_at,
            "reason": "no_active_soak",
            "started_at": None,
        }
    row = soak[0]
    count = row.get("check_count")
    return {
        "check_count": int(count) if isinstance(count, int) else 0,
        "cloudtrail": row.get("cloudtrail"),
        "counts": {"checks": int(count) if isinstance(count, int) else 0},
        "instance_id": row.get("instance_id"),
        "instance_state": row.get("instance_state") or row.get("status"),
        "last_check_time": checked_at,
        "reason": None,
        "started_at": None,
    }


def write_status(document: Mapping[str, Any], path: Path = STATUS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(document, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    if os.environ.get("SOAK_STATUS_IDLE") == "1":
        write_status(
            {
                "check_count": 0,
                "cloudtrail": None,
                "counts": {"checks": 0},
                "detail": os.environ.get("SOAK_STATUS_DETAIL", ""),
                "instance_id": None,
                "instance_state": "not_started",
                "last_check_time": _now(),
                "reason": os.environ.get("SOAK_STATUS_REASON", "no_active_soak"),
                "started_at": None,
            }
        )
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
