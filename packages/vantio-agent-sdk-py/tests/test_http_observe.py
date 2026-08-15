import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from vantio import shield
from vantio._http_observe import (
    _host_matches_regional,
    _in_scope,
    _is_control_plane_dest,
    _is_ollama_local,
)

from .mock_server import MockServer


class CatalogScopeTests(unittest.TestCase):
    def test_bedrock_regional_runtime_is_in_scope(self) -> None:
        self.assertTrue(_host_matches_regional("bedrock-runtime.us-east-1.amazonaws.com"))
        self.assertTrue(_in_scope("bedrock-runtime-fips.us-west-2.amazonaws.com"))
        self.assertTrue(_in_scope("bedrock-mantle.us-east-1.api.aws"))
        self.assertFalse(_in_scope("s3.us-east-1.amazonaws.com"))

    def test_vertex_regional_and_rep_are_in_scope(self) -> None:
        self.assertTrue(_in_scope("aiplatform.googleapis.com"))
        self.assertTrue(_in_scope("us-central1-aiplatform.googleapis.com"))
        self.assertTrue(_in_scope("aiplatform.us.rep.googleapis.com"))
        self.assertFalse(_in_scope("www.googleapis.com"))

    def test_new_inference_hosts(self) -> None:
        self.assertTrue(_in_scope("router.huggingface.co"))
        self.assertTrue(_in_scope("api-inference.huggingface.co"))
        self.assertTrue(_in_scope("my-ep.us-east-1.endpoints.huggingface.cloud"))
        self.assertFalse(_in_scope("huggingface.co"))
        self.assertTrue(_in_scope("api.replicate.com"))
        self.assertTrue(_in_scope("ollama.com"))
        self.assertTrue(_in_scope("integrate.api.nvidia.com"))

    def test_ollama_localhost_only_on_11434(self) -> None:
        self.assertTrue(_is_ollama_local("127.0.0.1", "11434"))
        self.assertTrue(_in_scope("localhost", "11434"))
        self.assertFalse(_in_scope("127.0.0.1", "80"))
        self.assertFalse(_in_scope("127.0.0.1"))


class ControlPlaneDestTests(unittest.TestCase):
    def test_ingest_host_port_passes_other_ports_do_not(self) -> None:
        os.environ["VANTIO_INGEST_URL"] = "http://127.0.0.1:8765"
        try:
            self.assertTrue(_is_control_plane_dest("127.0.0.1", "8765"))
            self.assertFalse(_is_control_plane_dest("127.0.0.1", "80"))
            self.assertFalse(_is_control_plane_dest("api.openai.com", "443"))
        finally:
            os.environ.pop("VANTIO_INGEST_URL", None)


class RequestsHttpxObserveTests(unittest.IsolatedAsyncioTestCase):
    async def test_requests_to_extra_host_writes_run_log(self) -> None:
        try:
            import requests
        except ImportError:
            self.skipTest("requests is not installed")
        home = tempfile.mkdtemp()
        os.environ["VANTIO_HOME"] = home
        os.environ["VANTIO_EXTRA_LLM_HOSTS"] = "127.0.0.1"
        try:
            with MockServer() as server:
                server.respond_with(200, {"ok": True})
                async with shield(trace_id="py-requests-observe"):
                    requests.get(server.url, timeout=2)
            log = Path(home) / "runs" / "py-requests-observe.json"
            self.assertTrue(log.is_file())
            data = json.loads(log.read_text(encoding="utf-8"))
            self.assertEqual(data["calls"][0]["action"], "OBSERVED")
            self.assertEqual(data["calls"][0]["mediation"], "python_requests")
            self.assertEqual(len(data["calls"]), 1)
            self.assertEqual(data["calls"][0]["hostname"], "127.0.0.1")
            self.assertNotIn("prompt", data["calls"][0])
        finally:
            os.environ.pop("VANTIO_HOME", None)
            os.environ.pop("VANTIO_EXTRA_LLM_HOSTS", None)

    async def test_httpx_to_extra_host_writes_run_log(self) -> None:
        try:
            import httpx
        except ImportError:
            self.skipTest("httpx is not installed")
        home = tempfile.mkdtemp()
        os.environ["VANTIO_HOME"] = home
        os.environ["VANTIO_EXTRA_LLM_HOSTS"] = "127.0.0.1"
        try:
            with MockServer() as server:
                server.respond_with(200, {"ok": True})
                async with shield(trace_id="py-httpx-observe"):
                    async with httpx.AsyncClient() as client:
                        await client.get(server.url, timeout=2)
            log = Path(home) / "runs" / "py-httpx-observe.json"
            self.assertTrue(log.is_file())
            data = json.loads(log.read_text(encoding="utf-8"))
            self.assertEqual(data["calls"][0]["action"], "OBSERVED")
            self.assertEqual(data["calls"][0]["mediation"], "python_httpx")
            self.assertEqual(len(data["calls"]), 1)
            self.assertEqual(data["calls"][0]["hostname"], "127.0.0.1")
            self.assertNotIn("prompt", data["calls"][0])
        finally:
            os.environ.pop("VANTIO_HOME", None)
            os.environ.pop("VANTIO_EXTRA_LLM_HOSTS", None)

    async def test_aiohttp_to_extra_host_writes_run_log(self) -> None:
        try:
            import aiohttp
        except ImportError:
            self.skipTest("aiohttp is not installed")
        home = tempfile.mkdtemp()
        os.environ["VANTIO_HOME"] = home
        os.environ["VANTIO_EXTRA_LLM_HOSTS"] = "127.0.0.1"
        try:
            with MockServer() as server:
                server.respond_with(200, {"ok": True})
                async with shield(trace_id="py-aiohttp-observe"):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(server.url) as resp:
                            await resp.read()
            log = Path(home) / "runs" / "py-aiohttp-observe.json"
            self.assertTrue(log.is_file())
            data = json.loads(log.read_text(encoding="utf-8"))
            self.assertEqual(data["calls"][0]["action"], "OBSERVED")
            self.assertEqual(data["calls"][0]["mediation"], "python_aiohttp")
            self.assertEqual(len(data["calls"]), 1)
            self.assertEqual(data["calls"][0]["hostname"], "127.0.0.1")
            self.assertNotIn("prompt", data["calls"][0])
        finally:
            os.environ.pop("VANTIO_HOME", None)
            os.environ.pop("VANTIO_EXTRA_LLM_HOSTS", None)

    async def test_requests_out_of_scope_does_not_write_run_log(self) -> None:
        try:
            import requests
        except ImportError:
            self.skipTest("requests is not installed")
        home = tempfile.mkdtemp()
        os.environ["VANTIO_HOME"] = home
        os.environ.pop("VANTIO_EXTRA_LLM_HOSTS", None)
        try:
            with MockServer() as server:
                server.respond_with(200, {"ok": True})
                async with shield(trace_id="py-requests-skip"):
                    requests.get(server.url, timeout=2)
            log = Path(home) / "runs" / "py-requests-skip.json"
            self.assertFalse(log.exists())
        finally:
            os.environ.pop("VANTIO_HOME", None)


