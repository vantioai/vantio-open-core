"use strict";

const { SCOPE } = require("./boundary.cjs");
const { api, doc } = require("./mapping_ref.cjs");

const UINT64_MAX = 18446744073709551615n;

const VALUE_MARKERS = Object.freeze([
  "BEGIN PRIVATE KEY",
  "BEGIN RSA PRIVATE KEY",
  "BEGIN OPENSSH PRIVATE KEY",
  "BEGIN EC PRIVATE KEY",
  "BEGIN DSA PRIVATE KEY",
  "AKIA",
  "ASIA",
  "AIza",
  "ya29.",
  "xoxb-",
  "xoxp-",
  "xoxa-",
  "ghp_",
  "github_pat_",
  "sk-",
  "api_key=",
  "password=",
  "secret=",
]);

function valueHasMarker(value) {
  if (typeof value !== "string") return false;
  for (const marker of VALUE_MARKERS) {
    if (value.includes(marker)) return true;
  }
  return false;
}

function parseNano(value) {
  if (typeof value !== "string") return null;
  if (!/^(0|[1-9][0-9]{0,19})$/.test(value)) return null;
  const parsed = BigInt(value);
  if (parsed > UINT64_MAX) return null;
  return parsed;
}

function clockPair(start, end) {
  const startNano = parseNano(start);
  const endNano = parseNano(end);
  if (start == null && end == null) return { ok: false, reason: "SPAN_TIME_ABSENT" };
  if (startNano == null || endNano == null) return { ok: false, reason: "SPAN_TIME_INVALID" };
  if (endNano <= startNano) return { ok: false, reason: "SPAN_TIME_NOT_POSITIVE" };
  return { ok: true, start: startNano.toString(), end: endNano.toString() };
}

function stringAttribute(value, pattern, max) {
  if (typeof value !== "string") return null;
  if (value.length < 1 || value.length > max) return null;
  if (!pattern.test(value)) return null;
  if (valueHasMarker(value)) return null;
  return value;
}

