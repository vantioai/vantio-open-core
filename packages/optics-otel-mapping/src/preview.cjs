"use strict";

const LIVE = Object.freeze({
  optics: "opticsStatus",
  application: "applicationStatus",
  http: "httpStatus",
  host: "hostname",
});

const CANONICAL = Object.freeze({
  optics: "optics_status",
  application: "application_status",
  http: "http_status",
  host: "destination_host",
});

function omit(list, code, field) {
  list.push({ code, field });
}

function httpCode(value) {
  if (typeof value !== "number" || !Number.isInteger(value)) return null;
  if (value < 100 || value > 599) return null;
  return value;
}

function methodCandidate(mapping, value) {
  if (typeof value !== "string") return null;
  if (value === "unknown") return null;
  if (!mapping.methods.includes(value)) return null;
  return value;
}

function pathCandidate(value) {
  if (typeof value !== "string") return null;
  if (value.length < 1 || value.length > 512) return null;
  if (!value.startsWith("/")) return null;
  if (/[\s?#@\\]/.test(value)) return null;
  return value;
}

function hostCandidate(value) {
  if (typeof value !== "string") return null;
  if (value.length < 1 || value.length > 253) return null;
  const folded = value.toLowerCase();
  if (folded.endsWith(".")) return null;
  if (folded.includes("..")) return null;
  if (!/^[a-z0-9._:-]+$/.test(folded)) return null;
  return folded;
}

function portCandidate(value) {
  if (typeof value !== "number" || !Number.isInteger(value)) return null;
  if (value < 1 || value > 65535) return null;
  return value;
}

function schemeCandidate(value) {
  if (value === "http" || value === "https" || value === "ws" || value === "wss") return value;
  return null;
}

function w3cTraceId(value) {
  return typeof value === "string" && /^[0-9a-f]{32}$/.test(value) && !/^0{32}$/.test(value);
}

function w3cSpanId(value) {
  return typeof value === "string" && /^[0-9a-f]{16}$/.test(value) && !/^0{16}$/.test(value);
}

function providerCandidate(mapping, record) {
  const confidence = record.provider_confidence;
  if (confidence !== "CATALOG" && confidence !== "REGIONAL_PATTERN") return null;
  const id = record.provider_id;
  for (const entry of mapping.provider_crosswalk) {
    if (entry.optics_provider_id === id) return entry.gen_ai_provider_name;
  }
  return null;
}

function operationCandidate(mapping, method, path) {
  if (method == null || path == null) return null;
  for (const rule of mapping.operation_rules) {
    if (rule.method === method && rule.path === path) return rule.gen_ai_operation_name;
  }
  return null;
}

function emptyPreview(reason, extra) {
  return {
    emitted: false,
    reason: "ADAPTERS_DISABLED",
    would_be_operational_if_i3_enabled: false,
    operational_block: reason,
    prohibited_input_present: false,
    candidates: {},
    span: { client: null, instrumentation: null },
    trace_context: null,
    omitted: extra || [],
  };
}

function canonicalOriginBlock(mapping, origin) {
  if (origin == null || origin === "") return "ORIGIN_ABSENT_NOT_LOCAL";
  const allowed = mapping.canonical_candidate_origins;
  if (Array.isArray(allowed) && allowed.includes(origin)) return null;
  if (origin === "SIMULATED_DEMO") return "SIMULATED_DEMO_EXCLUDED";
  return "ORIGIN_NOT_OPERATIONAL";
}

function designPreview(mapping, record) {
  const source = record && typeof record === "object" && !Array.isArray(record) ? record : {};
  const shape = source.source_shape;
  if (shape !== "live_display" && shape !== "canonical_observation") {
    return emptyPreview("SOURCE_SHAPE_UNKNOWN", [{ code: "SOURCE_SHAPE_UNKNOWN", field: "source_shape" }]);
  }
  if (source.record_type != null && source.record_type !== "observation_event") {
    return emptyPreview("RECORD_TYPE_OUT_OF_SCOPE", [{ code: "RECORD_TYPE_OUT_OF_SCOPE", field: "record_type" }]);
  }

  const names = shape === "live_display" ? LIVE : CANONICAL;
  const omitted = [];
  const origin = source.evidence_origin;

  if (shape === "canonical_observation") {
    const originBlock = canonicalOriginBlock(mapping, origin);
    if (originBlock) {
      return emptyPreview(originBlock, [{ code: originBlock, field: "evidence_origin" }]);
    }
  }

  const prohibitedNames = mapping.prohibited_input_names;
  let prohibited = false;
  for (const name of prohibitedNames) {
    if (Object.prototype.hasOwnProperty.call(source, name)) prohibited = true;
  }
  if (prohibited) omit(omitted, "PROHIBITED_INPUT_IGNORED", "prohibited_input");

  if (Array.isArray(source.calls)) omit(omitted, "CALL_LIST_NOT_COLLAPSED", "calls");

  const candidates = {};
  let operationalBlock = null;

  if (shape === "live_display") {
    operationalBlock = "LIVE_DISPLAY_IS_NOT_PROVENANCE";
    if (source.provider != null) omit(omitted, "LIVE_PROVIDER_NOT_PROMOTED", "provider");
  } else if (source.provider_id != null) {
    const mapped = providerCandidate(mapping, source);
    if (mapped) candidates["gen_ai.provider.name"] = mapped;
    else omit(omitted, "PROVIDER_NOT_MAPPED", "provider_id");
  }

  const method = methodCandidate(mapping, source.method);
  if (source.method != null && method == null) omit(omitted, "METHOD_NOT_MAPPED", "method");
  if (method) candidates["http.request.method"] = method;

  const path = pathCandidate(source.path);
  if (source.path != null && path == null) omit(omitted, "PATH_NOT_METADATA", "path");
  if (path) candidates["url.path"] = path;

  const operation = operationCandidate(mapping, method, path);
  if (operation) candidates["gen_ai.operation.name"] = operation;
  else if (method === "POST" && path != null) omit(omitted, "OPERATION_UNMAPPED", "path");

  if (shape === "canonical_observation") {
    const scheme = schemeCandidate(source.scheme);
    if (source.scheme != null && scheme == null) omit(omitted, "SCHEME_NOT_MAPPED", "scheme");
    if (scheme) candidates["url.scheme"] = scheme;
    const port = portCandidate(source.destination_port);
    if (source.destination_port != null && port == null) omit(omitted, "PORT_NOT_EXPLICIT", "destination_port");
    if (port != null) candidates["server.port"] = port;
  }

  const host = hostCandidate(source[names.host]);
  if (source[names.host] != null && host == null) omit(omitted, "HOST_NOT_METADATA", names.host);
  if (host) candidates["server.address"] = host;

  const http = httpCode(source[names.http]);
  if (source[names.http] != null && http == null) omit(omitted, "HTTP_STATUS_NOT_INTEGER", names.http);
  if (http != null) candidates["http.response.status_code"] = http;

  const application = source[names.application];
  const optics = source[names.optics];
  let client = null;
  let instrumentation = null;

  if (application === "SUCCESS") {
    if (http != null && http >= 200 && http <= 399) client = "OK";
    else omit(omitted, "STATUS_HTTP_DISAGREEMENT", names.application);
  } else if (application === "APPLICATION_ERROR") {
    if (http != null && http >= 400 && http <= 599) client = "ERROR";
    else omit(omitted, "STATUS_HTTP_DISAGREEMENT", names.application);
  } else if (application != null) {
    omit(omitted, "APPLICATION_STATUS_NO_SPAN", names.application);
  }

  if (optics === "OPTICS_ERROR") instrumentation = "ERROR";
  else if (optics === "SUCCESS") omit(omitted, "OPTIMISTIC_DEFAULT_FORBIDDEN", names.optics);
  else if (optics != null) omit(omitted, "OPTICS_STATUS_NO_SPAN", names.optics);

  let errorTypes = 0;
  if (client === "ERROR") errorTypes += 1;
  if (instrumentation === "ERROR") errorTypes += 1;
  if (errorTypes > 1) {
    client = null;
    instrumentation = null;
    omit(omitted, "STATUS_DIMENSION_CONFLICT", "error.type");
    operationalBlock = operationalBlock || "STATUS_DIMENSION_CONFLICT";
  } else if (client === "ERROR") {
    candidates["error.type"] = "application_error";
  } else if (instrumentation === "ERROR") {
    candidates["error.type"] = "optics_error";
  }

  if (source.bytes != null || source.request_bytes != null || source.response_bytes != null) {
    omit(omitted, "NOT_TOKEN_COUNTS", "bytes");
  }
  if (source.duration_ms != null) omit(omitted, "CORRESPONDENCE_ONLY", "duration_ms");
  if (source.clock_quality != null) omit(omitted, "CLOCK_QUALITY_NOT_A_SPAN", "clock_quality");
  if (source.run_id != null) omit(omitted, "RUN_ID_IS_NOT_TRACE_ID", "run_id");
  if (source.session_id != null) omit(omitted, "SESSION_IS_NOT_CONVERSATION", "session_id");
  if (source.process_id != null) omit(omitted, "PROCESS_ID_NOT_RESOURCE", "process_id");
  if (source.ok != null) omit(omitted, "OK_BOOLEAN_IGNORED", "ok");
  if (source.action != null) omit(omitted, "ACTION_IS_NOT_SPAN_STATUS", "action");

  let trace = null;
  if (shape === "live_display") {
    if (source.trace_id != null) omit(omitted, "LIVE_TRACE_ID_IS_RUN_BOUNDARY", "trace_id");
  } else if (source.trace_id != null || source.span_id != null) {
    const basis = source.trace_id_basis;
    const parentPresent = source.parent_span_id != null;
    const parentOk = !parentPresent || w3cSpanId(source.parent_span_id);
    if (basis === "ASSERTED_CONTEXT") {
      omit(omitted, "NEEDS_FOUNDER_DECISION", "trace_id_basis");
    } else if (basis === "APPLICATION_SUPPLIED" && w3cTraceId(source.trace_id) && w3cSpanId(source.span_id) && parentOk) {
      trace = { trace_id: source.trace_id, span_id: source.span_id };
      if (parentPresent) trace.parent_span_id = source.parent_span_id;
    } else {
      omit(omitted, "TRACE_BASIS_NOT_ELIGIBLE", "trace_id");
    }
  }

  if (prohibited) operationalBlock = operationalBlock || "PROHIBITED_INPUT_IGNORED";
  if (Array.isArray(source.calls)) operationalBlock = operationalBlock || "CALL_LIST_NOT_COLLAPSED";

  return {
    emitted: false,
    reason: "ADAPTERS_DISABLED",
    would_be_operational_if_i3_enabled: operationalBlock == null,
    operational_block: operationalBlock,
    prohibited_input_present: prohibited,
    candidates,
    span: { client, instrumentation },
    trace_context: trace,
    omitted,
  };
}

module.exports = { designPreview };
