"""
Sight Loop observe for Python HTTP clients while shield() is active.

Records host, path, status, and size — never prompts or completions.
In-scope LLM hosts (plus VANTIO_EXTRA_LLM_HOSTS), including regional Bedrock
and Vertex patterns and local Ollama on port 11434.

Wraps urllib.request.urlopen always. If requests, httpx, or aiohttp are
installed, wraps those too. Also wraps socket.connect / create_connection /
ssl.SSLSocket.connect to in-scope hosts (host-block and observe only — no TLS
payload redaction). Also wraps subprocess / os.system / asyncio curl and wget
spawns to in-scope hosts (host-block and observe; curl/wget bodies are not
rewritten). With a Gate API key, the same wrap can block, redact PII, or enforce
a spend limit on HTTP bodies. Browsers stay outside this wrap.
"""
from __future__ import annotations

import asyncio
import json
import os
import shlex
import socket
import ssl
import subprocess
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Iterator, Optional
from urllib.parse import urlparse

try:
    import requests as _requests
except ImportError:
    _requests = None  # type: ignore[assignment]

try:
    import httpx as _httpx
except ImportError:
    _httpx = None  # type: ignore[assignment]

try:
    import aiohttp as _aiohttp
except ImportError:
    _aiohttp = None  # type: ignore[assignment]

# Keep in lockstep with vantio-cli/bin/llm-hosts.cjs
_LLM_HOSTS = {
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "api.cohere.ai",
    "api.cohere.com",
    "api.mistral.ai",
    "api.groq.com",
    "api.together.xyz",
    "api.perplexity.ai",
    "inference.ai.azure.com",
    "openai.azure.com",
    "api.x.ai",
    "api.deepseek.com",
    "api.fireworks.ai",
    "openrouter.ai",
    "api.cerebras.ai",
    "api.voyageai.com",
    "api.sambanova.ai",
    "api.deepinfra.com",
    "router.huggingface.co",
    "api-inference.huggingface.co",
    "api.replicate.com",
    "ollama.com",
    "integrate.api.nvidia.com",
}

_lock = threading.Lock()
_depth = 0
_orig_urlopen = urllib.request.urlopen
_orig_requests_send: Any = None
_orig_httpx_sync_send: Any = None
_orig_httpx_async_send: Any = None
_orig_aiohttp_request: Any = None
_orig_socket_connect: Any = None
_orig_create_connection: Any = None
_orig_ssl_connect: Any = None
_orig_popen: Any = None
_orig_os_system: Any = None
_orig_asyncio_exec: Any = None
_orig_asyncio_shell: Any = None
_calls: list[dict[str, Any]] = []
_started_ms = 0.0
_trace_id = ""
# Gate on the wrap (same job as Node interceptor). Empty / missing key = Optics only.
_policy: dict[str, Any] = {
    "enforce": False,
    "redact_pii": False,
    "pii_types": ["ssn", "email", "credit_card", "phone"],
    "allowed_hosts": [],
    "blocked_hosts": [],
    "max_request_bytes": 0,
    "spend_cap_usd": 0.0,
    "dry_run": False,
}
_cloud_sync = False
_spent_usd = 0.0
# Same estimator as interceptor.cjs (rough token→USD; not a billing meter).
_USD_PER_BYTE = (5 / 1_000_000) / 4

# HTTP orig calls mark this so inner socket.connect is not ingested twice.
_http_owns_connect: ContextVar[bool] = ContextVar("vantio_http_owns_connect", default=False)
_http_owns_tls = threading.local()


class GateBlockedError(OSError):
    """Raised when Gate blocks a raw socket connect or a curl/wget spawn."""

    def __init__(self, hostname: str) -> None:
        super().__init__(f"Vantio Gate blocked host: {hostname}")
        self.hostname = hostname
        self.code = "VANTIO_GATE_BLOCKED"


@contextmanager
def _http_handled() -> Iterator[None]:
    token = _http_owns_connect.set(True)
    _http_owns_tls.depth = getattr(_http_owns_tls, "depth", 0) + 1
    try:
        yield
    finally:
        _http_owns_tls.depth = getattr(_http_owns_tls, "depth", 1) - 1
        _http_owns_connect.reset(token)


def _http_owns() -> bool:
    return _http_owns_connect.get() or getattr(_http_owns_tls, "depth", 0) > 0


def _http_orig(fn: Any, *args: Any, **kwargs: Any) -> Any:
    with _http_handled():
        return fn(*args, **kwargs)


async def _http_orig_async(fn: Any, *args: Any, **kwargs: Any) -> Any:
    with _http_handled():
        return await fn(*args, **kwargs)


def _extra_hosts() -> set[str]:
    raw = os.environ.get("VANTIO_EXTRA_LLM_HOSTS", "")
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def _host_listed(hostname: str, items: set[str]) -> bool:
    h = (hostname or "").lower()
    if not h:
        return False
    if h in items:
        return True
    for item in items:
        if item and "." in item and h.endswith("." + item):
            return True
    return False


def _host_matches_regional(hostname: str) -> bool:
    h = (hostname or "").lower()
    if not h:
        return False
    if h.startswith("bedrock-runtime") and h.endswith(".amazonaws.com"):
        # bedrock-runtime.{region}.amazonaws.com / bedrock-runtime-fips.{region}...
        labels = h.split(".")
        if len(labels) == 4 and labels[0] in ("bedrock-runtime", "bedrock-runtime-fips"):
            return True
    if h.startswith("bedrock-mantle.") and h.endswith(".api.aws"):
        labels = h.split(".")
        if len(labels) == 4 and labels[0] == "bedrock-mantle":
            return True
    if h.startswith("bedrock-agent-runtime") and h.endswith(".amazonaws.com"):
        labels = h.split(".")
        if len(labels) == 4 and labels[0] in (
            "bedrock-agent-runtime",
            "bedrock-agent-runtime-fips",
        ):
            return True
    if h == "aiplatform.googleapis.com":
        return True
    if h.endswith("-aiplatform.googleapis.com") and "." in h:
        return True
    if h in ("aiplatform.us.rep.googleapis.com", "aiplatform.eu.rep.googleapis.com"):
        return True
    if h == "endpoints.huggingface.cloud" or h.endswith(".endpoints.huggingface.cloud"):
        return True
    return False