function revalidateCandidates(candidates) {
  if (!candidates || typeof candidates !== "object" || Array.isArray(candidates)) {
    return { ok: false, reason: "CANDIDATE_REJECTED" };
  }
  const attributes = {};
  for (const key of Object.keys(candidates)) {
    if (!api.ALLOWED_MAP_TARGETS.has(key) || api.PROHIBITED_TARGETS.has(key)) {
      return { ok: false, reason: "CANDIDATE_REJECTED" };
    }
    const value = candidates[key];
    let accepted = null;
    if (key === "gen_ai.provider.name") {
      const known = doc.provider_crosswalk.some((entry) => entry.gen_ai_provider_name === value);
      accepted = known ? stringAttribute(value, /^[a-z0-9._]+$/, 64) : null;
    } else if (key === "gen_ai.operation.name") {
      accepted = value === "chat" ? "chat" : null;
    } else if (key === "http.request.method") {
      accepted = value !== "unknown" && doc.methods.includes(value) ? stringAttribute(value, /^[A-Z]+$/, 16) : null;
    } else if (key === "http.response.status_code") {
      accepted = typeof value === "number" && Number.isInteger(value) && value >= 100 && value <= 599 ? value : null;
    } else if (key === "url.path") {
      accepted = stringAttribute(value, /^\/[^\s?#@\\]{0,511}$/, 512);
    } else if (key === "url.scheme") {
      accepted = value === "http" || value === "https" || value === "ws" || value === "wss" ? value : null;
    } else if (key === "server.address") {
      accepted = stringAttribute(value, /^[a-z0-9._:-]{1,253}$/, 253);
    } else if (key === "server.port") {
      accepted = typeof value === "number" && Number.isInteger(value) && value >= 1 && value <= 65535 ? value : null;
    } else if (key === "error.type") {
      accepted = value === "application_error" || value === "optics_error" ? value : null;
    }
    if (typeof value === "string" && valueHasMarker(value)) {
      return { ok: false, reason: "CREDENTIAL_PATTERN_REJECTED" };
    }
    if (accepted == null) return { ok: false, reason: "CANDIDATE_REJECTED" };
    attributes[key] = accepted;
  }
  if (attributes["gen_ai.operation.name"] === "chat") {
    if (attributes["http.request.method"] !== "POST" || attributes["url.path"] !== "/v1/chat/completions") {
      return { ok: false, reason: "CANDIDATE_REJECTED" };
    }
  }
  return { ok: true, attributes };
}

function statusPlan(client, instrumentation) {
  if (client != null && instrumentation != null) {
    return { ok: false, reason: "STATUS_DIMENSIONS_NOT_COLLAPSED" };
  }
  if (client === "OK") return { ok: true, kind: 3, statusCode: 1 };
  if (client === "ERROR") return { ok: true, kind: 3, statusCode: 2 };
  if (instrumentation === "ERROR") return { ok: true, kind: 1, statusCode: 2 };
  if (client == null && instrumentation == null) return { ok: true, kind: 3, statusCode: 0 };
  return { ok: false, reason: "STATUS_UNRECOGNIZED" };
}

function errorTypeAgrees(attributes, client, instrumentation) {
  const errorType = attributes["error.type"];
  if (errorType === "application_error") {
    return client === "ERROR" && instrumentation == null;
  }
  if (errorType === "optics_error") {
    return instrumentation === "ERROR" && client == null;
  }
  if (errorType == null) {
    return client !== "ERROR" && instrumentation !== "ERROR";
  }
  return false;
}

function spanName(attributes) {
  if (attributes["gen_ai.operation.name"] === "chat") return "chat";
  return "gen_ai.client";
}

function attributeValue(value) {
  if (typeof value === "number") {
    return { intValue: String(value) };
  }
  return { stringValue: value };
}

function encodeSpan(plan) {
  const keys = Object.keys(plan.attributes).sort();
  const attributes = [];
  for (const key of keys) {
    attributes.push({ key, value: attributeValue(plan.attributes[key]) });
  }
  const span = {
    traceId: plan.traceId,
    spanId: plan.spanId,
    name: plan.name,
    kind: plan.kind,
    startTimeUnixNano: plan.startTimeUnixNano,
    endTimeUnixNano: plan.endTimeUnixNano,
    attributes,
    status: { code: plan.statusCode },
  };
  if (plan.parentSpanId) span.parentSpanId = plan.parentSpanId;
  return span;
}

function encodeTraceRequest(plans) {
  return JSON.stringify({
    resourceSpans: [
      {
        resource: { attributes: [] },
        scopeSpans: [
          {
            scope: { name: SCOPE.name, version: SCOPE.version },
            spans: plans.map(encodeSpan),
          },
        ],
      },
    ],
  });
}

function hexId(value, length) {
  if (typeof value !== "string") return false;
  if (value.length !== length) return false;
  if (!/^[0-9a-f]+$/.test(value)) return false;
  return value !== "0".repeat(length);
}

function hasOwnDeep(value, key) {
  if (Array.isArray(value)) return value.some((item) => hasOwnDeep(item, key));
  if (!value || typeof value !== "object") return false;
  if (Object.prototype.hasOwnProperty.call(value, key)) return true;
  for (const child of Object.keys(value)) {
    if (hasOwnDeep(value[child], key)) return true;
  }
  return false;
}

function payloadAccepted(body) {
  if (typeof body !== "string" || body.length < 2 || body.length > 1_000_000) return false;
  if (valueHasMarker(body)) return false;
  for (const name of api.PROHIBITED_TARGETS) {
    if (body.includes(name)) return false;
  }
  let parsed;
  try {
    parsed = JSON.parse(body);
  } catch {
    return false;
  }
  if (hasOwnDeep(parsed, "schemaUrl")) return false;
  if (!parsed || !Array.isArray(parsed.resourceSpans) || parsed.resourceSpans.length !== 1) return false;
  const resourceSpan = parsed.resourceSpans[0];
  if (!resourceSpan.resource || !Array.isArray(resourceSpan.resource.attributes) || resourceSpan.resource.attributes.length !== 0) {
    return false;
  }
  if (!Array.isArray(resourceSpan.scopeSpans) || resourceSpan.scopeSpans.length !== 1) return false;
  const scopeSpan = resourceSpan.scopeSpans[0];
  if (!scopeSpan.scope || scopeSpan.scope.name !== SCOPE.name || scopeSpan.scope.version !== SCOPE.version) return false;
  if (!Array.isArray(scopeSpan.spans) || scopeSpan.spans.length < 1) return false;
  for (const span of scopeSpan.spans) {
    if (!hexId(span.traceId, 32) || !hexId(span.spanId, 16)) return false;
    if (span.parentSpanId != null && !hexId(span.parentSpanId, 16)) return false;
    if (span.name !== "chat" && span.name !== "gen_ai.client") return false;
    if (span.kind !== 1 && span.kind !== 3) return false;
    const start = parseNano(span.startTimeUnixNano);
    const end = parseNano(span.endTimeUnixNano);
    if (start == null || end == null || end <= start) return false;
    if (!span.status || typeof span.status !== "object" || Array.isArray(span.status)) return false;
    if (Object.keys(span.status).some((key) => key !== "code")) return false;
    if (span.status.code !== 0 && span.status.code !== 1 && span.status.code !== 2) return false;
    if (span.kind === 1 && span.status.code !== 2) return false;
    if (!Array.isArray(span.attributes)) return false;
    for (const attribute of span.attributes) {
      if (!attribute || typeof attribute.key !== "string") return false;
      if (!api.ALLOWED_MAP_TARGETS.has(attribute.key) || api.PROHIBITED_TARGETS.has(attribute.key)) return false;
      const keys = attribute.value && typeof attribute.value === "object" ? Object.keys(attribute.value) : [];
      if (keys.length !== 1) return false;
      if (keys[0] !== "stringValue" && keys[0] !== "intValue") return false;
    }
    if (Object.prototype.hasOwnProperty.call(span, "events") || Object.prototype.hasOwnProperty.call(span, "links")) {
      return false;
    }
  }
  return true;
}

module.exports = {
  VALUE_MARKERS,
  clockPair,
  encodeTraceRequest,
  errorTypeAgrees,
  payloadAccepted,
  revalidateCandidates,
  spanName,
  statusPlan,
  valueHasMarker,
};
