"use strict";

const { bindingCountsFor } = require("./evidence.cjs");
const { assessStaleness } = require("./staleness.cjs");

function satisfactionFor(control, bindings, context = {}) {
  const staleness = assessStaleness(control, context);
  if (staleness.stale) {
    return {
      status: "NOT_SATISFIED",
      reason: "STALE",
      pass: false,
      prior_pass: "CLEARED",
      staleness,
    };
  }
  if (control.implementation_state === "NOT_IMPLEMENTED" || control.implementation_state === "DESIGNED") {
    return {
      status: "NOT_SATISFIED",
      reason: "NOT_A_PASS",
      pass: false,
      prior_pass: "NOT_PROMOTED",
      staleness,
    };
  }
  const counting = bindings.filter((binding) => bindingCountsFor(binding, control));
  if (counting.length === 0) {
    return {
      status: "NOT_SATISFIED",
      reason: "NO_COUNTING_EVIDENCE",
      pass: false,
      prior_pass: "NOT_PROMOTED",
      staleness,
    };
  }
  return {
    status: "BOUND_WITH_LIMITS",
    reason: "EVIDENCE_BOUND_NOT_A_COMPLIANCE_PASS",
    pass: false,
    prior_pass: "NOT_PROMOTED",
    staleness,
    binding_ids: counting.map((binding) => binding.binding_id),
  };
}

function isUnsupported(control) {
  return control.primary_support === "NOT_IMPLEMENTED" || control.primary_support === "UNVERIFIED";
}

function isExternal(control) {
  return (
    control.primary_support === "CUSTOMER_PROVIDES" ||
    control.primary_support === "CUSTOMER_CONFIGURES" ||
    control.primary_support === "THIRD_PARTY_REQUIRED" ||
    control.primary_support === "NOT_APPLICABLE"
  );
}

module.exports = {
  isExternal,
  isUnsupported,
  satisfactionFor,
};
