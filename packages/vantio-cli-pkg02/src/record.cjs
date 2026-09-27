"use strict";

const { validateEvidence } = require("../../optics-evidence-contract/src/validate.cjs");
const privacy = require("../../optics-evidence-contract/src/privacy.cjs");
const boundary = require("./boundary.cjs");

const PLATFORMS = new Set([
  "linux", "darwin", "win32", "freebsd", "openbsd", "netbsd", "android", "aix", "sunos", "cygwin",
]);
const ARCHES = new Set([
  "x64", "arm64", "ia32", "arm", "ppc64", "s390x", "riscv64", "mips64el", "loong64",
]);
const SCHEMES = new Set(["http", "https", "ws", "wss"]);
const ERROR_REASONS = new Set([
  "ACCESSOR_PROPERTY_FORBIDDEN",
  "CYCLE_REJECTED",
  "EXCESSIVE_NESTING",
  "HOSTILE_INPUT",
  "INPUT_BOUND",
  "MALFORMED_JSON",
  "MALFORMED_UTF8",
  "PROHIBITED_FIELD_NAME",
  "PROMPT_COMPLETION_EXCLUDED",
  "VALIDATOR_FAULT",
]);

function hasOwn(object, key) {
  return !!object && typeof object === "object" && Object.prototype.hasOwnProperty.call(object, key);
}

function applicationResultOf(options) {
  if (!options || typeof options !== "object") return null;
  if (!hasOwn(options, "applicationResult")) return null;
  return options.applicationResult;
}

function unicodeDiagnostic() {
  if (!privacy.profileReady()) return null;
  const id = privacy.profileId();
  if (id !== boundary.UNICODE_PROFILE_ID) return null;
  const version = privacy.profileVersion();
  if (version !== boundary.UNICODE_PROFILE_VERSION) return null;
  return {
    issue_location: null,
    unicode_profile_id: id,
    unicode_profile_version: version,
  };
}

function compatibilityBlock(legacyVersion) {
  return {
    legacy_marker: true,
    legacy_schema_version: legacyVersion === boundary.LEGACY_SCHEMA_VERSION ? boundary.LEGACY_SCHEMA_VERSION : null,
    live_writer_modified: false,
    source_shape: "node_run_log",
  };
}

function errorDocument(issueLocation) {
  const diagnostics = unicodeDiagnostic() || {
    issue_location: issueLocation,
    unicode_profile_id: null,
    unicode_profile_version: null,
  };
  diagnostics.issue_location = issueLocation;
  return {
    activates_unit_d: true,
    activates_unit_e: false,
    cli_or_sdk_version: boundary.FUTURE_CLI_VERSION,
    compatibility: compatibilityBlock(boundary.LEGACY_SCHEMA_VERSION),
    diagnostics,
    events: [],
    issue_location: issueLocation,
    optics_status: "OPTICS_ERROR",
    producer: boundary.PRODUCER,
    record_emitted: false,
    record_type: "run_envelope",
    schema_status: boundary.SCHEMA_STATUS,
    schema_version: boundary.SCHEMA_VERSION,
    shipped_product: false,
  };
}

function storeOptics(token) {
  if (boundary.WRITER_OPTICS.has(token)) return token;
  return "UNAVAILABLE";
}

function enforcementAction(action) {
  if (typeof action !== "string") return false;
  if (action === "OBSERVED") return false;
  if (boundary.ENFORCEMENT_ACTIONS.has(action)) return true;
  if (action.startsWith("BLOCKED")) return true;
  if (action.startsWith("DRY_RUN_BLOCKED")) return true;
  if (action === "ALLOWED") return true;
  return action !== "OBSERVED";
}

function versionToken(value) {
  return typeof value === "string" && /^[A-Za-z0-9._+-]{1,32}$/.test(value) ? value : null;
}

function runId(value) {
  return typeof value === "string" && /^[A-Za-z0-9_-]{1,80}$/.test(value) ? value : null;
}

function httpStatus(value) {
  return typeof value === "number" && Number.isInteger(value) && value >= 100 && value <= 599 ? value : null;
}

