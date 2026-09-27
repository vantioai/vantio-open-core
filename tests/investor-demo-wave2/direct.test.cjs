"use strict";

const assert = require("node:assert/strict");
const { execFileSync, execSync } = require("node:child_process");
const { mkdtempSync, readFileSync, existsSync, writeFileSync, mkdirSync } = require("node:fs");
const { tmpdir } = require("node:os");
const path = require("node:path");
const test = require("node:test");
const {
  BANNER,
  CANARY,
  CARD_IDS,
  CLASSIFICATION_AWAITING,
  CLASSIFICATION_READY,
  CLI_VERSION,
  PROOF_CLASSES,
  proposePolicy,
  runSession,
  uninstallSession,
  verifyExport,
} = require("../../packages/investor-demo-wave2/src/index.cjs");

const REPO = path.resolve(__dirname, "..", "..");

function operatorHome() {
  const dir = mkdtempSync(path.join(tmpdir(), "vantio-operator-"));
  mkdirSync(path.join(dir, ".vantio", "runs"), { recursive: true });
  writeFileSync(path.join(dir, ".vantio", "runs", "keep.json"), "{\"keep\":true}\n");
  return dir;
}

function finish(result) {
  return uninstallSession(result.sentinelPath);
}

test("live CLI session labels every card and stays internal until uninstall", () => {
  const operator = operatorHome();
  const result = runSession({
    repoRoot: REPO,
    operatorHome: operator,
    traceId: "0x00000000000000a2",
    startedAt: "2026-09-27T00:00:00.000Z",
  });
  assert.equal(result.producer_classification, CLASSIFICATION_AWAITING);
  assert.equal(result.session.mode, "LIVE_CLI");
  assert.equal(result.session.external_proof, "NOT_PROVED_EXTERNAL");
  assert.equal(result.session.announcement, "HOLD");
  assert.equal(result.session.visual_completion_counts, false);
  assert.equal(result.session.customer_activity_total, 0);
  assert.equal(result.session.cli_reopened, false);
  assert.equal(result.session.cli_package_version, CLI_VERSION);
  assert.equal(result.session.envelope.evidence_origin, "SIMULATED_DEMO");
  assert.equal(result.session.envelope.producer, "demo_command");
  assert.equal(result.session.envelope.action, "OBSERVED");
  assert.equal(result.session.envelope.content, null);
  assert.equal(result.session.envelope.trace_id, "0x00000000000000a2");
  assert.notEqual(result.session.live.trace_id, result.session.envelope.trace_id);
  assert.equal(result.session.live.cli_file_missing_origin, true);
  assert.equal(result.session.live.discover_is_customer_total, false);
  assert.equal(result.session.cards.length, CARD_IDS.length);
  for (const id of CARD_IDS) {
    const card = result.session.cards.find((item) => item.id === id);
    assert.ok(card, id);
    assert.ok(PROOF_CLASSES.includes(card.proof_class), card.proof_class);
    assert.equal(card.external_proof, "NOT_PROVED_EXTERNAL");
    assert.equal(card.counted_in_customer_activity, false);
    assert.ok(result.report.includes(`[${id}] proof_class=${card.proof_class}`));
  }
  assert.ok(result.report.includes(BANNER));
  assert.equal(result.session.cli_invocations.filter((row) => row.args[0] === "demo").length, 1);
  assert.equal(verifyExport(result.exportPath).ok, true);
  assert.equal(verifyExport(result.exportPath).producer_classification, CLASSIFICATION_AWAITING);

  const done = finish(result);
  assert.equal(done.producer_classification, CLASSIFICATION_READY);
  assert.equal(verifyExport(done.exportPath).ok, true);
  assert.equal(existsSync(path.join(path.dirname(result.sentinelPath), "demo-home")), false);
  assert.equal(existsSync(path.join(operator, ".vantio", "runs", "keep.json")), true);
  const ready = JSON.parse(readFileSync(done.exportPath, "utf8"));
  assert.equal(ready.cards.find((card) => card.id === "uninstall").executed, true);
  assert.equal(ready.cards.find((card) => card.id === "uninstall").proof_class, "INTERNAL_FUNCTIONAL");
});

