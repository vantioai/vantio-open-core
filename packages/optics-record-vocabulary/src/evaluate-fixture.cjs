"use strict";

const boundary = require("./boundary.cjs");
const { canonicalJson } = require("./canonical-json.cjs");
const { comparisonDocument } = require("./comparison.cjs");
const { FIXTURE_KEYS } = require("./fixture-contract.cjs");

const PRODUCER_KEYS = Object.freeze(["identity", "package_name", "surface", "version"]);
const INPUT_KEYS = Object.freeze(["call", "envelope", "extra"]);
const SURFACES = new Set(["cli_0_3_24", "python_3_1_0", "node_sdk_0_2_4", "reader", "future_not_shipped"]);
const PARSES = new Set(["OK", "MALFORMED_JSON", "ABSENT_FILE", "UNREADABLE"]);
const VERSIONS = new Set(["0.3.24", "3.1.0", "0.2.4", boundary.FUTURE_VERSION_PLACEHOLDER, null]);
const ORIGIN_LABELS = new Set([
  null,
  "LEGACY_UNMARKED",
  "SIMULATED_DEMO",
  "IMPORTED",
  "TEST_FIXTURE",
  "PRODUCT_HEALTH",
  "DERIVED_DIAGNOSTIC",
]);
const TRANSPORT = new Set(["dns", "connection", "tls", "timeout"]);
const FROZEN_SURFACES = new Set(["cli_0_3_24", "python_3_1_0", "node_sdk_0_2_4"]);
const FORBIDDEN_EXPECTED_KEYS = new Set([
  "ok",
  "plane",
  "prompt",
  "prompts",
  "cost",
  "usage",
  "token_count",
  "workflow",
  "machine",
  "opticsStatus",
  "applicationStatus",
  "hostname",
  "bytes",
  "pid",
  "ppid",
  "traceId",
  "vantio_run_log",
  "free_mode",
  "residual",
  "data_note",
  "est_spend_usd",
  "optics_trace_witness",
  "freshness",
  "widget_hint",
  "anonymousId",
  "status_labels",
]);

function sameStringList(left, right) {
  if (!Array.isArray(left) || left.length !== right.length) return false;
  for (let i = 0; i < left.length; i += 1) if (left[i] !== right[i]) return false;
  return true;
}

function plainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function exactKeys(value, expected) {
  const keys = Object.keys(value).sort();
  const want = expected.slice().sort();
  return sameStringList(keys, want);
}

function enumValues(vocabulary, recordType, name) {
  const row = vocabulary.canonical_rows.find((candidate) => candidate.record_type === recordType && candidate.canonical_name === name);
  return row && row.allowed_enum_values ? row.allowed_enum_values : null;
}

function workloadForHttp(status) {
  if (typeof status !== "number") return null;
  if (status >= 200 && status <= 399) return "SUCCESS";
  if (status >= 400 && status <= 599) return "APPLICATION_ERROR";
  return "UNAVAILABLE";
}

function collectObjects(fixture) {
  const objects = [];
  if (plainObject(fixture.expected_canonical)) objects.push(fixture.expected_canonical);
  if (Array.isArray(fixture.expected_events)) {
    for (const event of fixture.expected_events) if (plainObject(event)) objects.push(event);
  }
  return objects;
}

function valuesFor(fixture, path) {
  const values = [];
  if (path === "evidence_origin") values.push(fixture.evidence_origin);
  else if (path.startsWith("reading.")) values.push(fixture.semantic_dimension_readings[path.slice("reading.".length)]);
  else if (path.startsWith("canonical.")) {
    const key = path.slice("canonical.".length);
    values.push(fixture.expected_canonical ? fixture.expected_canonical[key] : undefined);
  } else {
    for (const object of collectObjects(fixture)) values.push(object[path]);
    if (fixture.semantic_dimension_readings && Object.prototype.hasOwnProperty.call(fixture.semantic_dimension_readings, path)) {
      values.push(fixture.semantic_dimension_readings[path]);
    }
  }
  return values;
}

function callOf(fixture) {
  return fixture.input_record && fixture.input_record.call;
}

function envelopeOf(fixture) {
  return fixture.input_record && fixture.input_record.envelope;
}

function extraOf(fixture) {
  return fixture.input_record && fixture.input_record.extra;
}

function knownCanonicalNames(vocabulary) {
  return new Set(vocabulary.canonical_rows.map((row) => row.canonical_name));
}

