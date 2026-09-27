"use strict";

const boundary = require("./boundary.cjs");
const { composeWiden, envelopesEqual, normalizeEnvelope, removed, subsetViolations, tightenTo } = require("./envelope.cjs");
const {
  distinct,
  hasConsensusSignal,
  hasRoleSignal,
  isHash,
  isSafeId,
  parseTime,
  scanRecord,
} = require("./scan.cjs");

const REJECTED = new Set(boundary.REJECTED_ACTS);
const RECOVERY_MODE = new Set(boundary.RECOVERY_MODES);
const CLASSES = new Set(boundary.APPROVAL_CLASSES);
const KINDS = new Set(["customer", "workload", "vantio"]);
const RESERVED = new Set(boundary.RESERVED_POWERS);
const WRITER_SOURCES = new Set([
  "approver_click",
  "billing",
  "console",
  "dry_run",
  "enterprise_writer",
  "support",
]);

function base(store, outcome, reason, extra) {
  const body = {
    outcome,
    reason,
    host_effect: "NONE",
    host_contacted: false,
    verified_on_host: false,
    live_customer_authority: false,
    external_identity_created: false,
    credential_created: false,
    identity_authenticated: false,
    role_used_as_proof: false,
    agent_consensus_counted: false,
    title_holder: store && store.root ? store.root.title_holder : null,
    vantio_sufficient: false,
    active_set_by_enterprise_writer: false,
    evaluation_only: true,
    satisfies_host_proof: false,
    schema_status: boundary.SCHEMA_STATUS,
    schema_version: boundary.SCHEMA_VERSION,
    duration_limit: "NOT_SET",
    decisions_resolved: false,
  };
  if (extra) Object.assign(body, extra);
  body.host_effect = "NONE";
  body.host_contacted = false;
  body.verified_on_host = false;
  body.live_customer_authority = false;
  body.external_identity_created = false;
  body.credential_created = false;
  body.identity_authenticated = false;
  body.role_used_as_proof = false;
  body.agent_consensus_counted = false;
  body.vantio_sufficient = false;
  body.active_set_by_enterprise_writer = false;
  body.evaluation_only = true;
  body.satisfies_host_proof = false;
  body.decisions_resolved = false;
  body.schema_status = boundary.SCHEMA_STATUS;
  body.schema_version = boundary.SCHEMA_VERSION;
  body.duration_limit = "NOT_SET";
  return body;
}

function assertStore(store) {
  if (!store || store.marker !== boundary.STORE_MARKER) {
    throw new TypeError("customer-held store required");
  }
}

function mint(store, prefix) {
  store.seq += 1;
  return `${prefix}-${store.seq}`;
}

function identityOf(store, id) {
  return store.identities.get(id) || null;
}

function rejectedAct(input) {
  if (!input || typeof input !== "object") return null;
  if (typeof input.act === "string" && REJECTED.has(input.act)) return input.act;
  if (input.dry_run_as_activation === true) return "dry_run_activation";
  if (input.second_enforcement_engine === true) return "second_enforcement_engine";
  return null;
}

function screen(store, input) {
  const prohibited = scanRecord(input);
  if (prohibited) return base(store, "REFUSED", prohibited);
  const act = rejectedAct(input);
  if (act) return base(store, "REJECTED", act.toUpperCase());
  return null;
}

function requireRoot(store) {
  if (!store.root) return base(store, "REFUSED", "ROOT_REQUIRED");
  return null;
}

function hostedWriteBlocked(store) {
  if (!store.available) return base(store, "REFUSED", "STORE_UNAVAILABLE_NO_WIDEN");
  return null;
}

function freezeBlocksWiden(store) {
  if (store.freeze) return base(store, "REFUSED", "FREEZE_RECORDED");
  return null;
}

function partyList(input) {
  if (!input || !Array.isArray(input.parties)) return null;
  return input.parties;
}

function knownKind(store, id) {
  if (!isSafeId(id)) return { ok: false, reason: "IDENTITY_ID_INVALID" };
  const identity = identityOf(store, id);
  if (!identity) return { ok: false, reason: "UNKNOWN_IDENTITY" };
  return { ok: true, identity };
}

function insideEnvelope(store, id) {
  if (store.root.root_ids.includes(id)) return true;
  return store.root.recognized_ids.includes(id);
}

function checkWidenParties(store, parties, recipient) {
  if (!Array.isArray(parties)) return base(store, "REFUSED", "PARTIES_REQUIRED");
  if (parties.some((id) => !isSafeId(id))) return base(store, "REFUSED", "IDENTITY_ID_INVALID");
  if (distinct(parties).length !== parties.length) {
    return base(store, "REJECTED", "SAME_PERSON_DUAL_CONTROL");
  }
  if (parties.length !== 2) return base(store, "REFUSED", "WIDEN_QUORUM_EXACTLY_TWO");
  for (const id of parties) {
    const known = knownKind(store, id);
    if (!known.ok) return base(store, "REFUSED", known.reason);
    if (known.identity.kind === "workload") return base(store, "REJECTED", "WORKLOAD_SELF_APPROVAL");
    if (known.identity.kind === "vantio") return base(store, "REJECTED", "VANTIO_NOT_A_SATISFYING_PARTY");
    if (known.identity.kind !== "customer") return base(store, "REFUSED", "UNKNOWN_IDENTITY");
    if (!insideEnvelope(store, id)) return base(store, "REFUSED", "NOT_INSIDE_ENVELOPE");
    if (recipient && id === recipient) return base(store, "REJECTED", "SELF_APPROVAL");
  }
  return null;
}

function checkRootParties(store, parties) {
  if (!Array.isArray(parties) || parties.length < 1) return base(store, "REFUSED", "PARTIES_REQUIRED");
  if (parties.some((id) => !isSafeId(id))) return base(store, "REFUSED", "IDENTITY_ID_INVALID");
  const unique = distinct(parties);
  if (unique.length !== parties.length) return base(store, "REJECTED", "SAME_PERSON_DUAL_CONTROL");
  for (const id of unique) {
    const known = knownKind(store, id);
    if (!known.ok) return base(store, "REFUSED", known.reason);
    if (known.identity.kind === "workload") return base(store, "REJECTED", "WORKLOAD_SELF_APPROVAL");
    if (known.identity.kind === "vantio") return base(store, "REJECTED", "VANTIO_NOT_A_SATISFYING_PARTY");
    if (!store.root.root_ids.includes(id)) return base(store, "REFUSED", "DELEGATE_CANNOT_ROOT");
  }
  return null;
}

function checkSingleCustomer(store, parties, { allowRecovery = false, allowReadGrant = false } = {}) {
  if (!Array.isArray(parties)) return { refusal: base(store, "REFUSED", "PARTIES_REQUIRED") };
  if (parties.length !== 1) return { refusal: base(store, "REFUSED", "SINGLE_PARTY_REQUIRED") };
  const id = parties[0];
  const known = knownKind(store, id);
  if (!known.ok) return { refusal: base(store, "REFUSED", known.reason) };
  if (known.identity.kind === "workload") {
    return { refusal: base(store, "REJECTED", "WORKLOAD_SELF_APPROVAL") };
  }
  if (known.identity.kind === "vantio") {
    return { refusal: base(store, "REJECTED", "VANTIO_NOT_A_SATISFYING_PARTY") };
  }
  const isRoot = store.root.root_ids.includes(id);
  const isRecovery = store.root.recovery_ids.includes(id);
  if (isRoot || (allowRecovery && isRecovery)) return { id, isRoot, isRecovery };
  if (allowReadGrant && openReadGrant(store, id)) return { id, isRoot: false, isRecovery: false };
  return { refusal: base(store, "REFUSED", "PARTY_CANNOT_EXERCISE") };
}

