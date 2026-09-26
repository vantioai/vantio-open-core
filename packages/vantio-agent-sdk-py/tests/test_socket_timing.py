"""Socket duration is measured around the real connect, on this interpreter."""
from __future__ import annotations

import json
import os
import socket
import ssl
import tempfile
import threading
import time
import unittest
from pathlib import Path

from vantio import shield
from vantio import _http_observe as observe

DELAY_S = 0.25
MIN_MS = 200


class _TcpSink:
    def __init__(self) -> None:
        self.port = 0
        self._sock: socket.socket | None = None
        self._alive = False
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "_TcpSink":
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(5)
        self.port = int(self._sock.getsockname()[1])
        self._alive = True

        def _run() -> None:
            while self._alive and self._sock is not None:
                try:
                    self._sock.settimeout(0.2)
                    conn, _addr = self._sock.accept()
                    conn.close()
                except (socket.timeout, TimeoutError):
                    continue
                except OSError:
                    if not self._alive:
                        return
                    continue

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._alive = False
        if self._sock is not None:
            self._sock.close()


class SocketTimingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._home = tempfile.mkdtemp()
        self._saved = {
            key: os.environ.get(key)
            for key in ("VANTIO_HOME", "VANTIO_EXTRA_LLM_HOSTS", "VANTIO_API_KEY")
        }
        os.environ["VANTIO_HOME"] = self._home
        os.environ["VANTIO_EXTRA_LLM_HOSTS"] = "127.0.0.1"
        os.environ.pop("VANTIO_API_KEY", None)

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _calls(self, trace_id: str) -> list[dict]:
        path = Path(self._home) / "runs" / f"{trace_id}.json"
        self.assertTrue(path.is_file(), trace_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        return [c for c in data["calls"] if c.get("mediation") == "python_socket"]

    def _assert_timed(self, call: dict, *, ok: bool) -> None:
        self.assertIsInstance(call["duration_ms"], int)
        self.assertGreaterEqual(call["duration_ms"], MIN_MS)
        self.assertLess(call["duration_ms"], 5000)
        self.assertIs(call["ok"], ok)
        self.assertEqual(call["opticsStatus"], "SUCCESS")
        self.assertEqual(call["applicationStatus"], "UNAVAILABLE")
        self.assertEqual(call["opticsLabel"], "Successful")
        self.assertEqual(call["applicationLabel"], call["applicationOutcomeLabel"])
        self.assertNotIn("Application error", call["applicationOutcomeLabel"])
        self.assertNotIn("Optics error", call["applicationOutcomeLabel"])
        if ok:
            self.assertNotIn("error", call)
            self.assertEqual(call["applicationOutcomeLabel"], "Provider outcome unavailable")
            self.assertEqual(call["providerResponse"], "No HTTP response")
            self.assertEqual(call["nextActionCategory"], "inspection")
        else:
            self.assertEqual(call["error"], "network_error")
            self.assertIn(
                call["applicationOutcomeLabel"],
                ("Connection to provider failed", "Secure connection to provider failed"),
            )
            self.assertEqual(call["nextActionCategory"], "remediation")

    async def test_connect_duration_covers_the_real_connect(self) -> None:
        with _TcpSink() as sink:
            async with shield(trace_id="py-time-connect"):
                real = observe._orig_socket_connect

                def slow(self, address, *args, **kwargs):
                    time.sleep(DELAY_S)
                    return real(self, address, *args, **kwargs)

                observe._orig_socket_connect = slow
                try:
                    sock = socket.socket()
                    sock.settimeout(2)
                    sock.connect(("127.0.0.1", sink.port))
                    sock.close()
                finally:
                    observe._orig_socket_connect = real
        call = self._calls("py-time-connect")[0]
        self._assert_timed(call, ok=True)
        self.assertEqual(call["action"], "OBSERVED")

    async def test_connect_ex_duration_covers_the_real_connect(self) -> None:
        with _TcpSink() as sink:
            async with shield(trace_id="py-time-connect-ex"):
                real = observe._orig_socket_connect_ex

                def slow(self, address):
                    time.sleep(DELAY_S)
                    return real(self, address)

                observe._orig_socket_connect_ex = slow
                try:
                    sock = socket.socket()
                    sock.settimeout(2)
                    rc = sock.connect_ex(("127.0.0.1", sink.port))
                    sock.close()
                finally:
                    observe._orig_socket_connect_ex = real
        self.assertEqual(rc, 0)
        call = self._calls("py-time-connect-ex")[0]
        self._assert_timed(call, ok=True)

    async def test_create_connection_duration_covers_the_real_connect(self) -> None:
        with _TcpSink() as sink:
            async with shield(trace_id="py-time-create"):
                real = observe._orig_create_connection

                def slow(address, *args, **kwargs):
                    time.sleep(DELAY_S)
                    return real(address, *args, **kwargs)

                observe._orig_create_connection = slow
                try:
                    sock = socket.create_connection(("127.0.0.1", sink.port), timeout=2)
                    sock.close()
                finally:
                    observe._orig_create_connection = real
        call = self._calls("py-time-create")[0]
        self._assert_timed(call, ok=True)

    async def test_refused_connect_is_a_timed_network_error(self) -> None:
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        port = int(probe.getsockname()[1])
        probe.close()
        async with shield(trace_id="py-time-refused"):
            real = observe._orig_socket_connect

            def slow(self, address, *args, **kwargs):
                time.sleep(DELAY_S)
                return real(self, address, *args, **kwargs)

            observe._orig_socket_connect = slow
            try:
                sock = socket.socket()
                sock.settimeout(2)
                with self.assertRaises(OSError):
                    sock.connect(("127.0.0.1", port))
                sock.close()
            finally:
                observe._orig_socket_connect = real
        call = self._calls("py-time-refused")[0]
        self._assert_timed(call, ok=False)

    async def test_ssl_connect_uses_the_timed_path(self) -> None:
        """Prove the SSL entry that this interpreter actually installs."""
        with _TcpSink() as sink:
            async with shield(trace_id="py-time-ssl"):
                distinct = (
                    observe._orig_ssl_connect is not None
                    and ssl.SSLSocket.connect is observe._observe_ssl_connect
                )
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                if not distinct:
                    self.assertIs(ssl.SSLSocket.connect, socket.socket.connect)
                    real = observe._orig_socket_connect

                    def slow_connect(self, address, *args, **kwargs):
                        time.sleep(DELAY_S)
                        return real(self, address, *args, **kwargs)

                    observe._orig_socket_connect = slow_connect
                    saved = real
                    slot = "_orig_socket_connect"
                else:
                    real = observe._orig_ssl_connect

                    def slow_ssl(self, address, *args, **kwargs):
                        time.sleep(DELAY_S)
                        return real(self, address, *args, **kwargs)

                    observe._orig_ssl_connect = slow_ssl
                    saved = real
                    slot = "_orig_ssl_connect"
                try:
                    raw = socket.socket()
                    raw.settimeout(2)
                    wrapped = ctx.wrap_socket(raw, server_hostname="127.0.0.1")
                    with self.assertRaises(OSError):
                        wrapped.connect(("127.0.0.1", sink.port))
                    wrapped.close()
                finally:
                    setattr(observe, slot, saved)
        call = self._calls("py-time-ssl")[0]
        self._assert_timed(call, ok=False)