function knownAliases(vocabulary) {
  const names = new Set();
  for (const row of vocabulary.canonical_rows) {
    for (const alias of row.compatibility_aliases) names.add(alias);
  }
  for (const row of vocabulary.compatibility_rows) names.add(row.live_name);
  return names;
}

const RULES = {
  missing_optics_status(fixture, errors) {
    const call = callOf(fixture);
    if (!plainObject(call)) errors.push("missing_optics_status needs a call");
    else if ("optics_status" in call || "opticsStatus" in call) errors.push("optics status was present");
    if (!fixture.expected_canonical || fixture.expected_canonical.optics_status !== "UNAVAILABLE") {
      errors.push("missing optics_status must be UNAVAILABLE");
    }
    if (fixture.semantic_dimension_readings.optics_health !== "UNAVAILABLE") errors.push("optics health reading");
  },
  missing_action(fixture, errors) {
    const call = callOf(fixture);
    if (!plainObject(call) || "action" in call) errors.push("action was present");
    for (const object of collectObjects(fixture)) {
      if (object && "action" in object) errors.push("action was stored");
    }
  },
  missing_http_status(fixture, errors) {
    const call = callOf(fixture);
    if (!plainObject(call)) errors.push("missing_http_status needs a call");
    else if ("status" in call || "http_status" in call || "httpStatus" in call) errors.push("http status key was present");
    for (const object of collectObjects(fixture)) {
      if ("http_status" in object) errors.push("http_status was stored");
    }
  },
  null_http_status_is_absent(fixture, errors) {
    const call = callOf(fixture);
    if (!plainObject(call) || call.status !== null) errors.push("null http status input");
    for (const object of collectObjects(fixture)) {
      if ("http_status" in object) errors.push("null http status was stored as a code");
    }
  },
  missing_byte_count(fixture, errors) {
    const call = callOf(fixture);
    if (!plainObject(call)) errors.push("missing_byte_count needs a call");
    else if ("bytes" in call || "response_bytes" in call) errors.push("byte key was present");
    for (const object of collectObjects(fixture)) {
      if ("response_bytes" in object) errors.push("missing bytes were stored");
    }
  },
  legacy_bytes_zero(fixture, errors) {
    const call = callOf(fixture);
    if (!plainObject(call) || call.bytes !== 0 || "response_bytes" in call) errors.push("legacy bytes zero input");
    if (!fixture.expected_canonical || fixture.expected_canonical.response_bytes !== null) {
      errors.push("legacy bytes zero must be null");
    }
  },
  explicit_response_bytes_zero(fixture, errors) {
    const call = callOf(fixture);
    if (!plainObject(call) || call.response_bytes !== 0 || "bytes" in call) errors.push("explicit zero input");
    if (!fixture.expected_canonical || fixture.expected_canonical.response_bytes !== 0) {
      errors.push("explicit response_bytes zero must stay zero");
    }
  },
  missing_evidence_origin(fixture, errors) {
    const envelope = envelopeOf(fixture);
    const call = callOf(fixture);
    if (envelope && "evidence_origin" in envelope) errors.push("envelope origin present");
    if (call && "evidence_origin" in call) errors.push("call origin present");
    if (fixture.evidence_origin !== "LEGACY_UNMARKED") errors.push("missing origin reader label");
    for (const object of collectObjects(fixture)) {
      if ("evidence_origin" in object) errors.push("missing origin was stored");
    }
  },
  inherited_trace(fixture, errors) {
    const envelope = envelopeOf(fixture);
    if (!plainObject(envelope) || typeof envelope.trace_id !== "string" || "optics_trace_witness" in envelope) {
      errors.push("inherited trace input");
    }
    const expected = fixture.expected_canonical;
    if (!expected || expected.run_id !== envelope.trace_id || "trace_id" in expected) errors.push("inherited trace mapping");
    if (expected.trace_id_basis !== "ASSERTED_CONTEXT") errors.push("inherited basis");
    if (fixture.semantic_dimension_readings.evidence_origin_basis === "OPTICS_GENERATED") errors.push("inherited basis reading");
  },
  unknown_status(fixture, errors, vocabulary) {
    const call = callOf(fixture);
    const allowed = enumValues(vocabulary, "observation_event", "optics_status");
    const raw = call && (call.opticsStatus || call.optics_status);
    if (!raw || allowed.includes(raw)) errors.push("unknown status input");
    if (!fixture.expected_canonical || fixture.expected_canonical.optics_status !== "UNAVAILABLE") errors.push("unknown status result");
    const text = fixture.diagnostic_limitations.join(" ");
    if (!text.includes("OPTIMISTIC_DEFAULT_FORBIDDEN") || !text.includes(raw)) errors.push("unknown status diagnostic");
  },
  unknown_enum(fixture, errors, vocabulary) {
    const call = callOf(fixture);
    const allowed = enumValues(vocabulary, "observation_event", "method");
    if (!call || allowed.includes(call.method)) errors.push("unknown enum input");
    for (const object of collectObjects(fixture)) {
      if ("method" in object) errors.push("unknown enum stored");
    }
    if (!fixture.fields_not_promoted.includes("method")) errors.push("unknown enum promotion");
    if (!fixture.diagnostic_limitations.join(" ").includes(call.method)) errors.push("unknown enum not preserved in diagnostic");
  },
  unreadable_record(fixture, errors) {
    if (fixture.input_parse !== "UNREADABLE" || fixture.record_emitted !== false || fixture.expected_canonical !== null) {
      errors.push("unreadable shape");
    }
    if (fixture.semantic_dimension_readings.optics_health !== "OPTICS_ERROR") errors.push("unreadable optics");
    if (fixture.semantic_dimension_readings.optics_health === "NOT_OBSERVED") errors.push("unreadable as NOT_OBSERVED");
  },
  corrupt_record(fixture, errors) {
    if (fixture.input_parse !== "MALFORMED_JSON" || fixture.record_emitted !== false || fixture.expected_canonical !== null) {
      errors.push("corrupt shape");
    }
    if (fixture.expected_canonical && Object.keys(fixture.expected_canonical).length === 0) errors.push("empty valid record");
    let parsed = false;
    try {
      JSON.parse(fixture.raw_input_note);
      parsed = true;
    } catch (_error) {
      parsed = false;
    }
    if (parsed || !fixture.raw_input_note) errors.push("corrupt note was valid json");
    if (fixture.semantic_dimension_readings.optics_health !== "OPTICS_ERROR") errors.push("corrupt optics");
    if (fixture.semantic_dimension_readings.issue_location !== "OPTICS") errors.push("corrupt issue location");
    if (!fixture.diagnostic_limitations.join(" ").includes("empty valid record")) errors.push("corrupt diagnostic");
  },
  absent_file(fixture, errors) {
    if (fixture.input_parse !== "ABSENT_FILE" || fixture.record_emitted !== false || fixture.expected_canonical !== null) {
      errors.push("absent file shape");
    }
    if (fixture.semantic_dimension_readings.optics_health !== "UNAVAILABLE") errors.push("absent file optics");
    if (fixture.semantic_dimension_readings.optics_health === "NOT_OBSERVED") errors.push("absent file as NOT_OBSERVED");
  },
  empty_shield(fixture, errors) {
    if (fixture.producer.version !== "3.1.0" || fixture.producer.surface !== "python_3_1_0") errors.push("empty shield producer");
    if (!fixture.diagnostic_limitations.join(" ").includes("empty shield")) errors.push("empty shield diagnostic");
  },
  empty_cli_file(fixture, errors) {
    const envelope = envelopeOf(fixture);
    if (!envelope || !Array.isArray(envelope.calls) || envelope.calls.length !== 0) errors.push("empty cli input");
    if (!fixture.expected_canonical || fixture.expected_canonical.optics_status !== "NOT_OBSERVED") errors.push("empty cli optics");
    if (fixture.expected_canonical.call_count !== 0) errors.push("empty cli call_count");
    if (fixture.expected_canonical.optics_status === "SUCCESS") errors.push("empty cli success");
    if (!fixture.diagnostic_limitations.join(" ").includes("file exists")) errors.push("empty cli diagnostic");
  },
  status_dimensions_separated(fixture, errors) {
    const readings = fixture.semantic_dimension_readings;
    const present = boundary.SEPARATED_DIMENSIONS.filter((dimension) => Object.prototype.hasOwnProperty.call(readings, dimension));
    if (present.length < 2) errors.push("separated readings");
    if (readings.optics_health === "SUCCESS") errors.push("optics health SUCCESS reading");
    if (readings.workload_outcome === "PARTIAL") errors.push("workload PARTIAL reading");
    if (readings.attempt_lifecycle === "PARTIAL" && readings.workload_outcome === "PARTIAL") errors.push("lifecycle collapse");
    for (const object of collectObjects(fixture)) {
      if (object.application_status === "PARTIAL") errors.push("application_status PARTIAL");
      if (object.optics_status === "SUCCESS") errors.push("optics_status SUCCESS");
      if ("lifecycle" in object && object.lifecycle === object.optics_status) errors.push("lifecycle equals optics");
      if ("lifecycle" in object && object.lifecycle === object.application_status) errors.push("lifecycle equals application");
    }
  },
  alias_canonical_names_only(fixture, errors) {
    if (fixture.aliases_used.length < 3) errors.push("alias fixture is thin");
    for (const object of collectObjects(fixture)) {
      for (const alias of fixture.aliases_used) {
        if (Object.prototype.hasOwnProperty.call(object, alias)) errors.push("alias stored " + alias);
      }
    }
  },
  provider_http_error(fixture, errors) {
    const call = callOf(fixture);
    const expected = fixture.expected_canonical;
    if (!call || call.status !== 500) errors.push("provider http input");
    if (!expected || expected.http_status !== 500 || expected.application_status !== "APPLICATION_ERROR") errors.push("provider http canonical");
    if (expected.optics_status === "SUCCESS" || expected.issue_location !== "PROVIDER_INTERACTION") errors.push("provider http dimensions");
    if ("ok" in expected) errors.push("ok stored");
  },
  transport_failure(fixture, errors) {
    const call = callOf(fixture);
    const expected = fixture.expected_canonical;
    if (!call || !TRANSPORT.has(call.failure_kind) || "status" in call) errors.push("transport input");
    if (!expected || expected.failure_kind !== call.failure_kind) errors.push("transport kind");
    if (expected.failure_kind === "network_error" || "http_status" in expected) errors.push("transport http");
    if (expected.issue_location !== "NETWORK" || expected.application_status !== "UNAVAILABLE") errors.push("transport outcome");
    if (expected.optics_status !== "UNAVAILABLE") errors.push("transport optics");
    if (call.error === "network_error" && ("error" in expected || expected.failure_kind === "network_error")) {
      errors.push("network_error string stored");
    }
  },
  customer_exception(fixture, errors) {
    const call = callOf(fixture);
    const expected = fixture.expected_canonical;
    if (!call || call.failure_kind !== "wrapped" || "status" in call) errors.push("customer exception input");
    if (!/^[A-Za-z0-9_]{1,64}$/.test(call.error_class || "")) errors.push("error_class token");
    if (!expected || expected.failure_kind !== "wrapped" || expected.error_class !== call.error_class) errors.push("customer canonical");
    if (expected.issue_location !== "CUSTOMER_APPLICATION" || expected.application_status === "SUCCESS") errors.push("customer dimensions");
  },
  partial_run(fixture, errors) {
    const expected = fixture.expected_canonical;
    const extra = extraOf(fixture);
    if (!extra || extra.summary_applicationStatus !== "PARTIAL") errors.push("partial live rollup");
    if (!expected || expected.lifecycle !== "PARTIAL") errors.push("partial lifecycle");
    if (!Array.isArray(fixture.expected_events) || fixture.expected_events.length < 2) errors.push("partial events");
    const tokens = fixture.expected_events.map((event) => event.application_status);
    if (new Set(tokens).size < 2) errors.push("partial tokens");
    if (tokens.includes("PARTIAL")) errors.push("application PARTIAL stored");
  },
  interrupted_run(fixture, errors) {
    if (!fixture.expected_canonical || fixture.expected_canonical.lifecycle !== "INTERRUPTED") errors.push("interrupted lifecycle");
    if (fixture.expected_canonical.optics_status === "SUCCESS") errors.push("interrupted success");
    if (fixture.semantic_dimension_readings.attempt_lifecycle !== "INTERRUPTED") errors.push("interrupted reading");
  },
  ambiguous_duration_zero(fixture, errors) {
    const call = callOf(fixture);
    if (!call || call.duration_ms !== 0) errors.push("duration zero input");
    if (!fixture.expected_canonical || "duration_ms" in fixture.expected_canonical) errors.push("pre-completion duration stored");
    if (!fixture.diagnostic_limitations.join(" ").includes("not a measured zero")) errors.push("duration diagnostic");
  },
  imported_evidence(fixture, errors) {
    const envelope = envelopeOf(fixture);
    const expected = fixture.expected_canonical;
    if (!envelope || envelope.evidence_origin !== "IMPORTED") errors.push("import input");
    if (fixture.evidence_origin !== "IMPORTED" || fixture.compatibility_classification !== "READ_ONLY") errors.push("import label");
    if (!expected || expected.evidence_origin !== "IMPORTED" || expected.original_evidence_origin !== envelope.original_evidence_origin) {
      errors.push("import canonical");
    }
    if (expected.evidence_origin === "LOCAL_OBSERVATION") errors.push("import upgraded");
  },
  simulated_evidence(fixture, errors, vocabulary) {
    const call = callOf(fixture);
    if (!call || call.hostname !== vocabulary.demo_host) errors.push("demo host");
    if (fixture.evidence_origin !== "SIMULATED_DEMO") errors.push("demo label");
    if (!fixture.expected_canonical || fixture.expected_canonical.evidence_origin !== "SIMULATED_DEMO") errors.push("demo canonical");
    if (fixture.expected_canonical.evidence_origin === "LOCAL_OBSERVATION") errors.push("demo upgraded");
  },
  node_sdk_not_local_record(fixture, errors) {
    const extra = extraOf(fixture);
    if (fixture.producer.surface !== "node_sdk_0_2_4" || fixture.record_emitted !== false || fixture.expected_canonical !== null) {
      errors.push("node sdk shape");
    }
    if (fixture.expected_unsupported_state !== "UNSUPPORTED" || fixture.compatibility_classification !== "UNSUPPORTED") {
      errors.push("node sdk unsupported");
    }
    if (!extra || typeof extra.eventPayload.timestamp_ns_decimal !== "string") errors.push("timestamp_ns representation");
    if (!fixture.diagnostic_limitations.join(" ").toLowerCase().includes("local run log")) errors.push("node sdk diagnostic");
  },
  future_field(fixture, errors, vocabulary) {
    const extra = extraOf(fixture);
    if (!extra || extra.freshness !== "CURRENT" || !("widget_hint" in extra) || !("cost" in extra)) errors.push("future field input");
    for (const name of ["freshness", "widget_hint", "cost"]) {
      if (!fixture.fields_not_promoted.includes(name)) errors.push("promoted " + name);
    }
    if (fixture.record_emitted !== false || fixture.expected_canonical !== null) errors.push("future field record");
    if (fixture.compatibility_classification !== "REJECT_WITH_EXPLANATION") errors.push("future field class");
    if (!vocabulary.prohibited_names_declared.includes("cost")) errors.push("cost not declared prohibited");
  },
  sampling_not_success(fixture, errors, vocabulary) {
    const call = callOf(fixture);
    const allowed = enumValues(vocabulary, "observation_event", "sampling");
    if (!call || allowed.includes(call.sampling)) errors.push("sampling input");
    if (!fixture.expected_canonical || fixture.expected_canonical.sampling !== "UNSAMPLED") errors.push("sampling canonical");
    if (fixture.expected_canonical.optics_status === "SUCCESS") errors.push("sampling success");
  },
  claimed_local_without_provenance(fixture, errors) {
    const envelope = envelopeOf(fixture);
    if (!envelope || envelope.evidence_origin !== "LOCAL_OBSERVATION" || "producer" in envelope) errors.push("claimed local input");
    if (fixture.evidence_origin !== "LEGACY_UNMARKED") errors.push("claimed local label");
    if (!fixture.expected_canonical || fixture.expected_canonical.reader_origin_label !== "LEGACY_UNMARKED") errors.push("claimed local canonical");
    if (fixture.expected_canonical.evidence_origin === "LOCAL_OBSERVATION") errors.push("claimed local stored");
    if (!fixture.diagnostic_limitations.join(" ").includes("PROVENANCE_INSUFFICIENT")) errors.push("provenance diagnostic");
  },
  cli_frozen_shape(fixture, errors) {
    const envelope = envelopeOf(fixture);
    if (fixture.producer.version !== "0.3.24" || fixture.producer.surface !== "cli_0_3_24") errors.push("cli producer");
    if (!envelope || envelope.vantio_run_log !== "1" || envelope.schema_version !== 2) errors.push("cli envelope");
    if ("schema_status" in envelope || "record_type" in envelope) errors.push("cli canonical markers");
    if ("ended_at" in (fixture.expected_canonical || {})) errors.push("generated_at stored as ended_at");
  },
  python_frozen_shape(fixture, errors) {
    const envelope = envelopeOf(fixture);
    const call = callOf(fixture);
    if (fixture.producer.version !== "3.1.0" || fixture.producer.surface !== "python_3_1_0") errors.push("python producer");
    if (!envelope || envelope.runtime !== "python" || envelope.schema_status !== boundary.SCHEMA_STATUS) errors.push("python envelope");
    if (!call || call.opticsStatus !== "SUCCESS") errors.push("python live success");
    if (!fixture.expected_canonical || fixture.expected_canonical.optics_status !== "UNAVAILABLE") errors.push("python canonical optics");
    if (call.ts !== "2026-07-01T00:00:00.100000+00:00") errors.push("python ts fixture drifted");
    if (fixture.expected_canonical.started_at !== "2026-07-01T00:00:00.100Z") errors.push("python canonical ts");
    if (!fixture.derived_fields.includes("started_at")) errors.push("python ts derivation");
    if (typeof envelope.mediation === "string" && envelope.mediation.includes(",")) {
      if (!fixture.fields_not_promoted.includes("mediation")) errors.push("joined mediation promoted");
    }
    if (!fixture.diagnostic_limitations.join(" ").includes("OPTIMISTIC_DEFAULT_FORBIDDEN")) errors.push("python success diagnostic");
  },
  successful_http(fixture, errors) {
    const call = callOf(fixture);
    const expected = fixture.expected_canonical;
    if (!call || typeof call.status !== "number" || call.status < 200 || call.status > 399) errors.push("success http input");
    if (!expected || expected.http_status !== call.status || expected.application_status !== "SUCCESS") errors.push("success http canonical");
    if (expected.optics_status === "SUCCESS") errors.push("success http optics");
    if (FROZEN_SURFACES.has(fixture.producer.surface) && expected.optics_status !== "UNAVAILABLE" && expected.optics_status !== "NOT_OBSERVED") {
      errors.push("frozen writer optics default");
    }
  },
  live_success_default_refused(fixture, errors) {
    const call = callOf(fixture);
    if (!call || call.opticsStatus !== "SUCCESS") errors.push("live success input");
    if (!fixture.expected_canonical || fixture.expected_canonical.optics_status !== "UNAVAILABLE") errors.push("live success canonical");
  },
  redirect_3xx(fixture, errors) {
    const call = callOf(fixture);
    if (!call || call.status < 300 || call.status > 399) errors.push("redirect input");
    if (fixture.expected_canonical.application_status !== "SUCCESS" || fixture.expected_canonical.optics_status === "SUCCESS") {
      errors.push("redirect dimensions");
    }
    if (!fixture.diagnostic_limitations.join(" ").includes("hop")) errors.push("redirect hop diagnostic");
  },
  witnessed_trace(fixture, errors, vocabulary) {
    const envelope = envelopeOf(fixture);
    const expected = fixture.expected_canonical;
    if (fixture.producer.surface !== "future_not_shipped" || fixture.producer.version !== boundary.FUTURE_VERSION_PLACEHOLDER) {
      errors.push("witness producer");
    }
    if (!envelope || envelope.optics_trace_witness !== vocabulary.trace_generation_witness.value) errors.push("witness input");
    if (!vocabulary.recognized_producers.includes(envelope.producer)) errors.push("witness producer token");
    if (!expected || expected.trace_id_basis !== "OPTICS_GENERATED" || "optics_trace_witness" in expected) errors.push("witness canonical");
    if (expected.trace_id !== envelope.trace_id || expected.run_id !== envelope.run_id || expected.run_id === expected.trace_id) {
      errors.push("witness identity split");
    }
  },
  explicit_observed_not_default(fixture, errors) {
    const call = callOf(fixture);
    if (fixture.producer.surface !== "future_not_shipped") errors.push("observed producer");
    if (!call || (call.optics_status !== "OBSERVED" && call.opticsStatus !== "OBSERVED")) errors.push("observed input");
    if (!fixture.expected_canonical || fixture.expected_canonical.optics_status !== "OBSERVED") errors.push("observed canonical");
    if (!fixture.diagnostic_limitations.join(" ").includes("not a default")) errors.push("observed diagnostic");
  },
  provider_guess_not_promoted(fixture, errors) {
    const call = callOf(fixture);
    if (!call || typeof call.provider !== "string" || "provider_id" in call) errors.push("provider guess input");
    if (fixture.expected_canonical && "provider_id" in fixture.expected_canonical) errors.push("provider guess stored");
    if (!fixture.diagnostic_limitations.join(" ").includes("not an allowlisted provider_id")) errors.push("provider diagnostic");
  },
};

