"use strict";

// Node.js 24 at or above 24.15.0, and Node.js 26, may load node:sqlite.
// Node.js 22 can already resolve the builtin. This gate refuses it anyway.
// The require stays inside the function so merely loading this module does not load the builtin.

const FLOOR_24 = Object.freeze({ major: 24, minor: 15, patch: 0 });

function parseNodeVersion(versionText) {
  const match = /^v?(\d+)\.(\d+)\.(\d+)/.exec(String(versionText || ""));
  if (!match) return null;
  return {
    major: Number(match[1]),
    minor: Number(match[2]),
    patch: Number(match[3]),
  };
}

function selectedBindingSupported(versionText) {
  const version = parseNodeVersion(versionText);
  if (!version) return false;
  if (version.major === 26) return true;
  if (version.major !== 24) return false;
  if (version.minor > FLOOR_24.minor) return true;
  if (version.minor < FLOOR_24.minor) return false;
  return version.patch >= FLOOR_24.patch;
}

function loadNodeSqliteSession() {
  if (!selectedBindingSupported(process.versions.node)) return null;
  try {
    // Not a circular import. The session module loads the selected builtin.
    // That load must not run on Node.js 22, 25, or any build below the selected floor.
    return require("./node-sqlite-session.cjs");
  } catch {
    return null;
  }
}

module.exports = {
  loadNodeSqliteSession,
  parseNodeVersion,
  selectedBindingSupported,
};
