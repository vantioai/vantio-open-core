"use strict";

const crypto = require("crypto");
const { readFileSync, statSync } = require("fs");
const path = require("path");

const { adaptFixture, adaptNodeCopy } = require("../../optics-node-adapter/src/index.cjs");
const boundary = require("./boundary.cjs");

function hasOwn(object, key) {
  return Object.prototype.hasOwnProperty.call(object, key);
}

function writerRequested(options) {
  if (!options || typeof options !== "object") return false;
  if (typeof options.path === "string") return true;
  const keys = Object.keys(options);
  for (let i = 0; i < keys.length; i += 1) {
    const key = keys[i];
    if (options[key] !== true) continue;
    if (boundary.WRITER_FLAGS.includes(key)) return true;
  }
  return false;
}

function baseExplanation() {
  return {
    achievement: "NOT_SHIPPED",
    audience: boundary.AUDIENCE,
    compatibility: {
      legacy_marker: false,
      legacy_schema_version: null,
      live_writer_modified: false,
      source_shape: "unavailable",
    },
    display: [],
    events: [],
    evidence_origin: null,
    explanation_text: "",
    input_bytes_identical: null,
    input_mutated: false,
    inside_cli_0_3_24: false,
    live_emission: false,
    live_writer_modified: false,
    notes: [],
    optics_displayed_as_success: false,
    optics_health: "UNAVAILABLE",
    optics_input_classes: [],
    optimistic_default_forbidden: false,
    posture: boundary.POSTURE,
    reader_disposition: "READ_AND_EXPLAIN",
    reader_name: boundary.READER_NAME,
    reader_origin_label: null,
    reader_version: boundary.READER_VERSION,
    reason_code: null,
    record: null,
    record_emitted: false,
    schema_status: boundary.SCHEMA_STATUS,
    schema_version: boundary.SCHEMA_VERSION,
    source_byte_length: null,
    source_name: null,
    source_sha256: null,
    stable_schema: false,
    units_d_e: boundary.UNITS_D_E,
    write_back: false,
    writes_live_run_directory: false,
    writer_activated: false,
  };
}

function classifyOptics(present, value) {
  if (!present || value === undefined) return "absent";
  if (value === null) return "null";
  if (value === "SUCCESS") return "refused_success";
  if (typeof value === "string" && boundary.OPTICS_ENUM.has(value)) return "enum";
  return "unknown";
}

function ownValue(object, key) {
  if (!object || typeof object !== "object") return { present: false, unreadable: false, value: undefined };
  const descriptor = Object.getOwnPropertyDescriptor(object, key);
  if (!descriptor) return { present: false, unreadable: false, value: undefined };
  if (!hasOwn(descriptor, "value")) return { present: false, unreadable: true, value: undefined };
  return { present: true, unreadable: false, value: descriptor.value };
}

function classesOfObject(object) {
  if (!object || typeof object !== "object" || Array.isArray(object)) return [];
  const classes = [];
  const canonical = ownValue(object, "optics_status");
  const legacy = ownValue(object, "opticsStatus");
  if (canonical.unreadable || legacy.unreadable) {
    classes.push("unreadable");
    return classes;
  }
  const chosen = canonical.present ? canonical : legacy;
  classes.push(classifyOptics(chosen.present, chosen.value));
  const calls = ownValue(object, "calls");
  if (!calls.present || !Array.isArray(calls.value)) return classes;
  for (let i = 0; i < calls.value.length; i += 1) {
    const call = calls.value[i];
    if (!call || typeof call !== "object") {
      classes.push("unknown");
      continue;
    }
    const callCanonical = ownValue(call, "optics_status");
    const callLegacy = ownValue(call, "opticsStatus");
    if (callCanonical.unreadable || callLegacy.unreadable) {
      classes.push("unreadable");
      continue;
    }
    const picked = callCanonical.present ? callCanonical : callLegacy;
    classes.push(classifyOptics(picked.present, picked.value));
  }
  return classes;
}

function classesFromInput(input) {
  if (Buffer.isBuffer(input)) {
    let text;
    try {
      text = new TextDecoder("utf-8", { fatal: true }).decode(input);
    } catch {
      return [];
    }
    return classesFromInput(text);
  }
  if (typeof input === "string") {
    const trimmed = input.trimStart();
    if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) return [];
    try {
      return classesOfObject(JSON.parse(input));
    } catch {
      return [];
    }
  }
  return classesOfObject(input);
}

function classesFromFixture(fixture) {
  const record = fixture && fixture.input_record;
  if (!record || typeof record !== "object") return [];
  const classes = [];
  if (record.envelope && typeof record.envelope === "object") {
    classes.push(...classesOfObject(record.envelope));
  }
  if (record.call && typeof record.call === "object") {
    classes.push(...classesOfObject(record.call));
  }
  return classes;
}