def _is_ollama_local(hostname: str, port: Optional[str]) -> bool:
    h = (hostname or "").lower()
    p = "" if port is None else str(port)
    if p != "11434":
        return False
    return h in ("localhost", "127.0.0.1", "::1", "[::1]")


def _in_scope(hostname: str, port: Optional[str] = None) -> bool:
    return (
        _host_listed(hostname, _LLM_HOSTS | _extra_hosts())
        or _host_matches_regional(hostname)
        or _is_ollama_local(hostname, port)
        or _host_listed(hostname, set(_policy.get("blocked_hosts") or []))
        or _host_listed(hostname, set(_policy.get("allowed_hosts") or []))
    )


def _reset_policy() -> None:
    global _cloud_sync, _spent_usd
    _policy.update({
        "enforce": False,
        "redact_pii": False,
        "pii_types": ["ssn", "email", "credit_card", "phone"],
        "allowed_hosts": [],
        "blocked_hosts": [],
        "max_request_bytes": 0,
        "spend_cap_usd": 0.0,
        "dry_run": False,
    })
    _cloud_sync = False
    _spent_usd = 0.0


def _is_control_plane(hostname: str, path: str) -> bool:
    try:
        ingest = os.environ.get("VANTIO_INGEST_URL", "https://vantio.ai")
        parsed = urlparse(ingest)
        host = (parsed.hostname or "").lower()
        if not host or (hostname or "").lower() != host:
            return False
        return str(path or "").startswith("/api/v1/")
    except Exception:
        return False


def _is_control_plane_dest(hostname: str, port: Optional[str]) -> bool:
    """True when this TCP dest is the Gate control plane (any path)."""
    try:
        ingest = urlparse(os.environ.get("VANTIO_INGEST_URL") or "https://vantio.ai")
        host = (ingest.hostname or "").lower()
        if not host or (hostname or "").lower() != host:
            return False
        ingest_port = ingest.port or (443 if ingest.scheme == "https" else 80)
        if port is None or port == "":
            return True
        return str(port) == str(ingest_port)
    except Exception:
        return False


def _load_policy() -> None:
    """Fetch Gate policy before urllib is patched. Fail-open. Optics-only when no key."""
    global _cloud_sync
    _reset_policy()
    key = os.environ.get("VANTIO_API_KEY") or ""
    if not key.strip():
        return
    ingest = (os.environ.get("VANTIO_INGEST_URL") or "https://vantio.ai").rstrip("/")
    try:
        req = urllib.request.Request(
            f"{ingest}/api/v1/config",
            headers={"x-vantio-identity": key},
            method="GET",
        )
        with _orig_urlopen(req, timeout=5.0) as resp:
            if getattr(resp, "status", 200) != 200:
                return
            data = json.loads(resp.read().decode("utf-8"))
        if not isinstance(data, dict):
            return
        _cloud_sync = data.get("tier") in ("PRO", "ENTERPRISE")
        raw = data.get("policy") if isinstance(data.get("policy"), dict) else {}

        def _bool(v: Any, d: bool) -> bool:
            return v if isinstance(v, bool) else d

        def _str_list(v: Any) -> list[str]:
            return [x for x in v if isinstance(x, str)] if isinstance(v, list) else []

        def _nonneg(v: Any, d: float) -> float:
            try:
                n = float(v)
                return n if n >= 0 else d
            except (TypeError, ValueError):
                return d

        _policy.update({
            "enforce": _bool(raw.get("enforce"), False),
            "redact_pii": _bool(raw.get("redact_pii"), False),
            "pii_types": _str_list(raw.get("pii_types")) or ["ssn", "email", "credit_card", "phone"],
            "allowed_hosts": _str_list(raw.get("allowed_hosts")),
            "blocked_hosts": _str_list(raw.get("blocked_hosts")),
            "max_request_bytes": int(_nonneg(raw.get("max_request_bytes"), 0)),
            "spend_cap_usd": float(_nonneg(raw.get("spend_cap_usd"), 0.0)),
            "dry_run": _bool(raw.get("dry_run"), False),
        })
    except Exception:
        _reset_policy()


def _ingest(hostname: str, action: str, extra: Optional[dict[str, Any]] = None) -> None:
    if not _cloud_sync:
        return
    key = os.environ.get("VANTIO_API_KEY") or ""
    ingest = (os.environ.get("VANTIO_INGEST_URL") or "https://vantio.ai").rstrip("/")
    if not key:
        return
    payload = {
        "eventPayload": {
            "target_host": hostname,
            "pid": os.getpid(),
            "action_taken": action,
            "timestamp_ns": int(time.time() * 1e9),
            "bytes_severed": 0,
            "mediation": "python_wrap",
            "plane": "optics_gate",
            **(extra or {}),
        }
    }
    try:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{ingest}/api/v1/ingest",
            data=body,
            headers={
                "content-type": "application/json",
                "x-vantio-identity": key,
            },
            method="POST",
        )
        with _http_handled():
            _orig_urlopen(req, timeout=2.0).read()
    except Exception:
        return


