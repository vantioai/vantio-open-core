"use strict";

const { PATH_KEY_LEN } = require("./catalog.cjs");

function pathBuffer(path) {
  if (typeof path !== "string") {
    throw new TypeError("path must be a string");
  }
  const end = path.indexOf("\0");
  const sliced = end === -1 ? path : path.slice(0, end);
  return Buffer.from(sliced, "utf8");
}

function matchesExact(list, buf) {
  if (buf.length === 0 || buf.length > PATH_KEY_LEN) return false;
  const text = buf.toString("utf8");
  return list.includes(text);
}

function matchesDir(list, buf) {
  if (buf.length === 0) return false;
  const head = buf.subarray(0, Math.min(buf.length, PATH_KEY_LEN));
  for (const prefix of list) {
    const pref = Buffer.from(prefix, "utf8");
    if (pref.length === 0 || pref.length > head.length || pref.length > PATH_KEY_LEN) continue;
    if (head.subarray(0, pref.length).equals(pref)) return true;
  }
  return false;
}

function matchesEnforce(host, buf) {
  return matchesExact(host.enforce_exact, buf) || matchesDir(host.enforce_dirs, buf);
}

function matchesBlocked(host, buf) {
  return matchesExact(host.blocked_exact, buf) || matchesDir(host.blocked_dirs, buf);
}

function assertPathList(list, kind) {
  if (!Array.isArray(list)) throw new TypeError(`${kind} must be an array`);
  for (const entry of list) {
    const buf = Buffer.from(entry, "utf8");
    if (buf.length === 0 || buf.length > PATH_KEY_LEN) {
      throw new Error(`${kind} entry exceeds the 64-byte map key: ${entry}`);
    }
    if (kind === "dir" && !entry.endsWith("/")) {
      throw new Error(`directory prefix must end with /: ${entry}`);
    }
  }
}

module.exports = {
  pathBuffer,
  matchesExact,
  matchesDir,
  matchesEnforce,
  matchesBlocked,
  assertPathList,
};
