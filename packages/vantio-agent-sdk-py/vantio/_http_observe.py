"""
Sight Loop observe for Python HTTP clients while shield() is active.

Records host, path, status, and size — never prompts or completions.
In-scope LLM hosts (plus VANTIO_EXTRA_LLM_HOSTS), including regional Bedrock
and Vertex patterns and local Ollama on port 11434.

Wraps urllib.request.urlopen and OpenerDirector.open always. If requests,
httpx, aiohttp, urllib3, or pycurl are installed, wraps those too. Also wraps
socket.connect / connect_ex / create_connection / ssl.SSLSocket.connect and
http.client request/putrequest to in-scope hosts (host-block and observe; TLS
payloads are not read). Also wraps subprocess / os.system / asyncio curl, wget,
httpie, and aria2c spawns to in-scope hosts (host-block and observe; file-body
and curl -F size from stat; stdin size when stdin is a file; wget -i URL lines;
inline argv bodies are rewritten for Gate PII; file contents and stdin pipes
are not read). With a Gate API key, the same wrap can block, redact PII, or
enforce a spend limit on HTTP bodies. Browsers stay outside this wrap.
"""
from __future__ import annotations

import asyncio
import http.client
import json
import os
import shlex
import socket
import ssl
import stat
import subprocess
import sys
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

try:
    import urllib3 as _urllib3
except ImportError:
    _urllib3 = None  # type: ignore[assignment]

try:
    import pycurl as _pycurl
except ImportError:
    _pycurl = None  # type: ignore[assignment]

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
_orig_opener_open: Any = None
_orig_requests_send: Any = None
_orig_httpx_sync_send: Any = None
_orig_httpx_async_send: Any = None
_orig_aiohttp_request: Any = None
_orig_socket_connect: Any = None
_orig_socket_connect_ex: Any = None
_orig_create_connection: Any = None
_orig_ssl_connect: Any = None
_orig_http_request: Any = None
_orig_http_putrequest: Any = None
_orig_urllib3_request: Any = None
_orig_pycurl_curl: Any = None
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
    """Raised when Gate blocks a raw socket connect, http.client request, or a curl/wget spawn."""

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


def _httpx_set_content(request: Any, payload: Any) -> None:
    encoded = payload if isinstance(payload, (bytes, bytearray)) else str(payload).encode("utf-8")
    encoded = bytes(encoded)
    try:
        request._content = encoded
    except Exception:
        return
    try:
        if _httpx is not None:
            request.stream = _httpx.ByteStream(encoded)
    except Exception:
        pass
    try:
        headers = getattr(request, "headers", None)
        if headers is not None:
            headers["content-length"] = str(len(encoded))
    except Exception:
        pass


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


