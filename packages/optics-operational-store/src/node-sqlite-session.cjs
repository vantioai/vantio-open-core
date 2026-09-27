"use strict";

// Loaded only after runtime-gate.cjs accepts the process version.
// require("node:sqlite") is the selected binding. No other SQLite package is loaded.

const { DatabaseSync } = require("node:sqlite");

function firstCell(row) {
  if (!row || typeof row !== "object") return undefined;
  const key = Object.keys(row)[0];
  if (key === undefined) return undefined;
  return row[key];
}

function isZero(value) {
  if (value === 0 || value === "0") return true;
  if (typeof value === "bigint") return value === 0n;
  return false;
}

function openDatabase(filePath, readOnly) {
  if (typeof DatabaseSync !== "function") {
    throw Object.assign(new Error("node:sqlite DatabaseSync is absent"), {
      code: "NODE_BINDING_CANNOT_LOAD",
    });
  }
  if (typeof filePath !== "string" || filePath.length === 0 || filePath.startsWith("file:")) {
    throw Object.assign(new Error("store path must be a filesystem path"), {
      code: "NODE_BINDING_CANNOT_LOAD",
    });
  }
  const options = readOnly
    ? {
        readOnly: true,
        timeout: 0,
        enableForeignKeyConstraints: false,
        allowExtension: false,
      }
    : {
        timeout: 0,
        enableForeignKeyConstraints: false,
        allowExtension: false,
      };
  const db = new DatabaseSync(filePath, options);
  try {
    const busy = firstCell(db.prepare("PRAGMA busy_timeout").get());
    const foreignKeys = firstCell(db.prepare("PRAGMA foreign_keys").get());
    if (!isZero(busy) || !isZero(foreignKeys)) {
      throw Object.assign(new Error("selected binding did not apply timeout or foreign keys"), {
        code: "NODE_BINDING_CANNOT_LOAD",
      });
    }
  } catch (err) {
    try {
      db.close();
    } catch {
      // The caller fail-opens. The constructor's file, if any, is removed by that caller
      // only when this call created it.
    }
    throw err;
  }
  return db;
}

module.exports = {
  openDatabase,
};
