"""Observe urllib, one asyncio HTTP client, socket failures, and subprocess size.

Records are appended after the call finishes. A shield that sees nothing
still closes so the writer can store an explicit NOT_OBSERVED envelope.
"""

import asyncio
import shlex
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from contextvars import ContextVar
from pathlib import Path
from urllib.parse import urlsplit

from vantio_future.clock import duration_ms, format_utc, now_utc
from vantio_future.hosts import host_in_scope
from vantio_future.writer import publish_run

_lock = threading.Lock()
_depth = 0
_trace_id = ""
_started_wall = None
_started_mono = None
_events = []
_attempted = 0
_http_owns = ContextVar("vantio_future_http_owns", default=False)

_orig_urlopen = urllib.request.urlopen
_orig_create_connection = socket.create_connection
_orig_run = subprocess.run


def shield_active():
    return _depth > 0


def _remember(raw):
    global _attempted
    with _lock:
        if _depth <= 0:
            return
        _attempted += 1
        _events.append(raw)


def _failure_kind(exc):
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, socket.timeout):
        return "timeout"
    name = type(exc).__name__
    if name == "gaierror":
        return "dns"
    if name in ("SSLError", "SSLEOFError", "SSLCertVerificationError"):
        return "tls"
    if isinstance(exc, ConnectionError):
        return "connection"
    if isinstance(exc, OSError):
        return "network"
    return "wrapped"


def _error_class(exc):
    name = type(exc).__name__
    if name.isidentifier() and len(name) <= 64:
        return name
    return None


def _http_code(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int) and 100 <= value <= 599:
        return value
    return None


def _status_from_exception(exc):
    if isinstance(exc, urllib.error.HTTPError):
        return _http_code(getattr(exc, "code", None))
    return None


def _header_length(headers):
    if headers is None or not hasattr(headers, "get"):
        return None
    raw = headers.get("Content-Length")
    if raw is None:
        return None
    text = str(raw).strip()
    if not text.isdigit():
        return None
    return int(text)


def _view(url, data):
    method = "POST" if data is not None else "GET"
    if isinstance(url, urllib.request.Request):
        full = url.full_url
        method = url.get_method()
    else:
        full = str(url)
    parts = urlsplit(full)
    path = parts.path or "/"
    if parts.query:
        path = path + "?" + parts.query
    return {
        "destination_host": parts.hostname or "",
        "destination_port": parts.port,
        "method": method,
        "path": path,
        "scheme": parts.scheme if parts.scheme in ("http", "https") else "unknown",
    }


def _finished(view, mediation, started_wall, started_mono, **extra):
    raw = {
        "clock_quality": "MONOTONIC",
        "destination_host": view.get("destination_host") or "",
        "duration_ms": duration_ms(started_mono),
        "lifecycle": "COMPLETE",
        "mediation": mediation,
        "optics_status": "OBSERVED",
        "scheme": view.get("scheme") or "unknown",
        "started_at": format_utc(started_wall),
    }
    if view.get("path"):
        raw["path"] = view["path"]
    if view.get("destination_port") is not None:
        raw["destination_port"] = view["destination_port"]
    if view.get("method"):
        raw["method"] = view["method"]
    raw.update(extra)
    _remember(raw)


def _record_http_result(view, status, headers, exc, started_wall, started_mono):
    code = _http_code(status)
    length = _header_length(headers)
    extra = {}
    if code is not None:
        extra["http_status"] = code
    elif exc is not None:
        extra["application_status"] = "UNAVAILABLE"
        extra["error_class"] = _error_class(exc)
        extra["failure_kind"] = _failure_kind(exc)
    if length is not None:
        extra["response_bytes"] = length
    _finished(view, "python_urllib", started_wall, started_mono, **extra)


