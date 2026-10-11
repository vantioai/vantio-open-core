#!/usr/bin/env python3
"""The descendant harness can start deny cases once the open pins are logged."""

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
    def test_open_pins_reach_the_deny_cases(self) -> None:
        decision = _decision()
        banner = (
            "Path DENY pinned: kprobe_open_deny -> __x64_sys_open\n"
            "Path DENY pinned: kprobe_openat_deny -> __x64_sys_openat\n"
        )
        self.assertEqual(decision(banner, True), "open_pins_before_scoped_line")
        self.assertEqual(decision("tc enforce : SCOPED (drop enrolled)", False), "scoped")
        self.assertEqual(decision("AUDIT (log only)", True), "missing")
        self.assertEqual(decision(banner, False), "missing")


if __name__ == "__main__":
    unittest.main()
