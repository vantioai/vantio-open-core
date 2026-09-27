"use strict";

const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const {
  PRODUCER_CLASSIFICATION,
  CLAIMS,
  SURFACES,
  MECHANISMS,
  NOT_REIMPLEMENTED,
  CITATIONS,
  PRIVATE_TIP,
  FIXTURE_HOST,
  DISPOSITIONS,
} = require("./catalog.cjs");
const { CASES } = require("./cases.cjs");
const { evaluate, snapshot } = require("./evaluate.cjs");
const { collectHostFacts } = require("./host-facts.cjs");
const { proveLiveChild } = require("./descendant.cjs");
const { proveEvidence } = require("./evidence.cjs");

function hostFor(entry) {
  return {
    ...structuredClone(FIXTURE_HOST),
    ...structuredClone(entry.host || {}),
  };
}

function runPureCases() {
  return CASES.map((entry) => {
    const host = hostFor(entry);
    const before = snapshot(host);
    const decision = evaluate(host, entry.attempt);
    const after = snapshot(host);
    if (before !== after) {
      throw new Error(`${entry.id} mutated the host`);
    }
    if (decision.kernel_executed !== false || decision.universal_linux !== false || decision.authority_widened !== false) {
      throw new Error(`${entry.id} widened authority or claimed a kernel execution`);
    }
    if (entry.id === "credentials-token" && JSON.stringify(decision).includes(entry.attempt.token)) {
      throw new Error("credential token was copied into the decision");
    }
    return {
      id: entry.id,
      surface: entry.surface,
      ...decision,
    };
  });
}

function prove() {
  const pure = runPureCases();
  const facts = collectHostFacts();
  const child = proveLiveChild();
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "pe-host-authority-"));
  let evidence;
  try {
    evidence = proveEvidence(dir);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
  const bySurface = {};
  for (const surface of SURFACES) bySurface[surface.id] = [];
  for (const row of pure) bySurface[row.surface].push(row.id);
  bySurface.descendants.push(child.id);
  for (const row of evidence.cases) bySurface.evidence_tampering.push(row.id);
  bySurface.privileges.push("privileges-local-process");

  for (const surface of SURFACES) {
    if (bySurface[surface.id].length === 0) {
      throw new Error(`surface ${surface.id} has no cases`);
    }
    for (const mechanismId of surface.mechanisms) {
      if (!MECHANISMS[mechanismId]) throw new Error(`missing mechanism ${mechanismId}`);
    }
  }

  const localPrivilege = {
    id: "privileges-local-process",
    surface: "privileges",
    disposition: facts.euid === 0 || facts.bpf_writable_by_this_euid || !facts.cap_eff_zero
      ? "NAMED_RESIDUAL"
      : "NOT_COVERED",
    mechanism_id: "local_effective_capabilities",
    kernel_executed: false,
    universal_linux: false,
    authority_widened: false,
    execution: "THIS_PROCESS",
    euid: facts.euid,
    cap_eff_zero: facts.cap_eff_zero,
    bpf_writable_by_this_euid: facts.bpf_writable_by_this_euid,
    reason: "local_process_fact_not_a_kernel_load",
  };
  if (!DISPOSITIONS.includes(localPrivilege.disposition)) {
    throw new Error("local privilege disposition missing");
  }

  return {
    producer_classification: PRODUCER_CLASSIFICATION,
    council_verdict: "PENDING_INDEPENDENT_COUNCIL",
    audience: "INTERNAL_RESTRICTED",
    universal_linux_control: false,
    kernel_loaded_this_force: false,
    loader_mutated_this_force: false,
    stranger_host: "NOT_RUN",
    customer_deploy: false,
    clean_host_infrastructure: false,
    private_tip: PRIVATE_TIP,
    citations: CITATIONS,
    claims: CLAIMS.slice(),
    not_reimplemented: NOT_REIMPLEMENTED,
    surfaces: SURFACES.map((surface) => ({
      id: surface.id,
      mechanisms: surface.mechanisms,
      supported_authority: surface.supported_authority,
      case_ids: bySurface[surface.id],
    })),
    host_facts: facts,
    local_privilege: localPrivilege,
    live_child: child,
    evidence: evidence.cases,
    cases: pure,
  };
}

module.exports = {
  prove,
  runPureCases,
  hostFor,
};
