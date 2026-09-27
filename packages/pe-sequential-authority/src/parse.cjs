"use strict";

const {
  AUTHORITY_SOURCES,
  DOMAIN_NAMES,
  LIMIT_AXES,
  MAX_COLLECTION,
  RESERVED_RIGHTS,
  STATES,
} = require("./boundary.cjs");

const ID_RE = /^[A-Za-z0-9._:-]{1,128}$/;
const BANNED_IDS = new Set(["__proto__", "constructor", "prototype"]);
const RESERVED_SET = new Set(RESERVED_RIGHTS);

const ENVELOPE_KEYS = Object.freeze([
  "envelope_id",
  "principal_id",
  "tenant_id",
  "workload_ids",
  "fleet_id",
  "node_ids",
  "parent_envelope_id",
  "lineage",
  "generation",
  "issued_against_parent_generation",
  "domains",
  "actions",
  "destinations",
  "credentials",
  "bound_uses",
  "not_before",
  "not_after",
  "redelegation",
  "ceilings",
  "max_steps",
  "state",
  "reserved_rights_held",
]);

const STEP_REQUIRED = Object.freeze([
  "step_id",
  "action",
  "authority_source",
  "sequence_id",
  "run_id",
  "process_id",
  "workload_id",
  "tenant_id",
  "node_id",
  "fleet_id",
  "resource_units",
]);

const STEP_OPTIONAL = Object.freeze([
  "destination",
  "credential_id",
  "receipt_id",
  "presented_receipt_id",
  "consensus",
  "raises_ceiling",
  "composed_effect",
  "revoke_target",
  "distinct_principal_per_process",
  "principal_id",
]);

const REQUEST_KEYS = Object.freeze([
  "envelope_id",
  "principal_id",
  "cause",
  "tenant_id",
  "workload_ids",
  "fleet_id",
  "node_ids",
  "domains",
  "actions",
  "destinations",
  "credentials",
  "bound_uses",
  "not_before",
  "not_after",
  "ceilings",
  "max_steps",
]);

const LEDGER_KEYS = Object.freeze([
  "consumption",
  "receipts",
  "revocations",
  "sequences",
  "step_counts",
]);

const EFFECT_KEYS = Object.freeze(["action", "credential_id", "destination"]);
const RECEIPT_KEYS = Object.freeze([
  "receipt_id",
  "action",
  "principal_id",
  "tenant_id",
  "workload_id",
  "destination",
  "credential_id",
  "node_id",
  "fleet_id",
  "sequence_id",
  "run_id",
  "envelope_id",
]);
const REVOCATION_KEYS = Object.freeze(["generation", "at"]);
const BOUND_KEYS = Object.freeze(["credential_id", "destination"]);
const CONSENSUS_KEYS = Object.freeze(["agents"]);

function reject(reason) {
  return { ok: false, reason };
}

function isPlainObject(value) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}

function unknownKey(value, allowed) {
  const allow = new Set(allowed);
  for (const key of Object.keys(value)) {
    if (!allow.has(key)) return key;
  }
  return null;
}

function missingKey(value, required) {
  for (const key of required) {
    if (!Object.prototype.hasOwnProperty.call(value, key)) return key;
  }
  return null;
}

function isId(value) {
  return typeof value === "string" && BANNED_IDS.has(value) === false && ID_RE.test(value);
}

function isUint(value) {
  return typeof value === "number" && Number.isInteger(value) && value >= 0 && value <= Number.MAX_SAFE_INTEGER;
}

function idList(value, field) {
  if (!Array.isArray(value)) return reject(field + "_not_list");
  if (value.length > MAX_COLLECTION) return reject(field + "_too_long");
  const out = [];
  const seen = new Set();
  for (const item of value) {
    if (!isId(item)) return reject(field + "_bad_id");
    if (seen.has(item)) return reject(field + "_duplicate");
    seen.add(item);
    out.push(item);
  }
  return { ok: true, value: out };
}

