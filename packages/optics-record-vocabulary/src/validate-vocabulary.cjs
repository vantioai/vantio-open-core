"use strict";

const boundary = require("./boundary.cjs");
const assignments = require("../vocabulary/assignments.cjs");

const CANONICAL_PRIVACY = new Set(["STRUCTURAL", "IDENTITY", "DIAGNOSTIC", "CUSTOMER_TEXT"]);
const POSTURES = new Set([
  "NORMALIZE_UNAVAILABLE",
  "NORMALIZE_DECLARED",
  "REJECT_FIELD",
  "REJECT_RECORD",
  "REJECT_NOT_SUCCESS",
]);
const FORCE_KEYS = [
  "canonical_name",
  "semantic_dimension",
  "type",
  "optionality",
  "allowed_enum_values",
  "absent_value_behavior",
  "invalid_value_behavior",
  "compatibility_aliases",
  "legacy_interpretation",
  "evidence_origin_effect",
  "issue_location_effect",
  "completeness_effect",
  "privacy_class",
  "metric_eligible",
  "export_eligible",
  "proof_eligible",
  "reader_fallback",
  "writer_requirement",
  "deprecation_posture",
];

function push(errors, message) {
  errors.push(message);
}

function includesText(value, needle) {
  return typeof value === "string" && value.includes(needle);
}

function inspectAliasGraph(canonicalRows) {
  const cycles = [];
  const ownershipConflicts = [];
  const fanoutViolations = [];
  const collisions = [];
  const byType = new Map();
  const names = new Set();

  for (const row of canonicalRows) {
    names.add(row.canonical_name);
    if (!byType.has(row.record_type)) byType.set(row.record_type, []);
    byType.get(row.record_type).push(row);
    if (row.compatibility_aliases.length > boundary.MAX_ALIAS_FANOUT) {
      fanoutViolations.push(row.row_id + " fanout " + row.compatibility_aliases.length);
    }
  }

  const globalOwner = new Map();
  for (const [recordType, rows] of byType) {
    const edges = new Map();
    for (const row of rows) {
      const seenAlias = new Set();
      for (const alias of row.compatibility_aliases) {
        if (seenAlias.has(alias)) fanoutViolations.push(row.row_id + " duplicate alias " + alias);
        seenAlias.add(alias);
        if (alias === row.canonical_name) cycles.push(recordType + " self-alias " + alias);
        const key = recordType + "\0" + alias;
        const prior = edges.get(alias);
        if (prior && prior !== row.canonical_name) {
          ownershipConflicts.push(key + " -> " + prior + " and " + row.canonical_name);
        }
        edges.set(alias, row.canonical_name);
        const owners = globalOwner.get(alias) || new Set();
        owners.add(row.canonical_name);
        globalOwner.set(alias, owners);
        if (names.has(alias) && alias !== row.canonical_name) {
          collisions.push({ record_type: recordType, alias, owner: row.canonical_name });
        }
      }
    }
    for (const start of edges.keys()) {
      const seen = new Set();
      let current = start;
      let depth = 0;
      while (edges.has(current)) {
        if (depth > boundary.MAX_ALIAS_WALK_DEPTH) {
          cycles.push(recordType + " walk exceeded depth at " + start);
          break;
        }
        if (seen.has(current)) {
          cycles.push(recordType + " cycle at " + start);
          break;
        }
        seen.add(current);
        current = edges.get(current);
        depth += 1;
      }
    }
  }

  for (const [alias, owners] of globalOwner) {
    if (owners.size > 1) ownershipConflicts.push(alias + " -> " + [...owners].join(","));
  }

  return { collisions, cycles, fanoutViolations, ownershipConflicts };
}

