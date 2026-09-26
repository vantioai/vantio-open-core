"""Customer outcome lines for Python Optics. Machine tokens stay unchanged."""
from __future__ import annotations

import http.client
import json
import os
import socket
import ssl
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

try:
    import aiohttp
except ImportError:
    aiohttp = None  # type: ignore[assignment]

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

try:
    import pycurl
except ImportError:
    pycurl = None  # type: ignore[assignment]

try:
    import requests
except ImportError:
    requests = None  # type: ignore[assignment]

try:
    import urllib3
except ImportError:
    urllib3 = None  # type: ignore[assignment]

from vantio import shield
from vantio import _http_observe as observe
from vantio._outcome import (
    apply_customer_outcome,
    classify_exception,
    customer_view_lines,
    empty_observation,
    http_outcome_label,
    http_response_text,
    resolve_provider,
    summarize_customer_fields,
)

from .mock_server import MockServer

HTTP_CODES = (200, 302, 400, 401, 403, 404, 408, 409, 422, 429, 500, 502, 503)

# Literal customer lines. These are the contract, not a mirror of a helper's return.
EXPECTED = {
    200: ("Successful", "HTTP 200 OK", "inspection", "SUCCESS", True),
    302: ("Successful", "HTTP 302 Found", "inspection", "SUCCESS", True),
    400: ("Provider rejected the request", "HTTP 400 Bad Request", "remediation", "APPLICATION_ERROR", False),
    401: ("Provider authentication failed", "HTTP 401 Unauthorized", "remediation", "APPLICATION_ERROR", False),
    403: ("Provider denied the request", "HTTP 403 Forbidden", "remediation", "APPLICATION_ERROR", False),
    404: ("Provider endpoint not found", "HTTP 404 Not Found", "remediation", "APPLICATION_ERROR", False),
    408: ("Provider request timed out", "HTTP 408 Request Timeout", "remediation", "APPLICATION_ERROR", False),
    409: ("Provider reported a request conflict", "HTTP 409 Conflict", "remediation", "APPLICATION_ERROR", False),
    422: (
        "Provider could not process the request",
        "HTTP 422 Unprocessable Entity",
        "remediation",
        "APPLICATION_ERROR",
        False,
    ),
    429: ("Provider rate-limited the request", "HTTP 429 Too Many Requests", "remediation", "APPLICATION_ERROR", False),
    500: ("Provider service error", "HTTP 500 Internal Server Error", "remediation", "APPLICATION_ERROR", False),
    502: ("Provider service error", "HTTP 502 Bad Gateway", "remediation", "APPLICATION_ERROR", False),
    503: ("Provider service error", "HTTP 503 Service Unavailable", "remediation", "APPLICATION_ERROR", False),
}

_FORBIDDEN = ("Application error", "Optics error", "vantio tail", "vantio prove", "vantio run node")


