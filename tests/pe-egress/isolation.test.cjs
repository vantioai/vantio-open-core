"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { describe, it } = require("node:test");
const { RESULT_LIST, evaluate } = require("../../packages/pe-egress-authority");

const root = path.resolve(__dirname, "../..");

function read(rel) {
  return fs.readFileSync(path.join(root, rel), "utf8");
}

describe("isolation", () => {
  it("stays out of the workspace, the npm allowlist, and the live CLI", () => {
    const workspace = read("pnpm-workspace.yaml");
    assert.equal(workspace.includes("pe-egress"), false);
    const publish = read(".github/workflows/npm-publish.yml");
    assert.equal(publish.includes("pe-egress"), false);
    const cli = read("packages/vantio-cli/package.json");
    assert.equal(cli.includes("\"version\": \"0.3.24\""), true);
    assert.equal(cli.includes("pe-egress"), false);
    const python = read("packages/vantio-agent-sdk-py/pyproject.toml");
    assert.equal(python.includes("version = \"3.1.0\""), true);
    const interceptor = read("packages/vantio-cli/bin/interceptor.cjs");
    assert.equal(interceptor.includes("pe-egress-authority"), false);
  });

  it("does not call the network or load the interceptor", () => {
    const srcDir = path.join(root, "packages/pe-egress-authority/src");
    const files = fs.readdirSync(srcDir).filter((name) => name.endsWith(".cjs"));
    const blob = files.map((name) => fs.readFileSync(path.join(srcDir, name), "utf8")).join("\n");
    assert.equal(/require\([^)]*interceptor/.test(blob), false);
    assert.equal(blob.includes("require(\"node:net\")"), false);
    assert.equal(blob.includes("require(\"node:http\")"), false);
    assert.equal(/fetch\s*\(/.test(blob), false);
    assert.equal(blob.includes("require(\"node:child_process\")"), false);
  });

  it("keeps every result inside the closed vocabulary", () => {
    assert.deepEqual(RESULT_LIST, [
      "ALLOWED",
      "DENIED",
      "REDACTED",
      "CONTAINED",
      "REVOKED",
      "UNSUPPORTED",
      "ENFORCEMENT_GAP",
      "EVIDENCE_UNAVAILABLE",
      "UNKNOWN",
    ]);
    const decision = evaluate({
      policy: { enforce: true, dry_run: false, scope: "llm_and_named" },
      path: { id: "app_fetch" },
      attempt: {
        policy_loaded: true,
        destination: { hostname: "api.openai.com", port: "443", protocol: "https", in_product_scope: true },
      },
    });
    assert.equal(decision.result, "ALLOWED");
    assert.equal(Object.hasOwn(decision, "success"), false);
  });

  it("matches the manifest vocabulary and keeps the council verdict empty", () => {
    const manifest = JSON.parse(read("docs/internal/pe-egress/EGRESS-MANIFEST.json"));
    assert.deepEqual(manifest.results, RESULT_LIST);
    assert.equal(manifest.producer_classification, "PE_EGRESS_PROGRAM_READY_FOR_COUNCIL");
    assert.equal(manifest.council_status, "PENDING_INDEPENDENT_COUNCIL");
    assert.equal(manifest.council_verdict, null);
    assert.equal(manifest.merge_authorized, false);
    assert.equal(manifest.this_force_executed_host, false);
    assert.equal(manifest.cli_version_untouched, "0.3.24");
    assert.equal(manifest.python_version_untouched, "3.1.0");
  });
});
