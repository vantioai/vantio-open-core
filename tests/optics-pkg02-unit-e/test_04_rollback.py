"""Rollback keeps canonical files and restores the previous writer shape."""

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
import urllib.request
from pathlib import Path

from support import LoopbackServer, ROOT, SDK_31

from vantio_future import force_reset, read_rolled_back, reset_writer_mode, set_writer_mode, shield
from vantio_future import writer as writer_module


class RollbackTests(unittest.IsolatedAsyncioTestCase):
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

    def _path(self, trace_id):
        return Path(self._home.name) / "runs" / f"{trace_id}.json"

    async def test_disable_writer_uses_previous_shape_and_keeps_canonical_file(self):
        with LoopbackServer(200) as base:
            async with shield(trace_id="unit-e-canonical"):
                response = urllib.request.urlopen(base + "/v1/chat", timeout=2)
                response.read()
                response.close()
            canonical_path = self._path("unit-e-canonical")
            before = canonical_path.read_bytes()
            canonical = json.loads(before.decode("utf-8"))
            self.assertEqual(canonical["schema_version"], 0)
            self.assertEqual(canonical["producer"], "python_observe")
            self.assertEqual(canonical["events"][0]["optics_status"], "OBSERVED")
            self.assertEqual(canonical["events"][0]["evidence_origin"], "LOCAL_OBSERVATION")
            set_writer_mode("legacy")
            async with shield(trace_id="unit-e-legacy"):
                response = urllib.request.urlopen(base + "/v1/chat", timeout=2)
                response.read()
                response.close()
            async with shield(trace_id="unit-e-legacy-empty"):
                pass
        self.assertEqual(canonical_path.read_bytes(), before)
        self.assertFalse(self._path("unit-e-legacy-empty").is_file())
        legacy = json.loads(self._path("unit-e-legacy").read_text(encoding="utf-8"))
        self.assertEqual(legacy["vantio_run_log"], "1")
        self.assertEqual(legacy["schema_version"], 2)
        self.assertEqual(legacy["workflow"], "sight_loop")
        self.assertEqual(legacy["runtime"], "python")
        self.assertNotIn("producer", legacy)
        self.assertEqual(legacy["calls"][0]["opticsStatus"], "SUCCESS")
        self.assertIn("+00:00", legacy["calls"][0]["ts"])
        self.assertNotIn("failure_kind", canonical["events"][0])
        reading = read_rolled_back(canonical_path)
        self.assertEqual(reading["optics_status"], "UNSUPPORTED")
        self.assertEqual(reading["schema_status"], "unstable-pre-1.0")
        self.assertEqual(reading["evidence_origin"], "LOCAL_OBSERVATION")
        self.assertFalse(reading["file_rewritten"])
        self.assertTrue(reading["bytes_unchanged"])
        self.assertEqual(canonical_path.read_bytes(), before)
        self.assertNotEqual(reading["optics_status"], "SUCCESS")

    async def test_validation_failure_keeps_the_return_value(self):
        sentinel = {"kept": True}

        async def work():
            async with shield(trace_id="unit-e-fail-open"):
                return sentinel

        original = writer_module.validate_evidence

        def explode(_value):
            raise RuntimeError("validator down")

        writer_module.validate_evidence = explode
        try:
            result = await work()
        finally:
            writer_module.validate_evidence = original
        self.assertIs(result, sentinel)
        self.assertFalse(self._path("unit-e-fail-open").exists())
        self.assertNotIn("validator down", json.dumps(sentinel))

    def _sealed_canary_file(self):
        script = textwrap.dedent(
            """
            import asyncio
            import json
            import os
            import threading
            import urllib.request
            from http.server import BaseHTTPRequestHandler, HTTPServer
            from vantio import shield

            class Handler(BaseHTTPRequestHandler):
                protocol_version = "HTTP/1.0"

                def do_GET(self):
                    body = b"{}"
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

                def log_message(self, fmt, *args):
                    return

            server = HTTPServer(("127.0.0.1", 0), Handler)
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            query = "prompt=CANARY_PROMPT_TEXT&api_key=CANARY_API_KEY&token=sk-proj-abcdefghijklmnop"

            async def main():
                url = "http://127.0.0.1:%d/v1/messages?%s" % (port, query)
                async with shield(trace_id="sealed-canary"):
                    response = urllib.request.urlopen(url, timeout=5)
                    response.read()
                    response.close()

            try:
                asyncio.run(main())
            finally:
                server.shutdown()
            path = os.path.join(os.environ["VANTIO_HOME"], "runs", "sealed-canary.json")
            print(open(path, encoding="utf-8").read())
            """
        )
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            home.mkdir()
            env = os.environ.copy()
            env["PYTHONPATH"] = str(SDK_31)
            env["VANTIO_HOME"] = str(home)
            env["VANTIO_EXTRA_LLM_HOSTS"] = "127.0.0.1"
            env["VANTIO_TELEMETRY_DISABLED"] = "1"
            env["DO_NOT_TRACK"] = "1"
            env.pop("VANTIO_TELEMETRY", None)
            env.pop("VANTIO_API_KEY", None)
            env.pop("VANTIO_PKG02_PYTHON_WRITER", None)
            completed = subprocess.run(
                [sys.executable, "-c", script],
                cwd=str(ROOT),
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        return json.loads(completed.stdout)

    async def test_legacy_canary_query_matches_sealed_path_and_summary(self):
        query = "prompt=CANARY_PROMPT_TEXT&api_key=CANARY_API_KEY&token=sk-proj-abcdefghijklmnop"
        needles = (
            "CANARY_PROMPT_TEXT",
            "CANARY_API_KEY",
            "sk-proj-abcdefghijklmnop",
            "prompt=",
            "api_key=",
            "token=",
        )
        with LoopbackServer(200) as base:
            url = base + "/v1/messages?" + query
            async with shield(trace_id="unit-e-canary-canonical"):
                response = urllib.request.urlopen(url, timeout=2)
                response.read()
                response.close()
            async with shield(trace_id="unit-e-benign-canonical"):
                response = urllib.request.urlopen(base + "/v1/messages?foo=1", timeout=2)
                response.read()
                response.close()
            set_writer_mode("legacy")
            async with shield(trace_id="unit-e-canary-legacy"):
                response = urllib.request.urlopen(url, timeout=2)
                response.read()
                response.close()
        canonical_text = self._path("unit-e-canary-canonical").read_text(encoding="utf-8")
        canonical = json.loads(canonical_text)
        # A secret in the query makes the contract drop path. A query without a secret stays the path only.
        self.assertNotIn("path", canonical["events"][0])
        benign = json.loads(self._path("unit-e-benign-canonical").read_text(encoding="utf-8"))
        self.assertEqual(benign["events"][0]["path"], "/v1/messages")
        legacy_text = self._path("unit-e-canary-legacy").read_text(encoding="utf-8")
        legacy = json.loads(legacy_text)
        self.assertEqual(legacy["calls"][0]["path"], "/v1/messages")
        self.assertNotIn("?", legacy["calls"][0]["path"])
        for needle in needles:
            self.assertNotIn(needle, legacy_text)
            self.assertNotIn(needle, canonical_text)
        sealed = self._sealed_canary_file()
        self.assertEqual(sealed["calls"][0]["path"], "/v1/messages")
        self.assertEqual(legacy["calls"][0]["path"], sealed["calls"][0]["path"])
        self.assertEqual(legacy["summary"], sealed["summary"])
        self.assertNotIn("?", sealed["calls"][0]["path"])


if __name__ == "__main__":
    unittest.main()
