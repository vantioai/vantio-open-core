"""Unsigned Optics observation fragment.

Enterprise seals this object in vantio-enterprise-private. This module does
not sign, does not enforce, and does not claim a host proof.
"""

from __future__ import annotations

import hashlib
from typing import Any

from canonical import canonical_json

SCHEMA_ID = "vantio.optics.observation-fragment"
SCHEMA_STATUS = "unstable-pre-1.0"
SCHEMA_VERSION = 0


def _enforcement_action(action: object) -> bool:
    if not isinstance(action, str) or action == "":
        return False
    if action == "OBSERVED":
        return False
    if action in {"ALLOWED", "REDACTED"}:
        return True
    return action.startswith("BLOCKED") or action.startswith("DRY_RUN")


def _int_or_null(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0:
        return None
    return value


def _text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return None


def build_observation_fragment(
    record: dict[str, Any],
    *,
    producer: str,
    producer_version: str,
) -> dict[str, Any]:
    """Return ok, reason, and fragment. A refusal has fragment None."""

    if not isinstance(record, dict):
        return {"ok": False, "reason": "MALFORMED", "fragment": None}
    summary = record.get("summary") if isinstance(record.get("summary"), dict) else {}
    if summary.get("blocked") or summary.get("redacted"):
        return {"ok": False, "reason": "ENFORCEMENT_ACTION_EXCLUDED", "fragment": None}
    raw_calls = record.get("calls")
    if raw_calls is None:
        raw_calls = []
    if not isinstance(raw_calls, list):
        return {"ok": False, "reason": "MALFORMED", "fragment": None}
    calls: list[dict[str, Any]] = []
    for call in raw_calls:
        if not isinstance(call, dict):
            return {"ok": False, "reason": "MALFORMED", "fragment": None}
        action = call.get("action")
        if _enforcement_action(action):
            return {"ok": False, "reason": "ENFORCEMENT_ACTION_EXCLUDED", "fragment": None}
        status = call.get("status", call.get("http_status"))
        calls.append(
            {
                "action": action if action == "OBSERVED" else None,
                "application_status": _text(call.get("applicationStatus") or call.get("application_status")),
                "hostname": _text(call.get("hostname")),
                "http_status": _int_or_null(status) if not isinstance(status, bool) else None,
                "method": _text(call.get("method")),
                "optics_status": _text(call.get("opticsStatus") or call.get("optics_status")),
                "path": _text(call.get("path")),
                "response_bytes": _int_or_null(call.get("bytes", call.get("response_bytes"))),
            }
        )
    body: dict[str, Any] = {
        "calls": calls,
        "claim_ceiling": "OBSERVATION_ONLY",
        "enforcement_attached": False,
        "live_enforcement": "NOT_APPLICABLE",
        "producer": producer,
        "producer_version": producer_version,
        "product": "optics",
        "role": "observation",
        "schema_id": SCHEMA_ID,
        "schema_status": SCHEMA_STATUS,
        "schema_version": SCHEMA_VERSION,
        "trace_id": _text(record.get("trace_id")) or "",
    }
    digest = hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()
    body["record_sha256"] = "sha256:" + digest
    return {"ok": True, "reason": None, "fragment": body}


def fragment_digest_matches(fragment: dict[str, Any]) -> bool:
    if not isinstance(fragment, dict):
        return False
    recorded = fragment.get("record_sha256")
    body = {key: value for key, value in fragment.items() if key != "record_sha256"}
    digest = "sha256:" + hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()
    return recorded == digest