def _redact_text(text: str) -> tuple[str, list[str]]:
    if not text or not _policy.get("redact_pii"):
        return text, []
    from vantio.sdk import redact_pii  # noqa: PLC0415

    result = redact_pii(text, _policy.get("pii_types") or None)
    return result.text, list(result.redactions)


def _body_to_text(body: Any) -> tuple[Optional[str], Optional[bytes], int]:
    """Return (text, bytes, length). Never raises."""
    if body is None:
        return None, None, 0
    if isinstance(body, bytes):
        try:
            return body.decode("utf-8"), body, len(body)
        except Exception:
            return None, body, len(body)
    if isinstance(body, bytearray):
        b = bytes(body)
        try:
            return b.decode("utf-8"), b, len(b)
        except Exception:
            return None, b, len(b)
    if isinstance(body, str):
        encoded = body.encode("utf-8")
        return body, encoded, len(encoded)
    return None, None, 0


def _gate_blocked_urllib(url: str, reason: str) -> urllib.error.HTTPError:
    payload = json.dumps({"error": "blocked_by_vantio", "reason": reason}).encode("utf-8")
    from email.message import EmailMessage

    hdrs = EmailMessage()
    hdrs["content-type"] = "application/json"
    hdrs["content-length"] = str(len(payload))
    return urllib.error.HTTPError(url, 403, reason, hdrs, BytesIO(payload))


def _gate_blocked_requests(reason: str) -> Any:
    if _requests is None:
        raise urllib.error.URLError(reason)
    resp = _requests.models.Response()
    resp.status_code = 403
    resp._content = json.dumps({"error": "blocked_by_vantio", "reason": reason}).encode("utf-8")
    resp.headers["content-type"] = "application/json"
    resp.reason = reason
    return resp


def _gate_blocked_httpx(reason: str) -> Any:
    if _httpx is None:
        raise urllib.error.URLError(reason)
    return _httpx.Response(
        403,
        json={"error": "blocked_by_vantio", "reason": reason},
    )


def _gate_blocked_aiohttp(method: str, url: Any, reason: str) -> BaseException:
    if _aiohttp is None:
        return urllib.error.URLError(reason)
    try:
        from multidict import CIMultiDict, CIMultiDictProxy
        from yarl import URL as YarlURL

        parsed = url if hasattr(url, "human_repr") else YarlURL(str(url))
        empty = CIMultiDict()
        request_info = _aiohttp.RequestInfo(
            parsed,
            str(method or "GET").upper(),
            CIMultiDictProxy(empty),
            parsed,
        )
        return _aiohttp.ClientResponseError(
            request_info,
            (),
            status=403,
            message=reason,
            headers=CIMultiDict({"content-type": "application/json"}),
        )
    except Exception:
        return _aiohttp.ClientError(f"blocked_by_vantio:{reason}")


def _aiohttp_request_body(kwargs: dict[str, Any]) -> Any:
    if kwargs.get("data") is not None:
        return kwargs["data"]
    if kwargs.get("json") is not None:
        try:
            return json.dumps(kwargs["json"])
        except Exception:
            return None
    return None

def _decide(hostname: str, port: Optional[str], path: str, body_len: int) -> str:
    """pass | observe | block | dry_block | block_size | dry_size | block_spend | dry_spend"""
    if not hostname or _is_control_plane(hostname, path) or not _in_scope(hostname, port):
        return "pass"
    key = os.environ.get("VANTIO_API_KEY") or ""
    if not key.strip():
        return "observe"
    if _policy.get("enforce"):
        blocked_list = set(_policy.get("blocked_hosts") or [])
        allowed_list = set(_policy.get("allowed_hosts") or [])
        blocked = _host_listed(hostname, blocked_list) or (
            len(allowed_list) > 0 and not _host_listed(hostname, allowed_list)
        )
        if blocked:
            return "dry_block" if _policy.get("dry_run") else "block"
        cap = int(_policy.get("max_request_bytes") or 0)
        if cap > 0 and body_len > cap:
            return "dry_size" if _policy.get("dry_run") else "block_size"
        spend_cap = float(_policy.get("spend_cap_usd") or 0.0)
        if spend_cap > 0 and _spent_usd >= spend_cap:
            return "dry_spend" if _policy.get("dry_run") else "block_spend"
    return "observe"


def _host_port_from_url(url: Any) -> tuple[str, Optional[str], str]:
    """Return (hostname, port, path). Never raises."""
    try:
        if hasattr(url, "host") and hasattr(url, "port") and not isinstance(url, str):
            host = str(getattr(url, "host", "") or "")
            port = getattr(url, "port", None)
            path = str(getattr(url, "path", "/") or "/")
            return host, (str(port) if port is not None else None), path
        raw = url
        if hasattr(url, "full_url"):
            raw = url.full_url
        parsed = urlparse(str(raw))
        host = parsed.hostname or ""
        port = parsed.port
        path = parsed.path or "/"
        return host, (str(port) if port is not None else None), path
    except Exception:
        return "", None, "/"


def _append(rec: dict[str, Any]) -> None:
    with _lock:
        _calls.append(rec)


def _record(
    hostname: str,
    action: str,
    mediation: str,
    **extra: Any,
) -> None:
    rec = {
        "hostname": hostname,
        "provider": extra.pop("provider", "other"),
        "action": action,
        "mediation": mediation,
        "ts": datetime.now(timezone.utc).isoformat(),
        **extra,
    }
    _append(rec)
    ingest_map = {
        "OBSERVED": None,
        "ALLOWED": "ALLOWED",
        "REDACTED": "REDACTED",
        "BLOCKED_HOST": "BLOCKED_HOST",
        "BLOCKED_SIZE": "BLOCKED_SIZE",
        "BLOCKED_SPEND": "BLOCKED_SPEND",
        "DRY_RUN_BLOCKED_HOST": "DRY_RUN_BLOCKED_HOST",
        "DRY_RUN_BLOCKED_SIZE": "DRY_RUN_BLOCKED_SIZE",
        "DRY_RUN_BLOCKED_SPEND": "DRY_RUN_BLOCKED_SPEND",
    }
    ingest_action = ingest_map.get(action)
    if ingest_action:
        ingest_extra: dict[str, Any] = {"mediation": mediation}
        if rec.get("bytes_observed") is not None:
            ingest_extra["bytes_observed"] = rec["bytes_observed"]
        _ingest(hostname, ingest_action, ingest_extra)


