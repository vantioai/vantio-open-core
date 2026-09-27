"use strict";

const { LIMITS, POSTURE } = require("./boundary.cjs");
const { evaluateRecords } = require("./authority.cjs");
const { encodeTraceRequest, payloadAccepted } = require("./encode.cjs");
const { parseCustomerEndpoint } = require("./endpoint.cjs");
const { credentialOptionPresent } = require("./names.cjs");
const { postOtlpJson } = require("./transport.cjs");

function own(options, key) {
  if (!options || typeof options !== "object") return undefined;
  if (!Object.prototype.hasOwnProperty.call(options, key)) return undefined;
  return options[key];
}

function activation(options) {
  if (own(options, "enabled") !== true) return { active: false, reason: "ADAPTER_DISABLED" };
  const adapter = own(options, "adapter");
  if (adapter === "otlp_metrics" || adapter === "otlp_logs") {
    return { active: false, reason: "SIGNAL_NOT_AUTHORIZED" };
  }
  if (adapter !== "otlp_traces") return { active: false, reason: "ADAPTER_NOT_SELECTED" };
  return { active: true, reason: null };
}

function resolveAttempts(options) {
  const value = own(options, "max_retries");
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    return 1 + LIMITS.defaultMaxRetries;
  }
  return Math.min(1 + value, LIMITS.hardMaxAttempts);
}

function resolveQueue(options) {
  const value = own(options, "max_queue");
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    return { limit: LIMITS.defaultMaxQueue, clamped: false };
  }
  if (value > LIMITS.hardMaxQueue) return { limit: LIMITS.hardMaxQueue, clamped: true };
  return { limit: value, clamped: false };
}

function resolveTimeout(options) {
  const value = own(options, "timeout_ms");
  if (typeof value !== "number" || !Number.isInteger(value)) return LIMITS.defaultTimeoutMs;
  if (value < LIMITS.minTimeoutMs) return LIMITS.minTimeoutMs;
  if (value > LIMITS.hardMaxTimeoutMs) return LIMITS.hardMaxTimeoutMs;
  return value;
}

function admit(records, queue) {
  const queued = [];
  const drops = [];
  for (const row of records) {
    const eligibility = row.eligibility;
    if (!eligibility.export_eligible) {
      drops.push({
        index: eligibility.index,
        phase: "eligibility",
        reason: eligibility.reason,
        operational: eligibility.operational === true,
        mapping_version: POSTURE.mapping_version,
      });
      continue;
    }
    if (queued.length >= queue.limit) {
      drops.push({
        index: eligibility.index,
        phase: "admission",
        reason: "BACKPRESSURE_QUEUE_LIMIT",
        operational: true,
        mapping_version: POSTURE.mapping_version,
      });
      continue;
    }
    queued.push(eligibility.index);
  }
  return {
    limit: queue.limit,
    clamped: queue.clamped,
    queued_indexes: queued,
    drops,
  };
}

function emptyAdmission() {
  return {
    limit: null,
    clamped: false,
    queued_indexes: [],
    drops: [],
  };
}

function classifyResponse(response) {
  if (!response || typeof response !== "object") {
    return { kind: "UNAVAILABLE", retry: true, status: null };
  }
  const status = response.status;
  const hasStatus = typeof status === "number" && Number.isInteger(status);
  if (hasStatus && (status === 200 || status === 202) && response.ok !== false) {
    return { kind: "ACCEPTED", retry: false, status };
  }
  if (!hasStatus && response.ok === true) return { kind: "ACCEPTED", retry: false, status: null };
  if (hasStatus && status === 429) return { kind: "BACKPRESSURE", retry: true, status };
  if (response.backpressure === true && !hasStatus) {
    return { kind: "BACKPRESSURE", retry: true, status: null };
  }
  if (hasStatus && status >= 500 && status <= 599) return { kind: "UNAVAILABLE", retry: true, status };
  if (hasStatus) return { kind: "REJECTED", retry: false, status };
  return { kind: "UNAVAILABLE", retry: true, status: null };
}

async function sendWithBounds(transport, request, maxAttempts) {
  let lastKind = "UNAVAILABLE";
  let lastStatus = null;
  let attempts = 0;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    attempts = attempt;
    let response;
    try {
      response = await transport({
        endpoint: request.endpoint,
        body: request.body,
        attempt,
        timeoutMs: request.timeoutMs,
        headers: { "content-type": "application/json" },
      });
    } catch {
      lastKind = "UNAVAILABLE";
      lastStatus = null;
      continue;
    }
    const decision = classifyResponse(response);
    lastKind = decision.kind;
    lastStatus = decision.status;
    if (decision.kind === "ACCEPTED") {
      return { outcome: "ACCEPTED", attempts, status: lastStatus };
    }
    if (!decision.retry) break;
  }
  let outcome = "EXPORTER_UNAVAILABLE";
  if (lastKind === "BACKPRESSURE") outcome = "BACKPRESSURE_EXPORTER";
  else if (lastKind === "REJECTED") outcome = "EXPORTER_REJECTED";
  return { outcome, attempts, status: lastStatus };
}

function freezeDeep(value) {
  if (value === null || typeof value !== "object") return value;
  if (Array.isArray(value)) {
    for (const item of value) freezeDeep(item);
    return Object.freeze(value);
  }
  for (const key of Object.keys(value)) freezeDeep(value[key]);
  return Object.freeze(value);
}

