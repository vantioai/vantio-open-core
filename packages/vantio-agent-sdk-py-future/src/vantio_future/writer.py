"""Canonical writer and the previous-shape writer used after rollback.

The default mode writes contract records. `legacy` mode writes the previous
3.1.0 shape for the next shield only. An existing file is left in place.
"""

import json
import os
from pathlib import Path

from vantio_future.clock import duration_ms, format_utc, now_utc
from vantio_future.contract_bridge import canonical_json, validate_evidence
from vantio_future.identity import (
    ACTIVATES_UNIT_D,
    EMPTY_SHIELD_DISPOSITION,
    FUTURE_VERSION,
    LEGACY_SCHEMA_VERSION,
    PRODUCER,
    PROHIBITED_RECORD_NAMES,
    RUNTIME,
    SCHEMA_STATUS,
    SCHEMA_VERSION,
    UNICODE_PROFILE_ID,
)

_mode = "canonical"


def writer_mode():
    env = os.environ.get("VANTIO_PKG02_PYTHON_WRITER", "").strip().lower()
    if env == "canonical" or env == "legacy":
        return env
    return _mode


def set_writer_mode(mode):
    global _mode
    if mode == "canonical":
        _mode = "canonical"
        return
    if mode == "legacy":
        _mode = "legacy"
        return
    raise ValueError("writer mode must be canonical or legacy")


def reset_writer_mode():
    global _mode
    _mode = "canonical"


def _http_code(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int) and 100 <= value <= 599:
        return value
    if isinstance(value, str) and value.isdigit():
        code = int(value)
        if 100 <= code <= 599:
            return code
    return None


def _application_from_http(code):
    if code is None:
        return None
    if 200 <= code < 400:
        return "SUCCESS"
    if 400 <= code <= 599:
        return "APPLICATION_ERROR"
    return "UNAVAILABLE"


def _optics_for_input(fields):
    if "optics_status" in fields:
        optics = fields["optics_status"]
    elif "opticsStatus" in fields:
        optics = fields["opticsStatus"]
    else:
        optics = None
    if optics in (None, "SUCCESS"):
        return "UNAVAILABLE"
    return optics


def _base_identity():
    return {
        "cli_or_sdk_version": FUTURE_VERSION,
        "evidence_origin": "LOCAL_OBSERVATION",
        "producer": PRODUCER,
        "runtime": RUNTIME,
        "schema_status": SCHEMA_STATUS,
        "schema_version": SCHEMA_VERSION,
    }


def _contract_event(fields):
    if any(name in fields for name in PROHIBITED_RECORD_NAMES):
        return None
    payload = _base_identity()
    payload["record_type"] = "observation_event"
    payload["action"] = "OBSERVED"
    payload["optics_status"] = _optics_for_input(fields)
    for key in (
        "clock_quality",
        "destination_host",
        "destination_port",
        "duration_ms",
        "error_class",
        "failure_kind",
        "lifecycle",
        "mediation",
        "method",
        "path",
        "request_bytes",
        "scheme",
        "started_at",
    ):
        if key in fields and fields[key] is not None:
            payload[key] = fields[key]
    if "response_bytes" in fields and fields["response_bytes"] is not None:
        payload["response_bytes"] = fields["response_bytes"]
    code = _http_code(fields.get("http_status"))
    if code is not None:
        payload["http_status"] = code
    application = fields.get("application_status")
    if application == "PARTIAL":
        application = None
    if code is None and application in ("SUCCESS", "APPLICATION_ERROR", "UNAVAILABLE", "NOT_OBSERVED"):
        payload["application_status"] = application
    if payload.get("failure_kind") == "none":
        payload.pop("failure_kind", None)
    if isinstance(payload.get("mediation"), str) and "," in payload["mediation"]:
        payload["mediation"] = "unknown"
    result = validate_evidence(payload)
    profile = (result.get("diagnostics") or {}).get("unicode_profile_id")
    if profile != UNICODE_PROFILE_ID:
        return None
    record = result.get("record")
    if not result.get("record_emitted") or not isinstance(record, dict):
        return None
    if record.get("optics_status") == "SUCCESS":
        return None
    if record.get("application_status") == "PARTIAL":
        return None
    if "provider_id" in record or "provider" in record:
        return None
    return record


def seal_event(fields):
    """Validate one observation. A prohibited name or a failed check emits nothing."""
    if not isinstance(fields, dict):
        return None
    try:
        return _contract_event(fields)
    except Exception:
        return None


def _lifecycle(events):
    statuses = []
    for event in events:
        status = event.get("application_status")
        if status in ("SUCCESS", "APPLICATION_ERROR"):
            statuses.append(status)
    if len(set(statuses)) > 1:
        return "PARTIAL"
    return "COMPLETE"


def _bundle_optics(attempted, events):
    if attempted <= 0:
        return "NOT_OBSERVED"
    if events:
        return "OBSERVED"
    return "UNAVAILABLE"


