#!/usr/bin/env python3
"""GCP 2D loader-kill: the after-restart deny row evidence and its 15 s wait.

Run 5 (provision 39867694852) failed 2D with no_new_deny_after_restart after
5.25 s. The rows could not tell a late row from a dropped one. On GCP only
(VANTIO_LAB_CLOUD=gcp), the guest now waits up to 15 s and records restart_rows
for both sides. The host grades those rows again. These tests do not call GCP.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import importlib.util

import offline_deliver as od

ROOT = Path(__file__).resolve().parents[2]


def _hu_pass() -> str:
    path = ROOT / "scripts" / "lab" / "host_evidence_hu.py"
    spec = importlib.util.spec_from_file_location("host_evidence_hu_2d", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.transcript(module.passing_facts())


HU_PASS = _hu_pass()
GUESTS = ROOT / "scripts/aws/lab-guests"
sys.path.insert(0, str(GUESTS))
import phase2_grade as grade  # noqa: E402

PID = 3363
ANCHOR = 6946
DENY = "/opt/vantio-lab/ceiling/deny.txt"


def _side(*, errno=13, wait_s=0.25, seen=True, before=False, anchor=ANCHOR, pid=PID, row_pid=None, count=None):
    row = {"lineage_anchor": anchor, "pid": pid if row_pid is None else row_pid} if seen else None
    rows_before = 0 if before else 1
    return grade.restart_row_side(
        pid=pid,
        errno=errno,
        row=row,
        wait_s=wait_s,
        row_count=(rows_before + 1 if seen else rows_before) if count is None else count,
        rows_before=rows_before,
        expected_anchor=None if before else ANCHOR,
        probe_at="2026-10-22T22:58:01.125Z",
        seen_at="2026-10-22T22:58:08.375Z" if seen else None,
        ledger_ts="2026-10-22T22:58:08.250Z" if seen else None,
    )


def _sample(pid: int) -> dict:
    return {
        "deny_event": {"lineage_anchor": ANCHOR, "path": od.CEILING_PATH, "pid": pid},
        "file_errno": 13,
        "lineage_anchor": ANCHOR,
        "path": od.CEILING_PATH,
        "pid": pid,
    }


def _restart(after: dict, *, before: dict | None = None, held: bool = True, reason=None) -> dict:
    before = before or _side(before=True)
    warnings = [f"late_deny_row_{phase}_restart" for phase, side in (("before", before), ("after", after))
                if side["row_seen"] and side["wait_s"] > 0.5]
    return {
        "held": held,
        "reason": reason,
        "pid": PID,
        "before_errno": before["errno"],
        "before_row_seen": before["row_seen"],
        "before_row_wait_s": before["wait_s"],
        "after_errno": after["errno"],
        "after_row_seen": after["row_seen"],
        "after_row_wait_s": after["wait_s"],
        "restart_rows": {"before": before, "after": after, "cap_s": 15.0, "late_s": 5.0},
        "warnings": warnings,
    }


def _body(restart: dict) -> dict:
    """A 2D body that holds on every other check, so only the restart rows decide."""
    return {
        "enroll_restart": restart,
        "enrolled_after": _sample(3370),
        "unenrolled_after": {"file_errno": 0, "path": od.CEILING_PATH, "pid": 3371},
        "while_loader_up": _sample(3359),
    }


def _capture(restart: dict, word: str) -> dict:
    return od._allow_capture(od._loader_capture("loader-kill", {"body": _body(restart), "rc": 0, "word": word}))


class RestartRowGradeTest(unittest.TestCase):
    def test_on_time_row_passes_without_late_s(self) -> None:
        side = _side(wait_s=0.25)
        self.assertIs(side["pass"], True)
        self.assertIsNone(side["cause"])
        self.assertNotIn("late_s", side)
        self.assertEqual(od._loader_word("2d-crash-recovery", _body(_restart(side))), "held")
        kept = _capture(_restart(side), "held")
        self.assertNotIn("late_s", kept)
        self.assertNotIn("claim_scope", kept)
        self.assertIsNone(od.restart_rows_late_s(kept["restart_rows"]))

    def test_late_within_15s_passes_with_the_warning_and_seconds(self) -> None:
        side = _side(wait_s=7.25)
        self.assertIs(side["pass"], True)
        self.assertEqual(side["late_s"], 7.25)
        restart = _restart(side)
        self.assertEqual(od._loader_word("2d-crash-recovery", _body(restart)), "held")
        kept = _capture(restart, "held")
        self.assertIs(kept["hold"], True)
        self.assertIn("late_deny_row_after_restart", kept["warnings"])
        # The host derives lateness from wait_s, not from the guest's late_s.
        self.assertNotIn("late_s", kept["restart_rows"]["after"])
        self.assertEqual(kept["late_s"], 7.25)
        self.assertEqual(kept["claim_scope"], od.LATE_CLAIM_SCOPE)
        self.assertEqual(kept["restart_rows"]["after"]["wait_s"], 7.25)
        self.assertNotIn("fail_reasons", kept)
        # The edges: exactly 5 s is not late, exactly 15 s still counts.
        self.assertNotIn("late_s", _side(wait_s=5.0))
        self.assertEqual(_side(wait_s=5.001)["late_s"], 5.001)
        self.assertIs(_side(wait_s=15.0)["pass"], True)

    def test_absent_row_fails_as_row_absent_errno13(self) -> None:
        side = _side(wait_s=15.0, seen=False)
        self.assertEqual(side["cause"], "row_absent_errno13")
        self.assertIs(side["pass"], False)
        self.assertNotIn("late_s", side)
        restart = _restart(side, held=False, reason="row_absent_errno13")
        self.assertEqual(od._loader_word("2d-crash-recovery", _body(restart)), "fail")
        kept = _capture(restart, "fail")
        self.assertIs(kept["hold"], False)
        self.assertIn("row_absent_errno13", kept["fail_reasons"])
        self.assertNotIn("late_deny_row_after_restart", kept.get("warnings", []))
        self.assertIs(kept["restart_rows"]["after"]["row_seen"], False)
        self.assertEqual(kept["restart_rows"]["after"]["errno"], 13)

    def test_row_past_the_cap_or_not_new_fails_under_its_own_name(self) -> None:
        # A row found only after the 15 s cap is row_past_cap, not row_absent_errno13.
        self.assertEqual(_side(wait_s=15.25)["cause"], "row_past_cap")
        self.assertEqual(od.restart_row_cause(od.allow_restart_side(_side(wait_s=15.25))), "row_past_cap")
        self.assertEqual(od._loader_word("2d-crash-recovery", _body(_restart(_side(wait_s=15.25)))), "fail")
        # Only the old pre-restart row: same pid, no new row past it.
        self.assertEqual(_side(count=1)["cause"], "row_not_new")
        for wait in (-0.25, float("nan"), float("inf"), True, "7.0", None):
            with self.subTest(wait=wait):
                self.assertEqual(_side(wait_s=wait)["cause"], "row_absent_errno13")

    def test_non_13_errno_fails(self) -> None:
        for errno in (1, 2, 110, 4095):
            with self.subTest(errno=errno):
                side = _side(errno=errno)
                self.assertEqual(side["cause"], "errno_not_13")
                body = _body(_restart(side, held=True))
                self.assertEqual(od._loader_word("2d-crash-recovery", body), "fail")

    def test_not_blocked_fails_as_not_blocked_and_is_never_softened(self) -> None:
        # A row in the ledger does not rescue a fail-open, and neither does the guest saying held.
        side = _side(errno=0)
        self.assertEqual(side["cause"], "not_blocked")
        forged = dict(side, cause=None, **{"pass": True})
        restart = _restart(forged, held=True)
        self.assertEqual(od._loader_word("2d-crash-recovery", _body(restart)), "fail")
        kept = _capture(restart, "fail")
        self.assertIn("not_blocked", kept["fail_reasons"])
        self.assertEqual(od.restart_rows_cause(kept["restart_rows"]), "not_blocked")
        absent = _side(errno=0, seen=False, wait_s=0.0)
        self.assertEqual(absent["cause"], "not_blocked")

    def test_bool_str_float_errno_is_rejected(self) -> None:
        for errno in (True, False, "13", 13.0, None, [13]):
            with self.subTest(errno=errno):
                side = _side(errno=errno)
                self.assertEqual(side["cause"], "errno_invalid")
                forged = dict(_side(), errno=errno)
                self.assertEqual(grade.restart_row_cause(forged), "errno_invalid")
                # The host grade rejects it on its own, not only through the sanitiser.
                self.assertEqual(od.restart_row_cause(forged), "errno_invalid")
                kept = od.allow_restart_side(forged)
                self.assertNotIn("errno", kept)
                self.assertEqual(od.restart_row_cause(kept), "errno_invalid")
                body = _body(_restart(forged, held=True))
                self.assertEqual(od._loader_word("2d-crash-recovery", body), "fail")

    def test_pid_and_anchor_must_match(self) -> None:
        self.assertEqual(_side(row_pid=9999)["cause"], "pid_mismatch")
        self.assertEqual(_side(anchor=7110)["cause"], "anchor_not_carried")
        for side in (_side(row_pid=9999), _side(anchor=7110)):
            self.assertEqual(od.restart_row_cause(od.allow_restart_side(side)), side["cause"])
            self.assertEqual(od._loader_word("2d-crash-recovery", _body(_restart(side))), "fail")
        self.assertEqual(_side(anchor=0)["cause"], "anchor_not_carried")
        # Before the restart any positive anchor is the one to carry.
        self.assertIs(_side(before=True, anchor=7110)["pass"], True)

    def test_before_side_has_the_same_fields_and_fails_under_its_own_name(self) -> None:
        self.assertEqual(set(_side(before=True)), set(_side()))
        before = _side(before=True, seen=False, wait_s=15.0)
        self.assertEqual(before["cause"], "row_absent_errno13")
        rows = od.allow_restart_rows({"before": before, "after": _side()})
        self.assertEqual(od.restart_rows_cause(rows), "row_absent_errno13_before_restart")
        restart = _restart(_side(), before=before, held=True)
        self.assertEqual(od._loader_word("2d-crash-recovery", _body(restart)), "fail")
        late = _side(before=True, wait_s=9.5)
        self.assertEqual(late["late_s"], 9.5)
        self.assertEqual(od._loader_word("2d-crash-recovery", _body(_restart(_side(), before=late))), "held")
        # A late before-restart row also marks the hold as not prompt.
        kept = _capture(_restart(_side(), before=late), "held")
        self.assertEqual((kept["late_s"], kept["claim_scope"]), (9.5, od.LATE_CLAIM_SCOPE))
        past = _side(before=True, wait_s=15.25)
        rows = od.allow_restart_rows({"before": past, "after": _side()})
        self.assertEqual(od.restart_rows_cause(rows), "row_past_cap_before_restart")

    def test_missing_side_or_guest_not_held_fails(self) -> None:
        restart = _restart(_side())
        del restart["restart_rows"]["after"]
        self.assertEqual(od._loader_word("2d-crash-recovery", _body(restart)), "fail")
        self.assertEqual(od._loader_word("2d-crash-recovery", _body(_restart(_side(), held=False))), "fail")
        self.assertEqual(od._loader_word("2d-crash-recovery", _body(dict(_restart(_side()), held="true"))), "fail")
        self.assertEqual(od.restart_rows_cause(restart["restart_rows"]), "restart_rows_missing")
        self.assertEqual(od.restart_rows_cause({}), "restart_rows_missing")
        # GCP 2D requires restart_rows: without them it fails as restart_rows_missing.
        old = _restart(_side())
        del old["restart_rows"]
        self.assertEqual(od._loader_word("2d-crash-recovery", _body(old)), "fail")
        no_restart = _body(old)
        del no_restart["enroll_restart"]
        self.assertEqual(od._loader_word("2d-crash-recovery", no_restart), "fail")
        for body in (_body(old), no_restart):
            kept = od._allow_capture(od._loader_capture("loader-kill", {"body": body, "rc": 0, "word": "fail"}))
            self.assertIn("restart_rows_missing", kept["fail_reasons"])
        # 2C (loader-restart) has no restart rows and is not asked for them.
        kept = od._loader_capture("loader-restart", {"body": {}, "rc": 0, "word": "fail"})
        self.assertNotIn("restart_rows_missing", kept.get("fail_reasons", []))

    def test_host_and_guest_grades_agree(self) -> None:
        self.assertEqual(od.RESTART_ROW_CAP_S, grade.RESTART_ROW_CAP_S)
        self.assertEqual(od.RESTART_ROW_LATE_S, grade.RESTART_ROW_LATE_S)
        self.assertEqual(od.RESTART_ROW_CAUSES, grade.RESTART_ROW_CAUSES)
        cases = [
            _side(errno=errno, wait_s=wait, seen=seen, anchor=anchor)
            for errno in (0, 1, 13)
            for wait in (0.0, 5.0, 7.25, 15.0, 15.25)
            for seen in (True, False)
            for anchor in (ANCHOR, 7110)
        ] + [_side(count=1), _side(row_pid=9999), _side(pid=0, row_pid=0), _side(anchor=0)]
        for side in cases:
            with self.subTest(side=side):
                self.assertEqual(od.restart_row_cause(od.allow_restart_side(side)), side["cause"])
                self.assertIn(side["cause"], {None, *grade.RESTART_ROW_CAUSES})


def _forged(**changes) -> dict:
    """A kept after side whose guest booleans all claim a pass, with some integers changed."""
    side = od.allow_restart_side(_side())
    for key in ("new_row", "pid_match", "anchor_match", "row_seen", "pass"):
        side[key] = True
    side.update(changes)
    return side


class HostRecomputeTest(unittest.TestCase):
    """The host recomputes pid_match, anchor_match and new_row from the kept integers."""

    def _word(self, after: dict, before: dict | None = None) -> str:
        rows = {"before": before or od.allow_restart_side(_side(before=True)), "after": after}
        return od._loader_word("2d-crash-recovery", _body(dict(_restart(_side()), restart_rows=rows)))

    def test_consistent_side_holds(self) -> None:
        self.assertIsNone(od.restart_row_cause(_forged()))
        self.assertEqual(self._word(_forged()), "held")

    def test_pid_must_equal_row_pid_and_be_positive(self) -> None:
        for changes in ({"row_pid": 9999}, {"pid": 0, "row_pid": 0}, {"row_pid": 0}):
            with self.subTest(changes=changes):
                self.assertEqual(od.restart_row_cause(_forged(**changes)), "pid_mismatch")
                self.assertEqual(self._word(_forged(**changes)), "fail")
        side = _forged()
        del side["row_pid"]
        self.assertEqual(od.restart_row_cause(side), "pid_mismatch")

    def test_anchor_must_equal_expected_and_be_positive(self) -> None:
        for changes in ({"anchor": 7110}, {"expected_anchor": 7110}, {"anchor": 0, "expected_anchor": 0}):
            with self.subTest(changes=changes):
                self.assertEqual(od.restart_row_cause(_forged(**changes)), "anchor_not_carried")
                self.assertEqual(self._word(_forged(**changes)), "fail")

    def test_row_seen_but_not_new_fails(self) -> None:
        for changes in ({"row_count": 1, "rows_before": 1}, {"row_count": 0, "rows_before": 1}):
            with self.subTest(changes=changes):
                self.assertEqual(od.restart_row_cause(_forged(**changes)), "row_not_new")
                self.assertEqual(self._word(_forged(**changes)), "fail")
        side = _forged()
        del side["rows_before"]
        self.assertEqual(od.restart_row_cause(side), "row_not_new")

    def test_after_expected_anchor_must_be_the_before_anchor(self) -> None:
        before = od.allow_restart_side(_side(before=True, anchor=7110))
        self.assertIsNone(od.restart_row_cause(before))
        self.assertIsNone(od.restart_row_cause(_forged()))
        rows = {"before": before, "after": _forged()}
        self.assertEqual(od.restart_rows_cause(rows), "anchor_not_carried")
        self.assertEqual(self._word(_forged(), before), "fail")
        missing = _forged()
        del missing["expected_anchor"]
        self.assertEqual(od.restart_rows_cause({"before": od.allow_restart_side(_side(before=True)),
                                                "after": missing}), "anchor_not_carried")

    def test_a_guest_boolean_that_disagrees_fails(self) -> None:
        for key in ("new_row", "pid_match", "anchor_match"):
            with self.subTest(key=key):
                self.assertEqual(od.restart_row_cause(_forged(**{key: False})), "guest_flag_mismatch")
                self.assertEqual(self._word(_forged(**{key: False})), "fail")
                self.assertEqual(grade.restart_row_cause(_forged(**{key: False})), "guest_flag_mismatch")

    def test_bad_wait_is_absent_on_the_host_itself(self) -> None:
        # Checked on the raw side, not only through the sanitiser.
        for wait in (float("nan"), float("inf"), -0.25, True, "7.0", None):
            with self.subTest(wait=wait):
                self.assertEqual(od.restart_row_cause(_forged(wait_s=wait)), "row_absent_errno13")
        self.assertEqual(od.restart_row_cause(_forged(wait_s=15.25)), "row_past_cap")

    def test_host_lateness_edges(self) -> None:
        before = od.allow_restart_side(_side(before=True))
        for wait, want in ((5.0, None), (5.001, 5.001), (15.0, 15.0), (15.25, None)):
            with self.subTest(wait=wait):
                self.assertEqual(od.restart_rows_late_s({"before": before, "after": _forged(wait_s=wait)}), want)

    def test_ledger_latency_is_evidence_only(self) -> None:
        self.assertEqual(od.allow_restart_side(_side())["ledger_latency_s"], 7.125)
        self.assertNotIn("ledger_latency_s", od.allow_restart_side(_side(seen=False)))
        cases = {
            ("2026-10-22T22:58:01.125Z", "2026-10-22T18:58:03.500-04:00"): 2.375,
            ("2026-10-22T22:58:01Z", "2026-10-22 22:58:02.5"): 1.5,
            ("1792709881.25", "1792709882750000000"): 1.5,
            ("2026-10-22T22:58:01Z", "garbage"): None,
            ("2026-10-22T22:58:01Z", "2026-10-25T22:58:01Z"): None,
        }
        for (probe, ledger), want in cases.items():
            with self.subTest(probe=probe, ledger=ledger):
                self.assertEqual(od.ledger_latency_s({"probe_at": probe, "ledger_ts": ledger}), want)
        # It never changes the grade.
        slow = dict(_forged(), ledger_latency_s=99.0)
        self.assertIsNone(od.restart_row_cause(slow))


class RestartRowsReachTheRowsTest(unittest.TestCase):
    def test_capture_sanitises_the_evidence(self) -> None:
        side = dict(
            _side(wait_s=7.25),
            probe_at="2026-10-22T22:58:01Z; rm -rf /",
            ledger_ts="x" * 41,
            token="ghp_" + "a" * 30,
            row_count=True,
            cause="made_up",
        )
        kept = od.allow_restart_side(side)
        for key in ("probe_at", "ledger_ts", "token", "row_count", "cause"):
            self.assertNotIn(key, kept)
        self.assertEqual(kept["seen_at"], "2026-10-22T22:58:08.375Z")
        self.assertEqual(kept["anchor"], ANCHOR)
        self.assertEqual(od.allow_restart_rows("junk"), {})
        self.assertEqual(od.allow_restart_rows({"other": side}), {})

    def test_allow_record_keeps_the_restart_rows(self) -> None:
        rows = {"before": _side(before=True), "after": _side(wait_s=7.25), "secret": "x"}
        kept = od.allow_record({"loader_kill_restart_rows": rows})
        self.assertEqual(set(kept["loader_kill_restart_rows"]), {"before", "after"})
        self.assertEqual(kept["loader_kill_restart_rows"]["after"]["errno"], 13)
        self.assertNotIn("late_s", kept["loader_kill_restart_rows"]["after"])
        self.assertEqual(kept["loader_kill_restart_rows"]["before"]["row_count"], 1)
        fields = od.kill_late_fields(od.allow_restart_rows(rows))
        self.assertEqual(fields, {"loader_kill_late_s": 7.25, "loader_kill_claim_scope": od.LATE_CLAIM_SCOPE})
        self.assertEqual(od.allow_record(fields), fields)
        self.assertEqual(od.allow_record({"loader_kill_late_s": None}), {"loader_kill_late_s": None})
        forged = od.allow_record({"loader_kill_late_s": True, "loader_kill_claim_scope": "prompt"})
        self.assertNotIn("loader_kill_late_s", forged)
        self.assertNotIn("loader_kill_claim_scope", forged)
        self.assertEqual(od.kill_late_fields({"before": _side(before=True), "after": _side()}),
                         {"loader_kill_late_s": None})

    def _write_rows(self, kill_body: dict) -> dict:
        """Drive od.run_batteries with every cloud call stubbed and return gcp-lab-rows.json."""
        repeat = {"b1_pass": True, "deny_hold": True, "deny_pid": 41, "desc_deny_pid": 42, "lineage_anchor": 7}

        def loader_case(_project: str, _name: str, _seal: str, mode: str) -> dict:
            if mode == "2d-crash-recovery":
                return {"body": kill_body, "rc": 0, "word": od._loader_word(mode, kill_body)}
            return {"body": {}, "rc": 0, "word": "held"}

        ok = subprocess.CompletedProcess([], 0, stdout="UNINSTALL_VERIFIED\n", stderr="")

        def ssh(_p, _n, command, timeout_s=None):
            if "host_evidence_hu.py" in command:
                return subprocess.CompletedProcess([], 0, stdout=HU_PASS, stderr="")
            return ok

        with tempfile.TemporaryDirectory() as tmp:
            evidence = Path(tmp) / "evidence"
            stubs = {
                "_enabled": mock.DEFAULT,
                "require_lab_project": mock.Mock(return_value="vantio-lab-test"),
                "_gate_ok": mock.DEFAULT,
                "batteries_requested": mock.Mock(return_value=True),
                "instance_name": mock.Mock(return_value="vantio-gcp-lab-1"),
                "refuse_batteries": mock.Mock(return_value="a" * 64),
                "_evidence_dir": mock.Mock(return_value=evidence),
                "_stage_payload": mock.Mock(return_value=[]),
                "_wait_until_running": mock.DEFAULT,
                "_ssh": mock.Mock(side_effect=ssh),
                "_scp_to": mock.DEFAULT,
                "_prepare_lab_lsm": mock.Mock(return_value={}),
                "_wait_live_boot": mock.Mock(return_value="boot-2"),
                "_run_one_battery": mock.Mock(return_value=repeat),
                "full_set_passes": mock.Mock(return_value=True),
                "_loader_case": mock.Mock(side_effect=loader_case),
                # 2E-2G are test_gcp_phase_batteries.py. Stub them out here.
                "run_phase_batteries": mock.Mock(return_value=[]),
                "phases_pass": mock.Mock(return_value=True),
                "drop_guest_copies": mock.DEFAULT,
                "remove_os_login_key": mock.DEFAULT,
            }
            with mock.patch.multiple(od, **stubs), contextlib.redirect_stdout(io.StringIO()):
                with contextlib.suppress(SystemExit):
                    od.run_batteries({"RUNNER_TEMP": tmp, "STOP_AFTER_MINUTES": "105"})
            rows = json.loads((evidence / "gcp-lab-rows.json").read_text(encoding="utf-8"))
            guest = json.loads((evidence / "guest-evidence.json").read_text(encoding="utf-8"))
            return rows, guest

    def test_rows_writer_carries_the_after_restart_evidence(self) -> None:
        absent = _side(wait_s=15.0, seen=False)
        rows, guest = self._write_rows(_body(_restart(absent, held=False, reason="row_absent_errno13")))
        self.assertEqual(rows["loader_kill"], "fail")
        after = rows["loader_kill_restart_rows"]["after"]
        self.assertEqual(after["errno"], 13)
        self.assertIs(after["row_seen"], False)
        self.assertEqual(after["wait_s"], 15.0)
        self.assertEqual(after["cause"], "row_absent_errno13")
        self.assertEqual(rows["loader_kill_restart_rows"]["before"]["wait_s"], 0.25)
        kill = next(item for item in guest["captures"] if item["name"] == "loader-kill")
        self.assertIn("row_absent_errno13", kill["fail_reasons"])
        self.assertEqual(kill["restart_rows"]["after"]["row_count"], 1)
        self.assertEqual(kill["before_row_wait_s"], 0.25)
        self.assertEqual(kill["after_row_wait_s"], 15.0)
        self.assertIsNone(rows["loader_kill_late_s"])
        self.assertNotIn("loader_kill_claim_scope", rows)
        self.assertEqual(after["ledger_latency_s"] if "ledger_latency_s" in after else None, None)
        self.assertEqual(rows["loader_kill_restart_rows"]["before"]["ledger_latency_s"], 7.125)
        late, _ = self._write_rows(_body(_restart(_side(wait_s=7.25))))
        self.assertEqual(late["loader_kill"], "held")
        self.assertEqual(late["loader_kill_late_s"], 7.25)
        self.assertEqual(late["loader_kill_claim_scope"], od.LATE_CLAIM_SCOPE)
        self.assertNotIn("late_s", late["loader_kill_restart_rows"]["after"])
        prompt, _ = self._write_rows(_body(_restart(_side())))
        self.assertEqual(prompt["loader_kill"], "held")
        self.assertIsNone(prompt["loader_kill_late_s"])
        self.assertNotIn("loader_kill_claim_scope", prompt)
        empty, _ = self._write_rows({})
        self.assertEqual(empty["loader_kill_restart_rows"], {})


class GuestWaitTest(unittest.TestCase):
    """The real phase2_host wait helpers over a fake ledger and clock."""

    def _host(self, row_at: float | None):
        text = (GUESTS / "phase2_host.py").read_text(encoding="utf-8")
        source = text[text.index("def _deny_rows"): text.index("def _banner_ready")]
        clock = {"now": 100.0}

        class FakeTime:
            @staticmethod
            def monotonic() -> float:
                return clock["now"]

            @staticmethod
            def sleep(seconds: float) -> None:
                clock["now"] += seconds

        old = {"Pid": PID, "ActionTaken": "DENIED", "PathAttempted": DENY, "lineage_anchor": ANCHOR, "Uid": 65534}

        def events() -> list:
            found = [dict(old, Timestamp="2026-10-22T22:58:00.000Z")]
            if row_at is not None and clock["now"] - 100.0 >= row_at:
                found.append(dict(old, Timestamp="2026-10-22T22:58:08.250Z"))
            return found

        ns = {
            "time": FakeTime,
            "events": events,
            "os": os,
            "grade": grade,
            "rows": types.SimpleNamespace(DENY=Path(DENY)),
            "sys": types.SimpleNamespace(stderr=io.StringIO()),
        }
        exec(compile("from __future__ import annotations\n" + source, str(GUESTS / "phase2_host.py"), "exec"), ns)
        return ns

    def test_timeout_is_15s_only_on_gcp(self) -> None:
        ns = self._host(None)
        with mock.patch.dict(os.environ, {"VANTIO_LAB_CLOUD": "gcp"}):
            self.assertEqual(ns["restart_row_timeout"](), 15.0)
        for value in (None, "aws", "GCP", ""):
            env = {} if value is None else {"VANTIO_LAB_CLOUD": value}
            with self.subTest(value=value), mock.patch.dict(os.environ, env, clear=True):
                self.assertEqual(ns["restart_row_timeout"](), ns["DENY_ROW_WAIT_S"])
                self.assertEqual(ns["DENY_ROW_WAIT_S"], 5.0)

    def test_a_7s_row_is_seen_in_15s_and_missed_in_5s(self) -> None:
        ns = self._host(7.0)
        row, waited, count = ns["wait_new_deny_event"](PID, 1, poll=True, timeout=15.0)
        self.assertEqual((row["lineage_anchor"], waited, count), (ANCHOR, 7.0, 2))
        ns = self._host(7.0)
        row, waited, count = ns["wait_new_deny_event"](PID, 1, poll=True)
        self.assertIsNone(row)
        self.assertGreaterEqual(waited, 5.0)
        self.assertEqual(count, 1)

    def test_no_row_stops_at_15s(self) -> None:
        ns = self._host(None)
        row, waited, count = ns["wait_new_deny_event"](PID, 1, poll=True, timeout=15.0)
        self.assertIsNone(row)
        self.assertEqual(waited, 15.0)
        self.assertEqual(count, 1)

    def test_ledger_time_is_read_only_for_restart_rows(self) -> None:
        ns = self._host(0.0)
        self.assertNotIn("ledger_ts", ns["_deny_rows"](PID)[0])
        self.assertEqual(ns["_ledger_ts"](PID, 1), "2026-10-22T22:58:08.250Z")
        self.assertIsNone(ns["_ledger_ts"](PID, 2))
        self.assertIsNone(ns["_ledger_ts"](PID, -1))


class WiringTest(unittest.TestCase):
    def test_only_the_gcp_guest_script_sets_the_flag(self) -> None:
        gcp = (ROOT / "scripts/gcp/lab-guests/enterprise-rows.sh").read_text(encoding="utf-8")
        line = next(item for item in gcp.splitlines() if 'python3 "$here/phase2_host.py"' in item)
        self.assertIn("sudo env VANTIO_LAB_CLOUD=gcp ", line)
        aws = (ROOT / "scripts/aws/lab-guests/enterprise-rows.sh").read_text(encoding="utf-8")
        self.assertNotIn("VANTIO_LAB_CLOUD", aws)

    def test_guest_gcp_grade_only_takes_a_hold_away(self) -> None:
        text = (GUESTS / "phase2_host.py").read_text(encoding="utf-8")
        body = text.split("def same_process_across_restart", 1)[1].split("\ndef ", 1)[0]
        gcp = body[body.index("        if gcp:\n            after_side"):]
        self.assertIn('body["held"] = False', gcp)
        self.assertNotIn('body["held"] = True', body)
        self.assertIn("timeout=restart_row_timeout()", body)
        self.assertIn("row_wait(pid, errno_before, restart_row_timeout())", body)


LAB_DENY = "/var/lib/vantio-pe-clean-host/d/secret"


def _no_ledger_time(*, before=False, seen=True, wait_s=2.965, map_rows=None, map_rows_before=None):
    """A side the way PE da961aa rows really arrive: the row has no time field."""
    rows_before = 0 if before else 1
    return grade.restart_row_side(
        pid=PID,
        errno=13,
        row={"lineage_anchor": ANCHOR, "pid": PID} if seen else None,
        wait_s=wait_s if seen else 15.03,
        row_count=rows_before + 1 if seen else rows_before,
        rows_before=rows_before,
        expected_anchor=None if before else ANCHOR,
        probe_at="2026-10-23T00:19:24.225Z",
        seen_at="2026-10-23T00:19:27.190Z" if seen else None,
        ledger_ts=None,
        map_rows=map_rows,
        map_rows_before=map_rows_before,
    )


class LedgerTimeSourceTest(unittest.TestCase):
    """Run 6 had no ledger_latency_s: PE ledger rows carry no time field.

    PE ledger_row and deny_ledger::post_kill_line (engine da961aa) write no
    Timestamp key. The guest labels the row time host_seen_at, and the host
    computes ledger_latency_s from seen_at with that label.
    """

    def test_guest_labels_the_row_time_source(self) -> None:
        self.assertEqual(_no_ledger_time()["ledger_ts_source"], grade.LEDGER_TS_HOST_SEEN)
        self.assertEqual(_side()["ledger_ts_source"], grade.LEDGER_TS_FROM_ROW)
        self.assertNotIn("ledger_ts_source", _no_ledger_time(seen=False))
        self.assertNotIn("ledger_ts_source", _side(seen=False))

    def test_run6_shape_gets_a_latency_on_both_sides(self) -> None:
        for before in (True, False):
            with self.subTest(before=before):
                kept = od.allow_restart_side(_no_ledger_time(before=before))
                self.assertEqual(kept["ledger_latency_s"], 2.965)
                self.assertEqual(kept["ledger_latency_source"], od.LEDGER_TS_HOST_SEEN)
                self.assertEqual(kept["ledger_ts_source"], od.LEDGER_TS_HOST_SEEN)
                self.assertNotIn("ledger_ts", kept)
        rows = od.allow_record(
            {"loader_kill_restart_rows": {"before": _no_ledger_time(before=True), "after": _no_ledger_time()}}
        )["loader_kill_restart_rows"]
        for name in ("before", "after"):
            self.assertEqual(rows[name]["ledger_latency_source"], "host_seen_at")
            self.assertEqual(rows[name]["ledger_latency_s"], 2.965)

    def test_a_row_time_wins_over_seen_at(self) -> None:
        kept = od.allow_restart_side(_side())
        self.assertEqual((kept["ledger_latency_s"], kept["ledger_latency_source"]), (7.125, "ledger_row"))
        self.assertEqual(
            od.ledger_latency({"probe_at": "2026-10-22T22:58:01Z", "ledger_ts": "bad", "seen_at": "2026-10-22T22:58:03Z"}),
            (2.0, "host_seen_at"),
        )
        self.assertEqual(od.ledger_latency({"seen_at": "2026-10-22T22:58:03Z"}), (None, None))

    def test_no_row_has_no_latency_even_with_a_forged_time(self) -> None:
        forged = dict(_no_ledger_time(seen=False), seen_at="2026-10-23T00:19:30.000Z", ledger_ts_source="host_seen_at")
        kept = od.allow_restart_side(forged)
        self.assertNotIn("ledger_latency_s", kept)
        self.assertNotIn("ledger_latency_source", kept)
        self.assertEqual(kept["cause"], "row_absent_errno13")

    def test_source_and_map_rows_are_allow_listed(self) -> None:
        side = dict(_no_ledger_time(), ledger_ts_source="ledger_row; x", map_rows=True, ledger_latency_source="made_up")
        kept = od.allow_restart_side(side)
        self.assertEqual(kept["ledger_ts_source"], "host_seen_at")
        self.assertNotIn("map_rows", kept)
        self.assertEqual(kept["ledger_latency_source"], "host_seen_at")
        self.assertEqual(od.allow_restart_side(_no_ledger_time(map_rows=2))["map_rows"], 2)
        self.assertNotIn("map_rows", _no_ledger_time(map_rows=-1))

    def test_host_sets_the_source_from_what_it_kept(self) -> None:
        # The guest says ledger_row, but its ledger_ts is garbage or missing.
        for ledger_ts in ("garbage", "x" * 41, None, 12.5):
            with self.subTest(ledger_ts=ledger_ts):
                side = dict(_no_ledger_time(), ledger_ts_source="ledger_row", ledger_ts=ledger_ts)
                kept = od.allow_restart_side(side)
                self.assertEqual(kept["ledger_ts_source"], "host_seen_at")
                self.assertEqual(kept["ledger_latency_source"], "host_seen_at")
                self.assertEqual(kept["ledger_latency_s"], 2.965)
        # The guest says host_seen_at, but the host kept a ledger_ts that parses.
        kept = od.allow_restart_side(dict(_side(), ledger_ts_source="host_seen_at"))
        self.assertEqual((kept["ledger_ts_source"], kept["ledger_latency_source"]), ("ledger_row", "ledger_row"))
        # No row: no source, whatever the guest says.
        kept = od.allow_restart_side(dict(_no_ledger_time(seen=False), ledger_ts_source="ledger_row"))
        self.assertNotIn("ledger_ts_source", kept)

    def test_after_side_map_rows_split_before_and_new(self) -> None:
        after = _no_ledger_time(map_rows=5, map_rows_before=2)
        self.assertEqual((after["map_rows"], after["map_rows_before"], after["map_rows_after_new"]), (5, 2, 3))
        self.assertEqual(_no_ledger_time(map_rows=1, map_rows_before=4)["map_rows_after_new"], 0)
        before = _no_ledger_time(before=True, map_rows=2)
        self.assertNotIn("map_rows_before", before)
        self.assertNotIn("map_rows_after_new", before)
        for bad in (None, -1, True, "2"):
            with self.subTest(bad=bad):
                self.assertNotIn("map_rows_after_new", _no_ledger_time(map_rows=5, map_rows_before=bad))
        # The host derives the after-restart share itself.
        kept = od.allow_restart_side(dict(after, map_rows_after_new=99))
        self.assertEqual(kept["map_rows_after_new"], 3)
        kept = od.allow_restart_side(dict(after, map_rows_before=7))
        self.assertEqual(kept["map_rows_after_new"], 0)
        kept = od.allow_restart_side(dict(after, map_rows_before=True))
        self.assertNotIn("map_rows_after_new", kept)
        self.assertNotIn("map_rows_before", kept)
        # Evidence only.
        self.assertIsNone(od.restart_row_cause(kept))
        missing = od.allow_restart_side(_no_ledger_time(seen=False, map_rows=5, map_rows_before=2))
        self.assertEqual(missing["map_rows_after_new"], 3)
        self.assertEqual(od.restart_row_cause(missing), "row_absent_errno13")

    def test_latency_and_map_rows_never_change_the_grade(self) -> None:
        # Guest map_rows cannot rescue the guest's own cause.
        self.assertEqual(_no_ledger_time(seen=False, map_rows=3)["cause"], "row_absent_errno13")
        self.assertFalse(_no_ledger_time(seen=False, map_rows=3)["pass"])
        missing = od.allow_restart_side(_no_ledger_time(seen=False, map_rows=3))
        self.assertEqual(missing["map_rows"], 3)
        self.assertEqual(od.restart_row_cause(missing), "row_absent_errno13")
        self.assertEqual(grade.restart_row_cause(_no_ledger_time(seen=False, map_rows=3)), "row_absent_errno13")
        self.assertIsNone(od.restart_row_cause(od.allow_restart_side(_no_ledger_time(map_rows=0))))


class MapRowCountTest(unittest.TestCase):
    """Rows drained from the deny-attr map carry the path cut to 32 bytes.

    The lab path is 38 bytes, so _deny_rows never counts those rows.
    _map_row_count records them as evidence only.
    """

    def _ns(self, found: list, deny: str = LAB_DENY) -> dict:
        text = (GUESTS / "phase2_host.py").read_text(encoding="utf-8")
        source = text[text.index("def _deny_rows"): text.index("def _banner_ready")]
        ns = {
            "time": types.SimpleNamespace(monotonic=lambda: 0.0, sleep=lambda _s: None, time=lambda: 0.0),
            "events": lambda: [dict(item) for item in found],
            "os": os,
            "grade": grade,
            "rows": types.SimpleNamespace(DENY=Path(deny)),
            "sys": types.SimpleNamespace(stderr=io.StringIO()),
        }
        exec(compile("from __future__ import annotations\n" + source, str(GUESTS / "phase2_host.py"), "exec"), ns)
        return ns

    def test_cut_rows_are_counted_here_and_not_as_deny_rows(self) -> None:
        cut = LAB_DENY[: grade.DENY_PATH_KEY_LEN]
        self.assertEqual(cut, "/var/lib/vantio-pe-clean-host/d/")
        base = {"Pid": PID, "ActionTaken": "DENIED", "lineage_anchor": ANCHOR}
        found = [
            dict(base, Payload=LAB_DENY),
            dict(base, Payload=cut, source="deny_attr_post_kill"),
            dict(base, Payload=cut),
            dict(base, Payload=cut, Pid=PID + 1),
            dict(base, Payload=cut, ActionTaken="BLOCKED"),
            dict(base, Payload="/var/lib/vantio-pe-clean-host/"),
        ]
        ns = self._ns(found)
        self.assertEqual(len(ns["_deny_rows"](PID)), 1)
        self.assertEqual(ns["_map_row_count"](PID), 2)
        self.assertEqual(ns["_map_row_count"](PID + 2), 0)

    def test_a_short_path_has_no_cut_rows(self) -> None:
        ns = self._ns([{"Pid": PID, "ActionTaken": "DENIED", "Payload": DENY, "lineage_anchor": ANCHOR}], deny=DENY)
        self.assertLessEqual(len(DENY.encode()), grade.DENY_PATH_KEY_LEN)
        self.assertEqual(ns["_map_row_count"](PID), 0)

    def test_guest_records_map_rows_on_both_sides(self) -> None:
        text = (GUESTS / "phase2_host.py").read_text(encoding="utf-8")
        body = text.split("def same_process_across_restart", 1)[1].split("\ndef ", 1)[0]
        self.assertEqual(body.count("map_rows_before = _map_row_count(pid)"), 1)
        self.assertEqual(body.count("map_rows=map_rows_before,"), 1)
        self.assertEqual(body.count("map_rows=_map_row_count(pid),\n                map_rows_before=map_rows_before,"), 1)


if __name__ == "__main__":
    unittest.main()
