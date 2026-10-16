"""The GCP t5-egress plan does not start a guest."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "gcp"))

import offline_deliver as od  # noqa: E402
import t5_lab_plan  # noqa: E402


class GcpT5PlanTests(unittest.TestCase):
    def test_default_schedule_is_unchanged(self) -> None:
        self.assertEqual(od.battery_schedule(), ["enterprise", "descendant-b1", "enterprise", "descendant-b1"])

    def test_evidence_keeps_the_battery_id(self) -> None:
        kept = od.allow_battery({"battery": "t5-egress", "result": "pass", "hostname": "hidden"})
        self.assertEqual(kept, {"battery": "t5-egress", "result": "pass"})

    def test_plan_does_not_dispatch(self) -> None:
        quiet = t5_lab_plan.plan({"GCP_LAB_PROJECT": "vantio-lab-oct08"})
        self.assertFalse(quiet["dispatch"])
        self.assertFalse(quiet["attached"])
        self.assertIn("not_dispatched", quiet["reasons"])
        self.assertIn("workflow_has_no_t5_input", quiet["reasons"])
        self.assertNotIn("navera", quiet["reasons"])

    def test_navera_and_static_keys_are_refused(self) -> None:
        foreign = t5_lab_plan.plan({"GCP_LAB_PROJECT": "vantio-lab-navera"})
        self.assertIn("navera", foreign["reasons"])
        self.assertFalse(foreign["dispatch"])
        keyed = t5_lab_plan.plan(
            {"GCP_LAB_PROJECT": "vantio-lab-oct08", "GOOGLE_APPLICATION_CREDENTIALS": "/tmp/key.json"}
        )
        self.assertIn("static_key", keyed["reasons"])
        self.assertFalse(keyed["dispatch"])


if __name__ == "__main__":
    unittest.main()
