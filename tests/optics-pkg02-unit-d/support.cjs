"use strict";

const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "../..");
const CLI = path.join(ROOT, "packages/vantio-cli/bin/vantio.js");
const FUTURE = path.join(ROOT, "packages/vantio-cli-pkg02/bin/vantio-future.cjs");
const ADAPTER = path.join(ROOT, "packages/optics-node-adapter/src/index.cjs");

function hasOwn(object, key) {
  return Object.prototype.hasOwnProperty.call(object, key);
}

function run(bin, args, home, extraEnv) {
  return spawnSync(process.execPath, [bin, ...args], {
    cwd: home,
    encoding: "utf8",
    env: Object.assign({}, process.env, {
      HOME: home,
      VANTIO_EXTRA_LLM_HOSTS: "127.0.0.1",
      VANTIO_HOME: path.join(home, ".vantio"),
    }, extraEnv || {}),
  });
}

function runFrozen(home, args, extraEnv) {
  return run(CLI, args, home, extraEnv);
}

function runFuture(home, script, extraEnv) {
  const file = path.join(home, "workload.cjs");
  fs.writeFileSync(file, script);
  return run(FUTURE, ["run", "node", file], home, extraEnv);
}

function runFiles(home) {
  const dir = path.join(home, ".vantio", "runs");
  return fs.readdirSync(dir).filter((name) => name.endsWith(".json")).sort().map((name) => path.join(dir, name));
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function opticsTokens(value, found) {
  if (!value || typeof value !== "object") return found;
  if (hasOwn(value, "optics_status")) found.push(value.optics_status);
  if (hasOwn(value, "opticsStatus")) found.push(value.opticsStatus);
  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i += 1) opticsTokens(value[i], found);
    return found;
  }
  const keys = Object.keys(value);
  for (let i = 0; i < keys.length; i += 1) {
    if (keys[i] === "optics_status" || keys[i] === "opticsStatus") continue;
    opticsTokens(value[keys[i]], found);
  }
  return found;
}

function assertNoOpticsSuccess(assert, document) {
  const tokens = opticsTokens(document, []);
  assert.equal(tokens.includes("SUCCESS"), false, JSON.stringify(tokens));
}

function prohibitedKeys(value, found) {
  if (!value || typeof value !== "object") return found;
  const keys = Object.keys(value);
  for (let i = 0; i < keys.length; i += 1) {
    found.push(keys[i]);
    prohibitedKeys(value[keys[i]], found);
  }
  return found;
}

const BANNED = [
  "plane",
  "data_note",
  "residual",
  "free_mode",
  "est_spend_usd",
  "prompt",
  "prompts",
  "completion",
  "completions",
  "machine",
  "anonymousId",
  "hostname",
];

function homeDir(prefix) {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

module.exports = {
  ADAPTER,
  BANNED,
  CLI,
  FUTURE,
  ROOT,
  assertNoOpticsSuccess,
  hasOwn,
  homeDir,
  opticsTokens,
  prohibitedKeys,
  readJson,
  runFiles,
  runFrozen,
  runFuture,
};
