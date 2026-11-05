#!/usr/bin/env python3
"""Offline checks for the lab seal gate. No network and no cloud credentials."""

from __future__ import annotations

import ast
import copy
import io
import json
import os
import re
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import yaml

import seal_dispatch

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "gcp-lab-provision.yml"
ARM_WORKFLOW = ROOT / ".github" / "workflows" / "w3-lab-auto-arm.yml"
GOOD_SEAL = "ab" * 32
GOOD_COMMIT = "cd" * 20
WORKFLOW_REF = (
    "vantioai/vantio-open-core/.github/workflows/gcp-lab-provision.yml@refs/heads/main"
)
MAIN_ENV = {
    "GITHUB_EVENT_NAME": "workflow_dispatch",
    "GITHUB_REPOSITORY": "vantioai/vantio-open-core",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_WORKFLOW_REF": WORKFLOW_REF,
}


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


def _named_step(job: dict, name: str) -> dict:
    for step in job["steps"]:
        if step.get("name") == name:
            return step
    raise AssertionError(name)


def run_bash(
    script: str,
    env: dict[str, str],
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    full = {"PATH": os.environ.get("PATH", "/usr/bin")}
    full.update(env)
    return subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env=full,
        cwd=cwd,
        check=False,
    )


def model_require_main(env: dict[str, str]) -> bool:
    """The four Require main equalities. Other syntax is not this guard."""
    return all(env.get(key) == value for key, value in MAIN_ENV.items())


def actions_log(text: str) -> str:
    """Drop ::add-mask:: commands, then redact those values from later lines.

    This is the log text a runner keeps after it consumes the command.
    It is not the pre-script environment dump. The runner writes that dump
    before any command in the step.
    """
    masks: list[str] = []
    kept: list[str] = []
    for line in text.splitlines():
        match = re.fullmatch(r"::add-mask::(.*)", line)
        if match:
            value = match.group(1)
            if value:
                masks.append(value)
            continue
        redacted = line
        for mask in masks:
            redacted = redacted.replace(mask, "***")
        kept.append(redacted)
    if not kept:
        return ""
    body = "\n".join(kept)
    if text.endswith("\n"):
        return body + "\n"
    return body


