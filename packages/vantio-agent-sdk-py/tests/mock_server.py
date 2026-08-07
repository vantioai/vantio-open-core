"""A minimal threaded HTTP server for exercising the SDK's real network paths
end-to-end (urllib.request.urlopen for the sync SDK, background threads for
telemetry) without mocking internals. Records every request it receives.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Optional


class RecordedRequest:
    def __init__(self, method: str, path: str, headers: dict, body: bytes) -> None:
        self.method = method
        self.path = path
        self.headers = headers
        self.body = body

    @property
    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8")) if self.body else None


class MockServer:
    """Usage:

        with MockServer() as server:
            server.respond_with(200, {"ok": True})
            ... make a request to server.url ...
            assert len(server.requests) == 1
    """

    def __init__(self) -> None:
        self.requests: list[RecordedRequest] = []
        self._status = 200
        self._body: bytes = b"{}"
        self._lock = threading.Lock()
        self._handler_override: Optional[Callable[[RecordedRequest], tuple[int, bytes]]] = None

        recorder = self

        class Handler(BaseHTTPRequestHandler):
            def _handle(self) -> None:
                length = int(self.headers.get("Content-Length", 0) or 0)
                body = self.rfile.read(length) if length else b""
                req = RecordedRequest(self.command, self.path, dict(self.headers), body)
                recorder.requests.append(req)

                with recorder._lock:
                    if recorder._handler_override is not None:
                        status, resp_body = recorder._handler_override(req)
                    else:
                        status, resp_body = recorder._status, recorder._body

                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp_body)))
                self.end_headers()
                self.wfile.write(resp_body)

            def do_GET(self) -> None:  # noqa: N802 (stdlib API name)
                self._handle()

            def do_POST(self) -> None:  # noqa: N802
                self._handle()

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                pass  # Silence default access-log noise in test output.

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def respond_with(self, status: int, body: dict) -> None:
        with self._lock:
            self._status = status
            self._body = json.dumps(body).encode("utf-8")
            self._handler_override = None

    def respond_with_handler(self, fn: Callable[[RecordedRequest], tuple[int, bytes]]) -> None:
        with self._lock:
            self._handler_override = fn

    def __enter__(self) -> "MockServer":
        self._thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self._server.shutdown()
        self._server.server_close()
