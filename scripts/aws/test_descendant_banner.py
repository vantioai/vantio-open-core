#!/usr/bin/env python3
"""The descendant re-arm waits for the scoped line and the cgroup pin line."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUEST = ROOT / "scripts" / "aws" / "lab-guests" / "descendant_b1.py"


def _decision():
    text = GUEST.read_text(encoding="utf-8")
    start = text.index("SCOPED_NEEDLE = ")
    end = text.index("\ndef loader_logs")
    namespace: dict = {}
    exec(text[start:end], namespace)
    return namespace["scoped_start_decision"]


class DescendantBannerTests(unittest.TestCase):
    def test_open_pins_do_not_start_the_rearm(self) -> None:
        decision = _decision()
        pins = (
            "Path DENY pinned: kprobe_open_deny -> __x64_sys_open\n"
            "Path DENY pinned: kprobe_openat_deny -> __x64_sys_openat\n"
        )
        self.assertEqual(decision(pins, True), "waiting_for_cgroup_pin")
        self.assertEqual(decision(pins, False), "missing")
        scoped = "tc enforce : SCOPED (drop enrolled)\n"
        self.assertEqual(decision(scoped, True), "waiting_for_cgroup_pin")
        self.assertEqual(decision(scoped, False), "missing")
        failed = scoped + "cgroup_skb_egress_enforce loaded without a pin. Container stop will drop it.\n"
        self.assertEqual(decision(failed, True), "waiting_for_cgroup_pin")
        ready = scoped + "cgroup_skb_egress_enforce\n"
        self.assertEqual(decision(ready, True), "scoped")
        self.assertEqual(decision(ready, False), "scoped")
        self.assertEqual(decision(pins + ready, True), "scoped")
        self.assertEqual(decision("AUDIT (log only)", True), "missing")
        source = GUEST.read_text(encoding="utf-8")
        waiter = source.split("def require_scoped_start", 1)[1].split("\ndef measure", 1)[0]
        self.assertNotIn("open_pins_before_scoped_line", waiter)
        self.assertIn('if decision == "scoped"', waiter)

    def test_post_reboot_ledger_wait_ignores_the_pre_boot_line(self) -> None:
        text = GUEST.read_text(encoding="utf-8")
        start = text.index("def fresh_scoped_ledger_line")
        end = text.index("\ndef _cgroup_pin_logged")
        namespace: dict = {}
        exec(text[start:end], namespace)
        fresh = namespace["fresh_scoped_ledger_line"]
        # events.ndjson survives the B1 reboot (run 39820487208 post: SCOPED x2).
        pre_boot = [
            {"EventType": "ENGINE_STARTED", "ActionTaken": "AUDIT"},
            {"EventType": "ENGINE_STARTED", "ActionTaken": "SCOPED"},
            {"EventType": "SYSCALL_OPENAT", "ActionTaken": "DENIED", "Pid": 19867},
            {"EventType": "ENGINE_STARTED", "ActionTaken": "AUDIT"},
        ]
        since = len(pre_boot)
        self.assertFalse(fresh(pre_boot, since))
        self.assertTrue(fresh(pre_boot, 0))
        self.assertFalse(fresh(pre_boot + [{"EventType": "SYSCALL_OPENAT", "ActionTaken": "DENIED"}], since))
        self.assertTrue(fresh(pre_boot + [{"EventType": "ENGINE_STARTED", "ActionTaken": "SCOPED"}], since))
        self.assertFalse(fresh([], 0))
        prepare = text.split("def prepare_enforce", 1)[1].split("\nSCOPED_NEEDLE", 1)[0]
        self.assertLess(prepare.index("ledger_since = len(events())"), prepare.index("blocked = rows.start_loader(adapter)"))
        self.assertIn("require_scoped_start(ledger_since, probe=start_window_probe)", prepare)
        waiter = text.split("def require_scoped_start", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("fresh_scoped_ledger_line(events(), ledger_since)", waiter)
        self.assertNotIn("for item in events():", waiter)

    def test_rows_carry_boot_lsm_and_the_reassert_record(self) -> None:
        text = GUEST.read_text(encoding="utf-8")
        measure = text.split("def measure(phase: str)", 1)[1].split("\ndef ", 1)[0]
        self.assertIn('"boot_lsm": boot_lsm()', measure)
        post = text.split("def _main", 1)[1]
        self.assertIn('"lab_lsm_reassert": reassert_record()', post)
        self.assertIn('Path("/var/lib/vantio-lab/lsm-reassert.json")', text)
        shell = (ROOT / "scripts" / "aws" / "lab-guests" / "enterprise-rows.sh").read_text(encoding="utf-8")
        branch = shell.split('if [ "$mode" = "descendant-b1" ]; then', 1)[1]
        pre_rm = branch.split('if [ "$phase" = "pre" ]; then', 1)[1].split("else", 1)[0]
        self.assertIn("/var/lib/vantio-lab/lsm-reassert.json", pre_rm)
        post_rm = branch.split('if [ "$phase" = "pre" ]; then', 1)[1].split("else", 1)[1].split("fi", 1)[0]
        self.assertNotIn("lsm-reassert.json", post_rm)

    @staticmethod
    def _start_namespace(items_by_call):
        """Exec the start-wait section with a fake clock, loader and events file."""
        text = GUEST.read_text(encoding="utf-8")
        start = text.index("SCOPED_NEEDLE = ")
        end = text.index("\ndef boot_lsm")

        class Clock:
            now = 0.0

            def time(self):
                return self.now

            def monotonic(self):
                return self.now

            def sleep(self, seconds):
                self.now += seconds

        clock = Clock()
        namespace: dict = {"time": clock, "Path": Path}
        exec(text[start:end], namespace)
        calls = {"events": 0, "probe": 0}

        def events():
            calls["events"] += 1
            return items_by_call(calls["events"])

        namespace["events"] = events
        namespace["loader_logs"] = lambda: "tc enforce : SCOPED (drop enrolled)\ncgroup_skb_egress_enforce\n"
        namespace["loader_is_running"] = lambda: True
        return namespace, clock, calls

    def test_ledger_wait_times_out_and_falls_through_with_timing(self) -> None:
        stale = [
            {"EventType": "ENGINE_STARTED", "ActionTaken": "AUDIT"},
            {"EventType": "ENGINE_STARTED", "ActionTaken": "SCOPED"},
        ]
        namespace, clock, calls = self._start_namespace(lambda _n: list(stale))

        def probe():
            calls["probe"] += 1
            clock.now += 0.25
            return {"pid": 4242, "file_errno": 13, "net_errno": 1}

        # Only the pre-boot SCOPED line exists: the wait must not raise and must not claim scoped.
        namespace["require_scoped_start"](len(stale), probe=probe)
        self.assertEqual(namespace["BANNER_STATUS"], "scoped_banner_without_ledger_line")
        timing = namespace["START_TIMING"]
        self.assertIs(timing["ledger_seen"], False)
        self.assertIsNone(timing["banner_to_ledger_s"])
        self.assertEqual(timing["banner_wait_s"], 0.0)
        self.assertEqual(timing["probe_done_after_banner_s"], 0.25)
        self.assertEqual(timing["ledger_timeout_s"], 0.25 + namespace["LEDGER_WAIT_TRIES"])
        self.assertEqual(timing["ledger_since"], len(stale))
        self.assertEqual(calls["probe"], 1)
        self.assertEqual(calls["events"], namespace["LEDGER_WAIT_TRIES"])
        self.assertEqual(namespace["START_PROBE"], {"pid": 4242, "file_errno": 13, "net_errno": 1})

    def test_ledger_wait_records_banner_to_ledger_time(self) -> None:
        stale = [{"EventType": "ENGINE_STARTED", "ActionTaken": "SCOPED"}]
        fresh = stale + [{"EventType": "ENGINE_STARTED", "ActionTaken": "SCOPED"}]
        namespace, _clock, calls = self._start_namespace(lambda n: fresh if n >= 6 else stale)
        order: list[str] = []

        def probe():
            order.append(f"probe_after_{calls['events']}_reads")
            return {"pid": 1, "file_errno": 13}

        namespace["require_scoped_start"](len(stale), probe=probe)
        self.assertEqual(namespace["BANNER_STATUS"], "scoped")
        timing = namespace["START_TIMING"]
        self.assertIs(timing["ledger_seen"], True)
        self.assertEqual(timing["banner_to_ledger_s"], 5.0)
        self.assertEqual(timing["start_wait_s"], 5.0)
        # The probe runs after the banner and before any ledger read.
        self.assertEqual(order, ["probe_after_0_reads"])

    def test_start_window_rows_classifies_delayed_and_dropped(self) -> None:
        text = GUEST.read_text(encoding="utf-8")
        start = text.index("def events() -> list[dict]:")
        end = text.index("\ndef egress_denied")
        namespace: dict = {"Path": Path, "json": __import__("json")}
        exec(text[start:end], namespace)
        digest = "sha256:d"

        def deny(pid, **extra):
            row = {"EventType": "SYSCALL_OPENAT", "ActionTaken": "DENIED", "Pid": pid, "policy_digest": digest, "lineage_anchor": 7}
            row.update(extra)
            return row

        old = [deny(11703), {"EventType": "ENGINE_STARTED", "ActionTaken": "SCOPED"}]
        new = [
            {"EventType": "ENGINE_STARTED", "ActionTaken": "SCOPED", "Timestamp": "t1"},
            deny(900, Timestamp="t2"),
            deny(11704),
            {"EventType": "SYSCALL_OPENAT", "ActionTaken": "DENIED", "Pid": 11709, "policy_digest": "other", "lineage_anchor": 7},
        ]
        namespace["events"] = lambda: old + new
        first_round = [
            {"name": "moved", "expect_deny": True, "file_errno": 13, "file_event": None, "pid": 11703, "pass": False},
            {"name": "clone3", "expect_deny": True, "file_errno": 13, "file_event": None, "pid": 11704, "pass": False},
            {"name": "reparent", "expect_deny": True, "file_errno": 13, "file_event": None, "pid": 11709, "pass": False},
            {"name": "unshare", "expect_deny": True, "file_errno": 13, "file_event": {"Pid": 11718}, "pid": 11718, "pass": True},
            {"name": "ancestor_9", "expect_deny": False, "file_errno": 0, "file_event": None, "pid": 11720, "pass": True},
        ]
        window = namespace["start_window_rows"](digest, len(old), {"pid": 900, "file_errno": 13}, first_round)
        by_name = {entry["name"]: entry for entry in window["checked"]}
        self.assertEqual(sorted(by_name), ["clone3", "moved", "reparent", "start_probe"])
        self.assertEqual(by_name["start_probe"]["status"], "recorded")
        self.assertIs(by_name["start_probe"]["after_ledger_line"], True)
        self.assertEqual(by_name["start_probe"]["row_time"], "t2")
        # A pre-boot row for a recycled pid does not count: it is before the offset.
        self.assertEqual(by_name["moved"]["status"], "dropped")
        self.assertEqual(by_name["clone3"]["status"], "delayed")
        # A row for another policy digest is not this pid's deny row.
        self.assertEqual(by_name["reparent"]["status"], "dropped")
        self.assertEqual((window["status"], window["delayed"], window["dropped"]), ("mixed", 1, 2))
        self.assertEqual((window["ledger_line_index"], window["ledger_line_time"]), (0, "t1"))
        self.assertIs(window["informational"], True)
        # The re-scan never edits the samples it read.
        self.assertEqual([item["pass"] for item in first_round], [False, False, False, True, True])
        none = namespace["start_window_rows"](digest, len(old), {"pid": 900, "file_errno": 0}, [])
        self.assertEqual(none["status"], "none_missing")
        self.assertEqual(none["checked"][0]["status"], "probe_not_denied")
        dropped = namespace["start_window_rows"](digest, len(old), {"pid": 901, "file_errno": 13}, [])
        self.assertEqual((dropped["status"], dropped["dropped"]), ("dropped", 1))

    def test_boot_lsm_uses_the_last_lsm_word(self) -> None:
        text = GUEST.read_text(encoding="utf-8")
        body = text.split("def boot_lsm", 1)[1].split("\nREASSERT_PATH", 1)[0]
        self.assertIn("reversed(words)", body)

    def test_new_fields_do_not_feed_the_grade(self) -> None:
        text = GUEST.read_text(encoding="utf-8")
        score = text.split("def score(", 1)[1].split("\ndef ", 1)[0]
        measure = text.split("def measure(phase: str)", 1)[1].split("\ndef ", 1)[0]
        for word in ("start_window", "START_PROBE", "START_TIMING", "warnings"):
            self.assertNotIn(word, score)
        self.assertIn('"pass": all(item["pass"] for item in samples)', measure)
        self.assertIn('"descendant_pass": all(item["pass"] for item in stable if not item.get("skipped")) and root_open.get("errno") == 0', measure)
        self.assertIn('"warnings": [f"scoped_banner={BANNER_STATUS}"] if BANNER_STATUS != "scoped" else []', measure)


if __name__ == "__main__":
    unittest.main()