def _observe_opener_open(self, fullurl, data=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT):  # type: ignore[no-untyped-def]
    if _http_owns():
        return _orig_opener_open(self, fullurl, data, timeout)
    hostname, port, path = _host_port_from_url(fullurl)
    try:
        raw_url = fullurl
        if hasattr(fullurl, "full_url"):
            raw_url = fullurl.full_url
        url_s = str(raw_url)
        scheme = "https" if url_s.startswith("https") else "http"
    except Exception:
        scheme = "https"
        url_s = str(fullurl)
    body = data if data is not None else getattr(fullurl, "data", None)
    kind, payload, redactions, record_send = _dispatch_gate(
        hostname, port, path, body, "python_urllib"
    )
    if kind == "pass":
        return _http_orig(_orig_opener_open, self, fullurl, data, timeout)
    if kind == "block":
        raise _gate_blocked_urllib(url_s, str(payload))
    send_data = data
    if data is None and hasattr(fullurl, "data"):
        if redactions:
            try:
                fullurl.data = (
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
        resp = _http_orig(_orig_opener_open, self, fullurl, send_data, timeout)
        _account_response_bytes(getattr(resp, "headers", None))
        if record_send:
            action = "REDACTED" if redactions else ("ALLOWED" if _cloud_sync else "OBSERVED")
            _record(
                hostname,
                action,
                "python_urllib",
                method="POST" if (data is not None or body is not None) else "GET",
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
            method="POST" if (data is not None or body is not None) else "GET",
            path=path,
            scheme=scheme,
            status=getattr(exc, "code", None),
            ok=False,
            duration_ms=int((time.time() - t0) * 1000),
            error="network_error",
            error_class=type(exc).__name__,
        )
        raise


def _install_opener() -> None:
    global _orig_opener_open
    if _orig_opener_open is not None:
        return
    _orig_opener_open = urllib.request.OpenerDirector.open
    urllib.request.OpenerDirector.open = _observe_opener_open  # type: ignore[assignment]


def _uninstall_opener() -> None:
    global _orig_opener_open
    try:
        if _orig_opener_open is not None:
            urllib.request.OpenerDirector.open = _orig_opener_open
    except Exception:
        pass
    _orig_opener_open = None


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
        if redactions:
            _httpx_set_content(request, payload)
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
        if redactions:
            _httpx_set_content(request, payload)
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


def _observe_socket_connect_ex(self: Any, address: Any) -> Any:
    hostname, port, ipc = _addr_host_port(address)
    if ipc:
        return _orig_socket_connect_ex(self, address)
    decision = _gate_socket_dest(hostname, port)
    if decision == "block":
        raise GateBlockedError(hostname or "")
    return _orig_socket_connect_ex(self, address)


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
    global _orig_socket_connect, _orig_socket_connect_ex, _orig_create_connection, _orig_ssl_connect
    if _orig_socket_connect is not None:
        return
    _orig_socket_connect = socket.socket.connect
    _orig_socket_connect_ex = socket.socket.connect_ex
    _orig_create_connection = socket.create_connection
    ssl_own = None
    try:
        ssl_own = ssl.SSLSocket.connect
        if ssl_own is _orig_socket_connect:
            ssl_own = None
    except Exception:
        ssl_own = None
    socket.socket.connect = _observe_socket_connect  # type: ignore[method-assign]
    socket.socket.connect_ex = _observe_socket_connect_ex  # type: ignore[method-assign]
    socket.create_connection = _observe_create_connection  # type: ignore[assignment]
    if ssl_own is not None:
        _orig_ssl_connect = ssl_own
        ssl.SSLSocket.connect = _observe_ssl_connect  # type: ignore[method-assign]
    else:
        _orig_ssl_connect = None


def _uninstall_socket() -> None:
    global _orig_socket_connect, _orig_socket_connect_ex, _orig_create_connection, _orig_ssl_connect
    try:
        if _orig_socket_connect is not None:
            socket.socket.connect = _orig_socket_connect
        if _orig_socket_connect_ex is not None:
            socket.socket.connect_ex = _orig_socket_connect_ex
        if _orig_create_connection is not None:
            socket.create_connection = _orig_create_connection
        if _orig_ssl_connect is not None:
            ssl.SSLSocket.connect = _orig_ssl_connect
    except Exception:
        pass
    _orig_socket_connect = None
    _orig_socket_connect_ex = None
    _orig_create_connection = None
    _orig_ssl_connect = None


def _http_conn_host_port(conn: Any) -> tuple[str, Optional[str]]:
    host = str(getattr(conn, "host", "") or "")
    port = getattr(conn, "port", None)
    return host, (str(port) if port is not None else None)


def _observe_http_client_request(
    self: Any,
    method: Any,
    url: Any,
    body: Any = None,
    headers: Any = None,
    encode_chunked: bool = False,
) -> Any:
    if _http_owns():
        return _orig_http_request(self, method, url, body, headers or {}, encode_chunked=encode_chunked)
    hostname, port = _http_conn_host_port(self)
    path = str(url or "/").split("?")[0] or "/"
    kind, payload, redactions, record_send = _dispatch_gate(
        hostname, port, path, body, "python_http_client"
    )
    if kind == "pass":
        return _http_orig(
            _orig_http_request, self, method, url, body, headers or {}, encode_chunked=encode_chunked
        )
    if kind == "block":
        raise GateBlockedError(hostname or "")
    send_body = payload if redactions else body
    t0 = time.time()
    method_s = str(method or "GET").upper()
    try:
        resp = _http_orig(
            _orig_http_request, self, method, url, send_body, headers or {}, encode_chunked=encode_chunked
        )
        if record_send:
            action = "REDACTED" if redactions else ("ALLOWED" if _cloud_sync else "OBSERVED")
            _record(hostname, action, "python_http_client", method=method_s, path=path, ok=True,
                    duration_ms=int((time.time() - t0) * 1000))
        return resp
    except Exception as exc:
        if isinstance(exc, GateBlockedError):
            raise
        _record(
            hostname, "OBSERVED", "python_http_client", method=method_s, path=path, ok=False,
            duration_ms=int((time.time() - t0) * 1000), error="network_error",
            error_class=type(exc).__name__,
        )
        raise


def _observe_http_client_putrequest(
    self: Any,
    method: Any,
    url: Any,
    skip_host: bool = False,
    skip_accept_encoding: bool = False,
) -> Any:
    if _http_owns():
        return _orig_http_putrequest(self, method, url, skip_host, skip_accept_encoding)
    hostname, port = _http_conn_host_port(self)
    path = str(url or "/").split("?")[0] or "/"
    kind, _payload, _redactions, record_send = _dispatch_gate(
        hostname, port, path, None, "python_http_client"
    )
    if kind == "block":
        raise GateBlockedError(hostname or "")
    if kind != "pass" and record_send:
        action = "ALLOWED" if _cloud_sync else "OBSERVED"
        _record(hostname, action, "python_http_client", method=str(method or "GET").upper(), path=path)
    return _http_orig(_orig_http_putrequest, self, method, url, skip_host, skip_accept_encoding)


def _install_http_client() -> None:
    global _orig_http_request, _orig_http_putrequest
    if _orig_http_request is not None:
        return
    _orig_http_request = http.client.HTTPConnection.request
    _orig_http_putrequest = http.client.HTTPConnection.putrequest
    http.client.HTTPConnection.request = _observe_http_client_request  # type: ignore[assignment]
    http.client.HTTPConnection.putrequest = _observe_http_client_putrequest  # type: ignore[assignment]


def _uninstall_http_client() -> None:
    global _orig_http_request, _orig_http_putrequest
    try:
        if _orig_http_request is not None:
            http.client.HTTPConnection.request = _orig_http_request
        if _orig_http_putrequest is not None:
            http.client.HTTPConnection.putrequest = _orig_http_putrequest
    except Exception:
        pass
    _orig_http_request = None
    _orig_http_putrequest = None


def _observe_urllib3_urlopen(self: Any, method: Any, url: Any, body: Any = None, headers: Any = None, **kwargs: Any) -> Any:
    if _http_owns():
        return _orig_urllib3_request(self, method, url, body=body, headers=headers, **kwargs)
    hostname, port = _http_conn_host_port(self)
    path = str(url or "/").split("?")[0] or "/"
    kind, payload, redactions, record_send = _dispatch_gate(
        hostname, port, path, body, "python_urllib3"
    )
    if kind == "pass":
        return _http_orig(_orig_urllib3_request, self, method, url, body=body, headers=headers, **kwargs)
    if kind == "block":
        raise GateBlockedError(hostname or "")
    send_body = payload if redactions else body
    t0 = time.time()
    method_s = str(method or "GET").upper()
    try:
        resp = _http_orig(
            _orig_urllib3_request, self, method, url, body=send_body, headers=headers, **kwargs
        )
        if record_send:
            action = "REDACTED" if redactions else ("ALLOWED" if _cloud_sync else "OBSERVED")
            status = getattr(resp, "status", None)
            _record(
                hostname, action, "python_urllib3", method=method_s, path=path, ok=True,
                status=status, duration_ms=int((time.time() - t0) * 1000),
            )
        return resp
    except Exception as exc:
        if isinstance(exc, GateBlockedError):
            raise
        _record(
            hostname, "OBSERVED", "python_urllib3", method=method_s, path=path, ok=False,
            duration_ms=int((time.time() - t0) * 1000), error="network_error",
            error_class=type(exc).__name__,
        )
        raise


def _install_urllib3() -> None:
    global _orig_urllib3_request
    if _urllib3 is None or _orig_urllib3_request is not None:
        return
    pool_mod = getattr(_urllib3, "connectionpool", None)
    if pool_mod is None:
        try:
            from urllib3 import connectionpool as pool_mod
        except ImportError:
            return
    pool_cls = getattr(pool_mod, "HTTPConnectionPool", None) if pool_mod is not None else None
    if pool_cls is None:
        return
    current = getattr(pool_cls, "urlopen", None)
    if current is None or current is _observe_urllib3_urlopen:
        return
    _orig_urllib3_request = current
    pool_cls.urlopen = _observe_urllib3_urlopen  # type: ignore[assignment]


def _uninstall_urllib3() -> None:
    global _orig_urllib3_request
    try:
        if _orig_urllib3_request is not None and _urllib3 is not None:
            pool_mod = getattr(_urllib3, "connectionpool", None)
            pool_cls = getattr(pool_mod, "HTTPConnectionPool", None) if pool_mod is not None else None
            if pool_cls is not None:
                pool_cls.urlopen = _orig_urllib3_request
    except Exception:
        pass
    _orig_urllib3_request = None


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


def _strip_spawn_prefixes(tokens: list[str]) -> list[str]:
    i = 0
    n = len(tokens)
    while i < n:
        base = _cmd_base(tokens[i])
        if base not in ("env", "timeout", "nice"):
            return tokens[i:]
        i += 1
        if base == "env":
            while i < n:
                t = tokens[i]
                if t.startswith("-"):
                    if t in ("-u", "--unset") and i + 1 < n:
                        i += 2
                    else:
                        i += 1
                    continue
                if "=" in t:
                    i += 1
                    continue
                break
            continue
        if base == "timeout":
            while i < n and tokens[i].startswith("-"):
                if tokens[i] in ("-s", "--signal", "-k", "--kill-after") and i + 1 < n:
                    i += 2
                else:
                    i += 1
            if i < n:
                i += 1
            continue
        if base == "nice":
            if i < n and tokens[i] in ("-n", "--adjustment") and i + 1 < n:
                i += 2
            elif i < n and tokens[i].startswith("-") and tokens[i][1:].lstrip("-").isdigit():
                i += 1
            continue
    return tokens[i:] if i < n else []


def _canonical_cli_tool(base: str) -> Optional[str]:
    if base == "curl":
        return "curl"
    if base == "wget":
        return "wget"
    if base in ("http", "https", "httpie"):
        return "httpie"
    if base in ("aria2c", "aria2"):
        return "aria2c"
    return None


def _cli_from_tokens(tokens: list[str]) -> Optional[tuple[str, list[str]]]:
    stripped = _strip_spawn_prefixes([str(t) for t in tokens])
    if not stripped:
        return None
    direct = _canonical_cli_tool(_cmd_base(stripped[0]))
    if direct:
        return direct, stripped[1:]
    if _cmd_base(stripped[0]) not in ("sh", "bash", "dash", "zsh"):
        return None
    args = stripped[1:]
    try:
        c_idx = args.index("-c")
    except ValueError:
        return None
    if c_idx + 1 >= len(args):
        return None
    inner = _strip_spawn_prefixes(_tokenize_shell(args[c_idx + 1]))
    if not inner:
        return None
    tool = _canonical_cli_tool(_cmd_base(inner[0]))
    if not tool:
        return None
    return tool, inner[1:]


def _http_cli_from_spawn(command: Any, argv: Any) -> Optional[tuple[str, list[str]]]:
    args = [str(a) for a in list(argv or [])]
    return _cli_from_tokens([str(command)] + args)


def _http_cli_from_exec(command: Any) -> Optional[tuple[str, list[str]]]:
    tokens = _tokenize_shell(str(command or ""))
    if not tokens:
        return None
    return _cli_from_tokens(tokens)


def _http_cli_from_popen(args: Any, kwargs: dict[str, Any]) -> Optional[tuple[str, list[str]]]:
    shell = bool(kwargs.get("shell"))
    if isinstance(args, bytes):
        args = args.decode("utf-8", "replace")
    if isinstance(args, str):
        if shell:
            return _http_cli_from_exec(args)
        return _cli_from_tokens([args])
    try:
        seq = list(args)
    except TypeError:
        return None
    if not seq:
        return None
    if shell:
        return _http_cli_from_exec(" ".join(str(x) for x in seq))
    return _cli_from_tokens([str(x) for x in seq])


def _stdin_byte_length(kwargs: Optional[dict[str, Any]]) -> int:
    kwargs = kwargs or {}
    data = kwargs.get("input")
    if data is not None:
        try:
            if isinstance(data, bytes):
                return len(data)
            if isinstance(data, str):
                enc = str(kwargs.get("encoding") or "utf-8")
                return len(data.encode(enc, "replace"))
        except Exception:
            return 0
    stdin = kwargs.get("stdin", None)
    fd: Optional[int] = None
    if stdin is None:
        try:
            fd = sys.stdin.fileno()
        except Exception:
            return 0
    elif stdin in (subprocess.PIPE, subprocess.DEVNULL):
        return 0
    elif isinstance(stdin, int):
        fd = stdin
    else:
        try:
            fd = stdin.fileno()
        except Exception:
            return 0
    try:
        st = os.fstat(fd)
        if stat.S_ISREG(st.st_mode):
            return int(st.st_size) or 0
    except Exception:
        return 0
    return 0


def _file_byte_length(rel: Any, stdin_size: int = 0) -> int:
    p = str(rel or "")
    if not p:
        return 0
    if p == "-":
        return int(stdin_size) or 0
    try:
        if os.path.isfile(p):
            return int(os.stat(p).st_size) or 0
    except Exception:
        return 0
    return 0


def _bytes_from_at_or_literal(value: Any, at_means_file: bool, stdin_size: int = 0) -> int:
    v = str(value if value is not None else "")
    if at_means_file and v.startswith("@"):
        return _file_byte_length(v[1:], stdin_size)
    return len(v.encode("utf-8"))


def _bytes_from_curl_form_value(value: Any, treat_at_as_file: bool, stdin_size: int = 0) -> int:
    v = str(value if value is not None else "")
    eq = v.find("=")
    rhs = v[eq + 1:] if eq >= 0 else v
    if not treat_at_as_file:
        return len(rhs.encode("utf-8"))
    if rhs.startswith("@") or rhs.startswith("<"):
        path = rhs[1:]
        semi = path.find(";")
        if semi >= 0:
            path = path[:semi]
        return _file_byte_length(path, stdin_size)
    return len(rhs.encode("utf-8"))


def _urls_from_list_file(path: str, stdin_size: int = 0, kwargs: Optional[dict[str, Any]] = None) -> list[str]:
    cap = 65536
    max_urls = 32
    text = ""
    kwargs = kwargs or {}
    try:
        if str(path or "") == "-":
            data = kwargs.get("input")
            if data is not None:
                if isinstance(data, bytes):
                    text = data[:cap].decode("utf-8", "replace")
                else:
                    text = str(data)[:cap]
            else:
                if not stdin_size:
                    return []
                stdin = kwargs.get("stdin", None)
                fd = 0
                if isinstance(stdin, int):
                    fd = stdin
                elif stdin is not None and stdin not in (subprocess.PIPE, subprocess.DEVNULL):
                    fd = stdin.fileno()
                elif stdin is None:
                    fd = sys.stdin.fileno()
                raw = os.pread(fd, min(int(stdin_size) or 0, cap), 0)
                text = raw.decode("utf-8", "replace")
        else:
            fd = os.open(str(path), os.O_RDONLY)
            try:
                raw = os.read(fd, cap)
                text = raw.decode("utf-8", "replace")
            finally:
                os.close(fd)
    except Exception:
        return []
    urls: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        token = s.split()[0]
        if token.startswith("http://") or token.startswith("https://"):
            urls.append(token)
        if len(urls) >= max_urls:
            break
    return urls


_CURL_DATA_AT_FILE = {
    "-d": True,
    "--data": True,
    "--data-binary": True,
    "--data-ascii": True,
    "--data-urlencode": True,
    "--json": True,
    "--data-raw": False,
}


def _url_from_curl_config(path: str) -> Optional[str]:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                lower = s.lower()
                if not lower.startswith("url"):
                    continue
                rest = s[3:].lstrip()
                if rest.startswith("="):
                    rest = rest[1:].strip()
                rest = rest.strip("\"'")
                if rest.startswith("http://") or rest.startswith("https://"):
                    return rest
    except Exception:
        return None
    return None


def _parse_curl_argv(argv: list[str], stdin_size: int = 0) -> tuple[list[str], int]:
    url: Optional[str] = None
    data_bytes = 0
    config_paths: list[str] = []
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
        if a in ("-K", "--config"):
            if i + 1 < len(args):
                config_paths.append(args[i + 1])
            i += 2
            continue
        if a.startswith("--config="):
            config_paths.append(a[len("--config="):])
            i += 1
            continue
        if a in _CURL_DATA_AT_FILE:
            value = args[i + 1] if i + 1 < len(args) else ""
            data_bytes += _bytes_from_at_or_literal(value, _CURL_DATA_AT_FILE[a], stdin_size)
            i += 2
            continue
        eq_handled = False
        for flag, at_file in _CURL_DATA_AT_FILE.items():
            if flag.startswith("--") and a.startswith(flag + "="):
                data_bytes += _bytes_from_at_or_literal(a[len(flag) + 1:], at_file, stdin_size)
                eq_handled = True
                break
        if eq_handled:
            i += 1
            continue
        if a.startswith("-d") and len(a) > 2 and not a.startswith("--"):
            data_bytes += _bytes_from_at_or_literal(a[2:], True, stdin_size)
            i += 1
            continue
        if a in ("-F", "--form"):
            data_bytes += _bytes_from_curl_form_value(args[i + 1] if i + 1 < len(args) else "", True, stdin_size)
            i += 2
            continue
        if a.startswith("--form="):
            data_bytes += _bytes_from_curl_form_value(a[len("--form="):], True, stdin_size)
            i += 1
            continue
        if a.startswith("-F") and len(a) > 2 and not a.startswith("--"):
            data_bytes += _bytes_from_curl_form_value(a[2:], True, stdin_size)
            i += 1
            continue
        if a == "--form-string":
            data_bytes += _bytes_from_curl_form_value(args[i + 1] if i + 1 < len(args) else "", False, stdin_size)
            i += 2
            continue
        if a.startswith("--form-string="):
            data_bytes += _bytes_from_curl_form_value(a[len("--form-string="):], False, stdin_size)
            i += 1
            continue
        if a in ("-T", "--upload-file"):
            data_bytes += _file_byte_length(args[i + 1] if i + 1 < len(args) else "", stdin_size)
            i += 2
            continue
        if a.startswith("--upload-file="):
            data_bytes += _file_byte_length(a[len("--upload-file="):], stdin_size)
            i += 1
            continue
        if a.startswith("-T") and len(a) > 2 and not a.startswith("--"):
            data_bytes += _file_byte_length(a[2:], stdin_size)
            i += 1
            continue
        if url is None and (a.startswith("http://") or a.startswith("https://")):
            url = a
        i += 1
    if url is None:
        for path in config_paths:
            found = _url_from_curl_config(path)
            if found:
                url = found
                break
    return ([url] if url else []), data_bytes


def _take_input_file_arg(args: list[str], i: int, a: str) -> Optional[tuple[str, int]]:
    if a in ("-i", "--input-file"):
        return (args[i + 1] if i + 1 < len(args) else ""), i + 2
    if a.startswith("--input-file="):
        return a[len("--input-file="):], i + 1
    return None


def _parse_wget_argv(argv: list[str], stdin_size: int = 0, kwargs: Optional[dict[str, Any]] = None) -> tuple[list[str], int]:
    url: Optional[str] = None
    data_bytes = 0
    list_paths: list[str] = []
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
        if a in ("--post-file", "--body-file"):
            data_bytes += _file_byte_length(args[i + 1] if i + 1 < len(args) else "", stdin_size)
            i += 2
            continue
        if a.startswith("--post-file="):
            data_bytes += _file_byte_length(a[len("--post-file="):], stdin_size)
            i += 1
            continue
        if a.startswith("--body-file="):
            data_bytes += _file_byte_length(a[len("--body-file="):], stdin_size)
            i += 1
            continue
        taken = _take_input_file_arg(args, i, a)
        if taken is not None:
            path, nxt = taken
            if path:
                list_paths.append(path)
            i = nxt
            continue
        if url is None and (a.startswith("http://") or a.startswith("https://")):
            url = a
        i += 1
    urls: list[str] = []
    if url:
        urls.append(url)
    for path in list_paths:
        for found in _urls_from_list_file(path, stdin_size, kwargs):
            if found not in urls:
                urls.append(found)
    return urls, data_bytes


def _parse_url_only_argv(argv: list[str], stdin_size: int = 0, kwargs: Optional[dict[str, Any]] = None) -> tuple[list[str], int]:
    urls: list[str] = []
    list_paths: list[str] = []
    args = [str(a) for a in argv]
    i = 0
    while i < len(args):
        a = args[i]
        taken = _take_input_file_arg(args, i, a)
        if taken is not None:
            path, nxt = taken
            if path:
                list_paths.append(path)
            i = nxt
            continue
        if (a.startswith("http://") or a.startswith("https://")) and a not in urls:
            urls.append(a)
        i += 1
    for path in list_paths:
        for found in _urls_from_list_file(path, stdin_size, kwargs):
            if found not in urls:
                urls.append(found)
    return urls, 0


def _parse_cli_argv(tool: str, argv: list[str], kwargs: Optional[dict[str, Any]] = None) -> tuple[list[str], int]:
    stdin_size = _stdin_byte_length(kwargs)
    if tool == "wget":
        return _parse_wget_argv(argv, stdin_size, kwargs)
    if tool in ("httpie", "aria2c"):
        return _parse_url_only_argv(argv, stdin_size, kwargs)
    return _parse_curl_argv(argv, stdin_size)


def _cli_mediation(tool: str) -> str:
    if tool == "wget":
        return "python_wget"
    if tool == "httpie":
        return "python_httpie"
    if tool == "aria2c":
        return "python_aria2c"
    return "python_curl"


def _rewrite_httpie_item(token: str, take_redact: Any) -> str:
    at = token.find("@")
    if at > 0 and "=" not in token and ":" not in token:
        return token
    for sep in (":=", "==", "="):
        idx = token.find(sep)
        if idx <= 0:
            continue
        rhs = token[idx + len(sep):]
        if rhs.startswith("@") or rhs.startswith("<"):
            return token
        return token[: idx + len(sep)] + take_redact(rhs)
    return token


def _rewrite_curl_form_value(value: str, treat_at_as_file: bool, take_redact: Any) -> str:
    eq = value.find("=")
    rhs = value[eq + 1:] if eq >= 0 else value
    if treat_at_as_file and (rhs.startswith("@") or rhs.startswith("<")):
        return value
    nxt = take_redact(rhs)
    if nxt == rhs:
        return value
    return (value[: eq + 1] + nxt) if eq >= 0 else nxt


def _rewrite_inline_cli_bodies(tool: str, argv: list[str]) -> tuple[list[str], list[str]]:
    out = [str(a) for a in argv]
    redactions: list[str] = []

    def take_redact(v: str) -> str:
        text, found = _redact_text(str(v))
        if found:
            redactions.extend(found)
            return text
        return v

    if tool == "aria2c":
        return out, redactions
    if tool == "httpie":
        i = 0
        while i < len(out):
            a = out[i]
            if a == "--raw" and i + 1 < len(out):
                out[i + 1] = take_redact(out[i + 1])
                i += 2
                continue
            if a.startswith("--raw="):
                out[i] = "--raw=" + take_redact(a[len("--raw="):])
                i += 1
                continue
            if a.startswith("-") and a != "-":
                i += 1
                continue
            if a.startswith("http://") or a.startswith("https://"):
                i += 1
                continue
            out[i] = _rewrite_httpie_item(a, take_redact)
            i += 1
        return out, redactions
    if tool == "wget":
        i = 0
        while i < len(out):
            a = out[i]
            if a in ("--post-data", "--body-data"):
                if i + 1 < len(out):
                    out[i + 1] = take_redact(out[i + 1])
                i += 2
                continue
            if a.startswith("--post-data="):
                out[i] = "--post-data=" + take_redact(a[len("--post-data="):])
                i += 1
                continue
            if a.startswith("--body-data="):
                out[i] = "--body-data=" + take_redact(a[len("--body-data="):])
                i += 1
                continue
            i += 1
        return out, redactions
    i = 0
    while i < len(out):
        a = out[i]
        if a in _CURL_DATA_AT_FILE:
            value = out[i + 1] if i + 1 < len(out) else ""
            if not (_CURL_DATA_AT_FILE[a] and str(value).startswith("@")):
                if i + 1 < len(out):
                    out[i + 1] = take_redact(value)
            i += 2
            continue
        eq_handled = False
        for flag, at_file in _CURL_DATA_AT_FILE.items():
            if flag.startswith("--") and a.startswith(flag + "="):
                value = a[len(flag) + 1:]
                if not (at_file and value.startswith("@")):
                    out[i] = flag + "=" + take_redact(value)
                eq_handled = True
                break
        if eq_handled:
            i += 1
            continue
        if a.startswith("-d") and len(a) > 2 and not a.startswith("--"):
            value = a[2:]
            if not value.startswith("@"):
                out[i] = "-d" + take_redact(value)
            i += 1
            continue
        if a in ("-F", "--form"):
            if i + 1 < len(out):
                out[i + 1] = _rewrite_curl_form_value(out[i + 1], True, take_redact)
            i += 2
            continue
        if a.startswith("--form="):
            out[i] = "--form=" + _rewrite_curl_form_value(a[len("--form="):], True, take_redact)
            i += 1
            continue
        if a.startswith("-F") and len(a) > 2 and not a.startswith("--"):
            out[i] = "-F" + _rewrite_curl_form_value(a[2:], True, take_redact)
            i += 1
            continue
        if a == "--form-string":
            if i + 1 < len(out):
                out[i + 1] = _rewrite_curl_form_value(out[i + 1], False, take_redact)
            i += 2
            continue
        if a.startswith("--form-string="):
            out[i] = "--form-string=" + _rewrite_curl_form_value(
                a[len("--form-string="):], False, take_redact
            )
            i += 1
            continue
        i += 1
    return out, redactions


def _splice_cli_tokens(tokens: list[str], rewritten_argv: list[str]) -> list[str]:
    stripped = _strip_spawn_prefixes(tokens)
    prefix = tokens[: len(tokens) - len(stripped)] if stripped else tokens[:]
    if not stripped:
        return tokens
    base = _cmd_base(stripped[0])
    if base in ("sh", "bash", "dash", "zsh"):
        rest = stripped[1:]
        try:
            c_idx = rest.index("-c")
        except ValueError:
            c_idx = -1
        if c_idx >= 0 and c_idx + 1 < len(rest):
            inner_tokens = _tokenize_shell(rest[c_idx + 1])
            inner_stripped = _strip_spawn_prefixes(inner_tokens)
            inner_prefix = (
                inner_tokens[: len(inner_tokens) - len(inner_stripped)] if inner_stripped else []
            )
            new_inner = (
                inner_prefix + [inner_stripped[0]] + rewritten_argv
                if inner_stripped
                else inner_tokens
            )
            new_stripped = list(stripped)
            new_stripped[c_idx + 2] = " ".join(shlex.quote(t) for t in new_inner)
            return prefix + new_stripped
    return prefix + [stripped[0]] + rewritten_argv


def _rewrite_popen_args(args: Any, kwargs: dict[str, Any], rewritten_argv: list[str]) -> Any:
    shell = bool(kwargs.get("shell"))
    if isinstance(args, bytes):
        args = args.decode("utf-8", "replace")
    if isinstance(args, str):
        tokens = _tokenize_shell(args)
        return " ".join(shlex.quote(t) for t in _splice_cli_tokens(tokens, rewritten_argv))
    try:
        seq = [str(x) for x in list(args)]
    except TypeError:
        return args
    if not seq:
        return args
    if shell:
        tokens = _tokenize_shell(" ".join(seq))
        return " ".join(shlex.quote(t) for t in _splice_cli_tokens(tokens, rewritten_argv))
    return _splice_cli_tokens(seq, rewritten_argv)


def _apply_cli_gate(
    tool: str, argv: list[str], kwargs: Optional[dict[str, Any]] = None
) -> tuple[Optional[GateBlockedError], Optional[list[str]]]:
    global _spent_usd
    urls, data_bytes = _parse_cli_argv(tool, argv, kwargs)
    if not urls:
        return None, None
    rows: list[tuple[Optional[str], Optional[str], str, str]] = []
    for url in urls:
        hostname, port, path = _host_port_from_url(url)
        decision = _decide(hostname, port, path, data_bytes)
        rows.append((hostname, path, decision, url))
    hard = [r for r in rows if r[2] in ("block", "block_size", "block_spend")]
    in_scope = [r for r in rows if r[2] != "pass"]
    to_record = hard if hard else in_scope
    mediation = _cli_mediation(tool)
    err: Optional[GateBlockedError] = None
    for hostname, path, decision, _url in to_record:
        extra = {"path": path, "bytes_observed": data_bytes}
        if decision == "block":
            _record(hostname, "BLOCKED_HOST", mediation, ok=False, **extra)
            if err is None:
                err = GateBlockedError(hostname or "")
        elif decision == "block_size":
            _record(hostname, "BLOCKED_SIZE", mediation, ok=False, **extra)
            if err is None:
                err = GateBlockedError(hostname or "")
        elif decision == "block_spend":
            _record(hostname, "BLOCKED_SPEND", mediation, ok=False, **extra)
            if err is None:
                err = GateBlockedError(hostname or "")
    if err is not None:
        return err, None
    new_argv = argv
    redactions: list[str] = []
    if _policy.get("redact_pii") and in_scope:
        new_argv, redactions = _rewrite_inline_cli_bodies(tool, argv)
    for hostname, path, decision, _url in to_record:
        extra = {"path": path, "bytes_observed": data_bytes}
        if decision == "dry_block":
            _record(hostname, "DRY_RUN_BLOCKED_HOST", mediation, **extra)
        elif decision == "dry_size":
            _record(hostname, "DRY_RUN_BLOCKED_SIZE", mediation, **extra)
        elif decision == "dry_spend":
            _record(hostname, "DRY_RUN_BLOCKED_SPEND", mediation, **extra)
        elif decision not in ("block", "block_size", "block_spend"):
            action = "REDACTED" if redactions else ("ALLOWED" if _cloud_sync else "OBSERVED")
            _record(hostname, action, mediation, **extra)
            _spent_usd += (data_bytes or 0) * _USD_PER_BYTE
    return None, (new_argv if redactions else None)


class _VantioPopen(subprocess.Popen):
    def __init__(self, args: Any, *pargs: Any, **kwargs: Any) -> None:
        try:
            cli = _http_cli_from_popen(args, kwargs)
            if cli is not None:
                err, new_argv = _apply_cli_gate(cli[0], cli[1], kwargs)
                if err is not None:
                    raise err
                if new_argv is not None:
                    args = _rewrite_popen_args(args, kwargs, new_argv)
        except GateBlockedError:
            raise
        except Exception:
            pass
        super().__init__(args, *pargs, **kwargs)


def _observe_os_system(command: Any) -> Any:
    try:
        cli = _http_cli_from_exec(command)
        if cli is not None:
            err, new_argv = _apply_cli_gate(cli[0], cli[1])
            if err is not None:
                raise err
            if new_argv is not None:
                command = _rewrite_popen_args(command, {"shell": True}, new_argv)
    except GateBlockedError:
        raise
    except Exception:
        pass
    return _orig_os_system(command)


async def _observe_asyncio_exec(program: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        cli = _http_cli_from_spawn(program, args)
        if cli is not None:
            err, new_argv = _apply_cli_gate(cli[0], cli[1], kwargs)
            if err is not None:
                raise err
            if new_argv is not None:
                tokens = _rewrite_popen_args([program, *args], kwargs, new_argv)
                if isinstance(tokens, list) and tokens:
                    program = tokens[0]
                    args = tuple(tokens[1:])
    except GateBlockedError:
        raise
    except Exception:
        pass
    return await _orig_asyncio_exec(program, *args, **kwargs)


async def _observe_asyncio_shell(cmd: Any, **kwargs: Any) -> Any:
    try:
        cli = _http_cli_from_exec(cmd)
        if cli is not None:
            err, new_argv = _apply_cli_gate(cli[0], cli[1], kwargs)
            if err is not None:
                raise err
            if new_argv is not None:
                cmd = _rewrite_popen_args(cmd, {**kwargs, "shell": True}, new_argv)
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


def _pycurl_decode(value: Any) -> str:
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", "replace")
    return str(value or "")


class _VantioCurl:
    """Python proxy around pycurl.Curl — C type methods are immutable."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        object.__setattr__(self, "_curl", _orig_pycurl_curl(*args, **kwargs))
        object.__setattr__(self, "_vantio_url", None)
        object.__setattr__(self, "_vantio_body", None)

    def setopt(self, option: Any, value: Any) -> Any:
        try:
            if _pycurl is not None and option == _pycurl.URL:
                object.__setattr__(self, "_vantio_url", _pycurl_decode(value))
            elif _pycurl is not None and option == _pycurl.POSTFIELDS:
                object.__setattr__(self, "_vantio_body", value)
        except Exception:
            pass
        return self._curl.setopt(option, value)

    def perform(self, *args: Any, **kwargs: Any) -> Any:
        url = self._vantio_url or ""
        body = self._vantio_body
        hostname, port, path = _host_port_from_url(url)
        kind, payload, redactions, record_send = _dispatch_gate(
            hostname, port, path, body, "python_pycurl"
        )
        if kind == "pass":
            return self._curl.perform(*args, **kwargs)
        if kind == "block":
            raise GateBlockedError(hostname or "")
        if redactions:
            self._curl.setopt(_pycurl.POSTFIELDS, payload)
            object.__setattr__(self, "_vantio_body", payload)
        t0 = time.time()
        try:
            result = self._curl.perform(*args, **kwargs)
            if record_send:
                action = "REDACTED" if redactions else ("ALLOWED" if _cloud_sync else "OBSERVED")
                _record(
                    hostname,
                    action,
                    "python_pycurl",
                    path=path,
                    ok=True,
                    duration_ms=int((time.time() - t0) * 1000),
                )
            return result
        except Exception as exc:
            if isinstance(exc, GateBlockedError):
                raise
            _record(
                hostname,
                "OBSERVED",
                "python_pycurl",
                path=path,
                ok=False,
                duration_ms=int((time.time() - t0) * 1000),
                error="network_error",
                error_class=type(exc).__name__,
            )
            raise

    def __getattr__(self, name: str) -> Any:
        return getattr(self._curl, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ("_curl", "_vantio_url", "_vantio_body"):
            object.__setattr__(self, name, value)
        else:
            setattr(self._curl, name, value)


def _install_pycurl() -> None:
    global _orig_pycurl_curl
    if _pycurl is None or _orig_pycurl_curl is not None:
        return
    current = getattr(_pycurl, "Curl", None)
    if current is None or current is _VantioCurl:
        return
    _orig_pycurl_curl = current
    _pycurl.Curl = _VantioCurl  # type: ignore[misc,assignment]


def _uninstall_pycurl() -> None:
    global _orig_pycurl_curl
    try:
        if _orig_pycurl_curl is not None and _pycurl is not None:
            _pycurl.Curl = _orig_pycurl_curl
    except Exception:
        pass
    _orig_pycurl_curl = None


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
                "note": "Python wrap observes urllib (urlopen and custom openers), requests/httpx/aiohttp/urllib3/pycurl when installed, http.client, socket.connect / connect_ex / create_connection, and subprocess curl/wget/httpie/aria2c to in-scope LLM hosts. File-body size is counted from stat; contents are not read. Inline argv bodies are rewritten for Gate PII. With a Gate key it can also block, redact PII, or enforce a spend limit on HTTP bodies. Browsers stay outside this wrap.",
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
            _install_opener()
            _install_requests()
            _install_httpx()
            _install_aiohttp()
            _install_socket()
            _install_http_client()
            _install_urllib3()
            _install_pycurl()
            _install_curl_spawn()


def uninstall() -> None:
    global _depth
    with _lock:
        if _depth <= 0:
            return
        _depth -= 1
        if _depth == 0:
            urllib.request.urlopen = _orig_urlopen  # type: ignore[assignment]
            _uninstall_opener()
            _uninstall_requests()
            _uninstall_httpx()
            _uninstall_aiohttp()
            _uninstall_socket()
            _uninstall_urllib3()
            _uninstall_pycurl()
            _uninstall_http_client()
            _uninstall_curl_spawn()
            _write_run_log()
            _reset_policy()