class PythonGateWrapTests(unittest.IsolatedAsyncioTestCase):
    def _gate_env(self, home: str) -> None:
        os.environ["VANTIO_HOME"] = home
        os.environ["VANTIO_EXTRA_LLM_HOSTS"] = "127.0.0.1"
        os.environ["VANTIO_API_KEY"] = "vk_test_dummy"

    def _clear_env(self) -> None:
        for key in (
            "VANTIO_HOME",
            "VANTIO_EXTRA_LLM_HOSTS",
            "VANTIO_API_KEY",
            "VANTIO_INGEST_URL",
        ):
            os.environ.pop(key, None)

    async def test_urlopen_blocked_host_never_hits_target(self) -> None:
        import urllib.error
        import urllib.request

        home = tempfile.mkdtemp()
        self._gate_env(home)
        try:
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
                                "redact_pii": False,
                                "pii_types": [],
                                "max_request_bytes": 0,
                                "spend_cap_usd": 0,
                                "dry_run": False,
                            },
                        }
                        return 200, json.dumps(body).encode("utf-8")
                    if req.path.startswith("/api/v1/ingest"):
                        return 200, b'{"status":0}'
                    return 200, b'{"ok":true}'

                server.respond_with_handler(handler)
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    async with shield(trace_id="py-gate-block"):
                        urllib.request.urlopen(server.url + "/v1/target", timeout=2)
                self.assertEqual(raised.exception.code, 403)
                target_hits = [r for r in server.requests if r.path == "/v1/target"]
                self.assertEqual(target_hits, [])
            log = Path(home) / "runs" / "py-gate-block.json"
            self.assertTrue(log.is_file())
            data = json.loads(log.read_text(encoding="utf-8"))
            self.assertEqual(data["calls"][0]["action"], "BLOCKED_HOST")
            self.assertNotIn("python_socket", {c.get("mediation") for c in data["calls"]})
            self.assertNotIn("python_curl", {c.get("mediation") for c in data["calls"]})
            self.assertNotIn("python_wget", {c.get("mediation") for c in data["calls"]})
            self.assertNotIn("python_http_client", {c.get("mediation") for c in data["calls"]})
            self.assertNotIn("python_httpie", {c.get("mediation") for c in data["calls"]})
            self.assertNotIn("python_aria2c", {c.get("mediation") for c in data["calls"]})
        finally:
            self._clear_env()

    async def test_urlopen_redacts_pii_before_leave(self) -> None:
        import urllib.request

        home = tempfile.mkdtemp()
        self._gate_env(home)
        try:
            with MockServer() as server:
                os.environ["VANTIO_INGEST_URL"] = server.url

                def handler(req):
                    if req.path.startswith("/api/v1/config"):
                        body = {
                            "tier": "PRO",
                            "policy": {
                                "enforce": False,
                                "blocked_hosts": [],
                                "allowed_hosts": ["127.0.0.1"],
                                "redact_pii": True,
                                "pii_types": ["email"],
                                "max_request_bytes": 0,
                                "spend_cap_usd": 0,
                                "dry_run": False,
                            },
                        }
                        return 200, json.dumps(body).encode("utf-8")
                    if req.path.startswith("/api/v1/ingest"):
                        return 200, b'{"status":0}'
                    return 200, b'{"ok":true}'

                server.respond_with_handler(handler)
                payload = json.dumps({"email": "shouldnotleak@example.com"}).encode("utf-8")
                req = urllib.request.Request(
                    server.url + "/v1/target",
                    data=payload,
                    method="POST",
                    headers={"content-type": "application/json"},
                )
                async with shield(trace_id="py-gate-redact"):
                    urllib.request.urlopen(req, timeout=2)
                targets = [r for r in server.requests if r.path == "/v1/target"]
                self.assertEqual(len(targets), 1)
                self.assertNotIn(b"shouldnotleak@example.com", targets[0].body)
                self.assertIn(b"[VANTIO_REDACTED:EMAIL]", targets[0].body)
            log = Path(home) / "runs" / "py-gate-redact.json"
            data = json.loads(log.read_text(encoding="utf-8"))
            self.assertEqual(data["calls"][0]["action"], "REDACTED")
            self.assertEqual(len(data["calls"]), 1)
            self.assertNotIn("python_socket", {c.get("mediation") for c in data["calls"]})
        finally:
            self._clear_env()

    async def test_aiohttp_blocked_host_never_hits_target(self) -> None:
        try:
            import aiohttp
        except ImportError:
            self.skipTest("aiohttp is not installed")
        home = tempfile.mkdtemp()
        self._gate_env(home)
        try:
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
                                "redact_pii": False,
                                "pii_types": [],
                                "max_request_bytes": 0,
                                "spend_cap_usd": 0,
                                "dry_run": False,
                            },
                        }
                        return 200, json.dumps(body).encode("utf-8")
                    if req.path.startswith("/api/v1/ingest"):
                        return 200, b'{"status":0}'
                    return 200, b'{"ok":true}'

                server.respond_with_handler(handler)
                with self.assertRaises(aiohttp.ClientResponseError) as raised:
                    async with shield(trace_id="py-aiohttp-block"):
                        async with aiohttp.ClientSession() as session:
                            await session.get(server.url + "/v1/target")
                self.assertEqual(raised.exception.status, 403)
                target_hits = [r for r in server.requests if r.path == "/v1/target"]
                self.assertEqual(target_hits, [])
            log = Path(home) / "runs" / "py-aiohttp-block.json"
            self.assertTrue(log.is_file())
            data = json.loads(log.read_text(encoding="utf-8"))
            self.assertEqual(data["calls"][0]["action"], "BLOCKED_HOST")
        finally:
            self._clear_env()

    async def test_aiohttp_redacts_pii_before_leave(self) -> None:
        try:
            import aiohttp
        except ImportError:
            self.skipTest("aiohttp is not installed")
        home = tempfile.mkdtemp()
        self._gate_env(home)
        try:
            with MockServer() as server:
                os.environ["VANTIO_INGEST_URL"] = server.url

                def handler(req):
                    if req.path.startswith("/api/v1/config"):
                        body = {
                            "tier": "PRO",
                            "policy": {
                                "enforce": False,
                                "blocked_hosts": [],
                                "allowed_hosts": ["127.0.0.1"],
                                "redact_pii": True,
                                "pii_types": ["email"],
                                "max_request_bytes": 0,
                                "spend_cap_usd": 0,
                                "dry_run": False,
                            },
                        }
                        return 200, json.dumps(body).encode("utf-8")
                    if req.path.startswith("/api/v1/ingest"):
                        return 200, b'{"status":0}'
                    return 200, b'{"ok":true}'

                server.respond_with_handler(handler)
                async with shield(trace_id="py-aiohttp-redact"):
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            server.url + "/v1/target",
                            json={"email": "shouldnotleak@example.com"},
                        ) as resp:
                            await resp.read()
                targets = [r for r in server.requests if r.path == "/v1/target"]
                self.assertEqual(len(targets), 1)
                self.assertNotIn(b"shouldnotleak@example.com", targets[0].body)
                self.assertIn(b"[VANTIO_REDACTED:EMAIL]", targets[0].body)
            log = Path(home) / "runs" / "py-aiohttp-redact.json"
            data = json.loads(log.read_text(encoding="utf-8"))
            self.assertEqual(data["calls"][0]["action"], "REDACTED")
            self.assertEqual(len(data["calls"]), 1)
            self.assertNotIn("python_socket", {c.get("mediation") for c in data["calls"]})
        finally:
            self._clear_env()


