"use strict";

const { POSTURE } = require("./boundary.cjs");

const api = require("../../optics-otel-mapping/src/index.cjs");
const doc = api.mappingDocument();

function identityProblem(mapping) {
  if (!mapping || typeof mapping !== "object") return "mapping document missing";
  if (mapping.mapping_id !== POSTURE.mapping_id) return "mapping_id";
  if (mapping.mapping_version !== POSTURE.mapping_version) return "mapping_version";
  if (mapping.schema_status !== POSTURE.schema_status) return "schema_status";
  if (mapping.stable_schema !== false) return "stable_schema";
  if (mapping.schema_url !== null) return "schema_url";
  if (mapping.public_shipped_support !== false) return "public_shipped_support";
  if (mapping.otlp_export_authorized !== false) return "otlp_export_authorized";
  if (mapping.adapters_default_enabled !== false) return "adapters_default_enabled";
  if (mapping.i3_status !== "NOT_AUTHORIZED") return "i3_status";
  if (mapping.founder_decision_12 !== "unresolved") return "founder_decision_12";
  if (!Array.isArray(mapping.canonical_candidate_origins) || mapping.canonical_candidate_origins.length !== 1) {
    return "canonical_candidate_origins";
  }
  if (mapping.canonical_candidate_origins[0] !== "LOCAL_OBSERVATION") return "canonical_candidate_origins";
  return "";
}

const problem = identityProblem(doc);
if (problem) {
  throw new Error("optics-otel-i3: approved mapping rejected (" + problem + ")");
}

module.exports = {
  api,
  doc,
  identityProblem,
};