function ignoreNonProof(store, input) {
  const parties = input && Array.isArray(input.parties) ? input.parties : null;
  const noParties = !parties || parties.length === 0;
  if (noParties && hasConsensusSignal(input)) return base(store, "REFUSED", "CONSENSUS_IS_NOT_APPROVAL");
  if (noParties && hasRoleSignal(input)) return base(store, "REFUSED", "ROLE_IS_NOT_IDENTITY_PROOF");
  return null;
}

function classOf(input) {
  if (!input || !Object.prototype.hasOwnProperty.call(input, "class")) return { missing: true };
  const value = input.class;
  if (typeof value !== "string" || value.length === 0) return { missing: true };
  if (!CLASSES.has(value)) return { unknown: true };
  return { value };
}

function witnessIds(input) {
  if (!input || !Object.prototype.hasOwnProperty.call(input, "witness_ids")) return [];
  if (!Array.isArray(input.witness_ids)) return null;
  return input.witness_ids;
}

function pushApproval(store, fields) {
  const approval = {
    approval_id: mint(store, "a"),
    class: fields.className,
    subject: fields.subject,
    parties: fields.parties.slice(),
    witness_ids: fields.witnessIds.slice(),
    witness_counts_toward_quorum: false,
    quorum_count: fields.parties.length,
    scope: fields.scope || null,
    version: store.approvalVersion + 1,
    rollback_target: fields.rollback || null,
    not_after: fields.notAfter || null,
    state: "APPROVED",
    identity_authenticated: false,
    agent_consensus_counted: false,
    role_counted_as_proof: false,
    can_authorize_host: false,
  };
  store.approvalVersion = approval.version;
  store.approvals.push(approval);
  return approval;
}

function createCustomerHeldStore() {
  return {
    marker: boundary.STORE_MARKER,
    seq: 0,
    approvalVersion: 0,
    available: true,
    identities: new Map(),
    root: null,
    grants: new Map(),
    approvals: [],
    host_intents: [],
    evidence: [],
    leave_intents: [],
    freeze: null,
    worm: false,
    spanner_selected: false,
    identity_provider_selected: false,
  };
}

function acceptOpaqueIdentity(store, input) {
  assertStore(store);
  const blocked = screen(store, input);
  if (blocked) return blocked;
  if (!input || !isSafeId(input.id)) return base(store, "REFUSED", "IDENTITY_ID_INVALID");
  if (!KINDS.has(input.kind)) return base(store, "REFUSED", "ROLE_IS_NOT_IDENTITY_KIND");
  const existing = identityOf(store, input.id);
  if (existing && existing.kind !== input.kind) return base(store, "REFUSED", "IDENTITY_KIND_CONFLICT");
  if (!existing) store.identities.set(input.id, { id: input.id, kind: input.kind });
  return base(store, "RECORDED", "OPAQUE_HANDLE_RECORDED", { id: input.id, kind: input.kind });
}

function foundRoot(store, input) {
  assertStore(store);
  const blocked = screen(store, input);
  if (blocked) return blocked;
  if (store.root) return base(store, "REFUSED", "ROOT_ALREADY_FOUNDED");
  const down = hostedWriteBlocked(store);
  if (down) return down;
  if (!input || !isSafeId(input.root_identity)) return base(store, "REFUSED", "IDENTITY_ID_INVALID");
  const known = knownKind(store, input.root_identity);
  if (!known.ok) return base(store, "REFUSED", known.reason);
  if (known.identity.kind === "vantio") return base(store, "REJECTED", "VANTIO_NOT_IN_ROOT_SET");
  if (known.identity.kind === "workload") return base(store, "REJECTED", "WORKLOAD_NOT_ROOT");
  const ceiling = normalizeEnvelope(input.authority_ceiling);
  if (!ceiling.ok) return base(store, "REFUSED", ceiling.reason);
  const policy = normalizeEnvelope(input.initial_policy);
  if (!policy.ok) return base(store, "REFUSED", policy.reason);
  const over = subsetViolations(policy.envelope, ceiling.envelope);
  if (over.length) return base(store, "REFUSED", "POLICY_EXCEEDS_CEILING", { violations: over });
  store.root = {
    root_ids: [input.root_identity],
    recovery_ids: [],
    recognized_ids: [input.root_identity],
    witness_present: false,
    witness_counts_toward_quorum: false,
    title_holder: "customer_root",
    title_domains: boundary.DOMAINS.slice(),
    authority_ceiling: ceiling.envelope,
    policy: policy.envelope,
    policy_version: 1,
    open_widens: [],
    reserved_powers: boundary.RESERVED_POWERS.slice(),
  };
  const approval = pushApproval(store, {
    className: "ROOT",
    subject: "found_root",
    parties: [input.root_identity],
    witnessIds: [],
    scope: policy.envelope,
    rollback: null,
    notAfter: null,
  });
  return base(store, "RECORDED", "ROOT_FOUNDED", {
    title_holder: "customer_root",
    root_ids: store.root.root_ids.slice(),
    vantio_in_root_set: false,
    workload_authority_expanded: false,
    approval_id: approval.approval_id,
  });
}

function recordRecognizedCustomer(store, input) {
  assertStore(store);
  const blocked = screen(store, input) || requireRoot(store) || hostedWriteBlocked(store);
  if (blocked) return blocked;
  const klass = classOf(input);
  if (klass.missing) return base(store, "REFUSED", "MISSING_CLASS");
  if (klass.unknown || klass.value !== "ROOT") return base(store, "REFUSED", "ROOT_CLASS_REQUIRED");
  const rootCheck = checkRootParties(store, partyList(input));
  if (rootCheck) return rootCheck;
  if (!input || !isSafeId(input.customer_id)) return base(store, "REFUSED", "IDENTITY_ID_INVALID");
  const known = knownKind(store, input.customer_id);
  if (!known.ok) return base(store, "REFUSED", known.reason);
  if (known.identity.kind === "vantio") return base(store, "REJECTED", "VANTIO_NOT_A_SATISFYING_PARTY");
  if (known.identity.kind === "workload") return base(store, "REFUSED", "WORKLOAD_CANNOT_BE_RECOGNIZED");
  if (!store.root.recognized_ids.includes(input.customer_id)) {
    store.root.recognized_ids.push(input.customer_id);
  }
  return base(store, "RECORDED", "CUSTOMER_RECOGNIZED", {
    customer_id: input.customer_id,
    in_root_set: store.root.root_ids.includes(input.customer_id),
    grant_minted: false,
  });
}