class _TcpSink:
    def __init__(self) -> None:
        self.hits = 0
        self.port = 0
        self._sock = None
        self._thread = None
        self._alive = False

    def __enter__(self) -> "_TcpSink":
        import socket as _socket
        import threading

        self._sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        self._sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(5)
        self.port = int(self._sock.getsockname()[1])
        self._alive = True

        def _run() -> None:
            import socket as _socket

            while self._alive:
                try:
                    self._sock.settimeout(0.2)
                    conn, _addr = self._sock.accept()
                    self.hits += 1
                    conn.close()
                except (_socket.timeout, TimeoutError):
                    continue
                except OSError:
                    return

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._alive = False
        try:
            if self._sock is not None:
                self._sock.close()
        except OSError:
            pass


class PythonSocketWrapTests(unittest.IsolatedAsyncioTestCase):
    def _gate_env(self, home: str) -> None:
        os.environ["VANTIO_HOME"] = home
        os.environ["VANTIO_API_KEY"] = "vk_test_dummy"

    def _clear_env(self) -> None:
        for key in (
            "VANTIO_HOME",
            "VANTIO_EXTRA_LLM_HOSTS",
            "VANTIO_API_KEY",
            "VANTIO_INGEST_URL",
        ):
            os.environ.pop(key, None)

    def _config_handler(self, blocked: bool):
        def handler(req):
            if req.path.startswith("/api/v1/config"):
                body = {
                    "tier": "PRO",
                    "policy": {
                        "enforce": True,
                        "blocked_hosts": ["127.0.0.1"] if blocked else [],
                        "allowed_hosts": [] if blocked else ["127.0.0.1"],
                        "redact_pii": False,
                        "pii_types": [],
                        "max_request_bytes": 0,
                        "spend_cap_usd": 0,
                        "dry_run": False,
                    },
                }
                return 200, json.dumps(body).encode("utf-8")
            if req.path.startswith("/api/v1/ingest"):
                return 200, b'{"status":0}'
            return 200, b'{"ok":true}'

        return handler

    async def test_create_connection_blocked_host_never_opens_tcp(self) -> None:
        import socket

        from vantio._http_observe import GateBlockedError

        home = tempfile.mkdtemp()
        self._gate_env(home)
        try:
            with MockServer() as server, _TcpSink() as sink:
                os.environ["VANTIO_INGEST_URL"] = server.url
                server.respond_with_handler(self._config_handler(blocked=True))
                with self.assertRaises(GateBlockedError) as raised:
                    async with shield(trace_id="py-socket-block"):
                        socket.create_connection(("127.0.0.1", sink.port), timeout=2)
                self.assertEqual(raised.exception.code, "VANTIO_GATE_BLOCKED")
                self.assertEqual(sink.hits, 0)
            log = Path(home) / "runs" / "py-socket-block.json"
            data = json.loads(log.read_text(encoding="utf-8"))
            self.assertEqual(data["calls"][0]["action"], "BLOCKED_HOST")
            self.assertEqual(data["calls"][0]["mediation"], "python_socket")
        finally:
            self._clear_env()

    async def test_create_connection_allowed_records_python_socket(self) -> None:
        import socket

        home = tempfile.mkdtemp()
        self._gate_env(home)
        try:
            with MockServer() as server, _TcpSink() as sink:
                os.environ["VANTIO_INGEST_URL"] = server.url
                server.respond_with_handler(self._config_handler(blocked=False))
                async with shield(trace_id="py-socket-allow"):
                    sock = socket.create_connection(("127.0.0.1", sink.port), timeout=2)
                    sock.close()
            log = Path(home) / "runs" / "py-socket-allow.json"
            data = json.loads(log.read_text(encoding="utf-8"))
            socket_calls = [c for c in data["calls"] if c.get("mediation") == "python_socket"]
            self.assertEqual(len(socket_calls), 1)
            self.assertEqual(socket_calls[0]["action"], "ALLOWED")
            deadline = time.time() + 2
            while sink.hits < 1 and time.time() < deadline:
                time.sleep(0.05)
            self.assertGreaterEqual(sink.hits, 1)
        finally:
            self._clear_env()

    async def test_socket_connect_blocked_host_never_opens_tcp(self) -> None:
        import socket

        from vantio._http_observe import GateBlockedError

        home = tempfile.mkdtemp()
        self._gate_env(home)
        try:
            with MockServer() as server, _TcpSink() as sink:
                os.environ["VANTIO_INGEST_URL"] = server.url
                server.respond_with_handler(self._config_handler(blocked=True))
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                try:
                    with self.assertRaises(GateBlockedError) as raised:
                        async with shield(trace_id="py-socket-connect-block"):
                            sock.connect(("127.0.0.1", sink.port))
                    self.assertEqual(raised.exception.code, "VANTIO_GATE_BLOCKED")
                    self.assertEqual(sink.hits, 0)
                finally:
                    sock.close()
            log = Path(home) / "runs" / "py-socket-connect-block.json"
            data = json.loads(log.read_text(encoding="utf-8"))
            self.assertEqual(data["calls"][0]["action"], "BLOCKED_HOST")
            self.assertEqual(data["calls"][0]["mediation"], "python_socket")
        finally:
            self._clear_env()

    async def test_unix_socket_passes_through(self) -> None:
        import socket

        home = tempfile.mkdtemp()
        self._gate_env(home)
        ipc = os.path.join(home, "ipc.sock")
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            with MockServer() as server:
                os.environ["VANTIO_INGEST_URL"] = server.url
                server.respond_with_handler(self._config_handler(blocked=True))
                srv.bind(ipc)
                srv.listen(1)
                srv.settimeout(2)
                async with shield(trace_id="py-socket-unix"):
                    cli = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    cli.settimeout(2)
                    cli.connect(ipc)
                    cli.close()
            log = Path(home) / "runs" / "py-socket-unix.json"
            if log.is_file():
                data = json.loads(log.read_text(encoding="utf-8"))
                self.assertNotIn("python_socket", {c.get("mediation") for c in data["calls"]})
            else:
                self.assertFalse(log.exists())
        finally:
            srv.close()
            self._clear_env()


