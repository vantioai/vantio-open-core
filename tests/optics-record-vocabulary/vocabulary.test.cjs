"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const { canonicalJson, inspectAliasGraph, loadVocabulary, validateVocabulary } = require("../../packages/optics-record-vocabulary/src/index.cjs");
const { buildVocabulary } = require("../../packages/optics-record-vocabulary/tools/build-vocabulary.cjs");

const ROOT = path.resolve(__dirname, "../..");

function readJson(relativePath) {
  return JSON.parse(fs.readFileSync(path.join(ROOT, relativePath), "utf8"));
}

function sha256(relativePath) {
  return crypto.createHash("sha256").update(fs.readFileSync(path.join(ROOT, relativePath))).digest("hex");
}

test("vocabulary JSON parses and validates", () => {
  const vocabulary = loadVocabulary();
  const report = validateVocabulary(vocabulary);
  assert.equal(report.ok, true, report.errors.join("\n"));
  assert.equal(vocabulary.audience, "INTERNAL_RESTRICTED");
  assert.equal(vocabulary.schema_status, "unstable-pre-1.0");
  assert.equal(vocabulary.schema_version, 0);
  assert.equal(vocabulary.stable_schema, false);
  assert.equal(vocabulary.shipped, false);
  assert.equal(vocabulary.live_writer, false);
  assert.equal(vocabulary.live_reader, false);
  assert.equal(vocabulary.migration, false);
  assert.equal(vocabulary.record_conversion, false);
  assert.equal(Object.isFrozen(vocabulary), true);
  assert.equal(Object.isFrozen(vocabulary.canonical_rows), true);
  assert.equal(vocabulary.counts.canonical_rows, 120);
  assert.equal(vocabulary.counts.unique_canonical_names, 88);
  assert.equal(vocabulary.counts.repeated_canonical_names, 22);
  assert.equal(vocabulary.counts.extra_rows_from_repeated_names, 32);
  assert.equal(vocabulary.counts.compatibility_rows, 67);
  assert.equal(vocabulary.counts.planning_entries, 187);
});

test("committed vocabulary matches the generator", () => {
  const committed = loadVocabulary();
  const built = buildVocabulary();
  assert.equal(canonicalJson(committed), canonicalJson(built));
});

test("row keys are unique and repeated names keep one row per record type", () => {
  const vocabulary = loadVocabulary();
  const keys = new Set();
  const names = new Map();
  for (const row of vocabulary.canonical_rows) {
    const key = row.record_type + "\0" + row.canonical_name;
    assert.equal(keys.has(key), false, key);
    keys.add(key);
    if (!names.has(row.canonical_name)) names.set(row.canonical_name, new Set());
    names.get(row.canonical_name).add(row.semantic_dimension);
  }
  assert.equal(keys.size, 120);
  assert.equal(names.size, 88);
  for (const [name, dimensions] of names) {
    if (name === "reason_code") {
      assert.equal(dimensions.size, 2);
    } else {
      assert.equal(dimensions.size, 1, name);
    }
  }
});

test("alias fan-out is bounded, acyclic, and singly owned", () => {
  const vocabulary = loadVocabulary();
  const graph = inspectAliasGraph(vocabulary.canonical_rows);
  assert.deepEqual(graph.cycles, []);
  assert.deepEqual(graph.ownershipConflicts, []);
  assert.deepEqual(graph.fanoutViolations, []);
  let edges = 0;
  let max = 0;
  for (const row of vocabulary.canonical_rows) {
    edges += row.compatibility_aliases.length;
    if (row.compatibility_aliases.length > max) max = row.compatibility_aliases.length;
    assert.ok(row.compatibility_aliases.length <= vocabulary.max_alias_fanout);
  }
  assert.equal(edges, 19);
  assert.equal(max, 2);
  const traceCollisions = graph.collisions.filter((item) => item.alias === "trace_id");
  assert.ok(traceCollisions.length >= 2);
  for (const collision of traceCollisions) assert.equal(collision.owner, "run_id");
});