def _apply_body(body: Any) -> tuple[Any, list[str], int]:
    text, raw, length = _body_to_text(body)
    if text is None:
        return body, [], length
    new_text, redactions = _redact_text(text)
    if not redactions:
        return body, [], length
    encoded = new_text.encode("utf-8")
    if isinstance(body, (bytes, bytearray)):
        return encoded, redactions, len(encoded)
    return new_text, redactions, len(encoded)


def _dispatch_gate(
    hostname: str,
    port: Optional[str],
    path: str,
    body: Any,
    mediation: str,
) -> tuple[str, Any, list[str], bool]:
    """Returns (kind, payload, redactions, record_send).

    kind: pass | block | send
    payload: original body, a block reason string, or the (possibly redacted) body
    record_send: False when a dry-run event was already recorded
    """
    _, _, length = _body_to_text(body)
    decision = _decide(hostname, port, path, length)
    if decision == "pass":
        return "pass", body, [], False
    if decision == "block":
        _record(hostname, "BLOCKED_HOST", mediation, path=path, ok=False)
        return "block", "host_not_permitted", [], False
    if decision == "block_size":
        _record(hostname, "BLOCKED_SIZE", mediation, path=path, ok=False)
        return "block", "request_too_large", [], False
    if decision == "block_spend":
        _record(hostname, "BLOCKED_SPEND", mediation, path=path, ok=False)
        return "block", "spend_cap_reached", [], False
    send_body, redactions, _ = _apply_body(body)
    if decision == "dry_block":
        _record(hostname, "DRY_RUN_BLOCKED_HOST", mediation, path=path)
        return "send", send_body, redactions, False
    if decision == "dry_size":
        _record(hostname, "DRY_RUN_BLOCKED_SIZE", mediation, path=path)
        return "send", send_body, redactions, False
    if decision == "dry_spend":
        _record(hostname, "DRY_RUN_BLOCKED_SPEND", mediation, path=path)
        return "send", send_body, redactions, False
    return "send", send_body, redactions, True


def _account_response_bytes(headers: Any) -> None:
    global _spent_usd
    if not headers:
        return
    try:
        cl = headers.get("content-length") if hasattr(headers, "get") else None
        if cl:
            _spent_usd += int(cl) * _USD_PER_BYTE
    except (TypeError, ValueError, AttributeError):
        return


def _observe_urlopen(url, data=None, timeout=None, *args, **kwargs):
    hostname, port, path = _host_port_from_url(url)
    try:
        raw_url = url
        if hasattr(url, "full_url"):
            raw_url = url.full_url
        scheme = "https" if str(raw_url).startswith("https") else "http"
        url_s = str(raw_url)
    except Exception:
        scheme = "https"
        url_s = str(url)

    body = data if data is not None else getattr(url, "data", None)
    kind, payload, redactions, record_send = _dispatch_gate(
        hostname, port, path, body, "python_urllib"
    )
    if kind == "pass":
        return _http_orig(_orig_urlopen, url, data, timeout, *args, **kwargs)
    if kind == "block":
        raise _gate_blocked_urllib(url_s, str(payload))

    send_data = data
    if data is None and hasattr(url, "data"):
        if redactions:
            try:
                url.data = (
                    payload
                    if isinstance(payload, (bytes, bytearray))
                    else str(payload).encode("utf-8")
                )
            except Exception:
                send_data = payload
    else:
        send_data = payload

    t0 = time.time()
    try:
        resp = _http_orig(_orig_urlopen, url, send_data, timeout, *args, **kwargs)
        _account_response_bytes(getattr(resp, "headers", None))
        if record_send:
            action = "REDACTED" if redactions else ("ALLOWED" if _cloud_sync else "OBSERVED")
            _record(
                hostname,
                action,
                "python_urllib",
                method="POST" if data is not None else "GET",
                path=path,
                scheme=scheme,
                status=getattr(resp, "status", None) or getattr(resp, "code", None),
                ok=True,
                duration_ms=int((time.time() - t0) * 1000),
            )
        return resp
    except Exception as exc:
        _record(
            hostname,
            "OBSERVED",
            "python_urllib",
            method="POST" if data is not None else "GET",
            path=path,
            scheme=scheme,
            status=getattr(exc, "code", None),
            ok=False,
            duration_ms=int((time.time() - t0) * 1000),
            error="network_error",
            error_class=type(exc).__name__,
        )
        raise