def _observe_urlopen(url, data=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, *args, **kwargs):
    view = _view(url, data)
    if not shield_active() or not host_in_scope(view["destination_host"]):
        return _orig_urlopen(url, data, timeout, *args, **kwargs)
    token = _http_owns.set(True)
    started_wall = now_utc()
    started_mono = time.perf_counter()
    try:
        try:
            response = _orig_urlopen(url, data, timeout, *args, **kwargs)
        except Exception as exc:
            code = _status_from_exception(exc)
            headers = getattr(exc, "headers", None)
            recorded = exc
            if code is None and not isinstance(exc, urllib.error.HTTPError):
                reason = getattr(exc, "reason", None)
                if isinstance(reason, BaseException):
                    recorded = reason
            _record_http_result(
                view,
                code,
                headers,
                None if code is not None else recorded,
                started_wall,
                started_mono,
            )
            raise
        status = getattr(response, "status", None)
        if _http_code(status) is None:
            getter = getattr(response, "getcode", None)
            if callable(getter):
                status = getter()
        _record_http_result(
            view,
            status,
            getattr(response, "headers", None),
            None,
            started_wall,
            started_mono,
        )
        return response
    finally:
        _http_owns.reset(token)


def _observe_create_connection(address, *args, **kwargs):
    if _http_owns.get() or not shield_active():
        return _orig_create_connection(address, *args, **kwargs)
    host = ""
    port = None
    if isinstance(address, tuple) and address:
        host = str(address[0])
        if len(address) > 1 and isinstance(address[1], int):
            port = address[1]
    if not host_in_scope(host):
        return _orig_create_connection(address, *args, **kwargs)
    started_wall = now_utc()
    started_mono = time.perf_counter()
    try:
        return _orig_create_connection(address, *args, **kwargs)
    except OSError as exc:
        view = {
            "destination_host": host,
            "destination_port": port,
            "method": None,
            "path": None,
            "scheme": "unknown",
        }
        _finished(
            view,
            "python_socket",
            started_wall,
            started_mono,
            application_status="UNAVAILABLE",
            error_class=_error_class(exc),
            failure_kind=_failure_kind(exc),
        )
        raise


def _argv(command):
    if isinstance(command, (list, tuple)):
        return [str(part) for part in command]
    if isinstance(command, str):
        return shlex.split(command)
    return []


def _subprocess_target(argv):
    if not argv:
        return None
    program = Path(argv[0]).name
    if program not in ("curl", "wget", "httpie", "aria2c"):
        return None
    url = ""
    for arg in argv[1:]:
        if arg.startswith("http://") or arg.startswith("https://"):
            url = arg
            break
    if not url:
        return None
    parts = urlsplit(url)
    data_path = None
    inline_size = None
    flags = {"--data-binary", "--data", "--data-raw", "-d"}
    for index, arg in enumerate(argv):
        value = None
        if arg in flags and index + 1 < len(argv):
            value = argv[index + 1]
        elif arg.startswith("--data-binary=") or arg.startswith("--data="):
            value = arg.split("=", 1)[1]
        if value is None:
            continue
        if value.startswith("@"):
            data_path = value[1:]
        else:
            inline_size = len(value.encode("utf-8"))
    request_bytes = None
    if data_path:
        try:
            request_bytes = Path(data_path).stat().st_size
        except OSError:
            request_bytes = None
    elif inline_size is not None:
        request_bytes = inline_size
    path = parts.path or "/"
    if parts.query:
        path = path + "?" + parts.query
    return {
        "destination_host": parts.hostname or "",
        "destination_port": parts.port,
        "method": "POST" if request_bytes is not None else "GET",
        "path": path,
        "request_bytes": request_bytes,
        "scheme": parts.scheme if parts.scheme in ("http", "https") else "unknown",
    }


