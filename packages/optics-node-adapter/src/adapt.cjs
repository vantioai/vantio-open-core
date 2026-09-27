"use strict";

const { types } = require("util");

const { validateBytes, validateEvidence } = require("../../optics-evidence-contract/src/validate.cjs");
const boundary = require("./boundary.cjs");

const ALIAS_KEYS = new Set([
  "opticsStatus",
  "applicationStatus",
  "hostname",
  "bytes",
  "pid",
  "ppid",
  "traceId",
  "httpStatus",
  "ts",
  "node_version",
  "cli_version",
  "generated_at",
  "ok",
  "provider",
  "vantio_run_log",
  "optics_trace_witness",
]);

const PROHIBITED_KEYS = new Set([
  "prompt",
  "prompts",
  "completion",
  "completions",
  "messages",
  "message",
  "body",
  "plane",
  "data_note",
  "residual",
  "free_mode",
  "est_spend_usd",
  "workflow",
  "machine",
  "anonymousId",
  "cost",
  "usage",
  "token_count",
  "freshness",
  "widget_hint",
]);

function shell() {
  return {
    achievement: "NOT_SHIPPED",
    adapter: "node",
    adapter_disposition: "READ",
    adapter_version: boundary.ADAPTER_VERSION,
    application_result: null,
    audience: boundary.AUDIENCE,
    compatibility: {
      legacy_marker: false,
      legacy_schema_version: null,
      live_writer_modified: false,
      source_shape: "unavailable",
    },
    diagnostics: {
      fields_not_promoted: [],
      issue_location: null,
      notes: [],
      stripped_names: [],
      unicode_profile_id: null,
      unicode_profile_version: null,
    },
    events: [],
    future_writer_version: boundary.FUTURE_CLI_PLACEHOLDER,
    input_retained: false,
    live_emission: false,
    live_writer_modified: false,
    optics_health: "UNAVAILABLE",
    optimistic_default_forbidden: false,
    posture: boundary.POSTURE,
    reader_origin_label: null,
    reason_code: null,
    record: null,
    record_emitted: false,
    schema_status: boundary.SCHEMA_STATUS,
    schema_version: boundary.SCHEMA_VERSION,
    stable_schema: false,
    writer_activated: false,
    writes_live_run_directory: false,
  };
}

function note(result, text) {
  if (!result.diagnostics.notes.includes(text)) result.diagnostics.notes.push(text);
}

function allowIssue(value) {
  return boundary.ISSUE_LOCATIONS.has(value) ? value : null;
}

function cloneJson(value) {
  return JSON.parse(JSON.stringify(value));
}

function hasOwn(object, key) {
  return Object.prototype.hasOwnProperty.call(object, key);
}

function readOwn(object, key) {
  if (!object || typeof object !== "object" || !hasOwn(object, key)) return { present: false, value: undefined };
  const descriptor = Object.getOwnPropertyDescriptor(object, key);
  if (!descriptor || !hasOwn(descriptor, "value")) return { present: false, value: undefined };
  return { present: true, value: descriptor.value };
}

function prototypeHasAccessor(value, seen, depth) {
  let proto = Object.getPrototypeOf(value);
  const protos = new Set();
  while (proto && proto !== Object.prototype && proto !== Array.prototype && !protos.has(proto)) {
    protos.add(proto);
    const descriptors = Object.getOwnPropertyDescriptors(proto);
    const keys = Object.keys(descriptors);
    for (let i = 0; i < keys.length; i += 1) {
      const descriptor = descriptors[keys[i]];
      if (descriptor.get || descriptor.set) return true;
      if (hasOwn(descriptor, "value") && hasAccessor(descriptor.value, seen, depth + 1)) return true;
    }
    proto = Object.getPrototypeOf(proto);
  }
  return false;
}

function hasAccessor(value, seen, depth) {
  if (!value || typeof value !== "object") return false;
  if (depth > 8) return false;
  if (seen.has(value)) return false;
  seen.add(value);
  if (types.isProxy(value)) return true;
  if (prototypeHasAccessor(value, seen, depth)) return true;
  const descriptors = Object.getOwnPropertyDescriptors(value);
  const keys = Object.keys(descriptors);
  for (let i = 0; i < keys.length; i += 1) {
    const descriptor = descriptors[keys[i]];
    if (descriptor.get || descriptor.set) return true;
    if (!hasOwn(descriptor, "value")) return true;
    if (hasAccessor(descriptor.value, seen, depth + 1)) return true;
  }
  return false;
}

