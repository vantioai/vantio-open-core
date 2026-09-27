"use strict";

const PROOF_CLASSES = Object.freeze([
  "INTERNAL_FUNCTIONAL",
  "SIMULATED_LABELED",
  "NARRATED_BOUNDARY",
  "OFFLINE_FALLBACK",
  "HELD_NOT_EXECUTED",
]);

const SIMULATION_LABELS = Object.freeze([
  "SIMULATED_DEMO",
  "NARRATED_BOUNDARY",
  "INJECTED_UNLABELED_SYNTHETIC",
]);

const CARD_IDS = Object.freeze([
  "workload_discovery",
  "optics_observation",
  "coverage",
  "ingress_egress_attempts",
  "policy_proposal",
  "simulation",
  "canary_enforcement",
  "allowed_blocked",
  "descendant_authority",
  "health_degradation",
  "recovery",
  "evidence_export",
  "revocation",
  "rollback",
  "uninstall",
  "independent_verification",
]);

const BEAT_IDS = Object.freeze([
  "B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B09",
  "B10", "B11", "B12", "B13", "B14", "B15", "B16", "B17", "B18",
]);

const NARRATED_BEATS = Object.freeze({
  B01: "docs/programs/production-readiness/demo/03-DEMO-SCRIPT.md",
  B02: "docs/PRODUCT_LINEUP.md",
  B05: "docs/governance/canonical/product-boundary.md",
  B06: "docs/products/optics/SUPPORTED-PATHS.md",
  B10: "docs/programs/production-readiness/demo/06-EXPECTED-OUTPUTS.md",
  B11: "docs/governance/canonical/status-tokens.md",
  B12: "docs/governance/canonical/product-boundary.md",
  B13: "docs/programs/production-readiness/demo/00-BOUNDARY.md",
  B14: "docs/programs/production-readiness/demo/08-CLAIM-LEDGER.json",
  B16: "docs/programs/production-readiness/demo/03-DEMO-SCRIPT.md",
  B18: "docs/programs/production-readiness/demo/09-LIMITATION-LEDGER.json",
});

const BANNER = "SIMULATION — SIMULATED_DEMO — vantio demo — no network — not a customer call";
const DEMO_SENTENCE = "Demo — in-process stub. No network.";
const PRODUCER = "demo_command";
const PRODUCER_VERSION = "wave2-0.0.0";
const ORIGIN = "SIMULATED_DEMO";
const HOSTNAME = "optics-demo.invalid";
const CANARY = "WAVE2CANARYPRIVACYTOKEN";
const CLASSIFICATION_READY = "INVESTOR_DEMO_WAVE2_READY_FOR_COUNCIL";
const CLASSIFICATION_AWAITING = "INVESTOR_DEMO_WAVE2_AWAITING_UNINSTALL";
const CLASSIFICATION_BLOCKED = "INVESTOR_DEMO_WAVE2_BLOCKED";
const DESIGN_TIP = "43cc35371e109e6a377cc31e4fd2438bfceea797";
const BASE_COMMIT = "89f95099d0dce463307eb75d78e7fcf2ef99feb2";
const CLI_VERSION = "0.3.24";
const SCHEMA_STATUS = "unstable-pre-1.0";
const AUDIENCE = "INTERNAL_RESTRICTED";
const F1_TRACE = "0xinjectunlabeled01";
const TRACE_RE = /^0x[0-9a-f]{16}$/;
const PRODUCER_VERSION_RE = /^[A-Za-z0-9._+-]{1,32}$/;
const FIXED_TIME = "2026-09-27T00:00:00.000Z";
const ISO_TIME_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/;

const FORBIDDEN_RUN_TOKENS = Object.freeze([
  "BLOCKED_HOST",
  "BLOCKED_SIZE",
  "BLOCKED_SPEND",
  "DRY_RUN_BLOCKED",
  "REDACTED",
]);

const LIMITATIONS_STATED = Object.freeze([
  "L-FOUNDER-BEATS-ABSENT",
  "L-DEMO-FILE-UNLABELED",
  "L-PROVE-OMITS-LABEL",
  "L-DISCOVER-COUNTS-DEMO",
  "L-NOT-DETERMINISTIC-IDS",
  "L-PE-NOT-RUN",
]);

module.exports = {
  AUDIENCE,
  BANNER,
  BASE_COMMIT,
  BEAT_IDS,
  CANARY,
  CARD_IDS,
  CLASSIFICATION_AWAITING,
  CLASSIFICATION_BLOCKED,
  CLASSIFICATION_READY,
  CLI_VERSION,
  DEMO_SENTENCE,
  DESIGN_TIP,
  F1_TRACE,
  FIXED_TIME,
  FORBIDDEN_RUN_TOKENS,
  HOSTNAME,
  ISO_TIME_RE,
  LIMITATIONS_STATED,
  NARRATED_BEATS,
  ORIGIN,
  PRODUCER,
  PRODUCER_VERSION,
  PRODUCER_VERSION_RE,
  PROOF_CLASSES,
  SCHEMA_STATUS,
  SIMULATION_LABELS,
  TRACE_RE,
};
