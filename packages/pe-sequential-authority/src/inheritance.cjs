"use strict";

const { LIMIT_AXES, RESERVED_DOMAINS, RESERVED_RIGHTS } = require("./boundary.cjs");

const RESERVED_SET = new Set(RESERVED_RIGHTS);
const RESERVED_DOMAIN_SET = new Set(RESERVED_DOMAINS);

function subset(childList, parentList) {
  for (const item of childList) {
    if (!parentList.includes(item)) return item;
  }
  return null;
}

function lineageChainDenial(envelope, catalog) {
  if (envelope.parent_envelope_id === null) {
    if (envelope.lineage.length !== 0) return "root_lineage_not_empty";
    if (envelope.issued_against_parent_generation !== null) return "root_parent_generation";
    return null;
  }
  if (envelope.lineage.length === 0) return "child_lineage_empty";
  if (envelope.lineage[envelope.lineage.length - 1] !== envelope.parent_envelope_id) {
    return "lineage_parent_mismatch";
  }
  let expectedParent = null;
  for (const id of envelope.lineage) {
    const ancestor = catalog[id];
    if (!ancestor) return "missing_ancestor";
    if (ancestor.parent_envelope_id !== expectedParent) return "lineage_chain_broken";
    expectedParent = id;
  }
  if (expectedParent !== envelope.parent_envelope_id) return "lineage_chain_broken";
  return null;
}

function inheritanceDenial(envelope, catalog) {
  const chain = lineageChainDenial(envelope, catalog);
  if (chain) return { rule: "INPUT_REJECTED", reason: chain, axis: "lineage" };
  if (envelope.parent_envelope_id === null) return null;
  const parent = catalog[envelope.parent_envelope_id];
  if (!parent) return { rule: "INPUT_REJECTED", reason: "missing_parent", axis: "lineage" };

  for (const action of envelope.actions) {
    if (RESERVED_SET.has(action)) {
      return {
        invariant: "DELEGATION_CANNOT_CREATE_RESERVED_RIGHTS",
        reason: "reserved_action_on_delegate",
        axis: "action",
      };
    }
  }
  for (const domain of envelope.domains) {
    if (RESERVED_DOMAIN_SET.has(domain)) {
      return {
        invariant: "DELEGATION_CANNOT_CREATE_RESERVED_RIGHTS",
        reason: "reserved_domain_on_delegate",
        axis: "lineage",
      };
    }
  }
  if (envelope.reserved_rights_held.length > 0) {
    return {
      invariant: "DELEGATION_CANNOT_CREATE_RESERVED_RIGHTS",
      reason: "reserved_rights_held_on_delegate",
      axis: "lineage",
    };
  }
  if (envelope.lineage.length > 1) {
    return { rule: "REDELEGATION_FORBIDDEN", reason: "redelegation_forbidden", axis: "lineage" };
  }

  if (subset(envelope.actions, parent.actions)) {
    return { invariant: "CHILD_CANNOT_EXCEED_INHERITANCE", reason: "action_outside_parent", axis: "action" };
  }
  if (subset(envelope.destinations, parent.destinations)) {
    return {
      invariant: "CHILD_CANNOT_EXCEED_INHERITANCE",
      reason: "destination_outside_parent",
      axis: "destination",
    };
  }
  if (subset(envelope.credentials, parent.credentials)) {
    return {
      invariant: "CHILD_CANNOT_EXCEED_INHERITANCE",
      reason: "credential_outside_parent",
      axis: "credential",
    };
  }
  if (subset(envelope.node_ids, parent.node_ids)) {
    return { invariant: "CHILD_CANNOT_EXCEED_INHERITANCE", reason: "node_outside_parent", axis: "node" };
  }
  if (subset(envelope.workload_ids, parent.workload_ids)) {
    return {
      invariant: "CHILD_CANNOT_EXCEED_INHERITANCE",
      reason: "workload_outside_parent",
      axis: "workload",
    };
  }
  if (subset(envelope.domains, parent.domains)) {
    return { invariant: "CHILD_CANNOT_EXCEED_INHERITANCE", reason: "domain_outside_parent", axis: "lineage" };
  }
  if (envelope.tenant_id !== parent.tenant_id) {
    return { invariant: "CHILD_CANNOT_EXCEED_INHERITANCE", reason: "tenant_outside_parent", axis: "tenant" };
  }
  if (envelope.fleet_id !== parent.fleet_id) {
    return { invariant: "CHILD_CANNOT_EXCEED_INHERITANCE", reason: "fleet_outside_parent", axis: "fleet" };
  }
  for (const pair of envelope.bound_uses) {
    const held = parent.bound_uses.some(
      (parentPair) =>
        parentPair.credential_id === pair.credential_id && parentPair.destination === pair.destination,
    );
    if (!held) {
      return {
        invariant: "CHILD_CANNOT_EXCEED_INHERITANCE",
        reason: "binding_outside_parent",
        axis: "credential",
      };
    }
  }
  for (const axis of LIMIT_AXES) {
    if (envelope.ceilings[axis] > parent.ceilings[axis]) {
      return {
        invariant: "CHILD_CANNOT_EXCEED_INHERITANCE",
        reason: "ceiling_above_parent",
        axis,
      };
    }
  }
  if (envelope.max_steps > parent.max_steps) {
    return {
      invariant: "CHILD_CANNOT_EXCEED_INHERITANCE",
      reason: "max_steps_above_parent",
      axis: "sequence",
    };
  }
  if (envelope.not_before < parent.not_before || envelope.not_after > parent.not_after) {
    return {
      invariant: "CHILD_CANNOT_EXCEED_INHERITANCE",
      reason: "window_outside_parent",
      axis: "time_window",
    };
  }
  return null;
}

module.exports = {
  inheritanceDenial,
};