function changeOwnerSet(store, input) {
  assertStore(store);
  const blocked = screen(store, input) || requireRoot(store) || hostedWriteBlocked(store);
  if (blocked) return blocked;
  const klass = classOf(input);
  if (klass.missing) return base(store, "REFUSED", "MISSING_CLASS");
  if (klass.unknown || klass.value !== "ROOT") return base(store, "REFUSED", "ROOT_CLASS_REQUIRED");
  const rootCheck = checkRootParties(store, partyList(input));
  if (rootCheck) return rootCheck;
  const add = Array.isArray(input.add) ? input.add : [];
  const remove = Array.isArray(input.remove) ? input.remove : [];
  for (const id of add.concat(remove)) {
    if (!isSafeId(id)) return base(store, "REFUSED", "IDENTITY_ID_INVALID");
  }
  const next = store.root.root_ids.slice();
  for (const id of remove) {
    const index = next.indexOf(id);
    if (index >= 0) next.splice(index, 1);
  }
  for (const id of add) {
    const known = knownKind(store, id);
    if (!known.ok) return base(store, "REFUSED", known.reason);
    if (known.identity.kind === "vantio") return base(store, "REJECTED", "VANTIO_NOT_IN_ROOT_SET");
    if (known.identity.kind === "workload") return base(store, "REJECTED", "WORKLOAD_NOT_ROOT");
    if (!next.includes(id)) next.push(id);
  }
  if (next.length < 1) return base(store, "REFUSED", "ROOT_SET_EMPTY");
  store.root.root_ids = next;
  for (const id of next) {
    if (!store.root.recognized_ids.includes(id)) store.root.recognized_ids.push(id);
  }
  store.root.title_holder = "customer_root";
  pushApproval(store, {
    className: "ROOT",
    subject: "owner_set",
    parties: distinct(input.parties),
    witnessIds: [],
    scope: null,
    rollback: null,
    notAfter: null,
  });
  return base(store, "APPROVED", "OWNER_SET_RECORDED", {
    root_ids: next.slice(),
    vantio_in_root_set: false,
  });
}

function nameRecoveryParty(store, input) {
  assertStore(store);
  const blocked = screen(store, input) || requireRoot(store) || hostedWriteBlocked(store);
  if (blocked) return blocked;
  const klass = classOf(input);
  if (klass.missing) return base(store, "REFUSED", "MISSING_CLASS");
  if (klass.unknown || klass.value !== "ROOT") return base(store, "REFUSED", "ROOT_CLASS_REQUIRED");
  const rootCheck = checkRootParties(store, partyList(input));
  if (rootCheck) return rootCheck;
  if (!input || !isSafeId(input.party_id)) return base(store, "REFUSED", "IDENTITY_ID_INVALID");
  const known = knownKind(store, input.party_id);
  if (!known.ok) return base(store, "REFUSED", known.reason);
  if (known.identity.kind === "vantio") return base(store, "REJECTED", "VANTIO_CANNOT_BE_RECOVERY_PARTY");
  if (known.identity.kind === "workload") return base(store, "REFUSED", "WORKLOAD_CANNOT_BE_RECOVERY_PARTY");
  if (!store.root.recovery_ids.includes(input.party_id)) store.root.recovery_ids.push(input.party_id);
  pushApproval(store, {
    className: "ROOT",
    subject: "recovery_party",
    parties: distinct(input.parties),
    witnessIds: [],
    scope: null,
    rollback: null,
    notAfter: null,
  });
  return base(store, "APPROVED", "RECOVERY_PARTY_NAMED", {
    recovery_ids: store.root.recovery_ids.slice(),
    root_can_still_recover: true,
  });
}

function removeWitness(store, input) {
  assertStore(store);
  const blocked = screen(store, input) || requireRoot(store) || hostedWriteBlocked(store);
  if (blocked) return blocked;
  const klass = classOf(input);
  if (klass.missing) return base(store, "REFUSED", "MISSING_CLASS");
  if (klass.unknown || klass.value !== "ROOT") return base(store, "REFUSED", "ROOT_CLASS_REQUIRED");
  const rootCheck = checkRootParties(store, partyList(input));
  if (rootCheck) return rootCheck;
  store.root.witness_present = false;
  store.root.witness_counts_toward_quorum = false;
  pushApproval(store, {
    className: "ROOT",
    subject: "remove_witness",
    parties: distinct(input.parties),
    witnessIds: [],
    scope: null,
    rollback: null,
    notAfter: null,
  });
  return base(store, "APPROVED", "WITNESS_REMOVED", {
    vantio_credential_required: false,
    title_holder: "customer_root",
  });
}

function recordHostIntent(store, input) {
  assertStore(store);
  const blocked = screen(store, input) || requireRoot(store) || hostedWriteBlocked(store);
  if (blocked) return blocked;
  const klass = classOf(input);
  if (klass.missing) return base(store, "REFUSED", "MISSING_CLASS");
  if (klass.unknown || klass.value !== "ROOT") return base(store, "REFUSED", "ROOT_CLASS_REQUIRED");
  const rootCheck = checkRootParties(store, partyList(input));
  if (rootCheck) return rootCheck;
  if (!input || (input.intent !== "enroll" && input.intent !== "retire")) {
    return base(store, "REFUSED", "HOST_INTENT_INVALID");
  }
  if (!isSafeId(input.host_id)) return base(store, "REFUSED", "HOST_ID_INVALID");
  const record = {
    intent_id: mint(store, "hi"),
    intent: input.intent,
    host_id: input.host_id,
    enrolled: false,
    protected: false,
    enforced: false,
    mechanism: "PHANTOM_ENGINE_ON_CUSTOMER_HOST",
    performed_here: false,
    retire_contradiction: input.intent === "retire" ? "VISIBLE_UNRESOLVED" : null,
  };
  store.host_intents.push(record);
  pushApproval(store, {
    className: "ROOT",
    subject: record.intent_id,
    parties: distinct(input.parties),
    witnessIds: [],
    scope: null,
    rollback: null,
    notAfter: null,
  });
  return base(store, "RECORDED", "HOST_INTENT_RECORDED", {
    intent: record,
    host_enrolled: false,
    host_protected: false,
    host_enforced: false,
  });
}

function requireEnvelope(input, key) {
  return normalizeEnvelope(input ? input[key] : undefined);
}

function grantCurrentlyOpen(grant) {
  return grant.state === "APPROVED"
    && grant.can_exercise === true
    && grant.record_layer_exercise === "OPEN";
}

function openSecurityGrant(store, actor) {
  for (const grant of store.grants.values()) {
    if (!grantCurrentlyOpen(grant)) continue;
    if (grant.domain !== "security" || grant.delegate !== actor) continue;
    return grant;
  }
  return null;
}

function openReadGrant(store, actor) {
  for (const grant of store.grants.values()) {
    if (!grantCurrentlyOpen(grant)) continue;
    if (grant.delegate !== actor) continue;
    if (grant.scope.actions.includes("read")) return grant;
  }
  return null;
}

function exerciseAtApproval(notBeforeMs, notAfterMs) {
  const now = Date.now();
  if (now >= notAfterMs) {
    return { can_exercise: false, record_layer_exercise: "ENDED" };
  }
  if (now < notBeforeMs) {
    return { can_exercise: false, record_layer_exercise: "NOT_YET" };
  }
  return { can_exercise: true, record_layer_exercise: "OPEN" };
}

function narrowInsideGrant(current, next, grant) {
  if (removed(current.domains, next.domains).length || removed(next.domains, current.domains).length) {
    return "DELEGATE_CANNOT_CHANGE_DOMAINS";
  }
  const hostCuts = removed(current.hosts, next.hosts);
  const destinationCuts = removed(current.destinations, next.destinations);
  const actionCuts = removed(current.actions, next.actions);
  if (hostCuts.some((item) => !grant.scope.hosts.includes(item))) return "OUTSIDE_GRANT";
  if (destinationCuts.some((item) => !grant.scope.destinations.includes(item))) return "OUTSIDE_GRANT";
  if (actionCuts.some((item) => !grant.scope.actions.includes(item))) return "OUTSIDE_GRANT";
  return null;
}

