"""Step 1 and step 2 run before the future writer is treated as the active line.

The inert Unit C adapter stays unused during a sealed 3.1.0 shield. The run
file bytes stay the same. A missing optics status, including the SUCCESS token
the sealed tests still expect, becomes UNAVAILABLE on the adapter copy.
"""

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from support import ADAPTER_SRC, ROOT, SDK_31

SEALED_TEST = SDK_31 / "tests" / "test_optics_status.py"


class PrerequisiteTests(unittest.TestCase):
    def test_sealed_suite_still_expects_optics_success(self):
        text = SEALED_TEST.read_text(encoding="utf-8")
        self.assertIn('self.assertEqual(call["opticsStatus"], "SUCCESS")', text)
        self.assertIn('self.assertEqual(data["summary"]["opticsStatus"], "SUCCESS")', text)
        pyproject = (SDK_31 / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('version = "3.1.0"', pyproject)

    def test_adapter_present_and_unused_keeps_3_1_0_bytes(self):
        script = textwrap.dedent(
            """
            import asyncio
            import threading
            from http.server import BaseHTTPRequestHandler, HTTPServer
            import urllib.request
            import optics_python_adapter
            from vantio import shield

            assert optics_python_adapter.adapt_copy is not None

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

            async def main():
                async with shield(trace_id="unit-e-sealed-byte"):
                    urllib.request.urlopen("http://127.0.0.1:%d/" % port, timeout=5)

            try:
                asyncio.run(main())
            finally:
                server.shutdown()
            """
        )
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / "home"
            home.mkdir()
            env = os.environ.copy()
            env["PYTHONPATH"] = os.pathsep.join((str(SDK_31), str(ADAPTER_SRC)))
            env["VANTIO_HOME"] = str(home)
            env["VANTIO_EXTRA_LLM_HOSTS"] = "127.0.0.1"
            env["VANTIO_TELEMETRY_DISABLED"] = "1"
            env["DO_NOT_TRACK"] = "1"
            env.pop("VANTIO_TELEMETRY", None)
            env.pop("VANTIO_API_KEY", None)
            completed = subprocess.run(
                [sys.executable, "-c", script],
                cwd=str(ROOT),
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
            target = home / "runs" / "unit-e-sealed-byte.json"
            self.assertTrue(target.is_file())
            before = target.read_bytes()
            parsed = json.loads(before.decode("utf-8"))
            self.assertEqual(parsed["schema_version"], 2)
            self.assertEqual(parsed["runtime"], "python")
            self.assertEqual(parsed["calls"][0]["opticsStatus"], "SUCCESS")
            sys.path.insert(0, str(ADAPTER_SRC))
            from optics_python_adapter import adapt_copy

            reading = adapt_copy(parsed)
            self.assertEqual(target.read_bytes(), before)
            self.assertEqual(parsed["calls"][0]["opticsStatus"], "SUCCESS")
            self.assertEqual(reading["canonical"]["optics_status"], "UNAVAILABLE")
            self.assertIn("OPTIMISTIC_DEFAULT_FORBIDDEN", reading["reasons"])
            self.assertNotEqual(reading["canonical"]["optics_status"], "SUCCESS")

    def test_missing_optics_status_becomes_unavailable(self):
        sys.path.insert(0, str(ADAPTER_SRC))
        from optics_python_adapter import adapt_copy

        call = {
            "action": "OBSERVED",
            "applicationStatus": "APPLICATION_ERROR",
            "hostname": "api.example.com",
            "mediation": "python_urllib",
            "method": "GET",
            "path": "/v1/messages",
            "scheme": "https",
            "status": 404,
            "ts": "2026-07-01T00:00:00.100000+00:00",
        }
        missing = adapt_copy({"call": dict(call)})
        self.assertEqual(missing["optics_reading"], "UNAVAILABLE")
        self.assertEqual(missing["canonical"]["optics_status"], "UNAVAILABLE")
        self.assertNotEqual(missing["canonical"]["optics_status"], "SUCCESS")
        success = dict(call)
        success["opticsStatus"] = "SUCCESS"
        refused = adapt_copy({"call": success})
        self.assertEqual(refused["canonical"]["optics_status"], "UNAVAILABLE")
        self.assertIn("OPTIMISTIC_DEFAULT_FORBIDDEN", refused["reasons"])
        self.assertEqual(success["opticsStatus"], "SUCCESS")


if __name__ == "__main__":
    unittest.main()