function methodAction(call) {
  const method = readOwn(call, "method");
  if (!method.present) return "absent";
  if (typeof method.value !== "string" || !/^[A-Za-z]{1,16}$/.test(method.value)) return "omit";
  if (method.value === "unknown" || boundary.METHODS.has(method.value.toUpperCase())) return "keep";
  return "omit";
}

function samplingAction(call) {
  const sampling = readOwn(call, "sampling");
  if (!sampling.present) return "absent";
  return sampling.value === "UNSAMPLED" ? "keep" : "omit";
}

function opticsFlags(call) {
  const canonical = readOwn(call, "optics_status");
  const token = canonical.present ? canonical : readOwn(call, "opticsStatus");
  if (!token.present || token.value === undefined) return { present: false, forbidden: false };
  const forbidden = token.value === "SUCCESS" || !boundary.OPTICS_STATUS.has(token.value);
  return { present: true, forbidden };
}

function callContext(call) {
  const optics = opticsFlags(call);
  const failure = readOwn(call, "failure_kind");
  const duration = readOwn(call, "duration_ms");
  const status = readOwn(call, "status");
  return {
    failureNone: failure.present && failure.value === "none",
    methodAction: methodAction(call),
    opticsForbidden: optics.forbidden,
    opticsPresent: optics.present,
    preCompletion: duration.present && duration.value === 0 && status.present && status.value === null,
    samplingAction: samplingAction(call),
  };
}

function emptyContext() {
  return callContext(null);
}

function snapshotNode(input) {
  const callsField = readOwn(input, "calls");
  const calls = Array.isArray(callsField.value) ? callsField.value : [];
  const generated = readOwn(input, "generated_at");
  const trace = readOwn(input, "trace_id");
  const mediation = readOwn(input, "mediation");
  const origin = readOwn(input, "evidence_origin");
  const originalOrigin = readOwn(input, "original_evidence_origin");
  const witness = readOwn(input, "optics_trace_witness");
  return {
    callContexts: calls.map(callContext),
    callsExplicit: hasOwn(input, "calls"),
    generatedAt: generated.present && typeof generated.value === "string" && !hasOwn(input, "ended_at"),
    kind: "node",
    legacyTrace: trace.present && typeof trace.value === "string" && !hasOwn(input, "run_id"),
    mediationJoined: mediation.present && typeof mediation.value === "string" && mediation.value.includes(","),
    origin: origin.present && typeof origin.value === "string" ? origin.value : null,
    originalOrigin: originalOrigin.present && typeof originalOrigin.value === "string" ? originalOrigin.value : null,
    spanPresent: hasOwn(input, "span_id"),
    witness: witness.present && witness.value === boundary.WITNESS_VALUE,
  };
}

function snapshotBare(input) {
  const origin = readOwn(input, "evidence_origin");
  const originalOrigin = readOwn(input, "original_evidence_origin");
  const witness = readOwn(input, "optics_trace_witness");
  return {
    callContexts: [callContext(input)],
    callsExplicit: false,
    generatedAt: false,
    kind: "call",
    legacyTrace: false,
    mediationJoined: false,
    origin: origin.present && typeof origin.value === "string" ? origin.value : null,
    originalOrigin: originalOrigin.present && typeof originalOrigin.value === "string" ? originalOrigin.value : null,
    spanPresent: hasOwn(input, "span_id"),
    witness: witness.present && witness.value === boundary.WITNESS_VALUE,
  };
}

function blankSnapshot(kind) {
  return {
    callContexts: [],
    callsExplicit: false,
    generatedAt: false,
    kind,
    legacyTrace: false,
    mediationJoined: false,
    origin: null,
    originalOrigin: null,
    spanPresent: false,
    witness: false,
  };
}

function snapshotValue(value, fallbackKind) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return blankSnapshot(fallbackKind);
  if (hasAccessor(value, new Set(), 0)) return blankSnapshot(fallbackKind);
  const marker = readOwn(value, "vantio_run_log");
  return marker.value === "1" ? snapshotNode(value) : snapshotBare(value);
}

function snapshotText(text) {
  try {
    return snapshotValue(JSON.parse(text), "text");
  } catch {
    return blankSnapshot("text");
  }
}

