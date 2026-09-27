"use strict";

const assert = require("node:assert/strict");
const { mkdtempSync, readFileSync, writeFileSync, mkdirSync, symlinkSync, existsSync } = require("node:fs");
const { tmpdir } = require("node:os");
const path = require("node:path");
const test = require("node:test");
const {
  CANARY,
  CLASSIFICATION_READY,
  F1_TRACE,
  evaluateDescendant,
  proposePolicy,
  runSession,
  uninstallSession,
  useProtectionState,
  verifyExport,
  buildEnvelope,
  assertProducerVersion,
} = require("../../packages/investor-demo-wave2/src/index.cjs");
const { assess } = require("../../packages/investor-demo-wave2/src/verify.cjs");
const { scanRuns } = require("../../packages/investor-demo-wave2/src/cli-probe.cjs");
const { loadProtectionStates } = require("../../packages/investor-demo-wave2/src/model.cjs");

const REPO = path.resolve(__dirname, "..", "..");

function operatorHome() {
  const dir = mkdtempSync(path.join(tmpdir(), "vantio-operator-"));
  mkdirSync(path.join(dir, ".vantio", "runs"), { recursive: true });
  writeFileSync(path.join(dir, ".vantio", "runs", "keep.json"), "{\"keep\":true}\n");
  return dir;
}

test("unlabeled synthetic is discarded and is not a success", () => {
  const operator = operatorHome();
  const result = runSession({
    repoRoot: REPO,
    operatorHome: operator,
    injectUnlabeled: true,
  });
  assert.equal(result.session.f1.disposition, "DISCARDED");
  assert.equal(result.session.f1.proved, false);
  assert.equal(result.session.f1.added_to_total, false);
  assert.equal(result.session.f1.success_narration, false);
  assert.equal(result.session.f1.display_to_investor, false);
  assert.equal(result.session.customer_activity_total, 0);
  assert.equal(result.session.customer_success_narration, false);
  assert.equal(result.session.unlabeled_file_success_narration, false);
  assert.equal(result.session.run_scan.unlabeled_synthetic_rows, 1);
  assert.ok(result.session.limitations_stated.includes("L-FOUNDER-BEATS-ABSENT"));
  assert.equal(result.session.cli_invocations.some((row) => row.args.some((arg) => String(arg).includes(F1_TRACE))), false);
  assert.equal(result.session.cli_invocations.some((row) => row.args.some((arg) => String(arg).includes("--from"))), false);
  const demoHome = path.join(path.dirname(result.sentinelPath), "demo-home");
  assert.equal(existsSync(path.join(demoHome, ".vantio", "runs", `${F1_TRACE}.json`)), true);
  const done = uninstallSession(result.sentinelPath);
  assert.equal(done.producer_classification, CLASSIFICATION_READY);
  assert.equal(existsSync(demoHome), false);
  assert.equal(existsSync(path.join(operator, ".vantio", "runs", "keep.json")), true);
});

test("uninstall refuses the operator home, the checkout, and a symlink", () => {
  const operator = operatorHome();
  assert.throws(() => runSession({
    repoRoot: REPO,
    operatorHome: operator,
    sessionRoot: operator,
    forceOffline: true,
  }), (error) => error.code === "REFUSED_OPERATOR_HOME");
  assert.equal(existsSync(path.join(operator, ".vantio", "runs", "keep.json")), true);
  assert.equal(existsSync(path.join(operator, "demo-home")), false);

  assert.throws(() => runSession({
    repoRoot: REPO,
    operatorHome: operator,
    sessionRoot: path.join(REPO, "investor-demo-session"),
    forceOffline: true,
  }), (error) => error.code === "REFUSED_SOURCE_CHECKOUT");
  assert.equal(existsSync(path.join(REPO, "investor-demo-session")), false);

  const real = mkdtempSync(path.join(tmpdir(), "vantio-real-"));
  const link = path.join(tmpdir(), `vantio-link-${Date.now()}`);
  symlinkSync(real, link);
  assert.throws(() => runSession({
    repoRoot: REPO,
    operatorHome: operator,
    sessionRoot: link,
    forceOffline: true,
  }), (error) => error.code === "REFUSED_SYMLINK");
  assert.equal(existsSync(path.join(real, "demo-home")), false);
});

test("a forged sentinel cannot delete the operator home", () => {
  const operator = operatorHome();
  const result = runSession({ repoRoot: REPO, operatorHome: operator, forceOffline: true });
  const sentinelPath = result.sentinelPath;
  const sentinel = JSON.parse(readFileSync(sentinelPath, "utf8"));
  sentinel.demo_home = operator;
  writeFileSync(sentinelPath, `${JSON.stringify(sentinel, null, 2)}\n`);
  assert.throws(() => uninstallSession(sentinelPath), (error) => (
    error.code === "REFUSED_DEMO_HOME_SHAPE" || error.code === "REFUSED_OPERATOR_HOME"
  ));
  assert.equal(existsSync(path.join(operator, ".vantio", "runs", "keep.json")), true);
});