function nonNegative(value) {
  return typeof value === "number" && Number.isInteger(value) && value >= 0 ? value : null;
}

function errorClass(value) {
  return typeof value === "string" && /^[A-Za-z0-9_]{1,64}$/.test(value) ? value : null;
}

function methodToken(value) {
  return typeof value === "string" && /^[A-Za-z]{1,16}$/.test(value) ? value : null;
}

function opticsFromCall(call) {
  const raw = hasOwn(call, "optics_status") ? call.optics_status : (hasOwn(call, "opticsStatus") ? call.opticsStatus : undefined);
  if (raw === undefined) return { forbidden: false, token: "OBSERVED" };
  if (raw === "SUCCESS" || !boundary.WRITER_OPTICS.has(raw)) return { forbidden: true, token: "UNAVAILABLE" };
  return { forbidden: false, token: raw };
}

function networkFailure(call, side) {
  if (side && side.networkError === true) return true;
  return call.error === "network_error";
}

function responseBytes(side) {
  if (!side || side.lengthPresent !== true) return { omit: true };
  const value = nonNegative(side.responseBytes);
  if (value == null) return { omit: true };
  return { omit: false, value };
}

function align(calls, sidecar) {
  const sides = Array.isArray(sidecar) ? sidecar : [];
  if (sides.length === calls.length) {
    return calls.map((call, index) => ({ call, side: sides[index] }));
  }
  const kept = calls.filter((call) => !enforcementAction(call && call.action));
  if (sides.length === kept.length) {
    let cursor = 0;
    return calls.map((call) => {
      if (enforcementAction(call && call.action)) return { call, side: null };
      const side = sides[cursor];
      cursor += 1;
      return { call, side };
    });
  }
  return calls.map((call) => ({ call, side: null }));
}

function scrub(value, seen) {
  if (!value || typeof value !== "object") return;
  if (seen.has(value)) return;
  seen.add(value);
  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i += 1) scrub(value[i], seen);
    return;
  }
  const keys = Object.keys(value);
  for (let i = 0; i < keys.length; i += 1) {
    const key = keys[i];
    if (boundary.PROHIBITED_KEYS.has(key) || key === "opticsStatus" || key === "bytes" || key === "ok" || key === "error") {
      delete value[key];
      continue;
    }
    scrub(value[key], seen);
  }
}

function baseIdentity(legacy) {
  const input = {
    cli_or_sdk_version: boundary.FUTURE_CLI_VERSION,
    clock_quality: "UNAVAILABLE",
    evidence_origin: "LOCAL_OBSERVATION",
    producer: boundary.PRODUCER,
    record_type: "observation_event",
    runtime: "node",
    sampling: "UNSAMPLED",
    schema_status: boundary.SCHEMA_STATUS,
    schema_version: boundary.SCHEMA_VERSION,
  };
  const version = versionToken(legacy && legacy.node_version);
  if (version) input.runtime_version = version;
  const id = runId(legacy && legacy.trace_id);
  if (id) input.run_id = id;
  return input;
}

function observationInput(legacy, call, side) {
  const input = baseIdentity(legacy);
  const optics = opticsFromCall(call || {});
  input.optics_status = optics.token;
  const host = typeof call.hostname === "string" ? call.hostname : null;
  if (host) input.destination_host = host;
  const method = methodToken(call.method);
  if (method) input.method = method;
  if (typeof call.path === "string" && call.path.length > 0) input.path = call.path;
  if (typeof call.scheme === "string" && SCHEMES.has(call.scheme)) input.scheme = call.scheme;
  const port = side && nonNegative(side.port);
  if (port != null && !((call.scheme === "https" && port === 443) || (call.scheme === "http" && port === 80))) {
    input.destination_port = port;
  }
  const status = httpStatus(call.status);
  if (status != null) input.http_status = status;
  else input.application_status = "UNAVAILABLE";
  const requestBytes = nonNegative(call.request_bytes);
  if (requestBytes != null) input.request_bytes = requestBytes;
  const bytes = responseBytes(side);
  if (!bytes.omit) input.response_bytes = bytes.value;
  if (typeof call.content_type === "string" && call.content_type.length > 0) input.content_type = call.content_type;
  const failedOpen = networkFailure(call, side);
  const preCompletion = call.duration_ms === 0 && status == null && !failedOpen;
  const duration = nonNegative(call.duration_ms);
  if (!preCompletion && duration != null) input.duration_ms = duration;
  if (typeof call.ts === "string") input.started_at = call.ts;
  if (call.action === "OBSERVED") input.action = "OBSERVED";
  if (failedOpen) input.failure_kind = "network";
  const named = errorClass(call.error_class) || (side && errorClass(side.errorClass));
  if (named) input.error_class = named;
  input.lifecycle = preCompletion ? "INTERRUPTED" : "COMPLETE";
  if (side && side.mediation === "node_fetch") input.mediation = "node_fetch";
  return { forbidden: optics.forbidden, input, preCompletion };
}

