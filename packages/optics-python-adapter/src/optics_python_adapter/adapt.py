"""Inert Python adapter.

Reads a detached copy. Calls the private evidence mapper. Returns a
vocabulary projection. Does not write a run file and does not import the live SDK.
"""

import copy

from optics_python_adapter.contract_loader import load_contract
from optics_python_adapter.posture import AUDIENCE, CLAIMED_CPYTHON, POSTURE
from optics_python_adapter.project import (
    envelope_claims_started_at,
    mixed_lifecycle,
    project_envelope,
    project_observation,
)


def _reading(**updates):
    reading = {
        "achievement": "NOT_SHIPPED",
        "audience": AUDIENCE,
        "canonical": None,
        "claimed_cpython": CLAIMED_CPYTHON,
        "diagnostics": [],
        "events": None,
        "events_invented": False,
        "fields_not_promoted": [],
        "live_writer_modified": False,
        "mediation_reading": None,
        "optics_reading": None,
        "posture": list(POSTURE),
        "reader_origin_label": None,
        "reasons": [],
        "record_emitted": False,
        "stable_schema": False,
        "unsupported_state": None,
        "writes_live_run_directory": False,
    }
    reading.update(updates)
    reading["diagnostics"] = sorted(set(reading["diagnostics"]))
    reading["fields_not_promoted"] = sorted(set(reading["fields_not_promoted"]))
    reading["reasons"] = sorted(set(reading["reasons"]))
    if reading["canonical"] is not None and reading["canonical"].get("optics_status") == "SUCCESS":
        reading["canonical"]["optics_status"] = "UNAVAILABLE"
        if "OPTIMISTIC_DEFAULT_FORBIDDEN" not in reading["reasons"]:
            reading["reasons"] = sorted(set(reading["reasons"] + ["OPTIMISTIC_DEFAULT_FORBIDDEN"]))
    return reading


def _unsupported(surface):
    if surface in ("future_not_shipped", "node_sdk_0_2_4"):
        return "UNSUPPORTED"
    return None


def _mediation(value, contract):
    if not isinstance(value, str) or value == "":
        return None, []
    if value in contract["mediation"] and "," not in value:
        return value, []
    return "unknown", ["mediation"]


def _finish_mapper(result, canonical, events, surface, mediation_reading, promoted, reasons, diagnostics):
    emitted = canonical is not None
    optics = None
    if isinstance(canonical, dict) and "optics_status" in canonical:
        optics = canonical["optics_status"]
    elif isinstance(events, list) and events:
        optics = events[0].get("optics_status")
    return _reading(
        canonical=canonical,
        diagnostics=diagnostics,
        events=events,
        fields_not_promoted=promoted,
        mediation_reading=mediation_reading,
        optics_reading=optics,
        reader_origin_label=None if result is None else result.get("reader_origin_label"),
        reasons=reasons,
        record_emitted=emitted,
        unsupported_state=_unsupported(surface),
    )


def _closed(optics_reading, reason, diagnostics=None):
    return _reading(
        diagnostics=diagnostics or [],
        optics_reading=optics_reading,
        reasons=[reason],
        record_emitted=False,
    )


def adapt_fixture(fixture):
    """Score one Unit A fixture. The fixture object is not modified."""
    if not isinstance(fixture, dict):
        return _closed("OPTICS_ERROR", "RECORD_TYPE_REJECTED")
    surface = None
    version = None
    producer = fixture.get("producer")
    if isinstance(producer, dict):
        surface = producer.get("surface")
        version = producer.get("version")
    parse = fixture.get("input_parse")
    if parse == "ABSENT_FILE":
        kind = "EMPTY_SHIELD_ABSENT" if surface == "python_3_1_0" else "ABSENT_FILE"
        return _closed("UNAVAILABLE", kind, ["absent file is UNAVAILABLE"])
    if parse == "UNREADABLE":
        return _closed("OPTICS_ERROR", "UNREADABLE", ["unreadable bytes are OPTICS_ERROR"])
    if parse == "MALFORMED_JSON":
        contract = load_contract()
        note = fixture.get("raw_input_note")
        if isinstance(note, str) and note != "":
            contract["validate_evidence"](note)
        return _closed("OPTICS_ERROR", "MALFORMED_JSON", ["malformed JSON has no record"])
    return adapt_copy(
        fixture.get("input_record"),
        surface=surface,
        producer_version=version,
    )


