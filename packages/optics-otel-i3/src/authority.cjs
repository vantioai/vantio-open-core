"use strict";

const { POSTURE } = require("./boundary.cjs");
const { clockPair, errorTypeAgrees, revalidateCandidates, spanName, statusPlan } = require("./encode.cjs");
const { api } = require("./mapping_ref.cjs");
const { KNOWN_FIELDS, blockingReason, safeFieldName } = require("./names.cjs");

const BLOCK_PRIORITY = [
  "PROHIBITED_CONTENT",
  "CREDENTIAL_FIELD",
  "KERNEL_DETAIL_EXCLUDED",
  "COMPANY_OPS_EXCLUDED",
  "UNSUPPORTED_PROOF_EXCLUDED",
];

function code(value, fallback) {
  if (typeof value === "string" && /^[A-Z0-9_]{1,64}$/.test(value)) return value;
  return fallback;
}

function emptyAuthority(index, block) {
  return {
    index,
    mapping_id: POSTURE.mapping_id,
    mapping_version: POSTURE.mapping_version,
    schema_status: POSTURE.schema_status,
    operational: false,
    operational_block: block,
    blocking_reason: null,
    candidate_rejection: null,
    source_shape: null,
    evidence_origin: null,
    unknown_fields: [],
    rejected_field_names: 0,
    blocking_fields: [],
    candidates: {},
    span: { client: null, instrumentation: null },
    trace_context: null,
  };
}

function hex(value, length) {
  return typeof value === "string"
    && value.length === length
    && /^[0-9a-f]+$/.test(value)
    && value !== "0".repeat(length);
}

function copyTrace(trace) {
  if (!trace || typeof trace !== "object" || Array.isArray(trace)) return null;
  if (!hex(trace.trace_id, 32) || !hex(trace.span_id, 16)) return null;
  const copy = { trace_id: trace.trace_id, span_id: trace.span_id };
  if (Object.prototype.hasOwnProperty.call(trace, "parent_span_id")) {
    if (!hex(trace.parent_span_id, 16)) return null;
    copy.parent_span_id = trace.parent_span_id;
  }
  return copy;
}

function tokenOrNull(value, pattern) {
  if (typeof value !== "string") return null;
  if (!pattern.test(value)) return null;
  return value;
}

function inspectKeys(record) {
  const unknown = [];
  const blocking = [];
  const reasons = new Set();
  let rejected = 0;
  for (const key of Object.keys(record)) {
    const safe = safeFieldName(key);
    if (safe == null) {
      rejected += 1;
      continue;
    }
    const reason = blockingReason(safe);
    if (reason) {
      blocking.push(safe);
      reasons.add(reason);
      continue;
    }
    if (!KNOWN_FIELDS.has(safe)) unknown.push(safe);
  }
  unknown.sort();
  blocking.sort();
  let blockingReasonChosen = null;
  for (const candidate of BLOCK_PRIORITY) {
    if (reasons.has(candidate)) {
      blockingReasonChosen = candidate;
      break;
    }
  }
  return {
    unknown_fields: unknown,
    blocking_fields: blocking,
    blocking_reason: blockingReasonChosen,
    rejected_field_names: rejected,
  };
}

function spanTokens(preview) {
  const client = preview && preview.span ? preview.span.client : null;
  const instrumentation = preview && preview.span ? preview.span.instrumentation : null;
  return {
    client: client === "OK" || client === "ERROR" ? client : null,
    instrumentation: instrumentation === "ERROR" ? instrumentation : null,
    unrecognized: (client != null && client !== "OK" && client !== "ERROR")
      || (instrumentation != null && instrumentation !== "ERROR"),
  };
}

