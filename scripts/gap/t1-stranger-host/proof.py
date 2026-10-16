#!/usr/bin/env python3
"""Run the local package proof. This does not start a cloud lab."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from constants import BASE_SHA, LABEL, PACKAGE_PREFIXES, PROOF_SCHEMA, TIER

ROOT = Path(__file__).resolve().parents[3]
TEST = ROOT / "tests" / "gap" / "t1-stranger-host" / "test_stranger_host.py"
EVIDENCE = ROOT / "evidence" / "gap" / "t1-stranger-host" / "local-package-proof.json"


def _git(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip()


def _allowed(path: str) -> bool:
    return any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in PACKAGE_PREFIXES)


def changed_paths() -> list[str]:
    names = _git(["diff", "--name-only", "origin/main"])
    status = _git(["status", "--porcelain=v1", "-uall"])
    found: list[str] = []
    for line in names.splitlines():
        if line:
            found.append(line)
    for line in status.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path:
            found.append(path)
    ordered: list[str] = []
    for path in found:
        if path not in ordered:
            ordered.append(path)
    return ordered


def main() -> int:
    proc = subprocess.run([sys.executable, str(TEST)], cwd=ROOT, capture_output=True, text=True, check=False)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    paths = changed_paths()
    outside = [path for path in paths if not _allowed(path)]
    passed = proc.returncode == 0 and not outside
    body = {
        "base_sha": BASE_SHA,
        "claim_cap": "FIXTURE_NOT_A_HOST_PROOF",
        "cloud_labs_run": False,
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "head_sha": _git(["rev-parse", "HEAD"]),
        "host_run": False,
        "label": LABEL,
        "paths_outside_package": outside,
        "pinned_trust_signature": "not_produced",
        "public_pin_moved": False,
        "schema": PROOF_SCHEMA,
        "stranger_host": "not_run",
        "tests_exit": proc.returncode,
        "tests_passed": proc.returncode == 0,
        "tier": TIER,
    }
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if outside:
        print("package paths left the T1 directory", file=sys.stderr)
    if passed:
        print("PACKAGE_PROOF_OK")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