def adapt_copy(source, surface=None, producer_version=None):
    """Adapt a copy of source. Path strings are not opened."""
    if isinstance(source, (str, bytes, bytearray)) or hasattr(source, "__fspath__"):
        return _closed("UNAVAILABLE", "PATH_NOT_OPENED", ["live paths are not opened"])
    if source is None:
        return _closed("UNAVAILABLE", "ABSENT_FILE")
    if not isinstance(source, dict):
        return _closed("OPTICS_ERROR", "RECORD_TYPE_REJECTED")
    working = copy.deepcopy(source)
    if _is_triple(working):
        return _adapt_triple(working, surface=surface, producer_version=producer_version)
    return _adapt_raw(working, surface=surface, producer_version=producer_version)


def _is_triple(value):
    allowed = {"call", "envelope", "extra"}
    return set(value.keys()).issubset(allowed) and ("call" in value or "envelope" in value or "extra" in value)


def _adapt_triple(triple, surface, producer_version):
    call = triple.get("call")
    envelope = triple.get("envelope")
    extra = triple.get("extra")
    if surface == "node_sdk_0_2_4":
        names = []
        if isinstance(extra, dict):
            names.extend(extra.keys())
            payload = extra.get("eventPayload")
            if isinstance(payload, dict):
                names.extend(payload.keys())
        return _reading(
            fields_not_promoted=names,
            optics_reading="UNAVAILABLE",
            reasons=["NO_LOCAL_RECORD"],
            record_emitted=False,
            unsupported_state="UNSUPPORTED",
        )
    if call is None and envelope is None:
        names = list(extra.keys()) if isinstance(extra, dict) else []
        return _reading(
            diagnostics=["future fields are not promoted"],
            fields_not_promoted=names,
            optics_reading="UNAVAILABLE",
            reasons=["FUTURE_FIELD_OMITTED"],
            record_emitted=False,
        )
    if isinstance(envelope, dict) and call is None and "calls" not in envelope and envelope.get("evidence_origin") == "IMPORTED":
        return _adapt_import(envelope, surface)
    if (
        isinstance(envelope, dict)
        and call is None
        and "calls" not in envelope
        and envelope.get("evidence_origin") == "LOCAL_OBSERVATION"
        and "producer" not in envelope
    ):
        return _adapt_claimed_local(envelope, surface)
    contract = load_contract()
    if isinstance(envelope, dict) and contract["witness_field"] in envelope:
        return _adapt_witness(envelope, surface, producer_version, contract)
    if isinstance(envelope, dict) and (isinstance(call, dict) or "calls" in envelope or envelope.get("vantio_run_log") == "1"):
        return _adapt_run_log(envelope, call if isinstance(call, dict) else None, surface)
    if isinstance(envelope, dict) and call is None:
        return _adapt_fragment(envelope, surface)
    if isinstance(call, dict):
        return _adapt_call(call, surface)
    return _closed("OPTICS_ERROR", "RECORD_TYPE_REJECTED")


def _adapt_raw(raw, surface, producer_version):
    contract = load_contract()
    if contract["witness_field"] in raw and "calls" not in raw:
        return _adapt_witness(raw, surface, producer_version, contract)
    if raw.get("evidence_origin") == "IMPORTED" and "calls" not in raw:
        return _adapt_import(raw, surface)
    if "calls" in raw or raw.get("vantio_run_log") == "1":
        return _adapt_run_log(raw, None, surface)
    if "hostname" in raw or "status" in raw or "http_status" in raw or "opticsStatus" in raw or "optics_status" in raw:
        return _adapt_call(raw, surface)
    return _closed("OPTICS_ERROR", "RECORD_TYPE_REJECTED")