function snapshotBytes(buffer) {
  let text;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(buffer);
  } catch {
    return blankSnapshot("bytes");
  }
  try {
    return snapshotValue(JSON.parse(text), "bytes");
  } catch {
    return blankSnapshot("bytes");
  }
}

function deleteKey(record, key) {
  if (record && hasOwn(record, key)) delete record[key];
}

function scrubRecord(record) {
  if (!record || typeof record !== "object") return;
  const keys = Object.keys(record);
  for (let i = 0; i < keys.length; i += 1) {
    const key = keys[i];
    if (ALIAS_KEYS.has(key) || PROHIBITED_KEYS.has(key)) delete record[key];
  }
}

function refuseSuccess(record, context, result) {
  if (!record || record.optics_status !== "SUCCESS") return;
  record.optics_status = "UNAVAILABLE";
  result.optimistic_default_forbidden = true;
  note(result, "legacy or explicit optics SUCCESS is refused on the detached copy");
  if (context && context.opticsForbidden) return;
  result.optimistic_default_forbidden = true;
}

function projectEvent(record, context, result) {
  if (!record) return null;
  scrubRecord(record);
  if (record.schema_version !== boundary.SCHEMA_VERSION) record.schema_version = boundary.SCHEMA_VERSION;
  if (context.methodAction === "omit") {
    deleteKey(record, "method");
    note(result, "invalid method omitted");
  }
  if (context.samplingAction === "omit") {
    deleteKey(record, "sampling");
    note(result, "invalid sampling omitted");
  }
  if (context.failureNone || record.failure_kind === "none") {
    deleteKey(record, "failure_kind");
    note(result, "failure_kind none omitted");
  }
  if (context.preCompletion) {
    deleteKey(record, "duration_ms");
    record.lifecycle = "INTERRUPTED";
    note(result, "pre-completion duration omitted");
  }
  if (context.opticsForbidden || record.optics_status === "SUCCESS") {
    if (record.optics_status === "SUCCESS" || context.opticsForbidden) {
      record.optics_status = "UNAVAILABLE";
      result.optimistic_default_forbidden = true;
      note(result, context.opticsPresent && context.opticsForbidden
        ? "optics token refused"
        : "legacy or explicit optics SUCCESS is refused on the detached copy");
    }
  } else {
    refuseSuccess(record, context, result);
  }
  if (!hasOwn(record, "application_status") && !hasOwn(record, "http_status")) {
    if ((record.failure_kind && record.failure_kind !== "none") || record.lifecycle === "INTERRUPTED") {
      record.application_status = "UNAVAILABLE";
    }
  }
  deleteKey(record, "optics_trace_witness");
  return record;
}

function projectEnvelope(record, snapshot, result) {
  if (!record) return null;
  scrubRecord(record);
  if (record.schema_version !== boundary.SCHEMA_VERSION) record.schema_version = boundary.SCHEMA_VERSION;
  if (!snapshot.spanPresent) {
    if (record.span_id == null) deleteKey(record, "span_id");
    if (record.parent_span_id == null) deleteKey(record, "parent_span_id");
    note(result, "omitted span stays omitted");
  }
  if (snapshot.mediationJoined || (typeof record.mediation === "string" && record.mediation.includes(","))) {
    deleteKey(record, "mediation");
    note(result, "comma-joined mediation omitted");
  }
  if (record.mediation === "unknown" && snapshot.mediationJoined) deleteKey(record, "mediation");
  if (snapshot.legacyTrace && !snapshot.witness) {
    record.trace_id_basis = "ASSERTED_CONTEXT";
    if (record.trace_id == null || typeof record.trace_id === "string") deleteKey(record, "trace_id");
    note(result, "inherited trace basis is ASSERTED_CONTEXT");
  }
  if (snapshot.origin === "IMPORTED") {
    record.evidence_origin = "IMPORTED";
    if (boundary.ORIGINAL_ORIGINS.has(snapshot.originalOrigin)) {
      record.original_evidence_origin = snapshot.originalOrigin;
    }
    result.reader_origin_label = "IMPORTED";
    note(result, "IMPORTED origin preserved");
  } else if (snapshot.origin === "LOCAL_OBSERVATION" && record.evidence_origin === "LOCAL_OBSERVATION" && result.reader_origin_label === "LEGACY_UNMARKED") {
    deleteKey(record, "evidence_origin");
  }
  if (snapshot.generatedAt && hasOwn(record, "ended_at")) {
    note(result, "ended_at is file write time taken from generated_at");
  }
  deleteKey(record, "optics_trace_witness");
  if (record.trace_id_basis == null) deleteKey(record, "trace_id_basis");
  if (record.trace_id == null && !snapshot.witness) deleteKey(record, "trace_id");
  return record;
}

