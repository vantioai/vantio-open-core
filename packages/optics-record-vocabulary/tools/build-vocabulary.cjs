"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const boundary = require("../src/boundary.cjs");
const assignments = require("../vocabulary/assignments.cjs");

const PACKAGE_ROOT = path.resolve(__dirname, "..");
const REPO_ROOT = path.resolve(PACKAGE_ROOT, "../..");

const PLANNING_VOCAB = "docs/planning/optics-pkg02/RECORD-VOCABULARY.json";
const CATALOG = "packages/optics-evidence-contract/contract/field-catalog.json";
const ENUMS = "packages/optics-evidence-contract/contract/enums.json";
const METADATA = "packages/optics-evidence-contract/contract/contract-metadata.json";
const PROHIBITED = "packages/optics-evidence-contract/contract/prohibited-fields.json";

const CLOSED_ENUM_TYPES = new Set([
  "enum",
  "enum:node|python",
  "origin_enum",
  "session_basis",
  "trace_basis_or_null",
  "fixed_phrase",
  "fixed_label",
  "origin_or_legacy",
  "origin_or_legacy_or_null",
]);

function readJson(relativePath) {
  const absolute = path.join(REPO_ROOT, relativePath);
  return JSON.parse(fs.readFileSync(absolute, "utf8"));
}

function sha256(relativePath) {
  const absolute = path.join(REPO_ROOT, relativePath);
  return crypto.createHash("sha256").update(fs.readFileSync(absolute)).digest("hex");
}

function unknownPosture(name, invalid) {
  if (name === "optics_status" && invalid === "NORMALIZE") return "NORMALIZE_UNAVAILABLE";
  if (invalid === "REJECT_FIELD") return "REJECT_FIELD";
  if (invalid === "REJECT_RECORD") return "REJECT_RECORD";
  if (invalid === "NORMALIZE") return "NORMALIZE_DECLARED";
  if (invalid === "REPLACE_WITH_SAFE_CATEGORY") return "NORMALIZE_DECLARED";
  throw new Error("unsupported invalid disposition for " + name + ": " + invalid);
}

function allowedEnums(entry, enums, metadata) {
  const type = entry.type;
  if (typeof type === "string" && type.startsWith("const:")) {
    return [type.slice("const:".length)];
  }
  if (!CLOSED_ENUM_TYPES.has(type)) return null;
  if (entry.record_type === "validation_result" && entry.canonical_name === "issue_location_label") {
    return enums.issue_location.map((token) => {
      const label = enums.issue_location_labels[token];
      if (!label) throw new Error("missing issue location label for " + token);
      return label;
    });
  }
  const key = assignments.enumKeyByField[entry.canonical_name];
  if (!key) throw new Error("no enum key for " + entry.record_type + "." + entry.canonical_name);
  if (key === "recognized_producers") return metadata.recognized_producers.slice();
  const values = enums[key];
  if (!Array.isArray(values)) throw new Error("missing enum " + key);
  return values.slice();
}

function nullVersusAbsent(type) {
  if (type === "null") return "VALUE_IS_NULL";
  if (typeof type === "string" && type.includes("null")) return "NULL_ALLOWED";
  return "ABSENCE_IS_OMISSION";
}

function canonicalRow(entry, index, enums, metadata, catalogNames) {
  const dimension = assignments.dimensionFor(entry.record_type, entry.canonical_name, "canonical", null);
  if (!dimension) throw new Error("unmapped canonical field " + entry.record_type + "." + entry.canonical_name);
  const aliases = (entry.compatibility_aliases || []).slice();
  const collisions = aliases.filter((alias) => catalogNames.has(alias) && alias !== entry.canonical_name);
  return {
    row_id: "canonical:" + entry.record_type + ":" + entry.canonical_name,
    role: "canonical",
    planning_index: index,
    record_type: entry.record_type,
    canonical_name: entry.canonical_name,
    live_name: null,
    semantic_dimension: dimension,
    semantic_definition: entry.semantic_definition,
    type: entry.type,
    optionality: entry.optionality,
    nullable: typeof entry.type === "string" && entry.type.includes("null"),
    null_versus_absent: nullVersusAbsent(entry.type),
    allowed_enum_values: allowedEnums(entry, enums, metadata),
    allowed_values_note: entry.allowed_values,
    absent_value_behavior: entry.absent_value_behavior,
    invalid_value_behavior: entry.invalid_value_behavior,
    unknown_enum_posture: unknownPosture(entry.canonical_name, entry.invalid_value_behavior),
    compatibility_aliases: aliases,
    legacy_interpretation: {
      live_keys: aliases,
      note: entry.inventory_note || "",
      collides_with_different_canonical_field: collisions.length > 0,
      collision_fields: collisions,
      primary_class: entry.primary_class,
      cli_class: entry.cli_class,
      python_class: entry.python_class,
      node_sdk_class: entry.node_sdk_class,
      optimistic_default: entry.primary_class === "OPTIMISTIC_DEFAULT",
    },
    evidence_origin_effect: entry.evidence_origin_interaction,
    issue_location_effect: entry.issue_location_interaction,
    completeness_effect: entry.completeness_impact,
    privacy_class: entry.privacy_class,
    metric_eligible: entry.metric_eligible,
    export_eligible: entry.export_eligible,
    proof_eligible: entry.proof_eligible,
    reader_fallback: entry.reader_fallback,
    writer_requirement: entry.writer_behavior_future,
    deprecation_posture: entry.deprecation_posture,
    normalization: entry.normalization,
    source_of_truth: entry.source_of_truth,
    cli_class: entry.cli_class,
    python_class: entry.python_class,
    node_sdk_class: entry.node_sdk_class,
    primary_class: entry.primary_class,
    conformance_fixtures_required: (entry.conformance_fixtures_required || []).slice(),
    schema_status: boundary.SCHEMA_STATUS,
    stable_schema: false,
  };
}