def _shape_call(call):
    shaped = copy.deepcopy(call)
    aliases = (
        ("hostname", "destination_host"),
        ("status", "http_status"),
        ("opticsStatus", "optics_status"),
        ("applicationStatus", "application_status"),
        ("ts", "started_at"),
    )
    for source_name, canonical_name in aliases:
        if source_name in shaped and canonical_name not in shaped:
            shaped[canonical_name] = shaped.pop(source_name)
    shaped["record_type"] = "observation_event"
    return shaped


def _adapt_call(call, surface):
    contract = load_contract()
    shaped = _shape_call(call)
    result = contract["validate_evidence"](shaped)
    record = result.get("record") or {}
    projected, reasons, diagnostics, promoted = project_observation(record, call, contract)
    if result.get("reason_code"):
        reasons.append(result["reason_code"])
    return _finish_mapper(result, projected, None, surface, None, promoted, reasons, diagnostics)


def _adapt_run_log(envelope, call, surface):
    contract = load_contract()
    shaped = copy.deepcopy(envelope)
    if "ts" in shaped and "started_at" not in shaped:
        shaped["started_at"] = shaped.pop("ts")
    if not isinstance(shaped.get("calls"), list):
        shaped["calls"] = [copy.deepcopy(call)] if isinstance(call, dict) else []
    if shaped.get("vantio_run_log") != "1":
        shaped["vantio_run_log"] = "1"
    mediation_reading, mediation_promoted = _mediation(envelope.get("mediation"), contract)
    result = contract["validate_evidence"](shaped)
    reasons = []
    diagnostics = []
    promoted = list(mediation_promoted)
    if result.get("reason_code"):
        reasons.append(result["reason_code"])
    source_calls = envelope["calls"] if isinstance(envelope.get("calls"), list) else shaped["calls"]
    if isinstance(envelope.get("calls"), list) and len(envelope["calls"]) == 0:
        canonical = project_envelope(result.get("record") or {}, envelope)
        canonical["call_count"] = 0
        canonical["optics_status"] = "NOT_OBSERVED"
        return _finish_mapper(result, canonical, None, surface, mediation_reading, promoted, reasons, diagnostics)
    projected_events = []
    mapper_events = result.get("events") or []
    for index, source_call in enumerate(source_calls):
        mapper_record = {}
        if index < len(mapper_events) and isinstance(mapper_events[index], dict):
            mapper_record = mapper_events[index].get("record") or {}
            if mapper_events[index].get("reason_code"):
                reasons.append(mapper_events[index]["reason_code"])
        projected, obs_reasons, obs_diagnostics, obs_promoted = project_observation(
            mapper_record,
            source_call if isinstance(source_call, dict) else {},
            contract,
        )
        reasons.extend(obs_reasons)
        diagnostics.extend(obs_diagnostics)
        promoted.extend(obs_promoted)
        projected_events.append(projected)
    if len(source_calls) > 1:
        canonical = {}
        if mixed_lifecycle(projected_events):
            canonical["lifecycle"] = "PARTIAL"
        if "summary_applicationStatus" in (envelope if isinstance(envelope, dict) else {}):
            promoted.append("summary_applicationStatus")
        return _finish_mapper(
            result,
            canonical,
            projected_events,
            surface,
            mediation_reading,
            promoted,
            reasons,
            diagnostics,
        )
    env_projected = project_envelope(result.get("record") or {}, envelope)
    obs_projected = projected_events[0] if projected_events else {}
    if envelope_claims_started_at(envelope) and "started_at" in env_projected:
        obs_projected.pop("started_at", None)
    canonical = {}
    canonical.update(env_projected)
    canonical.update(obs_projected)
    if envelope_claims_started_at(envelope) and "started_at" in env_projected:
        canonical["started_at"] = env_projected["started_at"]
    return _finish_mapper(result, canonical, None, surface, mediation_reading, promoted, reasons, diagnostics)