def _install_requests() -> None:
    global _orig_requests_send
    if _requests is None:
        return
    _orig_requests_send = _requests.sessions.Session.send

    def _observe_send(self, request, **kwargs):  # type: ignore[no-untyped-def]
        hostname, port, path = _host_port_from_url(getattr(request, "url", ""))
        body = getattr(request, "body", None)
        kind, payload, redactions, record_send = _dispatch_gate(
            hostname, port, path, body, "python_requests"
        )
        if kind == "pass":
            return _http_orig(_orig_requests_send, self, request, **kwargs)
        if kind == "block":
            return _gate_blocked_requests(str(payload))
        if redactions:
            request.body = payload
        t0 = time.time()
        method = str(getattr(request, "method", "GET") or "GET").upper()
        scheme = "https" if str(getattr(request, "url", "")).startswith("https") else "http"
        try:
            resp = _http_orig(_orig_requests_send, self, request, **kwargs)
            _account_response_bytes(getattr(resp, "headers", None))
            if record_send:
                action = "REDACTED" if redactions else ("ALLOWED" if _cloud_sync else "OBSERVED")
                _record(
                    hostname,
                    action,
                    "python_requests",
                    method=method,
                    path=path,
                    scheme=scheme,
                    status=getattr(resp, "status_code", None),
                    ok=True,
                    duration_ms=int((time.time() - t0) * 1000),
                )
            return resp
        except Exception as exc:
            _record(
                hostname,
                "OBSERVED",
                "python_requests",
                method=method,
                path=path,
                scheme=scheme,
                ok=False,
                duration_ms=int((time.time() - t0) * 1000),
                error="network_error",
                error_class=type(exc).__name__,
            )
            raise

    _requests.sessions.Session.send = _observe_send  # type: ignore[assignment]


def _uninstall_requests() -> None:
    global _orig_requests_send
    if _orig_requests_send is None:
        return
    try:
        if _requests is not None:
            _requests.sessions.Session.send = _orig_requests_send
    except Exception:
        pass
    _orig_requests_send = None


def _install_httpx() -> None:
    global _orig_httpx_sync_send, _orig_httpx_async_send
    if _httpx is None:
        return
    _orig_httpx_sync_send = _httpx.Client.send
    _orig_httpx_async_send = _httpx.AsyncClient.send

    def _observe_sync(self, request, **kwargs):  # type: ignore[no-untyped-def]
        hostname, port, path = _host_port_from_url(getattr(request, "url", ""))
        body = getattr(request, "content", None)
        kind, payload, redactions, record_send = _dispatch_gate(
            hostname, port, path, body, "python_httpx"
        )
        if kind == "pass":
            return _http_orig(_orig_httpx_sync_send, self, request, **kwargs)
        if kind == "block":
            return _gate_blocked_httpx(str(payload))
        t0 = time.time()
        method = str(getattr(request, "method", "GET") or "GET").upper()
        scheme = "https" if str(request.url).startswith("https") else "http"
        try:
            resp = _http_orig(_orig_httpx_sync_send, self, request, **kwargs)
            _account_response_bytes(getattr(resp, "headers", None))
            if record_send:
                action = "REDACTED" if redactions else ("ALLOWED" if _cloud_sync else "OBSERVED")
                _record(
                    hostname,
                    action,
                    "python_httpx",
                    method=method,
                    path=path,
                    scheme=scheme,
                    status=getattr(resp, "status_code", None),
                    ok=True,
                    duration_ms=int((time.time() - t0) * 1000),
                )
            return resp
        except Exception as exc:
            _record(
                hostname,
                "OBSERVED",
                "python_httpx",
                method=method,
                path=path,
                scheme=scheme,
                ok=False,
                duration_ms=int((time.time() - t0) * 1000),
                error="network_error",
                error_class=type(exc).__name__,
            )
            raise

    async def _observe_async(self, request, **kwargs):  # type: ignore[no-untyped-def]
        hostname, port, path = _host_port_from_url(getattr(request, "url", ""))
        body = getattr(request, "content", None)
        kind, payload, redactions, record_send = _dispatch_gate(
            hostname, port, path, body, "python_httpx"
        )
        if kind == "pass":
            return await _http_orig_async(_orig_httpx_async_send, self, request, **kwargs)
        if kind == "block":
            return _gate_blocked_httpx(str(payload))
        t0 = time.time()
        method = str(getattr(request, "method", "GET") or "GET").upper()
        scheme = "https" if str(request.url).startswith("https") else "http"
        try:
            resp = await _http_orig_async(_orig_httpx_async_send, self, request, **kwargs)
            _account_response_bytes(getattr(resp, "headers", None))
            if record_send:
                action = "REDACTED" if redactions else ("ALLOWED" if _cloud_sync else "OBSERVED")
                _record(
                    hostname,
                    action,
                    "python_httpx",
                    method=method,
                    path=path,
                    scheme=scheme,
                    status=getattr(resp, "status_code", None),
                    ok=True,
                    duration_ms=int((time.time() - t0) * 1000),
                )
            return resp
        except Exception as exc:
            _record(
                hostname,
                "OBSERVED",
                "python_httpx",
                method=method,
                path=path,
                scheme=scheme,
                ok=False,
                duration_ms=int((time.time() - t0) * 1000),
                error="network_error",
                error_class=type(exc).__name__,
            )
            raise

    _httpx.Client.send = _observe_sync  # type: ignore[assignment]
    _httpx.AsyncClient.send = _observe_async  # type: ignore[assignment]


def _uninstall_httpx() -> None:
    global _orig_httpx_sync_send, _orig_httpx_async_send
    if _orig_httpx_sync_send is None and _orig_httpx_async_send is None:
        return
    try:
        if _httpx is not None:
            if _orig_httpx_sync_send is not None:
                _httpx.Client.send = _orig_httpx_sync_send
            if _orig_httpx_async_send is not None:
                _httpx.AsyncClient.send = _orig_httpx_async_send
    except Exception:
        pass
    _orig_httpx_sync_send = None
    _orig_httpx_async_send = None


