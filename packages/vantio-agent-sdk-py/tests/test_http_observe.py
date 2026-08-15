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