test("offline fallback is labeled, resettable, and not a live CLI claim", () => {
  const operator = operatorHome();
  const result = runSession({
    repoRoot: REPO,
    operatorHome: operator,
    forceOffline: true,
  });
  assert.equal(result.session.mode, "OFFLINE_FALLBACK");
  assert.equal(result.session.cards.find((card) => card.id === "optics_observation").proof_class, "OFFLINE_FALLBACK");
  assert.equal(result.session.cards.find((card) => card.id === "workload_discovery").proof_class, "OFFLINE_FALLBACK");
  assert.equal(result.session.cards.find((card) => card.id === "optics_observation").simulation_label, "SIMULATED_DEMO");
  assert.equal(result.session.cli_invocations.length, 0);
  assert.equal(result.session.customer_activity_total, 0);
  assert.equal(result.producer_classification, CLASSIFICATION_AWAITING);
  const done = finish(result);
  assert.equal(done.producer_classification, CLASSIFICATION_READY);
  assert.equal(verifyExport(done.exportPath).external_proof, "NOT_PROVED_EXTERNAL");
});

test("coverage, authority, health, and decisions stay inside their proof classes", () => {
  const operator = operatorHome();
  const result = runSession({ repoRoot: REPO, operatorHome: operator, forceOffline: true });
  const coverage = result.session.cards.find((card) => card.id === "coverage");
  assert.equal(coverage.proof_class, "NARRATED_BOUNDARY");
  assert.equal(coverage.detail.unobserved_means_blocked, false);
  assert.equal(coverage.detail.room_executed_agent, false);
  const authority = result.session.authority;
  assert.equal(authority.accepted.state, "PROPOSED");
  assert.equal(authority.accepted.active, false);
  assert.equal(authority.refused.state, "REFUSED");
  assert.equal(authority.refused.active, false);
  assert.equal(result.session.health.host_protection_state, "not_enrolled");
  assert.equal(result.session.health.host_executed, false);
  assert.equal(result.session.recovery.claims_host_recovered, false);
  assert.equal(result.session.policy.applied, false);
  assert.equal(result.session.decisions.applied, false);
  assert.equal(result.session.canary.enforcement_applied, false);
  assert.equal(result.session.canary.canary_present_in_stored_record, false);
  assert.equal(readFileSync(result.exportPath, "utf8").includes(CANARY), false);
  finish(result);
});

test("the bin runs offline and verify accepts the export", () => {
  const operator = operatorHome();
  const sessionRoot = mkdtempSync(path.join(tmpdir(), "vantio-investor-demo-bin-"));
  const bin = path.join(REPO, "packages", "investor-demo-wave2", "bin", "investor-demo.cjs");
  const stdout = execFileSync(process.execPath, [
    bin,
    "run",
    "--offline",
    "--repo",
    REPO,
    "--operator-home",
    operator,
    "--session-root",
    sessionRoot,
  ], { encoding: "utf8" });
  assert.match(stdout, /proof_class=/);
  assert.match(stdout, /producer_classification=INVESTOR_DEMO_WAVE2_AWAITING_UNINSTALL/);
  const exportPath = path.join(sessionRoot, "export", "session-export.json");
  const verified = execFileSync(process.execPath, [bin, "verify", exportPath], { encoding: "utf8" });
  assert.match(verified, /"ok":true/);
  const sentinel = path.join(sessionRoot, "sentinel.json");
  assert.throws(() => proposePolicy(sentinel), (error) => error.code === "REFUSED_REVOKED");
  const removed = execFileSync(process.execPath, [bin, "uninstall", sentinel], { encoding: "utf8" });
  assert.match(removed, /INVESTOR_DEMO_WAVE2_READY_FOR_COUNCIL/);
});

test("frozen CLI 0.3.24 bytes are untouched", () => {
  const head = execSync("git rev-parse HEAD:packages/vantio-cli/bin/vantio.js", { cwd: REPO, encoding: "utf8" }).trim();
  const work = execSync("git hash-object packages/vantio-cli/bin/vantio.js", { cwd: REPO, encoding: "utf8" }).trim();
  assert.equal(work, head);
  const version = JSON.parse(readFileSync(path.join(REPO, "packages/vantio-cli/package.json"), "utf8")).version;
  assert.equal(version, "0.3.24");
});
