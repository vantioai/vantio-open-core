"use strict";

const { RESERVED_RIGHTS, assertNever } = require("./boundary.cjs");
const { compositionDenial } = require("./compose.cjs");
const { inheritanceDenial } = require("./inheritance.cjs");
const {
  compositionKey,
  consumed,
  copyLedger,
  effectiveCeiling,
  scopeKeys,
  stepCountKey,
} = require("./ledger.cjs");
const { isUint, parseCatalog, parseEnvelope, parseLedger, parseStep } = require("./parse.cjs");
const { inputResult, toResult } = require("./result.cjs");

const RESERVED_SET = new Set(RESERVED_RIGHTS);
const INPUT_KEYS = Object.freeze(["envelope", "catalog", "ledger", "step", "now"]);

function sourceDenial(step, envelope) {
  switch (step.authority_source) {
    case "consensus":
      return {
        invariant: "CONSENSUS_IS_NOT_AUTHORIZATION",
        reason: "consensus_is_not_a_source",
        axis: "action",
      };
    case "process_count":
      return {
        invariant: "PROCESS_COUNT_IS_NOT_PRINCIPAL",
        reason: "process_count_is_not_a_source",
        axis: "lineage",
      };
    case "envelope":
      break;
    default:
      return assertNever(step.authority_source);
  }
  if (
    step.distinct_principal_per_process === true ||
    (step.principal_id !== null && step.principal_id !== envelope.principal_id)
  ) {
    return {
      invariant: "PROCESS_COUNT_IS_NOT_PRINCIPAL",
      reason: "process_does_not_mint_a_principal",
      axis: "lineage",
    };
  }
  return null;
}

function receiptTuple(envelope, step, receiptId) {
  return {
    receipt_id: receiptId,
    action: step.action,
    principal_id: envelope.principal_id,
    tenant_id: step.tenant_id,
    workload_id: step.workload_id,
    destination: step.destination,
    credential_id: step.credential_id,
    node_id: step.node_id,
    fleet_id: step.fleet_id,
    sequence_id: step.sequence_id,
    run_id: step.run_id,
    envelope_id: envelope.envelope_id,
  };
}

function replayDenial(step, ledger, envelope) {
  if (step.presented_receipt_id === null) return null;
  const prior = ledger.receipts[step.presented_receipt_id];
  if (!prior) {
    return {
      invariant: "NO_REPLAY_ACROSS_ACTIONS",
      reason: "unknown_receipt",
      axis: "action",
    };
  }
  if (prior.action !== step.action) {
    return {
      invariant: "NO_REPLAY_ACROSS_ACTIONS",
      reason: "cross_action",
      axis: "action",
    };
  }
  const presented = receiptTuple(envelope, step, step.presented_receipt_id);
  for (const key of Object.keys(presented)) {
    if (presented[key] !== prior[key]) {
      return {
        invariant: "NO_REPLAY_ACROSS_ACTIONS",
        reason: "cross_action_tuple",
        axis: "action",
      };
    }
  }
  return {
    invariant: "NO_REPLAY_ACROSS_ACTIONS",
    reason: "receipt_is_not_a_bearer_token",
    axis: "action",
  };
}

function revokedRecord(id, envelope, catalog) {
  const catalogRecord = catalog[id];
  if (catalogRecord && catalogRecord.state === "REVOKED") return true;
  return id === envelope.envelope_id && envelope.state === "REVOKED";
}

function revocationDenial(envelope, catalog, ledger) {
  if (envelope.state === "EXPIRED") {
    return { rule: "LIMIT", reason: "expired_state", axis: "time_window" };
  }
  const chain = envelope.lineage.concat([envelope.envelope_id]);
  for (const id of chain) {
    const mark = ledger.revocations[id];
    if (!mark && !revokedRecord(id, envelope, catalog)) continue;
    if (envelope.state === "ACTIVE") {
      return {
        invariant: "STALE_DESCENDANT_DOES_NOT_SURVIVE_PARENT_REVOCATION",
        reason: id === envelope.envelope_id ? "stale_self_after_revocation" : "stale_descendant_after_ancestor_revocation",
        axis: "lineage",
      };
    }
    return {
      invariant: "REVOCATION_REACHES_DESCENDANTS",
      reason: id === envelope.envelope_id ? "revoked_envelope" : "ancestor_revoked",
      axis: "lineage",
    };
  }
  if (envelope.parent_envelope_id !== null) {
    const parent = catalog[envelope.parent_envelope_id];
    if (parent && envelope.issued_against_parent_generation !== parent.generation) {
      return {
        invariant: "STALE_DESCENDANT_DOES_NOT_SURVIVE_PARENT_REVOCATION",
        reason: "parent_generation_drift",
        axis: "lineage",
      };
    }
  }
  if (envelope.state !== "ACTIVE") {
    return { rule: "INPUT_REJECTED", reason: "envelope_state", axis: null };
  }
  return null;
}

