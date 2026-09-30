"""P2/P3 audit cases: bad ingest URL, separate concurrent records, ingest shape."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
import urllib.request
from pathlib import Path

from tests.mock_server import MockServer
from vantio import shield


class IngestAndConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._home = tempfile.mkdtemp()
        self._saved = {
            key: os.environ.get(key)
            for key in (
                "VANTIO_HOME",
                "VANTIO_EXTRA_LLM_HOSTS",
                "VANTIO_API_KEY",
                "VANTIO_INGEST_URL",
                "VANTIO_AUDIT_MODE",
            )
        }
        os.environ["VANTIO_HOME"] = self._home
        os.environ["VANTIO_EXTRA_LLM_HOSTS"] = "127.0.0.1"

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    async def test_bad_ingest_url_with_a_key_fails_closed_out_loud(self) -> None:
        os.environ["VANTIO_API_KEY"] = "vk_test_dummy"
        os.environ["VANTIO_INGEST_URL"] = "not a url"
        with MockServer() as server:
            async with shield(trace_id="bad-ingest"):
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    urllib.request.urlopen(server.url + "/v1/chat", timeout=2)
            self.assertEqual(raised.exception.code, 403)
            self.assertIn(b"enforcement_closed", raised.exception.read())
            self.assertEqual([r for r in server.requests if r.path == "/v1/chat"], [])
        log = json.loads((Path(self._home) / "runs" / "bad-ingest.json").read_text(encoding="utf-8"))
        self.assertEqual(log["calls"][0]["action"], "ENFORCEMENT_CLOSED")

    async def test_concurrent_shields_write_separate_records(self) -> None:
        os.environ.pop("VANTIO_API_KEY", None)
        os.environ.pop("VANTIO_INGEST_URL", None)

        async def one(trace: str, url: str) -> None:
            async with shield(trace_id=trace):
                urllib.request.urlopen(url, timeout=2)
                await asyncio.sleep(0.05)

        with MockServer() as server:
            server.respond_with(200, {"ok": True})
            url = server.url + "/v1/chat"
            await asyncio.gather(one("trace-a", url), one("trace-b", url))
        runs = Path(self._home) / "runs"
        files = list(runs.glob("*.json"))
        ids = {json.loads(path.read_text(encoding="utf-8"))["trace_id"] for path in files}
        self.assertEqual(ids, {"trace-a", "trace-b"})
        for path in files:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(data["calls"]), 1)
            self.assertEqual(data["calls"][0]["trace_id"] if "trace_id" in data["calls"][0] else data["trace_id"], data["trace_id"])

    async def test_python_ingest_sends_trace_id_and_audit_mode(self) -> None:
        os.environ["VANTIO_API_KEY"] = "vk_test_dummy"
        os.environ["VANTIO_AUDIT_MODE"] = "1"
        seen = []
        with MockServer() as server:
            os.environ["VANTIO_INGEST_URL"] = server.url

            def handler(req):
                if req.path.startswith("/api/v1/config"):
                    body = {
                        "tier": "PRO",
                        "policy": {
                            "enforce": True,
                            "blocked_hosts": ["127.0.0.1"],
                            "allowed_hosts": [],
                            "dry_run": False,
                        },
                    }
                    return 200, json.dumps(body).encode("utf-8")
                if req.path.startswith("/api/v1/ingest"):
                    seen.append(req.json)
                    return 200, b"{}"
                return 200, b"{}"

            server.respond_with_handler(handler)
            with self.assertRaises(urllib.error.HTTPError):
                async with shield(trace_id="ingest-trace"):
                    urllib.request.urlopen(server.url + "/v1/target", timeout=2)
        self.assertTrue(seen)
        self.assertEqual(seen[0]["traceId"], "ingest-trace")
        self.assertIs(seen[0]["auditMode"], True)
