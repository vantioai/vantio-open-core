"""Observation bugs: http.client pending, worker-thread records, ingest URL path."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from vantio import shield


class _Server(HTTPServer):
    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.startswith("/boom"):
            self.connection.close()
            return
        body = b"ok"
        self.send_response(201)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        return


class ObserveBugTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._home = tempfile.mkdtemp()
        self._saved = {k: os.environ.get(k) for k in ("VANTIO_HOME", "VANTIO_EXTRA_LLM_HOSTS", "VANTIO_API_KEY", "VANTIO_INGEST_URL")}
        os.environ["VANTIO_HOME"] = self._home
        os.environ["VANTIO_EXTRA_LLM_HOSTS"] = "127.0.0.1"
        os.environ.pop("VANTIO_API_KEY", None)
        os.environ.pop("VANTIO_INGEST_URL", None)
        self._server = _Server()
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def tearDown(self) -> None:
        self._server.shutdown()
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    async def test_getresponse_throw_clears_pending_and_does_not_attach_the_next_status(self) -> None:
        import http.client

        port = self._server.server_address[1]
        async with shield(trace_id="http-pending"):
            boom = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
            boom.request("GET", "/boom")
            with self.assertRaises(Exception):
                boom.getresponse()
            self.assertIsNone(getattr(boom, "_vantio_pending", None))
            ok = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
            ok.request("GET", "/ok")
            resp = ok.getresponse()
            self.assertEqual(resp.status, 201)
            resp.read()
        log = json.loads((Path(self._home) / "runs" / "http-pending.json").read_text(encoding="utf-8"))
        by_path = {c.get("path"): c for c in log["calls"]}
        self.assertEqual(by_path["/ok"]["status"], 201)
        boom_call = by_path.get("/boom")
        if boom_call is not None:
            self.assertNotEqual(boom_call.get("status"), 201)

    async def test_worker_thread_call_reaches_the_shield_record(self) -> None:
        port = self._server.server_address[1]
        url = f"http://127.0.0.1:{port}/ok"

        async def main() -> None:
            async with shield(trace_id="worker-trace"):
                box: dict[str, object] = {}

                def work() -> None:
                    urllib.request.urlopen(url, timeout=2).read()
                    box["ok"] = True

                thread = threading.Thread(target=work)
                thread.start()
                thread.join(timeout=3)
                urllib.request.urlopen(url, timeout=2).read()
                self.assertTrue(box.get("ok"))

        await main()
        log = json.loads((Path(self._home) / "runs" / "worker-trace.json").read_text(encoding="utf-8"))
        self.assertEqual(log["trace_id"], "worker-trace")
        self.assertGreaterEqual(len(log["calls"]), 2)


if __name__ == "__main__":
    unittest.main()
