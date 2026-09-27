"use strict";

const { createHash } = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const { REJECTED_SOLE_PROOFS } = require("./constants.cjs");
const { EVIDENCE_BINDINGS } = require("./data/evidence.cjs");

function repoRoot() {
  return path.resolve(__dirname, "../../..");
}

function sha256File(filePath) {
  const bytes = fs.readFileSync(filePath);
  return createHash("sha256").update(bytes).digest("hex");
}

function soleProofAdmissible(kind) {
  return !REJECTED_SOLE_PROOFS.includes(kind);
}

function rejectedSoleProof(binding) {
  const kinds = binding.sole_proof_kinds || [];
  if (kinds.length === 0) return false;
  return kinds.every((kind) => !soleProofAdmissible(kind));
}

function bindingCountsFor(binding, control) {
  if (!binding.counts_toward_satisfaction) return false;
  if (rejectedSoleProof(binding)) return false;
  if (!(binding.count_control_ids || []).includes(control.control_id)) return false;
  if (binding.artifact_status === "MISSING") return false;
  if (binding.freshness === "UNSET" || binding.freshness === "STALE") return false;
  if (binding.proof_class === "NOT_COMPLIANCE_ELIGIBLE" || binding.proof_class === "BLOCKED_UNSET" || binding.proof_class === "NONE") {
    return false;
  }
  if (control.implementation_state === "NOT_IMPLEMENTED" || control.implementation_state === "DESIGNED") return false;
  if (binding.independent_verifier === binding.producer && control.verification_state === "INDEPENDENTLY_TESTED") return false;
  return true;
}

function hydrateBinding(binding, root) {
  const artifacts = [];
  let missing = false;
  for (const relative of binding.artifacts) {
    const absolute = path.join(root, relative);
    if (!fs.existsSync(absolute) || !fs.statSync(absolute).isFile()) {
      missing = true;
      artifacts.push({
        path: relative,
        sha256: null,
        present: false,
      });
      continue;
    }
    artifacts.push({
      path: relative,
      sha256: sha256File(absolute),
      present: true,
    });
  }
  const artifactStatus = binding.artifacts.length === 0 ? "NO_ARTIFACT" : missing ? "MISSING" : "PRESENT";
  return {
    ...binding,
    artifact_records: artifacts,
    artifact_status: artifactStatus,
    verification_result: missing ? "ARTIFACT_MISSING" : binding.verification_result,
    informs_posture: missing ? false : binding.informs_posture,
    counts_toward_satisfaction: missing ? false : binding.counts_toward_satisfaction,
  };
}

function loadEvidence(root = repoRoot()) {
  return EVIDENCE_BINDINGS.map((binding) => hydrateBinding(binding, root));
}

module.exports = {
  bindingCountsFor,
  hydrateBinding,
  loadEvidence,
  rejectedSoleProof,
  repoRoot,
  soleProofAdmissible,
};