def run_workflow_check(script: str, seal: str, extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run the sealcheck script with that step's env. SEAL is the only override."""
    loaded = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    raw = _named_step(loaded["jobs"]["sealcheck"], "Check the seal input").get("env") or {}
    env = {"PATH": os.environ.get("PATH", "/usr/bin"), "SEAL": seal}
    for key, value in raw.items():
        if key == "SEAL":
            continue
        env[key] = str(value)
    if extra:
        env.update(extra)
    return subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


_STATUS_FNS = ("always()", "success()", "failure()", "cancelled()")


def _needs_list(needs: object) -> list[str]:
    if needs is None:
        return []
    if isinstance(needs, str):
        return [needs]
    if isinstance(needs, list):
        return [str(item) for item in needs]
    raise AssertionError(f"unexpected needs: {needs!r}")


def _split_top(text: str, op: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    start = 0
    index = 0
    while index < len(text):
        char = text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif depth == 0 and text.startswith(op, index):
            parts.append(text[start:index])
            index += len(op)
            start = index
            continue
        index += 1
    parts.append(text[start:])
    return parts


def _wrapped(text: str) -> bool:
    if not (text.startswith("(") and text.endswith(")")):
        return False
    depth = 0
    for index, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index == len(text) - 1
    return False


def _eval_if(
    expr: str,
    needs: list[str],
    conclusions: dict[str, str],
    outputs: dict[str, dict[str, str]],
) -> bool:
    """Evaluate the job `if` strings this workflow uses. Other syntax fails the test."""

    def term(text: str) -> bool:
        text = text.strip()
        if text == "always()":
            return True
        if text == "success()":
            return all(conclusions.get(name) == "success" for name in needs)
        if text == "failure()":
            return any(conclusions.get(name) == "failure" for name in needs)
        if text == "cancelled()":
            return any(conclusions.get(name) == "cancelled" for name in needs)
        if _wrapped(text):
            return _eval_if(text[1:-1], needs, conclusions, outputs)
        result = re.fullmatch(r"needs\.([A-Za-z0-9_-]+)\.result == '([A-Za-z0-9_-]+)'", text)
        if result:
            return conclusions.get(result.group(1)) == result.group(2)
        output = re.fullmatch(
            r"needs\.([A-Za-z0-9_-]+)\.outputs\.([A-Za-z0-9_-]+) == '([^']*)'",
            text,
        )
        if output:
            return outputs.get(output.group(1), {}).get(output.group(2)) == output.group(3)
        raise AssertionError(f"unparsed if term: {text!r}")

    def parse(text: str) -> bool:
        text = text.strip()
        or_parts = _split_top(text, "||")
        if len(or_parts) > 1:
            return any(parse(part) for part in or_parts)
        and_parts = _split_top(text, "&&")
        if len(and_parts) > 1:
            return all(parse(part) for part in and_parts)
        if _wrapped(text):
            return parse(text[1:-1])
        return term(text)

    return parse(expr)


def _job_starts(job: dict, conclusions: dict[str, str], outputs: dict[str, dict[str, str]]) -> bool:
    """GitHub starts a job when its if is true. A missing status function implies success()."""
    needs = _needs_list(job.get("needs"))
    expr = job.get("if")
    if not isinstance(expr, str) or expr == "":
        expr = "success()"
    elif not any(fn in expr for fn in _STATUS_FNS):
        expr = f"success() && ({expr})"
    return _eval_if(expr, needs, conclusions, outputs)


def schedule(
    doc: dict,
    outcomes: dict[str, str],
    outputs: dict[str, dict[str, str]] | None = None,
) -> dict[str, str]:
    """Conclusions for one provision run. A job that does not start is skipped."""
    outputs = outputs or {}
    conclusions: dict[str, str] = {}
    for job_id, job in doc["jobs"].items():
        if _job_starts(job, conclusions, outputs):
            conclusions[job_id] = outcomes.get(job_id, "success")
        else:
            conclusions[job_id] = "skipped"
    return conclusions


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
        self.assertEqual(
            [step["name"] for step in sealcheck["steps"]],
            ["Require main on vantio-open-core", "Check the seal input"],
        )
        for step in sealcheck["steps"]:
            self.assertNotIn("uses", step)
        fetch = self.doc["jobs"]["fetch"]
        needs = fetch["needs"]
        self.assertEqual(needs if isinstance(needs, list) else [needs], ["sealcheck"])
        teardown = self.doc["jobs"]["teardown"]
        self.assertEqual(teardown["needs"], ["sealcheck", "fetch", "deliver"])
        self.assertEqual(teardown["if"], "always()")
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
        env = {"SEAL": seal, "BUNDLE_COMMIT": commit, "GITHUB_ACTIONS": ""}
        with mock.patch.dict(os.environ, env, clear=False):
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

    def test_timed_out_jobs_keep_their_log(self) -> None:
        """A deliver job that hits timeout-minutes must still be fetched."""
        jobs = [
            {
                "name": "deliver-timeout",
                "status": "completed",
                "conclusion": "timed_out",
                "steps": [{"name": "Create the offline VM", "conclusion": "success"}],
            },
            {
                "name": "timeout-without-steps",
                "status": "completed",
                "conclusion": "timed_out",
            },
            {
                "name": "timeout-empty-steps",
                "status": "completed",
                "conclusion": "timed_out",
                "steps": [],
            },
            {
                "name": "startup-failure",
                "status": "completed",
                "conclusion": "startup_failure",
                "steps": [{"name": "Set up job", "conclusion": "failure"}],
            },
            {
                "name": "neutral-with-steps",
                "status": "completed",
                "conclusion": "neutral",
                "steps": [{"name": "Set up job", "conclusion": "success"}],
            },
            {
                "name": "startup-failure-never-started",
                "status": "completed",
                "conclusion": "startup_failure",
                "steps": [],
            },
            {
                "name": "skipped-with-a-step",
                "status": "completed",
                "conclusion": "skipped",
                "steps": [{"name": "Set up job"}],
            },
        ]
        seen: list[str] = []
        notes = seal_dispatch.fetch_job_logs(jobs, lambda job: seen.append(str(job["name"])))
        self.assertEqual(
            seen,
            [
                "deliver-timeout",
                "timeout-without-steps",
                "timeout-empty-steps",
                "startup-failure",
                "neutral-with-steps",
            ],
        )
        self.assertEqual(notes, [])
        self.assertNotIn("startup-failure-never-started", seen)
        self.assertNotIn("skipped-with-a-step", seen)
        self.assertTrue(seal_dispatch.job_needs_log(jobs[0]))
        self.assertTrue(seal_dispatch.job_needs_log(jobs[2]))
        self.assertFalse(
            seal_dispatch.job_needs_log(
                {"name": "idle", "status": "completed", "conclusion": "success", "steps": []}
            )
        )


class SealFailureSweep(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))

    def test_job_order_is_the_schedule_order(self) -> None:
        self.assertEqual(list(self.doc["jobs"]), ["sealcheck", "fetch", "gate", "deliver", "teardown"])

    def test_bad_seal_still_runs_teardown_and_keeps_the_cost_gate(self) -> None:
        gate = self.doc["jobs"]["gate"]
        deliver = self.doc["jobs"]["deliver"]
        teardown = self.doc["jobs"]["teardown"]
        self.assertEqual(gate["needs"], "fetch")
        self.assertEqual(gate["if"], "needs.fetch.result == 'success'")
        self.assertEqual(deliver["needs"], ["fetch", "gate"])
        self.assertEqual(
            deliver["if"],
            "needs.fetch.result == 'success' && needs.gate.outputs.expected_oop_usd == '0'",
        )
        self.assertNotIn("continue-on-error", gate)
        self.assertNotIn("continue-on-error", deliver)
        self.assertEqual(deliver["timeout-minutes"], 110)
        self.assertEqual(deliver["environment"], "gcp-lab")
        joined = "\n".join(step.get("run") or "" for step in teardown["steps"])
        self.assertIn("teardown-if-present", joined)
        self.assertNotIn("create-instance", joined)

        # A zero cost-gate output must not create a VM when the seal check failed.
        bad = schedule(self.doc, {"sealcheck": "failure"}, {"gate": {"expected_oop_usd": "0"}})
        self.assertEqual(bad["sealcheck"], "failure")
        self.assertEqual(bad["fetch"], "skipped")
        self.assertEqual(bad["gate"], "skipped")
        self.assertEqual(bad["deliver"], "skipped")
        self.assertNotEqual(bad["teardown"], "skipped")

        blocked = schedule(
            self.doc,
            {"sealcheck": "success", "fetch": "success", "gate": "success"},
            {"gate": {"expected_oop_usd": "1"}},
        )
        self.assertEqual(blocked["deliver"], "skipped")
        self.assertNotEqual(blocked["teardown"], "skipped")
        self.assertEqual(blocked["gate"], "success")

        allowed = schedule(
            self.doc,
            {"sealcheck": "success", "fetch": "success", "gate": "success"},
            {"gate": {"expected_oop_usd": "0"}},
        )
        self.assertEqual(allowed["deliver"], "success")
        self.assertNotEqual(allowed["teardown"], "skipped")

        fetch_failed = schedule(self.doc, {"sealcheck": "success", "fetch": "failure"}, {})
        self.assertEqual(fetch_failed["gate"], "skipped")
        self.assertEqual(fetch_failed["deliver"], "skipped")
        self.assertNotEqual(fetch_failed["teardown"], "skipped")

    def test_requiring_sealcheck_success_skips_the_sweep(self) -> None:
        """The previous if dropped teardown when the seal check failed."""
        mutated = copy.deepcopy(self.doc)
        mutated["jobs"]["teardown"]["if"] = "always() && needs.sealcheck.result == 'success'"
        conclusions = schedule(mutated, {"sealcheck": "failure"}, {"gate": {"expected_oop_usd": "0"}})
        self.assertEqual(conclusions["teardown"], "skipped")
        self.assertEqual(conclusions["deliver"], "skipped")
        real = schedule(self.doc, {"sealcheck": "failure"}, {})
        self.assertNotEqual(real["teardown"], "skipped")


class SealNotInWorkflowLog(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = workflow_check_script()
        cls.doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        cls.body = WORKFLOW.read_text(encoding="utf-8")

    def test_step_forces_the_c_locale(self) -> None:
        step = _named_step(self.doc["jobs"]["sealcheck"], "Check the seal input")
        self.assertEqual(step["env"]["LC_ALL"], "C")
        self.assertEqual(set(step["env"]), {"SEAL", "LC_ALL"})
        upper = run_workflow_check(self.script, "A" * 64, extra={"LANG": "en_US.UTF-8"})
        self.assertEqual(upper.returncode, 1)
        self.assertEqual(upper.stdout, "seal_len=64 result=fail\n")
        self.assertEqual(upper.stderr, "")
        lower = run_workflow_check(self.script, GOOD_SEAL, extra={"LANG": "en_US.UTF-8"})
        self.assertEqual(lower.returncode, 0)
        self.assertEqual(lower.stdout, "seal_len=64 result=pass\n")
        self.assertNotIn(GOOD_SEAL, lower.stdout + lower.stderr)

    def test_paste_warning_says_the_seal_is_printed_on_purpose(self) -> None:
        doc = (ROOT / "docs" / "lab" / "seal-dispatch.md").read_text(encoding="utf-8")
        self.assertIn("## Warning: `paste` prints the seal", doc)
        self.assertIn("on purpose", doc)
        self.assertIn("GITHUB_ACTIONS=true", doc)
        self.assertIn("GITHUB_OUTPUT", doc)
        self.assertIn("ACTIONS_STEP_DEBUG", doc)
        self.assertIn("docs/lab/seal-dispatch.md", seal_dispatch.__doc__ or "")
        self.assertNotIn("seal_dispatch.py", self.body)
        sealcheck = self.doc["jobs"]["sealcheck"]
        self.assertNotIn("outputs", sealcheck)

    def test_paste_refuses_to_print_the_seal_in_actions(self) -> None:
        line = seal_dispatch.paste_line(GOOD_SEAL, GOOD_COMMIT)
        self.assertEqual(line, f"seal={GOOD_SEAL} bundle_commit={GOOD_COMMIT}")
        with mock.patch.dict(
            os.environ,
            {"SEAL": GOOD_SEAL, "BUNDLE_COMMIT": GOOD_COMMIT, "GITHUB_ACTIONS": "true"},
            clear=False,
        ):
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = seal_dispatch.main(["paste"])
        self.assertEqual(code, 1)
        self.assertEqual(out.getvalue(), "seal_len=64 bundle_commit_len=40 result=pass\n")
        self.assertEqual(err.getvalue(), "paste does not print the seal in a GitHub Actions log\n")
        _hidden(out.getvalue() + err.getvalue(), GOOD_SEAL)
        _hidden(out.getvalue() + err.getvalue(), GOOD_COMMIT)

    def test_workflow_check_does_not_write_output_summary_or_env(self) -> None:
        banned = (
            "set -x",
            'echo "$SEAL"',
            'echo "${SEAL}"',
            "GITHUB_OUTPUT",
            "GITHUB_STEP_SUMMARY",
            "GITHUB_ENV",
            "::debug::",
            "::notice::",
            ">>",
        )
        for item in banned:
            self.assertNotIn(item, self.script)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "github_output"
            summary = Path(tmp) / "summary"
            envfile = Path(tmp) / "github_env"
            for path in (output, summary, envfile):
                path.write_text("KEEP\n", encoding="utf-8")
            done = run_workflow_check(
                self.script,
                GOOD_SEAL,
                extra={
                    "GITHUB_ACTIONS": "true",
                    "GITHUB_OUTPUT": str(output),
                    "GITHUB_STEP_SUMMARY": str(summary),
                    "GITHUB_ENV": str(envfile),
                },
            )
            failed = run_workflow_check(
                self.script,
                "a" * 51,
                extra={
                    "GITHUB_OUTPUT": str(output),
                    "GITHUB_STEP_SUMMARY": str(summary),
                    "GITHUB_ENV": str(envfile),
                },
            )
            self.assertEqual(done.returncode, 0)
            self.assertEqual(done.stdout, "seal_len=64 result=pass\n")
            self.assertNotIn(GOOD_SEAL, done.stdout + done.stderr)
            self.assertEqual(failed.returncode, 1)
            self.assertEqual(failed.stdout, "seal_len=51 result=fail\n")
            self.assertNotIn("a" * 51, failed.stdout + failed.stderr)
            for path in (output, summary, envfile):
                self.assertEqual(path.read_text(encoding="utf-8"), "KEEP\n")

    def test_check_does_not_write_workflow_output_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "github_output"
            summary = Path(tmp) / "summary"
            envfile = Path(tmp) / "github_env"
            for path in (output, summary, envfile):
                path.write_text("KEEP\n", encoding="utf-8")
            with mock.patch.dict(
                os.environ,
                {
                    "SEAL": GOOD_SEAL,
                    "GITHUB_ACTIONS": "true",
                    "GITHUB_OUTPUT": str(output),
                    "GITHUB_STEP_SUMMARY": str(summary),
                    "GITHUB_ENV": str(envfile),
                },
                clear=False,
            ):
                out, err = io.StringIO(), io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    code = seal_dispatch.main(["check"])
            self.assertEqual(code, 0)
            self.assertEqual(out.getvalue(), "seal_len=64 result=pass\n")
            self.assertEqual(err.getvalue(), "")
            _hidden(out.getvalue() + err.getvalue(), GOOD_SEAL)
            for path in (output, summary, envfile):
                self.assertEqual(path.read_text(encoding="utf-8"), "KEEP\n")
                self.assertNotIn(GOOD_SEAL, path.read_text(encoding="utf-8"))


class RequireMainGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))

    def _script(self, job_id: str) -> str:
        step = _named_step(self.doc["jobs"][job_id], "Require main on vantio-open-core")
        run = step.get("run")
        if not isinstance(run, str):
            raise AssertionError(job_id)
        return run

    def test_sealcheck_uses_the_same_guard_before_auth(self) -> None:
        seal = self._script("sealcheck")
        fetch = self._script("fetch")
        deliver = self._script("deliver")
        teardown = self._script("teardown")
        self.assertEqual(seal, teardown)
        self.assertTrue(fetch.startswith(seal), "fetch guard does not start with the sealcheck guard")
        self.assertTrue(deliver.startswith(seal), "deliver guard does not start with the sealcheck guard")
        self.assertNotIn("inputs.seal", seal)
        self.assertNotIn("google-github-actions/auth", seal)
        self.assertIsNone(_named_step(self.doc["jobs"]["sealcheck"], "Require main on vantio-open-core").get("env"))
        for job_id in ("fetch", "deliver", "teardown"):
            job = self.doc["jobs"][job_id]
            names = [step["name"] for step in job["steps"]]
            guard_at = names.index("Require main on vantio-open-core")
            auth_at = next(
                index
                for index, step in enumerate(job["steps"])
                if "google-github-actions/auth@" in str(step.get("uses") or "")
            )
            self.assertLess(guard_at, auth_at, job_id)
        seal_job = self.doc["jobs"]["sealcheck"]
        joined = "\n".join(str(step.get("uses") or "") for step in seal_job["steps"])
        self.assertEqual(joined.strip(), "")
        self.assertNotIn("environment", seal_job)
        self.assertNotIn("if", seal_job)

    def test_model_matches_the_shell_and_a_failed_guard_still_sweeps(self) -> None:
        script = self._script("sealcheck")
        cases = (
            MAIN_ENV,
            {**MAIN_ENV, "GITHUB_REF": "refs/heads/feature"},
            {**MAIN_ENV, "GITHUB_EVENT_NAME": "pull_request"},
            {**MAIN_ENV, "GITHUB_REPOSITORY": "example/other"},
            {
                **MAIN_ENV,
                "GITHUB_WORKFLOW_REF": WORKFLOW_REF.replace("@refs/heads/main", "@refs/heads/feature"),
            },
            {key: value for key, value in MAIN_ENV.items() if key != "GITHUB_REF"},
        )
        for env in cases:
            with self.subTest(ref=env.get("GITHUB_REF"), event=env.get("GITHUB_EVENT_NAME")):
                done = run_bash(script, env)
                self.assertEqual(done.returncode == 0, model_require_main(env))
                self.assertEqual(done.stdout, "")
                if model_require_main(env):
                    self.assertEqual(done.stderr, "")
        bad_env = {**MAIN_ENV, "GITHUB_REF": "refs/heads/feature"}
        self.assertFalse(model_require_main(bad_env))
        for job_id in ("sealcheck", "fetch", "deliver", "teardown"):
            done = run_bash(self._script(job_id), bad_env)
            self.assertNotEqual(done.returncode, 0, job_id)
            self.assertEqual(done.stdout, "", job_id)
            self.assertNotIn("inputs.", done.stdout)
        for job_id in ("sealcheck", "teardown"):
            done = run_bash(self._script(job_id), MAIN_ENV)
            self.assertEqual(done.returncode, 0, job_id)
            self.assertEqual(done.stdout, "")
            self.assertEqual(done.stderr, "")
        # A failed guard fails the job. The job `if` model then skips fetch.
        bad = schedule(self.doc, {"sealcheck": "failure"}, {"gate": {"expected_oop_usd": "0"}})
        self.assertEqual(bad["sealcheck"], "failure")
        self.assertEqual(bad["fetch"], "skipped")
        self.assertEqual(bad["gate"], "skipped")
        self.assertEqual(bad["deliver"], "skipped")
        self.assertNotEqual(bad["teardown"], "skipped")
        started = schedule(self.doc, {}, {})
        self.assertEqual(started["sealcheck"], "success")
        self.assertEqual(started["fetch"], "success")


