"""Evidence records store tokens and hashes, not conversation text."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

FORBIDDEN = frozenset(
    {
        "prompt",
        "completion",
        "body",
        "query",
        "packet",
        "payload",
        "conversation",
        "messages",
        "qname",
        "path",
        "headers",
    }
)


class EvidenceRejected(Exception):
    pass


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _check(value: object, trail: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or key.lower() in FORBIDDEN:
                raise EvidenceRejected(trail + "." + str(key))
            _check(item, trail + "." + key)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _check(item, f"{trail}[{index}]")
        return
    if isinstance(value, str) and len(value) > 512:
        raise EvidenceRejected(trail)


def evidence_record(drill_id: str, result: str, cases: list[dict[str, object]], **extra: object) -> dict[str, object]:
    record: dict[str, object] = {
        "drill_id": drill_id,
        "result": result,
        "label": "Lab-only",
        "kernel_attach": "Roadmap",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cases": cases,
    }
    record.update(extra)
    _check(record, "evidence")
    return record
