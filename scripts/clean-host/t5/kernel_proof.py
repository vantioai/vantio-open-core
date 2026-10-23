#!/usr/bin/env python3
"""Compile the T5 program and run its model tests. Does not call bpf."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PACKAGE = REPO / "packages" / "t5-egress-kernel"
EVIDENCE = REPO / "docs" / "planning" / "gap-t5-egress" / "evidence" / "kernel-compile.json"
sys.path.insert(0, str(REPO / "packages" / "t5-egress-drills"))
sys.path.insert(0, str(PACKAGE))

from t5_kernel.compile_bpf import compile_object  # noqa: E402


def main() -> int:
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{REPO / 'packages' / 't5-egress-drills'}:{PACKAGE}"
    tests = subprocess.run(
        [sys.executable, str(PACKAGE / "tests" / "test_kernel_model.py")],
        cwd=str(REPO),
        env=env,
        check=False,
    )
    compiled = compile_object(PACKAGE / "bpf" / "t5_egress.bpf.o")
    object_path = PACKAGE / "bpf" / "t5_egress.bpf.o"
    if object_path.is_file():
        object_path.unlink()
    passed = tests.returncode == 0 and compiled.get("status") in {"pass", "skipped"} and compiled.get("attached") is False
    record = {
        "track": "T5",
        "battery_id": "t5-egress",
        "label": "Lab-only" if compiled.get("status") == "pass" else "Roadmap",
        "kernel_attach": "Roadmap",
        "attached": False,
        "compile": compiled.get("status"),
        "unit_tests": "pass" if tests.returncode == 0 else "fail",
        "result": "pass" if passed else "fail",
        "entropy": "userspace",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seal_note": "Lane K lab seal is 46982f26 (8b1106ef until 2026-10-23, 6d3ce580 until 2026-10-22). The public pin stays e0b19d55.",
    }
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"kernel proof result={record['result']} compile={record['compile']}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
