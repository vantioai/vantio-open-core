import os
import tempfile
import time
import unittest

from vantio import _telemetry
from vantio._telemetry import is_telemetry_disabled, send_run_telemetry_once, send_telemetry

from .mock_server import MockServer


_TELEMETRY_ENV = ("VANTIO_TELEMETRY", "VANTIO_TELEMETRY_DISABLED", "DO_NOT_TRACK")


class TelemetryDisabledTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = {k: os.environ.get(k) for k in _TELEMETRY_ENV}
        for k in self._saved:
            os.environ.pop(k, None)

    def tearDown(self) -> None:
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_disabled_by_default(self) -> None:
        self.assertTrue(is_telemetry_disabled())

    def test_enabled_only_when_opted_in(self) -> None:
        os.environ["VANTIO_TELEMETRY"] = "1"
        self.assertFalse(is_telemetry_disabled())

    def test_true_when_vantio_telemetry_disabled(self) -> None:
        os.environ["VANTIO_TELEMETRY_DISABLED"] = "1"
        self.assertTrue(is_telemetry_disabled())

    def test_true_when_do_not_track(self) -> None:
        os.environ["DO_NOT_TRACK"] = "1"
        self.assertTrue(is_telemetry_disabled())

    def test_disabled_overrides_opt_in(self) -> None:
        os.environ["VANTIO_TELEMETRY"] = "1"
        os.environ["VANTIO_TELEMETRY_DISABLED"] = "1"
        self.assertTrue(is_telemetry_disabled())

    def test_do_not_track_overrides_opt_in(self) -> None:
        os.environ["VANTIO_TELEMETRY"] = "1"
        os.environ["DO_NOT_TRACK"] = "1"
        self.assertTrue(is_telemetry_disabled())


class SendTelemetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._saved = {
            k: os.environ.get(k)
            for k in ("HOME", "VANTIO_INGEST_URL", *_TELEMETRY_ENV)
        }
        os.environ["HOME"] = self._tmpdir.name
        for k in _TELEMETRY_ENV:
            os.environ.pop(k, None)

    def tearDown(self) -> None:
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._tmpdir.cleanup()

    def test_does_not_send_unless_opted_in(self) -> None:
        with MockServer() as server:
            os.environ["VANTIO_INGEST_URL"] = server.url
            send_telemetry(event="run", hosts=["api.openai.com"], call_count=1)
            time.sleep(0.3)
            self.assertEqual(len(server.requests), 0)

    def test_posts_only_the_allowlisted_fields(self) -> None:
        with MockServer() as server:
            server.respond_with(202, {"ok": True})
            os.environ["VANTIO_INGEST_URL"] = server.url
            os.environ["VANTIO_TELEMETRY"] = "1"

            send_telemetry(
                event="run",
                hosts=["api.openai.com"],
                call_count=3,
                sdk_version="3.0.0",
                # Not on the whitelist — must never reach the wire.
                framework=None,
            )
            time.sleep(0.3)  # send_telemetry fires on a background daemon thread.

            self.assertEqual(len(server.requests), 1)
            req = server.requests[0]
            self.assertEqual(req.path, "/api/v1/telemetry")
            body = req.json
            self.assertEqual(body["event"], "run")
            self.assertEqual(body["hosts"], ["api.openai.com"])
            self.assertEqual(body["callCount"], 3)
            self.assertEqual(body["runtime"], "python")
            self.assertEqual(body["sdkVersion"], "3.0.0")
            self.assertIn("anonymousId", body)
            self.assertNotIn("framework", body)

    def test_never_sends_anything_when_disabled(self) -> None:
        with MockServer() as server:
            os.environ["VANTIO_INGEST_URL"] = server.url
            os.environ["VANTIO_TELEMETRY"] = "1"
            os.environ["VANTIO_TELEMETRY_DISABLED"] = "1"
            send_telemetry(event="run")
            time.sleep(0.3)
            self.assertEqual(len(server.requests), 0)

    def test_do_not_track_overrides_opt_in_on_the_wire(self) -> None:
        with MockServer() as server:
            os.environ["VANTIO_INGEST_URL"] = server.url
            os.environ["VANTIO_TELEMETRY"] = "1"
            os.environ["DO_NOT_TRACK"] = "1"
            send_telemetry(event="run")
            time.sleep(0.3)
            self.assertEqual(len(server.requests), 0)

    def test_never_raises_when_the_endpoint_is_unreachable(self) -> None:
        os.environ["VANTIO_TELEMETRY"] = "1"
        os.environ["VANTIO_INGEST_URL"] = "http://127.0.0.1:1"
        try:
            send_telemetry(event="run")
        except Exception as exc:  # pragma: no cover - failure path
            self.fail(f"send_telemetry() must never raise, got: {exc}")

    def test_anonymous_id_persists_across_calls(self) -> None:
        with MockServer() as server:
            server.respond_with(202, {"ok": True})
            os.environ["VANTIO_INGEST_URL"] = server.url
            os.environ["VANTIO_TELEMETRY"] = "1"
            send_telemetry(event="run")
            time.sleep(0.3)
            send_telemetry(event="summary")
            time.sleep(0.3)
            self.assertEqual(len(server.requests), 2)
            first_id = server.requests[0].json["anonymousId"]
            second_id = server.requests[1].json["anonymousId"]
            self.assertEqual(first_id, second_id)


class SendRunTelemetryOnceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._saved = {k: os.environ.get(k) for k in ("HOME", "VANTIO_INGEST_URL", *_TELEMETRY_ENV)}
        os.environ["HOME"] = self._tmpdir.name
        for k in _TELEMETRY_ENV:
            os.environ.pop(k, None)
        # This module-level flag is process-global by design (one ping per
        # process) — reset it directly so each test starts from a clean slate.
        _telemetry._sent_once = False

    def tearDown(self) -> None:
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        _telemetry._sent_once = False
        self._tmpdir.cleanup()

    def test_only_sends_once_per_process(self) -> None:
        with MockServer() as server:
            server.respond_with(202, {"ok": True})
            os.environ["VANTIO_INGEST_URL"] = server.url
            os.environ["VANTIO_TELEMETRY"] = "1"

            send_run_telemetry_once()
            send_run_telemetry_once()
            send_run_telemetry_once()
            time.sleep(0.3)

            self.assertEqual(len(server.requests), 1)
            body = server.requests[0].json
            self.assertEqual(body["event"], "run")
            # shield() sends this ping before HTTP observations exist.
            self.assertEqual(body["callCount"], 0)
            self.assertEqual(body["hosts"], [])


if __name__ == "__main__":
    unittest.main()