function mixedLifecycle(envelope, events) {
  if (!envelope) return;
  const statuses = new Set();
  for (let i = 0; i < events.length; i += 1) {
    const status = events[i] && events[i].application_status;
    if (status === "SUCCESS" || status === "APPLICATION_ERROR") statuses.add(status);
  }
  if (statuses.size > 1) envelope.lifecycle = "PARTIAL";
}

function opticsHealth(snapshot, mapper, envelope, events) {
  const reason = mapper && mapper.reason_code;
  if (!envelope && events.length === 0) {
    if (reason === "MALFORMED_JSON" || reason === "MALFORMED_UTF8" || reason === "INPUT_BOUND"
      || reason === "VALIDATOR_FAULT" || reason === "HOSTILE_INPUT" || reason === "ACCESSOR_PROPERTY_FORBIDDEN"
      || reason === "PROMPT_COMPLETION_EXCLUDED" || reason === "PROHIBITED_FIELD_NAME"
      || reason === "CYCLE_REJECTED" || reason === "EXCESSIVE_NESTING") {
      return "OPTICS_ERROR";
    }
    return "UNAVAILABLE";
  }
  const contexts = snapshot.callContexts || [];
  if (snapshot.callsExplicit && contexts.length === 0 && events.length === 0 && envelope) {
    return "NOT_OBSERVED";
  }
  for (let i = 0; i < events.length; i += 1) {
    if (events[i] && events[i].optics_status) return events[i].optics_status;
  }
  if (envelope && envelope.optics_status) return envelope.optics_status;
  return "UNAVAILABLE";
}

function takeNames(list) {
  if (!Array.isArray(list)) return [];
  const names = [];
  for (let i = 0; i < list.length; i += 1) {
    if (typeof list[i] === "string" && boundary.SAFE_NAME.test(list[i])) names.push(list[i]);
  }
  return names;
}

function applyMapper(mapper, snapshot) {
  const result = shell();
  result.adapter_disposition = "READ";
  result.reason_code = mapper.reason_code || null;
  result.reader_origin_label = mapper.reader_origin_label || null;
  result.application_result = hasOwn(mapper, "application_result") ? mapper.application_result : null;
  result.compatibility = {
    legacy_marker: Boolean(mapper.compatibility && mapper.compatibility.legacy_marker),
    legacy_schema_version: mapper.compatibility ? mapper.compatibility.legacy_schema_version : null,
    live_writer_modified: Boolean(mapper.compatibility && mapper.compatibility.live_writer_modified),
    source_shape: mapper.compatibility && mapper.compatibility.source_shape ? mapper.compatibility.source_shape : "unknown",
  };
  result.live_writer_modified = result.compatibility.live_writer_modified;
  const profile = mapper.diagnostics && mapper.diagnostics.unicode_profile_id;
  if (profile === boundary.UNICODE_PROFILE_ID) {
    result.diagnostics.unicode_profile_id = profile;
    result.diagnostics.unicode_profile_version = boundary.UNICODE_PROFILE_VERSION;
  }
  result.diagnostics.issue_location = allowIssue(mapper.issue_location);
  result.diagnostics.stripped_names = takeNames(mapper.fields && mapper.fields.stripped);

  const contexts = snapshot.callContexts || [];
  let envelope = null;
  const events = [];
  if (mapper.record && mapper.record.record_type === "run_envelope") {
    envelope = projectEnvelope(cloneJson(mapper.record), snapshot, result);
  } else if (mapper.record && mapper.record.record_type === "observation_event") {
    const projected = projectEvent(cloneJson(mapper.record), contexts[0] || emptyContext(), result);
    result.record = projected;
    result.events = [];
    result.record_emitted = projected != null;
    result.optics_health = opticsHealth(snapshot, mapper, null, projected ? [projected] : []);
    if (result.optimistic_default_forbidden === false && contexts[0] && contexts[0].opticsForbidden) {
      result.optimistic_default_forbidden = true;
      note(result, "optics token refused");
    }
    return result;
  }

  const mapperEvents = Array.isArray(mapper.events) ? mapper.events : [];
  const projectedEvents = [];
  for (let i = 0; i < mapperEvents.length; i += 1) {
    const child = mapperEvents[i];
    if (!child || !child.record) continue;
    const record = projectEvent(cloneJson(child.record), contexts[i] || emptyContext(), result);
    if (!record) continue;
    events.push(record);
    projectedEvents.push({
      reader_origin_label: child.reader_origin_label || null,
      reason_code: child.reason_code || null,
      record,
      record_emitted: true,
    });
  }
  if (envelope && events.length > 1) mixedLifecycle(envelope, events);
  if (contexts.some((context) => context.opticsForbidden)) {
    result.optimistic_default_forbidden = true;
    note(result, "optics token refused");
  }
  result.record = envelope;
  result.events = projectedEvents;
  result.record_emitted = Boolean(envelope) || events.length > 0;
  result.optics_health = opticsHealth(snapshot, mapper, envelope, events);
  if (snapshot.kind === "node" && snapshot.callsExplicit && contexts.length === 0 && events.length === 0 && envelope) {
    result.optics_health = "NOT_OBSERVED";
  }
  return result;
}

