"""Vocabulary projection of a mapper result.

The scored object follows the merged Unit A fixtures. Defaults the mapper
fills in, and aliases, stay off that object.
"""

from optics_python_adapter.posture import PROHIBITED_CANONICAL_NAMES

_ENVELOPE_FIELDS = (
    ("run_id", ("run_id", "trace_id")),
    ("process_id", ("process_id", "pid")),
    ("parent_process_id", ("parent_process_id", "ppid")),
    ("runtime_version", ("runtime_version", "node_version")),
    ("platform", ("platform",)),
    ("arch", ("arch",)),
    ("cli_or_sdk_version", ("cli_or_sdk_version", "cli_version")),
    ("runtime", ("runtime",)),
    ("schema_status", ("schema_status",)),
    ("started_at", ("started_at", "ts")),
    ("duration_ms", ("duration_ms",)),
)


def _has(source, names):
    return isinstance(source, dict) and any(name in source for name in names)


def _scrub(value):
    if not isinstance(value, dict):
        return value
    cleaned = {}
    for key, item in value.items():
        if key in PROHIBITED_CANONICAL_NAMES:
            continue
        if key == "optics_status" and item == "SUCCESS":
            cleaned[key] = "UNAVAILABLE"
            continue
        cleaned[key] = item
    return cleaned


def precompletion(source):
    return (
        isinstance(source, dict)
        and source.get("duration_ms") == 0
        and "status" in source
        and source.get("status") is None
    )


def project_envelope(record, source):
    projected = {}
    if not isinstance(record, dict):
        return projected
    for canonical, aliases in _ENVELOPE_FIELDS:
        if canonical in record and _has(source, aliases):
            projected[canonical] = record[canonical]
    if isinstance(source, dict) and "schema_version" in source:
        projected["schema_version"] = 0
    return _scrub(projected)


def project_observation(record, source, contract):
    projected = {}
    reasons = []
    diagnostics = []
    promoted_away = []
    if not isinstance(record, dict):
        record = {}
    if not isinstance(source, dict):
        source = {}

    raw_optics = None
    if "opticsStatus" in source:
        raw_optics = source["opticsStatus"]
        promoted_away.append("opticsStatus")
    elif "optics_status" in source:
        raw_optics = source["optics_status"]
    if raw_optics == "SUCCESS" or (raw_optics is not None and raw_optics not in contract["optics_status"]):
        projected["optics_status"] = "UNAVAILABLE"
        reasons.append("OPTIMISTIC_DEFAULT_FORBIDDEN")
    elif "optics_status" in record:
        projected["optics_status"] = record["optics_status"]
    else:
        projected["optics_status"] = "UNAVAILABLE"
        reasons.append("MISSING_REQUIRED_STATUS")

    if "http_status" in record and ("status" in source or "http_status" in source):
        if record["http_status"] is not None:
            projected["http_status"] = record["http_status"]
    if "application_status" in record and record["application_status"] != "PARTIAL":
        if "http_status" in projected or "applicationStatus" in source or "application_status" in source:
            projected["application_status"] = record["application_status"]
    if "destination_host" in record and ("hostname" in source or "destination_host" in source):
        projected["destination_host"] = record["destination_host"]
    if "path" in source and "path" in record:
        projected["path"] = record["path"]
    if "scheme" in source and "scheme" in record:
        projected["scheme"] = record["scheme"]
    if "method" in source and "method" in record:
        raw_method = source["method"]
        if record["method"] == "unknown" and raw_method not in contract["methods"]:
            diagnostics.append("method " + str(raw_method) + " omitted")
            promoted_away.append("method")
            reasons.append("UNKNOWN_ENUM_OMITTED")
        else:
            projected["method"] = record["method"]
    if source.get("action") == "OBSERVED" and record.get("action") == "OBSERVED":
        projected["action"] = "OBSERVED"
    if "bytes" in source or "response_bytes" in source:
        if "response_bytes" in record:
            projected["response_bytes"] = record["response_bytes"]
    if "failure_kind" in record and record["failure_kind"] != "none":
        projected["failure_kind"] = record["failure_kind"]
    elif source.get("failure_kind") == "none":
        promoted_away.append("failure_kind")
    if record.get("issue_location") not in (None, "NONE"):
        projected["issue_location"] = record["issue_location"]
    if projected.get("issue_location") == "CUSTOMER_APPLICATION" and "error_class" in record:
        projected["error_class"] = record["error_class"]
    elif "error_class" in source and projected.get("issue_location") == "NETWORK":
        diagnostics.append("transport error_class " + str(source["error_class"]) + " omitted")
        promoted_away.append("error_class")
    if "evidence_origin" in record:
        projected["evidence_origin"] = record["evidence_origin"]
    if "ts" in source and "started_at" in record:
        projected["started_at"] = record["started_at"]
    if "sampling" in source and source["sampling"] != "UNSAMPLED":
        diagnostics.append("sampling " + str(source["sampling"]) + " omitted")
        promoted_away.append(str(source["sampling"]))
        reasons.append("SAMPLING_OMITTED")
    if "error" in source:
        promoted_away.append("error")
    if "provider" in source:
        promoted_away.append("provider")
    if "ok" in source:
        promoted_away.append("ok")

    if precompletion(source):
        projected.pop("duration_ms", None)
        projected["lifecycle"] = "INTERRUPTED"
        projected["application_status"] = "UNAVAILABLE"
        reasons.append("PRECOMPLETION_DURATION_OMITTED")
    elif "failure_kind" in projected and "application_status" not in projected and "http_status" not in projected:
        projected["application_status"] = "UNAVAILABLE"

    if projected.get("optics_status") == "SUCCESS":
        projected["optics_status"] = "UNAVAILABLE"
        reasons.append("OPTIMISTIC_DEFAULT_FORBIDDEN")
    return _scrub(projected), reasons, diagnostics, promoted_away


def envelope_claims_started_at(source):
    return _has(source, ("started_at", "ts"))


def mixed_lifecycle(events):
    statuses = []
    for event in events:
        if isinstance(event, dict) and "application_status" in event:
            statuses.append(event["application_status"])
    return len(set(statuses)) > 1