function actionDenial(envelope, step) {
  if (RESERVED_SET.has(step.action)) {
    const held = envelope.parent_envelope_id === null && envelope.reserved_rights_held.includes(step.action);
    if (!held) {
      return {
        invariant: "DELEGATION_CANNOT_CREATE_RESERVED_RIGHTS",
        reason: "reserved_right_not_held",
        axis: "action",
      };
    }
    return null;
  }
  if (!envelope.actions.includes(step.action)) {
    if (step.consensus !== null) {
      return {
        invariant: "CONSENSUS_IS_NOT_AUTHORIZATION",
        reason: "consensus_does_not_grant_action",
        axis: "action",
      };
    }
    return { rule: "LIMIT", reason: "action_not_granted", axis: "action" };
  }
  return null;
}

function revokeTargetDenial(envelope, catalog, step) {
  if (step.action !== "revoke_grant" && step.action !== "revoke_root") return null;
  if (step.revoke_target === null) {
    return { rule: "INPUT_REJECTED", reason: "revoke_target_required", axis: "lineage" };
  }
  const target = catalog[step.revoke_target];
  if (!target) return { rule: "INPUT_REJECTED", reason: "revoke_target_unknown", axis: "lineage" };
  if (envelope.lineage.includes(target.envelope_id)) {
    return {
      invariant: "CHILD_CANNOT_EXCEED_INHERITANCE",
      reason: "cannot_revoke_ancestor",
      axis: "lineage",
    };
  }
  const targetIsSelf = target.envelope_id === envelope.envelope_id;
  const targetIsDescendant = target.lineage.includes(envelope.envelope_id);
  if (!targetIsSelf && !targetIsDescendant) {
    return { rule: "LIMIT", reason: "revoke_target_outside_lineage", axis: "lineage" };
  }
  if (step.action === "revoke_root" && !targetIsSelf) {
    return {
      invariant: "DELEGATION_CANNOT_CREATE_RESERVED_RIGHTS",
      reason: "revoke_root_reaches_only_self",
      axis: "action",
    };
  }
  return { transition: target.envelope_id };
}

function membershipDenial(envelope, step) {
  if (step.tenant_id !== envelope.tenant_id) {
    return { rule: "LIMIT", reason: "tenant_not_in_envelope", axis: "tenant" };
  }
  if (step.fleet_id !== envelope.fleet_id) {
    return { rule: "LIMIT", reason: "fleet_not_in_envelope", axis: "fleet" };
  }
  if (!envelope.workload_ids.includes(step.workload_id)) {
    return { rule: "LIMIT", reason: "workload_not_in_envelope", axis: "workload" };
  }
  if (!envelope.node_ids.includes(step.node_id)) {
    return { rule: "LIMIT", reason: "node_not_in_envelope", axis: "node" };
  }
  if (step.destination !== null && !envelope.destinations.includes(step.destination)) {
    return { rule: "LIMIT", reason: "destination_not_in_envelope", axis: "destination" };
  }
  if (step.credential_id !== null && !envelope.credentials.includes(step.credential_id)) {
    return { rule: "LIMIT", reason: "credential_not_in_envelope", axis: "credential" };
  }
  return null;
}

function timeDenial(envelope, now) {
  if (now < envelope.not_before) {
    return { rule: "LIMIT", reason: "not_yet_valid", axis: "time_window" };
  }
  if (now >= envelope.not_after) {
    return { rule: "LIMIT", reason: "outside_window", axis: "time_window" };
  }
  return null;
}

function budgetDenial(envelope, catalog, ledger, step) {
  const units = step.resource_units;
  const actionCap = effectiveCeiling(envelope, catalog, "action");
  if (actionCap === null) return { rule: "INPUT_REJECTED", reason: "missing_ancestor", axis: "action" };
  if (units > envelope.ceilings.action || units > actionCap) {
    return { rule: "LIMIT", reason: "action_ceiling", axis: "action" };
  }
  for (const [axis, key] of scopeKeys(envelope, step)) {
    const cap = effectiveCeiling(envelope, catalog, axis);
    if (cap === null) return { rule: "INPUT_REJECTED", reason: "missing_ancestor", axis };
    const used = consumed(ledger, key);
    if (units > cap || used > cap - units) {
      return {
        invariant: "SPLIT_CANNOT_BYPASS_AGGREGATE",
        reason: "aggregate_ceiling",
        axis,
      };
    }
  }
  const countKey = stepCountKey(envelope, step);
  const count = ledger.step_counts[countKey] || 0;
  if (count >= envelope.max_steps) {
    return { rule: "LIMIT", reason: "sequence_step_ceiling", axis: "sequence" };
  }
  return null;
}

