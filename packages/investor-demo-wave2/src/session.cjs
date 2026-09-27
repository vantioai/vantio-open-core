"use strict";

const { randomBytes } = require("node:crypto");
const { existsSync, lstatSync, mkdirSync, readdirSync, readFileSync, rmSync } = require("node:fs");
const { tmpdir } = require("node:os");
const path = require("node:path");
const {
  AUDIENCE,
  BANNER,
  BASE_COMMIT,
  BEAT_IDS,
  CLASSIFICATION_AWAITING,
  CLASSIFICATION_BLOCKED,
  CLASSIFICATION_READY,
  CLI_VERSION,
  DESIGN_TIP,
  F1_TRACE,
  HOSTNAME,
  LIMITATIONS_STATED,
  NARRATED_BEATS,
  SCHEMA_STATUS,
} = require("./constants.cjs");
const { seal } = require("./canonical.cjs");
const { probeCli, scanRuns } = require("./cli-probe.cjs");
const {
  buildEnvelope,
  coverageReport,
  dropCanaryPayload,
  evaluateDescendant,
  loadProtectionStates,
  useProtectionState,
} = require("./model.cjs");
const { assertPlannedLayout, createSentinel, readSentinel, writeJson, readJson } = require("./safety.cjs");
const { assess, classificationFor, verifyExport } = require("./verify.cjs");
const { renderReport } = require("./report.cjs");

function makeCard(fields) {
  const card = {
    external_proof: "NOT_PROVED_EXTERNAL",
    customer_validation: "UNSET",
    evidence_tier: "UNSET",
    counted_in_customer_activity: false,
    announcement: "HOLD",
    ...fields,
  };
  if (card.counted_in_customer_activity !== false) {
    const error = new Error("REFUSED_SYNTHETIC_AS_CUSTOMER");
    error.code = "REFUSED_SYNTHETIC_AS_CUSTOMER";
    throw error;
  }
  return card;
}

function htmlProofs(dir) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir).filter((name) => /^vantio-proof-.*\.html$/.test(name)).sort();
}

function plantUnlabeled(demoHome) {
  const dir = path.join(demoHome, ".vantio", "runs");
  mkdirSync(dir, { recursive: true, mode: 0o700 });
  const defect = {
    vantio_run_log: "1",
    trace_id: F1_TRACE,
    calls: [{ hostname: "api.openai.com", action: "OBSERVED", bytes: 12 }],
  };
  writeJson(path.join(dir, `${F1_TRACE}.json`), defect);
}

function loadCliPackageVersion(repoRoot) {
  const pkg = JSON.parse(readFileSync(path.join(repoRoot, "packages/vantio-cli/package.json"), "utf8"));
  return pkg.version;
}

function authorityFixtures() {
  const parentScope = {
    hosts: ["host-a"],
    destinations: [HOSTNAME],
    actions: ["observe"],
  };
  const accepted = evaluateDescendant({
    redelegation: "forbidden",
    childRequestsRedelegation: false,
    domain: "workload",
    delegatorKind: "customer",
    delegateKind: "workload",
    parentScope,
    childScope: {
      hosts: ["host-a"],
      destinations: [HOSTNAME],
      actions: ["observe"],
    },
  });
  const refused = evaluateDescendant({
    redelegation: "forbidden",
    childRequestsRedelegation: true,
    domain: "security",
    delegatorKind: "workload",
    delegateKind: "workload",
    parentScope,
    childScope: {
      hosts: ["host-a", "host-b"],
      destinations: [HOSTNAME, "api.openai.com"],
      actions: ["observe", "enforce"],
    },
  });
  return { accepted, refused };
}