function validateVocabulary(vocabulary) {
  const errors = [];
  if (!vocabulary || typeof vocabulary !== "object") {
    return { ok: false, errors: ["vocabulary is not an object"] };
  }
  if (vocabulary.schema_status !== boundary.SCHEMA_STATUS) push(errors, "schema_status");
  if (vocabulary.schema_version !== 0) push(errors, "schema_version");
  if (vocabulary.stable_schema !== false) push(errors, "stable_schema");
  if (vocabulary.json_schema_is_source_of_truth !== false) push(errors, "json schema flag");
  if (vocabulary.shipped !== false || vocabulary.live_writer !== false || vocabulary.live_reader !== false) {
    push(errors, "inert flags");
  }
  if (vocabulary.migration !== false || vocabulary.record_conversion !== false) push(errors, "migration flag");
  if (vocabulary.unicode_profile_id !== boundary.UNICODE_PROFILE_ID) push(errors, "unicode profile id");
  if (vocabulary.unicode_profile_version !== boundary.UNICODE_PROFILE_VERSION) push(errors, "unicode profile version");
  if (vocabulary.alternate_unicode_profile !== false || vocabulary.unicode_profile_payload_field_added !== false) {
    push(errors, "alternate unicode profile");
  }
  if (vocabulary.max_alias_fanout !== boundary.MAX_ALIAS_FANOUT) push(errors, "fanout bound");
  if (vocabulary.reader_only_origin_label !== "LEGACY_UNMARKED") push(errors, "reader origin label");

  const canonicalRows = vocabulary.canonical_rows || [];
  const compatibilityRows = vocabulary.compatibility_rows || [];
  const coverage = vocabulary.planning_row_coverage || [];
  if (canonicalRows.length !== 120) push(errors, "canonical row count " + canonicalRows.length);
  if (compatibilityRows.length !== 67) push(errors, "compatibility row count " + compatibilityRows.length);
  if (coverage.length !== 187) push(errors, "coverage count " + coverage.length);

  const rowKeys = new Set();
  const nameCounts = new Map();
  const dimensionOfName = new Map();
  const fieldsByDimension = new Map();
  const knownDimensions = new Set([
    ...boundary.REQUIRED_DIMENSIONS,
    ...assignments.additionalDimensions,
  ]);

  for (const row of canonicalRows) {
    const key = row.record_type + "\0" + row.canonical_name;
    if (rowKeys.has(key)) push(errors, "duplicate row " + key);
    rowKeys.add(key);
    nameCounts.set(row.canonical_name, (nameCounts.get(row.canonical_name) || 0) + 1);
    for (const forceKey of FORCE_KEYS) {
      if (!Object.prototype.hasOwnProperty.call(row, forceKey)) push(errors, row.row_id + " missing " + forceKey);
    }
    if (!knownDimensions.has(row.semantic_dimension)) push(errors, row.row_id + " dimension");
    if (!CANONICAL_PRIVACY.has(row.privacy_class)) push(errors, row.row_id + " privacy");
    if (row.unknown_enum_posture === "COERCE_TO_SUCCESS" || !POSTURES.has(row.unknown_enum_posture)) {
      push(errors, row.row_id + " posture " + row.unknown_enum_posture);
    }
    if (row.stable_schema !== false || row.schema_status !== boundary.SCHEMA_STATUS) push(errors, row.row_id + " schema");
    if (typeof row.metric_eligible !== "boolean" || typeof row.export_eligible !== "boolean" || typeof row.proof_eligible !== "boolean") {
      push(errors, row.row_id + " eligibility");
    }
    if (!row.reader_fallback || !row.writer_requirement || !row.deprecation_posture) push(errors, row.row_id + " empty requirement");
    const specific = row.record_type + "." + row.canonical_name;
    const expectedDimension = assignments.recordFieldDimension[specific] || assignments.fieldDimension[row.canonical_name];
    if (row.semantic_dimension !== expectedDimension) push(errors, row.row_id + " dimension drift");
    const prior = dimensionOfName.get(row.canonical_name);
    if (prior && prior !== row.semantic_dimension && !assignments.recordFieldDimension[specific]) {
      push(errors, "dimension split " + row.canonical_name);
    }
    if (!assignments.recordFieldDimension[specific]) dimensionOfName.set(row.canonical_name, row.semantic_dimension);
    if (!fieldsByDimension.has(row.semantic_dimension)) fieldsByDimension.set(row.semantic_dimension, new Set());
    fieldsByDimension.get(row.semantic_dimension).add(row.record_type + "." + row.canonical_name);
    if (Array.isArray(row.allowed_enum_values)) {
      const uniq = new Set(row.allowed_enum_values);
      if (uniq.size !== row.allowed_enum_values.length) push(errors, row.row_id + " duplicate enum");
    }
  }

  if (nameCounts.size !== 88) push(errors, "unique names " + nameCounts.size);
  const graph = inspectAliasGraph(canonicalRows);
  for (const item of graph.cycles) push(errors, "alias cycle " + item);
  for (const item of graph.ownershipConflicts) push(errors, "alias ownership " + item);
  for (const item of graph.fanoutViolations) push(errors, "alias fanout " + item);

  for (const collision of graph.collisions) {
    const row = canonicalRows.find(
      (candidate) => candidate.record_type === collision.record_type && candidate.canonical_name === collision.owner,
    );
    if (!row || !row.legacy_interpretation.collides_with_different_canonical_field) {
      push(errors, "unrecorded collision " + collision.record_type + " " + collision.alias);
    }
    if (row && !row.legacy_interpretation.collision_fields.includes(collision.alias)) {
      push(errors, "collision field missing " + collision.alias);
    }
  }

  for (const dimension of boundary.REQUIRED_DIMENSIONS) {
    if (dimension === "integrity") {
      const binding = vocabulary.integrity_binding;
      if (!binding || binding.dimension !== "integrity") push(errors, "integrity binding");
      else if (binding.allowed_values.join(",") !== "OK,FAILED,UNKNOWN") push(errors, "integrity tokens");
      continue;
    }
    if (!fieldsByDimension.has(dimension) || fieldsByDimension.get(dimension).size === 0) {
      push(errors, "dimension unrepresented " + dimension);
    }
  }

  const separated = [
    ...boundary.SEPARATED_DIMENSIONS,
    ...boundary.ADDITIONAL_DISJOINT_DIMENSIONS,
  ];
  const seenFields = new Map();
  for (const dimension of separated) {
    const fields = fieldsByDimension.get(dimension) || new Set();
    for (const field of fields) {
      if (seenFields.has(field)) push(errors, "dimension collapse " + field + " " + seenFields.get(field) + " " + dimension);
      seenFields.set(field, dimension);
    }
  }

  const optics = canonicalRows.find((row) => row.record_type === "observation_event" && row.canonical_name === "optics_status");
  const application = canonicalRows.find((row) => row.record_type === "observation_event" && row.canonical_name === "application_status");
  const action = canonicalRows.find((row) => row.record_type === "observation_event" && row.canonical_name === "action");
  const http = canonicalRows.find((row) => row.record_type === "observation_event" && row.canonical_name === "http_status");
  const bytes = canonicalRows.find((row) => row.record_type === "observation_event" && row.canonical_name === "response_bytes");
  const origin = canonicalRows.find((row) => row.record_type === "observation_event" && row.canonical_name === "evidence_origin");
  const lifecycle = canonicalRows.find((row) => row.record_type === "observation_event" && row.canonical_name === "lifecycle");
  const sampling = canonicalRows.find((row) => row.record_type === "observation_event" && row.canonical_name === "sampling");
  if (!optics || !includesText(optics.absent_value_behavior, "UNAVAILABLE") || !includesText(optics.absent_value_behavior, "not SUCCESS")) {
    push(errors, "optics absent behavior");
  }
  if (!optics || optics.unknown_enum_posture !== "NORMALIZE_UNAVAILABLE") push(errors, "optics unknown posture");
  if (!optics || !optics.allowed_enum_values.includes("SUCCESS") || !optics.allowed_enum_values.includes("OBSERVED")) {
    push(errors, "optics enum");
  }
  if (!application || application.allowed_enum_values.includes("PARTIAL")) push(errors, "application PARTIAL");
  if (!lifecycle || !lifecycle.allowed_enum_values.includes("PARTIAL")) push(errors, "lifecycle PARTIAL");
  if (lifecycle && lifecycle.semantic_dimension === "completeness") push(errors, "lifecycle collapsed into completeness");
  if (lifecycle && lifecycle.semantic_dimension === "optics_health") push(errors, "lifecycle collapsed into optics");
  if (!action || !includesText(action.absent_value_behavior, "not OBSERVED")) push(errors, "action absent");
  if (!http || !includesText(http.absent_value_behavior, "not 200") || !includesText(http.absent_value_behavior, "not 0")) {
    push(errors, "http absent");
  }
  if (!bytes || !includesText(bytes.absent_value_behavior, "Legacy bytes 0 becomes null") || !includesText(bytes.absent_value_behavior, "Explicit response_bytes 0 is kept")) {
    push(errors, "bytes absent");
  }
  if (!origin || !includesText(origin.absent_value_behavior, "LEGACY_UNMARKED") || !includesText(origin.absent_value_behavior, "not stored as LOCAL_OBSERVATION")) {
    push(errors, "origin absent");
  }
  if (!sampling || sampling.allowed_enum_values.join(",") !== "UNSAMPLED") push(errors, "sampling enum");
  if (optics && application && optics.semantic_dimension === application.semantic_dimension) push(errors, "status collapse");

  const integrityTokens = new Set(vocabulary.integrity_binding.allowed_values);
  for (const token of optics.allowed_enum_values) {
    if (integrityTokens.has(token)) push(errors, "integrity token overlaps optics " + token);
  }

  let retained = 0;
  let compatibilityCoverage = 0;
  coverage.forEach((item, index) => {
    if (item.planning_index !== index) push(errors, "coverage index " + index);
    if (item.role === "canonical" && item.coverage === "RETAINED" && item.consolidation === null) retained += 1;
    if (item.role === "compatibility" && item.coverage === "RETAINED_AS_COMPATIBILITY" && item.consolidation) {
      compatibilityCoverage += 1;
    }
  });
  if (retained !== 120) push(errors, "retained canonical coverage " + retained);
  if (compatibilityCoverage !== 67) push(errors, "compatibility coverage " + compatibilityCoverage);

  for (const row of compatibilityRows) {
    if (row.canonical_name !== null) push(errors, "compatibility canonical name " + row.live_name);
    if (row.unknown_enum_posture === "COERCE_TO_SUCCESS") push(errors, "compatibility success posture");
    const expected = assignments.compatibilityDimension[row.live_name];
    if (row.semantic_dimension !== expected) push(errors, "compatibility dimension " + row.live_name);
  }

  const span = canonicalRows.find((row) => row.record_type === "run_envelope" && row.canonical_name === "span_id");
  if (!span || span.type !== "null" || span.null_versus_absent !== "VALUE_IS_NULL") push(errors, "envelope span null");

  return { ok: errors.length === 0, errors, alias_graph: graph };
}

module.exports = { inspectAliasGraph, validateVocabulary };