function compatibilityRow(entry, index, catalogNames) {
  const dimension = assignments.dimensionFor("live_or_reader", null, "compatibility", entry.live_name);
  if (!dimension) throw new Error("unmapped compatibility name " + entry.live_name);
  const liveName = entry.live_name;
  const collides = catalogNames.has(liveName);
  let posture = "REJECT_NOT_SUCCESS";
  if (liveName === "calls.opticsStatus" || liveName === "summary.opticsStatus" || liveName === "opticsLabel") {
    posture = "NORMALIZE_UNAVAILABLE";
  }
  return {
    row_id: "compatibility:live_or_reader:" + liveName,
    role: "compatibility",
    planning_index: index,
    record_type: entry.record_type,
    canonical_name: null,
    live_name: liveName,
    semantic_dimension: dimension,
    semantic_definition: entry.semantic_definition,
    type: entry.type,
    optionality: entry.optionality,
    nullable: false,
    null_versus_absent: "ABSENCE_IS_OMISSION",
    allowed_enum_values: null,
    allowed_values_note: entry.allowed_values,
    absent_value_behavior: entry.absent_value_behavior,
    invalid_value_behavior: entry.invalid_value_behavior,
    unknown_enum_posture: posture,
    compatibility_aliases: (entry.compatibility_aliases || []).slice(),
    legacy_interpretation: {
      live_keys: [liveName],
      note: entry.inventory_note || entry.semantic_definition,
      collides_with_different_canonical_field: collides,
      collision_fields: collides ? [liveName] : [],
      primary_class: entry.primary_class,
      cli_class: entry.cli_class,
      python_class: entry.python_class,
      node_sdk_class: entry.node_sdk_class,
      optimistic_default: entry.primary_class === "OPTIMISTIC_DEFAULT",
      prohibited: entry.primary_class === "PROHIBITED_BY_PKG01",
    },
    evidence_origin_effect: entry.evidence_origin_interaction,
    issue_location_effect: entry.issue_location_interaction,
    completeness_effect: entry.completeness_impact,
    privacy_class: entry.privacy_class,
    metric_eligible: entry.metric_eligible,
    export_eligible: entry.export_eligible,
    proof_eligible: entry.proof_eligible,
    reader_fallback: entry.reader_fallback,
    writer_requirement: entry.writer_behavior_future,
    deprecation_posture: entry.deprecation_posture,
    normalization: entry.normalization,
    source_of_truth: entry.source_of_truth,
    cli_class: entry.cli_class,
    python_class: entry.python_class,
    node_sdk_class: entry.node_sdk_class,
    primary_class: entry.primary_class,
    conformance_fixtures_required: (entry.conformance_fixtures_required || []).slice(),
    schema_status: boundary.SCHEMA_STATUS,
    stable_schema: false,
  };
}