function envelope(evaluated, fields) {
  const authority = evaluated.records.map((row) => row.authority);
  const eligibility = evaluated.records.map((row) => row.eligibility);
  return freezeDeep({
    producer_classification: POSTURE.producer_classification,
    adapter_id: POSTURE.adapter_id,
    mapping_id: POSTURE.mapping_id,
    mapping_version: POSTURE.mapping_version,
    schema_status: POSTURE.schema_status,
    schema_url: null,
    stable_schema: false,
    public_shipped_support: false,
    product_otlp_export_authorized: false,
    founder_decision_12: "unresolved",
    default_enabled: false,
    council: POSTURE.council,
    records_seen: evaluated.records_seen,
    authority,
    eligibility,
    ...fields,
  });
}

function idleDelivery(maxAttempts) {
  return {
    attempted: false,
    outcome: "NOT_ATTEMPTED",
    attempts: 0,
    max_attempts: maxAttempts,
    status: null,
    bytes_sent: 0,
    bytes_dropped: 0,
    endpoint_origin: null,
    path: null,
    drops: [],
  };
}

function plansFor(evaluated, indexes) {
  const byIndex = new Map(evaluated.records.map((row) => [row.eligibility.index, row.eligibility]));
  const plans = [];
  for (const index of indexes) {
    const entry = byIndex.get(index);
    if (!entry || entry.export_eligible !== true) return null;
    plans.push({
      traceId: entry.trace_id,
      spanId: entry.span_id,
      parentSpanId: entry.parent_span_id,
      name: entry.span_name,
      kind: entry.kind,
      startTimeUnixNano: entry.start_time_unix_nano,
      endTimeUnixNano: entry.end_time_unix_nano,
      attributes: entry.attributes,
      statusCode: entry.status_code,
    });
  }
  return plans;
}

function deliveryDrops(indexes, reason) {
  return indexes.map((index) => ({
    index,
    phase: "delivery",
    reason,
    operational: true,
    mapping_version: POSTURE.mapping_version,
  }));
}

async function exportOpticsRecords(records, options) {
  const settings = options && typeof options === "object" ? options : {};
  const evaluated = evaluateRecords(records);
  const gate = activation(settings);
  if (!gate.active) {
    return envelope(evaluated, {
      enabled: false,
      exported: false,
      reason: gate.reason,
      network: false,
      bytes_sent: 0,
      admission: emptyAdmission(),
      drops: [],
      delivery: idleDelivery(null),
    });
  }

  const queue = resolveQueue(settings);
  const admission = admit(evaluated.records, queue);
  const maxAttempts = resolveAttempts(settings);
  const timeoutMs = resolveTimeout(settings);

  if (credentialOptionPresent(settings)) {
    return envelope(evaluated, {
      enabled: true,
      exported: false,
      reason: "CREDENTIAL_OPTION_REJECTED",
      network: false,
      bytes_sent: 0,
      admission,
      drops: admission.drops,
      delivery: idleDelivery(maxAttempts),
    });
  }

  const endpoint = parseCustomerEndpoint(own(settings, "endpoint"));
  if (!endpoint.ok) {
    return envelope(evaluated, {
      enabled: true,
      exported: false,
      reason: endpoint.reason,
      network: false,
      bytes_sent: 0,
      admission,
      drops: admission.drops,
      delivery: idleDelivery(maxAttempts),
    });
  }

  const transport = own(settings, "transport") === undefined ? postOtlpJson : own(settings, "transport");
  if (typeof transport !== "function") {
    return envelope(evaluated, {
      enabled: true,
      exported: false,
      reason: "TRANSPORT_INVALID",
      network: false,
      bytes_sent: 0,
      admission,
      drops: admission.drops,
      delivery: idleDelivery(maxAttempts),
    });
  }

  if (admission.queued_indexes.length === 0) {
    return envelope(evaluated, {
      enabled: true,
      exported: false,
      reason: "NOTHING_TO_EXPORT",
      network: false,
      bytes_sent: 0,
      admission,
      drops: admission.drops,
      delivery: idleDelivery(maxAttempts),
    });
  }

  const plans = plansFor(evaluated, admission.queued_indexes);
  const body = plans ? encodeTraceRequest(plans) : "";
  if (!plans || !payloadAccepted(body)) {
    return envelope(evaluated, {
      enabled: true,
      exported: false,
      reason: "ENCODE_REJECTED",
      network: false,
      bytes_sent: 0,
      admission,
      drops: admission.drops,
      delivery: idleDelivery(maxAttempts),
    });
  }

  const sent = await sendWithBounds(transport, {
    endpoint: endpoint.url,
    body,
    timeoutMs,
  }, maxAttempts);
  const accepted = sent.outcome === "ACCEPTED";
  const byteLength = Buffer.byteLength(body);
  return envelope(evaluated, {
    enabled: true,
    exported: accepted,
    reason: sent.outcome,
    network: sent.attempts > 0,
    bytes_sent: accepted ? byteLength : 0,
    admission,
    drops: admission.drops,
    delivery: {
      attempted: sent.attempts > 0,
      outcome: sent.outcome,
      attempts: sent.attempts,
      max_attempts: maxAttempts,
      status: sent.status,
      bytes_sent: accepted ? byteLength : 0,
      bytes_dropped: accepted ? 0 : byteLength,
      endpoint_origin: sent.attempts > 0 ? endpoint.origin : null,
      path: sent.attempts > 0 ? endpoint.path : null,
      drops: accepted ? [] : deliveryDrops(admission.queued_indexes, sent.outcome),
    },
  });
}

module.exports = {
  exportOpticsRecords,
};