test("a synthetic alias cycle is rejected", () => {
  const graph = inspectAliasGraph([
    { record_type: "sample", canonical_name: "left", compatibility_aliases: ["right"], row_id: "left", legacy_interpretation: {} },
    { record_type: "sample", canonical_name: "right", compatibility_aliases: ["left"], row_id: "right", legacy_interpretation: {} },
  ]);
  assert.ok(graph.cycles.length > 0);
});

test("enum, absent, and unknown postures stay honest", () => {
  const vocabulary = loadVocabulary();
  const enums = readJson("packages/optics-evidence-contract/contract/enums.json");
  const metadata = readJson("packages/optics-evidence-contract/contract/contract-metadata.json");
  const byName = (recordType, name) => vocabulary.canonical_rows.find((row) => row.record_type === recordType && row.canonical_name === name);

  const optics = byName("observation_event", "optics_status");
  assert.deepEqual(optics.allowed_enum_values, enums.optics_status);
  assert.equal(optics.unknown_enum_posture, "NORMALIZE_UNAVAILABLE");
  assert.match(optics.absent_value_behavior, /UNAVAILABLE/);
  assert.match(optics.absent_value_behavior, /not SUCCESS/);
  assert.equal(optics.allowed_enum_values.includes("SUPER_SUCCESS"), false);

  const application = byName("observation_event", "application_status");
  assert.deepEqual(application.allowed_enum_values, enums.application_status);
  assert.equal(application.allowed_enum_values.includes("PARTIAL"), false);
  assert.deepEqual(byName("observation_event", "lifecycle").allowed_enum_values, enums.lifecycle);
  assert.deepEqual(byName("observation_event", "failure_kind").allowed_enum_values, enums.failure_kind);
  assert.deepEqual(byName("observation_event", "issue_location").allowed_enum_values, enums.issue_location);
  assert.deepEqual(byName("observation_event", "evidence_origin").allowed_enum_values, enums.evidence_origin_writer);
  assert.deepEqual(byName("observation_event", "sampling").allowed_enum_values, ["UNSAMPLED"]);
  assert.deepEqual(byName("observation_event", "action").allowed_enum_values, ["OBSERVED"]);
  assert.deepEqual(byName("run_envelope", "producer").allowed_enum_values, metadata.recognized_producers);
  assert.deepEqual(vocabulary.integrity_binding.allowed_values, enums.integrity_state);
  assert.match(byName("observation_event", "action").absent_value_behavior, /not OBSERVED/);
  assert.match(byName("observation_event", "http_status").absent_value_behavior, /not 200/);
  assert.match(byName("observation_event", "http_status").absent_value_behavior, /not 0/);
  assert.match(byName("observation_event", "response_bytes").absent_value_behavior, /Legacy bytes 0 becomes null/);
  assert.match(byName("observation_event", "response_bytes").absent_value_behavior, /Explicit response_bytes 0 is kept/);
  assert.match(byName("observation_event", "evidence_origin").absent_value_behavior, /LEGACY_UNMARKED/);

  for (const row of vocabulary.canonical_rows) {
    assert.notEqual(row.unknown_enum_posture, "COERCE_TO_SUCCESS");
  }
});

test("status dimensions do not share canonical fields", () => {
  const vocabulary = loadVocabulary();
  const separated = vocabulary.separated_dimensions;
  assert.deepEqual(separated, [
    "optics_health",
    "workload_outcome",
    "dependency_outcome",
    "coverage",
    "completeness",
    "integrity",
  ]);
  const seen = new Map();
  for (const row of vocabulary.canonical_rows) {
    if (!separated.includes(row.semantic_dimension) && !vocabulary.additional_disjoint_dimensions.includes(row.semantic_dimension)) {
      continue;
    }
    const field = row.record_type + "." + row.canonical_name;
    assert.equal(seen.has(field), false, field);
    seen.set(field, row.semantic_dimension);
  }
  const lifecycle = vocabulary.canonical_rows.find((row) => row.canonical_name === "lifecycle");
  const completeness = vocabulary.canonical_rows.find((row) => row.canonical_name === "completeness_impact");
  assert.equal(lifecycle.semantic_dimension, "attempt_lifecycle");
  assert.equal(completeness.semantic_dimension, "completeness");
  assert.notEqual(lifecycle.semantic_dimension, completeness.semantic_dimension);
  const opticsTokens = new Set(vocabulary.canonical_rows.find((row) => row.canonical_name === "optics_status").allowed_enum_values);
  for (const token of vocabulary.integrity_binding.allowed_values) assert.equal(opticsTokens.has(token), false);
});