function recordPolicyDecision(store, input) {
  assertStore(store);
  const blocked = screen(store, input) || requireRoot(store) || hostedWriteBlocked(store);
  if (blocked) return blocked;
  const klass = classOf(input);
  if (klass.missing) return base(store, "REFUSED", "MISSING_CLASS");
  if (klass.unknown) return base(store, "REFUSED", "UNKNOWN_CLASS");
  if (klass.value !== "NARROW" && klass.value !== "WIDEN" && klass.value !== "ROOT") {
    return base(store, "REFUSED", "CLASS_DOES_NOT_AUTHORIZE_POLICY");
  }
  const nonProof = ignoreNonProof(store, input);
  if (nonProof) return nonProof;
  const next = requireEnvelope(input, "next_policy");
  if (!next.ok) return base(store, "REFUSED", next.reason);
  const witnesses = witnessIds(input);
  if (witnesses === null) return base(store, "REFUSED", "WITNESS_LIST_INVALID");
  const current = store.root.policy;
  const ceiling = store.root.authority_ceiling;
  let parties = [];
  if (klass.value === "WIDEN") {
    const frozen = freezeBlocksWiden(store);
    if (frozen) return frozen;
    if (!input.not_after) return base(store, "REFUSED", "EXPIRY_REQUIRED");
    const notAfter = parseTime(input.not_after);
    const notBefore = input.not_before ? parseTime(input.not_before) : null;
    if (notAfter == null) return base(store, "REFUSED", "EXPIRY_INVALID");
    if (input.not_before && (notBefore == null || notAfter <= notBefore)) {
      return base(store, "REFUSED", "EXPIRY_NOT_AFTER_START");
    }
    const widenParties = checkWidenParties(store, partyList(input), null);
    if (widenParties) return widenParties;
    if (subsetViolations(next.envelope, ceiling).length) {
      return base(store, "REFUSED", "EXCEEDS_ROOT_ENVELOPE", {
        violations: subsetViolations(next.envelope, ceiling),
      });
    }
    if (subsetViolations(current, next.envelope).length) return base(store, "REFUSED", "NOT_A_PURE_WIDEN");
    if (envelopesEqual(current, next.envelope)) return base(store, "REFUSED", "NOT_A_WIDEN");
    const rollback = requireEnvelope(input, "rollback_target");
    if (!rollback.ok) return base(store, "REFUSED", "ROLLBACK_TARGET_REQUIRED");
    if (subsetViolations(rollback.envelope, current).length) {
      return base(store, "REFUSED", "ROLLBACK_WIDER_THAN_CURRENT");
    }
    parties = distinct(input.parties);
    const nowMs = Date.now();
    const windowEnded = notAfter <= nowMs;
    const deferred = !windowEnded && notBefore != null && notBefore > nowMs;
    const approval = pushApproval(store, {
      className: "WIDEN",
      subject: "policy",
      parties,
      witnessIds: witnesses,
      scope: next.envelope,
      rollback: rollback.envelope,
      notAfter: input.not_after,
    });
    if (windowEnded) {
      return base(store, "APPROVED", "POLICY_WIDEN_ENDED", {
        policy_version: store.root.policy_version,
        enterprise_state: "APPROVED",
        host_state: null,
        approval_id: approval.approval_id,
        policy_applied: false,
      });
    }
    if (!deferred) {
      store.root.policy = next.envelope;
      store.root.policy_version += 1;
    }
    store.root.open_widens.push({
      version: store.root.policy_version,
      not_before_ms: notBefore,
      not_after_ms: notAfter,
      baseline: current,
      next_policy: next.envelope,
      rollback_target: rollback.envelope,
      applied: !deferred,
    });
    return base(store, "APPROVED", deferred ? "POLICY_WIDEN_DEFERRED" : "POLICY_WIDENED", {
      policy_version: store.root.policy_version,
      enterprise_state: "APPROVED",
      host_state: null,
      approval_id: approval.approval_id,
      policy_applied: !deferred,
    });
  }
  if (subsetViolations(next.envelope, current).length) {
    return base(store, "REFUSED", "NOT_NARROW", { violations: subsetViolations(next.envelope, current) });
  }
  if (envelopesEqual(current, next.envelope)) return base(store, "REFUSED", "NOT_A_CHANGE");
  if (klass.value === "ROOT") {
    const rootCheck = checkRootParties(store, partyList(input));
    if (rootCheck) return rootCheck;
  } else {
    const listed = partyList(input);
    if (!Array.isArray(listed) || listed.length !== 1) return base(store, "REFUSED", "SINGLE_PARTY_REQUIRED");
    const known = knownKind(store, listed[0]);
    if (!known.ok) return base(store, "REFUSED", known.reason);
    if (known.identity.kind === "workload") return base(store, "REJECTED", "WORKLOAD_SELF_APPROVAL");
    if (known.identity.kind === "vantio") return base(store, "REJECTED", "VANTIO_NOT_A_SATISFYING_PARTY");
    if (!store.root.root_ids.includes(listed[0])) {
      const grant = openSecurityGrant(store, listed[0]);
      if (!grant) return base(store, "REFUSED", "SECURITY_GRANT_REQUIRED");
      const outside = narrowInsideGrant(current, next.envelope, grant);
      if (outside) return base(store, "REFUSED", outside);
    }
  }
  parties = distinct(input.parties);
  store.root.policy = next.envelope;
  store.root.policy_version += 1;
  const approval = pushApproval(store, {
    className: klass.value,
    subject: "policy",
    parties,
    witnessIds: witnesses,
    scope: next.envelope,
    rollback: current,
    notAfter: null,
  });
  return base(store, "APPROVED", "POLICY_NARROWED", {
    policy_version: store.root.policy_version,
    enterprise_state: "APPROVED",
    host_state: null,
    approval_id: approval.approval_id,
  });
}

function exclusiveToVantio(input) {
  if (!input || !Object.prototype.hasOwnProperty.call(input, "exclusive_to_vantio")) return [];
  if (!Array.isArray(input.exclusive_to_vantio)) return null;
  return input.exclusive_to_vantio;
}