function parseCeilings(value) {
  if (!isPlainObject(value)) return reject("ceilings_not_object");
  const extra = unknownKey(value, LIMIT_AXES);
  if (extra) return reject("ceilings_unknown_key");
  const missing = missingKey(value, LIMIT_AXES);
  if (missing) return reject("ceilings_missing_" + missing);
  const ceilings = {};
  for (const axis of LIMIT_AXES) {
    if (!isUint(value[axis])) return reject("ceilings_bad_" + axis);
    ceilings[axis] = value[axis];
  }
  return { ok: true, value: ceilings };
}

function parseBoundUses(value) {
  if (!Array.isArray(value)) return reject("bound_uses_not_list");
  if (value.length > MAX_COLLECTION) return reject("bound_uses_too_long");
  const out = [];
  const seen = new Set();
  for (const item of value) {
    if (!isPlainObject(item)) return reject("bound_use_not_object");
    if (unknownKey(item, BOUND_KEYS) || missingKey(item, BOUND_KEYS)) return reject("bound_use_keys");
    if (!isId(item.credential_id) || !isId(item.destination)) return reject("bound_use_bad_id");
    const pair = item.credential_id + "\0" + item.destination;
    if (seen.has(pair)) return reject("bound_use_duplicate");
    seen.add(pair);
    out.push({ credential_id: item.credential_id, destination: item.destination });
  }
  return { ok: true, value: out };
}

function parseDomains(value) {
  const listed = idList(value, "domains");
  if (!listed.ok) return listed;
  if (listed.value.length === 0) return reject("domains_empty");
  for (const domain of listed.value) {
    if (!DOMAIN_NAMES.includes(domain)) return reject("unknown_domain");
  }
  return listed;
}

function parseEnvelope(value) {
  if (!isPlainObject(value)) return reject("envelope_not_object");
  if (unknownKey(value, ENVELOPE_KEYS)) return reject("envelope_unknown_key");
  const missing = missingKey(value, ENVELOPE_KEYS);
  if (missing) return reject("envelope_missing_" + missing);
  if (!isId(value.envelope_id)) return reject("envelope_id");
  if (!isId(value.principal_id)) return reject("principal_id");
  if (!isId(value.tenant_id)) return reject("tenant_id");
  if (!isId(value.fleet_id)) return reject("fleet_id");
  const workloadIds = idList(value.workload_ids, "workload_ids");
  if (!workloadIds.ok) return workloadIds;
  const nodeIds = idList(value.node_ids, "node_ids");
  if (!nodeIds.ok) return nodeIds;
  const lineage = idList(value.lineage, "lineage");
  if (!lineage.ok) return lineage;
  const domains = parseDomains(value.domains);
  if (!domains.ok) return domains;
  const actions = idList(value.actions, "actions");
  if (!actions.ok) return actions;
  for (const action of actions.value) {
    if (RESERVED_SET.has(action)) return reject("reserved_listed_as_ordinary_action");
  }
  const destinations = idList(value.destinations, "destinations");
  if (!destinations.ok) return destinations;
  const credentials = idList(value.credentials, "credentials");
  if (!credentials.ok) return credentials;
  const boundUses = parseBoundUses(value.bound_uses);
  if (!boundUses.ok) return boundUses;
  const reserved = idList(value.reserved_rights_held, "reserved_rights_held");
  if (!reserved.ok) return reserved;
  for (const right of reserved.value) {
    if (!RESERVED_SET.has(right)) return reject("unknown_reserved_right");
  }
  if (value.parent_envelope_id !== null && !isId(value.parent_envelope_id)) return reject("parent_envelope_id");
  if (!isUint(value.generation)) return reject("generation");
  if (value.issued_against_parent_generation !== null && !isUint(value.issued_against_parent_generation)) {
    return reject("issued_against_parent_generation");
  }
  if (!isUint(value.not_before) || !isUint(value.not_after)) return reject("window");
  if (value.not_before >= value.not_after) return reject("window_order");
  if (value.redelegation !== "forbidden") return reject("redelegation_not_forbidden");
  if (!isUint(value.max_steps)) return reject("max_steps");
  if (!STATES.includes(value.state)) return reject("state");
  const ceilings = parseCeilings(value.ceilings);
  if (!ceilings.ok) return ceilings;
  for (const pair of boundUses.value) {
    if (!credentials.value.includes(pair.credential_id) || !destinations.value.includes(pair.destination)) {
      return reject("bound_use_outside_envelope");
    }
  }
  return {
    ok: true,
    value: {
      envelope_id: value.envelope_id,
      principal_id: value.principal_id,
      tenant_id: value.tenant_id,
      workload_ids: workloadIds.value,
      fleet_id: value.fleet_id,
      node_ids: nodeIds.value,
      parent_envelope_id: value.parent_envelope_id,
      lineage: lineage.value,
      generation: value.generation,
      issued_against_parent_generation: value.issued_against_parent_generation,
      domains: domains.value,
      actions: actions.value,
      destinations: destinations.value,
      credentials: credentials.value,
      bound_uses: boundUses.value,
      not_before: value.not_before,
      not_after: value.not_after,
      redelegation: "forbidden",
      ceilings: ceilings.value,
      max_steps: value.max_steps,
      state: value.state,
      reserved_rights_held: reserved.value,
    },
  };
}