class PythonCurlWrapTests(unittest.IsolatedAsyncioTestCase):
    def _gate_env(self, home: str) -> None:
        os.environ["VANTIO_HOME"] = home
        os.environ["VANTIO_EXTRA_LLM_HOSTS"] = "127.0.0.1"
        os.environ["VANTIO_API_KEY"] = "vk_test_dummy"

    def _clear_env(self) -> None:
        for key in (
            "VANTIO_HOME",
            "VANTIO_EXTRA_LLM_HOSTS",
            "VANTIO_API_KEY",
            "VANTIO_INGEST_URL",
        ):
            os.environ.pop(key, None)

    def _config_handler(self, blocked: bool, max_request_bytes: int = 0):
        def handler(req):
            if req.path.startswith("/api/v1/config"):
                body = {
                    "tier": "PRO",
                    "policy": {
                        "enforce": True,
                        "blocked_hosts": ["127.0.0.1"] if blocked else [],
                        "allowed_hosts": [] if blocked else ["127.0.0.1"],
                        "redact_pii": False,
                        "pii_types": [],
                        "max_request_bytes": max_request_bytes,
                        "spend_cap_usd": 0,
                        "dry_run": False,
                    },
                }
                return 200, json.dumps(body).encode("utf-8")
            if req.path.startswith("/api/v1/ingest"):
                return 200, b'{"status":0}'
            return 200, b'{"ok":true}'

        return handler

    def _curl_cmd(self, url: str, data: str = "hello-curl") -> list[str]:
        return ["curl", "-sS", "--max-time", "2", "-X", "POST", "-d", data, url]

    async def test_subprocess_curl_blocked_host_never_starts(self) -> None:
        from vantio._http_observe import GateBlockedError

        if not shutil.which("curl"):
            self.skipTest("curl is not installed")
        home = tempfile.mkdtemp()
        self._gate_env(home)
        try:
            with MockServer() as server:
                os.environ["VANTIO_INGEST_URL"] = server.url
                server.respond_with_handler(self._config_handler(blocked=True))
                target = server.url + "/v1/target"
                with self.assertRaises(GateBlockedError) as raised:
                    async with shield(trace_id="py-curl-block"):
                        subprocess.run(self._curl_cmd(target), capture_output=True, timeout=5)
                self.assertEqual(raised.exception.code, "VANTIO_GATE_BLOCKED")
                self.assertEqual([r for r in server.requests if r.path == "/v1/target"], [])
            log = Path(home) / "runs" / "py-curl-block.json"
            data = json.loads(log.read_text(encoding="utf-8"))
            curl_calls = [c for c in data["calls"] if c.get("mediation") == "python_curl"]
            self.assertEqual(len(curl_calls), 1)
            self.assertEqual(curl_calls[0]["action"], "BLOCKED_HOST")
        finally:
            self._clear_env()

    async def test_subprocess_curl_allowed_records_python_curl(self) -> None:
        if not shutil.which("curl"):
            self.skipTest("curl is not installed")
        home = tempfile.mkdtemp()
        self._gate_env(home)
        try:
            with MockServer() as server:
                os.environ["VANTIO_INGEST_URL"] = server.url
                server.respond_with_handler(self._config_handler(blocked=False))
                target = server.url + "/v1/target"
                async with shield(trace_id="py-curl-allow"):
                    completed = subprocess.run(
                        self._curl_cmd(target), capture_output=True, timeout=5
                    )
                self.assertEqual(completed.returncode, 0)
                hits = [r for r in server.requests if r.path == "/v1/target"]
                self.assertEqual(len(hits), 1)
                self.assertIn(b"hello-curl", hits[0].body)
            log = Path(home) / "runs" / "py-curl-allow.json"
            data = json.loads(log.read_text(encoding="utf-8"))
            curl_calls = [c for c in data["calls"] if c.get("mediation") == "python_curl"]
            self.assertEqual(len(curl_calls), 1)
            self.assertEqual(curl_calls[0]["action"], "ALLOWED")
            self.assertEqual(curl_calls[0]["bytes_observed"], len(b"hello-curl"))
        finally:
            self._clear_env()

    async def test_shell_curl_blocked_host_never_starts(self) -> None:
        from vantio._http_observe import GateBlockedError

        if not shutil.which("curl"):
            self.skipTest("curl is not installed")
        home = tempfile.mkdtemp()
        self._gate_env(home)
        try:
            with MockServer() as server:
                os.environ["VANTIO_INGEST_URL"] = server.url
                server.respond_with_handler(self._config_handler(blocked=True))
                target = server.url + "/v1/target"
                with self.assertRaises(GateBlockedError) as raised:
                    async with shield(trace_id="py-curl-sh"):
                        subprocess.run(
                            ["sh", "-c", "curl -sS --max-time 2 " + target],
                            capture_output=True,
                            timeout=5,
                        )
                self.assertEqual(raised.exception.code, "VANTIO_GATE_BLOCKED")
                self.assertEqual([r for r in server.requests if r.path == "/v1/target"], [])
            log = Path(home) / "runs" / "py-curl-sh.json"
            data = json.loads(log.read_text(encoding="utf-8"))
            self.assertEqual(data["calls"][0]["action"], "BLOCKED_HOST")
            self.assertEqual(data["calls"][0]["mediation"], "python_curl")
        finally:
            self._clear_env()

    async def test_subprocess_curl_over_max_request_bytes_never_hits(self) -> None:
        from vantio._http_observe import GateBlockedError

        if not shutil.which("curl"):
            self.skipTest("curl is not installed")
        home = tempfile.mkdtemp()
        self._gate_env(home)
        try:
            with MockServer() as server:
                os.environ["VANTIO_INGEST_URL"] = server.url
                server.respond_with_handler(
                    self._config_handler(blocked=False, max_request_bytes=4)
                )
                target = server.url + "/v1/target"
                with self.assertRaises(GateBlockedError) as raised:
                    async with shield(trace_id="py-curl-size"):
                        subprocess.run(self._curl_cmd(target), capture_output=True, timeout=5)
                self.assertEqual(raised.exception.code, "VANTIO_GATE_BLOCKED")
                self.assertEqual([r for r in server.requests if r.path == "/v1/target"], [])
            log = Path(home) / "runs" / "py-curl-size.json"
            data = json.loads(log.read_text(encoding="utf-8"))
            size_calls = [c for c in data["calls"] if c.get("action") == "BLOCKED_SIZE"]
            self.assertGreaterEqual(len(size_calls), 1)
            self.assertEqual(size_calls[0]["mediation"], "python_curl")
        finally:
            self._clear_env()


