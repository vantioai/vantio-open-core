"""HTTP ok follows the status code, and the two Optics statuses stay separate."""
from __future__ import annotations

import json
import os
import socket
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from vantio import shield
from vantio._http_observe import (
    _application_status,
    _ok_for_http_status,
    _rollup_status,
)

from .mock_server import MockServer


class StatusMappingTests(unittest.TestCase):
    def test_http_status_sets_ok_and_application_outcome(self) -> None:
        self.assertTrue(_ok_for_http_status(200))
        self.assertTrue(_ok_for_http_status(302))
        self.assertFalse(_ok_for_http_status(400))
        self.assertFalse(_ok_for_http_status(401))
        self.assertFalse(_ok_for_http_status(429))
        self.assertFalse(_ok_for_http_status(500))
        self.assertFalse(_ok_for_http_status(None))
        self.assertEqual(_application_status(200), "SUCCESS")
        self.assertEqual(_application_status(399), "SUCCESS")
        self.assertEqual(_application_status(401), "APPLICATION_ERROR")
        self.assertEqual(_application_status(500), "APPLICATION_ERROR")
        self.assertEqual(_application_status(None), "UNAVAILABLE")
        self.assertEqual(_application_status(99), "UNAVAILABLE")

    def test_rollup_keeps_optics_separate_from_mixed_outcomes(self) -> None:
        optics, application = _rollup_status([{"status": 200}, {"status": 500}])
        self.assertEqual(optics, "SUCCESS")
        self.assertEqual(application, "PARTIAL")
        optics, application = _rollup_status([])
        self.assertEqual(optics, "NOT_OBSERVED")
        self.assertEqual(application, "NOT_OBSERVED")


class HttpOutcomeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._home = tempfile.mkdtemp()
        self._saved = {
            key: os.environ.get(key)
            for key in ("VANTIO_HOME", "VANTIO_EXTRA_LLM_HOSTS", "VANTIO_API_KEY", "VANTIO_INGEST_URL")
        }
        os.environ["VANTIO_HOME"] = self._home
        os.environ["VANTIO_EXTRA_LLM_HOSTS"] = "127.0.0.1"
        os.environ.pop("VANTIO_API_KEY", None)
        os.environ.pop("VANTIO_INGEST_URL", None)

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _log(self, trace_id: str) -> dict:
        path = Path(self._home) / "runs" / f"{trace_id}.json"
        self.assertTrue(path.is_file(), trace_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def _assert_application_error(self, call: dict, status: int, mediation: str) -> None:
        self.assertEqual(call["mediation"], mediation)
        self.assertEqual(call["status"], status)
        self.assertIs(call["ok"], False)
        self.assertNotEqual(call.get("error"), "network_error")
        self.assertNotIn("error", call)
        self.assertEqual(call["opticsStatus"], "SUCCESS")
        self.assertEqual(call["applicationStatus"], "APPLICATION_ERROR")
        self.assertEqual(call["opticsLabel"], "Successful")
        self.assertEqual(call["applicationLabel"], "Application error")

    def _assert_success(self, call: dict, status: int) -> None:
        self.assertEqual(call["status"], status)
        self.assertIs(call["ok"], True)
        self.assertEqual(call["opticsStatus"], "SUCCESS")
        self.assertEqual(call["applicationStatus"], "SUCCESS")
        self.assertEqual(call["opticsLabel"], "Successful")
        self.assertEqual(call["applicationLabel"], "Successful")

    def _assert_log_labels(self, data: dict, application: str) -> None:
        self.assertEqual(data["status_labels"]["opticsStatus"], "Optics status")
        self.assertEqual(data["status_labels"]["applicationStatus"], "Application outcome")
        self.assertEqual(data["summary"]["opticsStatus"], "SUCCESS")
        self.assertEqual(data["summary"]["applicationStatus"], application)

    async def test_urlopen_http_error_is_an_application_outcome(self) -> None:
        for status in (404, 500):
            trace = f"py-urlopen-{status}"
            with MockServer() as server:
                server.respond_with(status, {"err": True})
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    async with shield(trace_id=trace):
                        urllib.request.urlopen(server.url + "/v1/chat", timeout=2)
                self.assertEqual(raised.exception.code, status)
            data = self._log(trace)
            calls = [c for c in data["calls"] if c.get("mediation") == "python_urllib"]
            self.assertEqual(len(calls), 1)
            self._assert_application_error(calls[0], status, "python_urllib")
            self._assert_log_labels(data, "APPLICATION_ERROR")

    async def test_urlopen_200_is_ok(self) -> None:
        with MockServer() as server:
            server.respond_with(200, {"ok": True})
            async with shield(trace_id="py-urlopen-200"):
                urllib.request.urlopen(server.url + "/v1/chat", timeout=2)
        data = self._log("py-urlopen-200")
        calls = [c for c in data["calls"] if c.get("mediation") == "python_urllib"]
        self.assertEqual(len(calls), 1)
        self._assert_success(calls[0], 200)
        self._assert_log_labels(data, "SUCCESS")

    async def test_opener_http_error_is_an_application_outcome(self) -> None:
        opener = urllib.request.build_opener()
        with MockServer() as server:
            server.respond_with(401, {"err": True})
            with self.assertRaises(urllib.error.HTTPError):
                async with shield(trace_id="py-opener-401"):
                    opener.open(server.url + "/v1/chat", timeout=2)
        data = self._log("py-opener-401")
        calls = [c for c in data["calls"] if c.get("mediation") == "python_urllib"]
        self.assertEqual(len(calls), 1)
        self._assert_application_error(calls[0], 401, "python_urllib")

    async def test_urlopen_connection_refused_stays_network_error(self) -> None:
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        port = int(probe.getsockname()[1])
        probe.close()
        with self.assertRaises(urllib.error.URLError):
            async with shield(trace_id="py-urlopen-down"):
                urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/chat", timeout=2)
        data = self._log("py-urlopen-down")
        calls = [c for c in data["calls"] if c.get("mediation") == "python_urllib"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["error"], "network_error")
        self.assertIs(calls[0]["ok"], False)
        self.assertEqual(calls[0]["opticsStatus"], "SUCCESS")
        self.assertEqual(calls[0]["applicationStatus"], "UNAVAILABLE")
        self.assertEqual(calls[0]["applicationLabel"], "Unavailable")

    async def test_requests_http_errors_are_not_ok(self) -> None:
        try:
            import requests
        except ImportError:
            self.skipTest("requests is not installed")
        for status in (200, 302, 401, 429, 500):
            trace = f"py-requests-{status}"
            with MockServer() as server:
                server.respond_with(status, {"err": status >= 400})
                async with shield(trace_id=trace):
                    resp = requests.get(server.url + "/v1/chat", timeout=2, allow_redirects=False)
                self.assertEqual(resp.status_code, status)
            call = self._log(trace)["calls"][0]
            self.assertEqual(call["mediation"], "python_requests")
            if status >= 400:
                self._assert_application_error(call, status, "python_requests")
            else:
                self._assert_success(call, status)

    async def test_httpx_sync_and_async_http_errors_are_not_ok(self) -> None:
        try:
            import httpx
        except ImportError:
            self.skipTest("httpx is not installed")
        for status in (401, 500):
            trace = f"py-httpx-sync-{status}"
            with MockServer() as server:
                server.respond_with(status, {"err": True})
                async with shield(trace_id=trace):
                    with httpx.Client(timeout=2) as client:
                        resp = client.get(server.url + "/v1/chat")
                self.assertEqual(resp.status_code, status)
            self._assert_application_error(self._log(trace)["calls"][0], status, "python_httpx")
            trace = f"py-httpx-async-{status}"
            with MockServer() as server:
                server.respond_with(status, {"err": True})
                async with shield(trace_id=trace):
                    async with httpx.AsyncClient(timeout=2) as client:
                        resp = await client.get(server.url + "/v1/chat")
                self.assertEqual(resp.status_code, status)
            self._assert_application_error(self._log(trace)["calls"][0], status, "python_httpx")

    async def test_aiohttp_http_error_is_not_ok(self) -> None:
        try:
            import aiohttp
        except ImportError:
            self.skipTest("aiohttp is not installed")
        with MockServer() as server:
            server.respond_with(503, {"err": True})
            async with shield(trace_id="py-aiohttp-503"):
                async with aiohttp.ClientSession() as session:
                    async with session.get(server.url + "/v1/chat") as resp:
                        self.assertEqual(resp.status, 503)
                        await resp.read()
        self._assert_application_error(self._log("py-aiohttp-503")["calls"][0], 503, "python_aiohttp")

    async def test_urllib3_http_error_is_not_ok(self) -> None:
        try:
            import urllib3
        except ImportError:
            self.skipTest("urllib3 is not installed")
        with MockServer() as server:
            server.respond_with(500, {"err": True})
            async with shield(trace_id="py-urllib3-500"):
                http = urllib3.PoolManager()
                resp = http.request("GET", server.url + "/v1/chat", timeout=2.0, retries=False)
                self.assertEqual(resp.status, 500)
        calls = [
            c for c in self._log("py-urllib3-500")["calls"] if c.get("mediation") == "python_urllib3"
        ]
        self.assertEqual(len(calls), 1)
        self._assert_application_error(calls[0], 500, "python_urllib3")


class CustomerSurfaceTests(unittest.TestCase):
    def test_readme_keeps_the_locked_contract_and_drops_stale_onboarding(self) -> None:
        readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
        lowered = readme.lower()
        self.assertIn("Optics status", readme)
        self.assertIn("Application outcome", readme)
        self.assertIn("VANTIO_TELEMETRY=1", readme)
        self.assertIn("VANTIO_TELEMETRY_DISABLED=1", readme)
        self.assertIn("DO_NOT_TRACK=1", readme)
        self.assertIn("separately provisioned", readme)
        for stale in ("stripe", "trial key", "vantio login", "dashboard", "whoami"):
            self.assertNotIn(stale, lowered)
