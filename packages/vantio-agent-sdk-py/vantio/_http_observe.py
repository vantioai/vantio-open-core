"""
Sight Loop observe for Python HTTP clients while shield() is active.

Records host, path, status, and size — never prompts or completions.
In-scope LLM hosts (plus VANTIO_EXTRA_LLM_HOSTS), including regional Bedrock
and Vertex patterns and local Ollama on port 11434.

Wraps urllib.request.urlopen always. If requests or httpx are installed,
wraps those too so agents that skip urllib are still observed. Raw sockets
and curl stay outside this wrap.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse

try:
    import requests as _requests
except ImportError:
    _requests = None  # type: ignore[assignment]

try:
    import httpx as _httpx
except ImportError:
    _httpx = None  # type: ignore[assignment]

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
_calls: list[dict[str, Any]] = []
_started_ms = 0.0
_trace_id = ""


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
    )


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


def _observe_urlopen(url, data=None, timeout=None, *args, **kwargs):
    hostname, port, path = _host_port_from_url(url)
    try:
        raw = url
        if hasattr(url, "full_url"):
            raw = url.full_url
        scheme = "https" if str(raw).startswith("https") else "http"
    except Exception:
        scheme = "https"

    if not hostname or not _in_scope(hostname, port):
        return _orig_urlopen(url, data, timeout, *args, **kwargs)

    t0 = time.time()
    try:
        resp = _orig_urlopen(url, data, timeout, *args, **kwargs)
        status = getattr(resp, "status", None) or getattr(resp, "code", None)
        _append({
            "hostname": hostname,
            "provider": "other",
            "method": "POST" if data is not None else "GET",
            "path": path,
            "scheme": scheme,
            "request_bytes": len(data) if isinstance(data, (bytes, bytearray)) else None,
            "bytes": None,
            "status": status,
            "ok": True,
            "content_type": None,
            "duration_ms": int((time.time() - t0) * 1000),
            "action": "OBSERVED",
            "mediation": "python_urllib",
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        return resp
    except Exception as exc:
        _append({
            "hostname": hostname,
            "provider": "other",
            "method": "POST" if data is not None else "GET",
            "path": path,
            "scheme": scheme,
            "request_bytes": None,
            "bytes": None,
            "status": getattr(exc, "code", None),
            "ok": False,
            "content_type": None,
            "duration_ms": int((time.time() - t0) * 1000),
            "action": "OBSERVED",
            "mediation": "python_urllib",
            "ts": datetime.now(timezone.utc).isoformat(),
            "error": "network_error",
            "error_class": type(exc).__name__,
        })
        raise


def _install_requests() -> None:
    global _orig_requests_send
    if _requests is None:
        return
    _orig_requests_send = _requests.sessions.Session.send

    def _observe_send(self, request, **kwargs):  # type: ignore[no-untyped-def]
        hostname, port, path = _host_port_from_url(getattr(request, "url", ""))
        if not hostname or not _in_scope(hostname, port):
            return _orig_requests_send(self, request, **kwargs)
        t0 = time.time()
        method = str(getattr(request, "method", "GET") or "GET").upper()
        body = getattr(request, "body", None)
        req_bytes = len(body) if isinstance(body, (bytes, bytearray)) else None
        try:
            resp = _orig_requests_send(self, request, **kwargs)
            _append({
                "hostname": hostname,
                "provider": "other",
                "method": method,
                "path": path,
                "scheme": "https" if str(getattr(request, "url", "")).startswith("https") else "http",
                "request_bytes": req_bytes,
                "bytes": None,
                "status": getattr(resp, "status_code", None),
                "ok": True,
                "content_type": None,
                "duration_ms": int((time.time() - t0) * 1000),
                "action": "OBSERVED",
                "mediation": "python_requests",
                "ts": datetime.now(timezone.utc).isoformat(),
            })
            return resp
        except Exception as exc:
            _append({
                "hostname": hostname,
                "provider": "other",
                "method": method,
                "path": path,
                "scheme": "https" if str(getattr(request, "url", "")).startswith("https") else "http",
                "request_bytes": req_bytes,
                "bytes": None,
                "status": None,
                "ok": False,
                "content_type": None,
                "duration_ms": int((time.time() - t0) * 1000),
                "action": "OBSERVED",
                "mediation": "python_requests",
                "ts": datetime.now(timezone.utc).isoformat(),
                "error": "network_error",
                "error_class": type(exc).__name__,
            })
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
        if not hostname or not _in_scope(hostname, port):
            return _orig_httpx_sync_send(self, request, **kwargs)
        t0 = time.time()
        method = str(getattr(request, "method", "GET") or "GET").upper()
        try:
            resp = _orig_httpx_sync_send(self, request, **kwargs)
            _append({
                "hostname": hostname,
                "provider": "other",
                "method": method,
                "path": path,
                "scheme": "https" if str(request.url).startswith("https") else "http",
                "request_bytes": None,
                "bytes": None,
                "status": getattr(resp, "status_code", None),
                "ok": True,
                "content_type": None,
                "duration_ms": int((time.time() - t0) * 1000),
                "action": "OBSERVED",
                "mediation": "python_httpx",
                "ts": datetime.now(timezone.utc).isoformat(),
            })
            return resp
        except Exception as exc:
            _append({
                "hostname": hostname,
                "provider": "other",
                "method": method,
                "path": path,
                "scheme": "https" if str(getattr(request, "url", "")).startswith("https") else "http",
                "request_bytes": None,
                "bytes": None,
                "status": None,
                "ok": False,
                "content_type": None,
                "duration_ms": int((time.time() - t0) * 1000),
                "action": "OBSERVED",
                "mediation": "python_httpx",
                "ts": datetime.now(timezone.utc).isoformat(),
                "error": "network_error",
                "error_class": type(exc).__name__,
            })
            raise

    async def _observe_async(self, request, **kwargs):  # type: ignore[no-untyped-def]
        hostname, port, path = _host_port_from_url(getattr(request, "url", ""))
        if not hostname or not _in_scope(hostname, port):
            return await _orig_httpx_async_send(self, request, **kwargs)
        t0 = time.time()
        method = str(getattr(request, "method", "GET") or "GET").upper()
        try:
            resp = await _orig_httpx_async_send(self, request, **kwargs)
            _append({
                "hostname": hostname,
                "provider": "other",
                "method": method,
                "path": path,
                "scheme": "https" if str(request.url).startswith("https") else "http",
                "request_bytes": None,
                "bytes": None,
                "status": getattr(resp, "status_code", None),
                "ok": True,
                "content_type": None,
                "duration_ms": int((time.time() - t0) * 1000),
                "action": "OBSERVED",
                "mediation": "python_httpx",
                "ts": datetime.now(timezone.utc).isoformat(),
            })
            return resp
        except Exception as exc:
            _append({
                "hostname": hostname,
                "provider": "other",
                "method": method,
                "path": path,
                "scheme": "https" if str(getattr(request, "url", "")).startswith("https") else "http",
                "request_bytes": None,
                "bytes": None,
                "status": None,
                "ok": False,
                "content_type": None,
                "duration_ms": int((time.time() - t0) * 1000),
                "action": "OBSERVED",
                "mediation": "python_httpx",
                "ts": datetime.now(timezone.utc).isoformat(),
                "error": "network_error",
                "error_class": type(exc).__name__,
            })
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
                "note": "Python shield observes urllib, and requests/httpx when those libraries are installed, to in-scope LLM hosts. Raw sockets and curl stay outside this wrap.",
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
            urllib.request.urlopen = _observe_urlopen  # type: ignore[assignment]
            _install_requests()
            _install_httpx()


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
            _write_run_log()