class PythonWgetWrapTests(unittest.IsolatedAsyncioTestCase):
    def _gate_env(self, home: str) -> None:
        os.environ["VANTIO_HOME"] = home
        os.environ["VANTIO_EXTRA_LLM_HOSTS"] = "127.0.0.1"
        os.environ["VANTIO_API_KEY"] = "vk_test_dummy"

    def _clear_env(self) -> None:
        for key in (
            "VANTIO_HOME",
            "VANTIO_EXTRA_LLM_HOSTS",
            "VANTIO_API_KEY",
            "VANTIO_INGEST_URL",
        ):
            os.environ.pop(key, None)

    def _config_handler(self, blocked: bool, max_request_bytes: int = 0):
        def handler(req):
            if req.path.startswith("/api/v1/config"):
                body = {
                    "tier": "PRO",
                    "policy": {
                        "enforce": True,
                        "blocked_hosts": ["127.0.0.1"] if blocked else [],
                        "allowed_hosts": [] if blocked else ["127.0.0.1"],
                        "redact_pii": False,
                        "pii_types": [],
                        "max_request_bytes": max_request_bytes,
                        "spend_cap_usd": 0,
                        "dry_run": False,
                    },
                }
                return 200, json.dumps(body).encode("utf-8")
            if req.path.startswith("/api/v1/ingest"):
                return 200, b'{"status":0}'
            return 200, b'{"ok":true}'

        return handler

    def _wget_cmd(self, url: str, data: str = "hello-wget") -> list[str]:
        return [
            "wget",
            "-q",
            "-O",
            "-",
            "--timeout=2",
            "--tries=1",
            f"--post-data={data}",
            url,
        ]

    async def test_subprocess_wget_blocked_host_never_starts(self) -> None:
        from vantio._http_observe import GateBlockedError

        if not shutil.which("wget"):
            self.skipTest("wget is not installed")
        home = tempfile.mkdtemp()
        self._gate_env(home)
        try:
            with MockServer() as server:
                os.environ["VANTIO_INGEST_URL"] = server.url
                server.respond_with_handler(self._config_handler(blocked=True))
                target = server.url + "/v1/target"
                with self.assertRaises(GateBlockedError) as raised:
                    async with shield(trace_id="py-wget-block"):
                        subprocess.run(self._wget_cmd(target), capture_output=True, timeout=5)
                self.assertEqual(raised.exception.code, "VANTIO_GATE_BLOCKED")
                self.assertEqual([r for r in server.requests if r.path == "/v1/target"], [])
            log = Path(home) / "runs" / "py-wget-block.json"
            data = json.loads(log.read_text(encoding="utf-8"))
            wget_calls = [c for c in data["calls"] if c.get("mediation") == "python_wget"]
            self.assertEqual(len(wget_calls), 1)
            self.assertEqual(wget_calls[0]["action"], "BLOCKED_HOST")
        finally:
            self._clear_env()

    async def test_subprocess_wget_allowed_records_python_wget(self) -> None:
        if not shutil.which("wget"):
            self.skipTest("wget is not installed")
        home = tempfile.mkdtemp()
        self._gate_env(home)
        try:
            with MockServer() as server:
                os.environ["VANTIO_INGEST_URL"] = server.url
                server.respond_with_handler(self._config_handler(blocked=False))
                target = server.url + "/v1/target"
                async with shield(trace_id="py-wget-allow"):
                    completed = subprocess.run(
                        self._wget_cmd(target), capture_output=True, timeout=5
                    )
                self.assertEqual(completed.returncode, 0)
                hits = [r for r in server.requests if r.path == "/v1/target"]
                self.assertEqual(len(hits), 1)
                self.assertIn(b"hello-wget", hits[0].body)
            log = Path(home) / "runs" / "py-wget-allow.json"
            data = json.loads(log.read_text(encoding="utf-8"))
            wget_calls = [c for c in data["calls"] if c.get("mediation") == "python_wget"]
            self.assertEqual(len(wget_calls), 1)
            self.assertEqual(wget_calls[0]["action"], "ALLOWED")
            self.assertEqual(wget_calls[0]["bytes_observed"], len(b"hello-wget"))
        finally:
            self._clear_env()

    async def test_shell_wget_blocked_host_never_starts(self) -> None:
        from vantio._http_observe import GateBlockedError

        if not shutil.which("wget"):
            self.skipTest("wget is not installed")
        home = tempfile.mkdtemp()
        self._gate_env(home)
        try:
            with MockServer() as server:
                os.environ["VANTIO_INGEST_URL"] = server.url
                server.respond_with_handler(self._config_handler(blocked=True))
                target = server.url + "/v1/target"
                with self.assertRaises(GateBlockedError) as raised:
                    async with shield(trace_id="py-wget-sh"):
                        subprocess.run(
                            ["sh", "-c", "wget -q -O - --timeout=2 --tries=1 " + target],
                            capture_output=True,
                            timeout=5,
                        )
                self.assertEqual(raised.exception.code, "VANTIO_GATE_BLOCKED")
                self.assertEqual([r for r in server.requests if r.path == "/v1/target"], [])
            log = Path(home) / "runs" / "py-wget-sh.json"
            data = json.loads(log.read_text(encoding="utf-8"))
            self.assertEqual(data["calls"][0]["action"], "BLOCKED_HOST")
            self.assertEqual(data["calls"][0]["mediation"], "python_wget")
        finally:
            self._clear_env()

    async def test_subprocess_wget_over_max_request_bytes_never_hits(self) -> None:
        from vantio._http_observe import GateBlockedError

        if not shutil.which("wget"):
            self.skipTest("wget is not installed")
        home = tempfile.mkdtemp()
        self._gate_env(home)
        try:
            with MockServer() as server:
                os.environ["VANTIO_INGEST_URL"] = server.url
                server.respond_with_handler(
                    self._config_handler(blocked=False, max_request_bytes=4)
                )
                target = server.url + "/v1/target"
                with self.assertRaises(GateBlockedError) as raised:
                    async with shield(trace_id="py-wget-size"):
                        subprocess.run(self._wget_cmd(target), capture_output=True, timeout=5)
                self.assertEqual(raised.exception.code, "VANTIO_GATE_BLOCKED")
                self.assertEqual([r for r in server.requests if r.path == "/v1/target"], [])
            log = Path(home) / "runs" / "py-wget-size.json"
            data = json.loads(log.read_text(encoding="utf-8"))
            size_calls = [c for c in data["calls"] if c.get("action") == "BLOCKED_SIZE"]
            self.assertGreaterEqual(len(size_calls), 1)
            self.assertEqual(size_calls[0]["mediation"], "python_wget")
        finally:
            self._clear_env()


