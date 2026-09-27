"use strict";

const EVIDENCE_STATUS = ["SUPPORTED", "UNSUPPORTED", "UNKNOWN", "CONFLICTING"];
const DISPOSITIONS = [
  "KEEP",
  "REWRITE",
  "HOLD",
  "RETIRE",
  "EXTERNAL_ACCOUNT_ACTION_REQUIRED",
  "DEFER_TO_T16",
];
const CLAIM_CLASSES = [
  "product",
  "capability",
  "security",
  "performance",
  "compliance",
  "version",
  "partnership",
  "other",
];

const SHIP_FLAGS = [
  "authorizes_public_rewrite",
  "authorizes_publish",
  "authorizes_announce",
  "authorizes_registry_mutation",
  "authorizes_external_account_edit",
  "authorizes_track_16",
  "authorizes_track_17",
  "authorizes_tracks_18_through_21",
  "public_ship_authorization",
  "clean_host_internal_proof",
  "proved_external",
];

const OPTIMISTIC_EVIDENCE = new Set([
  "SUCCESS",
  "SHIPPED",
  "VERIFIED",
  "PROVED",
  "PROVED_EXTERNAL",
  "CLEAN_HOST_INTERNAL_PROOF",
]);

function publicShipAuthorized(_ledger) {
  return false;
}

function dispositionExecutesNow(_ledger, _disposition) {
  return false;
}

function freezeProblems(ledger) {
  const problems = [];
  if (!ledger || typeof ledger !== "object") {
    return ["ledger is missing"];
  }
  if (ledger.status !== "FROZEN_INVENTORY") {
    problems.push(`status ${ledger.status} is not FROZEN_INVENTORY`);
  }
  if (ledger.classification !== "W3_PUBLIC_CLAIM_CONTENT_INVENTORY_READY_FOR_COUNCIL") {
    problems.push("classification token is missing");
  }
  if (publicShipAuthorized(ledger) !== false) {
    problems.push("FROZEN_INVENTORY was treated as public-ship authorization");
  }
  const freeze = ledger.freeze;
  if (!freeze || typeof freeze !== "object") {
    problems.push("freeze block is missing");
    return problems;
  }
  if (freeze.status !== "FROZEN_INVENTORY") problems.push("freeze.status is not FROZEN_INVENTORY");
  if (freeze.kind !== "INVENTORY_ONLY") problems.push("freeze.kind is not INVENTORY_ONLY");
  for (const flag of SHIP_FLAGS) {
    if (freeze[flag] !== false) problems.push(`freeze.${flag} is not false`);
  }
  if (ledger.public_surfaces_mutated !== false) problems.push("public_surfaces_mutated is not false");
  if (ledger.t14_dispositions_mutated !== false) problems.push("t14_dispositions_mutated is not false");
  if (ledger.frozen_packages_reopened !== false) problems.push("frozen_packages_reopened is not false");
  if (!Array.isArray(ledger.claims) || ledger.claims.length === 0) {
    problems.push("claims are missing");
    return problems;
  }
  const ids = new Set();
  for (const claim of ledger.claims) {
    if (!claim || typeof claim.claim_id !== "string" || !/^CL-W3-T15-\d{3}$/.test(claim.claim_id)) {
      problems.push("claim_id is missing or malformed");
      continue;
    }
    if (ids.has(claim.claim_id)) problems.push(`duplicate ${claim.claim_id}`);
    ids.add(claim.claim_id);
    if (!CLAIM_CLASSES.includes(claim.claim_class)) {
      problems.push(`${claim.claim_id} claim_class ${claim.claim_class}`);
    }
    if (typeof claim.claim_text !== "string" || claim.claim_text.trim() === "") {
      problems.push(`${claim.claim_id} has no claim text`);
    }
    if (claim.text_form !== "verbatim" && claim.text_form !== "paraphrase") {
      problems.push(`${claim.claim_id} text_form`);
    }
    if (!EVIDENCE_STATUS.includes(claim.evidence_status)) {
      problems.push(`${claim.claim_id} evidence_status ${claim.evidence_status}`);
    }
    if (OPTIMISTIC_EVIDENCE.has(claim.evidence_status)) {
      problems.push(`${claim.claim_id} uses an optimistic evidence status`);
    }
    if (!DISPOSITIONS.includes(claim.recommended_disposition)) {
      problems.push(`${claim.claim_id} disposition ${claim.recommended_disposition}`);
    }
    if (claim.executes_now !== false) problems.push(`${claim.claim_id} executes_now is not false`);
    if (dispositionExecutesNow(ledger, claim.recommended_disposition) !== false) {
      problems.push(`${claim.claim_id} disposition was treated as execution`);
    }
    if (!Array.isArray(claim.surfaces) || claim.surfaces.length === 0) {
      problems.push(`${claim.claim_id} has no surfaces`);
    }
    if (!Array.isArray(claim.evidence) || claim.evidence.length === 0) {
      problems.push(`${claim.claim_id} has no evidence notes`);
    }
    if (!Array.isArray(claim.drift_ids)) problems.push(`${claim.claim_id} drift_ids is not an array`);
  }
  return problems;
}

module.exports = {
  CLAIM_CLASSES,
  DISPOSITIONS,
  EVIDENCE_STATUS,
  OPTIMISTIC_EVIDENCE,
  SHIP_FLAGS,
  dispositionExecutesNow,
  freezeProblems,
  publicShipAuthorized,
};
