"""
Vantio Optics Python SDK — Sight Loop observe.
Provides shield() decorator/context-manager, report_anomaly() for cloud ingest,
fetch_policy() for policy retrieval, and redact_pii() for local PII scrubbing.
Zero dependencies beyond the Python standard library. requests, httpx, and
aiohttp are optional: if they are installed, shield() observes them the same way
as urllib.
"""
from __future__ import annotations

import asyncio
import functools
import hashlib
import hmac
import json
import os
import re
import urllib.request
import urllib.error
import uuid
import warnings
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, TypeVar

from ._http_observe import install as install_http_observe
from ._http_observe import uninstall as uninstall_http_observe
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
        install_http_observe(tid)
        try:
            return await fn(*args, **kwargs)
        finally:
            uninstall_http_observe()
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
        install_http_observe(self._trace_id)
        return VantioContext(trace_id=self._trace_id)

    async def __aexit__(self, *_: Any) -> None:
        uninstall_http_observe()
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
    every async hop in the call tree. While active, shield() observes urllib
    and, when those libraries are installed, requests, httpx, and aiohttp —
    metadata only. socket.connect and subprocess curl/wget to in-scope hosts share
    host-block and observe. Browsers stay outside this wrap.
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


# ── Policy fetch (parity with JS SDK fetchPolicy) ─────────────────────────────


@dataclass
class VantioPolicy:
    """
    Cloud-managed policy returned by GET /api/v1/config (Tier 2).
    Mirrors VantioPolicy in @vantio/agent-sdk.

    Enforcement runs locally — this object drives block/redact/cap decisions
    in your SDK code. Fetch with fetch_policy(); build manually for testing.

    Note: the ``pii_redact`` attribute corresponds to ``redact_pii`` in the
    JSON policy object and in the JS SDK. Named ``pii_redact`` here to avoid
    shadowing the module-level ``redact_pii()`` function.
    """
    enforce: bool = False
    pii_redact: bool = False
    pii_types: List[str] = field(default_factory=lambda: ["ssn", "email", "credit_card", "phone"])
    allowed_hosts: List[str] = field(default_factory=list)
    blocked_hosts: List[str] = field(default_factory=list)
    max_request_bytes: int = 0
    spend_cap_usd: float = 0.0
    # When true, enforcement decisions should be logged/reported as DRY_RUN_*
    # events but requests are NOT blocked. Mirrors dry_run in the JS SDK.
    dry_run: bool = False


def _normalize_policy(raw: dict) -> VantioPolicy:
    """Coerce an untrusted policy dict to a VantioPolicy with safe defaults."""
    def _bool(v: Any, d: bool) -> bool:
        return v if isinstance(v, bool) else d

    def _str_list(v: Any, d: List[str]) -> List[str]:
        if isinstance(v, list):
            return [x for x in v if isinstance(x, str)]
        return list(d)

    def _nonneg(v: Any, d: float) -> float:
        try:
            n = float(v)
            return n if n >= 0 else d
        except (TypeError, ValueError):
            return d

    return VantioPolicy(
        enforce=_bool(raw.get("enforce"), False),
        pii_redact=_bool(raw.get("redact_pii"), False),
        pii_types=_str_list(raw.get("pii_types"), ["ssn", "email", "credit_card", "phone"]),
        allowed_hosts=_str_list(raw.get("allowed_hosts"), []),
        blocked_hosts=_str_list(raw.get("blocked_hosts"), []),
        max_request_bytes=int(_nonneg(raw.get("max_request_bytes"), 0)),
        spend_cap_usd=float(_nonneg(raw.get("spend_cap_usd"), 0.0)),
        dry_run=_bool(raw.get("dry_run"), False),
    )