function proposeGrant(store, input) {
  assertStore(store);
  const blocked = screen(store, input) || requireRoot(store) || hostedWriteBlocked(store);
  if (blocked) return blocked;
  const frozen = freezeBlocksWiden(store);
  if (frozen) return frozen;
  const klass = classOf(input);
  if (klass.missing) return base(store, "REFUSED", "MISSING_CLASS");
  if (klass.unknown) return base(store, "REFUSED", "UNKNOWN_CLASS");
  if (klass.value !== "WIDEN") return base(store, "REFUSED", "GRANT_REQUIRES_WIDEN");
  const nonProof = ignoreNonProof(store, input);
  if (nonProof) return nonProof;
  if (input.redelegation && input.redelegation !== "forbidden") {
    return base(store, "REFUSED", "REDELEGATION_NOT_ALLOWED");
  }
  if (!isSafeId(input.delegator) || !isSafeId(input.delegate)) {
    return base(store, "REFUSED", "IDENTITY_ID_INVALID");
  }
  if (input.delegator === input.delegate) return base(store, "REJECTED", "SELF_APPROVAL");
  const delegator = knownKind(store, input.delegator);
  const delegate = knownKind(store, input.delegate);
  if (!delegator.ok) return base(store, "REFUSED", delegator.reason);
  if (!delegate.ok) return base(store, "REFUSED", delegate.reason);
  if (!store.root.root_ids.includes(input.delegator)) {
    return base(store, "REFUSED", "REDELEGATION_FORBIDDEN");
  }
  if (delegator.identity.kind === "workload" || delegator.identity.kind === "vantio") {
    return base(store, "REFUSED", "DELEGATOR_CANNOT_GRANT");
  }
  if (!boundary.DOMAINS.includes(input.domain)) return base(store, "REFUSED", "UNKNOWN_DOMAIN");
  if (delegate.identity.kind === "workload" && input.domain !== "workload") {
    return base(store, "REFUSED", "WORKLOAD_CANNOT_HOLD_SECURITY_OR_RECOVERY");
  }
  if (delegate.identity.kind === "vantio") return base(store, "REJECTED", "VANTIO_NOT_A_SATISFYING_PARTY");
  if (typeof input.purpose !== "string" || input.purpose.length < 1 || input.purpose.length > 200) {
    return base(store, "REFUSED", "PURPOSE_REQUIRED");
  }
  const notBefore = parseTime(input.not_before);
  const notAfter = parseTime(input.not_after);
  if (notBefore == null || notAfter == null) return base(store, "REFUSED", "EXPIRY_REQUIRED");
  if (notAfter <= notBefore) return base(store, "REFUSED", "EXPIRY_NOT_AFTER_START");
  const scope = normalizeEnvelope(input.scope);
  if (!scope.ok) return base(store, "REFUSED", scope.reason);
  if (!scope.envelope.domains.includes(input.domain)) return base(store, "REFUSED", "SCOPE_DOMAIN_MISSING");
  if (delegate.identity.kind === "workload" && scope.envelope.domains.some((item) => item !== "workload")) {
    return base(store, "REFUSED", "WORKLOAD_CANNOT_HOLD_SECURITY_OR_RECOVERY");
  }
  if (delegate.identity.kind === "workload" && scope.envelope.actions.some((item) => RESERVED.has(item))) {
    return base(store, "REFUSED", "WORKLOAD_CANNOT_HOLD_RESERVED_POWER");
  }
  const subset = subsetViolations(scope.envelope, store.root.policy);
  if (subset.length) return base(store, "REFUSED", "NOT_A_DELEGATION_WIDENS", { violations: subset });
  const rollback = requireEnvelope(input, "rollback_target");
  if (!rollback.ok) return base(store, "REFUSED", "ROLLBACK_TARGET_REQUIRED");
  if (subsetViolations(rollback.envelope, store.root.policy).length) {
    return base(store, "REFUSED", "ROLLBACK_WIDER_THAN_CURRENT");
  }
  const exclusive = exclusiveToVantio(input);
  if (exclusive === null) return base(store, "REFUSED", "EXCLUSIVE_LIST_INVALID");
  if (exclusive.some((item) => RESERVED.has(item))) return base(store, "REFUSED", "GRANT_HANDS_POWER_TO_VANTIO");
  const witnesses = witnessIds(input);
  if (witnesses === null) return base(store, "REFUSED", "WITNESS_LIST_INVALID");
  const widenParties = checkWidenParties(store, partyList(input), input.delegate);
  if (widenParties && widenParties.outcome === "REJECTED") return widenParties;
  const grant = {
    grant_id: mint(store, "g"),
    delegator: input.delegator,
    delegate: input.delegate,
    domain: input.domain,
    scope: scope.envelope,
    purpose: input.purpose,
    not_before: input.not_before,
    not_after: input.not_after,
    not_before_ms: notBefore,
    not_after_ms: notAfter,
    redelegation: "forbidden",
    approval_class: "WIDEN",
    rollback_target: rollback.envelope,
    state: "PROPOSED",
    can_exercise: false,
    record_layer_exercise: "CLOSED",
    host_quote: null,
    host_expanded_authority_cleared: "UNSATISFIED",
    version: store.root.policy_version,
  };
  if (widenParties) {
    store.grants.set(grant.grant_id, grant);
    return base(store, "PROPOSED", widenParties.reason, {
      grant_id: grant.grant_id,
      can_exercise: false,
      enterprise_state: "PROPOSED",
    });
  }
  const exercise = exerciseAtApproval(notBefore, notAfter);
  grant.state = "APPROVED";
  grant.can_exercise = exercise.can_exercise;
  grant.record_layer_exercise = exercise.record_layer_exercise;
  store.grants.set(grant.grant_id, grant);
  const approval = pushApproval(store, {
    className: "WIDEN",
    subject: grant.grant_id,
    parties: distinct(input.parties),
    witnessIds: witnesses,
    scope: scope.envelope,
    rollback: rollback.envelope,
    notAfter: input.not_after,
  });
  return base(store, "APPROVED", "GRANT_RECORDED", {
    grant_id: grant.grant_id,
    enterprise_state: "APPROVED",
    host_state: null,
    title_moved: false,
    approval_id: approval.approval_id,
    quorum_count: 2,
  });
}

function sealExpiredGrant(grant, nowMs) {
  if (grant.state !== "APPROVED" || grant.record_layer_exercise === "ENDED") return;
  const clock = nowMs != null ? nowMs : Date.now();
  if (clock >= grant.not_after_ms) {
    grant.record_layer_exercise = "ENDED";
    grant.can_exercise = false;
    grant.host_expanded_authority_cleared = "UNSATISFIED";
  }
}

function exercisePhase(grant, nowMs) {
  if (grant.state === "REVOKED" || grant.record_layer_exercise === "ENDED") return "ENDED";
  if (nowMs != null && nowMs >= grant.not_after_ms) return "ENDED";
  if (nowMs != null && nowMs < grant.not_before_ms) return "NOT_YET";
  if (nowMs == null && grant.record_layer_exercise === "NOT_YET") return "NOT_YET";
  if (nowMs == null && Date.now() >= grant.not_after_ms) return "ENDED";
  if (nowMs == null && grant.record_layer_exercise === "OPEN" && Date.now() < grant.not_before_ms) return "NOT_YET";
  if (grant.record_layer_exercise === "OPEN") return "OPEN";
  if (nowMs != null && nowMs >= grant.not_before_ms && nowMs < grant.not_after_ms) return "OPEN";
  return "CLOSED";
}

function rawPermittedScope(grant, phase) {
  if (phase === "ENDED" || grant.state === "REVOKED") return grant.rollback_target;
  return grant.scope;
}