function buildVocabulary() {
  const planning = readJson(PLANNING_VOCAB);
  const catalog = readJson(CATALOG);
  const enums = readJson(ENUMS);
  const metadata = readJson(METADATA);
  const prohibited = readJson(PROHIBITED);
  const catalogNames = new Set(catalog.fields.map((field) => field.name));
  const canonicalRows = [];
  const compatibilityRows = [];
  const coverage = [];

  planning.entries.forEach((entry, index) => {
    if (entry.role === "canonical") {
      canonicalRows.push(canonicalRow(entry, index, enums, metadata, catalogNames));
      coverage.push({
        planning_index: index,
        role: "canonical",
        record_type: entry.record_type,
        canonical_name: entry.canonical_name,
        live_name: null,
        coverage: "RETAINED",
        consolidation: null,
      });
      return;
    }
    if (entry.role === "compatibility") {
      compatibilityRows.push(compatibilityRow(entry, index, catalogNames));
      coverage.push({
        planning_index: index,
        role: "compatibility",
        record_type: entry.record_type,
        canonical_name: null,
        live_name: entry.live_name,
        coverage: "RETAINED_AS_COMPATIBILITY",
        consolidation: "Compatibility names are not PKG-01 catalog fields. They stay compatibility rows and are not merged into a canonical field.",
      });
      return;
    }
    throw new Error("unknown planning role " + entry.role);
  });

  const uniqueNames = new Set(canonicalRows.map((row) => row.canonical_name));
  const nameCounts = new Map();
  for (const row of canonicalRows) nameCounts.set(row.canonical_name, (nameCounts.get(row.canonical_name) || 0) + 1);
  let repeatedNames = 0;
  for (const count of nameCounts.values()) if (count > 1) repeatedNames += 1;
  return {
    audience: boundary.AUDIENCE,
    posture: boundary.POSTURE.slice(),
    schema_status: boundary.SCHEMA_STATUS,
    schema_version: boundary.SCHEMA_VERSION,
    stable_schema: false,
    json_schema_is_source_of_truth: false,
    shipped: false,
    live_writer: false,
    live_reader: false,
    migration: false,
    record_conversion: false,
    unicode_profile_id: boundary.UNICODE_PROFILE_ID,
    unicode_profile_version: boundary.UNICODE_PROFILE_VERSION,
    unicode_profile_payload_field_added: false,
    alternate_unicode_profile: false,
    max_alias_fanout: boundary.MAX_ALIAS_FANOUT,
    max_alias_walk_depth: boundary.MAX_ALIAS_WALK_DEPTH,
    required_dimensions: boundary.REQUIRED_DIMENSIONS.slice(),
    separated_dimensions: boundary.SEPARATED_DIMENSIONS.slice(),
    additional_disjoint_dimensions: boundary.ADDITIONAL_DISJOINT_DIMENSIONS.slice(),
    additional_dimensions: assignments.additionalDimensions.slice(),
    integrity_binding: assignments.integrityBinding,
    recognized_producers: metadata.recognized_producers.slice(),
    reader_only_origin_label: "LEGACY_UNMARKED",
    demo_host: metadata.demo_host,
    trace_generation_witness: {
      field: metadata.trace_generation_witness.field,
      value: metadata.trace_generation_witness.value,
      stored_on_record: false,
    },
    frozen_versions: {
      cli: boundary.FROZEN_VERSIONS.cli,
      node_sdk: boundary.FROZEN_VERSIONS.nodeSdk,
      python: boundary.FROZEN_VERSIONS.python,
      evidence_contract: boundary.FROZEN_VERSIONS.evidenceContract,
    },
    planning_row_policy: "All 120 canonical planning rows are retained. Row identity is record_type plus canonical_name. Unique names are fewer because some names repeat across record types. No canonical row was merged away. The 67 compatibility rows stay compatibility rows because they are not PKG-01 catalog fields.",
    counts: {
      planning_entries: planning.entries.length,
      canonical_rows: canonicalRows.length,
      unique_canonical_names: uniqueNames.size,
      repeated_canonical_names: repeatedNames,
      extra_rows_from_repeated_names: canonicalRows.length - uniqueNames.size,
      compatibility_rows: compatibilityRows.length,
    },
    source_sha256: {
      [PLANNING_VOCAB]: sha256(PLANNING_VOCAB),
      [CATALOG]: sha256(CATALOG),
      [ENUMS]: sha256(ENUMS),
      [METADATA]: sha256(METADATA),
      [PROHIBITED]: sha256(PROHIBITED),
    },
    prohibited_names_declared: prohibited.prohibited_field_names.slice(),
    canonical_rows: canonicalRows,
    compatibility_rows: compatibilityRows,
    planning_row_coverage: coverage,
  };
}

function writeVocabulary(targetPath) {
  const vocabulary = buildVocabulary();
  const json = JSON.stringify(vocabulary, null, 2) + "\n";
  fs.writeFileSync(targetPath, json);
  return vocabulary;
}

if (require.main === module) {
  const target = path.join(PACKAGE_ROOT, "vocabulary", "record-vocabulary.json");
  const vocabulary = writeVocabulary(target);
  process.stdout.write(
    "wrote " +
      target +
      " canonical=" +
      vocabulary.counts.canonical_rows +
      " unique=" +
      vocabulary.counts.unique_canonical_names +
      " compatibility=" +
      vocabulary.counts.compatibility_rows +
      "\n",
  );
}

module.exports = { buildVocabulary, writeVocabulary };
