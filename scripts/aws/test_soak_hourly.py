#!/usr/bin/env python3
"""The soak hourly check and the boot user-data that installs it."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "aws"))
sys.path.insert(0, str(ROOT / "scripts" / "aws" / "lab-guests"))

import soak_check  # noqa: E402
import w3_lab_auto as lab  # noqa: E402
import w3_lab_steps as steps  # noqa: E402


def _pass_facts() -> dict:
    return {
        "allow_errno": 0,
        "began": "2026-10-13T12:00:00Z",
        "control_errno": 0,
        "cpu": "0.2",
        "drops": 0,
        "egress_anchor": 8498,
        "egress_errno": 110,
        "engine_loaded": True,
        "enrollment_intact": True,
        "file_anchor": 8498,
        "file_attributed": True,
        "file_errno": 13,
        "mem_kb": 500000,
        "programs_attached": True,
        "rss_kb": 12000,
    }


class SoakHourlyTest(unittest.TestCase):
    def test_pass_requires_attributed_file_and_egress(self) -> None:
        result, detail = soak_check.decide(_pass_facts())
        self.assertEqual(result, "pass")
        self.assertIn("began:2026-10-13T12:00:00Z", detail)
        self.assertIn("drops:0", detail)
        self.assertIn("eanchor:8498", detail)
        self.assertRegex(detail, r"^[A-Za-z0-9_.:-]+$")

    def test_timeout_without_an_anchor_is_not_a_pass(self) -> None:
        facts = _pass_facts()
        facts["egress_anchor"] = 0
        result, detail = soak_check.decide(facts)
        self.assertEqual(result, "fail")
        self.assertIn("reason:egress_deny", detail)

    def test_file_errno_zero_is_not_a_pass(self) -> None:
        facts = _pass_facts()
        facts["file_errno"] = 0
        result, detail = soak_check.decide(facts)
        self.assertEqual(result, "fail")
        self.assertIn("file_deny", detail)

    def test_control_timeout_is_not_a_pass(self) -> None:
        facts = _pass_facts()
        facts["control_errno"] = 110
        result, detail = soak_check.decide(facts)
        self.assertEqual(result, "fail")
        self.assertIn("reason:control", detail)

    def test_missing_engine_is_a_skip_before_the_probe_exists(self) -> None:
        result, detail = soak_check.decide({"waiting": True, "began": "2026-10-13T12:00:00Z"})
        self.assertEqual(result, "skip")
        self.assertIn("reason:engine_not_loaded", detail)

    def test_user_data_installs_the_timer_and_does_not_reboot(self) -> None:
        script = lab.build_soak_user_data()
        self.assertLessEqual(len(script.encode("utf-8")), 16384)
        self.assertIn("vantio-soak-hourly.timer", script)
        self.assertIn("record-check.sh", script)
        self.assertIn("OnCalendar=hourly", script)
        self.assertNotIn("shutdown -h", script)
        self.assertNotIn("systemctl reboot", script)
        self.assertNotIn("shutdown -h", (ROOT / "scripts/aws/lab-guests/soak-hourly.sh").read_text(encoding="utf-8"))
        plan = lab.plan_launch(
            {
                "associate_public_ipv4": "true",
                "max_life_hours": "36",
                "name": "vantio-w3-lab-auto-soak",
                "soak": True,
            },
            lab.parse_time("2026-10-13T12:00:00Z"),
        )
        self.assertEqual(plan["user_data"], script)

    def test_arm_wires_soak_hourly_without_a_reboot(self) -> None:
        rows = (ROOT / "scripts/aws/lab-guests/enterprise-rows.sh").read_text(encoding="utf-8")
        start = rows.index("  soak-hourly)")
        stop = rows.index("\n    ;;\n", start)
        block = rows[start:stop]
        self.assertNotIn("reboot", block)
        self.assertNotIn("authorized_uninstall", block)
        self.assertIn("soak-hourly.sh start", block)
        arm = (ROOT / ".github/workflows/w3-lab-auto-arm.yml").read_text(encoding="utf-8")
        self.assertIn("- soak-hourly", arm)
        self.assertIn("scripts/aws/lab-guests/soak_check.py", arm)
        launch = (ROOT / ".github/workflows/w3-lab-auto-long-soak.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/aws/lab-guests/soak-hourly.sh", launch)
        steps = (ROOT / "scripts/aws/w3_lab_steps.py").read_text(encoding="utf-8")
        self.assertIn('"soak-hourly"', steps)

    def test_collect_keeps_the_check_detail(self) -> None:
        raw = '{"detail":"began:2026-10-13T12:00:00Z.drops:0","name":"hourly","result":"pass","seq":1}\n'
        parsed = steps.parse_check_details(raw)
        self.assertEqual(parsed[0]["result"], "pass")
        self.assertIn("began:2026-10-13T12:00:00Z", parsed[0]["detail"])
        self.assertEqual(steps.parse_check_details('{"detail":"PRIVATE KEY","name":"hourly","result":"pass","seq":1}'), [])


if __name__ == "__main__":
    unittest.main()