def _adapt_fragment(envelope, surface):
    contract = load_contract()
    shaped = {"record_type": "run_envelope"}
    if "run_id" in envelope:
        shaped["run_id"] = envelope["run_id"]
    elif "trace_id" in envelope:
        shaped["run_id"] = envelope["trace_id"]
    if "pid" in envelope:
        shaped["process_id"] = envelope["pid"]
    elif "process_id" in envelope:
        shaped["process_id"] = envelope["process_id"]
    if "ppid" in envelope:
        shaped["parent_process_id"] = envelope["ppid"]
    elif "parent_process_id" in envelope:
        shaped["parent_process_id"] = envelope["parent_process_id"]
    if "ts" in envelope:
        shaped["started_at"] = envelope["ts"]
    elif "started_at" in envelope:
        shaped["started_at"] = envelope["started_at"]
    result = contract["validate_evidence"](shaped)
    record = result.get("record") or {}
    canonical = project_envelope(record, shaped)
    if "trace_id" in envelope and contract["witness_field"] not in envelope:
        canonical["trace_id_basis"] = "ASSERTED_CONTEXT"
    if "optics_status" not in canonical and "opticsStatus" not in envelope:
        canonical["optics_status"] = "UNAVAILABLE"
    reasons = ["ASSERTED_CONTEXT"]
    if result.get("reason_code"):
        reasons.append(result["reason_code"])
    return _finish_mapper(result, canonical, None, surface, None, ["trace_id"], reasons, ["legacy trace_id stored as run_id"])


def _adapt_import(envelope, surface):
    contract = load_contract()
    shaped = {"record_type": "import_quarantine"}
    shaped.update(copy.deepcopy(envelope))
    result = contract["validate_evidence"](shaped)
    record = result.get("record") or {}
    canonical = {
        "evidence_origin": record.get("evidence_origin"),
        "original_evidence_origin": record.get("original_evidence_origin"),
    }
    return _finish_mapper(result, canonical, None, surface, None, [], [result.get("reason_code") or "IMPORTED"], [])


def _adapt_claimed_local(envelope, surface):
    contract = load_contract()
    shaped = {"record_type": "run_envelope", "evidence_origin": envelope.get("evidence_origin")}
    result = contract["validate_evidence"](shaped)
    canonical = {"reader_origin_label": result.get("reader_origin_label")}
    return _finish_mapper(
        result,
        canonical,
        None,
        surface,
        None,
        ["evidence_origin"],
        [result.get("reason_code") or "PROVENANCE_INSUFFICIENT"],
        ["claimed local without producer stays LEGACY_UNMARKED"],
    )


def _adapt_witness(envelope, surface, producer_version, contract):
    shaped = {
        "record_type": "run_envelope",
        "producer": envelope.get("producer"),
        "run_id": envelope.get("run_id"),
        "trace_id": envelope.get("trace_id"),
        "trace_id_basis": "OPTICS_GENERATED",
        contract["witness_field"]: envelope.get(contract["witness_field"]),
    }
    version = envelope.get("cli_or_sdk_version") or producer_version
    if isinstance(version, str) and version != "":
        shaped["cli_or_sdk_version"] = version
    result = contract["validate_evidence"](shaped)
    record = result.get("record") or {}
    canonical = {
        "producer": record.get("producer"),
        "run_id": record.get("run_id"),
        "trace_id": record.get("trace_id"),
        "trace_id_basis": record.get("trace_id_basis"),
    }
    return _finish_mapper(
        result,
        canonical,
        None,
        surface,
        None,
        [contract["witness_field"]],
        [result.get("reason_code") or "OK"],
        ["witness absent from canonical"],
    )


def canonical_json(value):
    return load_contract()["canonical_json"](value)