class SealLogMask(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))

    def _mask_script(self, job_id: str) -> str:
        step = _named_step(self.doc["jobs"][job_id], "Mask the seal input")
        run = step.get("run")
        if not isinstance(run, str):
            raise AssertionError(job_id)
        return run

    def test_fetch_and_deliver_mask_before_later_steps(self) -> None:
        fetch_script = self._mask_script("fetch")
        self.assertEqual(fetch_script, self._mask_script("deliver"))
        self.assertIn('printf \'%s\\n\' "::add-mask::${EXPECTED_SEAL}"', fetch_script)
        self.assertNotIn("inputs.seal", fetch_script)
        self.assertNotIn("set -x", fetch_script)
        for job_id in ("fetch", "deliver"):
            steps = self.doc["jobs"][job_id]["steps"]
            names = [step["name"] for step in steps]
            mask_at = names.index("Mask the seal input")
            self.assertEqual(names[0], "Require main on vantio-open-core")
            self.assertLess(0, mask_at)
            first = next(index for index, step in enumerate(steps) if "inputs.seal" in yaml.dump(step))
            self.assertEqual(first, mask_at, job_id)
            self.assertTrue(
                any("inputs.seal" in yaml.dump(step.get("env") or {}) for step in steps[mask_at + 1 :]),
                job_id,
            )
            self.assertNotIn("continue-on-error", steps[mask_at])
        check = _named_step(self.doc["jobs"]["sealcheck"], "Check the seal input")
        self.assertNotIn("::add-mask::", str(check.get("run")))
        self.assertNotIn("inputs.seal", yaml.dump(self.doc["jobs"]["gate"]))
        teardown_names = [step["name"] for step in self.doc["jobs"]["teardown"]["steps"]]
        self.assertNotIn("Mask the seal input", teardown_names)
        doc = (ROOT / "docs" / "lab" / "seal-dispatch.md").read_text(encoding="utf-8")
        self.assertIn("::add-mask::", doc)
        self.assertIn("before the script", doc)
        self.assertIn("seal_sha256", doc)
        self.assertIn("does not cross jobs", doc)
        self.assertIn("ACTIONS_STEP_DEBUG", doc)

    def test_mask_hides_a_later_line_and_rejects_bad_values(self) -> None:
        script = self._mask_script("fetch")
        valid = run_bash(script, {"EXPECTED_SEAL": GOOD_SEAL, "LC_ALL": "C", "LANG": "en_US.UTF-8"})
        self.assertEqual(valid.returncode, 0)
        self.assertEqual(valid.stderr, "")
        self.assertEqual(valid.stdout, f"::add-mask::{GOOD_SEAL}\n")
        self.assertEqual(actions_log(valid.stdout), "")
        later = actions_log(valid.stdout + f"EXPECTED_SEAL={GOOD_SEAL}\nW3_EXPECTED_SEAL={GOOD_SEAL}\n")
        self.assertEqual(later, "EXPECTED_SEAL=***\nW3_EXPECTED_SEAL=***\n")
        self.assertNotIn(GOOD_SEAL, later)
        # A line written before the command is the step-debug limit.
        pre = actions_log(f"EXPECTED_SEAL={GOOD_SEAL}\n" + valid.stdout + "after\n")
        self.assertTrue(pre.startswith(f"EXPECTED_SEAL={GOOD_SEAL}\n"))
        self.assertIn("after", pre)
        self.assertNotIn(GOOD_SEAL, pre.split("\n", 1)[1])
        rejected = ("", "a" * 51, "g" * 64, "A" * 64, "ab" * 31 + "AB")
        for value in rejected:
            with self.subTest(length=len(value)):
                done = run_bash(script, {"EXPECTED_SEAL": value, "LC_ALL": "C", "LANG": "en_US.UTF-8"})
                self.assertEqual(done.returncode, 1)
                self.assertEqual(done.stdout, f"seal_len={len(value)} result=fail\n")
                self.assertEqual(done.stderr, "")
                self.assertNotIn("::add-mask::", done.stdout)
                _hidden(done.stdout + done.stderr, value)