function finishUnread(kind, reason, optics) {
  const result = shell();
  result.adapter_disposition = kind;
  result.reason_code = reason;
  result.optics_health = optics;
  result.diagnostics.issue_location = optics === "OPTICS_ERROR" ? "OPTICS" : null;
  result.record_emitted = false;
  return result;
}

function adaptPrepared(prepared, options) {
  if (prepared.kind === "absent") return finishUnread("ABSENT_FILE", "ABSENT_FILE", "UNAVAILABLE");
  if (prepared.kind === "unreadable") return finishUnread("UNREADABLE", "UNREADABLE", "OPTICS_ERROR");
  if (prepared.kind === "unsupported") {
    const result = finishUnread("UNSUPPORTED", "UNSUPPORTED", "UNAVAILABLE");
    result.diagnostics.fields_not_promoted = prepared.names || [];
    return result;
  }
  if (prepared.kind === "path") return finishUnread("PATH_REFUSED", "PATH_REFUSED", "OPTICS_ERROR");
  if (prepared.kind === "writer") return finishUnread("WRITER_INACTIVE", "WRITER_INACTIVE", "OPTICS_ERROR");

  const applicationResult = options && hasOwn(options, "applicationResult") ? options.applicationResult : undefined;
  const mapperOptions = applicationResult === undefined ? undefined : { applicationResult };
  let mapper;
  if (prepared.kind === "text") mapper = validateEvidence(prepared.text, mapperOptions);
  else if (prepared.kind === "bytes") mapper = validateBytes(prepared.buffer, mapperOptions);
  else mapper = validateEvidence(prepared.value, mapperOptions);
  const snapshot = prepared.snapshot || blankSnapshot(prepared.kind);
  const result = applyMapper(mapper, snapshot);
  if (result.optics_health === "NOT_OBSERVED" && snapshot.kind === "text") result.optics_health = "OPTICS_ERROR";
  if (mapper.reason_code === "MALFORMED_JSON" || mapper.reason_code === "MALFORMED_UTF8") {
    result.optics_health = "OPTICS_ERROR";
    result.record = null;
    result.events = [];
    result.record_emitted = false;
    result.diagnostics.issue_location = "OPTICS";
  }
  if (result.record && result.record.record_type === "run_envelope" && result.events.length === 0
    && (result.optics_health === "NOT_OBSERVED" || result.optics_health === "UNAVAILABLE")) {
    result.record.optics_status = result.optics_health;
  }
  return result;
}

function writerRequested(options) {
  if (!options || typeof options !== "object") return false;
  return options.activate === true || options.write === true || options.emit === true || typeof options.path === "string";
}

function pathLike(text) {
  const trimmed = text.trimStart();
  if (trimmed.startsWith("{") || trimmed.startsWith("[")) return false;
  return true;
}

