#!/usr/bin/env python3
"""Run the T5 unit tests and named drills. Write one Lab-only evidence file.

Exit 0 only when every drill passes. This script does not start a cloud lab
and does not load eBPF.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PACKAGE = REPO / "packages" / "t5-egress-drills"
POLICY = Path(__file__).resolve().parent / "policy.json"
CATALOG = Path(__file__).resolve().parent / "catalog.json"
EVIDENCE = REPO / "docs" / "planning" / "gap-t5-egress" / "evidence" / "proof.json"

NET_DRILLS = (
    "t5-dns-allow-list",
    "t5-dns-long-label",
    "t5-dns-high-entropy",
    "t5-dns-query-volume",
    "t5-dns-unknown-delegation",
    "t5-icmp-egress",
    "t5-get-write",
    "t5-loopback-priv-esc",
)
MOUNT_DRILLS = ("t5-symlink-escape",)


def _inode(path: str) -> int:
    return Path(path).stat().st_ino


def _run_drill(drill_id: str, isolation: str, out_dir: Path) -> dict[str, object]:
    evidence_path = out_dir / f"{drill_id}.json"
    parent_net = _inode("/proc/self/ns/net")
    parent_mnt = _inode("/proc/self/ns/mnt")
    flag = "--net" if isolation == "netns" else "--mount"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PACKAGE)
    command = [
        "unshare",
        "--user",
        "--map-root-user",
        flag,
        sys.executable,
        "-m",
        "t5_egress.runner",
        drill_id,
        str(evidence_path),
        str(POLICY),
        str(parent_net),
    ]
    timeout = 90 if drill_id == "t5-dns-query-volume" else 30
    completed = subprocess.run(command, env=env, timeout=timeout, check=False)
    if not evidence_path.is_file():
        return {"drill_id": drill_id, "result": "fail", "detail": "no evidence", "exit_code": completed.returncode}
    record = json.loads(evidence_path.read_text(encoding="utf-8"))
    record["exit_code"] = completed.returncode
    if isolation == "netns":
        record["netns_differs"] = record.get("ns_net_inode") != parent_net
        if not record["netns_differs"]:
            record["result"] = "fail"
    else:
        record["mount_ns_differs"] = record.get("ns_mnt_inode") != parent_mnt
        if not record["mount_ns_differs"]:
            record["result"] = "fail"
    if completed.returncode != 0:
        record["result"] = "fail"
    cases = record.get("cases")
    if not isinstance(cases, list) or not cases or any(item.get("ok") is not True for item in cases):
        record["result"] = "fail"
    return record


def main() -> int:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PACKAGE)
    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", str(PACKAGE / "tests")],
        cwd=str(PACKAGE),
        env=env,
        check=False,
    )
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    catalog_ids = [item["id"] for item in catalog["drills"]]
    expected = list(NET_DRILLS) + list(MOUNT_DRILLS)
    if catalog_ids != expected or catalog.get("cloud_run") is not False:
        print("catalog does not match the proof runner", file=sys.stderr)
        return 1
    drills: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="t5-proof-") as tmp:
        out_dir = Path(tmp)
        for drill_id in NET_DRILLS:
            drills.append(_run_drill(drill_id, "netns", out_dir))
        for drill_id in MOUNT_DRILLS:
            drills.append(_run_drill(drill_id, "mountns", out_dir))
    passed = tests.returncode == 0 and all(item.get("result") == "pass" for item in drills)
    proof = {
        "track": "T5",
        "label": "Lab-only",
        "kernel_attach": "Roadmap",
        "cloud_run": False,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "policy_sha256": hashlib.sha256(POLICY.read_bytes()).hexdigest(),
        "unit_tests": "pass" if tests.returncode == 0 else "fail",
        "result": "pass" if passed else "fail",
        "drills": drills,
    }
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"proof result={proof['result']} evidence={EVIDENCE}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