function noteAllowed(text) {
  if (text === "legacy or explicit optics SUCCESS is refused on the detached copy") return "optics token refused";
  if (typeof text === "string" && boundary.ALLOWED_NOTES.has(text)) return text;
  return null;
}

function cloneJson(value) {
  return JSON.parse(JSON.stringify(value));
}

function scrubOptics(record, flagged) {
  if (!record || record.optics_status !== "SUCCESS") return;
  record.optics_status = "UNAVAILABLE";
  flagged.forbidden = true;
}

function byteToken(record) {
  if (!record || !hasOwn(record, "response_bytes")) return "absent";
  if (record.response_bytes === null) return "null";
  if (record.response_bytes === 0) return "0";
  return String(record.response_bytes);
}

function pushLine(lines, subject, dimension, token, gloss) {
  lines.push({
    dimension,
    gloss: gloss || null,
    subject,
    token,
  });
}

function appendRecordLines(lines, subject, record) {
  if (!record || typeof record !== "object") return;
  const optics = hasOwn(record, "optics_status") ? record.optics_status : "absent";
  pushLine(
    lines,
    subject,
    "optics_status",
    optics,
    optics === "absent" ? "Absent" : boundary.OPTICS_GLOSS[optics] || null,
  );
  if (record.record_type === "observation_event" || hasOwn(record, "application_status")) {
    const application = hasOwn(record, "application_status") ? record.application_status : "absent";
    pushLine(
      lines,
      subject,
      "application_status",
      application,
      boundary.APPLICATION_GLOSS[application] || (application === "absent" ? "Absent" : null),
    );
  }
  if (record.record_type === "observation_event" || hasOwn(record, "http_status") || hasOwn(record, "response_bytes")) {
    let http = "absent";
    if (hasOwn(record, "http_status")) http = record.http_status === null ? "null" : record.http_status;
    pushLine(lines, subject, "http_status", http, null);
    pushLine(lines, subject, "response_bytes", byteToken(record), null);
  }
  if (hasOwn(record, "issue_location")) {
    pushLine(lines, subject, "issue_location", record.issue_location, null);
  }
  if (hasOwn(record, "lifecycle")) {
    pushLine(lines, subject, "lifecycle", record.lifecycle, boundary.OPTICS_GLOSS[record.lifecycle] || null);
  }
  if (hasOwn(record, "evidence_origin")) {
    pushLine(
      lines,
      subject,
      "evidence_origin",
      record.evidence_origin,
      boundary.ORIGIN_GLOSS[record.evidence_origin] || null,
    );
  }
}

function recordSubject(record, fallback) {
  if (record && record.record_type === "run_envelope") return "envelope";
  if (record && record.record_type === "observation_event") return "record";
  return fallback;
}

function buildDisplay(explanation) {
  const lines = [];
  pushLine(
    lines,
    "reading",
    "optics_health",
    explanation.optics_health,
    boundary.OPTICS_GLOSS[explanation.optics_health] || null,
  );
  if (explanation.reader_origin_label) {
    pushLine(
      lines,
      "reading",
      "evidence_origin",
      explanation.reader_origin_label,
      boundary.ORIGIN_GLOSS[explanation.reader_origin_label] || null,
    );
  } else {
    pushLine(lines, "reading", "evidence_origin", "absent", "Absent");
  }
  appendRecordLines(lines, recordSubject(explanation.record, "record"), explanation.record);
  for (let i = 0; i < explanation.events.length; i += 1) {
    const event = explanation.events[i];
    const subject = "event[" + String(i) + "]";
    appendRecordLines(lines, subject, event.record);
    if (event.reader_origin_label && event.reader_origin_label !== explanation.reader_origin_label) {
      pushLine(
        lines,
        subject,
        "evidence_origin",
        event.reader_origin_label,
        boundary.ORIGIN_GLOSS[event.reader_origin_label] || null,
      );
    }
  }
  return lines;
}

function renderLine(line) {
  const gloss = line.gloss ? " (" + line.gloss + ")" : "";
  return line.subject + "." + line.dimension + "=" + String(line.token) + gloss;
}

function finishText(explanation) {
  explanation.display = buildDisplay(explanation);
  explanation.explanation_text = explanation.display.map(renderLine).join("\n");
  explanation.optics_displayed_as_success = explanation.display.some((line) => {
    return (line.dimension === "optics_status" || line.dimension === "optics_health") && line.token === "SUCCESS";
  });
  return explanation;
}

