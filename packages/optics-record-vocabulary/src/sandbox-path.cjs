"use strict";

const fs = require("fs");
const path = require("path");

function sandboxError() {
  const error = new Error("PATH_OUTSIDE_SANDBOX");
  error.code = "PATH_OUTSIDE_SANDBOX";
  return error;
}

function resolveInside(rootDirectory, targetPath) {
  if (typeof targetPath !== "string" || targetPath.length === 0) throw sandboxError();
  let rootReal;
  try {
    rootReal = fs.realpathSync(rootDirectory);
  } catch (_error) {
    throw sandboxError();
  }
  const resolved = path.resolve(targetPath);
  const parent = path.dirname(resolved);
  if (!fs.existsSync(parent)) throw sandboxError();
  let parentReal;
  try {
    parentReal = fs.realpathSync(parent);
  } catch (_error) {
    throw sandboxError();
  }
  const relative = path.relative(rootReal, parentReal);
  if (relative.startsWith("..") || path.isAbsolute(relative)) throw sandboxError();
  const base = path.basename(resolved);
  if (base.length === 0 || base === "." || base === "..") throw sandboxError();
  return path.join(parentReal, base);
}

module.exports = { resolveInside };
