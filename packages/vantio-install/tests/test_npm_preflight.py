"""Ubuntu nodejs without npm is a plan fact, not an apply crash."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from tests.test_stage_a import Harness  # noqa: E402
from vantio_install import constants  # noqa: E402
from vantio_install.commands import apt_install_npm_argv  # noqa: E402
from vantio_install.preflight import NPM_PREREQUISITE  # noqa: E402

SEAL = "e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e"


class NpmPreflightTests(unittest.TestCase):
    def make(self) -> Harness:
        harness = Harness()
        self.addCleanup(harness.close)
        return harness

    def test_pins_stay_on_the_run3_seal(self) -> None:
        pins = constants.FROZEN_PINS
        self.assertEqual(pins["optics_cli_version"], "0.3.24")
        self.assertEqual(pins["agent_sdk_py_version"], "3.1.0")
        self.assertEqual(pins["pe_archive_sha256"], SEAL)
        self.assertIn("PF-OCI-LOAD", constants.PREFLIGHT_ORDER)
        self.assertIn("PF-NPM", constants.PREFLIGHT_ORDER)

    def test_present_npm_stays_a_version_check(self) -> None:
        harness = self.make()
        code, body = harness.run("plan")
        self.assertEqual(code, 0, body)
        step = next(row for row in body["planned_steps"] if row["id"] == "ensure_node")
        self.assertEqual(step["npm_action"], "present")
        self.assertFalse(step["mutation"])
        self.assertEqual(step["argv"], ["npm", "--version"])
        self.assertEqual(body["prerequisites"], [])
        plan = json.loads(harness.tx_file("PLAN.json").read_text(encoding="utf-8"))
        ops = plan["live_operations"]
        self.assertLess(ops.index("ensure_npm"), ops.index("install_optics_cli"))

    def test_missing_npm_on_ubuntu_root_is_written_into_the_plan(self) -> None:
        harness = self.make()
        harness.host["npm_version"] = None
        harness.host["node_version"] = "v18.19.1"
        harness.host["effective_uid"] = 0
        code, body = harness.run("plan")
        self.assertEqual(code, 0, body)
        self.assertEqual(body["state"], "PLANNED")
        self.assertEqual(body["prerequisites"][0]["text"], NPM_PREREQUISITE)
        self.assertEqual(body["prerequisites"][0]["argv"], apt_install_npm_argv())
        step = next(row for row in body["planned_steps"] if row["id"] == "ensure_node")
        self.assertTrue(step["mutation"])
        self.assertEqual(step["npm_action"], "remediate")
        self.assertEqual(step["prerequisite"], NPM_PREREQUISITE)
        self.assertEqual(step["argv"], apt_install_npm_argv())
        preflight = json.loads(harness.tx_file("PREFLIGHT.json").read_text(encoding="utf-8"))
        check = next(row for row in preflight["checks"] if row["id"] == "PF-NPM")
        self.assertEqual(check["result"], "PASS")
        self.assertEqual(check["remediation"], NPM_PREREQUISITE)
        self.assertNotIn("PF-NPM", body["failed_or_limiting_checks"])

    def test_missing_npm_without_root_blocks_before_apply(self) -> None:
        harness = self.make()
        harness.host["npm_version"] = None
        harness.host["effective_uid"] = 1000
        code, body = harness.run("plan")
        self.assertEqual(code, 2, body)
        self.assertEqual(body["state"], "PREFLIGHT_BLOCKED")
        self.assertEqual(body["planned_steps"], [])
        self.assertIn("PF-NPM", body["failed_or_limiting_checks"])
        self.assertEqual(body["prerequisites"][0]["text"], NPM_PREREQUISITE)
        self.assertNotIn("argv", body["prerequisites"][0])
        plan = json.loads(harness.tx_file("PLAN.json").read_text(encoding="utf-8"))
        self.assertEqual(plan["planned_steps"], [])
        self.assertEqual(plan["prerequisites"][0]["text"], NPM_PREREQUISITE)


if __name__ == "__main__":
    unittest.main()