def fetch_policy(
    api_key: str,
    *,
    ingest_url: Optional[str] = None,
    timeout: float = 5.0,
) -> VantioPolicy:
    """
    Fetch the cloud-managed policy from GET /api/v1/config.

    Fails open: on any network failure, non-2xx status, malformed body, or
    timeout, a permissive default :class:`VantioPolicy` is returned so an
    unreachable control plane can never block the agent.

    Mirrors ``fetchPolicy()`` in ``@vantio/agent-sdk``.

    Args:
        api_key:    Your Vantio API key (``VANTIO_API_KEY``).
        ingest_url: Override the control plane base URL.
                    Defaults to ``VANTIO_INGEST_URL`` env var or ``https://vantio.ai``.
        timeout:    Request timeout in seconds (default 5.0).

    Returns:
        A :class:`VantioPolicy` reflecting the tenant's current policy.

    Example::

        from vantio import fetch_policy, redact_pii
        import os

        policy = fetch_policy(os.environ["VANTIO_API_KEY"])
        if policy.pii_redact:
            result = redact_pii(user_input, policy.pii_types)
            prompt = result.text   # PII scrubbed before it reaches the LLM
    """
    url = (
        ingest_url or os.environ.get("VANTIO_INGEST_URL", "https://vantio.ai")
    ).rstrip("/")
    try:
        req = urllib.request.Request(
            f"{url}/api/v1/config",
            headers={"x-vantio-identity": api_key},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return VantioPolicy()
            data = json.loads(resp.read().decode("utf-8"))
            if not isinstance(data, dict) or "policy" not in data:
                return VantioPolicy()
            p = data["policy"]
            return _normalize_policy(p) if isinstance(p, dict) else VantioPolicy()
    except Exception:
        # Fail open — the control plane being unreachable must never crash the agent.
        return VantioPolicy()


# ── Local PII redaction (parity with JS SDK redactPII) ────────────────────────

# Patterns kept identical to interceptor.cjs and @vantio/agent-sdk.
_PY_PII_PATTERNS: dict = {
    "ssn":         (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
                    "SSN"),
    "email":       (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
                    "EMAIL"),
    "credit_card": (re.compile(r"\b(?:\d[ \-]?){13,16}\b"),
                    "CC"),
    "phone":       (re.compile(r"\b\(?\d{3}\)?[\-.\s]?\d{3}[\-.\s]?\d{4}\b"),
                    "PHONE"),
}


@dataclass
class RedactionResult:
    """
    Result of a :func:`redact_pii` call.

    Attributes:
        text:       The input string with matched PII spans replaced by
                    ``[VANTIO_REDACTED:LABEL]`` tokens.
        redactions: The PII category name for each redacted span, one entry
                    per replacement, in the order they appear in *text*.
                    Empty when no PII was found.
    """
    text: str
    redactions: List[str]


def redact_pii(
    text: str,
    pii_types: Optional[List[str]] = None,
) -> RedactionResult:
    """
    Locally redact PII from *text* using the same patterns as the CLI
    interceptor and the Node.js SDK (``redactPII``).

    Replaces matches with ``[VANTIO_REDACTED:LABEL]``. Pure and
    side-effect-free — no content ever leaves the process.

    Mirrors ``redactPII()`` in ``@vantio/agent-sdk``.

    Args:
        text:      The string to scan and redact.
        pii_types: PII categories to check. Defaults to all four built-in
                   categories: ``["ssn", "email", "credit_card", "phone"]``.
                   Values are normalised to lowercase before lookup, so
                   ``"EMAIL"`` and ``"email"`` are equivalent.

    Returns:
        A :class:`RedactionResult` with ``.text`` (redacted string) and
        ``.redactions`` (list of matched category names).

    Example::

        from vantio import redact_pii

        result = redact_pii("Contact bob@example.com or call 555-123-4567")
        # result.text       → "Contact [VANTIO_REDACTED:EMAIL] or call [VANTIO_REDACTED:PHONE]"
        # result.redactions → ["email", "phone"]
    """
    if pii_types is None:
        pii_types = ["ssn", "email", "credit_card", "phone"]
    if not isinstance(text, str):
        return RedactionResult(text=text, redactions=[])

    out = text
    redactions: List[str] = []

    for typ in pii_types:
        key = typ.strip().lower() if isinstance(typ, str) else str(typ)
        entry = _PY_PII_PATTERNS.get(key)
        if not entry:
            continue
        pattern, label = entry
        new_out, count = pattern.subn(f"[VANTIO_REDACTED:{label}]", out)
        if count > 0:
            redactions.extend([key] * count)
            out = new_out

    return RedactionResult(text=out, redactions=redactions)
