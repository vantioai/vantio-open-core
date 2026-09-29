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

test("the proof package is outside the workspace and the frozen packages", () => {
  const workspace = fs.readFileSync(path.join(root, "pnpm-workspace.yaml"), "utf8");
  assert.equal(workspace.includes("pe-host-authority"), false);
  const cli = JSON.parse(fs.readFileSync(path.join(root, "packages/vantio-cli/package.json"), "utf8"));
  assert.equal(cli.version, "0.3.24");
  const python = fs.readFileSync(path.join(root, "packages/vantio-agent-sdk-py/pyproject.toml"), "utf8");
  assert.match(python, /^version = "3.1.0"$/m);
  const nodeSdk = JSON.parse(fs.readFileSync(path.join(root, "packages/vantio-agent-sdk/package.json"), "utf8"));
  assert.equal(nodeSdk.version, "0.2.4");
});

test("proof sources do not import the live CLI, SDK, or a loader", () => {
  const dir = path.join(root, "packages/pe-host-authority/src");
  for (const name of fs.readdirSync(dir)) {
    const text = fs.readFileSync(path.join(dir, name), "utf8");
    assert.equal(text.includes("vantio-cli"), false, name);
    assert.equal(text.includes("vantio-agent-sdk"), false, name);
    assert.equal(text.includes("interceptor.cjs"), false, name);
    assert.equal(text.includes("include_bytes"), false, name);
    assert.equal(/cargo\s|bpftool|sudo /.test(text), false, name);
  }
});

test("the proof tree does not carry a council pass token", () => {
  const files = [
    ...fs.readdirSync(path.join(root, "packages/pe-host-authority/src")).map((name) => path.join(root, "packages/pe-host-authority/src", name)),
  ];
  const docs = path.join(root, "docs/internal/pe-host-authority");
  if (fs.existsSync(docs)) {
    for (const name of fs.readdirSync(docs)) files.push(path.join(docs, name));
  }
  for (const file of files) {
    const text = fs.readFileSync(file, "utf8");
    assert.equal(text.includes("COUNCIL_PASS"), false, file);
    assert.equal(text.includes("PE_HOST_AUTHORITY_COUNCIL_PASSED"), false, file);
  }
});
}
