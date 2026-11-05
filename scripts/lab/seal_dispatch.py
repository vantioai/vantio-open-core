#!/usr/bin/env python3
"""Seal and bundle-commit checks for a lab dispatch.

The GCP provision workflow enforces the same 64-lowercase-hex rule before
checkout. `paste` prints one operator line, `seal=<64 hex> bundle_commit=<40 hex>`,
on purpose. That print is for a terminal, not a workflow log. See
docs/lab/seal-dispatch.md. `paste` refuses while GITHUB_ACTIONS=true so the
seal is not written to a job log. `check` and `check-pasted` print lengths
and pass or fail only. This module does not call GitHub or a cloud.

Job log collection keeps a log for a job that ran, including conclusion
timed_out. It skips a skipped job and a job that never started.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Callable, Mapping, Sequence

SEAL_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_NOT_STARTED = frozenset({"", "queued", "waiting", "pending", "requested"})
# timed_out means the job ran until the clock, so it is fetched even when
# the step list is empty. startup_failure and neutral stay in this set so a
# missing steps key still counts as ran.
_RAN = frozenset({"success", "failure", "cancelled", "timed_out", "startup_failure", "neutral"})


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

    A timed_out job is kept even when its step list is empty: the conclusion
    means the job ran until timeout-minutes. Any other completed job with at
    least one step ran, including startup_failure and neutral. Skipped jobs
    can still carry startedAt. Run 41159461489's cost-gate and deliver jobs
    did, with conclusion skipped and no steps.
    """
    conclusion = job.get("conclusion")
    status = job.get("status")
    if conclusion == "skipped" or status == "skipped":
        return False
    if not isinstance(status, str) or status in _NOT_STARTED:
        return False
    if status == "in_progress" or conclusion == "timed_out":
        return True
    steps = job.get("steps")
    if status == "completed" and isinstance(steps, list) and len(steps) > 0:
        return True
    if "steps" in job and not steps:
        return False
    if conclusion not in _RAN:
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
        # The operator line contains the seal. A workflow log must not.
        if os.environ.get("GITHUB_ACTIONS") == "true":
            sys.stdout.write(format_pasted_check(seal, bundle_commit) + "\n")
            sys.stderr.write("paste does not print the seal in a GitHub Actions log\n")
            return 1
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
