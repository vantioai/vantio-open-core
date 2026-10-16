#!/usr/bin/env python3
"""Unit tests for the T0 OpenClaw hygiene checker."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "gap"))

import t0_openclaw_hygiene as hygiene
import t0_proof


class CalverTests(unittest.TestCase):
    def test_floor_and_numeric_order(self) -> None:
        self.assertTrue(hygiene.version_below("2026.1.28", "2026.1.29"))
        self.assertFalse(hygiene.version_below("2026.1.29", "2026.1.29"))
        self.assertTrue(hygiene.version_below("2026.1.29-beta.1", "2026.1.29"))
        self.assertFalse(hygiene.version_below("2026.6.34", "2026.1.29"))
        self.assertFalse(hygiene.version_below("2026.10.4", "2026.1.29"))
        self.assertLess("2026.10.4", "2026.6.34")
        self.assertGreater(
            hygiene.compare_calver(hygiene.parse_calver("2026.10.4"), hygiene.parse_calver("2026.6.34")),
            0,
        )

    def test_floating_token_is_not_a_version(self) -> None:
        with self.assertRaises(ValueError):
            hygiene.parse_calver("latest")


class RepoTests(unittest.TestCase):
    def test_repository_pin_passes(self) -> None:
        result = hygiene.evaluate(ROOT)
        self.assertTrue(result.ok, result.findings)
        self.assertIn("phantom-box-apply-image-pin", result.approval_gates)

    def test_negative_cases_fail_closed(self) -> None:
        cases = {str(case["name"]): case["fail_closed"] for case in t0_proof.negative_cases(ROOT)}
        self.assertTrue(cases["floating-tag-rejected"])
        self.assertTrue(cases["affected-tag-rejected"])
        self.assertTrue(cases["blocked-publisher-rejected"])
        self.assertTrue(cases["marketplace-clawhub-rejected"])
        self.assertTrue(cases["hook-hash-mismatch-rejected"])
        self.assertTrue(cases["missing-pin-rejected"])
        self.assertTrue(all(cases.values()))

    def test_proof_payload_matches_checker(self) -> None:
        payload = t0_proof.build_payload(ROOT)
        self.assertEqual(payload["checker_ok"], True)
        self.assertEqual(payload["affected"], "unknown")
        self.assertEqual(payload["running_version"], "unknown")
        self.assertEqual(payload["negative_cases_closed"], True)
        self.assertEqual(payload["design_commit"], t0_proof.DESIGN_COMMIT)


if __name__ == "__main__":
    unittest.main()
