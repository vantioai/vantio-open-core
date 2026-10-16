"use strict";

const { MAX_LINE_BYTES, MAX_RECORDS, REASON_CODES, assertListed } = require("./boundary.cjs");
const { isPlainObject } = require("./normalize.cjs");

function failure(reasonCode, detail) {
  assertListed(reasonCode, REASON_CODES, "reason_code");
  return { ok: false, reason_code: reasonCode, detail };
}

function loadNdjson(text) {
  if (typeof text !== "string") {
    return failure("SCHEMA", "ndjson");
  }
  const lines = text.split("\n");
  const records = [];
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (line.trim() === "") {
      continue;
    }
    if (Buffer.byteLength(line, "utf8") > MAX_LINE_BYTES) {
      return failure("LIMIT_EXCEEDED", `line ${index + 1}`);
    }
    if (records.length >= MAX_RECORDS) {
      return failure("LIMIT_EXCEEDED", "ndjson");
    }
    let value;
    try {
      value = JSON.parse(line, (key, nested) => {
        if (key === "__proto__" || key === "prototype" || key === "constructor") {
          throw new Error("forbidden-key");
        }
        return nested;
      });
    } catch (error) {
      if (error instanceof Error && error.message === "forbidden-key") {
        return failure("SCHEMA", `line ${index + 1}`);
      }
      return failure("CORRUPT_LINE", `line ${index + 1}`);
    }
    if (!isPlainObject(value)) {
      return failure("CORRUPT_LINE", `line ${index + 1}`);
    }
    records.push(value);
  }
  return { ok: true, records };
}

module.exports = {
  loadNdjson,
};
