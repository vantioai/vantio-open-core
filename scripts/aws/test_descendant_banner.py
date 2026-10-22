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
        self.assertIn("require_scoped_start(ledger_since)", prepare)
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


if __name__ == "__main__":
    unittest.main()