class ArmSealReject(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = yaml.safe_load(ARM_WORKFLOW.read_text(encoding="utf-8"))
        check = _named_step(cls.doc["jobs"]["arm"], "Check the seal input")
        canonical = _named_step(cls.doc["jobs"]["arm"], "Read the canonical seal")
        if not isinstance(check.get("run"), str) or not isinstance(canonical.get("run"), str):
            raise AssertionError("arm scripts")
        cls.script = check["run"]
        cls.canonical = canonical["run"]
        cls.lane = json.loads((ROOT / "release" / "pe-canonical-seal.json").read_text(encoding="utf-8"))[
            "lane_seal"
        ]["sha256"]

    def test_the_check_is_before_arming(self) -> None:
        names = [step["name"] for step in self.doc["jobs"]["arm"]["steps"]]
        check_at = names.index("Check the seal input")
        self.assertEqual(names[0], "Require main on vantio-open-core")
        for later in (
            "Checkout arm script",
            "Read the canonical seal",
            "Assume vantio-w3-lab-provision",
            "Arm the guest marker",
        ):
            self.assertLess(check_at, names.index(later), later)
        step = _named_step(self.doc["jobs"]["arm"], "Check the seal input")
        self.assertNotIn("continue-on-error", step)
        self.assertEqual(step["env"]["LC_ALL"], "C")
        self.assertEqual(set(step["env"]), {"SEAL", "LC_ALL"})
        trigger = self.doc.get(True, self.doc.get("on"))
        inputs = trigger["workflow_dispatch"]["inputs"]["seal"]
        self.assertIs(inputs["required"], True)
        self.assertNotIn("default", inputs)
        raw = ARM_WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("Empty uses release/pe-canonical-seal.json lane_seal.sha256", raw)
        self.assertNotIn('if [ -z "$seal" ]', self.canonical)
        self.assertNotIn('seal="$lane"', self.canonical)
        self.assertNotIn(self.lane, ARM_WORKFLOW.read_text(encoding="utf-8"))

    def test_empty_short_non_hex_and_valid(self) -> None:
        rejected = (("", 0), ("a" * 51, 51), ("g" * 64, 64))
        for value, length in rejected:
            with self.subTest(length=length):
                done = run_bash(self.script, {"SEAL": value, "LC_ALL": "C", "LANG": "en_US.UTF-8"})
                self.assertEqual(done.returncode, 1)
                self.assertEqual(done.stdout, f"seal_len={length} result=fail\n")
                self.assertEqual(done.stderr, "")
                self.assertNotIn("::add-mask::", done.stdout)
                _hidden(done.stdout + done.stderr, value)
                self.assertEqual(actions_log(done.stdout), done.stdout)
        valid = run_bash(self.script, {"SEAL": GOOD_SEAL, "LC_ALL": "C", "LANG": "en_US.UTF-8"})
        self.assertEqual(valid.returncode, 0)
        self.assertEqual(valid.stderr, "")
        self.assertEqual(valid.stdout, f"seal_len=64 result=pass\n::add-mask::{GOOD_SEAL}\n")
        self.assertEqual(actions_log(valid.stdout), "seal_len=64 result=pass\n")
        self.assertNotIn(GOOD_SEAL, actions_log(valid.stdout))
        masked = actions_log(valid.stdout + f"SEAL={GOOD_SEAL}\n")
        self.assertEqual(masked, "seal_len=64 result=pass\nSEAL=***\n")
        self.assertNotIn(GOOD_SEAL, masked)

    def test_canonical_step_rejects_without_the_lane_digest(self) -> None:
        pin = "cd" * 32
        for value in ("", "a" * 51, "g" * 64):
            with self.subTest(length=len(value)):
                with tempfile.TemporaryDirectory() as tmp:
                    output = Path(tmp) / "github_output"
                    done = run_bash(
                        self.canonical,
                        {
                            "INPUT_SEAL": value,
                            "INPUT_PUBLIC_PIN": pin,
                            "GITHUB_OUTPUT": str(output),
                            "LC_ALL": "C",
                        },
                        cwd=ROOT,
                    )
                    self.assertEqual(done.returncode, 1)
                    self.assertEqual(done.stdout, f"seal_len={len(value)} result=fail\n")
                    self.assertEqual(done.stderr, "")
                    self.assertNotIn(self.lane, done.stdout + done.stderr)
                    _hidden(done.stdout + done.stderr, value)
                    self.assertFalse(output.exists())
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "github_output"
            done = run_bash(
                self.canonical,
                {
                    "INPUT_SEAL": GOOD_SEAL,
                    "INPUT_PUBLIC_PIN": pin,
                    "GITHUB_OUTPUT": str(output),
                    "LC_ALL": "C",
                },
                cwd=ROOT,
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(done.stdout, "")
            self.assertEqual(done.stderr, "")
            self.assertNotIn(GOOD_SEAL, done.stdout + done.stderr)
            self.assertNotIn(self.lane, done.stdout + done.stderr)
            self.assertEqual(output.read_text(encoding="utf-8"), f"seal={GOOD_SEAL}\npublic_pin={pin}\n")


class SweeperStaysDisarmed(unittest.TestCase):
    def test_scheduled_sweeper_flag_stays_false(self) -> None:
        """Arming sweeper_enabled is a human call. This only checks it stays false."""
        raw = json.loads((ROOT / "scripts" / "gcp" / "lab_capabilities.json").read_text(encoding="utf-8"))
        self.assertIs(raw["sweeper_enabled"], False)
        text = (ROOT / ".github" / "workflows" / "gcp-lab-sweeper.yml").read_text(encoding="utf-8")
        self.assertIn("sets sweeper_enabled to true", text)
        self.assertIn("ships false", text)


if __name__ == "__main__":
    unittest.main()
