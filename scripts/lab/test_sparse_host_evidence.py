#!/usr/bin/env python3
"""Import each lab runner from that job's sparse-checkout set.

The checker is deleted before the second import. Teardown, verify-removed,
collect, and the GCP always-run teardown must still import. This test does
not call a cloud.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CHECKER = "scripts/lab/host_evidence_hu.py"
RUNNER_MARKERS = ("scripts/aws/w3_lab_steps.py", "scripts/gcp/offline_deliver.py")
PROBE = r"""
import inspect
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, "scripts/aws")
sys.path.insert(0, "scripts/gcp")
for name in os.environ["PROBE_MODS"].split():
    __import__(name)
print("IMPORT_OK")
if os.environ.get("PROBE_CALL") != "1":
    raise SystemExit(0)

def boom():
    raise AssertionError("checker loaded")

if "w3_lab_steps" in sys.modules:
    import w3_lab_steps
    w3_lab_steps._load_host_evidence = boom
    for name in ("execute_teardown", "execute_verify", "execute_collect", "preflight_long_soak", "close_ssh"):
        source = inspect.getsource(getattr(w3_lab_steps, name))
        if "_load_host_evidence" in source or "host_evidence_hu" in source:
            raise SystemExit("depends " + name)
    os.environ.pop("INSTANCE_ID", None)
    for call in (
        lambda: w3_lab_steps.execute_teardown(lambda _args: {}, datetime.now(timezone.utc)),
        lambda: w3_lab_steps.execute_verify(lambda _args: {}, datetime.now(timezone.utc)),
    ):
        try:
            call()
        except Exception as exc:
            if "checker loaded" in str(exc):
                raise
if "offline_deliver" in sys.modules:
    import offline_deliver
    offline_deliver._load_host_evidence = boom
    for name in ("teardown_if_present", "remove_os_login_key", "delete_handoff"):
        source = inspect.getsource(getattr(offline_deliver, name))
        if "_load_host_evidence" in source or "host_evidence_hu" in source:
            raise SystemExit("depends " + name)
    try:
        offline_deliver.teardown_if_present({})
    except SystemExit as exc:
        if exc.code != "refusing to call gcloud":
            raise
    pub = os.path.expanduser("~/.ssh/google_compute_engine.pub")
    if not os.path.isfile(pub) and offline_deliver.remove_os_login_key() != 0:
        raise SystemExit("oslogin")
print("CALL_OK")
"""


def _jobs() -> list[dict]:
    found: list[dict] = []
    for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
        body = yaml.safe_load(path.read_text(encoding="utf-8"))
        jobs = body.get("jobs") if isinstance(body, dict) else None
        if not isinstance(jobs, dict):
            continue
        for job_name, job in jobs.items():
            if not isinstance(job, dict):
                continue
            for step in job.get("steps") or []:
                if not isinstance(step, dict):
                    continue
                raw = (step.get("with") or {}).get("sparse-checkout")
                if not isinstance(raw, str):
                    continue
                paths = [line.strip() for line in raw.splitlines() if line.strip()]
                if not any(marker in paths for marker in RUNNER_MARKERS):
                    continue
                found.append(
                    {
                        "job": f"{path.name}:{job_name}",
                        "mods": _mods(paths),
                        "paths": paths,
                    }
                )
    return found


def _mods(paths: list[str]) -> list[str]:
    mods: list[str] = []
    if "scripts/aws/w3_lab_steps.py" in paths:
        mods.append("w3_lab_steps")
    if "scripts/gcp/offline_deliver.py" in paths:
        mods.append("offline_deliver")
    return mods


def _copy_set(paths: list[str], dest: Path) -> None:
    for entry in paths:
        source = ROOT / entry
        target = dest / entry
        if not source.exists():
            raise AssertionError(f"missing {entry}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"), dirs_exist_ok=True)
        else:
            shutil.copy2(source, target)


def _import(dest: Path, mods: list[str], *, call: bool) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PROBE_MODS"] = " ".join(mods)
    env["PROBE_CALL"] = "1" if call else "0"
    env.pop("INSTANCE_ID", None)
    return subprocess.run(
        [sys.executable, "-c", PROBE],
        cwd=dest,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


class SparseImportTests(unittest.TestCase):
    def test_every_runner_job_imports_with_and_without_the_checker(self) -> None:
        jobs = _jobs()
        self.assertGreaterEqual(len(jobs), 8)
        names = {job["job"] for job in jobs}
        for required in (
            "w3-lab-auto-arm.yml:",
            "w3-lab-auto-teardown.yml:",
            "w3-lab-auto-verify-removed.yml:",
            "w3-lab-auto-collect.yml:",
            "w3-lab-auto-long-soak.yml:",
            "gcp-lab-provision.yml:",
        ):
            self.assertTrue(any(name.startswith(required) for name in names), required)
        for job in jobs:
            with self.subTest(job=job["job"]):
                self.assertIn(CHECKER, job["paths"])
                self.assertTrue(job["mods"])
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    _copy_set(job["paths"], root)
                    listed = _import(root, job["mods"], call=False)
                    self.assertEqual(listed.returncode, 0, listed.stderr)
                    self.assertIn("IMPORT_OK", listed.stdout)
                    checker = root / CHECKER
                    self.assertTrue(checker.is_file())
                    checker.unlink()
                    bare = _import(root, job["mods"], call=True)
                    self.assertEqual(bare.returncode, 0, bare.stderr)
                    self.assertIn("IMPORT_OK", bare.stdout)
                    self.assertIn("CALL_OK", bare.stdout)


if __name__ == "__main__":
    unittest.main()
