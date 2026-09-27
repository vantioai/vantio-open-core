"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const store = require("../../packages/optics-operational-store/src/index.cjs");

const ROOT = path.resolve(__dirname, "../..");
const CANARY = "sk-CANARYPROMPT0001";

function walk(dir, out) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === "node_modules" || entry.name === ".git") continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else out.push(full);
  }
  return out;
}

test("node sources in this package do not select a binding or create a home store", () => {
  const files = walk(path.join(ROOT, "packages/optics-operational-store"), []);
  const nodeFiles = files.filter((full) => /\.(?:cjs|js|mjs)$/.test(full));
  const bannedPackages = /require\(\s*["'](?:sqlite3|better-sqlite3|better-sqlite)["']/;
  const selectedBinding = /require\(\s*["']node:sqlite["']\)|from\s+["']node:sqlite["']/;
  for (const full of nodeFiles) {
    const text = fs.readFileSync(full, "utf8");
    assert.equal(bannedPackages.test(text), false, full);
    if (selectedBinding.test(text)) {
      assert.equal(path.basename(full), "node-sqlite-session.cjs", full);
    }
  }
  const previous = process.env.VANTIO_HOME;
  delete process.env.VANTIO_HOME;
  const home = path.join(os.homedir(), ".vantio", "optics", "store.sqlite");
  const before = fs.existsSync(home);
  try {
    const opened = store.openStore({
      create: true,
      sql: "ATTACH DATABASE '/tmp/escaped.sqlite' AS evil",
      applicationResult: { token: CANARY },
    });
    assert.equal(opened.reason_code, "SQL_REJECTED");
    assert.equal(opened.file_created, false);
    assert.equal(opened.application_continues, true);
    assert.equal(opened.application_result.token, CANARY);
    assert.equal(fs.existsSync(home), before);
    assert.equal(fs.existsSync("/tmp/escaped.sqlite"), false);
  } finally {
    if (previous === undefined) delete process.env.VANTIO_HOME;
    else process.env.VANTIO_HOME = previous;
  }
});

test("a symlink evidence path is not followed by the node facade", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "o7-node-link-"));
  const outside = path.join(dir, "outside");
  const link = path.join(dir, "link");
  fs.mkdirSync(outside);
  fs.symlinkSync(outside, link);
  try {
    const opened = store.openStore({ evidenceRoot: link, create: true, migrate: true });
    assert.equal(opened.file_created, false);
    assert.equal(opened.writes_enabled, false);
    assert.equal(fs.existsSync(path.join(outside, "optics", "store.sqlite")), false);
    const putResult = store.put(opened, { prompt: CANARY, sql: "DROP TABLE records" });
    assert.equal(putResult.stored, false);
    assert.equal(fs.readdirSync(outside).length, 0);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