def _install_aiohttp() -> None:
    global _orig_aiohttp_request
    if _aiohttp is None:
        return
    _orig_aiohttp_request = _aiohttp.ClientSession._request

    async def _observe_request(self, method, str_or_url, **kwargs):  # type: ignore[no-untyped-def]
        hostname, port, path = _host_port_from_url(str_or_url)
        body = _aiohttp_request_body(kwargs)
        kind, payload, redactions, record_send = _dispatch_gate(
            hostname, port, path, body, "python_aiohttp"
        )
        if kind == "pass":
            return await _http_orig_async(_orig_aiohttp_request, self, method, str_or_url, **kwargs)
        if kind == "block":
            raise _gate_blocked_aiohttp(str(method), str_or_url, str(payload))
        send_kwargs = dict(kwargs)
        if redactions:
            if kwargs.get("json") is not None and isinstance(payload, str):
                try:
                    send_kwargs["json"] = json.loads(payload)
                except json.JSONDecodeError:
                    send_kwargs.pop("json", None)
                    send_kwargs["data"] = payload
            else:
                send_kwargs["data"] = payload
        t0 = time.time()
        method_s = str(method or "GET").upper()
        try:
            raw = str(str_or_url)
        except Exception:
            raw = ""
        scheme = "https" if raw.startswith("https") else "http"
        try:
            resp = await _http_orig_async(_orig_aiohttp_request, self, method, str_or_url, **send_kwargs)
            _account_response_bytes(getattr(resp, "headers", None))
            if record_send:
                action = "REDACTED" if redactions else ("ALLOWED" if _cloud_sync else "OBSERVED")
                _record(
                    hostname,
                    action,
                    "python_aiohttp",
                    method=method_s,
                    path=path,
                    scheme=scheme,
                    status=getattr(resp, "status", None),
                    ok=True,
                    duration_ms=int((time.time() - t0) * 1000),
                )
            return resp
        except Exception as exc:
            _record(
                hostname,
                "OBSERVED",
                "python_aiohttp",
                method=method_s,
                path=path,
                scheme=scheme,
                ok=False,
                duration_ms=int((time.time() - t0) * 1000),
                error="network_error",
                error_class=type(exc).__name__,
            )
            raise

    _aiohttp.ClientSession._request = _observe_request  # type: ignore[assignment]


def _uninstall_aiohttp() -> None:
    global _orig_aiohttp_request
    if _orig_aiohttp_request is None:
        return
    try:
        if _aiohttp is not None:
            _aiohttp.ClientSession._request = _orig_aiohttp_request
    except Exception:
        pass
    _orig_aiohttp_request = None


def _addr_host_port(address: Any) -> tuple[Optional[str], Optional[str], bool]:
    """Return (hostname, port, is_ipc). Never raises."""
    try:
        if isinstance(address, bytes):
            address = address.decode("utf-8", "replace")
        if isinstance(address, str):
            return None, None, True
        if isinstance(address, (tuple, list)) and address:
            host = address[0]
            port = address[1] if len(address) > 1 else None
            if isinstance(host, bytes):
                host = host.decode("utf-8", "replace")
            if isinstance(host, str) and ("/" in host or host.startswith("\0")):
                return None, None, True
            hostname = str(host).replace("[", "").replace("]", "") if host else None
            return hostname, (str(port) if port is not None else None), False
    except Exception:
        return None, None, False
    return None, None, False


def _gate_socket_dest(hostname: Optional[str], port: Optional[str]) -> str:
    """pass | connect | block. Records observe/dry-run when needed."""
    if not hostname or _http_owns() or _is_control_plane_dest(hostname, port):
        return "pass"
    kind, _payload, _redactions, record_send = _dispatch_gate(
        hostname, port, "/", None, "python_socket"
    )
    if kind == "pass":
        return "pass"
    if kind == "block":
        return "block"
    if record_send:
        action = "ALLOWED" if _cloud_sync else "OBSERVED"
        _record(hostname, action, "python_socket")
    return "connect"


def _observe_socket_connect(self: Any, address: Any, *args: Any, **kwargs: Any) -> Any:
    hostname, port, ipc = _addr_host_port(address)
    if ipc:
        return _orig_socket_connect(self, address, *args, **kwargs)
    decision = _gate_socket_dest(hostname, port)
    if decision == "block":
        raise GateBlockedError(hostname or "")
    return _orig_socket_connect(self, address, *args, **kwargs)


def _observe_ssl_connect(self: Any, address: Any, *args: Any, **kwargs: Any) -> Any:
    hostname, port, ipc = _addr_host_port(address)
    if ipc:
        with _http_handled():
            return _orig_ssl_connect(self, address, *args, **kwargs)
    decision = _gate_socket_dest(hostname, port)
    if decision == "block":
        raise GateBlockedError(hostname or "")
    with _http_handled():
        return _orig_ssl_connect(self, address, *args, **kwargs)


def _observe_create_connection(address: Any, *args: Any, **kwargs: Any) -> Any:
    hostname, port, ipc = _addr_host_port(address)
    if ipc:
        with _http_handled():
            return _orig_create_connection(address, *args, **kwargs)
    decision = _gate_socket_dest(hostname, port)
    if decision == "block":
        raise GateBlockedError(hostname or "")
    with _http_handled():
        return _orig_create_connection(address, *args, **kwargs)


def _install_socket() -> None:
    global _orig_socket_connect, _orig_create_connection, _orig_ssl_connect
    if _orig_socket_connect is not None:
        return
    _orig_socket_connect = socket.socket.connect
    _orig_create_connection = socket.create_connection
    ssl_own = None
    try:
        ssl_own = ssl.SSLSocket.connect
        if ssl_own is _orig_socket_connect:
            ssl_own = None
    except Exception:
        ssl_own = None
    socket.socket.connect = _observe_socket_connect  # type: ignore[method-assign]
    socket.create_connection = _observe_create_connection  # type: ignore[assignment]
    if ssl_own is not None:
        _orig_ssl_connect = ssl_own
        ssl.SSLSocket.connect = _observe_ssl_connect  # type: ignore[method-assign]
    else:
        _orig_ssl_connect = None