function optionalId(value, field) {
  if (value === undefined || value === null) return { ok: true, value: null };
  if (!isId(value)) return reject(field);
  return { ok: true, value };
}

function parseConsensus(value) {
  if (value === undefined || value === null) return { ok: true, value: null };
  if (!isPlainObject(value)) return reject("consensus_not_object");
  if (unknownKey(value, CONSENSUS_KEYS) || missingKey(value, CONSENSUS_KEYS)) return reject("consensus_keys");
  const agents = idList(value.agents, "consensus_agents");
  if (!agents.ok) return agents;
  return { ok: true, value: { agents: agents.value } };
}

function parseStep(value) {
  if (!isPlainObject(value)) return reject("step_not_object");
  const allowed = STEP_REQUIRED.concat(STEP_OPTIONAL);
  if (unknownKey(value, allowed)) return reject("step_unknown_key");
  const missing = missingKey(value, STEP_REQUIRED);
  if (missing) return reject("step_missing_" + missing);
  if (!isId(value.step_id)) return reject("step_id");
  if (!isId(value.action)) return reject("action");
  if (!AUTHORITY_SOURCES.includes(value.authority_source)) return reject("unknown_authority_source");
  if (!isId(value.sequence_id) || !isId(value.run_id) || !isId(value.process_id)) return reject("correlation_id");
  if (!isId(value.workload_id) || !isId(value.tenant_id) || !isId(value.node_id) || !isId(value.fleet_id)) {
    return reject("scope_id");
  }
  if (!isUint(value.resource_units)) return reject("resource_units");
  const destination = optionalId(value.destination, "destination");
  if (!destination.ok) return destination;
  const credentialId = optionalId(value.credential_id, "credential_id");
  if (!credentialId.ok) return credentialId;
  const receiptId = optionalId(value.receipt_id, "receipt_id");
  if (!receiptId.ok) return receiptId;
  const presented = optionalId(value.presented_receipt_id, "presented_receipt_id");
  if (!presented.ok) return presented;
  if (receiptId.value !== null && presented.value !== null) return reject("receipt_and_presentation");
  const consensus = parseConsensus(value.consensus);
  if (!consensus.ok) return consensus;
  const principalId = optionalId(value.principal_id, "principal_id");
  if (!principalId.ok) return principalId;
  const composed = optionalId(value.composed_effect, "composed_effect");
  if (!composed.ok) return composed;
  const revokeTarget = optionalId(value.revoke_target, "revoke_target");
  if (!revokeTarget.ok) return revokeTarget;
  if (value.raises_ceiling !== undefined && typeof value.raises_ceiling !== "boolean") return reject("raises_ceiling");
  if (
    value.distinct_principal_per_process !== undefined &&
    typeof value.distinct_principal_per_process !== "boolean"
  ) {
    return reject("distinct_principal_per_process");
  }
  return {
    ok: true,
    value: {
      step_id: value.step_id,
      action: value.action,
      authority_source: value.authority_source,
      sequence_id: value.sequence_id,
      run_id: value.run_id,
      process_id: value.process_id,
      workload_id: value.workload_id,
      tenant_id: value.tenant_id,
      node_id: value.node_id,
      fleet_id: value.fleet_id,
      resource_units: value.resource_units,
      destination: destination.value,
      credential_id: credentialId.value,
      receipt_id: receiptId.value,
      presented_receipt_id: presented.value,
      consensus: consensus.value,
      raises_ceiling: value.raises_ceiling === true,
      composed_effect: composed.value,
      revoke_target: revokeTarget.value,
      distinct_principal_per_process: value.distinct_principal_per_process === true,
      principal_id: principalId.value,
    },
  };
}