function commit(ledger, envelope, step) {
  const units = step.resource_units;
  for (const [, key] of scopeKeys(envelope, step)) {
    ledger.consumption[key] = consumed(ledger, key) + units;
  }
  const countKey = stepCountKey(envelope, step);
  ledger.step_counts[countKey] = (ledger.step_counts[countKey] || 0) + 1;
  const historyKey = compositionKey(envelope);
  if (!ledger.sequences[historyKey]) ledger.sequences[historyKey] = [];
  ledger.sequences[historyKey].push({
    action: step.action,
    credential_id: step.credential_id,
    destination: step.destination,
  });
  if (step.receipt_id === null) return null;
  const receipt = receiptTuple(envelope, step, step.receipt_id);
  ledger.receipts[step.receipt_id] = receipt;
  return receipt;
}

function deny(spec, ledger, envelope, step) {
  return toResult({
    disposition: "DENY",
    ledger,
    envelope_id: envelope ? envelope.envelope_id : null,
    principal_id: envelope ? envelope.principal_id : null,
    process_id: step ? step.process_id : null,
    consensus_ignored: Boolean(step && step.consensus && step.authority_source === "envelope" && spec.invariant !== "CONSENSUS_IS_NOT_AUTHORIZATION"),
    ...spec,
  });
}

function evaluate(input) {
  if (input === null || typeof input !== "object" || Array.isArray(input)) {
    return inputResult("evaluate_not_object");
  }
  const keys = Object.keys(input);
  for (const key of keys) {
    if (!INPUT_KEYS.includes(key)) return inputResult("evaluate_unknown_key");
  }
  for (const key of INPUT_KEYS) {
    if (!Object.prototype.hasOwnProperty.call(input, key)) return inputResult("evaluate_missing_" + key);
  }
  if (!isUint(input.now)) return inputResult("now");
  const envelopeParsed = parseEnvelope(input.envelope);
  if (!envelopeParsed.ok) return inputResult(envelopeParsed.reason);
  const catalogParsed = parseCatalog(input.catalog);
  if (!catalogParsed.ok) return inputResult(catalogParsed.reason);
  const ledgerParsed = parseLedger(input.ledger);
  if (!ledgerParsed.ok) return inputResult(ledgerParsed.reason);
  const stepParsed = parseStep(input.step);
  if (!stepParsed.ok) return inputResult(stepParsed.reason);

  const envelope = envelopeParsed.value;
  const catalog = catalogParsed.value;
  const ledger = ledgerParsed.value;
  const step = stepParsed.value;
  const held = copyLedger(ledger);

  const source = sourceDenial(step, envelope);
  if (source) return deny(source, held, envelope, step);
  const replay = replayDenial(step, held, envelope);
  if (replay) return deny(replay, held, envelope, step);
  const revoked = revocationDenial(envelope, catalog, held);
  if (revoked) return deny(revoked, held, envelope, step);
  const inherited = inheritanceDenial(envelope, catalog);
  if (inherited) return deny(inherited, held, envelope, step);
  const action = actionDenial(envelope, step);
  if (action) return deny(action, held, envelope, step);
  const target = revokeTargetDenial(envelope, catalog, step);
  if (target && target.transition === undefined) return deny(target, held, envelope, step);
  const time = timeDenial(envelope, input.now);
  if (time) return deny(time, held, envelope, step);
  const member = membershipDenial(envelope, step);
  if (member) return deny(member, held, envelope, step);
  const composed = compositionDenial(envelope, held, step);
  if (composed) return deny(composed, held, envelope, step);
  if (step.receipt_id !== null && held.receipts[step.receipt_id]) {
    return deny({ rule: "INPUT_REJECTED", reason: "duplicate_receipt", axis: "action" }, held, envelope, step);
  }
  const budget = budgetDenial(envelope, catalog, held, step);
  if (budget) return deny(budget, held, envelope, step);

  const receipt = commit(held, envelope, step);
  return toResult({
    disposition: "ALLOW",
    reason: "within_envelope",
    envelope_id: envelope.envelope_id,
    principal_id: envelope.principal_id,
    process_id: step.process_id,
    consensus_ignored: step.consensus !== null,
    ledger: held,
    receipt,
    revoke_transition: target && target.transition ? target.transition : null,
  });
}

module.exports = {
  evaluate,
};