function fromReading(reading, extra) {
  const explanation = baseExplanation();
  const flagged = { forbidden: false };
  explanation.reason_code = reading && reading.reason_code ? reading.reason_code : null;
  explanation.reader_origin_label = reading && reading.reader_origin_label ? reading.reader_origin_label : null;
  explanation.evidence_origin = explanation.reader_origin_label;
  explanation.record_emitted = Boolean(reading && reading.record_emitted);
  explanation.optimistic_default_forbidden = Boolean(reading && reading.optimistic_default_forbidden);
  explanation.live_writer_modified = Boolean(reading && reading.live_writer_modified);
  const compatibility = reading && reading.compatibility ? reading.compatibility : {};
  explanation.compatibility = {
    legacy_marker: Boolean(compatibility.legacy_marker),
    legacy_schema_version: hasOwn(compatibility, "legacy_schema_version") ? compatibility.legacy_schema_version : null,
    live_writer_modified: Boolean(compatibility.live_writer_modified),
    source_shape: compatibility.source_shape || "unknown",
  };
  const notes = [];
  const rawNotes = reading && reading.diagnostics ? reading.diagnostics.notes : null;
  if (Array.isArray(rawNotes)) {
    for (let i = 0; i < rawNotes.length; i += 1) {
      const allowed = noteAllowed(rawNotes[i]);
      if (allowed && !notes.includes(allowed)) notes.push(allowed);
    }
  }
  explanation.notes = notes;
  if (reading && reading.record) explanation.record = cloneJson(reading.record);
  const events = reading && Array.isArray(reading.events) ? reading.events : [];
  explanation.events = events.map((event) => ({
    reader_origin_label: event && event.reader_origin_label ? event.reader_origin_label : null,
    reason_code: event && event.reason_code ? event.reason_code : null,
    record: event && event.record ? cloneJson(event.record) : null,
    record_emitted: Boolean(event && event.record_emitted),
  }));
  scrubOptics(explanation.record, flagged);
  for (let i = 0; i < explanation.events.length; i += 1) scrubOptics(explanation.events[i].record, flagged);
  let health = reading && reading.optics_health ? reading.optics_health : "UNAVAILABLE";
  if (health === "SUCCESS") {
    health = "UNAVAILABLE";
    flagged.forbidden = true;
  }
  explanation.optics_health = health;
  if (flagged.forbidden) explanation.optimistic_default_forbidden = true;
  if (extra) {
    if (hasOwn(extra, "input_bytes_identical")) explanation.input_bytes_identical = extra.input_bytes_identical;
    if (hasOwn(extra, "source_byte_length")) explanation.source_byte_length = extra.source_byte_length;
    if (hasOwn(extra, "source_name")) explanation.source_name = extra.source_name;
    if (hasOwn(extra, "source_sha256")) explanation.source_sha256 = extra.source_sha256;
  }
  return finishText(explanation);
}

function refusal(reason, health) {
  const explanation = baseExplanation();
  explanation.reason_code = reason;
  explanation.optics_health = health;
  return finishText(explanation);
}

function safeBase(filePath) {
  const base = path.basename(filePath);
  return boundary.SAFE_NAME.test(base) ? base : null;
}

function explainCopy(input, options) {
  if (writerRequested(options)) return refusal("WRITER_INACTIVE", "OPTICS_ERROR");
  const explanation = fromReading(adaptNodeCopy(input));
  explanation.optics_input_classes = classesFromInput(input);
  return explanation;
}

function explainFixture(fixture, options) {
  if (writerRequested(options)) return refusal("WRITER_INACTIVE", "OPTICS_ERROR");
  const explanation = fromReading(adaptFixture(fixture));
  explanation.optics_input_classes = classesFromFixture(fixture);
  return explanation;
}

function readRunFile(filePath, options) {
  if (writerRequested(options)) return refusal("WRITER_INACTIVE", "OPTICS_ERROR");
  if (typeof filePath !== "string" || filePath.length === 0) return refusal("PATH_REFUSED", "OPTICS_ERROR");
  let stat;
  try {
    stat = statSync(filePath);
  } catch (err) {
    if (err && err.code === "ENOENT") return refusal("ABSENT_FILE", "UNAVAILABLE");
    return refusal("UNREADABLE", "OPTICS_ERROR");
  }
  if (!stat.isFile()) return refusal("UNREADABLE", "OPTICS_ERROR");
  let before;
  try {
    before = readFileSync(filePath);
  } catch {
    return refusal("UNREADABLE", "OPTICS_ERROR");
  }
  const explanation = fromReading(adaptNodeCopy(before), {
    input_bytes_identical: true,
    source_byte_length: before.length,
    source_name: safeBase(filePath),
    source_sha256: crypto.createHash("sha256").update(before).digest("hex"),
  });
  explanation.optics_input_classes = classesFromInput(before);
  let after = null;
  try {
    after = readFileSync(filePath);
  } catch {
    after = null;
  }
  const identical = Buffer.isBuffer(after) && before.equals(after);
  explanation.input_bytes_identical = identical;
  if (!identical) {
    explanation.optics_health = "OPTICS_ERROR";
    explanation.reason_code = "INPUT_CHANGED";
    explanation.record = null;
    explanation.events = [];
    explanation.record_emitted = false;
    return finishText(explanation);
  }
  return explanation;
}

module.exports = {
  explainCopy,
  explainFixture,
  readRunFile,
};
