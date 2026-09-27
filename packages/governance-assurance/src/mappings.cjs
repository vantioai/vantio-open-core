"use strict";

const { LIMITS } = require("./constants.cjs");
const { FRAMEWORKS, documentByVersion, frameworkById } = require("./data/frameworks.cjs");
const { MAPPINGS } = require("./data/mappings.cjs");

function selectMappings(frameworkId, version, mappings = MAPPINGS) {
  const framework = frameworkById(frameworkId);
  if (!framework) {
    return { ok: false, reason: "UNKNOWN_FRAMEWORK", active: false, mappings: [] };
  }
  const document = documentByVersion(frameworkId, version);
  if (!document) {
    return { ok: false, reason: "UNKNOWN_FRAMEWORK_VERSION", active: false, mappings: [] };
  }
  const selected = mappings.filter((item) => item.framework_id === frameworkId && item.document_version === version);
  return {
    ok: true,
    reason: document.superseded_status === "SUPERSEDED" ? "SUPERSEDED" : "CURRENT",
    active: document.superseded_status === "CURRENT",
    superseded_status: document.superseded_status,
    superseded_by: document.superseded_by,
    mappings: selected,
  };
}

function walkMappings(startId, mappings = MAPPINGS, depth = 0, seen = new Set(), state = { nodes: 0 }) {
  if (depth > LIMITS.maxDepth) throw new Error("MAPPING_DEPTH_EXCEEDED");
  state.nodes += 1;
  if (state.nodes > LIMITS.maxNodes) throw new Error("MAPPING_NODE_LIMIT");
  if (seen.has(startId)) throw new Error("MAPPING_CYCLE");
  seen.add(startId);
  const mapping = mappings.find((item) => item.mapping_id === startId);
  if (!mapping) return [];
  const chain = [mapping];
  for (const related of mapping.related_mapping_ids || []) {
    chain.push(...walkMappings(related, mappings, depth + 1, seen, state));
  }
  return chain;
}

function unmappedControls(frameworkId, version, controlIds, mappings = MAPPINGS) {
  const selected = selectMappings(frameworkId, version, mappings);
  if (!selected.ok || !selected.active) return controlIds.slice();
  const covered = new Set(selected.mappings.map((item) => item.control_id).filter(Boolean));
  return controlIds.filter((id) => !covered.has(id));
}

module.exports = {
  FRAMEWORKS,
  MAPPINGS,
  selectMappings,
  unmappedControls,
  walkMappings,
};