def _uninstall_socket() -> None:
    global _orig_socket_connect, _orig_create_connection, _orig_ssl_connect
    try:
        if _orig_socket_connect is not None:
            socket.socket.connect = _orig_socket_connect
        if _orig_create_connection is not None:
            socket.create_connection = _orig_create_connection
        if _orig_ssl_connect is not None:
            ssl.SSLSocket.connect = _orig_ssl_connect
    except Exception:
        pass
    _orig_socket_connect = None
    _orig_create_connection = None
    _orig_ssl_connect = None


def _cmd_base(file: Any) -> str:
    try:
        name = os.path.basename(str(file or "")).lower()
        if name.endswith(".exe"):
            name = name[:-4]
        return name
    except Exception:
        return ""


def _tokenize_shell(s: str) -> list[str]:
    try:
        return shlex.split(str(s or ""), posix=True)
    except Exception:
        return []


def _http_cli_from_spawn(command: Any, argv: Any) -> Optional[tuple[str, list[str]]]:
    args = [str(a) for a in list(argv or [])]
    base = _cmd_base(command)
    if base in ("curl", "wget"):
        return base, args
    if base not in ("sh", "bash", "dash", "zsh"):
        return None
    try:
        c_idx = args.index("-c")
    except ValueError:
        return None
    if c_idx + 1 >= len(args):
        return None
    tokens = _tokenize_shell(args[c_idx + 1])
    if not tokens:
        return None
    tool = _cmd_base(tokens[0])
    if tool not in ("curl", "wget"):
        return None
    return tool, tokens[1:]


def _http_cli_from_exec(command: Any) -> Optional[tuple[str, list[str]]]:
    tokens = _tokenize_shell(str(command or ""))
    if not tokens:
        return None
    tool = _cmd_base(tokens[0])
    if tool in ("curl", "wget"):
        return tool, tokens[1:]
    return _http_cli_from_spawn(tokens[0], tokens[1:])


def _http_cli_from_popen(args: Any, kwargs: dict[str, Any]) -> Optional[tuple[str, list[str]]]:
    shell = bool(kwargs.get("shell"))
    if isinstance(args, bytes):
        args = args.decode("utf-8", "replace")
    if isinstance(args, str):
        if shell:
            return _http_cli_from_exec(args)
        base = _cmd_base(args)
        if base in ("curl", "wget"):
            return base, []
        return None
    try:
        seq = list(args)
    except TypeError:
        return None
    if not seq:
        return None
    if shell:
        return _http_cli_from_exec(" ".join(str(x) for x in seq))
    return _http_cli_from_spawn(seq[0], seq[1:])


def _parse_curl_argv(argv: list[str]) -> tuple[Optional[str], int]:
    url: Optional[str] = None
    data_bytes = 0
    args = [str(a) for a in argv]
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--url", "-url"):
            url = args[i + 1] if i + 1 < len(args) else None
            i += 2
            continue
        if a.startswith("--url="):
            url = a[len("--url="):]
            i += 1
            continue
        if a in (
            "-d", "--data", "--data-raw", "--data-binary",
            "--data-ascii", "--data-urlencode", "--json",
        ):
            value = args[i + 1] if i + 1 < len(args) else ""
            data_bytes += len(str(value).encode("utf-8"))
            i += 2
            continue
        if a.startswith("-d") and len(a) > 2 and not a.startswith("--"):
            data_bytes += len(a[2:].encode("utf-8"))
            i += 1
            continue
        if url is None and (a.startswith("http://") or a.startswith("https://")):
            url = a
        i += 1
    return url, data_bytes


def _parse_wget_argv(argv: list[str]) -> tuple[Optional[str], int]:
    url: Optional[str] = None
    data_bytes = 0
    args = [str(a) for a in argv]
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--post-data", "--body-data"):
            value = args[i + 1] if i + 1 < len(args) else ""
            data_bytes += len(str(value).encode("utf-8"))
            i += 2
            continue
        if a.startswith("--post-data="):
            data_bytes += len(a[len("--post-data="):].encode("utf-8"))
            i += 1
            continue
        if a.startswith("--body-data="):
            data_bytes += len(a[len("--body-data="):].encode("utf-8"))
            i += 1
            continue
        if url is None and (a.startswith("http://") or a.startswith("https://")):
            url = a
        i += 1
    return url, data_bytes


def _parse_cli_argv(tool: str, argv: list[str]) -> tuple[Optional[str], int]:
    if tool == "wget":
        return _parse_wget_argv(argv)
    return _parse_curl_argv(argv)


def _apply_cli_gate(tool: str, argv: list[str]) -> Optional[GateBlockedError]:
    global _spent_usd
    url, data_bytes = _parse_cli_argv(tool, argv)
    if not url:
        return None
    hostname, port, path = _host_port_from_url(url)
    decision = _decide(hostname, port, path, data_bytes)
    if decision == "pass":
        return None
    mediation = "python_wget" if tool == "wget" else "python_curl"
    extra = {"path": path, "bytes_observed": data_bytes}
    if decision == "block":
        _record(hostname, "BLOCKED_HOST", mediation, ok=False, **extra)
        return GateBlockedError(hostname or "")
    if decision == "block_size":
        _record(hostname, "BLOCKED_SIZE", mediation, ok=False, **extra)
        return GateBlockedError(hostname or "")
    if decision == "block_spend":
        _record(hostname, "BLOCKED_SPEND", mediation, ok=False, **extra)
        return GateBlockedError(hostname or "")
    if decision == "dry_block":
        _record(hostname, "DRY_RUN_BLOCKED_HOST", mediation, **extra)
    elif decision == "dry_size":
        _record(hostname, "DRY_RUN_BLOCKED_SIZE", mediation, **extra)
    elif decision == "dry_spend":
        _record(hostname, "DRY_RUN_BLOCKED_SPEND", mediation, **extra)
    else:
        action = "ALLOWED" if _cloud_sync else "OBSERVED"
        _record(hostname, action, mediation, **extra)
        _spent_usd += (data_bytes or 0) * _USD_PER_BYTE
    return None


