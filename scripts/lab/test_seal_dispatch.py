#!/usr/bin/env python3
"""Offline checks for the lab seal gate. No network and no cloud credentials."""

from __future__ import annotations

import ast
import io
import os
import subprocess
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import yaml

import seal_dispatch

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "gcp-lab-provision.yml"
GOOD_SEAL = "ab" * 32
GOOD_COMMIT = "cd" * 20


def _hidden(blob: str, value: str) -> None:
    # The length line itself contains a space and a newline. A one-character
    # whitespace value is covered by the exact stdout equality instead.
    if len(value) >= 8 and value in blob:
        raise AssertionError(f"value was printed (len={len(value)})")


def workflow_check_script(text: str | None = None) -> str:
    body = WORKFLOW.read_text(encoding="utf-8") if text is None else text
    marker = "      - name: Check the seal input\n"
    rest = body[body.index(marker) :]
    header = "        run: |\n"
    script = rest[rest.index(header) + len(header) :]
    lines: list[str] = []
    for line in script.splitlines():
        if line.startswith("          "):
            lines.append(line[10:])
            continue
        if line.strip() == "":
            lines.append("")
            continue
        break
    return "\n".join(lines) + "\n"


def run_workflow_check(script: str, seal: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env={"SEAL": seal, "PATH": os.environ.get("PATH", "/usr/bin")},
        check=False,
    )


class WorkflowSealCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = workflow_check_script()
        cls.doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))

    def test_ci_runs_this_file(self) -> None:
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("python3 scripts/lab/test_seal_dispatch.py -v", ci)

    def test_sealcheck_is_first_and_blocks_later_jobs(self) -> None:
        jobs = list(self.doc["jobs"])
        self.assertEqual(jobs[0], "sealcheck")
        sealcheck = self.doc["jobs"]["sealcheck"]
        self.assertNotIn("environment", sealcheck)
        self.assertEqual(sealcheck["permissions"], {"contents": "read"})
        self.assertNotIn("secrets", yaml.dump(sealcheck))
        self.assertEqual([step["name"] for step in sealcheck["steps"]], ["Check the seal input"])
        self.assertNotIn("uses", sealcheck["steps"][0])
        fetch = self.doc["jobs"]["fetch"]
        needs = fetch["needs"]
        self.assertEqual(needs if isinstance(needs, list) else [needs], ["sealcheck"])
        teardown = self.doc["jobs"]["teardown"]
        self.assertEqual(teardown["needs"], ["sealcheck", "fetch", "deliver"])
        self.assertEqual(teardown["if"], "always() && needs.sealcheck.result == 'success'")
        self.assertNotIn("inputs.seal", self.script)
        self.assertIn("SEAL: ${{ inputs.seal }}", WORKFLOW.read_text(encoding="utf-8"))

    def test_accepts_64_lowercase_hex(self) -> None:
        done = run_workflow_check(self.script, GOOD_SEAL)
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stdout, "seal_len=64 result=pass\n")
        self.assertEqual(done.stderr, "")
        _hidden(done.stdout + done.stderr, GOOD_SEAL)

    def test_rejects_short_long_upper_nonhex_empty_and_whitespace(self) -> None:
        rejected = (
            "a" * 51,
            "a" * 65,
            "a" * 63,
            "a" * 0,
            "A" * 64,
            "AB" * 32,
            GOOD_SEAL.upper(),
            "g" * 64,
            "a" * 63 + "z",
            "a" * 63 + "-",
            "",
            " ",
            "\n",
            "\t",
            " " * 64,
            " " + GOOD_SEAL,
            GOOD_SEAL + " ",
            GOOD_SEAL + "\n",
            "\n" + GOOD_SEAL,
            GOOD_SEAL[:32] + " " + GOOD_SEAL[32:],
            "ab" * 31 + "AB",
        )
        self.assertEqual(len(GOOD_SEAL), 64)
        for value in rejected:
            with self.subTest(length=len(value)):
                done = run_workflow_check(self.script, value)
                self.assertEqual(done.returncode, 1)
                self.assertEqual(done.stdout, f"seal_len={len(value)} result=fail\n")
                self.assertEqual(done.stderr, "")
                _hidden(done.stdout + done.stderr, value)
                self.assertEqual(seal_dispatch.format_seal_check(value), done.stdout.rstrip("\n"))
                self.assertFalse(seal_dispatch.seal_ok(value))

    def test_module_check_matches_the_workflow_and_hides_the_value(self) -> None:
        self.assertTrue(seal_dispatch.seal_ok(GOOD_SEAL))
        self.assertEqual(seal_dispatch.format_seal_check(GOOD_SEAL), "seal_len=64 result=pass")
        _hidden(seal_dispatch.format_seal_check(GOOD_SEAL), GOOD_SEAL)
        with mock.patch.dict(os.environ, {"SEAL": GOOD_SEAL}, clear=False):
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = seal_dispatch.main(["check"])
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue(), "seal_len=64 result=pass\n")
        self.assertEqual(err.getvalue(), "")
        _hidden(out.getvalue() + err.getvalue(), GOOD_SEAL)

    def test_removed_validation_fails_the_reject_case(self) -> None:
        """The 51-character reject fails closed only while the pattern is present."""
        needle = r"^[0-9a-f]{64}$"
        self.assertIn(needle, self.script)
        mutated = self.script.replace(needle, ".*", 1)
        self.assertNotEqual(mutated, self.script)
        short = "a" * 51
        real = run_workflow_check(self.script, short)
        self.assertEqual(real.returncode, 1)
        self.assertEqual(real.stdout, "seal_len=51 result=fail\n")
        broken = run_workflow_check(mutated, short)
        with self.assertRaises(AssertionError):
            self.assertEqual(broken.returncode, 1)
            self.assertEqual(broken.stdout, "seal_len=51 result=fail\n")
        self.assertEqual(broken.returncode, 0)
        _hidden(broken.stdout + broken.stderr, short)

        source = (ROOT / "scripts" / "lab" / "seal_dispatch.py").read_text(encoding="utf-8")
        gate = "return isinstance(value, str) and SEAL_RE.fullmatch(value) is not None"
        self.assertEqual(source.count(gate), 1)
        mutated_source = source.replace(gate, "return True", 1)
        namespace = {"__name__": "seal_dispatch_mutated"}
        exec(compile(mutated_source, "seal_dispatch_mutated.py", "exec"), namespace)
        self.assertFalse(seal_dispatch.seal_ok(short))
        self.assertTrue(namespace["seal_ok"](short))
        with self.assertRaises(AssertionError):
            self.assertFalse(namespace["seal_ok"](short))