class PythonBatch308Tests(unittest.IsolatedAsyncioTestCase):
    def _gate_env(self, home: str) -> None:
        os.environ["VANTIO_HOME"] = home
        os.environ["VANTIO_EXTRA_LLM_HOSTS"] = "127.0.0.1"
        os.environ["VANTIO_API_KEY"] = "vk_test_dummy"

    def _clear_env(self) -> None:
        for key in (
            "VANTIO_HOME",
            "VANTIO_EXTRA_LLM_HOSTS",
            "VANTIO_API_KEY",
            "VANTIO_INGEST_URL",
        ):
            os.environ.pop(key, None)

    def _config_handler(self, blocked: bool, max_request_bytes: int = 0, redact: bool = False):
        def handler(req):
            if req.path.startswith("/api/v1/config"):
                body = {
                    "tier": "PRO",
                    "policy": {
                        "enforce": True if not redact else False,
                        "blocked_hosts": ["127.0.0.1"] if blocked else [],
                        "allowed_hosts": [] if blocked else ["127.0.0.1"],
                        "redact_pii": redact,
                        "pii_types": ["email"] if redact else [],
                        "max_request_bytes": max_request_bytes,
                        "spend_cap_usd": 0,
                        "dry_run": False,
                    },
                }
                return 200, json.dumps(body).encode("utf-8")
            if req.path.startswith("/api/v1/ingest"):
                return 200, b'{"status":0}'
            return 200, b'{"ok":true}'

        return handler

    async def test_curl_post_file_over_max_never_hits(self) -> None:
        from vantio._http_observe import GateBlockedError

        if not shutil.which("curl"):
            self.skipTest("curl is not installed")
        home = tempfile.mkdtemp()
        self._gate_env(home)
        body_path = Path(home) / "body.txt"
        body_path.write_text("hello-post-file", encoding="utf-8")
        try:
            with MockServer() as server:
                os.environ["VANTIO_INGEST_URL"] = server.url
                server.respond_with_handler(self._config_handler(blocked=False, max_request_bytes=4))
                target = server.url + "/v1/target"
                with self.assertRaises(GateBlockedError):
                    async with shield(trace_id="py-curl-post-file"):
                        subprocess.run(
                            ["curl", "-sS", "--max-time", "2", "-X", "POST", "-d", "@" + str(body_path), target],
                            capture_output=True,
                            timeout=5,
                        )
                self.assertEqual([r for r in server.requests if r.path == "/v1/target"], [])
            data = json.loads((Path(home) / "runs" / "py-curl-post-file.json").read_text(encoding="utf-8"))
            size_calls = [c for c in data["calls"] if c.get("action") == "BLOCKED_SIZE"]
            self.assertGreaterEqual(len(size_calls), 1)
            self.assertEqual(size_calls[0]["mediation"], "python_curl")
            self.assertEqual(size_calls[0]["bytes_observed"], len(b"hello-post-file"))
        finally:
            self._clear_env()

    async def test_wget_post_file_over_max_never_hits(self) -> None:
        from vantio._http_observe import GateBlockedError

        if not shutil.which("wget"):
            self.skipTest("wget is not installed")
        home = tempfile.mkdtemp()
        self._gate_env(home)
        body_path = Path(home) / "body.txt"
        body_path.write_text("hello-post-file", encoding="utf-8")
        try:
            with MockServer() as server:
                os.environ["VANTIO_INGEST_URL"] = server.url
                server.respond_with_handler(self._config_handler(blocked=False, max_request_bytes=4))
                target = server.url + "/v1/target"
                with self.assertRaises(GateBlockedError):
                    async with shield(trace_id="py-wget-post-file"):
                        subprocess.run(
                            ["wget", "-q", "-O", "-", "--timeout=2", "--tries=1",
                             "--post-file=" + str(body_path), target],
                            capture_output=True,
                            timeout=5,
                        )
                self.assertEqual([r for r in server.requests if r.path == "/v1/target"], [])
            data = json.loads((Path(home) / "runs" / "py-wget-post-file.json").read_text(encoding="utf-8"))
            size_calls = [c for c in data["calls"] if c.get("action") == "BLOCKED_SIZE"]
            self.assertGreaterEqual(len(size_calls), 1)
            self.assertEqual(size_calls[0]["mediation"], "python_wget")
        finally:
            self._clear_env()

    async def test_timeout_prefix_curl_blocked_never_starts(self) -> None:
        from vantio._http_observe import GateBlockedError

        if not shutil.which("curl") or not shutil.which("timeout"):
            self.skipTest("curl or timeout is not installed")
        home = tempfile.mkdtemp()
        self._gate_env(home)
        try:
            with MockServer() as server:
                os.environ["VANTIO_INGEST_URL"] = server.url
                server.respond_with_handler(self._config_handler(blocked=True))
                target = server.url + "/v1/target"
                with self.assertRaises(GateBlockedError):
                    async with shield(trace_id="py-timeout-curl"):
                        subprocess.run(["timeout", "2", "curl", "-sS", "--max-time", "2", target],
                                       capture_output=True, timeout=5)
                self.assertEqual([r for r in server.requests if r.path == "/v1/target"], [])
            data = json.loads((Path(home) / "runs" / "py-timeout-curl.json").read_text(encoding="utf-8"))
            self.assertEqual(data["calls"][0]["mediation"], "python_curl")
            self.assertEqual(data["calls"][0]["action"], "BLOCKED_HOST")
        finally:
            self._clear_env()

    async def test_curl_config_url_blocked_never_starts(self) -> None:
        from vantio._http_observe import GateBlockedError

        if not shutil.which("curl"):
            self.skipTest("curl is not installed")
        home = tempfile.mkdtemp()
        self._gate_env(home)
        try:
            with MockServer() as server:
                os.environ["VANTIO_INGEST_URL"] = server.url
                server.respond_with_handler(self._config_handler(blocked=True))
                target = server.url + "/v1/target"
                cfg = Path(home) / "curl.cfg"
                cfg.write_text("url = " + target + "\n", encoding="utf-8")
                with self.assertRaises(GateBlockedError):
                    async with shield(trace_id="py-curl-k"):
                        subprocess.run(["curl", "-sS", "--max-time", "2", "-K", str(cfg)],
                                       capture_output=True, timeout=5)
                self.assertEqual([r for r in server.requests if r.path == "/v1/target"], [])
            data = json.loads((Path(home) / "runs" / "py-curl-k.json").read_text(encoding="utf-8"))
            self.assertEqual(data["calls"][0]["mediation"], "python_curl")
            self.assertEqual(data["calls"][0]["action"], "BLOCKED_HOST")
        finally:
            self._clear_env()

    async def test_connect_ex_blocked_host_never_opens_tcp(self) -> None:
        import socket

        from vantio._http_observe import GateBlockedError

        home = tempfile.mkdtemp()
        self._gate_env(home)
        try:
            with MockServer() as server, _TcpSink() as sink:
                os.environ["VANTIO_INGEST_URL"] = server.url
                server.respond_with_handler(self._config_handler(blocked=True))
                sock = socket.socket()
                sock.settimeout(2)
                try:
                    with self.assertRaises(GateBlockedError):
                        async with shield(trace_id="py-connect-ex"):
                            sock.connect_ex(("127.0.0.1", sink.port))
                finally:
                    sock.close()
                self.assertEqual(sink.hits, 0)
            data = json.loads((Path(home) / "runs" / "py-connect-ex.json").read_text(encoding="utf-8"))
            self.assertEqual(data["calls"][0]["mediation"], "python_socket")
            self.assertEqual(data["calls"][0]["action"], "BLOCKED_HOST")
        finally:
            self._clear_env()

    async def test_http_client_blocked_never_hits_target(self) -> None:
        import http.client
        from urllib.parse import urlparse

        from vantio._http_observe import GateBlockedError

        home = tempfile.mkdtemp()
        self._gate_env(home)
        try:
            with MockServer() as server:
                os.environ["VANTIO_INGEST_URL"] = server.url
                server.respond_with_handler(self._config_handler(blocked=True))
                parsed = urlparse(server.url)
                conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=2)
                try:
                    with self.assertRaises(GateBlockedError):
                        async with shield(trace_id="py-http-client"):
                            conn.request("GET", "/v1/target")
                finally:
                    conn.close()
                self.assertEqual([r for r in server.requests if r.path == "/v1/target"], [])
            data = json.loads((Path(home) / "runs" / "py-http-client.json").read_text(encoding="utf-8"))
            self.assertEqual(data["calls"][0]["mediation"], "python_http_client")
            self.assertEqual(data["calls"][0]["action"], "BLOCKED_HOST")
        finally:
            self._clear_env()

    async def test_opener_open_blocked_never_hits_target(self) -> None:
        import urllib.error
        import urllib.request

        home = tempfile.mkdtemp()
        self._gate_env(home)
        try:
            with MockServer() as server:
                os.environ["VANTIO_INGEST_URL"] = server.url
                server.respond_with_handler(self._config_handler(blocked=True))
                opener = urllib.request.build_opener()
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    async with shield(trace_id="py-opener"):
                        opener.open(server.url + "/v1/target", timeout=2)
                self.assertEqual(raised.exception.code, 403)
                self.assertEqual([r for r in server.requests if r.path == "/v1/target"], [])
            data = json.loads((Path(home) / "runs" / "py-opener.json").read_text(encoding="utf-8"))
            self.assertEqual(data["calls"][0]["mediation"], "python_urllib")
            self.assertEqual(data["calls"][0]["action"], "BLOCKED_HOST")
        finally:
            self._clear_env()

    async def test_httpx_redacts_pii_before_leave(self) -> None:
        try:
            import httpx
        except ImportError:
            self.skipTest("httpx is not installed")
        home = tempfile.mkdtemp()
        self._gate_env(home)
        try:
            with MockServer() as server:
                os.environ["VANTIO_INGEST_URL"] = server.url
                server.respond_with_handler(self._config_handler(blocked=False, redact=True))
                async with shield(trace_id="py-httpx-redact"):
                    async with httpx.AsyncClient() as client:
                        await client.post(
                            server.url + "/v1/target",
                            content=json.dumps({"email": "shouldnotleak@example.com"}).encode("utf-8"),
                            headers={"content-type": "application/json"},
                            timeout=2,
                        )
                targets = [r for r in server.requests if r.path == "/v1/target"]
                self.assertEqual(len(targets), 1)
                self.assertNotIn(b"shouldnotleak@example.com", targets[0].body)
                self.assertIn(b"[VANTIO_REDACTED:EMAIL]", targets[0].body)
            data = json.loads((Path(home) / "runs" / "py-httpx-redact.json").read_text(encoding="utf-8"))
            self.assertEqual(data["calls"][0]["action"], "REDACTED")
            self.assertEqual(data["calls"][0]["mediation"], "python_httpx")
        finally:
            self._clear_env()

    async def test_urllib3_blocked_never_hits_target(self) -> None:
        try:
            import urllib3
        except ImportError:
            self.skipTest("urllib3 is not installed")
        from vantio._http_observe import GateBlockedError

        home = tempfile.mkdtemp()
        self._gate_env(home)
        try:
            with MockServer() as server:
                os.environ["VANTIO_INGEST_URL"] = server.url
                server.respond_with_handler(self._config_handler(blocked=True))
                http = urllib3.PoolManager()
                with self.assertRaises(GateBlockedError):
                    async with shield(trace_id="py-urllib3"):
                        http.request("GET", server.url + "/v1/target", timeout=2.0)
                self.assertEqual([r for r in server.requests if r.path == "/v1/target"], [])
            data = json.loads((Path(home) / "runs" / "py-urllib3.json").read_text(encoding="utf-8"))
            mediations = {c.get("mediation") for c in data["calls"]}
            self.assertTrue("python_urllib3" in mediations or "python_http_client" in mediations)
            self.assertIn("BLOCKED_HOST", {c.get("action") for c in data["calls"]})
        finally:
            self._clear_env()


