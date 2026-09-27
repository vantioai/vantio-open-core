"use strict";

const { CONTROL_KEYS, DROPPED_KEYS, EFFECTS, HOST_PATTERN, ID_PATTERN } = require("./boundary.cjs");

function validId(value) {
  return typeof value === "string" && ID_PATTERN.test(value);
}

function validHost(value) {
  return typeof value === "string" && HOST_PATTERN.test(value);
}

function taintedKey(input) {
  return Object.keys(input).find((key) => {
    const lowered = key.toLowerCase();
    return DROPPED_KEYS.has(lowered) || CONTROL_KEYS.has(lowered);
  });
}

function structuralEvent(input, mode = "strip") {
  if (!input || typeof input !== "object" || Array.isArray(input)) return { ok: false, code: "BAD_INPUT" };
  if (mode === "reject" && taintedKey(input)) return { ok: false, code: "BAD_INPUT" };
  if (!validId(input.subject_ref)) return { ok: false, code: "BAD_INPUT" };
  if (!validHost(input.host)) return { ok: false, code: "BAD_INPUT" };
  if (!Number.isSafeInteger(input.byte_count) || input.byte_count < 0) return { ok: false, code: "BAD_INPUT" };
  if (!Number.isSafeInteger(input.at) || input.at < 0) return { ok: false, code: "BAD_INPUT" };
  return {
    ok: true,
    value: {
      subject_ref: input.subject_ref,
      host: input.host,
      byte_count: input.byte_count,
      at: input.at,
    },
  };
}

function validatePredicate(effect, predicate) {
  if (!EFFECTS.includes(effect)) return { ok: false, code: "BAD_EFFECT" };
  if (!predicate || typeof predicate !== "object" || Array.isArray(predicate)) {
    return { ok: false, code: "WIDE_PREDICATE" };
  }
  const next = {};
  if (Object.hasOwn(predicate, "host_equals")) {
    if (!validHost(predicate.host_equals)) return { ok: false, code: "BAD_INPUT" };
    next.host_equals = predicate.host_equals;
  }
  if (Object.hasOwn(predicate, "min_bytes")) {
    if (!Number.isSafeInteger(predicate.min_bytes) || predicate.min_bytes < 1) {
      return { ok: false, code: "BAD_INPUT" };
    }
    next.min_bytes = predicate.min_bytes;
  }
  if (effect === "DECLARED_HOST_MATCH" && !next.host_equals) return { ok: false, code: "WIDE_PREDICATE" };
  if (effect === "DECLARED_BYTE_CAP" && !next.min_bytes) return { ok: false, code: "WIDE_PREDICATE" };
  if (!next.host_equals && !next.min_bytes) return { ok: false, code: "WIDE_PREDICATE" };
  return { ok: true, value: next };
}

function matches(predicate, event) {
  if (predicate.host_equals && event.host !== predicate.host_equals) return false;
  if (typeof predicate.min_bytes === "number" && event.byte_count < predicate.min_bytes) return false;
  return true;
}

function impactOf(ruleId, label, decisions) {
  const subjects = new Set();
  let matched = 0;
  let unmatched = 0;
  let byteCountSum = 0;
  for (const decision of decisions) {
    if (decision.matched) {
      matched += 1;
      subjects.add(decision.subject_ref);
      byteCountSum += decision.byte_count;
    } else {
      unmatched += 1;
    }
  }
  return {
    rule_id: ruleId,
    label,
    matched,
    unmatched,
    distinct_subjects: subjects.size,
    byte_count_sum: byteCountSum,
  };
}

function uniqueIds(values, max) {
  if (!Array.isArray(values) || values.length < 1 || values.length > max) return null;
  const seen = new Set();
  for (const value of values) {
    if (!validId(value) || value === "*" || seen.has(value)) return null;
    seen.add(value);
  }
  return [...seen];
}

function isSuperset(larger, smaller) {
  const have = new Set(larger);
  return smaller.every((item) => have.has(item));
}

function isStrictSuperset(larger, smaller) {
  return isSuperset(larger, smaller) && larger.length > smaller.length;
}

module.exports = {
  impactOf,
  isStrictSuperset,
  isSuperset,
  matches,
  structuralEvent,
  uniqueIds,
  validHost,
  validId,
  validatePredicate,
};
