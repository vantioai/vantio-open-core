import json
import os
import tempfile
import unittest
from pathlib import Path

from vantio import shield
from vantio._http_observe import (
    _host_matches_regional,
    _in_scope,
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
        finally:
            self._clear_env()