test("origin, trace, and producer version are refused when they leave the demo rule", () => {
  assert.throws(() => buildEnvelope({ evidenceOrigin: "LOCAL_OBSERVATION" }), (error) => error.code === "REFUSED_ORIGIN");
  assert.throws(() => buildEnvelope({ traceId: "not-a-trace" }), (error) => error.code === "REFUSED_TRACE_ID");
  assert.throws(() => buildEnvelope({ startedAt: "yesterday" }), (error) => error.code === "REFUSED_TIMESTAMP");
  assert.throws(() => assertProducerVersion("has spaces"), (error) => error.code === "REFUSED_PRODUCER_VERSION");
  assert.throws(() => assertProducerVersion("x".repeat(33)), (error) => error.code === "REFUSED_PRODUCER_VERSION");
  const envelope = buildEnvelope({ traceId: "0x00000000000000a2", startedAt: "2026-09-27T00:00:00.000Z" });
  assert.equal(Object.prototype.hasOwnProperty.call(envelope, "vantio_run_log"), false);
  assert.equal(envelope.evidence_origin, "SIMULATED_DEMO");
});

test("widening descendant authority and unknown health states fail closed", () => {
  const widened = evaluateDescendant({
    redelegation: "forbidden",
    childRequestsRedelegation: false,
    domain: "workload",
    delegatorKind: "customer",
    delegateKind: "workload",
    parentScope: { hosts: ["host-a"], destinations: ["optics-demo.invalid"], actions: ["observe"] },
    childScope: { hosts: ["host-a"], destinations: ["optics-demo.invalid", "api.openai.com"], actions: ["observe"] },
  });
  assert.equal(widened.state, "REFUSED");
  assert.equal(widened.active, false);
  assert.ok(widened.refusals.includes("WIDENS_AUTHORITY"));
  const redelegated = evaluateDescendant({
    redelegation: "allowed",
    childRequestsRedelegation: true,
    domain: "security",
    delegatorKind: "workload",
    delegateKind: "workload",
    parentScope: { hosts: ["host-a"], destinations: ["optics-demo.invalid"], actions: ["observe"] },
    childScope: { hosts: ["host-a"], destinations: ["optics-demo.invalid"], actions: ["observe"] },
  });
  assert.equal(redelegated.state, "REFUSED");
  assert.ok(redelegated.refusals.includes("REDELEGATION_FORBIDDEN"));
  assert.ok(redelegated.refusals.includes("WORKLOAD_CANNOT_HOLD_DOMAIN"));
  const catalog = loadProtectionStates(REPO);
  assert.equal(useProtectionState(catalog, "degraded").ok, true);
  assert.equal(useProtectionState(catalog, "protected_for_real").ok, false);
});

test("revocation blocks a later proposal and a second uninstall does not widen deletion", () => {
  const operator = operatorHome();
  const proof = path.join(operator, "vantio-proof-keep.html");
  writeFileSync(proof, "keep\n");
  const result = runSession({ repoRoot: REPO, operatorHome: operator, forceOffline: true });
  assert.throws(() => proposePolicy(result.sentinelPath), (error) => error.code === "REFUSED_REVOKED");
  const sentinel = JSON.parse(readFileSync(result.sentinelPath, "utf8"));
  sentinel.html_proofs = [proof];
  writeFileSync(result.sentinelPath, `${JSON.stringify(sentinel, null, 2)}\n`);
  const done = uninstallSession(result.sentinelPath);
  assert.equal(done.producer_classification, CLASSIFICATION_READY);
  assert.equal(existsSync(proof), true);
  const again = uninstallSession(result.sentinelPath);
  assert.equal(again.already_removed, true);
  assert.equal(existsSync(path.join(operator, ".vantio", "runs", "keep.json")), true);
});

test("run files with enforcement tokens are not customer activity", () => {
  const dir = mkdtempSync(path.join(tmpdir(), "vantio-runs-"));
  const runs = path.join(dir, ".vantio", "runs");
  mkdirSync(runs, { recursive: true });
  writeFileSync(path.join(runs, "bad.json"), `${JSON.stringify({
    vantio_run_log: "1",
    trace_id: "0xbad0000000000001",
    calls: [{ hostname: "api.openai.com", action: "BLOCKED_HOST", bytes: 4 }],
  })}\n`);
  const scan = scanRuns(dir);
  assert.equal(scan.forbidden_tokens_present, true);
  assert.equal(scan.customer_activity_total, 0);
  assert.equal(scan.unlabeled_synthetic_rows, 1);
});

test("a ready export cannot be rewritten into an external proof", () => {
  const operator = operatorHome();
  const result = runSession({ repoRoot: REPO, operatorHome: operator, forceOffline: true });
  const done = uninstallSession(result.sentinelPath);
  const doc = JSON.parse(readFileSync(done.exportPath, "utf8"));
  doc.external_proof = "PROVED_EXTERNAL";
  doc.producer_classification = CLASSIFICATION_READY;
  const problems = assess(doc);
  assert.ok(problems.includes("external_proof"));
  assert.equal(verifyExport(doc).ok, false);
  assert.equal(readFileSync(done.exportPath, "utf8").includes(CANARY), false);
  assert.equal(JSON.parse(readFileSync(done.exportPath, "utf8")).announcement, "HOLD");
});

test("missing proof class and a released announcement fail the invariant check", () => {
  const operator = operatorHome();
  const result = runSession({ repoRoot: REPO, operatorHome: operator, forceOffline: true });
  const doc = structuredClone(result.session);
  doc.cards[0].proof_class = "PRETTY";
  doc.announcement = "RELEASED";
  const problems = assess(doc);
  assert.ok(problems.includes("proof_class:workload_discovery"));
  assert.ok(problems.includes("announcement"));
  uninstallSession(result.sentinelPath);
});