class PasteAndDispatchCheck(unittest.TestCase):
    def _run(self, command: str, seal: str, commit: str) -> tuple[int, str, str]:
        with mock.patch.dict(os.environ, {"SEAL": seal, "BUNDLE_COMMIT": commit}, clear=False):
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = seal_dispatch.main([command])
        return code, out.getvalue(), err.getvalue()

    def test_paste_line_is_one_whole_line(self) -> None:
        line = seal_dispatch.paste_line(GOOD_SEAL, GOOD_COMMIT)
        self.assertEqual(line, f"seal={GOOD_SEAL} bundle_commit={GOOD_COMMIT}")
        assert line is not None
        self.assertEqual(line.count("\n"), 0)
        self.assertEqual(len(GOOD_SEAL), 64)
        self.assertEqual(len(GOOD_COMMIT), 40)
        code, out, err = self._run("paste", GOOD_SEAL, GOOD_COMMIT)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out, line + "\n")
        self.assertEqual(out.splitlines(), [line])

    def test_pre_dispatch_check_rejects_the_51_character_seal(self) -> None:
        short = "ab" * 25 + "c"
        self.assertEqual(len(short), 51)
        self.assertIsNone(seal_dispatch.paste_line(short, GOOD_COMMIT))
        report = seal_dispatch.format_pasted_check(short, GOOD_COMMIT)
        self.assertEqual(report, "seal_len=51 bundle_commit_len=40 result=fail")
        _hidden(report, short)
        _hidden(report, GOOD_COMMIT)
        for command in ("paste", "check-pasted"):
            code, out, err = self._run(command, short, GOOD_COMMIT)
            self.assertEqual(code, 1, command)
            self.assertEqual(out, report + "\n")
            self.assertEqual(err, "")
            _hidden(out + err, short)
            _hidden(out + err, GOOD_COMMIT)

    def test_pre_dispatch_check_rejects_bad_lengths_and_hides_values(self) -> None:
        cases = (
            (GOOD_SEAL, "c" * 39),
            (GOOD_SEAL, "c" * 41),
            (GOOD_SEAL, ""),
            (GOOD_SEAL, GOOD_COMMIT.upper()),
            (GOOD_SEAL, GOOD_COMMIT + " "),
            ("", GOOD_COMMIT),
            (" " + GOOD_SEAL, GOOD_COMMIT),
            ("G" * 64, GOOD_COMMIT),
            ("g" * 64, "h" * 40),
        )
        for seal, commit in cases:
            with self.subTest(seal_len=len(seal), commit_len=len(commit)):
                self.assertIsNone(seal_dispatch.paste_line(seal, commit))
                code, out, err = self._run("check-pasted", seal, commit)
                self.assertEqual(code, 1)
                self.assertEqual(
                    out,
                    f"seal_len={len(seal)} bundle_commit_len={len(commit)} result=fail\n",
                )
                self.assertEqual(err, "")
                _hidden(out + err, seal)
                _hidden(out + err, commit)

    def test_pre_dispatch_check_passes_only_the_right_lengths(self) -> None:
        code, out, err = self._run("check-pasted", GOOD_SEAL, GOOD_COMMIT)
        self.assertEqual(code, 0)
        self.assertEqual(out, "seal_len=64 bundle_commit_len=40 result=pass\n")
        self.assertEqual(err, "")
        _hidden(out, GOOD_SEAL)
        _hidden(out, GOOD_COMMIT)

    def test_helper_does_not_dispatch_or_open_a_network_library(self) -> None:
        source = (ROOT / "scripts" / "lab" / "seal_dispatch.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module.split(".")[0])
        self.assertEqual(sorted(set(imported)), ["__future__", "os", "re", "sys", "typing"])
        for banned in ("subprocess", "urllib", "socket", "http", "boto", "google", "gh "):
            self.assertNotIn(banned, source)
        self.assertNotIn("workflow run", source)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = seal_dispatch.main([])
        self.assertEqual(code, 2)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("usage", err.getvalue())


class JobLogFetch(unittest.TestCase):
    def test_skipped_and_never_ran_jobs_are_not_fetched(self) -> None:
        # Shape of run 41159461489: skipped jobs still have startedAt and no steps.
        jobs = [
            {
                "name": "Fetch sealed bundle to private bucket",
                "status": "completed",
                "conclusion": "failure",
                "startedAt": "2026-10-31T02:19:27Z",
                "steps": [{"name": "Prepare and verify the private bundle", "conclusion": "failure"}],
            },
            {
                "name": "Teardown and verify removal",
                "status": "completed",
                "conclusion": "success",
                "startedAt": "2026-10-31T02:19:42Z",
                "steps": [{"name": "Set up job", "conclusion": "success"}],
            },
            {
                "name": "Pre-run cost check",
                "status": "completed",
                "conclusion": "skipped",
                "startedAt": "2026-10-31T02:19:40Z",
                "steps": [],
            },
            {
                "name": "Deliver offline VM",
                "status": "completed",
                "conclusion": "skipped",
                "startedAt": "2026-10-31T02:19:41Z",
                "steps": [],
            },
            {"name": "queued", "status": "queued", "conclusion": None},
            {"name": "waiting", "status": "waiting", "conclusion": None, "steps": []},
            {"name": "empty-completed", "status": "completed", "conclusion": None, "steps": []},
        ]
        seen: list[str] = []

        def get_log(job: dict) -> None:
            seen.append(str(job["name"]))
            raise OSError("404")

        notes = seal_dispatch.fetch_job_logs(jobs, get_log)
        self.assertEqual(seen, ["Fetch sealed bundle to private bucket", "Teardown and verify removal"])
        self.assertEqual(notes, ["log GET failed", "log GET failed"])
        self.assertNotIn("Pre-run cost check", seen)
        self.assertNotIn("Deliver offline VM", seen)

    def test_a_running_job_is_still_fetched(self) -> None:
        seen: list[str] = []
        jobs = (
            {"name": "live", "status": "in_progress", "conclusion": None, "steps": []},
            {"name": "cancelled-after-start", "status": "completed", "conclusion": "cancelled", "steps": [{"name": "Set up job"}]},
        )
        notes = seal_dispatch.fetch_job_logs(jobs, lambda job: seen.append(str(job["name"])))
        self.assertEqual(seen, ["live", "cancelled-after-start"])
        self.assertEqual(notes, [])

    def test_skipped_without_steps_key_is_not_fetched(self) -> None:
        calls: list[object] = []
        notes = seal_dispatch.fetch_job_logs(
            [{"name": "gate", "status": "completed", "conclusion": "skipped", "startedAt": "2026-10-31T02:19:40Z"}],
            lambda job: calls.append(job),
        )
        self.assertEqual(calls, [])
        self.assertEqual(notes, [])


if __name__ == "__main__":
    unittest.main()