function buildBeats(cli, f1) {
  const live = cli.mode === "LIVE_CLI";
  const narrated = (id) => ({
    id,
    founder_text: "ABSENT",
    simulation_label: "NARRATED_BOUNDARY",
    proof_class: "NARRATED_BOUNDARY",
    source: NARRATED_BEATS[id],
    command: null,
    executed: false,
  });
  const command = (id, name, ok) => ({
    id,
    founder_text: "ABSENT",
    simulation_label: "SIMULATED_DEMO",
    proof_class: live && ok ? "INTERNAL_FUNCTIONAL" : (cli.mode === "LIVE_DEVIATION" ? "HELD_NOT_EXECUTED" : "OFFLINE_FALLBACK"),
    source: "packages/vantio-cli/bin/vantio.js",
    command: name,
    executed: live && ok,
  });
  return [
    narrated("B01"),
    narrated("B02"),
    { ...command("B03", "--version", true), simulation_label: "NARRATED_BOUNDARY" },
    { ...command("B04", "status", true), simulation_label: "NARRATED_BOUNDARY" },
    narrated("B05"),
    narrated("B06"),
    command("B07", "demo", true),
    command("B08", "read-run-file", true),
    command("B09", "prove", true),
    narrated("B10"),
    narrated("B11"),
    narrated("B12"),
    narrated("B13"),
    narrated("B14"),
    {
      id: "B15",
      founder_text: "ABSENT",
      simulation_label: f1 ? "INJECTED_UNLABELED_SYNTHETIC" : "SIMULATED_DEMO",
      proof_class: live ? "INTERNAL_FUNCTIONAL" : (cli.mode === "LIVE_DEVIATION" ? "HELD_NOT_EXECUTED" : "OFFLINE_FALLBACK"),
      source: "docs/programs/production-readiness/demo/07-FAILURE-INJECTION-OUTLINE.md",
      command: "discover",
      executed: live,
      f1_disposition: f1 ? "DISCARDED" : "NOT_PLANTED",
    },
    narrated("B16"),
    {
      id: "B17",
      founder_text: "ABSENT",
      simulation_label: "NARRATED_BOUNDARY",
      proof_class: "HELD_NOT_EXECUTED",
      source: "docs/programs/production-readiness/demo/05-RESET-OUTLINE.md",
      command: "uninstall",
      executed: false,
    },
    narrated("B18"),
  ];
}

function observationPassed(cli) {
  return cli.mode === "LIVE_CLI" || cli.mode === "OFFLINE_FALLBACK";
}