class OutcomeMappingTests(unittest.TestCase):
    def test_http_lines_match_the_status_table(self) -> None:
        for status, (label, response, category, _token, _ok) in EXPECTED.items():
            self.assertEqual(http_outcome_label(status), label)
            self.assertEqual(http_response_text(status), response)
            self.assertNotIn("Application error", label)

    def test_other_4xx_stays_a_rejection_without_a_new_token(self) -> None:
        self.assertEqual(http_outcome_label(418), "Provider rejected the request")
        self.assertTrue(http_response_text(418).startswith("HTTP 418"))
        self.assertEqual(http_outcome_label(599), "Provider service error")

    def test_catalog_identity_is_exact_and_does_not_guess(self) -> None:
        catalog = {
            "api.openai.com": ("openai", "OpenAI"),
            "api.anthropic.com": ("anthropic", "Anthropic"),
            "generativelanguage.googleapis.com": ("google", "Google"),
            "api.cohere.ai": ("cohere", "Cohere"),
            "api.cohere.com": ("cohere", "Cohere"),
            "api.mistral.ai": ("mistral", "Mistral"),
            "api.groq.com": ("groq", "Groq"),
            "api.together.xyz": ("together", "Together"),
            "api.perplexity.ai": ("perplexity", "Perplexity"),
            "inference.ai.azure.com": ("azure_openai", "Azure OpenAI"),
            "openai.azure.com": ("azure_openai", "Azure OpenAI"),
            "api.x.ai": ("xai", "xAI"),
            "api.deepseek.com": ("deepseek", "DeepSeek"),
            "api.fireworks.ai": ("fireworks", "Fireworks"),
            "openrouter.ai": ("openrouter", "OpenRouter"),
            "api.cerebras.ai": ("cerebras", "Cerebras"),
            "api.voyageai.com": ("voyage", "Voyage"),
            "api.sambanova.ai": ("sambanova", "SambaNova"),
            "api.deepinfra.com": ("deepinfra", "DeepInfra"),
            "router.huggingface.co": ("huggingface", "Hugging Face"),
            "api-inference.huggingface.co": ("huggingface", "Hugging Face"),
            "api.replicate.com": ("replicate", "Replicate"),
            "ollama.com": ("ollama", "Ollama"),
            "integrate.api.nvidia.com": ("nvidia", "NVIDIA"),
            "bedrock-runtime.us-east-1.amazonaws.com": ("bedrock", "Bedrock"),
            "aiplatform.googleapis.com": ("vertex", "Vertex"),
            "my-model.endpoints.huggingface.cloud": ("huggingface", "Hugging Face"),
        }
        for host, ident in catalog.items():
            self.assertEqual(resolve_provider(host), ident, host)
        self.assertEqual(resolve_provider("foo.api.openai.com"), ("openai", "OpenAI"))
        self.assertEqual(resolve_provider("127.0.0.1", "11434"), ("ollama", "Ollama"))
        self.assertIsNone(resolve_provider("127.0.0.1"))
        self.assertIsNone(resolve_provider("203.0.113.10"))
        self.assertIsNone(resolve_provider("not-openai.example"))
        self.assertIsNone(resolve_provider("api.openai.com.evil.test"))

    def test_known_provider_uses_provider_response_wording(self) -> None:
        rec = {
            "hostname": "api.openai.com",
            "provider": "other",
            "status": 401,
            "opticsStatus": "SUCCESS",
            "applicationStatus": "APPLICATION_ERROR",
            "opticsLabel": "Successful",
        }
        apply_customer_outcome(rec)
        self.assertEqual(rec["provider"], "openai")
        self.assertEqual(rec["providerName"], "OpenAI")
        self.assertEqual(rec["destination"], "api.openai.com")
        self.assertNotIn("upstreamService", rec)
        self.assertEqual(
            customer_view_lines(rec),
            [
                "Optics status: Successful",
                "Observed outcome: Provider authentication failed",
                "Provider response: HTTP 401 Unauthorized",
            ],
        )
        self.assertEqual(rec["nextActionCategory"], "remediation")
        self.assertIn("shield()", rec["nextAction"])

    def test_unknown_host_uses_upstream_wording(self) -> None:
        rec = {
            "hostname": "203.0.113.10",
            "provider": "other",
            "status": 500,
            "opticsLabel": "Successful",
        }
        apply_customer_outcome(rec)
        self.assertEqual(rec["provider"], "other")
        self.assertNotIn("providerName", rec)
        self.assertEqual(rec["upstreamService"], "203.0.113.10")
        self.assertEqual(rec["providerResponseLabel"], "Upstream response")
        self.assertEqual(rec["applicationOutcomeLabel"], "Provider service error")
        self.assertEqual(rec["providerResponse"], "HTTP 500 Internal Server Error")

    def test_transport_classification_ignores_exception_text(self) -> None:
        secret = "sk-live-do-not-store"
        refused = urllib.error.URLError(ConnectionRefusedError(secret))
        kind, phrase = classify_exception(refused)
        self.assertEqual((kind, phrase), ("connection", "Connection refused"))
        self.assertNotIn(secret, phrase)
        dns = urllib.error.URLError(socket.gaierror(socket.EAI_NONAME, secret))
        self.assertEqual(classify_exception(dns), ("dns", "DNS lookup failed"))
        tls = urllib.error.URLError(ssl.SSLError(secret))
        self.assertEqual(classify_exception(tls), ("tls", "TLS handshake failed"))
        wrapped = RuntimeError(secret)
        self.assertEqual(classify_exception(wrapped), ("wrapped", "RuntimeError"))
        self.assertNotIn(secret, classify_exception(wrapped)[1])

    def test_empty_and_mixed_summary_lines(self) -> None:
        empty = empty_observation()
        self.assertEqual(empty["opticsStatus"], "NOT_OBSERVED")
        self.assertEqual(empty["applicationStatus"], "NOT_OBSERVED")
        self.assertEqual(empty["schema_status"], "unstable-pre-1.0")
        self.assertEqual(
            customer_view_lines(empty),
            [
                "Optics status: Not observed",
                "Observed outcome: No supported AI call observed",
                "Upstream response: ",
            ],
        )
        self.assertEqual(empty["nextActionCategory"], "inspection")
        mixed = summarize_customer_fields(
            [
                {"applicationOutcomeLabel": "Successful", "providerResponse": "HTTP 200 OK", "providerResponseLabel": "Upstream response"},
                {"applicationOutcomeLabel": "Provider service error", "providerResponse": "HTTP 500 Internal Server Error", "providerResponseLabel": "Upstream response"},
            ],
            "PARTIAL",
        )
        self.assertEqual(mixed["applicationOutcomeLabel"], "Partial")
        self.assertEqual(mixed["nextActionCategory"], "inspection")
        self.assertNotEqual(mixed["applicationOutcomeLabel"], "Application error")
        same_token = summarize_customer_fields(
            [
                {"applicationOutcomeLabel": "Provider authentication failed", "providerResponse": "HTTP 401 Unauthorized", "providerResponseLabel": "Upstream response", "nextActionCategory": "remediation", "nextAction": "cred"},
                {"applicationOutcomeLabel": "Provider service error", "providerResponse": "HTTP 500 Internal Server Error", "providerResponseLabel": "Upstream response", "nextActionCategory": "remediation", "nextAction": "retry"},
            ],
            "APPLICATION_ERROR",
        )
        self.assertEqual(same_token["applicationOutcomeLabel"], "Partial")
        single = summarize_customer_fields(
            [
                {
                    "applicationOutcomeLabel": "Provider authentication failed",
                    "providerResponse": "HTTP 401 Unauthorized",
                    "providerResponseLabel": "Provider response",
                    "nextActionCategory": "remediation",
                    "nextAction": "Check the API credential the agent sent, then run again under shield().",
                }
            ],
            "APPLICATION_ERROR",
        )
        self.assertEqual(single["applicationOutcomeLabel"], "Provider authentication failed")
        self.assertEqual(single["providerResponse"], "HTTP 401 Unauthorized")


class OutcomeIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._home = tempfile.mkdtemp()
        self._saved = {
            key: os.environ.get(key)
            for key in ("VANTIO_HOME", "VANTIO_EXTRA_LLM_HOSTS", "VANTIO_API_KEY", "VANTIO_INGEST_URL")
        }
        os.environ["VANTIO_HOME"] = self._home
        os.environ["VANTIO_EXTRA_LLM_HOSTS"] = "127.0.0.1,does-not-exist.invalid"
        os.environ.pop("VANTIO_API_KEY", None)
        os.environ.pop("VANTIO_INGEST_URL", None)
        self._timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(2)

    def tearDown(self) -> None:
        socket.setdefaulttimeout(self._timeout)
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _log(self, trace_id: str) -> dict:
        path = Path(self._home) / "runs" / f"{trace_id}.json"
        self.assertTrue(path.is_file(), trace_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def _assert_http_call(self, call: dict, status: int, mediation: str) -> None:
        label, response, category, token, ok = EXPECTED[status]
        self.assertEqual(call["mediation"], mediation)
        self.assertEqual(call["status"], status)
        self.assertIs(call["ok"], ok)
        self.assertEqual(call["opticsStatus"], "SUCCESS")
        self.assertNotEqual(call["opticsStatus"], "OPTICS_ERROR")
        self.assertEqual(call["applicationStatus"], token)
        self.assertEqual(call["opticsLabel"], "Successful")
        self.assertEqual(call["applicationOutcomeLabel"], label)
        self.assertEqual(call["applicationLabel"], label)
        self.assertEqual(call["providerResponse"], response)
        self.assertEqual(call["providerResponseLabel"], "Upstream response")
        self.assertEqual(call["upstreamService"], "127.0.0.1")
        self.assertNotIn("providerName", call)
        self.assertEqual(call["nextActionCategory"], category)
        self.assertNotEqual(call.get("error"), "network_error")
        blob = json.dumps(call)
        for banned in _FORBIDDEN:
            self.assertNotIn(banned, blob)
        for banned in ("blocked", "enforced"):
            self.assertNotIn(banned, call["nextAction"].lower())
            self.assertNotIn(banned, call["applicationOutcomeLabel"].lower())

    def _statuses_for(self, calls: list[dict], mediation: str) -> None:
        matched = [c for c in calls if c.get("mediation") == mediation]
        by_status: dict[int, list[dict]] = {}
        for call in matched:
            by_status.setdefault(call["status"], []).append(call)
        for status in HTTP_CODES:
            found = by_status.get(status) or []
            self.assertGreaterEqual(len(found), 1, f"{mediation} missing {status}")
            for call in found:
                self._assert_http_call(call, status, mediation)

    def _open_exact(self, opener: urllib.request.OpenerDirector, url: str, status: int) -> None:
        """Read one status. No redirect handler, so 302 stays 302."""
        try:
            resp = opener.open(url, timeout=2)
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, status)
            return
        got = getattr(resp, "status", None)
        if got is None:
            got = getattr(resp, "code", None)
        self.assertEqual(got, status)
        resp.read()

    def _urllib_codes(self, server: MockServer) -> None:
        opener = urllib.request.OpenerDirector()
        opener.add_handler(urllib.request.HTTPHandler())
        for status in HTTP_CODES:
            server.respond_with(status, {"n": status})
            self._open_exact(opener, server.url + f"/s/{status}", status)

    def _optional_clients(self, server: MockServer) -> set[str]:
        ran: set[str] = set()
        if requests is not None:
            ran.add("python_requests")
            for status in HTTP_CODES:
                server.respond_with(status, {"n": status})
                resp = requests.get(server.url + f"/s/{status}", timeout=2, allow_redirects=False)
                self.assertEqual(resp.status_code, status)
        if httpx is not None:
            ran.add("python_httpx")
            with httpx.Client(timeout=2, follow_redirects=False) as client:
                for status in HTTP_CODES:
                    server.respond_with(status, {"n": status})
                    resp = client.get(server.url + f"/s/{status}")
                    self.assertEqual(resp.status_code, status)
        if urllib3 is not None:
            ran.add("python_urllib3")
            http = urllib3.PoolManager()
            for status in HTTP_CODES:
                server.respond_with(status, {"n": status})
                resp = http.request("GET", server.url + f"/s/{status}", timeout=2.0, retries=False)
                self.assertEqual(resp.status, status)
        return ran

    async def _optional_async(self, server: MockServer) -> set[str]:
        ran: set[str] = set()
        if httpx is not None:
            ran.add("python_httpx")
            async with httpx.AsyncClient(timeout=2, follow_redirects=False) as client:
                for status in HTTP_CODES:
                    server.respond_with(status, {"n": status})
                    resp = await client.get(server.url + f"/s/{status}")
                    self.assertEqual(resp.status_code, status)
        if aiohttp is not None:
            ran.add("python_aiohttp")
            async with aiohttp.ClientSession() as session:
                for status in HTTP_CODES:
                    server.respond_with(status, {"n": status})
                    async with session.get(server.url + f"/s/{status}", allow_redirects=False) as resp:
                        self.assertEqual(resp.status, status)
                        await resp.read()
        return ran

    async def test_http_matrix_across_clients(self) -> None:
        with MockServer() as server:
            async with shield(trace_id="outcome-matrix"):
                self._urllib_codes(server)
                sync_ran = self._optional_clients(server)
                async_ran = await self._optional_async(server)
        data = self._log("outcome-matrix")
        self.assertEqual(data["schema_status"], "unstable-pre-1.0")
        self.assertEqual(data["status_labels"]["opticsStatus"], "Optics status")
        self.assertEqual(data["status_labels"]["applicationStatus"], "Observed outcome")
        self.assertEqual(data["summary"]["opticsStatus"], "SUCCESS")
        self.assertEqual(data["summary"]["applicationStatus"], "PARTIAL")
        self.assertEqual(data["summary"]["applicationOutcomeLabel"], "Partial")
        self.assertEqual(data["summary"]["nextActionCategory"], "inspection")
        blob = json.dumps(data)
        for banned in _FORBIDDEN:
            self.assertNotIn(banned, blob)
        self._statuses_for(data["calls"], "python_urllib")
        for mediation in sync_ran | async_ran:
            self._statuses_for(data["calls"], mediation)
        if "python_httpx" in async_ran:
            httpx_calls = [c for c in data["calls"] if c.get("mediation") == "python_httpx"]
            self.assertGreaterEqual(len(httpx_calls), len(HTTP_CODES) * 2)

    async def test_dns_connection_tls_wrapped_and_unavailable(self) -> None:
        secret = "sk-live-do-not-store"
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        refused_port = int(probe.getsockname()[1])
        probe.close()
        with MockServer() as server:
            server.respond_with(200, {"ok": True})
            async with shield(trace_id="outcome-transport"):
                with self.assertRaises(urllib.error.URLError):
                    urllib.request.urlopen("http://does-not-exist.invalid/v1/chat", timeout=2)
                with self.assertRaises(urllib.error.URLError):
                    urllib.request.urlopen(f"http://127.0.0.1:{refused_port}/v1/chat", timeout=2)
                with self.assertRaises(urllib.error.URLError):
                    urllib.request.urlopen(server.url.replace("http://", "https://", 1) + "/v1/chat", timeout=2)
                real = observe._orig_urlopen

                def boom(*args, **kwargs):
                    raise RuntimeError(secret)

                observe._orig_urlopen = boom
                try:
                    with self.assertRaises(RuntimeError):
                        urllib.request.urlopen(server.url + "/v1/chat", timeout=2)
                finally:
                    observe._orig_urlopen = real
                conn = http.client.HTTPConnection("127.0.0.1", server._server.server_address[1], timeout=2)
                conn.request("GET", "/v1/chat")
                resp = conn.getresponse()
                body = resp.read()
                self.assertEqual(resp.status, 200)
                self.assertNotIn(secret.encode(), body)
                conn.close()
        data = self._log("outcome-transport")
        blob = json.dumps(data)
        self.assertNotIn(secret, blob)
        for banned in _FORBIDDEN:
            self.assertNotIn(banned, blob)
        urllib_calls = [c for c in data["calls"] if c.get("mediation") == "python_urllib"]
        self.assertEqual(len(urllib_calls), 4)
        dns, refused, tls, wrapped = urllib_calls
        self._assert_transport(
            dns,
            label="Provider could not be resolved",
            response="DNS lookup failed",
            network=True,
        )
        self._assert_transport(
            refused,
            label="Connection to provider failed",
            response="Connection refused",
            network=True,
        )
        self._assert_transport(
            tls,
            label="Secure connection to provider failed",
            response="TLS handshake failed",
            network=True,
        )
        self._assert_transport(
            wrapped,
            label="Wrapped application raised an exception",
            response="RuntimeError",
            network=False,
        )
        self.assertEqual(wrapped["error_class"], "RuntimeError")
        self.assertNotIn("error", wrapped)
        client_calls = [c for c in data["calls"] if c.get("mediation") == "python_http_client"]
        self.assertEqual(len(client_calls), 1)
        unavailable = client_calls[0]
        self.assertIs(unavailable["ok"], True)
        self.assertNotIn("status", unavailable)
        self.assertEqual(unavailable["opticsStatus"], "SUCCESS")
        self.assertEqual(unavailable["applicationStatus"], "UNAVAILABLE")
        self.assertEqual(unavailable["applicationOutcomeLabel"], "Provider outcome unavailable")
        self.assertEqual(unavailable["providerResponse"], "No HTTP response")
        self.assertEqual(unavailable["nextActionCategory"], "inspection")
        self.assertEqual(
            customer_view_lines(unavailable),
            [
                "Optics status: Successful",
                "Observed outcome: Provider outcome unavailable",
                "Upstream response: No HTTP response",
            ],
        )

    def _assert_transport(self, call: dict, *, label: str, response: str, network: bool) -> None:
        self.assertEqual(call["opticsStatus"], "SUCCESS")
        self.assertNotEqual(call["opticsStatus"], "OPTICS_ERROR")
        self.assertEqual(call["applicationStatus"], "UNAVAILABLE")
        self.assertNotIn("status", call)
        self.assertIs(call["ok"], False)
        self.assertEqual(call["applicationOutcomeLabel"], label)
        self.assertEqual(call["applicationLabel"], label)
        self.assertEqual(call["providerResponse"], response)
        self.assertEqual(call["providerResponseLabel"], "Upstream response")
        self.assertEqual(call["nextActionCategory"], "remediation")
        if network:
            self.assertEqual(call["error"], "network_error")
        else:
            self.assertNotEqual(call.get("error"), "network_error")

    async def test_empty_shield_does_not_write_a_log(self) -> None:
        async with shield(trace_id="outcome-empty"):
            pass
        path = Path(self._home) / "runs" / "outcome-empty.json"
        self.assertFalse(path.exists())
        empty = empty_observation()
        self.assertEqual(empty["applicationOutcomeLabel"], "No supported AI call observed")
        self.assertEqual(empty["nextActionCategory"], "inspection")

    async def test_mixed_rollup_keeps_per_call_lines(self) -> None:
        with MockServer() as server:
            async with shield(trace_id="outcome-mixed"):
                opener = urllib.request.OpenerDirector()
                opener.add_handler(urllib.request.HTTPHandler())
                server.respond_with(200, {"ok": True})
                self._open_exact(opener, server.url + "/ok", 200)
                server.respond_with(401, {"err": True})
                self._open_exact(opener, server.url + "/auth", 401)
                server.respond_with(500, {"err": True})
                self._open_exact(opener, server.url + "/down", 500)
        data = self._log("outcome-mixed")
        self.assertEqual(data["summary"]["opticsStatus"], "SUCCESS")
        self.assertEqual(data["summary"]["applicationStatus"], "PARTIAL")
        self.assertEqual(data["summary"]["opticsLabel"], "Successful")
        self.assertEqual(data["summary"]["applicationOutcomeLabel"], "Partial")
        labels = [c["applicationOutcomeLabel"] for c in data["calls"]]
        self.assertEqual(
            labels,
            ["Successful", "Provider authentication failed", "Provider service error"],
        )
        self.assertEqual(
            customer_view_lines(data["calls"][1]),
            [
                "Optics status: Successful",
                "Observed outcome: Provider authentication failed",
                "Upstream response: HTTP 401 Unauthorized",
            ],
        )

    async def test_pycurl_success_path_does_not_invent_status(self) -> None:
        if pycurl is None:
            self.skipTest("pycurl is not installed; its success path stores no HTTP status")
        with MockServer() as server:
            server.respond_with(200, {"ok": True})
            async with shield(trace_id="outcome-pycurl"):
                curl = pycurl.Curl()
                curl.setopt(pycurl.URL, server.url + "/v1/chat")
                curl.setopt(pycurl.TIMEOUT, 2)
                curl.perform()
                curl.close()
        calls = [c for c in self._log("outcome-pycurl")["calls"] if c.get("mediation") == "python_pycurl"]
        self.assertEqual(len(calls), 1)
        self.assertNotIn("status", calls[0])
        self.assertEqual(calls[0]["applicationStatus"], "UNAVAILABLE")
        self.assertEqual(calls[0]["applicationOutcomeLabel"], "Provider outcome unavailable")
        self.assertEqual(calls[0]["providerResponse"], "No HTTP response")