function parseEffect(value) {
  if (!isPlainObject(value)) return reject("effect_not_object");
  if (unknownKey(value, EFFECT_KEYS) || missingKey(value, EFFECT_KEYS)) return reject("effect_keys");
  if (!isId(value.action)) return reject("effect_action");
  if (value.credential_id !== null && !isId(value.credential_id)) return reject("effect_credential");
  if (value.destination !== null && !isId(value.destination)) return reject("effect_destination");
  return {
    ok: true,
    value: {
      action: value.action,
      credential_id: value.credential_id,
      destination: value.destination,
    },
  };
}

function parseReceipt(value) {
  if (!isPlainObject(value)) return reject("receipt_not_object");
  if (unknownKey(value, RECEIPT_KEYS) || missingKey(value, RECEIPT_KEYS)) return reject("receipt_keys");
  const out = {};
  for (const key of RECEIPT_KEYS) {
    if (key === "destination" || key === "credential_id") {
      if (value[key] !== null && !isId(value[key])) return reject("receipt_" + key);
      out[key] = value[key];
      continue;
    }
    if (!isId(value[key])) return reject("receipt_" + key);
    out[key] = value[key];
  }
  return { ok: true, value: out };
}

function parseRevocation(value) {
  if (!isPlainObject(value)) return reject("revocation_not_object");
  if (unknownKey(value, REVOCATION_KEYS) || missingKey(value, REVOCATION_KEYS)) return reject("revocation_keys");
  if (!isUint(value.generation) || value.generation < 1) return reject("revocation_generation");
  if (!isUint(value.at)) return reject("revocation_at");
  return { ok: true, value: { generation: value.generation, at: value.at } };
}

function parseMap(value, parseItem, field) {
  if (!isPlainObject(value)) return reject(field + "_not_object");
  const keys = Object.keys(value);
  if (keys.length > MAX_COLLECTION) return reject(field + "_too_long");
  const out = Object.create(null);
  for (const key of keys) {
    if (BANNED_IDS.has(key)) return reject(field + "_bad_key");
    const item = parseItem(value[key], key);
    if (!item.ok) return item;
    out[key] = item.value;
  }
  return { ok: true, value: out };
}

function parseLedger(value) {
  if (!isPlainObject(value)) return reject("ledger_not_object");
  if (unknownKey(value, LEDGER_KEYS) || missingKey(value, LEDGER_KEYS)) return reject("ledger_keys");
  const consumption = parseMap(value.consumption, (item) => {
    if (!isUint(item)) return reject("consumption_value");
    return { ok: true, value: item };
  }, "consumption");
  if (!consumption.ok) return consumption;
  const receipts = parseMap(value.receipts, (item, key) => {
    const receipt = parseReceipt(item);
    if (!receipt.ok) return receipt;
    if (receipt.value.receipt_id !== key) return reject("receipt_key_mismatch");
    return receipt;
  }, "receipts");
  if (!receipts.ok) return receipts;
  const revocations = parseMap(value.revocations, (item) => parseRevocation(item), "revocations");
  if (!revocations.ok) return revocations;
  const sequences = parseMap(value.sequences, (item) => {
    if (!Array.isArray(item)) return reject("sequence_not_list");
    if (item.length > MAX_COLLECTION) return reject("sequence_too_long");
    const effects = [];
    for (const effect of item) {
      const parsed = parseEffect(effect);
      if (!parsed.ok) return parsed;
      effects.push(parsed.value);
    }
    return { ok: true, value: effects };
  }, "sequences");
  if (!sequences.ok) return sequences;
  const stepCounts = parseMap(value.step_counts, (item) => {
    if (!isUint(item)) return reject("step_count_value");
    return { ok: true, value: item };
  }, "step_counts");
  if (!stepCounts.ok) return stepCounts;
  return {
    ok: true,
    value: {
      consumption: consumption.value,
      receipts: receipts.value,
      revocations: revocations.value,
      sequences: sequences.value,
      step_counts: stepCounts.value,
    },
  };
}