function checkStructure(fixture, vocabulary, errors) {
  if (!plainObject(fixture)) {
    errors.push("fixture is not an object");
    return;
  }
  if (!exactKeys(fixture, FIXTURE_KEYS)) errors.push("fixture keys");
  if (!sameStringList(fixture.posture, boundary.POSTURE)) errors.push("posture");
  if (fixture.audience !== boundary.AUDIENCE) errors.push("audience");
  if (fixture.achievement !== "NOT_SHIPPED") errors.push("achievement");
  if (fixture.stable_schema !== false) errors.push("stable_schema");
  if (fixture.writes_live_run_directory !== false) errors.push("live run write");
  if (typeof fixture.id !== "string" || !/^[a-z0-9-]+$/.test(fixture.id)) errors.push("id");
  if (fixture.scenario !== fixture.id) errors.push("scenario id");
  if (typeof fixture.title !== "string" || fixture.title.length === 0) errors.push("title");
  if (!PARSES.has(fixture.input_parse)) errors.push("input_parse");
  if (!plainObject(fixture.producer) || !exactKeys(fixture.producer, PRODUCER_KEYS)) errors.push("producer keys");
  else {
    if (!SURFACES.has(fixture.producer.surface)) errors.push("surface");
    if (!VERSIONS.has(fixture.producer.version)) errors.push("version");
    if (typeof fixture.producer.identity !== "string" || typeof fixture.producer.package_name !== "string") errors.push("producer identity");
  }
  if (!boundary.COMPATIBILITY_CLASSES.includes(fixture.compatibility_classification)) errors.push("classification");
  if (fixture.compatibility_classification === "FULL") errors.push("FULL is not a Unit A result");
  if (!ORIGIN_LABELS.has(fixture.evidence_origin)) errors.push("evidence origin label");
  if (fixture.evidence_origin === "LOCAL_OBSERVATION") errors.push("LOCAL_OBSERVATION label");
  if (!Array.isArray(fixture.aliases_used) || !Array.isArray(fixture.derived_fields) || !Array.isArray(fixture.fields_not_promoted)) {
    errors.push("list fields");
  }
  if (!Array.isArray(fixture.diagnostic_limitations) || fixture.diagnostic_limitations.length === 0) errors.push("diagnostics");
  if (!Array.isArray(fixture.rule_ids) || fixture.rule_ids.length === 0) errors.push("rules");
  if (!Array.isArray(fixture.prohibited_optimistic_interpretations) || fixture.prohibited_optimistic_interpretations.length === 0) {
    errors.push("prohibitions");
  }
  if (typeof fixture.raw_input_note !== "string") errors.push("raw note");
  if (typeof fixture.record_emitted !== "boolean") errors.push("record_emitted");
  if (!plainObject(fixture.semantic_dimension_readings)) errors.push("readings");
  const knownDimensions = new Set([...boundary.REQUIRED_DIMENSIONS, ...vocabulary.additional_dimensions]);
  for (const dimension of Object.keys(fixture.semantic_dimension_readings || {})) {
    if (!knownDimensions.has(dimension)) errors.push("unknown reading " + dimension);
  }
  if (fixture.record_emitted) {
    if (!plainObject(fixture.expected_canonical) || Object.keys(fixture.expected_canonical).length === 0) errors.push("empty canonical");
  } else if (fixture.expected_canonical !== null || fixture.expected_events !== null) {
    errors.push("emitted false with canonical");
  }
  if (fixture.expected_events !== null && (!Array.isArray(fixture.expected_events) || fixture.expected_events.length === 0)) {
    errors.push("events");
  }
  if (fixture.input_parse === "OK") {
    if (!plainObject(fixture.input_record) || !exactKeys(fixture.input_record, INPUT_KEYS)) errors.push("input_record keys");
  } else if (fixture.input_record !== null) errors.push("input_record should be null");

  const names = knownCanonicalNames(vocabulary);
  const aliases = knownAliases(vocabulary);
  for (const alias of fixture.aliases_used || []) {
    if (!aliases.has(alias)) errors.push("unknown alias " + alias);
  }
  for (const object of collectObjects(fixture)) {
    for (const key of Object.keys(object)) {
      if (!names.has(key)) errors.push("non-canonical key " + key);
      if (FORBIDDEN_EXPECTED_KEYS.has(key)) errors.push("forbidden key " + key);
    }
    if (object.optics_status === "SUCCESS") errors.push("optics SUCCESS");
    if (object.application_status === "PARTIAL") errors.push("application PARTIAL");
    if (object.evidence_origin === "LOCAL_OBSERVATION") errors.push("stored LOCAL_OBSERVATION");
    if ("http_status" in object && (object.http_status === 0 || object.http_status < 100 || object.http_status > 599)) {
      errors.push("http_status range");
    }
    if ("http_status" in object && "application_status" in object && object.application_status !== workloadForHttp(object.http_status)) {
      errors.push("http workload mismatch");
    }
    const issue = enumValues(vocabulary, "observation_event", "issue_location");
    if ("issue_location" in object && !issue.includes(object.issue_location)) errors.push("issue_location");
    const failure = enumValues(vocabulary, "observation_event", "failure_kind");
    if ("failure_kind" in object && !failure.includes(object.failure_kind)) errors.push("failure_kind");
    const application = enumValues(vocabulary, "observation_event", "application_status");
    if ("application_status" in object && !application.includes(object.application_status)) errors.push("application_status");
    const optics = enumValues(vocabulary, "observation_event", "optics_status");
    if ("optics_status" in object && !optics.includes(object.optics_status)) errors.push("optics_status");
  }
  const readings = plainObject(fixture.semantic_dimension_readings) ? fixture.semantic_dimension_readings : null;
  if (readings && readings.optics_health === "SUCCESS") errors.push("reading optics SUCCESS");
  if (readings && readings.optics_health === "NOT_OBSERVED" && fixture.id !== "cli-empty-call-file") {
    errors.push("NOT_OBSERVED reading");
  }
  const ruleIds = Array.isArray(fixture.rule_ids) ? fixture.rule_ids : [];
  for (const object of collectObjects(fixture)) {
    if (object.optics_status === "NOT_OBSERVED" && fixture.id !== "cli-empty-call-file") errors.push("NOT_OBSERVED stored");
    if (object.trace_id_basis === "OPTICS_GENERATED" && !ruleIds.includes("witnessed_trace")) errors.push("OPTICS_GENERATED");
  }
  if (plainObject(fixture.producer) && FROZEN_SURFACES.has(fixture.producer.surface)) {
    for (const object of collectObjects(fixture)) {
      if (object.optics_status === "OBSERVED") errors.push("frozen surface stored OBSERVED");
    }
  }
  let prohibitsSuccess = false;
  for (const item of fixture.prohibited_optimistic_interpretations || []) {
    if (!plainObject(item) || typeof item.path !== "string" || !("forbidden_value" in item)) errors.push("prohibition shape");
    else if (item.path === "optics_status" && item.forbidden_value === "SUCCESS") prohibitsSuccess = true;
    for (const value of valuesFor(fixture, item.path)) {
      if (value === item.forbidden_value) errors.push("prohibited value present " + item.path);
    }
  }
  if (!prohibitsSuccess) errors.push("missing SUCCESS prohibition");
  const seenRules = new Set();
  for (const ruleId of fixture.rule_ids || []) {
    if (seenRules.has(ruleId)) errors.push("duplicate rule " + ruleId);
    seenRules.add(ruleId);
    if (!Object.prototype.hasOwnProperty.call(RULES, ruleId)) errors.push("unknown rule " + ruleId);
  }
}