function buildCards(state) {
  const live = state.cli.mode === "LIVE_CLI";
  const offline = state.cli.mode === "OFFLINE_FALLBACK";
  const discoveryClass = live ? "INTERNAL_FUNCTIONAL" : (offline ? "OFFLINE_FALLBACK" : "HELD_NOT_EXECUTED");
  return [
    makeCard({
      id: "workload_discovery",
      title: "Workload discovery",
      proof_class: discoveryClass,
      is_simulation: true,
      simulation_label: "SIMULATED_DEMO",
      functional_check: "wave2_totals_exclude_simulated_and_unlabeled_rows",
      functional_passed: observationPassed(state.cli) && state.runScan.customer_activity_total === 0,
      statement: "Discovery lists the demo host under the simulation banner. The wave2 total that says customer activity is 0. A CLI observed-locally sentence, when the frozen CLI ran, is not that total.",
      detail: {
        customer_activity_total: state.runScan.customer_activity_total,
        simulated_demo_rows: state.runScan.simulated_demo_rows,
        unlabeled_synthetic_rows: state.runScan.unlabeled_synthetic_rows,
        cli_discover_is_customer_total: false,
        cli_discover_ran: live,
      },
    }),
    makeCard({
      id: "optics_observation",
      title: "Optics observation",
      proof_class: discoveryClass,
      is_simulation: true,
      simulation_label: "SIMULATED_DEMO",
      functional_check: "stub_or_offline_fallback_is_labeled",
      functional_passed: observationPassed(state.cli),
      statement: "The observation is the in-process stub or the labeled offline fallback. CLI 0.3.24 still writes no evidence_origin. The wave2 envelope carries SIMULATED_DEMO.",
      detail: {
        mode: state.cli.mode,
        cli_file_missing_origin: live ? true : "NOT_RUN",
        envelope_origin: state.envelope.evidence_origin,
        hostname: HOSTNAME,
        network: "none",
      },
    }),
    makeCard({
      id: "coverage",
      title: "Coverage",
      proof_class: "NARRATED_BOUNDARY",
      is_simulation: false,
      simulation_label: null,
      functional_check: "unobserved_is_not_blocked",
      functional_passed: state.coverage.rule_holds === true && state.coverage.room_executed_agent === false,
      statement: "An unobserved path is not a blocked path. This room did not start an agent.",
      detail: state.coverage,
    }),
    makeCard({
      id: "ingress_egress_attempts",
      title: "Ingress and egress attempts",
      proof_class: "SIMULATED_LABELED",
      is_simulation: true,
      simulation_label: "SIMULATED_DEMO",
      functional_check: "one_labeled_egress_and_no_listener",
      functional_passed: state.listenerOpened === false && state.egressCount === 1,
      statement: "One labeled egress stub was recorded. No ingress listener was opened. No ingress row is not a block.",
      detail: {
        egress_attempts: [{
          hostname: HOSTNAME,
          method: "POST",
          path: "/v1/chat/completions",
          bytes: 0,
          network: "none",
          action: "OBSERVED",
          simulation_label: "SIMULATED_DEMO",
        }],
        ingress_attempts: [],
        ingress_disposition: "NOT_OBSERVED",
        listener_opened: false,
      },
    }),
    makeCard({
      id: "policy_proposal",
      title: "Policy proposal",
      proof_class: "SIMULATED_LABELED",
      is_simulation: true,
      simulation_label: "SIMULATED_DEMO",
      functional_check: "proposal_not_applied",
      functional_passed: state.policy.applied === false && state.policy.state !== "ACTIVE",
      statement: "A labeled proposal was recorded and was not applied. Rollback leaves it rolled back.",
      detail: state.policy,
    }),
    makeCard({
      id: "simulation",
      title: "Simulation",
      proof_class: "INTERNAL_FUNCTIONAL",
      is_simulation: true,
      simulation_label: "SIMULATED_DEMO",
      functional_check: "banner_and_envelope",
      functional_passed: state.banner === BANNER && state.envelope.simulation_label === "SIMULATED_DEMO",
      statement: BANNER,
      detail: { banner: state.banner, envelope_trace_id: state.envelope.trace_id },
    }),
    makeCard({
      id: "canary_enforcement",
      title: "Canary enforcement",
      proof_class: "INTERNAL_FUNCTIONAL",
      is_simulation: true,
      simulation_label: "SIMULATED_DEMO",
      functional_check: "canary_absent_and_enforcement_not_applied",
      functional_passed: state.canary.canary_present_in_stored_record === false && state.canary.enforcement_applied === false,
      statement: "A privacy canary was presented to the writer and is absent from the stored record. No enforcement action was applied.",
      detail: {
        canary_presented: true,
        canary_present_in_stored_record: false,
        enforcement_applied: false,
        action_written: "NONE",
      },
    }),
    makeCard({
      id: "allowed_blocked",
      title: "Allowed and blocked",
      proof_class: "SIMULATED_LABELED",
      is_simulation: true,
      simulation_label: "SIMULATED_DEMO",
      functional_check: "shapes_not_applied_and_run_files_have_no_enforcement_tokens",
      functional_passed: state.decisions.applied === false && state.runScan.forbidden_tokens_present === false,
      statement: "Permit and deny shapes are labeled simulations with applied false. The room did not write an enforcement event.",
      detail: state.decisions,
    }),
    makeCard({
      id: "descendant_authority",
      title: "Descendant authority",
      proof_class: "INTERNAL_FUNCTIONAL",
      is_simulation: true,
      simulation_label: "SIMULATED_DEMO",
      functional_check: "subset_stays_proposed_and_widen_is_refused",
      functional_passed: state.authority.accepted.state === "PROPOSED"
        && state.authority.accepted.active === false
        && state.authority.refused.state === "REFUSED"
        && state.authority.refused.refusals.includes("WIDENS_AUTHORITY"),
      statement: "A fixture child inside the parent scope stays PROPOSED. A widening child is REFUSED. Neither result is ACTIVE. No host reported attachment.",
      detail: state.authority,
    }),
    makeCard({
      id: "health_degradation",
      title: "Health degradation",
      proof_class: "SIMULATED_LABELED",
      is_simulation: true,
      simulation_label: "SIMULATED_DEMO",
      functional_check: "degraded_is_in_the_ws4_catalog",
      functional_passed: state.health.degraded_catalog_member === true && state.health.host_executed === false,
      statement: "Degraded is a labeled fixture checked against the WS4 protection-state catalog. No host was enrolled.",
      detail: state.health,
    }),
    makeCard({
      id: "recovery",
      title: "Recovery",
      proof_class: "INTERNAL_FUNCTIONAL",
      is_simulation: true,
      simulation_label: "SIMULATED_DEMO",
      functional_check: "session_recovers_without_claiming_host_enrollment",
      functional_passed: state.recovery.host_protection_state === "not_enrolled" && state.recovery.session_state === "observing",
      statement: "The demo session record returns to observing. The host protection state stays not_enrolled.",
      detail: state.recovery,
    }),
    makeCard({
      id: "evidence_export",
      title: "Evidence export",
      proof_class: "INTERNAL_FUNCTIONAL",
      is_simulation: true,
      simulation_label: "SIMULATED_DEMO",
      functional_check: "export_carries_labels_and_not_a_customer_report",
      functional_passed: true,
      statement: "The export is the labeled session record. It is not an HTML customer proof.",
      detail: { format: "json", html_customer_report: false },
    }),
    makeCard({
      id: "revocation",
      title: "Revocation",
      proof_class: "INTERNAL_FUNCTIONAL",
      is_simulation: true,
      simulation_label: "SIMULATED_DEMO",
      functional_check: "demo_session_revoked_without_credential_rotation",
      functional_passed: state.revoked === true && state.credentialRotated === false,
      statement: "The demo session sentinel is revoked. No credential was created or rotated. No customer grant was revoked.",
      detail: { revoked: true, credential_rotated: false, customer_grant_revoked: false },
    }),
    makeCard({
      id: "rollback",
      title: "Rollback",
      proof_class: "INTERNAL_FUNCTIONAL",
      is_simulation: true,
      simulation_label: "SIMULATED_DEMO",
      functional_check: "controls_return_to_baseline_and_run_files_remain",
      functional_passed: state.policy.state === "ROLLED_BACK" && state.runFilesRetained === true,
      statement: "Policy and health controls return to the pre-proposal baseline. Run files stay until uninstall.",
      detail: { policy_state: state.policy.state, run_files_deleted: false },
    }),
    makeCard({
      id: "uninstall",
      title: "Uninstall",
      proof_class: "HELD_NOT_EXECUTED",
      is_simulation: true,
      simulation_label: "SIMULATED_DEMO",
      functional_check: "demo_home_removed_operator_home_kept",
      functional_passed: false,
      executed: false,
      statement: "Uninstall removes the recorded demo home after the sentinel checks. It does not remove the operator home.",
      detail: { executed: false },
    }),
    makeCard({
      id: "independent_verification",
      title: "Independent verification",
      proof_class: "INTERNAL_FUNCTIONAL",
      is_simulation: false,
      simulation_label: null,
      functional_check: "local_recompute_not_an_external_verifier",
      functional_passed: true,
      statement: "Verification recomputes this export locally. Council is pending. The external proof field stays unset as an external proof.",
      detail: { council_status: "PENDING_INDEPENDENT_COUNCIL", verifier: "local_recompute" },
    }),
  ];
}