function parseCatalog(value) {
  if (!isPlainObject(value)) return reject("catalog_not_object");
  const keys = Object.keys(value);
  if (keys.length > MAX_COLLECTION) return reject("catalog_too_long");
  const out = Object.create(null);
  for (const key of keys) {
    if (!isId(key)) return reject("catalog_bad_key");
    const envelope = parseEnvelope(value[key]);
    if (!envelope.ok) return envelope;
    if (envelope.value.envelope_id !== key) return reject("catalog_key_mismatch");
    out[key] = envelope.value;
  }
  return { ok: true, value: out };
}

function parseRequest(value) {
  if (!isPlainObject(value)) return reject("request_not_object");
  if (unknownKey(value, REQUEST_KEYS)) return reject("request_unknown_key");
  const missing = missingKey(value, REQUEST_KEYS);
  if (missing) return reject("request_missing_" + missing);
  if (!isId(value.envelope_id) || !isId(value.principal_id) || !isId(value.tenant_id) || !isId(value.fleet_id)) {
    return reject("request_id");
  }
  if (value.cause !== "grant" && value.cause !== "process_spawn" && value.cause !== "consensus") {
    return reject("unknown_cause");
  }
  const workloadIds = idList(value.workload_ids, "workload_ids");
  if (!workloadIds.ok) return workloadIds;
  const nodeIds = idList(value.node_ids, "node_ids");
  if (!nodeIds.ok) return nodeIds;
  const domains = parseDomains(value.domains);
  if (!domains.ok) return domains;
  const actions = idList(value.actions, "actions");
  if (!actions.ok) return actions;
  const destinations = idList(value.destinations, "destinations");
  if (!destinations.ok) return destinations;
  const credentials = idList(value.credentials, "credentials");
  if (!credentials.ok) return credentials;
  const boundUses = parseBoundUses(value.bound_uses);
  if (!boundUses.ok) return boundUses;
  if (!isUint(value.not_before) || !isUint(value.not_after) || value.not_before >= value.not_after) {
    return reject("window_order");
  }
  if (!isUint(value.max_steps)) return reject("max_steps");
  const ceilings = parseCeilings(value.ceilings);
  if (!ceilings.ok) return ceilings;
  return {
    ok: true,
    value: {
      envelope_id: value.envelope_id,
      principal_id: value.principal_id,
      cause: value.cause,
      tenant_id: value.tenant_id,
      workload_ids: workloadIds.value,
      fleet_id: value.fleet_id,
      node_ids: nodeIds.value,
      domains: domains.value,
      actions: actions.value,
      destinations: destinations.value,
      credentials: credentials.value,
      bound_uses: boundUses.value,
      not_before: value.not_before,
      not_after: value.not_after,
      ceilings: ceilings.value,
      max_steps: value.max_steps,
    },
  };
}

function emptyLedger() {
  return {
    consumption: Object.create(null),
    receipts: Object.create(null),
    revocations: Object.create(null),
    sequences: Object.create(null),
    step_counts: Object.create(null),
  };
}

module.exports = {
  emptyLedger,
  isId,
  isUint,
  parseCatalog,
  parseEnvelope,
  parseLedger,
  parseRequest,
  parseStep,
};
