"use strict";

const BASE = "89f95099d0dce463307eb75d78e7fcf2ef99feb2";

const ENTRY = "docs/programs/production-readiness/authority/WAVE2-AUTHORITY.json";

const READING_RULE = "On a conflict, docs/programs/production-readiness/authority/WAVE2-AUTHORITY.json is the current authority. Earlier fields in this file remain the 2026-09-27T07:44:14Z refresh observation.";

const POINTER = {
  id: "AUTH-WAVE2-2026-09-27",
  classification: "WAVE2_AUTHORITY_RECONCILED_READY_FOR_COUNCIL",
  authority_date: "2026-09-27",
  record: ENTRY,
  historical_packet_rewritten: false,
  reading_rule: READING_RULE,
};

const REGISTERS = [
  "docs/programs/production-readiness/MASTER-MANIFEST.json",
  "docs/programs/production-readiness/WORKSTREAM-REGISTRY.json",
  "docs/programs/production-readiness/DECISION-REGISTER.json",
  "docs/programs/production-readiness/RELEASE-REGISTER.json",
];

const ALLOWED = [
  ...REGISTERS,
  "docs/programs/production-readiness/authority/00-INVENTORY.md",
  "docs/programs/production-readiness/authority/01-BOUNDARY.md",
  "docs/programs/production-readiness/authority/02-ARCHITECTURE-COUNCIL-NOTES.md",
  ENTRY,
  "tests/wave2-authority/assess.cjs",
  "tests/wave2-authority/direct.test.cjs",
  "tests/wave2-authority/adversarial.test.cjs",
];

const WS11_ITEMS = [
  ["R1", "pinning"],
  ["R2", "reproducible-build assessment"],
  ["R3", "artifact manifest"],
  ["R4", "exact-hash custody"],
  ["R5", "signing/provenance characterization"],
  ["R6", "SBOM where appropriate"],
  ["R7", "vuln+license scan"],
  ["R8", "clean-env install"],
  ["R9", "upgrade/rollback verify"],
  ["R10", "registry-byte verify"],
  ["R11", "ordinary-client proof"],
  ["R12", "evidence retention"],
  ["R13", "private PE package distribution"],
  ["R14", "version-matched docs gates"],
  ["R15", "emergency release/revocation"],
  ["R16", "partial-publication recovery"],
  ["R17", "role separation"],
  ["R18", "independent release verifier"],
];

const TRUTH_IDS = [
  "python-3.1.0-exact-hash-publication",
  "units-d-e",
  "o7",
  "investor-demo-wave-2",
  "i3",
  "enterprise-e1-e3",
  "ws11",
  "stranger-host-execution",
  "announcements",
  "wave-1",
];

const CLOSED_IDS = [
  "customer-deploy",
  "stranger-host-execution",
  "announcements",
  "credential-create-or-rotate",
  "money",
  "cli-0.3.24-reopen",
  "python-3.1.0-byte-mutation",
  "pe-customer-confidential-public-main",
  "formal-slsa-or-certification",
  "internal-to-external-proof-promotion",
  "optimistic-success",
];

function truth(record, id) {
  return (record.truths || []).find((item) => item.id === id);
}

function closed(record, id) {
  return (record.closed || []).find((item) => item.id === id);
}

function samePending(actual) {
  return Array.isArray(actual)
    && actual.length === 2
    && actual[0] === "named_host"
    && actual[1] === "named_operator";
}