class _VantioPopen(subprocess.Popen):
    def __init__(self, args: Any, *pargs: Any, **kwargs: Any) -> None:
        try:
            cli = _http_cli_from_popen(args, kwargs)
            if cli is not None:
                err = _apply_cli_gate(cli[0], cli[1])
                if err is not None:
                    raise err
        except GateBlockedError:
            raise
        except Exception:
            pass
        super().__init__(args, *pargs, **kwargs)


def _observe_os_system(command: Any) -> Any:
    try:
        cli = _http_cli_from_exec(command)
        if cli is not None:
            err = _apply_cli_gate(cli[0], cli[1])
            if err is not None:
                raise err
    except GateBlockedError:
        raise
    except Exception:
        pass
    return _orig_os_system(command)


async def _observe_asyncio_exec(program: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        cli = _http_cli_from_spawn(program, args)
        if cli is not None:
            err = _apply_cli_gate(cli[0], cli[1])
            if err is not None:
                raise err
    except GateBlockedError:
        raise
    except Exception:
        pass
    return await _orig_asyncio_exec(program, *args, **kwargs)


async def _observe_asyncio_shell(cmd: Any, **kwargs: Any) -> Any:
    try:
        cli = _http_cli_from_exec(cmd)
        if cli is not None:
            err = _apply_cli_gate(cli[0], cli[1])
            if err is not None:
                raise err
    except GateBlockedError:
        raise
    except Exception:
        pass
    return await _orig_asyncio_shell(cmd, **kwargs)


def _install_curl_spawn() -> None:
    global _orig_popen, _orig_os_system, _orig_asyncio_exec, _orig_asyncio_shell
    if _orig_popen is not None:
        return
    _orig_popen = subprocess.Popen
    subprocess.Popen = _VantioPopen  # type: ignore[misc,assignment]
    _orig_os_system = os.system
    os.system = _observe_os_system  # type: ignore[assignment]
    _orig_asyncio_exec = asyncio.create_subprocess_exec
    _orig_asyncio_shell = asyncio.create_subprocess_shell
    asyncio.create_subprocess_exec = _observe_asyncio_exec  # type: ignore[assignment]
    asyncio.create_subprocess_shell = _observe_asyncio_shell  # type: ignore[assignment]


def _uninstall_curl_spawn() -> None:
    global _orig_popen, _orig_os_system, _orig_asyncio_exec, _orig_asyncio_shell
    try:
        if _orig_popen is not None:
            subprocess.Popen = _orig_popen
        if _orig_os_system is not None:
            os.system = _orig_os_system
        if _orig_asyncio_exec is not None:
            asyncio.create_subprocess_exec = _orig_asyncio_exec
        if _orig_asyncio_shell is not None:
            asyncio.create_subprocess_shell = _orig_asyncio_shell
    except Exception:
        pass
    _orig_popen = None
    _orig_os_system = None
    _orig_asyncio_exec = None
    _orig_asyncio_shell = None


def _write_run_log() -> None:
    if not _calls or not _trace_id:
        return
    try:
        home = os.environ.get("VANTIO_HOME") or os.path.join(os.path.expanduser("~"), ".vantio")
        runs = os.path.join(home, "runs")
        os.makedirs(runs, mode=0o700, exist_ok=True)
        now = datetime.now(timezone.utc)
        hosts = sorted({c.get("hostname") or "unknown" for c in _calls})
        mediations = sorted({c.get("mediation") or "python_urllib" for c in _calls})
        payload = {
            "vantio_run_log": "1",
            "schema_version": 2,
            "plane": "optics",
            "workflow": "sight_loop",
            "data_note": "Developer egress data log — metadata only; never prompts or completions.",
            "trace_id": _trace_id,
            "runtime": "python",
            "mediation": ",".join(mediations),
            "started_at": datetime.fromtimestamp(_started_ms, timezone.utc).isoformat() if _started_ms else now.isoformat(),
            "generated_at": now.isoformat(),
            "calls": list(_calls),
            "summary": {
                "total_calls": len(_calls),
                "hosts": hosts,
            },
            "residual": {
                "note": "Python wrap observes urllib, requests/httpx/aiohttp when installed, socket.connect / create_connection, and subprocess curl/wget to in-scope LLM hosts. With a Gate key it can also block, redact PII, or enforce a spend limit on HTTP bodies. Curl and wget bodies are not rewritten. Browsers stay outside this wrap.",
            },
        }
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in _trace_id)[:80]
        path = os.path.join(runs, f"{safe}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
            fh.write("\n")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    except Exception:
        return


def install(trace_id: str) -> None:
    global _depth, _started_ms, _trace_id
    with _lock:
        _depth += 1
        if _depth == 1:
            _calls.clear()
            _started_ms = time.time()
            _trace_id = trace_id
            _load_policy()
            urllib.request.urlopen = _observe_urlopen  # type: ignore[assignment]
            _install_requests()
            _install_httpx()
            _install_aiohttp()
            _install_socket()
            _install_curl_spawn()


def uninstall() -> None:
    global _depth
    with _lock:
        if _depth <= 0:
            return
        _depth -= 1
        if _depth == 0:
            urllib.request.urlopen = _orig_urlopen  # type: ignore[assignment]
            _uninstall_requests()
            _uninstall_httpx()
            _uninstall_aiohttp()
            _uninstall_socket()
            _uninstall_curl_spawn()
            _write_run_log()
            _reset_policy()
