"""
[ ∅ VANTIO ] Python Agent SDK
Provides shield() decorator/context-manager and report_anomaly() for cloud ingest.
Zero dependencies beyond the Python standard library.
"""
from __future__ import annotations

import asyncio
import functools
import hashlib
import hmac
import json
import os
import urllib.request
import uuid
import warnings
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeVar

from ._telemetry import send_run_telemetry_once

T = TypeVar("T")

_trace_id_var: ContextVar[Optional[str]] = ContextVar("vantio_trace_id", default=None)


def _sdk_version() -> Optional[str]:
    """Best-effort SDK version for anonymous telemetry. Never raises."""
    try:
        from vantio import __version__  # lazy import — avoids an import cycle
        return __version__
    except Exception:
        return None


@dataclass
class VantioContext:
    trace_id: str


def _decorate(fn: Callable, trace_id: Optional[str]) -> Callable:
    """Shared decorator implementation used by both `@shield` (bare) and
    `@shield(trace_id=...)` (via _ShieldContextManager.__call__ below) so the
    two entry points can never drift out of sync with each other."""

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        tid = trace_id or str(uuid.uuid4())
        token = _trace_id_var.set(tid)
        # Lane 1: anonymous, opt-out, once-per-process usage ping. Never blocks.
        send_run_telemetry_once(_sdk_version())
        try:
            return await fn(*args, **kwargs)
        finally:
            _trace_id_var.reset(token)

    return wrapper


class _ShieldContextManager:
    """Async context manager form: async with shield() as ctx: ...

    Also callable as a decorator factory so `@shield(trace_id="x")` works —
    without __call__ here, `shield(trace_id="x")` returns this object, and
    `@shield(trace_id="x")` would then try to call it as a decorator and fail
    with a confusing "object is not callable" TypeError.
    """

    def __init__(self, trace_id: Optional[str] = None):
        self._trace_id = trace_id or str(uuid.uuid4())
        self._token = None

    async def __aenter__(self) -> VantioContext:
        self._token = _trace_id_var.set(self._trace_id)
        # Lane 1: anonymous, opt-out, once-per-process usage ping. Never blocks.
        send_run_telemetry_once(_sdk_version())
        return VantioContext(trace_id=self._trace_id)

    async def __aexit__(self, *_: Any) -> None:
        if self._token is not None:
            _trace_id_var.reset(self._token)

    def __call__(self, fn: Callable) -> Callable:
        return _decorate(fn, self._trace_id)


def shield(fn: Optional[Callable] = None, *, trace_id: Optional[str] = None):
    """
    shield() — canonical Vantio interceptor.

    Use as a decorator:
        @shield
        async def run_agent(): ...

    With an explicit, pinned trace id:
        @shield(trace_id="my-fixed-id")
        async def run_agent(): ...

    Or as a context manager:
        async with shield() as ctx:
            print(ctx.trace_id)
            await run_agent()

    Generates a VANTIO_TRACE_ID and propagates it via contextvars through
    every async hop in the call tree. Zero monkey-patching. Zero globals.
    """
    if fn is None:
        # Called as shield() or shield(trace_id=...) — return an object that
        # works as either an async context manager or a decorator factory,
        # since the caller's intent isn't known until it's used one way or
        # the other.
        return _ShieldContextManager(trace_id=trace_id)

    # Called as bare @shield.
    return _decorate(fn, trace_id)


def get_current_trace_id() -> Optional[str]:
    """Returns the VANTIO_TRACE_ID for the current async context, or None."""
    return _trace_id_var.get()


async def report_anomaly(
    *,
    target_host: Optional[str] = None,
    bytes_severed: Optional[int] = None,
    pid: Optional[int] = None,
    timestamp_ns: Optional[int] = None,
    action_taken: str = "OBSERVED",
    ingest_url: Optional[str] = None,
    api_key: Optional[str] = None,
    audit_mode: Optional[bool] = None,
) -> None:
    """
    Send an anomaly event to the Vantio ingest endpoint.
    Must be called within a shield() context. Non-fatal — never crashes the agent.
    Activated only when VANTIO_CLOUD_INGEST=true (or '1').
    """
    trace_id = get_current_trace_id()
    if trace_id is None:
        warnings.warn("[vantio] report_anomaly() called outside shield() context — skipping")
        return

    cloud = os.environ.get("VANTIO_CLOUD_INGEST", "").lower() in ("true", "1")
    if not cloud:
        return

    url = ingest_url or os.environ.get("VANTIO_INGEST_URL")
    key = api_key or os.environ.get("VANTIO_API_KEY")
    if not url or not key:
        return

    is_audit = audit_mode if audit_mode is not None else os.environ.get("VANTIO_AUDIT_MODE") == "1"

    payload = json.dumps({
        "traceId": trace_id,
        "auditMode": is_audit,
        "eventPayload": {
            k: v for k, v in {
                "target_host":   target_host,
                "bytes_severed": bytes_severed,
                "pid":           pid,
                "timestamp_ns":  timestamp_ns,
                "action_taken":  action_taken,
            }.items() if v is not None
        },
    }).encode("utf-8")

    # HMAC-SHA256 of the trace ID keyed by the API key.
    # Sent as x-vantio-hmac for optional future server-side validation.
    # Note: the server currently returns its own HMAC over the response in
    # x-vantio-signature; this outbound header is not validated server-side today.
    sig = hmac.new(key.encode(), trace_id.encode(), hashlib.sha256).hexdigest()

    try:
        req = urllib.request.Request(
            f"{url.rstrip('/')}/api/v1/ingest",
            data=payload,
            headers={
                "Content-Type":      "application/json",
                "x-vantio-identity": key,
                "x-vantio-hmac":     sig,
            },
            method="POST",
        )
        loop = asyncio.get_running_loop()
        # Bound the blocking urlopen — without a timeout a stalled ingest endpoint
        # would hang the executor thread (and this coroutine) indefinitely.
        await loop.run_in_executor(
            None, functools.partial(urllib.request.urlopen, req, timeout=5)
        )
    except Exception as exc:
        # Non-fatal — never crash the agent over an ingest failure. But NOT
        # silent: a bare `except: pass` here made a 403 (e.g. a free-tier key
        # attempting cloud ingest, which requires Pro/Enterprise) or any other
        # persistent failure completely invisible. Mirrors the JS SDK, which
        # already surfaces non-fatal ingest failures via console.warn.
        warnings.warn(f"[vantio] report_anomaly() ingest request failed (non-fatal): {exc}")