function assess(record) {
  const errors = [];
  const fail = (code) => {
    if (!errors.includes(code)) errors.push(code);
  };

  if (!record || typeof record !== "object") return ["SCHEMA"];
  if (record.schema !== "vantio.program.production-readiness.wave2-authority/v1") fail("SCHEMA");
  if (record.audience !== "INTERNAL_RESTRICTED") fail("AUDIENCE");
  if (record.id !== POINTER.id) fail("ID");
  if (record.classification !== POINTER.classification) fail("CLASSIFICATION");
  if (record.authority_date !== "2026-09-27") fail("AUTHORITY_DATE");
  if (record.accepted_main_sha !== BASE) fail("BASE_SHA");
  if (record.historical_packets_rewritten !== false) fail("HISTORY_REWRITTEN");
  if (record.merges !== false) fail("MERGE");
  if (record.product_implementation !== false) fail("IMPLEMENTATION");
  if (record.reading_rule !== READING_RULE) fail("READING_RULE");
  if (record.entry_path !== ENTRY) fail("ENTRY_PATH");
  if (JSON.stringify(record.files_carrying_the_pointer) !== JSON.stringify(REGISTERS)) fail("POINTERS");
  if (record.track_0_brief?.sha256 !== "1ef951556b9fb415239f2a87600a4b3c37558d45755ebe143d233304d291ed38") {
    fail("BRIEF_HASH");
  }

  const ids = (record.truths || []).map((item) => item.id);
  if (JSON.stringify(ids) !== JSON.stringify(TRUTH_IDS)) fail("TRUTH_SET");

  const python = truth(record, "python-3.1.0-exact-hash-publication") || {};
  if (python.authority !== "AUTHORIZED") fail("PYTHON_AUTHORITY");
  if (python.hold !== false) fail("PYTHON_HOLD");
  if (python.historical_state_left_in_place !== "PUBLISHED_REGISTRY_BYTES_VERIFIED_CLIENT_PROVED") {
    fail("PYTHON_STATE");
  }
  if (python.wheel_sha256_cited_from_release_register !== "dcf84cb3c4f144ece21032001657bfd9c91067faeffbefd0fb2ae19d6109dbeb") {
    fail("PYTHON_WHEEL");
  }
  if (python.sdist_sha256_cited_from_release_register !== "9f991291d5e44a23e17a9b0d7db24f6e7048d4c76cf0a9c37e35ccbcfe999c4f") {
    fail("PYTHON_SDIST");
  }
  if (python.new_registry_observation !== false) fail("PYTHON_OBSERVATION");
  if (python.bytes_mutated !== false) fail("PYTHON_BYTES");
  if (python.workflow_dispatched !== false) fail("PYTHON_WORKFLOW");
  if (python.another_cut_authorized !== false) fail("PYTHON_CUT");

  const units = truth(record, "units-d-e") || {};
  if (units.founder_blocked !== false) fail("UNITS_FOUNDER_BLOCK");
  if (units.gate !== "reader-compat") fail("UNITS_GATE");
  if (units.gate_adjudicated !== false) fail("UNITS_ADJUDICATED");
  if (units.writers_activated !== false) fail("UNITS_ACTIVATED");
  if (units.cli_0_3_24 !== "FROZEN") fail("CLI_FREEZE");
  if (units.python_3_1_0_bytes !== "UNMUTATED") fail("PYTHON_BYTES");

  const o7 = truth(record, "o7") || {};
  if (o7.founder_blocked !== false) fail("O7_FOUNDER_BLOCK");
  if (o7.gate !== "option-c-revalidation") fail("O7_GATE");
  if (o7.revalidation_adjudicated !== false) fail("O7_ADJUDICATED");
  if (o7.gate_8_opened !== false) fail("O7_GATE8");
  if (o7.store_created !== false) fail("O7_STORE");

  const demo = truth(record, "investor-demo-wave-2") || {};
  if (demo.authority !== "AUTHORIZED_INTERNALLY") fail("DEMO_AUTHORITY");
  if (demo.announcement !== "HOLD") fail("DEMO_ANNOUNCEMENT");
  if (demo.readiness_reclassified !== false) fail("DEMO_READINESS");

  const i3 = truth(record, "i3") || {};
  if (i3.authority !== "AUTHORIZED_INTERNALLY") fail("I3_AUTHORITY");
  if (i3.default !== "DISABLED") fail("I3_DEFAULT");
  if (i3.enabled !== false) fail("I3_ENABLED");

  const enterprise = truth(record, "enterprise-e1-e3") || {};
  if (enterprise.authority !== "AUTHORIZED_INTERNALLY") fail("ENTERPRISE_AUTHORITY");
  if (enterprise.live_customer_authority !== false) fail("ENTERPRISE_CUSTOMER");
  if (enterprise.customer_deploy !== false) fail("CUSTOMER_DEPLOY");
  if (enterprise.council_pass_claimed !== false) fail("COUNCIL");
  if (JSON.stringify(enterprise.scopes) !== JSON.stringify(["E1", "E2", "E3"])) fail("ENTERPRISE_SCOPES");

  const ws11 = truth(record, "ws11") || {};
  if (ws11.status !== "DEFINED") fail("WS11_STATUS");
  if (ws11.implemented !== false) fail("WS11_IMPLEMENTED");
  if (ws11.title !== "Release engineering and supply-chain assurance") fail("WS11_TITLE");

  const items = record.ws11_items || [];
  if (items.length !== WS11_ITEMS.length) fail("WS11_ITEMS");
  WS11_ITEMS.forEach(([id, label], index) => {
    if (!items[index] || items[index].id !== id || items[index].label !== label) fail("WS11_LABEL");
  });
  if (record.ws11_definition_source?.expanded_specs_retrieved !== false) fail("WS11_EXPANDED");
  if (record.ws11_definition_source?.in_track_0_upload !== false) fail("WS11_SOURCE");
  if (record.ws11_definition_source?.label_depth !== "one-line") fail("WS11_DEPTH");

  const stranger = truth(record, "stranger-host-execution") || {};
  if (stranger.state !== "BLOCKED") fail("STRANGER_STATE");
  if (!samePending(stranger.pending)) fail("STRANGER_PENDING");
  if (stranger.executed !== false) fail("STRANGER_EXECUTED");

  const announcements = truth(record, "announcements") || {};
  if (announcements.state !== "HOLD") fail("ANNOUNCEMENTS");
  if (announcements.sent !== false) fail("ANNOUNCEMENTS_SENT");

  const wave = truth(record, "wave-1") || {};
  if (wave.state !== "CLOSED_AS_EXECUTABLE_DESIGN_FOUNDATION") fail("WAVE1_STATE");
  if (wave.accepted_main_sha !== BASE) fail("WAVE1_SHA");
  if (wave.letters_titled !== false) fail("WAVE1_LETTERS");

  if (record.ws0?.title_defined_by_this_entry !== false) fail("WS0_INVENTED");
  if (record.ws4_redefined_by_this_entry !== false) fail("WS4_REDEFINED");
  if (record.reader_compat_evidence?.gate_passed !== false) fail("UNITS_ADJUDICATED");
  if (record.reader_compat_evidence?.unit_f_merge_is_ancestor_of_accepted_main !== true) fail("UNIT_F_ANCESTOR");

  const scopes = record.standing_auth_scopes_named_only || [];
  if (scopes.length !== 3 || scopes.some((scope) => scope.packet_defined_here !== false)) fail("SCOPE_INVENTED");

  const closedIds = (record.closed || []).map((item) => item.id);
  if (JSON.stringify(closedIds) !== JSON.stringify(CLOSED_IDS)) fail("CLOSED_SET");
  if (closed(record, "stranger-host-execution")?.state !== "BLOCKED") fail("STRANGER_STATE");
  if (!samePending(closed(record, "stranger-host-execution")?.pending)) fail("STRANGER_PENDING");
  if (closed(record, "announcements")?.state !== "HOLD") fail("ANNOUNCEMENTS");
  CLOSED_IDS.forEach((id) => {
    const item = closed(record, id);
    if (!item) fail("CLOSED_SET");
    if (id !== "stranger-host-execution" && id !== "announcements" && item.state !== "CLOSED") {
      fail("CLOSED_OPENED");
    }
  });

  const claims = record.provenance_claims || {};
  if (claims.formal_slsa !== false
    || claims.certification !== false
    || claims.reproducibility_proved !== false
    || claims.hardware_backed_provenance !== false) {
    fail("PROVENANCE");
  }

  if (record.council?.status !== "PENDING_INDEPENDENT_COUNCIL") fail("COUNCIL");
  if (record.council?.verdict !== null) fail("COUNCIL");
  if (record.council?.this_agent_sits_council !== false) fail("COUNCIL");

  const readings = record.historical_readings || [];
  const readingIds = new Set(TRUTH_IDS);
  if (readings.length < 12) fail("READINGS");
  readings.forEach((reading) => {
    if (!readingIds.has(reading.current_reading_id)) fail("READINGS");
    if (typeof reading.sentence !== "string" || reading.sentence.length === 0) fail("READINGS");
  });

  (record.out_of_scope_historical_packets || []).forEach((packet) => {
    if (packet.left_intact !== true) fail("OUT_OF_SCOPE_EDITED");
  });
  if ((record.out_of_scope_historical_packets || []).length < 5) fail("OUT_OF_SCOPE_EDITED");

  return errors;
}

function withoutAuthority(value) {
  const copy = structuredClone(value);
  delete copy.superseding_authority;
  return copy;
}

module.exports = {
  ALLOWED,
  BASE,
  ENTRY,
  POINTER,
  READING_RULE,
  REGISTERS,
  WS11_ITEMS,
  assess,
  withoutAuthority,
};
