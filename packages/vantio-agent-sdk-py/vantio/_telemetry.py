"""
[ ∅ VANTIO ] Lane 1 — anonymous, opt-out usage telemetry (Python parity).

Mirrors the Node CLI telemetry hook. Sends ONLY anonymous, aggregate metadata:
a random anonymous id, the runtime/os strings, an event name, the set of LLM
hostnames contacted, and a few counts. It NEVER sends prompts, completions, API
keys, emails, or any content/PII — that is the entire privacy contract.

Fire-and-forget on a short-timeout daemon thread so it can never block, slow,
or crash the agent. Standard library only — no third-party dependencies.

Opt out: VANTIO_TELEMETRY_DISABLED=1  or  DO_NOT_TRACK=1
"""
from __future__ import annotations

import json
import os
import platform
import sys
import threading
import urllib.request
import uuid
from typing import Optional, Sequence

_DEFAULT_BASE_URL = "https://vantio.ai"

# Guards a single anonymous "run" event per process (see send_run_telemetry_once).
_sent_once = False
_once_lock = threading.Lock()


def is_telemetry_disabled() -> bool:
    """True when the user has opted out via VANTIO_TELEMETRY_DISABLED or DO_NOT_TRACK."""
    return (
        os.environ.get("VANTIO_TELEMETRY_DISABLED") == "1"
        or os.environ.get("DO_NOT_TRACK") == "1"
    )


def _anonymous_id() -> str:
    """Read (or lazily create) a persistent random anonymous id.

    Stored at ``~/.vantio/telemetry-id``. On any filesystem error we fall back
    to an ephemeral per-run id — this function never raises.
    """
    try:
        vantio_dir = os.path.join(os.path.expanduser("~"), ".vantio")
        id_path = os.path.join(vantio_dir, "telemetry-id")
        try:
            with open(id_path, "r", encoding="utf-8") as fh:
                existing = fh.read().strip()
            if existing:
                return existing
        except OSError:
            pass  # Not created yet — fall through and create it.

        new_id = str(uuid.uuid4())
        try:
            os.makedirs(vantio_dir, exist_ok=True)
            with open(id_path, "w", encoding="utf-8") as fh:
                fh.write(new_id + "\n")
            try:
                os.chmod(id_path, 0o600)
            except OSError:
                pass
        except OSError:
            pass  # Home dir not writable — ephemeral id for this run only.
        return new_id
    except Exception:
        return str(uuid.uuid4())  # Never raise.


def _post(url: str, body: bytes) -> None:
    try:
        req = urllib.request.Request(
            url,
            data=body,
            # No api key. No auth header. Anonymous by construction.
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        # Bound the blocking urlopen so a stalled endpoint can never hang us.
        urllib.request.urlopen(req, timeout=3)  # noqa: S310 (fixed scheme below)
    except Exception:
        pass  # Swallow all errors — telemetry must never surface.


def send_telemetry(
    *,
    event: str = "summary",
    hosts: Optional[Sequence[str]] = None,
    call_count: int = 0,
    redacted_count: Optional[int] = None,
    blocked_count: Optional[int] = None,
    sdk_version: Optional[str] = None,
    framework: Optional[str] = None,
) -> None:
    """Fire-and-forget anonymous usage telemetry. Never blocks, never raises.

    Only the whitelisted, anonymous fields below are ever transmitted.
    """
    try:
        if is_telemetry_disabled():
            return

        base = os.environ.get("VANTIO_INGEST_URL") or _DEFAULT_BASE_URL
        # Only ever speak http(s); refuse anything exotic a misconfig might inject.
        if not base.startswith(("http://", "https://")):
            return
        url = f"{base.rstrip('/')}/api/v1/telemetry"

        payload = {
            "anonymousId": _anonymous_id(),
            "runtime": "python",
            "runtimeVersion": platform.python_version(),
            "os": sys.platform,
            "event": event if event in ("run", "summary") else "summary",
            "hosts": [str(h) for h in (hosts or [])][:50],
            "callCount": int(call_count) if isinstance(call_count, int) else 0,
        }
        if sdk_version is not None:
            payload["sdkVersion"] = str(sdk_version)
        if redacted_count is not None:
            payload["redactedCount"] = int(redacted_count)
        if blocked_count is not None:
            payload["blockedCount"] = int(blocked_count)
        if framework is not None:
            payload["framework"] = str(framework)

        body = json.dumps(payload).encode("utf-8")
        threading.Thread(target=_post, args=(url, body), daemon=True).start()
    except Exception:
        pass  # Telemetry must never affect the agent.


def send_run_telemetry_once(sdk_version: Optional[str] = None) -> None:
    """Emit a single anonymous ``run`` event per process.

    Used by ``shield()`` so a process that runs an agent reports one anonymous
    usage ping regardless of how many times shield is entered. Safe to call
    repeatedly — only the first call does anything.
    """
    global _sent_once
    try:
        if is_telemetry_disabled():
            return
        with _once_lock:
            if _sent_once:
                return
            _sent_once = True
        send_telemetry(event="run", sdk_version=sdk_version)
    except Exception:
        pass  # Telemetry must never affect the agent.
