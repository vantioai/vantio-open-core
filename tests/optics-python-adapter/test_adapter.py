"""Unit C adapter scores the merged Unit A fixtures on copies."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "optics-python-adapter" / "src"))

from optics_python_adapter import (  # noqa: E402
    CLAIMED_CPYTHON,
    adapt_copy,
    adapt_fixture,
    canonical_json,
)
from optics_python_adapter.contract_loader import load_contract  # noqa: E402

FIXTURES = ROOT / "packages" / "optics-record-vocabulary" / "fixtures" / "conformance-fixtures.json"
NODE_CANONICAL = ROOT / "packages" / "optics-record-vocabulary" / "src" / "canonical-json.cjs"


def _fixtures():
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def _node_canonical(value):
    completed = subprocess.run(
        [
            "node",
            "-e",
            "const {canonicalJson}=require(process.argv[1]); process.stdout.write(canonicalJson(JSON.parse(require('fs').readFileSync(0,'utf8'))))",
            str(NODE_CANONICAL),
        ],
        input=json.dumps(value),
        text=True,
        check=True,
        capture_output=True,
    )
    return completed.stdout


class FixtureScoreTests(unittest.TestCase):
    def test_claimed_cpython_is_the_running_interpreter(self):
        self.assertEqual(CLAIMED_CPYTHON, "3.12")
        self.assertEqual(sys.version_info[:2], (3, 12))

    def test_every_unit_a_fixture_matches_the_declared_canonical(self):
        load_contract()
        mismatches = []
        for fixture in _fixtures():
            before = copy.deepcopy(fixture)
            reading = adapt_fixture(fixture)
            if fixture != before:
                mismatches.append(fixture["id"] + " mutated the fixture")
            if reading["writes_live_run_directory"] is not False:
                mismatches.append(fixture["id"] + " writes")
            if reading["live_writer_modified"] is not False:
                mismatches.append(fixture["id"] + " live writer")
            if reading["events_invented"] is not False:
                mismatches.append(fixture["id"] + " invented events")
            if reading["record_emitted"] != fixture["record_emitted"]:
                mismatches.append(fixture["id"] + " emitted " + str(reading["record_emitted"]))
            if reading["canonical"] != fixture["expected_canonical"]:
                mismatches.append(
                    fixture["id"]
                    + " canonical "
                    + json.dumps(reading["canonical"], sort_keys=True)
                    + " != "
                    + json.dumps(fixture["expected_canonical"], sort_keys=True)
                )
            if reading["events"] != fixture["expected_events"]:
                mismatches.append(
                    fixture["id"]
                    + " events "
                    + json.dumps(reading["events"], sort_keys=True)
                    + " != "
                    + json.dumps(fixture["expected_events"], sort_keys=True)
                )
            if reading["unsupported_state"] != fixture["expected_unsupported_state"]:
                mismatches.append(fixture["id"] + " unsupported " + str(reading["unsupported_state"]))
            blob = json.dumps(reading["canonical"]) + json.dumps(reading["events"])
            if "SUCCESS" in blob and '"optics_status": "SUCCESS"' in blob:
                mismatches.append(fixture["id"] + " stored optics SUCCESS")
            if reading["canonical"] == {} and fixture["expected_canonical"] is None:
                mismatches.append(fixture["id"] + " empty object")
        self.assertEqual(mismatches, [])

    def test_python_success_timestamp_and_joined_mediation(self):
        fixture = next(item for item in _fixtures() if item["id"] == "python-3-1-0")
        source_ts = fixture["input_record"]["call"]["ts"]
        reading = adapt_fixture(fixture)
        self.assertEqual(source_ts, "2026-07-01T00:00:00.100000+00:00")
        self.assertEqual(reading["canonical"]["started_at"], "2026-07-01T00:00:00.100Z")
        self.assertEqual(reading["canonical"]["optics_status"], "UNAVAILABLE")
        self.assertIn("OPTIMISTIC_DEFAULT_FORBIDDEN", reading["reasons"])
        self.assertEqual(reading["mediation_reading"], "unknown")
        self.assertNotIn("mediation", reading["canonical"])
        self.assertIsNone(reading["events"])
        self.assertIn("mediation", reading["fields_not_promoted"])
        self.assertIn("failure_kind", reading["fields_not_promoted"])

    def test_absent_and_corrupt_are_not_observed_success(self):
        by_id = {item["id"]: item for item in _fixtures()}
        empty = adapt_fixture(by_id["empty-shield"])
        missing = adapt_fixture(by_id["no-file"])
        corrupt = adapt_fixture(by_id["corrupt-record"])
        unreadable = adapt_fixture(by_id["unreadable-record"])
        self.assertEqual(empty["optics_reading"], "UNAVAILABLE")
        self.assertEqual(missing["optics_reading"], "UNAVAILABLE")
        self.assertNotEqual(empty["optics_reading"], "NOT_OBSERVED")
        self.assertEqual(corrupt["optics_reading"], "OPTICS_ERROR")
        self.assertEqual(unreadable["optics_reading"], "OPTICS_ERROR")
        self.assertIsNone(corrupt["canonical"])
        self.assertNotEqual(corrupt["canonical"], {})

    def test_sampling_and_unknown_method_are_omitted(self):
        by_id = {item["id"]: item for item in _fixtures()}
        sampled = adapt_fixture(by_id["sampling-not-success"])
        method = adapt_fixture(by_id["unknown-enum"])
        self.assertNotIn("sampling", sampled["canonical"])
        self.assertNotEqual(sampled["canonical"].get("optics_status"), "SUCCESS")
        self.assertTrue(any("SAMPLED" in item for item in sampled["diagnostics"]))
        self.assertNotIn("method", method["canonical"])
        self.assertTrue(any("FLY" in item for item in method["diagnostics"]))

    def test_shared_projection_matches_node_canonical_bytes(self):
        fixture = next(item for item in _fixtures() if item["id"] == "python-3-1-0")
        reading = adapt_fixture(fixture)
        python_bytes = canonical_json(reading["canonical"])
        node_bytes = _node_canonical(reading["canonical"])
        self.assertEqual(python_bytes, node_bytes)
        cli = next(item for item in _fixtures() if item["id"] == "cli-0-3-24")
        cli_reading = adapt_fixture(cli)
        self.assertEqual(canonical_json(cli_reading["canonical"]), _node_canonical(cli_reading["canonical"]))

    def test_adapter_does_not_open_a_path_argument(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "run.json"
            target.write_text('{"sealed":true}', encoding="utf-8")
            before = target.read_bytes()
            reading = adapt_copy(target)
            self.assertEqual(target.read_bytes(), before)
            self.assertFalse(reading["record_emitted"])
            self.assertEqual(reading["optics_reading"], "UNAVAILABLE")
            self.assertNotEqual(reading["optics_reading"], "NOT_OBSERVED")

    def test_a_three_one_zero_file_is_byte_identical_after_adapt(self):
        payload = {
            "vantio_run_log": "1",
            "schema_version": 2,
            "schema_status": "unstable-pre-1.0",
            "runtime": "python",
            "trace_id": "6f1d7a2e-3c4b-4d5e-8f90-a1b2c3d4e5f6",
            "mediation": "python_urllib,python_requests",
            "calls": [
                {
                    "hostname": "api.example.com",
                    "provider": "other",
                    "method": "POST",
                    "path": "/v1/messages",
                    "scheme": "https",
                    "status": 200,
                    "action": "OBSERVED",
                    "opticsStatus": "SUCCESS",
                    "applicationStatus": "SUCCESS",
                    "failure_kind": "none",
                    "ts": "2026-07-01T00:00:00.100000+00:00",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "6f1d7a2e.json"
            target.write_text(json.dumps(payload), encoding="utf-8")
            before = target.read_bytes()
            parsed = json.loads(before.decode("utf-8"))
            reading = adapt_copy(parsed)
            self.assertEqual(target.read_bytes(), before)
            self.assertEqual(parsed["calls"][0]["opticsStatus"], "SUCCESS")
            self.assertEqual(parsed["calls"][0]["ts"], "2026-07-01T00:00:00.100000+00:00")
            self.assertEqual(reading["canonical"]["optics_status"], "UNAVAILABLE")
            self.assertEqual(reading["mediation_reading"], "unknown")
            self.assertEqual(len(payload["calls"]), 1)
            self.assertIsNone(reading["events"])


if __name__ == "__main__":
    unittest.main()
