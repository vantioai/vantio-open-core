import asyncio
import hashlib
import hmac
import os
import re
import unittest
import warnings

from vantio import get_current_trace_id, report_anomaly, shield
from vantio.sdk import VantioContext

from .mock_server import MockServer

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


class ShieldDecoratorTests(unittest.IsolatedAsyncioTestCase):
    async def test_generates_a_random_trace_id(self) -> None:
        seen = {}

        @shield
        async def run_agent() -> None:
            seen["trace_id"] = get_current_trace_id()

        await run_agent()
        self.assertIsNotNone(seen["trace_id"])
        self.assertRegex(seen["trace_id"], UUID_RE)

    async def test_uses_an_explicit_trace_id(self) -> None:
        seen = {}

        @shield(trace_id="fixed-id-123")
        async def run_agent() -> None:
            seen["trace_id"] = get_current_trace_id()

        await run_agent()
        self.assertEqual(seen["trace_id"], "fixed-id-123")

    async def test_get_current_trace_id_is_none_outside_any_frame(self) -> None:
        self.assertIsNone(get_current_trace_id())

    async def test_propagates_the_return_value(self) -> None:
        @shield
        async def run_agent() -> int:
            return 42

        self.assertEqual(await run_agent(), 42)

    async def test_propagates_an_exception(self) -> None:
        @shield
        async def run_agent() -> None:
            raise ValueError("boom")

        with self.assertRaises(ValueError):
            await run_agent()

    async def test_trace_id_is_restored_after_the_decorated_call_completes(self) -> None:
        @shield(trace_id="inner-id")
        async def inner() -> None:
            pass

        @shield(trace_id="outer-id")
        async def outer() -> None:
            self.assertEqual(get_current_trace_id(), "outer-id")
            await inner()
            self.assertEqual(get_current_trace_id(), "outer-id")

        await outer()
        self.assertIsNone(get_current_trace_id())

    async def test_concurrent_calls_do_not_leak_trace_ids(self) -> None:
        results = {}

        @shield(trace_id="task-a")
        async def task_a() -> None:
            await asyncio.sleep(0.01)
            results["a"] = get_current_trace_id()

        @shield(trace_id="task-b")
        async def task_b() -> None:
            await asyncio.sleep(0.01)
            results["b"] = get_current_trace_id()

        await asyncio.gather(task_a(), task_b())
        self.assertEqual(results, {"a": "task-a", "b": "task-b"})


class ShieldContextManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_context_manager_form_exposes_a_trace_id(self) -> None:
        async with shield() as ctx:
            self.assertIsInstance(ctx, VantioContext)
            self.assertRegex(ctx.trace_id, UUID_RE)
            self.assertEqual(get_current_trace_id(), ctx.trace_id)
        self.assertIsNone(get_current_trace_id())

    async def test_context_manager_respects_an_explicit_trace_id(self) -> None:
        async with shield(trace_id="explicit-cm-id") as ctx:
            self.assertEqual(ctx.trace_id, "explicit-cm-id")
            self.assertEqual(get_current_trace_id(), "explicit-cm-id")


class ReportAnomalyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._saved_env = {
            k: os.environ.get(k)
            for k in ("VANTIO_CLOUD_INGEST", "VANTIO_INGEST_URL", "VANTIO_API_KEY", "VANTIO_AUDIT_MODE")
        }
        for k in self._saved_env:
            os.environ.pop(k, None)

    def tearDown(self) -> None:
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    async def test_warns_and_skips_outside_a_shield_context(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            await report_anomaly(target_host="api.openai.com")
        self.assertTrue(any("outside shield() context" in str(w.message) for w in caught))

    async def test_noop_when_cloud_ingest_is_not_activated(self) -> None:
        with MockServer() as server:
            os.environ["VANTIO_INGEST_URL"] = server.url
            os.environ["VANTIO_API_KEY"] = "vk_test_key"
            # VANTIO_CLOUD_INGEST deliberately left unset.
            async with shield():
                await report_anomaly(target_host="api.openai.com")
            self.assertEqual(len(server.requests), 0)

    async def test_noop_when_url_or_key_missing_even_with_cloud_ingest_true(self) -> None:
        with MockServer() as server:
            os.environ["VANTIO_CLOUD_INGEST"] = "true"
            # No VANTIO_INGEST_URL / VANTIO_API_KEY set.
            async with shield():
                await report_anomaly(target_host="api.openai.com")
            self.assertEqual(len(server.requests), 0)

    async def test_sends_the_expected_request_shape_and_hmac(self) -> None:
        with MockServer() as server:
            server.respond_with(200, {"status": 0})
            os.environ["VANTIO_CLOUD_INGEST"] = "1"
            async with shield(trace_id="trace-xyz") as ctx:
                await report_anomaly(
                    target_host="api.openai.com",
                    bytes_severed=99,
                    pid=4242,
                    action_taken="BLOCKED_HOST",
                    ingest_url=server.url,
                    api_key="vk_test_key",
                    audit_mode=True,
                )

            self.assertEqual(len(server.requests), 1)
            req = server.requests[0]
            self.assertEqual(req.method, "POST")
            self.assertEqual(req.path, "/api/v1/ingest")
            self.assertEqual(req.headers.get("X-Vantio-Identity"), "vk_test_key")

            body = req.json
            self.assertEqual(body["traceId"], "trace-xyz")
            self.assertEqual(body["traceId"], ctx.trace_id)
            self.assertEqual(body["auditMode"], True)
            self.assertEqual(
                body["eventPayload"],
                {
                    "target_host": "api.openai.com",
                    "bytes_severed": 99,
                    "pid": 4242,
                    "action_taken": "BLOCKED_HOST",
                },
            )

            expected_hmac = hmac.new(b"vk_test_key", b"trace-xyz", hashlib.sha256).hexdigest()
            self.assertEqual(req.headers.get("X-Vantio-Hmac"), expected_hmac)

    async def test_warns_non_fatal_on_a_server_error_response(self) -> None:
        with MockServer() as server:
            server.respond_with(500, {"error": "boom"})
            os.environ["VANTIO_CLOUD_INGEST"] = "true"
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                async with shield():
                    # Must not raise even though the server 500s.
                    await report_anomaly(
                        target_host="x", ingest_url=server.url, api_key="vk_test_key"
                    )
            self.assertTrue(any("ingest request failed" in str(w.message) for w in caught))

    async def test_warns_non_fatal_on_a_connection_failure(self) -> None:
        os.environ["VANTIO_CLOUD_INGEST"] = "true"
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            async with shield():
                # Port 1 is reserved — connection refused, never a real server.
                await report_anomaly(
                    target_host="x", ingest_url="http://127.0.0.1:1", api_key="vk_test_key"
                )
        self.assertTrue(any("ingest request failed" in str(w.message) for w in caught))


if __name__ == "__main__":
    unittest.main()
