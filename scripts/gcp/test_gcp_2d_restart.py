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

import offline_deliver as od

ROOT = Path(__file__).resolve().parents[2]
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

    def test_late_within_15s_passes_with_the_warning_and_seconds(self) -> None:
        side = _side(wait_s=7.25)
        self.assertIs(side["pass"], True)
        self.assertEqual(side["late_s"], 7.25)
        restart = _restart(side)
        self.assertEqual(od._loader_word("2d-crash-recovery", _body(restart)), "held")
        kept = _capture(restart, "held")
        self.assertIs(kept["hold"], True)
        self.assertIn("late_deny_row_after_restart", kept["warnings"])
        self.assertEqual(kept["restart_rows"]["after"]["late_s"], 7.25)
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

    def test_row_past_the_cap_or_not_new_is_absent(self) -> None:
        self.assertEqual(_side(wait_s=15.25)["cause"], "row_absent_errno13")
        # Only the old pre-restart row: same pid, no new row past it.
        self.assertEqual(_side(count=1)["cause"], "row_absent_errno13")
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

    def test_missing_side_or_guest_not_held_fails(self) -> None:
        restart = _restart(_side())
        del restart["restart_rows"]["after"]
        self.assertEqual(od._loader_word("2d-crash-recovery", _body(restart)), "fail")
        self.assertEqual(od._loader_word("2d-crash-recovery", _body(_restart(_side(), held=False))), "fail")
        self.assertEqual(od._loader_word("2d-crash-recovery", _body(dict(_restart(_side()), held="true"))), "fail")
        # A body from before this change (no restart_rows) keeps its old grade.
        old = _restart(_side())
        del old["restart_rows"]
        self.assertEqual(od._loader_word("2d-crash-recovery", _body(old)), "held")

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
        ]
        for side in cases:
            with self.subTest(side=side):
                self.assertEqual(od.restart_row_cause(od.allow_restart_side(side)), side["cause"])
                self.assertIn(side["cause"], {None, *grade.RESTART_ROW_CAUSES})


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
        self.assertEqual(kept["loader_kill_restart_rows"]["after"]["late_s"], 7.25)
        self.assertEqual(kept["loader_kill_restart_rows"]["before"]["row_count"], 1)

    def _write_rows(self, kill_body: dict) -> dict:
        """Drive od.run_batteries with every cloud call stubbed and return gcp-lab-rows.json."""
        repeat = {"b1_pass": True, "deny_hold": True, "deny_pid": 41, "desc_deny_pid": 42, "lineage_anchor": 7}

        def loader_case(_project: str, _name: str, _seal: str, mode: str) -> dict:
            if mode == "2d-crash-recovery":
                return {"body": kill_body, "rc": 0, "word": od._loader_word(mode, kill_body)}
            return {"body": {}, "rc": 0, "word": "held"}

        ok = subprocess.CompletedProcess([], 0, stdout="UNINSTALL_VERIFIED\n", stderr="")
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
                "_ssh": mock.Mock(return_value=ok),
                "_scp_to": mock.DEFAULT,
                "_prepare_lab_lsm": mock.Mock(return_value={}),
                "_wait_live_boot": mock.Mock(return_value="boot-2"),
                "_run_one_battery": mock.Mock(return_value=repeat),
                "full_set_passes": mock.Mock(return_value=True),
                "_loader_case": mock.Mock(side_effect=loader_case),
                "drop_guest_copies": mock.DEFAULT,
                "remove_os_login_key": mock.DEFAULT,
            }
            with mock.patch.multiple(od, **stubs), contextlib.redirect_stdout(io.StringIO()):
                with contextlib.suppress(SystemExit):
                    od.run_batteries({"RUNNER_TEMP": tmp})
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
        late, _ = self._write_rows(_body(_restart(_side(wait_s=7.25))))
        self.assertEqual(late["loader_kill"], "held")
        self.assertEqual(late["loader_kill_restart_rows"]["after"]["late_s"], 7.25)
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


if __name__ == "__main__":
    unittest.main()
