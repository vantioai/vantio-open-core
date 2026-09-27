"use strict";

const constants = require("./constants.cjs");
const { canonicalize, stableStringify } = require("./canonical.cjs");
const { catalogProblems, controlProblems } = require("./schema.cjs");
const { CONTROLS } = require("./data/controls.cjs");
const { FRAMEWORKS } = require("./data/frameworks.cjs");
const { MAPPINGS } = require("./data/mappings.cjs");
const { EVIDENCE_BINDINGS } = require("./data/evidence.cjs");
const { bindingCountsFor, custodyOnlyReleaseClose, hydrateBinding, loadEvidence, soleProofAdmissible, versionFileOnly } = require("./evidence.cjs");
const { selectMappings, unmappedControls, walkMappings } = require("./mappings.cjs");
const { applyOverrides, buildMatrix, customerResponsibilityCount } = require("./responsibility.cjs");
const { isExternal, isUnsupported, satisfactionFor } = require("./satisfaction.cjs");
const { assessStaleness } = require("./staleness.cjs");
const { assertReportsSafe, buildReports, claimProblems, publicDisclosure, renderFramework, renderView, writeReports } = require("./reports.cjs");

function loadCatalog() {
  const problems = catalogProblems(CONTROLS);
  if (problems.length > 0) throw new Error(problems.join("; "));
  return CONTROLS;
}

module.exports = {
  ...constants,
  CONTROLS,
  EVIDENCE_BINDINGS,
  FRAMEWORKS,
  MAPPINGS,
  applyOverrides,
  assertReportsSafe,
  bindingCountsFor,
  canonicalize,
  custodyOnlyReleaseClose,
  claimProblems,
  assessStaleness,
  buildMatrix,
  buildReports,
  catalogProblems,
  controlProblems,
  customerResponsibilityCount,
  hydrateBinding,
  isExternal,
  isUnsupported,
  loadCatalog,
  loadEvidence,
  publicDisclosure,
  renderFramework,
  renderView,
  satisfactionFor,
  stableStringify,
  selectMappings,
  soleProofAdmissible,
  unmappedControls,
  versionFileOnly,
  walkMappings,
  writeReports,
};
