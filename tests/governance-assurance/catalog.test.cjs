"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { test: privateTreeSkipTest } = require("node:test");

if (!fs.existsSync(path.resolve(__dirname, "../../docs/internal"))) {
  privateTreeSkipTest("docs/internal", { skip: "PRIVATE_TREE_REMOVED_FROM_PUBLIC_TIP" }, () => {});
} else {
"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const root = path.resolve(__dirname, "../..");
const api = require("../../packages/governance-assurance/src/index.cjs");

test("catalog has forty unique controls from inventory through decommissioning", () => {
  const controls = api.loadCatalog();
  assert.equal(controls.length, 40);
  assert.equal(api.catalogProblems(controls).length, 0);
  const ids = controls.map((control) => control.control_id);
  assert.equal(new Set(ids).size, 40);
  assert.equal(controls[0].title.includes("inventory"), true);
  assert.equal(controls[controls.length - 1].title, "Decommissioning");
  for (const control of controls) {
    assert.equal(control.review_date, "2026-09-28");
    assert.equal(api.SUPPORT_CLASSES.includes(control.primary_support), true);
    assert.equal(control.customer_responsibilities.length > 0, true);
    assert.equal(control.Vantio_responsibilities.length > 0, true);
    assert.equal(/%/.test(control.claim_ceiling), false);
  }
});

test("schema rejects a missing field, a duplicate id, and a promoted verification state", () => {
  const [sample] = api.CONTROLS;
  const missing = { ...sample };
  delete missing.claim_ceiling;
  assert.equal(api.controlProblems(missing).includes("missing claim_ceiling"), true);
  const promoted = { ...sample, verification_state: "PROVED_EXTERNAL" };
  assert.equal(api.controlProblems(promoted).some((item) => item.includes("promotion")), true);
  const duplicate = [sample, { ...sample }];
  assert.equal(api.catalogProblems(duplicate).some((item) => item.includes("duplicate")), true);
  assert.equal(api.catalogProblems(Array.from({ length: 257 }, () => ({}))).some((item) => item.includes("max")), true);
});

test("package stays private and off the shipping workspace", () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(root, "packages/governance-assurance/package.json"), "utf8"));
  assert.equal(manifest.private, true);
  assert.equal(manifest.version, "0.2.0-internal");
  assert.equal(manifest.vantio.pnpm_workspace_member, false);
  assert.equal(manifest.vantio.npm_publish, false);
  const workspace = fs.readFileSync(path.join(root, "pnpm-workspace.yaml"), "utf8");
  assert.equal(workspace.includes("governance-assurance"), false);
  const promote = fs.readFileSync(path.join(root, "scripts/release/promote_npm.mjs"), "utf8");
  assert.equal(promote.includes("governance-assurance"), false);
  const cli = JSON.parse(fs.readFileSync(path.join(root, "packages/vantio-cli/package.json"), "utf8"));
  assert.equal(cli.version, "0.3.24");
  const python = fs.readFileSync(path.join(root, "packages/vantio-agent-sdk-py/pyproject.toml"), "utf8");
  assert.match(python, /version = "3.1.0"/);
  const npmSdk = JSON.parse(fs.readFileSync(path.join(root, "packages/vantio-agent-sdk/package.json"), "utf8"));
  assert.equal(npmSdk.version, "0.2.4");
  const boundary = fs.readFileSync(path.join(root, "docs/internal/governance-assurance/00-BOUNDARY.md"), "utf8");
  assert.match(boundary, /Vantio does \*\*not\*\* independently make an AI system lawful/);
  assert.match(boundary, /PENDING_INDEPENDENT_COUNCIL/);
  assert.match(boundary, /WS17_GOVERNANCE_ASSURANCE_0_2_0_INTERNAL_REBIND_READY_FOR_COUNCIL/);
});
}