class PythonSpawnExtras309Tests(unittest.IsolatedAsyncioTestCase):
    def _gate_env(self, home: str) -> None:
        os.environ["VANTIO_HOME"] = home
        os.environ["VANTIO_EXTRA_LLM_HOSTS"] = "127.0.0.1"
        os.environ["VANTIO_API_KEY"] = "vk_test_dummy"

    def _clear_env(self) -> None:
        for key in (
            "VANTIO_HOME",
            "VANTIO_EXTRA_LLM_HOSTS",
            "VANTIO_API_KEY",
            "VANTIO_INGEST_URL",
        ):
            os.environ.pop(key, None)

    def _config_handler(self, blocked: bool, max_request_bytes: int = 0):
        def handler(req):
            if req.path.startswith("/api/v1/config"):
                body = {
                    "tier": "PRO",
                    "policy": {
                        "enforce": True,
                        "blocked_hosts": ["127.0.0.1"] if blocked else [],
                        "allowed_hosts": [] if blocked else ["127.0.0.1"],
                        "redact_pii": False,
                        "pii_types": [],
                        "max_request_bytes": max_request_bytes,
                        "spend_cap_usd": 0,
                        "dry_run": False,
                    },
                }
                return 200, json.dumps(body).encode("utf-8")
            if req.path.startswith("/api/v1/ingest"):
                return 200, b'{"status":0}'
            return 200, b'{"ok":true}'

        return handler

    async def test_curl_stdin_over_max_never_hits(self) -> None:
        from vantio._http_observe import GateBlockedError

        if not shutil.which("curl"):
            self.skipTest("curl is not installed")
        home = tempfile.mkdtemp()
        self._gate_env(home)
        body_path = Path(home) / "body.txt"
        body_path.write_text("hello-stdin-body", encoding="utf-8")
        try:
            with MockServer() as server:
                os.environ["VANTIO_INGEST_URL"] = server.url
                server.respond_with_handler(self._config_handler(blocked=False, max_request_bytes=4))
                target = server.url + "/v1/target"
                with self.assertRaises(GateBlockedError):
                    async with shield(trace_id="py-curl-stdin"):
                        with open(body_path, "rb") as fh:
                            subprocess.run(
                                ["curl", "-sS", "--max-time", "2", "-X", "POST", "-d", "@-", target],
                                stdin=fh,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                timeout=5,
                            )
                self.assertEqual([r for r in server.requests if r.path == "/v1/target"], [])
            data = json.loads((Path(home) / "runs" / "py-curl-stdin.json").read_text(encoding="utf-8"))
            size_calls = [c for c in data["calls"] if c.get("action") == "BLOCKED_SIZE"]
            self.assertGreaterEqual(len(size_calls), 1)
            self.assertEqual(size_calls[0]["mediation"], "python_curl")
            self.assertEqual(size_calls[0]["bytes_observed"], len(b"hello-stdin-body"))
        finally:
            self._clear_env()

    async def test_curl_form_file_over_max_never_ingests_contents(self) -> None:
        from vantio._http_observe import GateBlockedError

        if not shutil.which("curl"):
            self.skipTest("curl is not installed")
        home = tempfile.mkdtemp()
        self._gate_env(home)
        secret = "SECRET_SHOULD_NOT_INGEST_py_curl_form"
        body_path = Path(home) / "body.txt"
        body_path.write_text(secret, encoding="utf-8")
        try:
            with MockServer() as server:
                os.environ["VANTIO_INGEST_URL"] = server.url
                server.respond_with_handler(self._config_handler(blocked=False, max_request_bytes=4))
                target = server.url + "/v1/target"
                with self.assertRaises(GateBlockedError):
                    async with shield(trace_id="py-curl-form"):
                        subprocess.run(
                            ["curl", "-sS", "--max-time", "2", "-F", "file=@" + str(body_path), target],
                            capture_output=True,
                            timeout=5,
                        )
                self.assertEqual([r for r in server.requests if r.path == "/v1/target"], [])
            raw = (Path(home) / "runs" / "py-curl-form.json").read_text(encoding="utf-8")
            self.assertNotIn(secret, raw)
            data = json.loads(raw)
            size_calls = [c for c in data["calls"] if c.get("action") == "BLOCKED_SIZE"]
            self.assertGreaterEqual(len(size_calls), 1)
            self.assertEqual(size_calls[0]["mediation"], "python_curl")
            self.assertEqual(size_calls[0]["bytes_observed"], len(secret.encode("utf-8")))
        finally:
            self._clear_env()

    async def test_wget_input_file_blocked_never_starts(self) -> None:
        from vantio._http_observe import GateBlockedError

        if not shutil.which("wget"):
            self.skipTest("wget is not installed")
        home = tempfile.mkdtemp()
        self._gate_env(home)
        try:
            with MockServer() as server:
                os.environ["VANTIO_INGEST_URL"] = server.url
                server.respond_with_handler(self._config_handler(blocked=True))
                target = server.url + "/v1/target"
                list_path = Path(home) / "urls.txt"
                list_path.write_text(target + "\n", encoding="utf-8")
                with self.assertRaises(GateBlockedError):
                    async with shield(trace_id="py-wget-i"):
                        subprocess.run(
                            ["wget", "-q", "-O", "-", "--timeout=2", "--tries=1", "-i", str(list_path)],
                            capture_output=True,
                            timeout=5,
                        )
                self.assertEqual([r for r in server.requests if r.path == "/v1/target"], [])
            data = json.loads((Path(home) / "runs" / "py-wget-i.json").read_text(encoding="utf-8"))
            self.assertEqual(data["calls"][0]["mediation"], "python_wget")
            self.assertEqual(data["calls"][0]["action"], "BLOCKED_HOST")
        finally:
            self._clear_env()

    async def test_httpie_blocked_never_starts(self) -> None:
        from vantio._http_observe import GateBlockedError

        home = tempfile.mkdtemp()
        self._gate_env(home)
        try:
            with MockServer() as server:
                os.environ["VANTIO_INGEST_URL"] = server.url
                server.respond_with_handler(self._config_handler(blocked=True))
                target = server.url + "/v1/target"
                with self.assertRaises(GateBlockedError):
                    async with shield(trace_id="py-httpie"):
                        subprocess.run(["http", "GET", target], capture_output=True, timeout=5)
                self.assertEqual([r for r in server.requests if r.path == "/v1/target"], [])
            data = json.loads((Path(home) / "runs" / "py-httpie.json").read_text(encoding="utf-8"))
            self.assertEqual(data["calls"][0]["mediation"], "python_httpie")
            self.assertEqual(data["calls"][0]["action"], "BLOCKED_HOST")
        finally:
            self._clear_env()

    async def test_aria2c_blocked_never_starts(self) -> None:
        from vantio._http_observe import GateBlockedError

        home = tempfile.mkdtemp()
        self._gate_env(home)
        try:
            with MockServer() as server:
                os.environ["VANTIO_INGEST_URL"] = server.url
                server.respond_with_handler(self._config_handler(blocked=True))
                target = server.url + "/v1/target"
                with self.assertRaises(GateBlockedError):
                    async with shield(trace_id="py-aria2c"):
                        subprocess.run(["aria2c", target], capture_output=True, timeout=5)
                self.assertEqual([r for r in server.requests if r.path == "/v1/target"], [])
            data = json.loads((Path(home) / "runs" / "py-aria2c.json").read_text(encoding="utf-8"))
            self.assertEqual(data["calls"][0]["mediation"], "python_aria2c")
            self.assertEqual(data["calls"][0]["action"], "BLOCKED_HOST")
        finally:
            self._clear_env()