function noteSpawn(store, input) {
  assertStore(store);
  const blocked = screen(store, input);
  if (blocked) return blocked;
  const before = store.grants.size;
  if (!input || !isSafeId(input.parent_grant_id)) {
    return base(store, "REFUSED", "SPAWN_DOES_NOT_MINT", { grant_minted: false, grant_count: before });
  }
  const grant = store.grants.get(input.parent_grant_id);
  if (!grant || (grant.state !== "APPROVED" && grant.state !== "REVOKED")) {
    return base(store, "REFUSED", "GRANT_NOT_APPROVED", { grant_minted: false, grant_count: store.grants.size });
  }
  const nowMs = input.now ? parseTime(input.now) : null;
  if (input.now && nowMs == null) {
    return base(store, "REFUSED", "CLOCK_INVALID", { grant_minted: false, grant_count: store.grants.size });
  }
  sealExpiredGrant(grant, nowMs);
  const phase = exercisePhase(grant, nowMs);
  if (phase === "NOT_YET" || phase === "CLOSED") {
    return base(store, "REFUSED", phase === "NOT_YET" ? "GRANT_NOT_YET" : "GRANT_NOT_APPROVED", {
      grant_minted: false,
      grant_count: store.grants.size,
      within_subset: false,
      inheritance: phase === "NOT_YET" ? "NOT_YET" : "CLOSED",
    });
  }
  if (grant.state === "REVOKED" && !input.child_envelope) {
    return base(store, "REFUSED", "GRANT_NOT_APPROVED", { grant_minted: false, grant_count: store.grants.size });
  }
  const inheritance = phase === "ENDED" ? "ROLLBACK_SCOPE_ONLY" : "PARENT_EGRESS_SCOPE_ONLY";
  if (!input.child_envelope) {
    return base(store, "RECORDED", "SPAWN_IS_NOT_A_GRANT", {
      grant_minted: false,
      inheritance,
      grant_count: store.grants.size,
    });
  }
  const child = normalizeEnvelope(input.child_envelope);
  if (!child.ok) return base(store, "REFUSED", child.reason, { grant_minted: false });
  const raw = rawPermittedScope(grant, phase);
  const permitted = store.root ? tightenTo(raw, store.root.policy) : raw;
  const violations = subsetViolations(child.envelope, permitted);
  if (violations.length) {
    return base(store, "REFUSED", "CHILD_EXCEEDS_PERMITTED_SUBSET", {
      violations,
      grant_minted: false,
      grant_count: store.grants.size,
      within_subset: false,
      inheritance,
    });
  }
  return base(store, "RECORDED", "SPAWN_IS_NOT_A_GRANT", {
    grant_minted: false,
    inheritance,
    grant_count: store.grants.size,
    within_subset: true,
  });
}

function quoteHostReport(store, input) {
  assertStore(store);
  const blocked = screen(store, input) || requireRoot(store);
  if (blocked) return blocked;
  if (!input || WRITER_SOURCES.has(input.source) || input.source !== "host_report") {
    return base(store, "REJECTED", "ENTERPRISE_WRITER_CANNOT_ASSERT_ACTIVE");
  }
  if (store.available === false) return base(store, "REFUSED", "STORE_UNAVAILABLE_NO_WIDEN");
  if (input.quoted_outcome !== "ACTIVE" && input.quoted_outcome !== "REFUSED") {
    return base(store, "REFUSED", "HOST_QUOTE_OUTCOME_INVALID");
  }
  const grant = input.subject_id ? store.grants.get(input.subject_id) : null;
  if (!grant) return base(store, "REFUSED", "UNKNOWN_GRANT");
  if (grant.state !== "APPROVED" || grant.can_exercise !== true) {
    return base(store, "REFUSED", "NOT_APPROVED", { enterprise_state: grant.state });
  }
  if (input.envelope_version !== grant.version) return base(store, "REFUSED", "VERSION_MISMATCH");
  grant.host_quote = {
    outcome: input.quoted_outcome,
    source: "host_report",
    verified_on_host: false,
    host_contacted: false,
  };
  if (input.quoted_outcome === "REFUSED") {
    grant.state = "REFUSED";
    grant.can_exercise = false;
    grant.record_layer_exercise = "CLOSED";
    grant.refusal_source = "host_quote";
  }
  return base(store, "QUOTED", "HOST_QUOTE_RECORDED", {
    enterprise_state: grant.state,
    quoted_host_outcome: input.quoted_outcome,
    display_source: "host_quote",
  });
}

function noteClock(store, input) {
  assertStore(store);
  const blocked = screen(store, input) || requireRoot(store);
  if (blocked) return blocked;
  const nowMs = parseTime(input && input.now);
  if (nowMs == null) return base(store, "REFUSED", "CLOCK_REQUIRED");
  const ended = [];
  for (const grant of store.grants.values()) {
    if (grant.state !== "APPROVED") continue;
    if (grant.record_layer_exercise === "ENDED") continue;
    if (nowMs >= grant.not_after_ms) {
      grant.record_layer_exercise = "ENDED";
      grant.can_exercise = false;
      grant.host_expanded_authority_cleared = "UNSATISFIED";
      ended.push(grant.grant_id);
    } else if (nowMs < grant.not_before_ms) {
      grant.record_layer_exercise = "NOT_YET";
      grant.can_exercise = false;
    } else if (grant.record_layer_exercise === "NOT_YET") {
      grant.record_layer_exercise = "OPEN";
      grant.can_exercise = true;
    }
  }
  let policyReverted = false;
  let policy = store.root.policy;
  const remaining = [];
  if (store.available !== false) {
    for (const open of store.root.open_widens) {
      if (nowMs >= open.not_after_ms) {
        if (open.applied) {
          const tightened = tightenTo(policy, open.rollback_target);
          if (!envelopesEqual(policy, tightened)) policyReverted = true;
          policy = tightened;
        }
        continue;
      }
      if (open.not_before_ms != null && nowMs < open.not_before_ms) {
        if (open.applied) {
          const tightened = tightenTo(policy, open.rollback_target);
          if (!envelopesEqual(policy, tightened)) policyReverted = true;
          policy = tightened;
          open.applied = false;
        }
        remaining.push(open);
        continue;
      }
      if (!open.applied) {
        if (store.freeze) {
          remaining.push(open);
          continue;
        }
        const baseline = open.baseline || open.rollback_target;
        const composed = composeWiden(policy, baseline, open.next_policy);
        if (!envelopesEqual(policy, composed)) {
          policy = composed;
          store.root.policy_version += 1;
          open.version = store.root.policy_version;
        }
        open.applied = true;
      }
      remaining.push(open);
    }
    store.root.policy = policy;
    store.root.open_widens = remaining;
  }
  if (policyReverted) store.root.policy_host_check = "UNSATISFIED";
  return base(store, "RECORDED", "CLOCK_NOTED", {
    ended_grant_ids: ended,
    policy_reverted: policyReverted,
    host_expanded_authority_cleared: "UNSATISFIED",
    claimed_expired_state: false,
  });
}

function revokeGrant(store, input) {
  assertStore(store);
  const blocked = screen(store, input) || requireRoot(store) || hostedWriteBlocked(store);
  if (blocked) return blocked;
  const grant = input && input.grant_id ? store.grants.get(input.grant_id) : null;
  if (!grant) return base(store, "REFUSED", "UNKNOWN_GRANT");
  if (grant.state === "REVOKED") return base(store, "REFUSED", "ALREADY_REVOKED");
  const klass = classOf(input);
  if (klass.missing) return base(store, "REFUSED", "MISSING_CLASS");
  if (klass.unknown) return base(store, "REFUSED", "UNKNOWN_CLASS");
  const parties = partyList(input);
  const denial = authorizeRevoke(store, grant, klass, parties);
  if (denial) return denial;
  grant.state = "REVOKED";
  grant.can_exercise = false;
  grant.record_layer_exercise = "ENDED";
  grant.host_expanded_authority_cleared = "UNSATISFIED";
  store.root.title_holder = "customer_root";
  pushApproval(store, {
    className: klass.value,
    subject: grant.grant_id,
    parties: distinct(parties),
    witnessIds: [],
    scope: grant.rollback_target,
    rollback: grant.rollback_target,
    notAfter: null,
  });
  return base(store, "APPROVED", "GRANT_REVOKED", {
    enterprise_state: "REVOKED",
    title_holder: "customer_root",
    title_moved: false,
    host_expanded_authority_cleared: "UNSATISFIED",
  });
}

