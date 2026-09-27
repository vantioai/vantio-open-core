"use strict";

const { readFileSync } = require("node:fs");
const {
  AUDIENCE,
  CANARY,
  CARD_IDS,
  CLASSIFICATION_AWAITING,
  CLASSIFICATION_BLOCKED,
  CLASSIFICATION_READY,
  LIMITATIONS_STATED,
  PROOF_CLASSES,
  SIMULATION_LABELS,
} = require("./constants.cjs");
const { canonicalize, sha256, withoutHash } = require("./canonical.cjs");

function cardById(doc, id) {
  return (doc.cards || []).find((card) => card.id === id) || null;
}

function assess(doc) {
  const problems = [];
  if (!doc || doc.schema !== "vantio.investor-demo.wave2-export/v1") problems.push("schema");
  if (doc.audience !== AUDIENCE) problems.push("audience");
  if (doc.external_proof !== "NOT_PROVED_EXTERNAL") problems.push("external_proof");
  if (doc.customer_validation !== "UNSET") problems.push("customer_validation");
  if (doc.evidence_tier !== "UNSET") problems.push("evidence_tier");
  if (doc.announcement !== "HOLD") problems.push("announcement");
  if (doc.visual_completion_counts !== false) problems.push("visual_completion");
  if (doc.customer_activity_total !== 0) problems.push("customer_total");
  if (doc.customer_success_narration !== false) problems.push("customer_success");
  if (doc.cli_reopened !== false) problems.push("cli_reopened");
  if (!Array.isArray(doc.cards) || doc.cards.length !== CARD_IDS.length) problems.push("card_count");
  CARD_IDS.forEach((id, index) => {
    const card = doc.cards && doc.cards[index];
    if (!card || card.id !== id) {
      problems.push(`card_order:${id}`);
      return;
    }
    if (!PROOF_CLASSES.includes(card.proof_class)) problems.push(`proof_class:${id}`);
    if (card.proof_class === "PROVED_EXTERNAL" || card.external_proof !== "NOT_PROVED_EXTERNAL") {
      problems.push(`external:${id}`);
    }
    if (card.customer_validation !== "UNSET" || card.evidence_tier !== "UNSET") problems.push(`tier:${id}`);
    if (card.counted_in_customer_activity !== false) problems.push(`customer_card:${id}`);
    if (card.announcement !== "HOLD") problems.push(`announcement:${id}`);
    if (card.functional_passed !== true && id !== "uninstall") problems.push(`functional:${id}`);
    if (card.is_simulation === true) {
      if (!SIMULATION_LABELS.includes(card.simulation_label)) problems.push(`label:${id}`);
      if (card.simulation_label === "LIVE_LOCAL_OBSERVATION") problems.push(`live_label:${id}`);
    } else if (card.simulation_label !== null) {
      problems.push(`unexpected_label:${id}`);
    }
  });

  const envelope = doc.envelope;
  if (!envelope || envelope.evidence_origin !== "SIMULATED_DEMO" || envelope.producer !== "demo_command") {
    problems.push("envelope");
  }
  if (envelope && (envelope.action !== "OBSERVED" || envelope.content !== null || envelope.network !== "none")) {
    problems.push("envelope_shape");
  }
  if (envelope && Object.prototype.hasOwnProperty.call(envelope, "vantio_run_log")) problems.push("envelope_run_marker");
  if (doc.run_scan && doc.run_scan.customer_activity_total !== 0) problems.push("scan_total");
  if (doc.run_scan && doc.run_scan.forbidden_tokens_present !== false) problems.push("forbidden_tokens");
  if (doc.run_scan && doc.run_scan.local_observation_present !== false) problems.push("local_observation");
  if (!doc.policy || doc.policy.applied !== false || doc.policy.state === "ACTIVE") problems.push("policy");
  if (!doc.authority || doc.authority.accepted.state !== "PROPOSED" || doc.authority.accepted.active !== false) {
    problems.push("authority_accepted");
  }
  if (!doc.authority || doc.authority.refused.state !== "REFUSED" || doc.authority.refused.active !== false) {
    problems.push("authority_refused");
  }
  if (!doc.health || doc.health.host_protection_state !== "not_enrolled" || doc.health.degraded_catalog_member !== true) {
    problems.push("health");
  }
  if (!doc.recovery || doc.recovery.host_protection_state !== "not_enrolled") problems.push("recovery");
  if (doc.mode === "LIVE_DEVIATION") problems.push("live_deviation");
  if (doc.f1 && doc.f1.planted === true) {
    if (doc.f1.disposition !== "DISCARDED" || doc.f1.proved !== false || doc.f1.added_to_total !== false) {
      problems.push("f1");
    }
    if (doc.f1.success_narration !== false || doc.unlabeled_file_success_narration !== false) problems.push("f1_narration");
  }
  for (const id of LIMITATIONS_STATED) {
    if (!doc.limitations_stated || !doc.limitations_stated.includes(id)) problems.push(`limitation:${id}`);
  }
  const uninstall = cardById(doc, "uninstall");
  if (uninstall && uninstall.executed === true && uninstall.functional_passed !== true) problems.push("uninstall_functional");
  const serialized = JSON.stringify(withoutHash(doc));
  if (serialized.includes(CANARY)) problems.push("canary_present");
  if (/(?<!NOT_)PROVED_EXTERNAL/.test(serialized)) problems.push("proved_external_string");
  if (doc.producer_classification === CLASSIFICATION_READY) {
    if (!uninstall || uninstall.executed !== true) problems.push("uninstall_not_executed");
  }
  if (doc.producer_classification === CLASSIFICATION_AWAITING) {
    if (!uninstall || uninstall.executed !== false) problems.push("awaiting_uninstall_flag");
  }
  return problems;
}

function classificationFor(doc, problems) {
  if (problems.length > 0) return CLASSIFICATION_BLOCKED;
  const uninstall = cardById(doc, "uninstall");
  if (!uninstall || uninstall.executed !== true) return CLASSIFICATION_AWAITING;
  return CLASSIFICATION_READY;
}

function verifyExport(input) {
  const doc = typeof input === "string" ? JSON.parse(readFileSync(input, "utf8")) : input;
  const invariantProblems = assess(doc).filter((item) => item !== "uninstall_not_executed" && item !== "awaiting_uninstall_flag");
  const expectedClass = classificationFor(doc, invariantProblems);
  const problems = [];
  if (doc.canonical_sha256 !== sha256(canonicalize(withoutHash(doc)))) problems.push("sha256");
  if (doc.producer_classification !== expectedClass) problems.push("classification");
  if (doc.producer_classification === CLASSIFICATION_READY && invariantProblems.length > 0) problems.push("optimistic_ready");
  return {
    ok: problems.length === 0,
    problems,
    invariant_problems: invariantProblems,
    producer_classification: doc.producer_classification,
    external_proof: "NOT_PROVED_EXTERNAL",
  };
}

module.exports = {
  assess,
  classificationFor,
  verifyExport,
};