def _observe_run(*args, **kwargs):
    command = args[0] if args else kwargs.get("args")
    target = _subprocess_target(_argv(command))
    if not shield_active() or target is None or not host_in_scope(target["destination_host"]):
        return _orig_run(*args, **kwargs)
    started_wall = now_utc()
    started_mono = time.perf_counter()
    try:
        result = _orig_run(*args, **kwargs)
    except Exception as exc:
        extra = {
            "application_status": "UNAVAILABLE",
            "error_class": _error_class(exc),
            "failure_kind": "wrapped",
        }
        if target["request_bytes"] is not None:
            extra["request_bytes"] = target["request_bytes"]
        _finished(target, "python_subprocess", started_wall, started_mono, **extra)
        raise
    extra = {"application_status": "UNAVAILABLE"}
    if target["request_bytes"] is not None:
        extra["request_bytes"] = target["request_bytes"]
    _finished(target, "python_subprocess", started_wall, started_mono, **extra)
    return result


def _install_hooks():
    urllib.request.urlopen = _observe_urlopen
    socket.create_connection = _observe_create_connection
    subprocess.run = _observe_run


def _restore_hooks():
    urllib.request.urlopen = _orig_urlopen
    socket.create_connection = _orig_create_connection
    subprocess.run = _orig_run


def install(trace_id):
    global _attempted, _depth, _started_mono, _started_wall, _trace_id
    with _lock:
        if _depth == 0:
            _events.clear()
            _attempted = 0
            _trace_id = trace_id
            _started_wall = now_utc()
            _started_mono = time.perf_counter()
            _install_hooks()
        _depth += 1


def uninstall():
    global _attempted, _depth, _trace_id
    with _lock:
        if _depth <= 0:
            return
        _depth -= 1
        if _depth != 0:
            return
        _restore_hooks()
        snapshot = list(_events)
        attempted = _attempted
        trace = _trace_id
        started_wall = _started_wall
        started_mono = _started_mono
        _events.clear()
        _attempted = 0
        _trace_id = ""
    publish_run(trace, started_wall, started_mono, snapshot, attempted)


def force_reset():
    global _attempted, _depth, _started_mono, _started_wall, _trace_id
    with _lock:
        _restore_hooks()
        _events.clear()
        _depth = 0
        _attempted = 0
        _trace_id = ""
        _started_wall = None
        _started_mono = None


def _parse_http(raw):
    head, _, body = raw.partition(b"\r\n\r\n")
    lines = head.split(b"\r\n")
    status = None
    if lines:
        parts = lines[0].split(b" ")
        if len(parts) >= 2 and parts[1].isdigit():
            status = int(parts[1])
    length = None
    for line in lines[1:]:
        if line.lower().startswith(b"content-length:"):
            text = line.split(b":", 1)[1].strip()
            if text.isdigit():
                length = int(text)
    return status, length, body


async def async_http_get(url):
    """Stdlib asyncio HTTP/1.1 GET. The record is written after the body arrives."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    port = parts.port or (443 if parts.scheme == "https" else 80)
    path = parts.path or "/"
    if parts.query:
        path = path + "?" + parts.query
    scheme = parts.scheme if parts.scheme in ("http", "https") else "unknown"
    view = {
        "destination_host": host,
        "destination_port": port,
        "method": "GET",
        "path": path,
        "scheme": scheme,
    }
    record = shield_active() and host_in_scope(host)
    token = _http_owns.set(True) if record else None
    started_wall = now_utc()
    started_mono = time.perf_counter()
    try:
        reader, writer = await asyncio.open_connection(host, port)
        try:
            request = f"GET {path} HTTP/1.0\r\nHost: {host}\r\nConnection: close\r\n\r\n"
            writer.write(request.encode("ascii", "strict"))
            await writer.drain()
            raw = await reader.read()
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
        status, length, body = _parse_http(raw)
        if record:
            extra = {}
            if status is not None:
                extra["http_status"] = status
            else:
                extra["application_status"] = "UNAVAILABLE"
            if length is not None:
                extra["response_bytes"] = length
            _finished(view, "python_http_client", started_wall, started_mono, **extra)
        return body
    except Exception as exc:
        if record:
            _finished(
                view,
                "python_http_client",
                started_wall,
                started_mono,
                application_status="UNAVAILABLE",
                error_class=_error_class(exc),
                failure_kind=_failure_kind(exc),
            )
        raise
    finally:
        if token is not None:
            _http_owns.reset(token)
