"use strict";

const { existsSync, lstatSync, realpathSync, readFileSync, writeFileSync, mkdirSync } = require("node:fs");
const { homedir, tmpdir } = require("node:os");
const path = require("node:path");

const SENTINEL_SCHEMA = "vantio.investor-demo.sentinel/v1";

function sameOrInside(candidate, parent) {
  const rel = path.relative(parent, candidate);
  return rel === "" || (!rel.startsWith("..") && !path.isAbsolute(rel));
}

function resolveExisting(target) {
  return realpathSync(target);
}

function assertDirectoryNotSymlink(target) {
  const stat = lstatSync(target);
  if (stat.isSymbolicLink()) {
    const error = new Error("REFUSED_SYMLINK");
    error.code = "REFUSED_SYMLINK";
    throw error;
  }
  if (!stat.isDirectory()) {
    const error = new Error("REFUSED_NOT_DIRECTORY");
    error.code = "REFUSED_NOT_DIRECTORY";
    throw error;
  }
}

function assertPlannedLayout(layout) {
  const sessionRoot = path.resolve(layout.sessionRoot);
  const demoHome = path.resolve(layout.demoHome);
  const operatorHome = path.resolve(layout.operatorHome);
  const repoRoot = path.resolve(layout.repoRoot);
  const tempRoot = path.resolve(tmpdir());
  const userHome = path.resolve(homedir());
  if (path.basename(demoHome) !== "demo-home" || path.dirname(demoHome) !== sessionRoot) {
    const error = new Error("REFUSED_DEMO_HOME_SHAPE");
    error.code = "REFUSED_DEMO_HOME_SHAPE";
    throw error;
  }
  if (demoHome === operatorHome || demoHome === userHome || sessionRoot === operatorHome || sessionRoot === userHome) {
    const error = new Error("REFUSED_OPERATOR_HOME");
    error.code = "REFUSED_OPERATOR_HOME";
    throw error;
  }
  if (sameOrInside(sessionRoot, repoRoot) || sameOrInside(demoHome, repoRoot)) {
    const error = new Error("REFUSED_SOURCE_CHECKOUT");
    error.code = "REFUSED_SOURCE_CHECKOUT";
    throw error;
  }
  if (!sameOrInside(sessionRoot, tempRoot) || sessionRoot === tempRoot) {
    const error = new Error("REFUSED_OUTSIDE_TEMP");
    error.code = "REFUSED_OUTSIDE_TEMP";
    throw error;
  }
}

function assertSafeSessionLayout(layout) {
  const sessionRoot = resolveExisting(layout.sessionRoot);
  const demoHome = resolveExisting(layout.demoHome);
  const operatorHome = resolveExisting(layout.operatorHome);
  const repoRoot = resolveExisting(layout.repoRoot);
  const tempRoot = resolveExisting(tmpdir());
  const userHome = resolveExisting(homedir());

  assertDirectoryNotSymlink(layout.sessionRoot);
  assertDirectoryNotSymlink(layout.demoHome);

  if (path.basename(demoHome) !== "demo-home" || path.dirname(demoHome) !== sessionRoot) {
    const error = new Error("REFUSED_DEMO_HOME_SHAPE");
    error.code = "REFUSED_DEMO_HOME_SHAPE";
    throw error;
  }
  if (demoHome === operatorHome || demoHome === userHome || sessionRoot === operatorHome || sessionRoot === userHome) {
    const error = new Error("REFUSED_OPERATOR_HOME");
    error.code = "REFUSED_OPERATOR_HOME";
    throw error;
  }
  if (sameOrInside(sessionRoot, repoRoot) || sameOrInside(demoHome, repoRoot)) {
    const error = new Error("REFUSED_SOURCE_CHECKOUT");
    error.code = "REFUSED_SOURCE_CHECKOUT";
    throw error;
  }
  if (!sameOrInside(sessionRoot, tempRoot) || sessionRoot === tempRoot) {
    const error = new Error("REFUSED_OUTSIDE_TEMP");
    error.code = "REFUSED_OUTSIDE_TEMP";
    throw error;
  }
  return { sessionRoot, demoHome, operatorHome, repoRoot };
}

function writeJson(file, value) {
  writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, { mode: 0o600 });
}