function adaptNodeCopy(input, options) {
  if (writerRequested(options)) return adaptPrepared({ kind: "writer" }, options);
  if (typeof input === "string") {
    if (pathLike(input)) return adaptPrepared({ kind: "path" }, options);
    return adaptPrepared({ kind: "text", text: input, snapshot: snapshotText(input) }, options);
  }
  if (Buffer.isBuffer(input)) {
    return adaptPrepared({ kind: "bytes", buffer: input, snapshot: snapshotBytes(input) }, options);
  }
  if (input == null || typeof input !== "object" || Array.isArray(input)) {
    return adaptPrepared({ kind: "text", text: input, snapshot: blankSnapshot("text") }, options);
  }
  if (hasAccessor(input, new Set(), 0)) {
    return adaptPrepared({ kind: "node", snapshot: blankSnapshot("node"), value: input }, options);
  }
  const marker = readOwn(input, "vantio_run_log");
  const snapshot = marker.value === "1" ? snapshotNode(input) : snapshotBare(input);
  return adaptPrepared({ kind: "node", snapshot, value: input }, options);
}

function safeNames(extra) {
  if (!extra || typeof extra !== "object") return [];
  const names = [];
  const keys = Object.keys(extra);
  for (let i = 0; i < keys.length; i += 1) {
    if (boundary.SAFE_NAME.test(keys[i])) names.push(keys[i]);
  }
  return names;
}

function versionToken(fixture) {
  const version = fixture && fixture.producer ? fixture.producer.version : null;
  return typeof version === "string" && boundary.SAFE_VERSION.test(version) ? version : null;
}

function assembleFixture(fixture) {
  if (!fixture || typeof fixture !== "object") return { kind: "unsupported", names: [] };
  if (fixture.input_parse === "MALFORMED_JSON") {
    const text = typeof fixture.raw_input_note === "string" && fixture.raw_input_note.length > 0
      ? fixture.raw_input_note
      : "{";
    return { kind: "text", text, snapshot: { kind: "text", callContexts: [], callsExplicit: false } };
  }
  if (fixture.input_parse === "ABSENT_FILE") return { kind: "absent" };
  if (fixture.input_parse === "UNREADABLE") return { kind: "unreadable" };
  const record = fixture.input_record;
  if (!record || typeof record !== "object") return { kind: "unsupported", names: [] };
  const envelope = record.envelope && typeof record.envelope === "object" ? cloneJson(record.envelope) : null;
  const call = record.call && typeof record.call === "object" ? cloneJson(record.call) : null;
  if (!envelope && !call) return { kind: "unsupported", names: safeNames(record.extra) };

  if (envelope && !call && envelope.optics_trace_witness === boundary.WITNESS_VALUE && typeof envelope.trace_id === "string" && typeof envelope.run_id === "string") {
    const version = typeof envelope.cli_or_sdk_version === "string" ? envelope.cli_or_sdk_version : versionToken(fixture);
    const value = {
      optics_trace_witness: boundary.WITNESS_VALUE,
      producer: envelope.producer,
      record_type: "run_envelope",
      run_id: envelope.run_id,
      trace_id: envelope.trace_id,
      trace_id_basis: "OPTICS_GENERATED",
    };
    if (version && boundary.SAFE_VERSION.test(version)) value.cli_or_sdk_version = version;
    return {
      kind: "contract",
      snapshot: {
        callContexts: [],
        callsExplicit: false,
        generatedAt: false,
        kind: "contract",
        legacyTrace: false,
        mediationJoined: false,
        origin: null,
        originalOrigin: null,
        spanPresent: false,
        witness: true,
      },
      value,
    };
  }

  const copy = envelope ? cloneJson(envelope) : {};
  if (copy.vantio_run_log !== "1") copy.vantio_run_log = "1";
  if (typeof copy.ts === "string" && typeof copy.started_at !== "string") {
    copy.started_at = copy.ts;
    delete copy.ts;
  }
  const hadCalls = Array.isArray(copy.calls);
  if (call && !hadCalls) copy.calls = [call];
  else if (!hadCalls) copy.calls = [];
  const snapshot = snapshotNode(copy);
  snapshot.callsExplicit = hadCalls || Boolean(call);
  if (!hadCalls && !call) snapshot.callContexts = [];
  return { kind: "node", snapshot, value: copy };
}

function adaptFixture(fixture, options) {
  return adaptPrepared(assembleFixture(fixture), options);
}

module.exports = {
  adaptFixture,
  adaptNodeCopy,
};