function authorizeRevoke(store, grant, klass, parties) {
  if (grant.domain === "security" || grant.domain === "recovery") {
    if (klass.value !== "ROOT") return base(store, "REFUSED", "ROOT_CLASS_REQUIRED");
    return checkRootParties(store, parties);
  }
  if (grant.domain !== "workload") return base(store, "REFUSED", "UNKNOWN_DOMAIN");
  if (klass.value === "ROOT") return checkRootParties(store, parties);
  if (klass.value === "NARROW" && Array.isArray(parties) && parties.length === 1 && parties[0] === grant.delegator) {
    const known = knownKind(store, parties[0]);
    if (!known.ok) return base(store, "REFUSED", known.reason);
    if (known.identity.kind !== "customer") return base(store, "REJECTED", "WORKLOAD_SELF_APPROVAL");
    return null;
  }
  return base(store, "REFUSED", "REVOKE_NOT_AUTHORIZED");
}

function materialIdentities(material) {
  const map = new Map();
  if (!material || !Array.isArray(material.identities)) return map;
  for (const item of material.identities) {
    if (item && isSafeId(item.id) && KINDS.has(item.kind)) map.set(item.id, item.kind);
  }
  return map;
}

function recoveryQuorumFromMaterial(material, vantioReason) {
  if (!material || typeof material !== "object") return { refusalReason: "CUSTOMER_MATERIAL_REQUIRED" };
  const parties = material.parties;
  if (!Array.isArray(parties) || parties.length < 1) return { refusalReason: "PARTIES_REQUIRED" };
  if (distinct(parties).length !== parties.length) return { rejected: "SAME_PERSON_DUAL_CONTROL" };
  const kinds = materialIdentities(material);
  const roots = Array.isArray(material.material_root_ids) ? material.material_root_ids : [];
  const recovery = Array.isArray(material.material_recovery_ids) ? material.material_recovery_ids : [];
  let customerSeat = false;
  for (const id of parties) {
    if (!isSafeId(id)) return { refusalReason: "IDENTITY_ID_INVALID" };
    const kind = kinds.get(id);
    if (!kind) return { refusalReason: "UNKNOWN_IDENTITY" };
    if (kind === "workload") return { rejected: "WORKLOAD_SELF_APPROVAL" };
    if (kind === "vantio") return { rejected: vantioReason };
    if (kind === "customer" && (roots.includes(id) || recovery.includes(id))) customerSeat = true;
  }
  if (!customerSeat) return { refusalReason: "PARTY_CANNOT_EXERCISE" };
  return { ok: true, parties: distinct(parties) };
}

function recover(input) {
  const store = input && input.store && input.store.marker === boundary.STORE_MARKER ? input.store : null;
  const blocked = screen(store, input);
  if (blocked) return blocked;
  const material = input ? input.material : null;
  if (!material) return base(store, "REFUSED", "CUSTOMER_MATERIAL_REQUIRED");
  const materialScan = scanRecord(material);
  if (materialScan) return base(store, "REFUSED", materialScan);
  if (!RECOVERY_MODE.has(material.mode)) return base(store, "REJECTED", "RECOVERY_MODE_REJECTED");
  const quorum = recoveryQuorumFromMaterial(material, "VANTIO_ONLY_RECOVER");
  if (quorum.rejected) return base(store, "REJECTED", quorum.rejected);
  if (!quorum.ok) return base(store, "REFUSED", quorum.refusalReason);
  const pre = normalizeEnvelope(material.pre_containment);
  if (!pre.ok) return base(store, "REFUSED", pre.reason);
  let proposed = null;
  if (material.mode === "stay-quarantined" && !material.proposed_envelope) {
    proposed = pre.envelope;
  } else {
    const next = normalizeEnvelope(material.proposed_envelope);
    if (!next.ok) return base(store, "REFUSED", next.reason);
    proposed = next.envelope;
  }
  const wider = subsetViolations(proposed, pre.envelope);
  if (wider.length) return base(store, "REJECTED", "WIDER_THAN_CEILING", { violations: wider });
  if (material.mode === "last-known") {
    const rollback = normalizeEnvelope(material.rollback_target);
    if (!rollback.ok) return base(store, "REFUSED", "ROLLBACK_TARGET_REQUIRED");
    if (subsetViolations(rollback.envelope, pre.envelope).length) {
      return base(store, "REJECTED", "WIDER_THAN_CEILING");
    }
  }
  return base(store, "APPROVED", "RECOVERY_RECORDED", {
    mode: material.mode,
    thaw: false,
    vantio_required: false,
    hosted_store_written: false,
    host_action_status: "UNSATISFIED",
    parties: quorum.parties,
    witness_required: false,
  });
}

function recordFreeze(input) {
  const store = input && input.store && input.store.marker === boundary.STORE_MARKER ? input.store : null;
  const blocked = screen(store, input);
  if (blocked) return blocked;
  const material = input && input.material ? input.material : null;
  let parties = [];
  if (material) {
    const quorum = recoveryQuorumFromMaterial(material, "VANTIO_ONLY_FREEZE");
    if (quorum.rejected) return base(store, "REJECTED", quorum.rejected);
    if (!quorum.ok) return base(store, "REFUSED", quorum.refusalReason);
    parties = quorum.parties;
  } else if (store && store.root) {
    const single = checkSingleCustomer(store, input.parties, { allowRecovery: true });
    if (single.refusal) return single.refusal;
    parties = [single.id];
  } else {
    return base(store, "REFUSED", "CUSTOMER_MATERIAL_REQUIRED");
  }
  if (store && store.root && material) {
    const allowed = parties.some((id) => store.root.root_ids.includes(id) || store.root.recovery_ids.includes(id));
    if (!allowed) return base(store, "REFUSED", "PARTY_CANNOT_EXERCISE");
  }
  if (store && store.root) {
    store.freeze = {
      parties,
      host_action_status: "UNSATISFIED",
      expansion_stopped_on_host: "UNSATISFIED",
    };
    pushApproval(store, {
      className: "RECOVERY",
      subject: "freeze",
      parties,
      witnessIds: [],
      scope: null,
      rollback: null,
      notAfter: null,
    });
  }
  return base(store, "APPROVED", "FREEZE_RECORDED", {
    hosted_store_written: Boolean(store && store.available && store.root),
    host_freeze_performed: false,
    host_action_status: "UNSATISFIED",
    parties,
    vantio_required: false,
  });
}

function customerLeaveParty(store, input, kind) {
  const single = checkSingleCustomer(store, input.parties, {
    allowRecovery: true,
    allowReadGrant: kind === "export",
  });
  return single;
}

