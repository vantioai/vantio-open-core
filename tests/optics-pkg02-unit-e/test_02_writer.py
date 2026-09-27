"""Future writer record delta and shared canonical bytes."""

import copy
import json
import sys
import unittest

from support import SHARED_FIXTURE, forbidden_names, load_json, node_adapter_canonical, node_canonical

from vantio_future import (  # noqa: E402
    ACTIVATES_UNIT_D,
    ACTIVATES_UNIT_E,
    CLAIMED_CPYTHON,
    CLASSIFICATION,
    FUTURE_VERSION,
    NEVER_VEHICLE_VERSION,
    PRODUCER,
    REGISTRY_PUBLISH,
    RUNTIME,
    SCHEMA_VERSION,
    SEALED_PYTHON_VERSION,
    UNICODE_PROFILE_ID,
    seal_event,
)
from vantio_future.contract_bridge import canonical_json  # noqa: E402
from vantio_future.writer import assemble_canonical  # noqa: E402


def _raw(http_status, mediation):
    return {
        "destination_host": "api.example.com",
        "duration_ms": 4,
        "http_status": http_status,
        "mediation": mediation,
        "method": "GET",
        "optics_status": "OBSERVED",
        "path": "/v1/messages",
        "scheme": "https",
        "started_at": "2026-07-01T00:00:00.100Z",
    }


