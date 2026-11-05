#!/usr/bin/env python3
"""Seal and bundle-commit checks for a lab dispatch.

The GCP provision workflow enforces the same 64-lowercase-hex rule before
checkout. This module prints one paste line for the operator and checks the
pasted lengths before any dispatch. It does not call GitHub or a cloud.

Job log collection skips a log GET when the job was skipped or never ran.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Callable, Mapping, Sequence

SEAL_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_NOT_STARTED = frozenset({"", "queued", "waiting", "pending", "requested"})
_RAN = frozenset({"success", "failure", "cancelled"})


def seal_ok(value: str) -> bool:
    return isinstance(value, str) and SEAL_RE.fullmatch(value) is not None


def commit_ok(value: str) -> bool:
    return isinstance(value, str) and COMMIT_RE.fullmatch(value) is not None


def format_seal_check(value: str) -> str:
    result = "pass" if seal_ok(value) else "fail"
    return f"seal_len={len(value)} result={result}"


def format_pasted_check(seal: str, bundle_commit: str) -> str:
    ok = seal_ok(seal) and commit_ok(bundle_commit)
    result = "pass" if ok else "fail"
    return f"seal_len={len(seal)} bundle_commit_len={len(bundle_commit)} result={result}"


def paste_line(seal: str, bundle_commit: str) -> str | None:
    """One line the operator pastes whole. None when either value is the wrong length."""
    if not seal_ok(seal) or not commit_ok(bundle_commit):
        return None
    return f"seal={seal} bundle_commit={bundle_commit}"


def job_needs_log(job: Mapping[str, object]) -> bool:
    """False for a skipped job or a job that never ran, so the caller skips the log GET.

    Skipped jobs can still carry startedAt. Run 41159461489's cost-gate and
    deliver jobs did, with conclusion skipped and no steps.
    """
    conclusion = job.get("conclusion")
    status = job.get("status")
    if conclusion == "skipped" or status == "skipped":
        return False
    if not isinstance(status, str) or status in _NOT_STARTED:
        return False
    if "steps" in job and not job.get("steps") and status != "in_progress":
        return False
    if conclusion not in _RAN and status != "in_progress":
        return False
    return True


def fetch_job_logs(
    jobs: Sequence[Mapping[str, object]],
    get_log: Callable[[Mapping[str, object]], object],
) -> list[str]:
    """GET logs only for jobs that ran. A failed GET is recorded without the error body."""
    notes: list[str] = []
    for job in jobs:
        if not job_needs_log(job):
            continue
        try:
            get_log(job)
        except Exception:
            notes.append("log GET failed")
    return notes


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    command = args[0] if args else ""
    seal = os.environ.get("SEAL", "")
    bundle_commit = os.environ.get("BUNDLE_COMMIT", "")
    if command == "check":
        sys.stdout.write(format_seal_check(seal) + "\n")
        return 0 if seal_ok(seal) else 1
    if command == "paste":
        line = paste_line(seal, bundle_commit)
        if line is None:
            sys.stdout.write(format_pasted_check(seal, bundle_commit) + "\n")
            return 1
        sys.stdout.write(line + "\n")
        return 0
    if command == "check-pasted":
        sys.stdout.write(format_pasted_check(seal, bundle_commit) + "\n")
        return 0 if seal_ok(seal) and commit_ok(bundle_commit) else 1
    sys.stderr.write("usage: seal_dispatch.py check|paste|check-pasted\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
