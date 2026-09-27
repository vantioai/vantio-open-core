"""Ordinary-client proof for the future shield."""

import json
import os
import socket
import subprocess
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from support import LoopbackServer, forbidden_names

from vantio_future import async_http_get, force_reset, reset_writer_mode, shield


class OrdinaryClientTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._home = tempfile.TemporaryDirectory()
        self._saved = {
            key: os.environ.get(key)
            for key in ("VANTIO_HOME", "VANTIO_EXTRA_LLM_HOSTS", "VANTIO_PKG02_PYTHON_WRITER")
        }
        os.environ["VANTIO_HOME"] = self._home.name
        os.environ["VANTIO_EXTRA_LLM_HOSTS"] = "127.0.0.1"
        os.environ.pop("VANTIO_PKG02_PYTHON_WRITER", None)
        reset_writer_mode()
        force_reset()

    def tearDown(self):
        force_reset()
        reset_writer_mode()
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._home.cleanup()

    def _bundle(self, trace_id):
        path = Path(self._home.name) / "runs" / f"{trace_id}.json"
        self.assertTrue(path.is_file(), trace_id)
        return json.loads(path.read_text(encoding="utf-8")), path

    def _assert_seen(self, bundle, mediation):
        self.assertEqual(bundle["runtime"], "python")
        self.assertEqual(bundle["producer"], "python_observe")
        self.assertEqual(bundle["schema_version"], 0)
        self.assertEqual(bundle["schema_status"], "unstable-pre-1.0")
        self.assertEqual(bundle["compatibility"]["legacy_schema_version"], 2)
        self.assertEqual(bundle["unicode_profile_id"], "PKG01-UCD-16.0.0")
        self.assertEqual(bundle["optics_status"], "OBSERVED")
        self.assertEqual(bundle["envelope"]["schema_version"], 0)
        self.assertEqual(bundle["envelope"]["runtime"], "python")
        self.assertEqual(bundle["envelope"]["producer"], "python_observe")
        self.assertRegex(bundle["envelope"]["started_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
        self.assertRegex(bundle["envelope"]["ended_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
        self.assertIsInstance(bundle["envelope"]["duration_ms"], int)
        self.assertEqual(forbidden_names(bundle), [])
        self.assertEqual(len(bundle["events"]), 1)
        event = bundle["events"][0]
        self.assertEqual(event["mediation"], mediation)
        self.assertNotIn(",", event["mediation"])
        self.assertEqual(event["optics_status"], "OBSERVED")
        self.assertNotEqual(event["optics_status"], "SUCCESS")
        self.assertNotEqual(event.get("application_status"), "PARTIAL")
        self.assertRegex(event["started_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
        self.assertIsInstance(event["duration_ms"], int)
        return event

    async def test_urllib_http_4xx_omits_missing_size(self):
        with LoopbackServer(404) as base:
            with self.assertRaises(urllib.error.HTTPError) as raised:
                async with shield(trace_id="unit-e-urllib-404"):
                    urllib.request.urlopen(base + "/v1/chat", timeout=2)
            raised.exception.close()
        bundle, _path = self._bundle("unit-e-urllib-404")
        event = self._assert_seen(bundle, "python_urllib")
        self.assertEqual(event["http_status"], 404)
        self.assertEqual(event["application_status"], "APPLICATION_ERROR")
        self.assertEqual(event["issue_location"], "PROVIDER_INTERACTION")
        self.assertNotIn("response_bytes", event)
        text = json.dumps(bundle)
        self.assertNotIn("Not Found", text)
        self.assertNotIn("HTTP Error", text)

    async def test_asyncio_client_records_after_completion(self):
        with LoopbackServer(404) as base:
            async with shield(trace_id="unit-e-async-404"):
                body = await async_http_get(base + "/v1/async")
        self.assertIsInstance(body, bytes)
        bundle, _path = self._bundle("unit-e-async-404")
        event = self._assert_seen(bundle, "python_http_client")
        self.assertEqual(event["http_status"], 404)
        self.assertEqual(event["application_status"], "APPLICATION_ERROR")
        self.assertEqual(event["lifecycle"], "COMPLETE")
        self.assertNotIn("response_bytes", event)

    async def test_socket_failure_keeps_failure_kind(self):
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        with self.assertRaises(ConnectionRefusedError):
            async with shield(trace_id="unit-e-socket"):
                socket.create_connection(("127.0.0.1", port), timeout=0.5)
        bundle, _path = self._bundle("unit-e-socket")
        event = self._assert_seen(bundle, "python_socket")
        self.assertEqual(event["failure_kind"], "connection")
        self.assertEqual(event["error_class"], "ConnectionRefusedError")
        self.assertEqual(event["application_status"], "UNAVAILABLE")
        self.assertEqual(event["issue_location"], "NETWORK")
        self.assertNotIn("http_status", event)
        self.assertNotIn("response_bytes", event)
        self.assertNotIn("Connection refused", json.dumps(bundle))

    async def test_empty_shield_is_not_observed(self):
        async with shield(trace_id="unit-e-empty"):
            pass
        bundle, _path = self._bundle("unit-e-empty")
        self.assertEqual(bundle["optics_status"], "NOT_OBSERVED")
        self.assertEqual(bundle["empty_shield"], "NOT_OBSERVED_ENVELOPE")
        self.assertEqual(bundle["events"], [])
        self.assertEqual(bundle["envelope"]["call_count"], 0)
        self.assertIsInstance(bundle["envelope"]["duration_ms"], int)
        self.assertNotIn("SUCCESS", json.dumps(bundle))
        self.assertEqual(forbidden_names(bundle), [])

    async def test_subprocess_size_omits_body_and_response_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            tool = Path(directory) / "curl"
            tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            tool.chmod(0o755)
            body = Path(directory) / "body.bin"
            body.write_bytes(b"CANARY_SUBPROCESS_BODY")
            async with shield(trace_id="unit-e-subprocess"):
                subprocess.run(
                    [str(tool), "--data-binary", "@" + str(body), "http://127.0.0.1/v1/size"],
                    check=False,
                )
        bundle, _path = self._bundle("unit-e-subprocess")
        event = self._assert_seen(bundle, "python_subprocess")
        self.assertEqual(event["request_bytes"], len(b"CANARY_SUBPROCESS_BODY"))
        self.assertNotIn("response_bytes", event)
        self.assertEqual(event["application_status"], "UNAVAILABLE")
        self.assertEqual(event["optics_status"], "OBSERVED")
        text = json.dumps(bundle)
        self.assertNotIn("CANARY_SUBPROCESS_BODY", text)
        self.assertNotIn(",", event["mediation"])


if __name__ == "__main__":
    unittest.main()
