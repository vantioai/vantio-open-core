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
        self.assertNotIn("workflow_has_no_t5_input", quiet["reasons"])
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

    def test_dispatch_guard_accepts_only_the_lane_seal(self) -> None:
        env = {
            "T5_EGRESS": "true",
            "GCP_LAB_PROJECT": "vantio-lab-oct08",
            "EXPECTED_SEAL": od.t5_battery.LANE_SEAL,
            "RUN_BATTERIES": "false",
            "SELF_SERVICE": "false",
        }
        self.assertEqual(od.assert_t5_dispatch(env), od.t5_battery.LANE_SEAL)
        public = dict(env)
        public["EXPECTED_SEAL"] = od.t5_battery.PUBLIC_PIN
        with self.assertRaises(SystemExit):
            od.assert_t5_dispatch(public)
        mixed = dict(env)
        mixed["RUN_BATTERIES"] = "true"
        with self.assertRaises(SystemExit):
            od.assert_t5_dispatch(mixed)
        foreign = dict(env)
        foreign["GCP_LAB_PROJECT"] = "vantio-lab-navera"
        with self.assertRaises(SystemExit):
            od.assert_t5_dispatch(foreign)

    def test_t5_evidence_keeps_the_lab_cgroup_only(self) -> None:
        kept = od.allow_battery(
            {
                "battery": "t5-egress",
                "result": "pass",
                "verifier": "accepted",
                "user_port": "pass",
                "kernel_attach": "Lab-only",
                "label": "Lab-only",
                "cgroup": "/sys/fs/cgroup/vantio-t5-lab.slice/t5-drill",
                "attached": True,
                "outside_unaffected": True,
                "enrolled_slice": False,
                "hostname": "hidden.example",
            }
        )
        self.assertEqual(kept["cgroup"], "/sys/fs/cgroup/vantio-t5-lab.slice/t5-drill")
        self.assertEqual(kept["verifier"], "accepted")
        self.assertNotIn("hostname", kept)
        other = od.allow_battery({"cgroup": "/sys/fs/cgroup/vantio-enrolled.slice"})
        self.assertIsNone(other)


if __name__ == "__main__":
    unittest.main()