function authorityFromPreview(index, record, preview, keys) {
  const previewOperational = preview.would_be_operational_if_i3_enabled === true;
  const span = spanTokens(preview);
  let operational = previewOperational;
  let operationalBlock = previewOperational ? null : code(preview.operational_block, "NOT_OPERATIONAL");
  if (operational && keys.blocking_reason) {
    operational = false;
    operationalBlock = keys.blocking_reason;
  } else if (operational && keys.rejected_field_names > 0) {
    operational = false;
    operationalBlock = "FIELD_NAME_REJECTED";
  } else if (operational && span.unrecognized) {
    operational = false;
    operationalBlock = "STATUS_UNRECOGNIZED";
  }

  let candidates = {};
  let candidateRejection = null;
  let trace = null;
  let spanView = { client: null, instrumentation: null };
  if (operational) {
    const checked = revalidateCandidates(preview.candidates);
    if (!checked.ok) {
      candidateRejection = code(checked.reason, "CANDIDATE_REJECTED");
    } else {
      candidates = checked.attributes;
      trace = copyTrace(preview.trace_context);
      spanView = { client: span.client, instrumentation: span.instrumentation };
    }
  }

  return {
    index,
    mapping_id: POSTURE.mapping_id,
    mapping_version: POSTURE.mapping_version,
    schema_status: POSTURE.schema_status,
    operational,
    operational_block: operationalBlock,
    blocking_reason: keys.blocking_reason,
    candidate_rejection: candidateRejection,
    source_shape: tokenOrNull(record.source_shape, /^(live_display|canonical_observation)$/),
    evidence_origin: tokenOrNull(record.evidence_origin, /^[A-Z0-9_]{1,64}$/),
    unknown_fields: keys.unknown_fields,
    rejected_field_names: keys.rejected_field_names,
    blocking_fields: keys.blocking_fields,
    candidates,
    span: spanView,
    trace_context: trace,
  };
}

function evaluateOne(record, index) {
  if (record === null || typeof record !== "object" || Array.isArray(record)) {
    return {
      authority: emptyAuthority(index, "RECORD_NOT_OBJECT"),
      eligibility: {
        index,
        export_eligible: false,
        operational: false,
        reason: "RECORD_NOT_OBJECT",
      },
    };
  }
  let keys;
  let preview;
  try {
    keys = inspectKeys(record);
    preview = api.preview(record);
  } catch {
    return {
      authority: emptyAuthority(index, "RECORD_UNREADABLE"),
      eligibility: {
        index,
        export_eligible: false,
        operational: false,
        reason: "RECORD_UNREADABLE",
      },
    };
  }
  const authority = authorityFromPreview(index, record, preview, keys);
  return { authority, eligibility: eligibilityFor(record, authority) };
}

function eligibilityFor(record, authority) {
  const base = {
    index: authority.index,
    export_eligible: false,
    operational: authority.operational,
    reason: null,
  };
  if (!authority.operational) {
    base.reason = authority.operational_block || "NOT_OPERATIONAL";
    return base;
  }
  if (authority.candidate_rejection) {
    base.reason = authority.candidate_rejection;
    return base;
  }
  const plan = statusPlan(authority.span.client, authority.span.instrumentation);
  if (!plan.ok) {
    base.reason = plan.reason;
    return base;
  }
  if (!errorTypeAgrees(authority.candidates, authority.span.client, authority.span.instrumentation)) {
    base.reason = "ERROR_TYPE_MISMATCH";
    return base;
  }
  if (!authority.trace_context) {
    base.reason = "TRACE_CONTEXT_NOT_ELIGIBLE";
    return base;
  }
  const start = Object.prototype.hasOwnProperty.call(record, "start_time_unix_nano")
    ? record.start_time_unix_nano
    : null;
  const end = Object.prototype.hasOwnProperty.call(record, "end_time_unix_nano")
    ? record.end_time_unix_nano
    : null;
  const clock = clockPair(start, end);
  if (!clock.ok) {
    base.reason = clock.reason;
    return base;
  }
  return {
    index: authority.index,
    export_eligible: true,
    operational: true,
    reason: null,
    attributes: authority.candidates,
    span_name: spanName(authority.candidates),
    kind: plan.kind,
    status_code: plan.statusCode,
    trace_id: authority.trace_context.trace_id,
    span_id: authority.trace_context.span_id,
    parent_span_id: authority.trace_context.parent_span_id || null,
    start_time_unix_nano: clock.start,
    end_time_unix_nano: clock.end,
  };
}

function evaluateRecords(records) {
  const list = Array.isArray(records) ? records : [];
  const rows = [];
  for (let index = 0; index < list.length; index += 1) {
    rows.push(evaluateOne(list[index], index));
  }
  return {
    mapping_id: POSTURE.mapping_id,
    mapping_version: POSTURE.mapping_version,
    schema_status: POSTURE.schema_status,
    records_seen: list.length,
    records: rows,
  };
}

module.exports = {
  evaluateRecords,
};
