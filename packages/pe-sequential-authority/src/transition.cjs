"use strict";

const { RESERVED_DOMAINS, RESERVED_RIGHTS, assertNever } = require("./boundary.cjs");
const { inheritanceDenial } = require("./inheritance.cjs");
const { cloneEnvelope, copyLedger } = require("./ledger.cjs");
const { isId, isUint, parseCatalog, parseEnvelope, parseLedger, parseRequest } = require("./parse.cjs");
const { inputResult, toResult } = require("./result.cjs");

const RESERVED_SET = new Set(RESERVED_RIGHTS);
const RESERVED_DOMAIN_SET = new Set(RESERVED_DOMAINS);

function parentStateDenial(parent) {
  if (parent.state === "REVOKED") {
    return {
      invariant: "REVOCATION_REACHES_DESCENDANTS",
      reason: "revoked_parent_cannot_delegate",
      axis: "lineage",
    };
  }
  if (parent.state === "EXPIRED") {
    return { rule: "LIMIT", reason: "expired_parent_cannot_delegate", axis: "time_window" };
  }
  if (parent.state !== "ACTIVE") return { rule: "INPUT_REJECTED", reason: "envelope_state", axis: null };
  return null;
}

function causeDenial(cause) {
  switch (cause) {
    case "grant":
      return null;
    case "process_spawn":
      return {
        invariant: "PROCESS_COUNT_IS_NOT_PRINCIPAL",
        reason: "process_spawn_is_not_a_grant",
        axis: "lineage",
      };
    case "consensus":
      return {
        invariant: "CONSENSUS_IS_NOT_AUTHORIZATION",
        reason: "consensus_is_not_a_grant",
        axis: "action",
      };
    default:
      return assertNever(cause);
  }
}

function reservedRequestDenial(request) {
  for (const action of request.actions) {
    if (RESERVED_SET.has(action)) {
      return {
        invariant: "DELEGATION_CANNOT_CREATE_RESERVED_RIGHTS",
        reason: "delegation_cannot_create_reserved_right",
        axis: "action",
      };
    }
  }
  for (const domain of request.domains) {
    if (RESERVED_DOMAIN_SET.has(domain)) {
      return {
        invariant: "DELEGATION_CANNOT_CREATE_RESERVED_RIGHTS",
        reason: "delegation_cannot_create_reserved_domain",
        axis: "lineage",
      };
    }
  }
  return null;
}

function buildChild(parent, request) {
  return {
    envelope_id: request.envelope_id,
    principal_id: request.principal_id,
    tenant_id: request.tenant_id,
    workload_ids: request.workload_ids.slice(),
    fleet_id: request.fleet_id,
    node_ids: request.node_ids.slice(),
    parent_envelope_id: parent.envelope_id,
    lineage: parent.lineage.concat([parent.envelope_id]),
    generation: parent.generation,
    issued_against_parent_generation: parent.generation,
    domains: request.domains.slice(),
    actions: request.actions.slice(),
    destinations: request.destinations.slice(),
    credentials: request.credentials.slice(),
    bound_uses: request.bound_uses.map((pair) => ({
      credential_id: pair.credential_id,
      destination: pair.destination,
    })),
    not_before: request.not_before,
    not_after: request.not_after,
    redelegation: "forbidden",
    ceilings: { ...request.ceilings },
    max_steps: request.max_steps,
    state: "ACTIVE",
    reserved_rights_held: [],
  };
}

function proposeDelegation(parentInput, requestInput) {
  const parentParsed = parseEnvelope(parentInput);
  if (!parentParsed.ok) return inputResult(parentParsed.reason);
  const requestParsed = parseRequest(requestInput);
  if (!requestParsed.ok) return inputResult(requestParsed.reason);
  const parent = parentParsed.value;
  const request = requestParsed.value;
  const state = parentStateDenial(parent);
  if (state) {
    return toResult({
      disposition: "DENY",
      envelope_id: parent.envelope_id,
      principal_id: parent.principal_id,
      ...state,
    });
  }
  const cause = causeDenial(request.cause);
  if (cause) {
    return toResult({
      disposition: "DENY",
      envelope_id: parent.envelope_id,
      principal_id: parent.principal_id,
      ...cause,
    });
  }
  if (parent.parent_envelope_id !== null) {
    return toResult({
      disposition: "DENY",
      rule: "REDELEGATION_FORBIDDEN",
      reason: "redelegation_forbidden",
      axis: "lineage",
      envelope_id: parent.envelope_id,
      principal_id: parent.principal_id,
    });
  }
  const reserved = reservedRequestDenial(request);
  if (reserved) {
    return toResult({
      disposition: "DENY",
      envelope_id: parent.envelope_id,
      principal_id: parent.principal_id,
      ...reserved,
    });
  }
  const child = buildChild(parent, request);
  const checked = parseEnvelope(child);
  if (!checked.ok) return inputResult(checked.reason);
  const catalog = Object.create(null);
  catalog[parent.envelope_id] = parent;
  const inherited = inheritanceDenial(checked.value, catalog);
  if (inherited) {
    return toResult({
      disposition: "DENY",
      envelope_id: parent.envelope_id,
      principal_id: parent.principal_id,
      ...inherited,
    });
  }
  return toResult({
    disposition: "ALLOW",
    reason: "subset_grant",
    envelope_id: checked.value.envelope_id,
    principal_id: checked.value.principal_id,
    envelope: checked.value,
  });
}

function descendantIds(catalog, envelopeId) {
  const ids = [];
  for (const id of Object.keys(catalog)) {
    if (id === envelopeId || catalog[id].lineage.includes(envelopeId)) ids.push(id);
  }
  ids.sort();
  return ids;
}

function revoke(catalogInput, ledgerInput, envelopeId, now) {
  const catalogParsed = parseCatalog(catalogInput);
  if (!catalogParsed.ok) return inputResult(catalogParsed.reason);
  const ledgerParsed = parseLedger(ledgerInput);
  if (!ledgerParsed.ok) return inputResult(ledgerParsed.reason);
  if (!isId(envelopeId)) return inputResult("envelope_id");
  if (!isUint(now)) return inputResult("now");
  const catalog = catalogParsed.value;
  if (!catalog[envelopeId]) return inputResult("revoke_target_unknown");
  const ids = descendantIds(catalog, envelopeId);
  const nextCatalog = Object.create(null);
  for (const id of Object.keys(catalog)) nextCatalog[id] = cloneEnvelope(catalog[id]);
  const nextLedger = copyLedger(ledgerParsed.value);
  for (const id of ids) {
    const current = nextCatalog[id];
    if (current.generation >= Number.MAX_SAFE_INTEGER) return inputResult("generation_overflow");
    const generation = current.generation + 1;
    current.state = "REVOKED";
    current.generation = generation;
    nextLedger.revocations[id] = { generation, at: now };
  }
  return toResult({
    disposition: "ALLOW",
    reason: "revocation_recorded",
    envelope_id: envelopeId,
    catalog: nextCatalog,
    ledger: nextLedger,
    revoked_ids: ids,
  });
}

module.exports = {
  proposeDelegation,
  revoke,
};
