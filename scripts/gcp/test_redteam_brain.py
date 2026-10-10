"""Cost and hash pins for the offline red-team brain. No download and no GCP."""

from __future__ import annotations

import unittest
from decimal import Decimal

import redteam_brain as brain


class BrainTests(unittest.TestCase):
    def test_e2_standard_4_for_two_hours_stays_under_the_dollar_cap(self) -> None:
        # 120 minutes is the longest life the lab will start.
        gross = brain.assert_under_cap(brain.BRAIN_MACHINE, 120, brain.BRAIN_DISK_GB)
        self.assertLess(gross, brain.GROSS_RUN_CAP_USD)
        self.assertLess(gross, brain.LAB_BUDGET_USD)
        quote = brain.brain_plan(90)
        self.assertEqual(quote["machine_type"], "e2-standard-4")
        self.assertEqual(quote["expected_oop_usd"], "0")
        self.assertEqual(quote["model_sha256"], brain.MODEL_SHA256)
        self.assertLess(Decimal(quote["gross_usd"]), Decimal("0.30"))

    def test_unknown_machine_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            brain.estimate_gross_usd("n2-standard-32", 10, Decimal("10"))

    def test_hash_pin_is_exact(self) -> None:
        self.assertTrue(brain.hashes_match(brain.MODEL_SHA256, brain.RUNTIME_SHA256))
        self.assertFalse(brain.hashes_match("ab" * 32, brain.RUNTIME_SHA256))
        self.assertEqual(brain.MODEL_BYTES, 2104932768)


if __name__ == "__main__":
    unittest.main()
