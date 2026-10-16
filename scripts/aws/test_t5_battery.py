"""Allow-list tests for battery id t5-egress. These tests do not call AWS."""

from __future__ import annotations

import json
import os
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "aws"))
sys.path.insert(0, str(ROOT / "scripts" / "clean-host" / "t5"))

import t5_battery  # noqa: E402
import w3_lab_auto as lab  # noqa: E402
import w3_lab_steps as steps  # noqa: E402

LANE = t5_battery.LANE_SEAL
PIN = t5_battery.PUBLIC_PIN
INSTANCE = "i-0123456789abcdef0"


class T5BatteryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)

    def _ready(self, tmp: str) -> None:
        path = Path(tmp) / "caps.json"
        path.write_text(json.dumps({"ssh_instance_connect": True, "max_life_hours_36": True, "ssm": False}))
        os.environ["W3_LAB_CAPABILITIES"] = str(path)
        os.environ["INSTANCE_ID"] = INSTANCE
        os.environ["PUBLIC_PIN"] = PIN
        os.environ["W3_RUNNER_CIDR"] = "1.1.1.1/32"
        os.environ["EVIDENCE_PATH"] = str(Path(tmp) / "arm.json")
        os.environ["W3_STAMP"] = str(Path(tmp) / "stamp.json")
        os.environ["W3_BUNDLE_DIR"] = str(Path(tmp) / "bundle")
        os.environ["W3_BATTERY"] = "t5-egress"

    def test_public_pin_is_not_the_lane_seal(self) -> None:
        self.assertNotEqual(LANE, PIN)
        self.assertTrue(t5_battery.lane_seal(LANE))
        self.assertFalse(t5_battery.lane_seal(PIN))

    def test_wrong_seal_stops_before_aws(self) -> None:
        runner_calls: list[list[str]] = []

        def runner(args: list[str]):
            runner_calls.append(args)
            raise AssertionError("aws")

        with tempfile.TemporaryDirectory() as tmp:
            self._ready(tmp)
            os.environ["SEAL"] = PIN
            with self.assertRaises(lab.GuardAbort) as caught:
                steps.execute_enterprise_rows(runner)  # type: ignore[arg-type]
        self.assertEqual(caught.exception.reason, "bundle_wrong_seal")
        self.assertEqual(runner_calls, [])

    def test_brain_dir_is_refused(self) -> None:
        def runner(args: list[str]):
            raise AssertionError(args)

        with tempfile.TemporaryDirectory() as tmp:
            self._ready(tmp)
            os.environ["SEAL"] = LANE
            os.environ["W3_BRAIN_DIR"] = str(Path(tmp) / "brain")
            with self.assertRaises(lab.GuardAbort) as caught:
                steps.execute_enterprise_rows(runner)  # type: ignore[arg-type]
        self.assertEqual(caught.exception.reason, "battery")

    def test_unknown_battery_is_still_rejected(self) -> None:
        def runner(args: list[str]):
            raise AssertionError(args)

        with tempfile.TemporaryDirectory() as tmp:
            self._ready(tmp)
            os.environ["SEAL"] = LANE
            os.environ["W3_BATTERY"] = "not-a-battery"
            with self.assertRaises(lab.GuardAbort) as caught:
                steps.execute_enterprise_rows(runner)  # type: ignore[arg-type]
        self.assertEqual(caught.exception.reason, "battery")

    def test_guest_script_refuses_navera_and_does_not_attach(self) -> None:
        text = t5_battery.GUEST_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("t5-egress", text)
        self.assertIn("navera", text)
        self.assertIn("vantio-enrolled.slice", text)
        self.assertNotIn("bpf(", text)
        self.assertNotIn("enterprise-rows.sh", text)

    def test_pack_tree_contains_the_program(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "t5-egress.tar"
            t5_battery.pack_tree(ROOT, dest)
            with tarfile.open(dest) as archive:
                names = archive.getnames()
        self.assertIn("packages/t5-egress-kernel/bpf/t5_egress.bpf.c", names)
        self.assertIn("scripts/clean-host/t5/proof.py", names)
        self.assertTrue(all("navera" not in name for name in names))


if __name__ == "__main__":
    unittest.main()