class WriterDeltaTests(unittest.TestCase):
    def test_identity_is_the_future_line(self):
        self.assertEqual(FUTURE_VERSION, "PKG02-FUTURE-PYTHON-UNASSIGNED")
        self.assertNotEqual(FUTURE_VERSION, SEALED_PYTHON_VERSION)
        self.assertNotEqual(FUTURE_VERSION, NEVER_VEHICLE_VERSION)
        self.assertEqual(SEALED_PYTHON_VERSION, "3.1.0")
        self.assertEqual(NEVER_VEHICLE_VERSION, "3.0.15")
        self.assertTrue(ACTIVATES_UNIT_E)
        self.assertFalse(ACTIVATES_UNIT_D)
        self.assertFalse(REGISTRY_PUBLISH)
        self.assertEqual(CLASSIFICATION, "OPTICS_PKG02_UNIT_E_READY_FOR_COUNCIL")
        self.assertEqual(CLAIMED_CPYTHON, "3.12")
        self.assertEqual(sys.version_info[:2], (3, 12))
        self.assertEqual(PRODUCER, "python_observe")
        self.assertEqual(RUNTIME, "python")
        self.assertEqual(SCHEMA_VERSION, 0)
        self.assertEqual(UNICODE_PROFILE_ID, "PKG01-UCD-16.0.0")

    def test_missing_and_success_optics_become_unavailable(self):
        missing = seal_event(
            {
                "destination_host": "api.example.com",
                "http_status": 404,
                "mediation": "python_urllib",
                "method": "GET",
                "path": "/v1/messages",
                "scheme": "https",
                "started_at": "2026-07-01T00:00:00.100Z",
            }
        )
        self.assertEqual(missing["optics_status"], "UNAVAILABLE")
        success = seal_event(
            {
                "destination_host": "api.example.com",
                "http_status": 200,
                "mediation": "python_urllib",
                "opticsStatus": "SUCCESS",
                "path": "/v1/messages",
                "scheme": "https",
                "started_at": "2026-07-01T00:00:00.100Z",
            }
        )
        self.assertEqual(success["optics_status"], "UNAVAILABLE")
        self.assertNotIn("opticsStatus", success)

    def test_shared_fixture_matches_node_adapter_bytes(self):
        fixture = load_json(SHARED_FIXTURE)
        before = copy.deepcopy(fixture)
        record = seal_event(fixture)
        self.assertEqual(fixture, before)
        python_bytes = canonical_json(record)
        self.assertEqual(python_bytes, node_canonical(record))
        self.assertEqual(python_bytes, node_adapter_canonical(fixture))
        self.assertEqual(record["runtime"], "python")
        self.assertEqual(record["producer"], "python_observe")
        self.assertEqual(record["schema_version"], 0)
        self.assertEqual(record["optics_status"], "OBSERVED")
        self.assertEqual(record["application_status"], "APPLICATION_ERROR")
        self.assertEqual(record["http_status"], 404)
        self.assertEqual(record["started_at"], "2026-07-01T00:00:00.100Z")
        self.assertNotIn("response_bytes", record)
        self.assertNotIn("provider_id", record)
        self.assertNotIn("workflow", record)

    def test_response_bytes_zero_stays_and_missing_is_omitted(self):
        explicit = seal_event(
            {
                "destination_host": "api.example.com",
                "http_status": 200,
                "mediation": "python_urllib",
                "optics_status": "OBSERVED",
                "response_bytes": 0,
                "scheme": "https",
                "started_at": "2026-07-01T00:00:00.100Z",
            }
        )
        self.assertEqual(explicit["response_bytes"], 0)
        omitted = seal_event(
            {
                "destination_host": "api.example.com",
                "http_status": 200,
                "mediation": "python_urllib",
                "optics_status": "OBSERVED",
                "scheme": "https",
                "started_at": "2026-07-01T00:00:00.100Z",
            }
        )
        self.assertNotIn("response_bytes", omitted)

    def test_duration_is_omitted_when_it_was_not_measured(self):
        bundle = assemble_canonical(
            "unit-e-no-duration",
            "2026-07-01T00:00:00.100Z",
            "2026-07-01T00:00:00.100Z",
            None,
            [],
            0,
        )
        self.assertNotIn("duration_ms", bundle["envelope"])
        self.assertEqual(bundle["optics_status"], "NOT_OBSERVED")
        self.assertEqual(bundle["events"], [])
        self.assertEqual(bundle["unicode_profile_id"], "PKG01-UCD-16.0.0")
        self.assertEqual(bundle["compatibility"]["legacy_schema_version"], 2)
        self.assertEqual(bundle["envelope"]["schema_version"], 0)
        self.assertEqual(forbidden_names(bundle), [])

    def test_mixed_application_tokens_use_lifecycle_partial(self):
        bundle = assemble_canonical(
            "unit-e-mixed",
            "2026-07-01T00:00:00.100Z",
            "2026-07-01T00:00:00.200Z",
            100,
            [_raw(200, "python_urllib"), _raw(404, "python_subprocess")],
            2,
        )
        self.assertEqual(bundle["envelope"]["lifecycle"], "PARTIAL")
        self.assertNotIn("application_status", bundle["envelope"])
        statuses = [event["application_status"] for event in bundle["events"]]
        self.assertEqual(statuses, ["SUCCESS", "APPLICATION_ERROR"])
        self.assertNotIn("PARTIAL", statuses)
        mediations = [event["mediation"] for event in bundle["events"]]
        self.assertEqual(mediations, ["python_urllib", "python_subprocess"])
        self.assertFalse(any("," in item for item in mediations))
        self.assertNotIn("mediation", bundle["envelope"])
        self.assertEqual(bundle["optics_status"], "OBSERVED")

    def test_provider_prompt_and_rejected_unicode_are_not_stored(self):
        clean = {
            "destination_host": "api.example.com",
            "http_status": 200,
            "mediation": "python_urllib",
            "optics_status": "OBSERVED",
            "scheme": "https",
            "started_at": "2026-07-01T00:00:00.100Z",
        }
        self.assertIsNone(seal_event({**clean, "provider": "other"}))
        self.assertIsNone(seal_event({**clean, "prompt": "CANARY_PROMPT_TEXT"}))
        rejected = seal_event({**clean, "destination_host": "bad\u0379.example"})
        blob = "" if rejected is None else canonical_json(rejected)
        self.assertNotIn("\u0379", blob)
        self.assertNotIn("CANARY_PROMPT_TEXT", blob)
        if rejected is not None:
            self.assertNotEqual(rejected.get("destination_host"), "bad\u0379.example")

    def test_failure_kind_is_kept_for_a_seen_socket_outcome(self):
        record = seal_event(
            {
                "application_status": "UNAVAILABLE",
                "destination_host": "127.0.0.1",
                "destination_port": 9,
                "error_class": "ConnectionRefusedError",
                "failure_kind": "connection",
                "mediation": "python_socket",
                "optics_status": "OBSERVED",
                "scheme": "unknown",
                "started_at": "2026-07-01T00:00:00.100Z",
            }
        )
        self.assertEqual(record["failure_kind"], "connection")
        self.assertEqual(record["error_class"], "ConnectionRefusedError")
        self.assertEqual(record["optics_status"], "OBSERVED")
        self.assertEqual(record["application_status"], "UNAVAILABLE")
        self.assertEqual(record["issue_location"], "NETWORK")
        self.assertNotIn("response_bytes", record)
        self.assertNotIn("Connection refused", json.dumps(record))


if __name__ == "__main__":
    unittest.main()