function evaluateFixture(fixture, vocabulary) {
  let before;
  try {
    before = canonicalJson(fixture);
  } catch (error) {
    return { ok: false, errors: [error.code || error.message], comparison: null };
  }
  const errors = [];
  try {
    checkStructure(fixture, vocabulary, errors);
    if (errors.length === 0) {
      for (const ruleId of fixture.rule_ids) RULES[ruleId](fixture, errors, vocabulary);
    }
  } catch (error) {
    errors.push(error.code || error.message);
  }
  let after;
  try {
    after = canonicalJson(fixture);
  } catch (error) {
    errors.push(error.code || error.message);
  }
  if (before !== after) errors.push("CALLER_MUTATED");
  return {
    ok: errors.length === 0,
    errors,
    comparison: errors.length === 0 ? comparisonDocument(fixture) : null,
  };
}

function evaluateFixtures(fixtures, vocabulary) {
  const errors = [];
  const comparisons = [];
  const ids = new Set();
  if (!Array.isArray(fixtures)) return { ok: false, errors: ["fixtures are not an array"], comparisons };
  for (const fixture of fixtures) {
    if (fixture && ids.has(fixture.id)) errors.push("duplicate fixture " + fixture.id);
    if (fixture && fixture.id) ids.add(fixture.id);
    const result = evaluateFixture(fixture, vocabulary);
    if (!result.ok) errors.push(fixture && fixture.id ? fixture.id + ": " + result.errors.join("; ") : result.errors.join("; "));
    else comparisons.push(result.comparison);
  }
  return { ok: errors.length === 0, errors, comparisons };
}

module.exports = { RULES, evaluateFixture, evaluateFixtures };
