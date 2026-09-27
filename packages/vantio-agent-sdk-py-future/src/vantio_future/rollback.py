"""Reader used after the new writer is disabled.

A canonical file stays on disk. This reader reports UNSUPPORTED and surfaces
schema_status. It does not rewrite the file and it does not map the status
to SUCCESS.
"""

import json
from pathlib import Path


def read_rolled_back(path):
    target = Path(path)
    before = target.read_bytes()
    payload = json.loads(before.decode("utf-8"))
    after = target.read_bytes()
    origin = None
    envelope = payload.get("envelope") if isinstance(payload, dict) else None
    if isinstance(envelope, dict):
        origin = envelope.get("evidence_origin")
    canonical = (
        isinstance(payload, dict)
        and payload.get("schema_version") == 0
        and payload.get("producer") == "python_observe"
    )
    if canonical:
        optics = "UNSUPPORTED"
    else:
        optics = "LEGACY_SHAPE"
    return {
        "bytes_unchanged": before == after,
        "evidence_origin": origin,
        "file_rewritten": False,
        "optics_status": optics,
        "schema_status": payload.get("schema_status") if isinstance(payload, dict) else None,
    }
