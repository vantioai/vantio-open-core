"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const { execFileSync } = require("node:child_process");

const eg = require("../../internal/enterprise-governance/src/index.cjs");

const ROOT = path.resolve(__dirname, "../..");

function read(rel) {
  return fs.readFileSync(path.join(ROOT, rel), "utf8");
}

test("producer classification is ready for a separate council", () => {
  assert.equal(eg.PRODUCER_CLASSIFICATION, "ENTERPRISE_E1_E3_INTERNAL_READY_FOR_COUNCIL");
  assert.equal(eg.COUNCIL_STATUS, "PENDING_INDEPENDENT_COUNCIL");
  assert.equal(eg.COUNCIL_VERDICT, null);
  assert.equal(eg.SCHEMA_STATUS, "unstable-pre-1.0");
  assert.equal(eg.SCHEMA_VERSION, 0);
  assert.equal(eg.DECISIONS["EG-D5"].resolved, false);
  assert.equal(eg.DECISIONS["EG-D6"].resolved, false);
  assert.equal(eg.DECISIONS["EG-D7"].safe_default, "NOT_SET");
  assert.equal(Object.keys(eg.REQUIREMENTS).length, 33);
  assert.equal(eg.REQUIREMENTS["EG-E2-8"], "RECORD_LAYER_ONLY_HOST_UNSATISFIED");
  assert.equal(eg.REQUIREMENTS["EG-E3-8"], "HOST_UNSATISFIED");
  assert.equal(eg.REQUIREMENTS["EG-SUB-6"], "HOST_UNSATISFIED");
  assert.equal(eg.REQUIREMENTS["EG-SP-1"], "NOT_RUN_HOST_UNSATISFIED");
  assert.equal(eg.PLAN_SITUATION, "ENTERPRISE_GOVERNANCE_E1_E3_PLAN_MERGED_NO_IMPLEMENTATION");
  const status = JSON.parse(read("docs/internal/enterprise-e1-e3/STATUS.json"));
  assert.equal(status.producer_classification, eg.PRODUCER_CLASSIFICATION);
  assert.equal(status.council_verdict, null);
  assert.deepEqual(status.requirements, eg.REQUIREMENTS);
});

test("this tree does not touch packages, extensions, workflows, governance, or the plan packet", () => {
  const status = execFileSync("git", [
    "status",
    "--porcelain",
    "--",
    "packages",
    "extensions",
    ".github",
    "docs/governance",
    "docs/planning/enterprise-governance",
  ], { cwd: ROOT, encoding: "utf8" });
  assert.equal(status.trim(), "");
  const workspace = read("pnpm-workspace.yaml");
  assert.equal(workspace.includes("internal/enterprise-governance"), false);
  const cli = JSON.parse(read("packages/vantio-cli/package.json"));
  assert.equal(cli.version, "0.3.24");
  assert.equal(read("packages/vantio-agent-sdk-py/pyproject.toml").includes('version = "3.1.0"'), true);
  assert.equal(read("packages/vantio-agent-sdk-py/vantio/__init__.py").includes('__version__ = "3.1.0"'), true);
});

test("planning packet bytes still match the merged manifest", () => {
  const manifest = JSON.parse(read("docs/planning/enterprise-governance/GOVERNANCE-MANIFEST.json"));
  assert.equal(manifest.producer_classification, "ENTERPRISE_GOVERNANCE_E1_E3_PLAN_READY_FOR_COUNCIL");
  assert.equal(manifest.council_status, "PENDING_INDEPENDENT_COUNCIL");
  for (const [name, expected] of Object.entries(manifest.files_sha256)) {
    const body = fs.readFileSync(path.join(ROOT, "docs/planning/enterprise-governance", name));
    const actual = crypto.createHash("sha256").update(body).digest("hex");
    assert.equal(actual, expected, name);
  }
});

test("evaluator source does not reach a network, a host, or a second enforcement engine", () => {
  const sources = [
    "internal/enterprise-governance/src/boundary.cjs",
    "internal/enterprise-governance/src/envelope.cjs",
    "internal/enterprise-governance/src/scan.cjs",
    "internal/enterprise-governance/src/engine.cjs",
    "internal/enterprise-governance/src/index.cjs",
  ];
  const banned = [
    'require("fs")',
    "require('fs')",
    'require("net")',
    'require("http")',
    'require("https")',
    'require("child_process")',
    'require("tls")',
    "TC_ACT_SHOT",
    "SSL_write",
    "@google-cloud/spanner",
    "identity-provider",
  ];
  for (const rel of sources) {
    const text = read(rel);
    for (const token of banned) assert.equal(text.includes(token), false, `${rel} ${token}`);
  }
  assert.equal(read("internal/enterprise-governance/src/engine.cjs").includes("grant.state = \"ACTIVE\""), false);
  assert.equal(read("internal/enterprise-governance/src/engine.cjs").includes("grant.state = \"EXPIRED\""), false);
});