function recordCustomerCopy(store, input, kind) {
  assertStore(store);
  const blocked = screen(store, input) || requireRoot(store);
  if (blocked) return blocked;
  if (input && input.holder === "vantio_only") return base(store, "REJECTED", "VANTIO_ONLY_EVIDENCE");
  if (!input || input.holder !== "customer") return base(store, "REFUSED", "CUSTOMER_HOLDER_REQUIRED");
  if ((kind === "hash" || kind === "export") && !isHash(input.hash)) return base(store, "REFUSED", "HASH_REQUIRED");
  const party = customerLeaveParty(store, input, kind);
  if (party.refusal) return party.refusal;
  if (!store.available) {
    return base(store, "RECORDED", "CUSTOMER_COPY_WITHOUT_HOSTED_STORE", {
      hosted_store_written: false,
      customer_keeps_record: true,
      host_action_status: "UNSATISFIED",
    });
  }
  const record = {
    record_id: mint(store, kind === "export" ? "ex" : "lv"),
    kind,
    holder: "customer",
    hash: input.hash || null,
    vantio_copy_required: false,
    bytes_stored: false,
    host_performed: false,
  };
  if (kind === "export" || kind === "hash") store.evidence.push(record);
  else store.leave_intents.push(record);
  return base(store, "RECORDED", "CUSTOMER_COPY_RECORDED", {
    record_id: record.record_id,
    customer_keeps_record: true,
    vantio_copy_required: false,
    host_action_status: "UNSATISFIED",
  });
}

function exportEvidence(store, input) {
  return recordCustomerCopy(store, input, "export");
}

function hashEvidence(store, input) {
  return recordCustomerCopy(store, input, "hash");
}

function recordRollbackIntent(store, input) {
  return recordCustomerCopy(store, input, "rollback");
}

function recordUninstallIntent(store, input) {
  return recordCustomerCopy(store, input, "uninstall");
}

function leaveFromCustomerHeldMaterial(input) {
  const blocked = screen(null, input);
  if (blocked) return blocked;
  if (!input || input.holder === "vantio_only") return base(null, "REJECTED", "VANTIO_ONLY_EVIDENCE");
  if (input.holder !== "customer") return base(null, "REFUSED", "CUSTOMER_HOLDER_REQUIRED");
  if (!isHash(input.hash)) return base(null, "REFUSED", "HASH_REQUIRED");
  const quorum = recoveryQuorumFromMaterial(input, "VANTIO_NOT_A_SATISFYING_PARTY");
  if (quorum.rejected) return base(null, "REJECTED", quorum.rejected);
  if (!quorum.ok) return base(null, "REFUSED", quorum.refusalReason);
  return base(null, "RECORDED", "LEAVE_RECORDED_FROM_CUSTOMER_MATERIAL", {
    customer_keeps_export: true,
    hosted_store_written: false,
    host_action_status: "UNSATISFIED",
    steps: ["export", "hash", "rollback", "uninstall"],
  });
}

function setRecordStoreAvailable(store, available) {
  assertStore(store);
  store.available = Boolean(available);
  return base(store, "RECORDED", available ? "STORE_AVAILABLE" : "STORE_UNAVAILABLE", {
    last_known_policy_version: store.root ? store.root.policy_version : null,
    widened: false,
  });
}

function applyBillingOrSupport(store, input) {
  assertStore(store);
  const before = snapshot(store);
  const blocked = screen(store, input);
  if (blocked) return blocked;
  return base(store, "REFUSED", "BILLING_OR_SUPPORT_DOES_NOT_MOVE_TITLE", {
    snapshot_unchanged: JSON.stringify(before) === JSON.stringify(snapshot(store)),
    title_holder: store.root ? store.root.title_holder : null,
  });
}

function refuseAlways(reason) {
  return base(null, "REJECTED", reason, { class_defined: false, mutated: false });
}

function refuseHostMark() {
  return refuseAlways("ENTERPRISE_CANNOT_MARK_HOST");
}

function refuseSecondEnforcementEngine() {
  return refuseAlways("SECOND_ENFORCEMENT_ENGINE");
}

function refuseDryRunActivation() {
  return refuseAlways("DRY_RUN_ACTIVATION");
}

function refuseBreakglass() {
  return refuseAlways("BREAKGLASS_OFF");
}

function displayGrant(grant) {
  if (!grant) return null;
  const quote = grant.host_quote;
  return {
    enterprise_state: grant.state,
    can_exercise: grant.can_exercise === true && grant.record_layer_exercise === "OPEN",
    quoted_host_outcome: quote ? quote.outcome : null,
    display_active: Boolean(quote && quote.outcome === "ACTIVE"),
    display_source: quote ? "host_quote" : "enterprise_record",
    verified_on_host: false,
    host_contacted: false,
  };
}

function publicGrant(grant) {
  return {
    grant_id: grant.grant_id,
    delegator: grant.delegator,
    delegate: grant.delegate,
    domain: grant.domain,
    state: grant.state,
    can_exercise: grant.can_exercise,
    record_layer_exercise: grant.record_layer_exercise,
    redelegation: grant.redelegation,
    version: grant.version,
    display: displayGrant(grant),
    host_expanded_authority_cleared: grant.host_expanded_authority_cleared,
  };
}

function snapshot(store) {
  assertStore(store);
  return {
    title_holder: store.root ? store.root.title_holder : null,
    root_ids: store.root ? store.root.root_ids.slice() : [],
    recovery_ids: store.root ? store.root.recovery_ids.slice() : [],
    recognized_ids: store.root ? store.root.recognized_ids.slice() : [],
    witness_present: store.root ? store.root.witness_present : false,
    witness_counts_toward_quorum: false,
    title_domains: store.root ? store.root.title_domains.slice() : [],
    reserved_powers: store.root ? store.root.reserved_powers.slice() : [],
    policy: store.root ? store.root.policy : null,
    policy_version: store.root ? store.root.policy_version : 0,
    authority_ceiling: store.root ? store.root.authority_ceiling : null,
    grant_count: store.grants.size,
    grants: [...store.grants.values()].map(publicGrant),
    approval_count: store.approvals.length,
    host_intents: store.host_intents.map((item) => Object.assign({}, item)),
    host_enrolled: false,
    host_protected: false,
    host_enforced: false,
    store_available: store.available,
    evidence_count: store.evidence.length,
    freeze: store.freeze ? { host_action_status: store.freeze.host_action_status } : null,
    worm: false,
    spanner_selected: false,
    identity_provider_selected: false,
    active_grant_states: [...store.grants.values()].map((grant) => grant.state),
  };
}

function inspect(store, input) {
  assertStore(store);
  const blocked = screen(store, input) || requireRoot(store);
  if (blocked) return blocked;
  const klass = classOf(input);
  if (klass.missing) return base(store, "REFUSED", "MISSING_CLASS");
  if (klass.unknown || klass.value !== "INSPECT") return base(store, "REFUSED", "INSPECT_CLASS_REQUIRED");
  if (input && input.next_policy) return base(store, "REFUSED", "INSPECT_IS_READ_ONLY");
  const single = checkSingleCustomer(store, partyList(input), { allowReadGrant: true });
  if (single.refusal) return single.refusal;
  return base(store, "APPROVED", "INSPECT_RECORDED", {
    read_only: true,
    host_state: null,
  });
}

module.exports = {
  WRITER_SOURCES,
  acceptOpaqueIdentity,
  applyBillingOrSupport,
  changeOwnerSet,
  createCustomerHeldStore,
  displayGrant,
  exportEvidence,
  foundRoot,
  hashEvidence,
  inspect,
  leaveFromCustomerHeldMaterial,
  nameRecoveryParty,
  noteClock,
  noteSpawn,
  proposeGrant,
  quoteHostReport,
  recordFreeze,
  recordHostIntent,
  recordPolicyDecision,
  recordRecognizedCustomer,
  recordRollbackIntent,
  recordUninstallIntent,
  recover,
  refuseBreakglass,
  refuseDryRunActivation,
  refuseHostMark,
  refuseSecondEnforcementEngine,
  removeWitness,
  revokeGrant,
  setRecordStoreAvailable,
  snapshot,
};
