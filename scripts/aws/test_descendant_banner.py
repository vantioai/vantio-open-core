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


if __name__ == "__main__":
    unittest.main()