test("every planning row is retained", () => {
  const vocabulary = loadVocabulary();
  const planning = readJson("docs/planning/optics-pkg02/RECORD-VOCABULARY.json");
  assert.equal(planning.entries.length, vocabulary.planning_row_coverage.length);
  let canonical = 0;
  let compatibility = 0;
  planning.entries.forEach((entry, index) => {
    const coverage = vocabulary.planning_row_coverage[index];
    assert.equal(coverage.planning_index, index);
    assert.equal(coverage.role, entry.role);
    if (entry.role === "canonical") {
      canonical += 1;
      assert.equal(coverage.coverage, "RETAINED");
      assert.equal(coverage.consolidation, null);
      assert.equal(coverage.canonical_name, entry.canonical_name);
      assert.equal(coverage.record_type, entry.record_type);
    } else {
      compatibility += 1;
      assert.equal(coverage.coverage, "RETAINED_AS_COMPATIBILITY");
      assert.equal(typeof coverage.consolidation, "string");
      assert.equal(coverage.live_name, entry.live_name);
    }
  });
  assert.equal(canonical, 120);
  assert.equal(compatibility, 67);
});

test("PKG-01 field compatibility is exact and not weakened", () => {
  const vocabulary = loadVocabulary();
  const catalog = readJson("packages/optics-evidence-contract/contract/field-catalog.json");
  const prohibited = readJson("packages/optics-evidence-contract/contract/prohibited-fields.json");
  const unicode = readJson("packages/optics-evidence-contract/contract/unicode-profile-metadata.json");
  assert.equal(catalog.fields.length, 120);
  for (const field of catalog.fields) {
    const row = vocabulary.canonical_rows.find((candidate) => candidate.record_type === field.record_type && candidate.canonical_name === field.name);
    assert.ok(row, field.record_type + "." + field.name);
    assert.equal(row.type, field.type);
    assert.equal(row.invalid_value_behavior, field.invalid_disposition);
    assert.equal(row.privacy_class, field.sensitivity);
    assert.equal(row.metric_eligible, field.metric_label_eligible);
    assert.equal(row.export_eligible, field.export_eligible);
    assert.equal(row.proof_eligible, field.proof_eligible);
    assert.equal(row.optionality === "required", field.required);
    assert.equal(row.normalization, field.normalization);
  }
  const names = new Set(vocabulary.canonical_rows.map((row) => row.record_type + "." + row.canonical_name));
  assert.equal(names.size, catalog.fields.length);
  assert.deepEqual(vocabulary.prohibited_names_declared, prohibited.prohibited_field_names);
  assert.equal(vocabulary.unicode_profile_id, unicode.profile_id);
  assert.equal(vocabulary.unicode_profile_version, unicode.profile_version);
  assert.equal(vocabulary.alternate_unicode_profile, false);
  assert.equal(vocabulary.trace_generation_witness.stored_on_record, false);
  for (const relativePath of vocabulary.source_sha256 ? Object.keys(vocabulary.source_sha256) : []) {
    assert.equal(vocabulary.source_sha256[relativePath], sha256(relativePath));
  }
});

test("source hashes cover the governed inputs", () => {
  const vocabulary = loadVocabulary();
  for (const relativePath of [
    "docs/planning/optics-pkg02/RECORD-VOCABULARY.json",
    "packages/optics-evidence-contract/contract/field-catalog.json",
    "packages/optics-evidence-contract/contract/enums.json",
    "packages/optics-evidence-contract/contract/contract-metadata.json",
    "packages/optics-evidence-contract/contract/prohibited-fields.json",
  ]) {
    assert.equal(vocabulary.source_sha256[relativePath], sha256(relativePath));
  }
});