function readJson(file) {
  return JSON.parse(readFileSync(file, "utf8"));
}

function createSentinel(layout, extra) {
  const resolved = assertSafeSessionLayout(layout);
  mkdirSync(layout.sessionRoot, { recursive: true, mode: 0o700 });
  const sentinel = {
    schema: SENTINEL_SCHEMA,
    audience: "INTERNAL_RESTRICTED",
    session_id: extra.sessionId,
    session_token: extra.sessionToken,
    session_root: resolved.sessionRoot,
    demo_home: resolved.demoHome,
    operator_home: resolved.operatorHome,
    repo_root: resolved.repoRoot,
    created_at: extra.createdAt,
    revoked: false,
    removed: false,
    mode: null,
    html_proofs: [],
    announcement: "HOLD",
  };
  const sentinelPath = path.join(resolved.sessionRoot, "sentinel.json");
  writeJson(path.join(resolved.sessionRoot, "token"), { session_token: extra.sessionToken });
  writeJson(sentinelPath, sentinel);
  return { sentinel, sentinelPath, resolved };
}

function readSentinel(sentinelPath) {
  const sentinel = readJson(sentinelPath);
  if (sentinel.schema !== SENTINEL_SCHEMA) {
    const error = new Error("REFUSED_SENTINEL_SCHEMA");
    error.code = "REFUSED_SENTINEL_SCHEMA";
    throw error;
  }
  const tokenFile = readJson(path.join(sentinel.session_root, "token"));
  if (!sentinel.session_token || tokenFile.session_token !== sentinel.session_token) {
    const error = new Error("REFUSED_SENTINEL_TOKEN");
    error.code = "REFUSED_SENTINEL_TOKEN";
    throw error;
  }
  const sentinelReal = resolveExisting(path.dirname(sentinelPath));
  if (sentinelReal !== resolveExisting(sentinel.session_root)) {
    const error = new Error("REFUSED_SENTINEL_PATH");
    error.code = "REFUSED_SENTINEL_PATH";
    throw error;
  }
  if (sentinel.removed === true) {
    assertRemovedRecord(sentinel);
    return sentinel;
  }
  assertSafeSessionLayout({
    sessionRoot: sentinel.session_root,
    demoHome: sentinel.demo_home,
    operatorHome: sentinel.operator_home,
    repoRoot: sentinel.repo_root,
  });
  return sentinel;
}

function assertRemovedRecord(sentinel) {
  const sessionRoot = resolveExisting(sentinel.session_root);
  const operatorHome = resolveExisting(sentinel.operator_home);
  const repoRoot = resolveExisting(sentinel.repo_root);
  const userHome = resolveExisting(homedir());
  const demoHome = path.resolve(sentinel.demo_home);
  const tempRoot = resolveExisting(tmpdir());
  if (path.basename(demoHome) !== "demo-home" || path.dirname(demoHome) !== sessionRoot) {
    const error = new Error("REFUSED_DEMO_HOME_SHAPE");
    error.code = "REFUSED_DEMO_HOME_SHAPE";
    throw error;
  }
  if (demoHome === operatorHome || demoHome === userHome || sessionRoot === operatorHome || sessionRoot === userHome) {
    const error = new Error("REFUSED_OPERATOR_HOME");
    error.code = "REFUSED_OPERATOR_HOME";
    throw error;
  }
  if (sameOrInside(sessionRoot, repoRoot)) {
    const error = new Error("REFUSED_SOURCE_CHECKOUT");
    error.code = "REFUSED_SOURCE_CHECKOUT";
    throw error;
  }
  if (!sameOrInside(sessionRoot, tempRoot) || sessionRoot === tempRoot) {
    const error = new Error("REFUSED_OUTSIDE_TEMP");
    error.code = "REFUSED_OUTSIDE_TEMP";
    throw error;
  }
  if (existsSync(demoHome)) {
    const error = new Error("REMOVED_BUT_PRESENT");
    error.code = "REMOVED_BUT_PRESENT";
    throw error;
  }
}

module.exports = {
  SENTINEL_SCHEMA,
  assertPlannedLayout,
  assertSafeSessionLayout,
  createSentinel,
  readJson,
  readSentinel,
  sameOrInside,
  writeJson,
};