function publish(doc) {
  const draft = { ...doc, producer_classification: CLASSIFICATION_AWAITING };
  const problems = assess(draft).filter((item) => item !== "uninstall_not_executed" && item !== "awaiting_uninstall_flag");
  const producerClassification = problems.length > 0 ? CLASSIFICATION_BLOCKED : CLASSIFICATION_AWAITING;
  return seal({ ...draft, producer_classification: producerClassification, invariant_problems: problems });
}

function runSession(options = {}) {
  const repoRoot = path.resolve(options.repoRoot || path.join(__dirname, "..", "..", ".."));
  const operatorHome = path.resolve(options.operatorHome || process.env.HOME);
  const sessionRoot = options.sessionRoot
    ? path.resolve(options.sessionRoot)
    : path.join(tmpdir(), `vantio-investor-demo-${randomBytes(6).toString("hex")}`);
  const demoHome = path.join(sessionRoot, "demo-home");
  if (existsSync(sessionRoot) && lstatSync(sessionRoot).isSymbolicLink()) {
    const error = new Error("REFUSED_SYMLINK");
    error.code = "REFUSED_SYMLINK";
    throw error;
  }
  assertPlannedLayout({ sessionRoot, demoHome, operatorHome, repoRoot });
  mkdirSync(demoHome, { recursive: true, mode: 0o700 });
  const created = createSentinel(
    { sessionRoot, demoHome, operatorHome, repoRoot },
    {
      sessionId: randomBytes(8).toString("hex"),
      sessionToken: randomBytes(16).toString("hex"),
      createdAt: options.startedAt || new Date().toISOString(),
    },
  );

  const beforeHtml = new Set(htmlProofs(repoRoot));
  const cliPackageVersion = loadCliPackageVersion(repoRoot);
  const cliPath = options.cliPath || path.join(repoRoot, "packages", "vantio-cli", "bin", "vantio.js");
  const cli = probeCli({
    repoRoot,
    demoHome,
    cliPath,
    forceOffline: options.forceOffline === true,
  });
  const afterHtml = htmlProofs(repoRoot).filter((name) => !beforeHtml.has(name));
  created.sentinel.mode = cli.mode;
  created.sentinel.html_proofs = afterHtml.map((name) => path.join(repoRoot, name));
  created.sentinel.cli_invocations = cli.invocations.map((row) => row.args);
  writeJson(created.sentinelPath, created.sentinel);

  if (options.injectUnlabeled === true) plantUnlabeled(demoHome);
  const runScan = scanRuns(demoHome);
  const envelope = buildEnvelope({
    traceId: options.traceId,
    startedAt: options.startedAt,
    evidenceOrigin: options.evidenceOrigin,
  });
  const envelopeDir = path.join(demoHome, ".vantio", "demo-session");
  mkdirSync(envelopeDir, { recursive: true, mode: 0o700 });
  writeJson(path.join(envelopeDir, "labeled-envelope.json"), envelope);

  const catalog = (() => {
    try {
      return { value: loadProtectionStates(repoRoot), error: null };
    } catch (error) {
      return { value: null, error: error.code || "HEALTH_CATALOG_UNAVAILABLE" };
    }
  })();
  const degraded = catalog.value ? useProtectionState(catalog.value, "degraded") : { ok: false, host_executed: false };
  const observing = catalog.value ? useProtectionState(catalog.value, "observing") : { ok: false };
  const notEnrolled = catalog.value ? useProtectionState(catalog.value, "not_enrolled") : { ok: false };
  const canary = dropCanaryPayload();
  const authority = authorityFixtures();
  const policy = {
    state: "ROLLED_BACK",
    proposal_state: "PROPOSED",
    applied: false,
    simulation_label: "SIMULATED_DEMO",
    counted_in_customer_activity: false,
  };
  const health = {
    degraded_catalog_member: degraded.ok === true,
    host_executed: false,
    host_protection_state: notEnrolled.ok ? "not_enrolled" : null,
    catalog_error: catalog.error,
    simulation_label: "SIMULATED_DEMO",
  };
  const recovery = {
    session_state: observing.ok ? "observing" : null,
    host_protection_state: notEnrolled.ok ? "not_enrolled" : null,
    claims_host_recovered: false,
    simulation_label: "SIMULATED_DEMO",
  };
  const decisions = {
    permit: { shape: "SIMULATED_PERMIT_SHAPE", applied: false, simulation_label: "SIMULATED_DEMO" },
    deny: { shape: "SIMULATED_DENY_SHAPE", applied: false, simulation_label: "SIMULATED_DEMO" },
    applied: false,
  };
  const provedF1 = cli.invocations.some((row) => row.args.some((arg) => String(arg).includes(F1_TRACE) || arg === "--from" || String(arg).startsWith("--from")));
  const f1 = options.injectUnlabeled === true ? {
    planted: true,
    trace_id: F1_TRACE,
    disposition: "DISCARDED",
    proved: provedF1,
    added_to_total: false,
    success_narration: false,
    display_to_investor: false,
    simulation_label: "INJECTED_UNLABELED_SYNTHETIC",
  } : null;

  created.sentinel.revoked = true;
  writeJson(created.sentinelPath, created.sentinel);

  const coverage = coverageReport();
  const cards = buildCards({
    cli,
    runScan,
    envelope,
    coverage,
    policy,
    canary,
    decisions,
    authority,
    health,
    recovery,
    revoked: true,
    credentialRotated: false,
    runFilesRetained: true,
    listenerOpened: false,
    egressCount: 1,
    banner: BANNER,
  });
  const beats = buildBeats(cli, f1);
  if (beats.map((beat) => beat.id).join() !== BEAT_IDS.join()) {
    throw new Error("BEAT_ORDER");
  }

  const doc = publish({
    schema: "vantio.investor-demo.wave2-export/v1",
    schema_status: SCHEMA_STATUS,
    audience: AUDIENCE,
    council_status: "PENDING_INDEPENDENT_COUNCIL",
    external_proof: "NOT_PROVED_EXTERNAL",
    customer_validation: "UNSET",
    evidence_tier: "UNSET",
    announcement: "HOLD",
    visual_completion_counts: false,
    design_tip: DESIGN_TIP,
    base_commit: BASE_COMMIT,
    founder_text: "ABSENT",
    cli_version_required: CLI_VERSION,
    cli_package_version: cliPackageVersion,
    cli_reopened: cliPackageVersion !== CLI_VERSION,
    mode: cli.mode,
    mode_reason: cli.reason,
    customer_activity_total: 0,
    customer_success_narration: false,
    unlabeled_file_success_narration: false,
    banner: BANNER,
    envelope,
    run_scan: runScan,
    policy,
    authority,
    health,
    recovery,
    coverage,
    decisions,
    canary: {
      canary_presented: canary.canary_presented,
      canary_present_in_stored_record: canary.canary_present_in_stored_record,
      enforcement_applied: canary.enforcement_applied,
    },
    f1,
    limitations_stated: [...LIMITATIONS_STATED],
    beats,
    cards,
    cli_invocations: cli.invocations.map((row) => ({ args: row.args, status: row.status })),
    live: cli.live,
  });

  const exportDir = path.join(created.resolved.sessionRoot, "export");
  mkdirSync(exportDir, { recursive: true, mode: 0o700 });
  const exportPath = path.join(exportDir, "session-export.json");
  writeJson(exportPath, doc);
  const verified = verifyExport(exportPath);
  if (!verified.ok) {
    const error = new Error(`EXPORT_INCONSISTENT:${verified.problems.join(",")}`);
    error.code = "EXPORT_INCONSISTENT";
    throw error;
  }
  return {
    sentinelPath: created.sentinelPath,
    exportPath,
    session: doc,
    report: renderReport(doc),
    producer_classification: doc.producer_classification,
  };
}