function envelopeInput(legacy, eventCount, dropped, lifecycle) {
  const input = baseIdentity(legacy);
  input.record_type = "run_envelope";
  input.coverage_note = "WRAPPED_PROCESS";
  input.call_count = eventCount;
  input.dropped_count = dropped;
  input.lifecycle = lifecycle;
  input.span_id = null;
  input.parent_span_id = null;
  delete input.optics_status;
  delete input.sampling;
  const platform = legacy && legacy.platform;
  if (typeof platform === "string" && PLATFORMS.has(platform)) input.platform = platform;
  const arch = legacy && legacy.arch;
  if (typeof arch === "string" && ARCHES.has(arch)) input.arch = arch;
  if (typeof legacy.started_at === "string") input.started_at = legacy.started_at;
  if (typeof legacy.generated_at === "string") input.ended_at = legacy.generated_at;
  const duration = nonNegative(legacy && legacy.duration_ms);
  if (duration != null) input.duration_ms = duration;
  if (hasOwn(legacy, "pid")) {
    const pid = legacy.pid == null ? null : nonNegative(legacy.pid);
    if (pid != null || legacy.pid == null) input.process_id = pid;
  }
  if (hasOwn(legacy, "ppid")) {
    const ppid = legacy.ppid == null ? null : nonNegative(legacy.ppid);
    if (ppid != null || legacy.ppid == null) input.parent_process_id = ppid;
  }
  return input;
}

function envelopeLifecycle(events) {
  const apps = new Set();
  let interrupted = false;
  for (let i = 0; i < events.length; i += 1) {
    const event = events[i];
    if (!event) continue;
    if (event.lifecycle === "INTERRUPTED") interrupted = true;
    if (event.application_status === "SUCCESS" || event.application_status === "APPLICATION_ERROR") {
      apps.add(event.application_status);
    }
  }
  if (apps.size > 1) return "PARTIAL";
  if (interrupted) return "INTERRUPTED";
  return "COMPLETE";
}

function fileOptics(events) {
  if (events.length === 0) return "NOT_OBSERVED";
  let sawObserved = false;
  let sawUnavailable = false;
  let sawError = false;
  for (let i = 0; i < events.length; i += 1) {
    const token = events[i] && events[i].optics_status;
    if (token === "OBSERVED") sawObserved = true;
    else if (token === "OPTICS_ERROR") sawError = true;
    else if (token === "UNAVAILABLE" || token === "NOT_OBSERVED") sawUnavailable = true;
    else return "UNAVAILABLE";
  }
  if (sawError && !sawObserved) return "OPTICS_ERROR";
  if (sawObserved) return "OBSERVED";
  if (sawUnavailable) return "UNAVAILABLE";
  return "UNAVAILABLE";
}

function outcome(document, applicationResult, emitted, optics) {
  return {
    application_result: applicationResult,
    document,
    optics_status: optics,
    record_emitted: emitted,
  };
}