def assemble_canonical(trace_id, started_at, ended_at, duration, events, attempted):
    sealed = []
    for raw in events:
        record = seal_event(raw)
        if record is not None:
            sealed.append(record)
    optics = _bundle_optics(attempted, sealed)
    envelope_input = _base_identity()
    envelope_input.update(
        {
            "call_count": len(sealed),
            "ended_at": ended_at,
            "lifecycle": _lifecycle(sealed) if sealed else "COMPLETE",
            "record_type": "run_envelope",
            "run_id": trace_id,
            "started_at": started_at,
        }
    )
    if duration is not None:
        envelope_input["clock_quality"] = "MONOTONIC"
        envelope_input["duration_ms"] = duration
    envelope_result = validate_evidence(envelope_input)
    profile = (envelope_result.get("diagnostics") or {}).get("unicode_profile_id")
    version = (envelope_result.get("diagnostics") or {}).get("unicode_profile_version")
    if profile != UNICODE_PROFILE_ID:
        raise RuntimeError("unicode profile mismatch")
    envelope = envelope_result.get("record")
    if not isinstance(envelope, dict):
        raise RuntimeError("envelope rejected")
    bundle = {
        "cli_or_sdk_version": FUTURE_VERSION,
        "compatibility": {"legacy_schema_version": LEGACY_SCHEMA_VERSION},
        "empty_shield": EMPTY_SHIELD_DISPOSITION if optics == "NOT_OBSERVED" else None,
        "envelope": envelope,
        "events": sealed,
        "optics_status": optics,
        "producer": PRODUCER,
        "runtime": RUNTIME,
        "schema_status": SCHEMA_STATUS,
        "schema_version": SCHEMA_VERSION,
        "unicode_profile_id": profile,
        "unicode_profile_version": version,
    }
    if bundle["empty_shield"] is None:
        del bundle["empty_shield"]
    return bundle


def _legacy_timestamp(raw, fallback):
    stamp = raw.get("started_at")
    if isinstance(stamp, str) and stamp.endswith("Z") and "T" in stamp:
        body = stamp[:-1]
        if "." in body:
            left, frac = body.split(".", 1)
            return left + "." + (frac + "000000")[:6] + "+00:00"
        return body + "+00:00"
    return fallback


def _legacy_call(raw, fallback_ts):
    call = {
        "action": "OBSERVED",
        "hostname": raw.get("destination_host") or "unknown",
        "mediation": raw.get("mediation") or "python_urllib",
        "opticsStatus": "SUCCESS",
        "provider": "other",
        "ts": _legacy_timestamp(raw, fallback_ts),
    }
    code = _http_code(raw.get("http_status"))
    if code is not None:
        call["status"] = code
        call["applicationStatus"] = _application_from_http(code)
        call["ok"] = 200 <= code < 400
    else:
        call["applicationStatus"] = raw.get("application_status") or "UNAVAILABLE"
        call["ok"] = False
    if raw.get("failure_kind") not in (None, "none"):
        call["failure_kind"] = raw["failure_kind"]
    if raw.get("error_class"):
        call["error_class"] = raw["error_class"]
    if raw.get("method"):
        call["method"] = raw["method"]
    if raw.get("path"):
        call["path"] = raw["path"]
    if raw.get("scheme"):
        call["scheme"] = raw["scheme"]
    if "response_bytes" in raw and raw["response_bytes"] is not None:
        call["bytes_observed"] = raw["response_bytes"]
    if raw.get("request_bytes") is not None:
        call["bytes_observed"] = raw["request_bytes"]
    if raw.get("duration_ms") is not None:
        call["duration_ms"] = raw["duration_ms"]
    return call


def assemble_legacy(trace_id, started_at, ended_at, events):
    calls = [_legacy_call(raw, started_at) for raw in events]
    mediations = sorted({call.get("mediation") or "python_urllib" for call in calls}) or ["python_urllib"]
    return {
        "calls": calls,
        "data_note": "Developer egress data log — metadata only; never prompts or completions.",
        "generated_at": ended_at,
        "mediation": ",".join(mediations),
        "plane": "optics",
        "residual": {
            "note": "Previous Python writer shape restored for a later shield after Unit E rollback.",
        },
        "runtime": "python",
        "schema_status": SCHEMA_STATUS,
        "schema_version": LEGACY_SCHEMA_VERSION,
        "started_at": started_at,
        "status_labels": {
            "applicationStatus": "Observed outcome",
            "opticsStatus": "Optics status",
        },
        "trace_id": trace_id,
        "vantio_run_log": "1",
        "workflow": "sight_loop",
    }


def _safe_trace(trace_id):
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(trace_id))[:80]
    return safe or "run"


def _allocate(directory, trace_id):
    safe = _safe_trace(trace_id)
    candidate = directory / f"{safe}.json"
    if not candidate.exists():
        return candidate
    for index in range(1, 100):
        alt = directory / f"{safe}.{index}.json"
        if not alt.exists():
            return alt
    return None


def _runs_dir():
    home = os.environ.get("VANTIO_HOME") or os.path.join(os.path.expanduser("~"), ".vantio")
    runs = Path(home) / "runs"
    runs.mkdir(mode=0o700, parents=True, exist_ok=True)
    return runs


def publish_run(trace_id, started_wall, started_mono, events, attempted):
    """Write the next shield file. Failures stay inside this function."""
    if ACTIVATES_UNIT_D:
        return None
    try:
        ended = now_utc()
        started = started_wall or ended
        measured = duration_ms(started_mono)
        mode = writer_mode()
        if mode == "legacy":
            if not events:
                return None
            payload = assemble_legacy(trace_id, started.isoformat(), ended.isoformat(), events)
            text = json.dumps(payload, indent=2) + "\n"
        elif mode == "canonical":
            payload = assemble_canonical(
                trace_id,
                format_utc(started),
                format_utc(ended),
                measured,
                events,
                attempted,
            )
            text = canonical_json(payload) + "\n"
        else:
            return None
        path = _allocate(_runs_dir(), trace_id)
        if path is None:
            return None
        path.write_text(text, encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return path
    except Exception:
        return None