function loadExport(sentinel) {
  return readJson(path.join(sentinel.session_root, "export", "session-export.json"));
}

function storeExport(sentinel, doc) {
  const exportPath = path.join(sentinel.session_root, "export", "session-export.json");
  writeJson(exportPath, doc);
  return exportPath;
}

function proposePolicy(sentinelPath) {
  const sentinel = readSentinel(sentinelPath);
  if (sentinel.revoked === true) {
    const error = new Error("REFUSED_REVOKED");
    error.code = "REFUSED_REVOKED";
    throw error;
  }
  if (sentinel.removed === true) {
    const error = new Error("REFUSED_REMOVED");
    error.code = "REFUSED_REMOVED";
    throw error;
  }
  return {
    state: "PROPOSED",
    applied: false,
    simulation_label: "SIMULATED_DEMO",
    counted_in_customer_activity: false,
  };
}

function uninstallSession(sentinelPath) {
  const sentinel = readSentinel(sentinelPath);
  if (sentinel.removed === true) {
    const doc = loadExport(sentinel);
    return { already_removed: true, exportPath: path.join(sentinel.session_root, "export", "session-export.json"), producer_classification: doc.producer_classification };
  }
  const demoStat = lstatSync(sentinel.demo_home);
  if (demoStat.isSymbolicLink() || !demoStat.isDirectory()) {
    const error = new Error("REFUSED_SYMLINK");
    error.code = "REFUSED_SYMLINK";
    throw error;
  }
  for (const proof of sentinel.html_proofs || []) {
    const base = path.basename(proof);
    if (!/^vantio-proof-.*\.html$/.test(base)) continue;
    const resolved = path.resolve(proof);
    if (resolved === path.resolve(sentinel.operator_home) || resolved.startsWith(`${path.resolve(sentinel.operator_home)}${path.sep}`)) {
      continue;
    }
    if (existsSync(resolved) && !lstatSync(resolved).isSymbolicLink()) rmSync(resolved);
  }
  rmSync(sentinel.demo_home, { recursive: true });
  if (existsSync(sentinel.demo_home)) {
    const error = new Error("UNINSTALL_INCOMPLETE");
    error.code = "UNINSTALL_INCOMPLETE";
    throw error;
  }
  sentinel.removed = true;
  writeJson(path.join(sentinel.session_root, "sentinel.json"), sentinel);

  const doc = loadExport(sentinel);
  const cards = doc.cards.map((card) => {
    if (card.id !== "uninstall") return card;
    return {
      ...card,
      proof_class: "INTERNAL_FUNCTIONAL",
      functional_passed: true,
      executed: true,
      detail: { executed: true, operator_home_removed: false },
    };
  });
  const beats = doc.beats.map((beat) => (beat.id === "B17" ? { ...beat, executed: true, proof_class: "INTERNAL_FUNCTIONAL" } : beat));
  const drafted = { ...doc, cards, beats, producer_classification: CLASSIFICATION_AWAITING };
  delete drafted.canonical_sha256;
  const problems = assess(drafted).filter((item) => item !== "uninstall_not_executed" && item !== "awaiting_uninstall_flag");
  const producerClassification = problems.length > 0 ? CLASSIFICATION_BLOCKED : classificationFor(
    { ...drafted, producer_classification: CLASSIFICATION_READY, cards },
    problems,
  );
  const sealed = seal({ ...drafted, producer_classification: producerClassification, invariant_problems: problems });
  const exportPath = storeExport(sentinel, sealed);
  const verified = verifyExport(exportPath);
  if (!verified.ok) {
    const error = new Error(`EXPORT_INCONSISTENT:${verified.problems.join(",")}`);
    error.code = "EXPORT_INCONSISTENT";
    throw error;
  }
  return {
    already_removed: false,
    exportPath,
    producer_classification: sealed.producer_classification,
    session: sealed,
    report: renderReport(sealed),
  };
}

module.exports = {
  proposePolicy,
  runSession,
  uninstallSession,
};