function composeCanonical(legacy, sidecar, options) {
  const applicationResult = applicationResultOf(options);
  const diagnostics = unicodeDiagnostic();
  if (!diagnostics) return outcome(errorDocument("OPTICS"), applicationResult, false, "OPTICS_ERROR");
  if (!legacy || typeof legacy !== "object" || Array.isArray(legacy)) {
    return outcome(errorDocument("OPTICS"), applicationResult, false, "OPTICS_ERROR");
  }
  if (options && options.injectFault === true) {
    validateEvidence(
      { record_type: "run_envelope", schema_version: boundary.SCHEMA_VERSION },
      { applicationResult, injectFault: true },
    );
    return outcome(errorDocument("OPTICS"), applicationResult, false, "OPTICS_ERROR");
  }
  const calls = Array.isArray(legacy.calls) ? legacy.calls : [];
  const paired = align(calls, sidecar);
  const events = [];
  let dropped = 0;
  let forbidden = false;
  for (let i = 0; i < paired.length; i += 1) {
    const call = paired[i].call;
    if (!call || typeof call !== "object") {
      dropped += 1;
      continue;
    }
    if (enforcementAction(call.action)) {
      dropped += 1;
      continue;
    }
    const built = observationInput(legacy, call, paired[i].side);
    if (built.forbidden) forbidden = true;
    let validated;
    try {
      validated = validateEvidence(built.input, { applicationResult });
    } catch {
      return outcome(errorDocument("OPTICS"), applicationResult, false, "OPTICS_ERROR");
    }
    if (!validated || validated.record_emitted !== true || !validated.record) {
      dropped += 1;
      if (validated && ERROR_REASONS.has(validated.reason_code)) {
        return outcome(errorDocument("OPTICS"), applicationResult, false, "OPTICS_ERROR");
      }
      continue;
    }
    if (validated.record.optics_status === "SUCCESS" || !boundary.WRITER_OPTICS.has(validated.record.optics_status)) {
      forbidden = true;
      dropped += 1;
      continue;
    }
    if (!hasOwn(validated.record, "issue_location")) {
      return outcome(errorDocument("OPTICS"), applicationResult, false, "OPTICS_ERROR");
    }
    events.push(validated.record);
  }
  const lifecycle = envelopeLifecycle(events);
  const input = envelopeInput(legacy, events.length, dropped, lifecycle);
  let envelope;
  try {
    envelope = validateEvidence(input, { applicationResult });
  } catch {
    return outcome(errorDocument("OPTICS"), applicationResult, false, "OPTICS_ERROR");
  }
  if (!envelope || envelope.record_emitted !== true || !envelope.record || envelope.record.evidence_origin !== "LOCAL_OBSERVATION") {
    return outcome(errorDocument("OPTICS"), applicationResult, false, "OPTICS_ERROR");
  }
  if (envelope.record.schema_version !== boundary.SCHEMA_VERSION) {
    return outcome(errorDocument("OPTICS"), applicationResult, false, "OPTICS_ERROR");
  }
  const optics = storeOptics(events.length === 0 && forbidden ? "UNAVAILABLE" : fileOptics(events));
  const profile = envelope.diagnostics && envelope.diagnostics.unicode_profile_id;
  if (profile !== boundary.UNICODE_PROFILE_ID) {
    return outcome(errorDocument("OPTICS"), applicationResult, false, "OPTICS_ERROR");
  }
  const document = Object.assign({}, envelope.record);
  document.optics_status = optics;
  document.issue_location = events.length > 0 && hasOwn(events[0], "issue_location") ? events[0].issue_location : "NONE";
  document.activates_unit_d = true;
  document.activates_unit_e = false;
  document.shipped_product = false;
  document.record_emitted = true;
  document.compatibility = compatibilityBlock(
    typeof legacy.schema_version === "number" ? legacy.schema_version : null,
  );
  document.diagnostics = {
    ended_at_is_wrap_exit_at_file_write: typeof legacy.generated_at === "string",
    issue_location: document.issue_location,
    optimistic_default_forbidden: forbidden,
    unicode_profile_id: boundary.UNICODE_PROFILE_ID,
    unicode_profile_version: boundary.UNICODE_PROFILE_VERSION,
  };
  document.events = events;
  scrub(document, new Set());
  if (document.optics_status === "SUCCESS") {
    return outcome(errorDocument("OPTICS"), applicationResult, false, "OPTICS_ERROR");
  }
  return outcome(document, applicationResult, true, document.optics_status);
}

module.exports = {
  composeCanonical,
  errorDocument,
};
