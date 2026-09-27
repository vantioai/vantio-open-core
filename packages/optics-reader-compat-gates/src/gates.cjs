"use strict";

const { readFileSync, readdirSync, lstatSync } = require("fs");
const path = require("path");

const { readRunFile } = require("../../optics-record-reader/src/explain.cjs");
const boundary = require("./boundary.cjs");

function hasOwn(object, key) {
  return Object.prototype.hasOwnProperty.call(object, key);
}

function blockedReport(reason) {
  return {
    achievement: boundary.ACHIEVEMENT,
    activates_unit_d: false,
    activates_unit_e: false,
    audience: boundary.AUDIENCE,
    blocked_reason: reason,
    bytes_rewritten: false,
    council_verdict: null,
    directory_unchanged: false,
    frozen_cli_modified: false,
    gates: boundary.GATE_IDS.map((id) => ({
      achievement: boundary.ACHIEVEMENT,
      disposition: "BLOCKED",
      evidence: ["evaluator refused the request"],
      failures: ["evaluator refused the request"],
      id,
      matrix_class: "UNSUPPORTED",
      passed: false,
    })),
    live_emission: false,
    merges_pull_request: false,
    posture: boundary.POSTURE,
    producer_classification: boundary.CLASSIFICATION_BLOCKED,
    producer_ready_for_council: false,
    schema_status: boundary.SCHEMA_STATUS,
    schema_version: boundary.SCHEMA_VERSION,
    stable_schema: false,
    units_d_e: boundary.UNITS_D_E,
    write_back: false,
    writer_activated: false,
  };
}

function classifyStoredOptics(value) {
  if (value === undefined) return "absent";
  if (value === null) return "null";
  if (value === "SUCCESS") return "refused_success";
  if (typeof value === "string" && boundary.OPTICS_TOKENS.has(value)) return value;
  return "unknown";
}

function collectStoredOptics(value, found) {
  if (!value || typeof value !== "object") return;
  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i += 1) collectStoredOptics(value[i], found);
    return;
  }
  if (hasOwn(value, "optics_status")) found.push(classifyStoredOptics(value.optics_status));
  else if (hasOwn(value, "opticsStatus")) found.push(classifyStoredOptics(value.opticsStatus));
  if (Array.isArray(value.calls)) collectStoredOptics(value.calls, found);
  if (value.summary && typeof value.summary === "object") collectStoredOptics(value.summary, found);
}

function allowReason(value) {
  return typeof value === "string" && boundary.REASON_CODES.has(value) ? value : null;
}

function allowOrigin(value) {
  return typeof value === "string" && boundary.ORIGINS.has(value) ? value : null;
}

function allowClass(value) {
  return typeof value === "string" && boundary.INPUT_CLASSES.has(value) ? value : null;
}

function allowApplication(value) {
  return typeof value === "string" && boundary.APPLICATION_TOKENS.has(value) ? value : null;
}

function byteToken(record) {
  if (!record || !hasOwn(record, "response_bytes")) return "absent";
  if (record.response_bytes === null) return "null";
  if (record.response_bytes === 0) return "zero";
  return "present";
}

function httpToken(record) {
  if (!record || !hasOwn(record, "http_status")) return "absent";
  if (record.http_status === null) return "null";
  if (typeof record.http_status === "number" && Number.isFinite(record.http_status)) return record.http_status;
  return "unlisted";
}

function opticsOnRecord(record) {
  if (!record || typeof record !== "object") return null;
  if (!hasOwn(record, "optics_status")) return "absent";
  return classifyStoredOptics(record.optics_status);
}

function explanationHasOpticsSuccess(explanation) {
  if (!explanation || typeof explanation !== "object") return true;
  if (explanation.optics_displayed_as_success === true) return true;
  if (explanation.optics_health === "SUCCESS") return true;
  if (opticsOnRecord(explanation.record) === "SUCCESS") return true;
  const events = Array.isArray(explanation.events) ? explanation.events : [];
  for (let i = 0; i < events.length; i += 1) {
    if (opticsOnRecord(events[i] && events[i].record) === "SUCCESS") return true;
  }
  const text = typeof explanation.explanation_text === "string" ? explanation.explanation_text : "";
  if (text.includes("optics_status=SUCCESS") || text.includes("optics_health=SUCCESS")) return true;
  return false;
}

function echoedProhibited(explanation) {
  const text = JSON.stringify(explanation);
  for (let i = 0; i < boundary.PROHIBITED_ECHOES.length; i += 1) {
    if (text.includes(boundary.PROHIBITED_ECHOES[i])) return true;
  }
  return false;
}

function mentionsLocal(explanation) {
  return JSON.stringify(explanation).includes("LOCAL_OBSERVATION");
}

function parseSource(buffer) {
  try {
    const text = new TextDecoder("utf-8", { fatal: true }).decode(buffer);
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function sourceMarkers(parsed) {
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    return {
      cliVersionFrozen: false,
      origin: null,
      originalOrigin: null,
      runLog: false,
      runtime: null,
      schemaStatus: null,
      schemaVersion: null,
    };
  }
  const runtime = parsed.runtime === "python" || parsed.runtime === "node" ? parsed.runtime : null;
  const schemaStatus = typeof parsed.schema_status === "string" && boundary.SAFE_SCHEMA_STATUS.test(parsed.schema_status)
    ? parsed.schema_status
    : null;
  return {
    cliVersionFrozen: parsed.cli_version === boundary.FROZEN_CLI_VERSION,
    origin: allowOrigin(parsed.evidence_origin),
    originalOrigin: allowOrigin(parsed.original_evidence_origin),
    runLog: parsed.vantio_run_log === "1",
    runtime,
    schemaStatus,
    schemaVersion: Number.isInteger(parsed.schema_version) ? parsed.schema_version : null,
  };
}

function eventOrigins(explanation) {
  const origins = [];
  const events = explanation && Array.isArray(explanation.events) ? explanation.events : [];
  for (let i = 0; i < events.length; i += 1) {
    const event = events[i];
    const label = allowOrigin(event && event.reader_origin_label);
    const recordOrigin = allowOrigin(event && event.record && event.record.evidence_origin);
    if (label) origins.push(label);
    if (recordOrigin && recordOrigin !== label) origins.push(recordOrigin);
  }
  return origins;
}

function rootOptics(parsed) {
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return "unreadable";
  if (hasOwn(parsed, "optics_status")) return classifyStoredOptics(parsed.optics_status);
  if (hasOwn(parsed, "opticsStatus")) return classifyStoredOptics(parsed.opticsStatus);
  return "absent";
}

function summarizeExplanation(explanation) {
  const record = explanation && explanation.record;
  const classes = [];
  const rawClasses = explanation && Array.isArray(explanation.optics_input_classes) ? explanation.optics_input_classes : [];
  for (let i = 0; i < rawClasses.length; i += 1) {
    const allowed = allowClass(rawClasses[i]);
    if (allowed) classes.push(allowed);
  }
  const application = record && hasOwn(record, "application_status")
    ? (allowApplication(record.application_status) || "unlisted")
    : "absent";
  const health = explanation && boundary.OPTICS_TOKENS.has(explanation.optics_health) ? explanation.optics_health : "UNLISTED";
  return {
    applicationStatus: application,
    eventOrigins: eventOrigins(explanation),
    httpStatus: httpToken(record),
    inputClasses: classes,
    legacySchemaVersion: explanation && explanation.compatibility && Number.isInteger(explanation.compatibility.legacy_schema_version)
      ? explanation.compatibility.legacy_schema_version
      : null,
    mentionsLocalObservation: mentionsLocal(explanation),
    opticsHealth: health,
    opticsSuccess: explanationHasOpticsSuccess(explanation),
    optimisticDefaultForbidden: Boolean(explanation && explanation.optimistic_default_forbidden),
    originLabel: allowOrigin(explanation && explanation.reader_origin_label),
    originalOrigin: allowOrigin(record && record.original_evidence_origin),
    prohibitedEcho: echoedProhibited(explanation),
    reasonCode: allowReason(explanation && explanation.reason_code),
    recordEmitted: Boolean(explanation && explanation.record_emitted),
    recordOptics: opticsOnRecord(record),
    recordOrigin: allowOrigin(record && record.evidence_origin),
    responseBytes: byteToken(record),
    schemaVersion: record && Number.isInteger(record.schema_version) ? record.schema_version : null,
    unitsDE: explanation && explanation.units_d_e === boundary.UNITS_D_E ? boundary.UNITS_D_E : "UNLISTED",
    writerActivated: Boolean(explanation && explanation.writer_activated),
    writeBack: explanation ? explanation.write_back !== false : true,
  };
}

function resolveInside(root, name) {
  if (typeof name !== "string" || !boundary.SAFE_NAME.test(name)) return null;
  const full = path.resolve(root, name);
  if (full !== path.join(root, name)) return null;
  const prefix = root.endsWith(path.sep) ? root : root + path.sep;
  if (!full.startsWith(prefix)) return null;
  return full;
}

function directoryNames(root) {
  return readdirSync(root).slice().sort();
}

function sameNames(left, right) {
  if (left.length !== right.length) return false;
  for (let i = 0; i < left.length; i += 1) {
    if (left[i] !== right[i]) return false;
  }
  return true;
}

function roleSetProblem(entries) {
  if (!Array.isArray(entries) || entries.length !== boundary.REQUIRED_ROLES.length) return "ROLE_SET_REFUSED";
  const seen = new Set();
  for (let i = 0; i < entries.length; i += 1) {
    const entry = entries[i];
    if (!entry || typeof entry.role !== "string" || typeof entry.name !== "string") return "ROLE_SET_REFUSED";
    if (!boundary.REQUIRED_ROLES.includes(entry.role)) return "ROLE_SET_REFUSED";
    if (seen.has(entry.role)) return "ROLE_SET_REFUSED";
    seen.add(entry.role);
  }
  return null;
}

function readClean(root, entry) {
  const full = resolveInside(root, entry.name);
  if (!full) return { problem: "NAME_REFUSED" };
  let listed;
  try {
    listed = lstatSync(full);
  } catch {
    return { problem: "READ_FAILED" };
  }
  if (listed.isSymbolicLink()) return { problem: "SYMLINK_REFUSED" };
  if (!listed.isFile()) return { problem: "READ_FAILED" };
  let before;
  try {
    before = readFileSync(full);
  } catch {
    return { problem: "READ_FAILED" };
  }
  const explained = readRunFile(full);
  let after;
  try {
    after = readFileSync(full);
  } catch {
    return { problem: "READ_FAILED" };
  }
  const parsed = parseSource(before);
  const stored = [];
  collectStoredOptics(parsed, stored);
  const rawToken = parsed && typeof parsed === "object" && !Array.isArray(parsed) && typeof parsed.optics_status === "string"
    ? parsed.optics_status
    : null;
  return {
    buffer: before,
    bytesIdentical: before.equals(after),
    echoedRawOptics: Boolean(rawToken) && JSON.stringify(explained).includes(rawToken),
    markers: sourceMarkers(parsed),
    name: entry.name,
    parsed,
    reader: summarizeExplanation(explained),
    role: entry.role,
    rootOptics: rootOptics(parsed),
    storedOptics: stored,
  };
}

function rereadUnchanged(root, name, before) {
  const full = resolveInside(root, name);
  if (!full) return false;
  try {
    return readFileSync(full).equals(before);
  } catch {
    return false;
  }
}

function publicEntry(entry) {
  return {
    byteLength: entry.buffer.length,
    bytesIdentical: entry.bytesIdentical,
    cliVersionFrozen: entry.markers.cliVersionFrozen,
    name: entry.name,
    reader: {
      applicationStatus: entry.reader.applicationStatus,
      eventOrigins: entry.reader.eventOrigins,
      httpStatus: entry.reader.httpStatus,
      inputClasses: entry.reader.inputClasses,
      legacySchemaVersion: entry.reader.legacySchemaVersion,
      mentionsLocalObservation: entry.reader.mentionsLocalObservation,
      opticsHealth: entry.reader.opticsHealth,
      opticsSuccess: entry.reader.opticsSuccess,
      optimisticDefaultForbidden: entry.reader.optimisticDefaultForbidden,
      originLabel: entry.reader.originLabel,
      originalOrigin: entry.reader.originalOrigin,
      prohibitedEcho: entry.reader.prohibitedEcho,
      reasonCode: entry.reader.reasonCode,
      recordEmitted: entry.reader.recordEmitted,
      recordOptics: entry.reader.recordOptics,
      recordOrigin: entry.reader.recordOrigin,
      responseBytes: entry.reader.responseBytes,
      schemaVersion: entry.reader.schemaVersion,
      unitsDE: entry.reader.unitsDE,
      writeBack: entry.reader.writeBack,
      writerActivated: entry.reader.writerActivated,
    },
    role: entry.role,
    rootOptics: entry.rootOptics,
    runLog: entry.markers.runLog,
    runtime: entry.markers.runtime,
    schemaStatus: entry.markers.schemaStatus,
    schemaVersion: entry.markers.schemaVersion,
    sourceOrigin: entry.markers.origin,
    sourceOriginalOrigin: entry.markers.originalOrigin,
    storedOptics: entry.storedOptics,
  };
}

function byRole(entries) {
  const map = new Map();
  for (let i = 0; i < entries.length; i += 1) map.set(entries[i].role, entries[i]);
  return map;
}

function opticsClean(entry) {
  return entry.bytesIdentical && entry.reader.opticsSuccess === false && entry.reader.writerActivated === false && entry.reader.writeBack === false && entry.reader.unitsDE === boundary.UNITS_D_E;
}

function gate(id, matrix, disposition, failures, evidence) {
  return {
    achievement: boundary.ACHIEVEMENT,
    disposition,
    evidence: evidence.slice(),
    failures: failures.slice(),
    id,
    matrix_class: matrix,
    passed: failures.length === 0,
  };
}

function pushMissing(failures, label) {
  failures.push(label + " entry missing");
}

function evaluateMixed(map) {
  const failures = [];
  const cli = map.get("legacy_cli");
  const python = map.get("legacy_python");
  const future = map.get("future_canonical");
  if (!cli || !python || !future) {
    pushMissing(failures, "mixed");
    return gate("mixed_version_directories", "PARTIAL", "PARTIAL", failures, ["mixed directory incomplete"]);
  }
  if (!opticsClean(cli) || !opticsClean(python) || !opticsClean(future)) failures.push("mixed read changed bytes or optics success");
  if (cli.buffer.equals(python.buffer) || cli.buffer.equals(future.buffer) || python.buffer.equals(future.buffer)) {
    failures.push("mixed files collapsed to one byte string");
  }
  if (cli.markers.schemaVersion !== 2 || cli.markers.cliVersionFrozen !== true || cli.markers.runLog !== true) {
    failures.push("legacy cli file lost its frozen marker");
  }
  if (future.markers.schemaVersion !== 0 || future.markers.schemaStatus !== boundary.SCHEMA_STATUS) {
    failures.push("future file lost its canonical marker");
  }
  if (cli.reader.originLabel !== "LEGACY_UNMARKED" || python.reader.originLabel !== "LEGACY_UNMARKED") {
    failures.push("legacy origin moved during a mixed read");
  }
  if (future.markers.origin !== "LOCAL_OBSERVATION") failures.push("future source origin moved");
  const evidence = failures.length === 0
    ? ["legacy and future files stayed side by side with their own bytes"]
    : ["mixed directory did not stay partial"];
  return gate("mixed_version_directories", "PARTIAL", "PARTIAL", failures, evidence);
}

function evaluateLegacy(map) {
  const failures = [];
  const cli = map.get("legacy_cli");
  const python = map.get("legacy_python");
  if (!cli || !python) {
    pushMissing(failures, "legacy");
    return gate("legacy_records", "REQUIRES_ADAPTER", "LEGACY_UNMARKED", failures, ["legacy entries missing"]);
  }
  if (!opticsClean(cli) || cli.reader.originLabel !== "LEGACY_UNMARKED") failures.push("cli legacy read failed");
  if (cli.markers.schemaVersion !== 2 || cli.markers.runLog !== true || cli.markers.cliVersionFrozen !== true) {
    failures.push("cli legacy source marker missing");
  }
  if (cli.reader.legacySchemaVersion !== 2) failures.push("cli legacy schema was not kept on the compatibility field");
  if (cli.reader.mentionsLocalObservation) failures.push("cli legacy read accepted local observation");
  if (!opticsClean(python) || python.reader.originLabel !== "LEGACY_UNMARKED") failures.push("python legacy read failed");
  if (python.markers.runtime !== "python" || python.markers.runLog !== true || python.markers.schemaVersion !== 2) {
    failures.push("python legacy source marker missing");
  }
  if (!python.storedOptics.includes("refused_success")) failures.push("python legacy source lost stored optics SUCCESS");
  if (python.reader.optimisticDefaultForbidden !== true) failures.push("python stored optics SUCCESS was not refused");
  if (python.reader.opticsHealth === "SUCCESS" || python.reader.recordOptics === "SUCCESS") failures.push("python legacy displayed optics SUCCESS");
  if (python.reader.mentionsLocalObservation) failures.push("python legacy read accepted local observation");
  const evidence = failures.length === 0
    ? ["legacy CLI 0.3.24 and Python 3.1.0 records stayed unmarked"]
    : ["legacy records were not read as legacy"];
  return gate("legacy_records", "REQUIRES_ADAPTER", "LEGACY_UNMARKED", failures, evidence);
}

function evaluateFuture(map, frozen) {
  const failures = [];
  const future = map.get("future_canonical");
  if (!future) {
    pushMissing(failures, "future");
    return gate("future_records", "REQUIRES_ADAPTER", "UNSUPPORTED", failures, ["future entry missing"]);
  }
  if (!opticsClean(future)) failures.push("future read changed bytes or showed optics SUCCESS");
  if (future.markers.schemaVersion !== 0 || future.markers.schemaStatus !== boundary.SCHEMA_STATUS) {
    failures.push("future source schema marker missing");
  }
  if (!future.storedOptics.includes("OBSERVED")) failures.push("future source lost explicit OBSERVED");
  if (future.reader.opticsHealth !== "OBSERVED" || future.reader.recordOptics !== "OBSERVED") {
    failures.push("inert reader dropped explicit OBSERVED");
  }
  if (future.reader.originLabel !== "LOCAL_OBSERVATION" || future.reader.recordOrigin !== "LOCAL_OBSERVATION") {
    failures.push("future provenance was not preserved");
  }
  if (future.reader.applicationStatus !== "SUCCESS") failures.push("workload SUCCESS left the application dimension");
  if (!frozen.honestUnsupported) failures.push("frozen CLI pairing was not classified unsupported");
  const evidence = failures.length === 0
    ? ["future record explained as OBSERVED while the frozen CLI pairing stays unsupported"]
    : ["future record was not explained safely"];
  return gate("future_records", "REQUIRES_ADAPTER", "UNSUPPORTED", failures, evidence);
}

function evaluateUnknown(map) {
  const failures = [];
  const unknown = map.get("unknown_status");
  if (!unknown) {
    pushMissing(failures, "unknown");
    return gate("unknown_statuses", "REJECT_WITH_EXPLANATION", "UNAVAILABLE", failures, ["unknown entry missing"]);
  }
  if (!opticsClean(unknown)) failures.push("unknown status read changed bytes or showed optics SUCCESS");
  if (!unknown.storedOptics.includes("unknown")) failures.push("unknown token was not classified unknown");
  if (!unknown.reader.inputClasses.includes("unknown")) failures.push("reader input class was not unknown");
  if (unknown.reader.opticsHealth !== "UNAVAILABLE" || unknown.reader.recordOptics !== "UNAVAILABLE") {
    failures.push("unknown status was not UNAVAILABLE");
  }
  if (unknown.reader.optimisticDefaultForbidden !== true) failures.push("unknown status missed the optimistic-default refusal");
  if (unknown.echoedRawOptics) failures.push("raw unknown token was echoed");
  if (unknown.reader.inputClasses.includes("absent") || unknown.reader.inputClasses.includes("null")) {
    failures.push("unknown status collapsed into absent or null");
  }
  const evidence = failures.length === 0
    ? ["unknown optics token stayed UNAVAILABLE"]
    : ["unknown status was not refused"];
  return gate("unknown_statuses", "REJECT_WITH_EXPLANATION", "UNAVAILABLE", failures, evidence);
}

function evaluateAbsent(map) {
  const failures = [];
  const absent = map.get("absent_fields");
  if (!absent) {
    pushMissing(failures, "absent");
    return gate("absent_fields", "PARTIAL", "UNAVAILABLE", failures, ["absent entry missing"]);
  }
  if (!opticsClean(absent)) failures.push("absent-field read changed bytes or showed optics SUCCESS");
  if (absent.rootOptics !== "absent") failures.push("source optics field was not absent");
  if (!absent.reader.inputClasses.includes("absent")) failures.push("reader class was not absent");
  if (absent.reader.inputClasses.includes("unknown")) failures.push("absent field was classed unknown");
  if (absent.reader.opticsHealth !== "UNAVAILABLE" || absent.reader.recordOptics !== "UNAVAILABLE") {
    failures.push("absent optics became a filled token");
  }
  if (absent.reader.opticsHealth === "OBSERVED") failures.push("absent optics became OBSERVED");
  if (absent.reader.httpStatus !== "absent") failures.push("absent http status was filled");
  if (absent.reader.responseBytes !== "absent") failures.push("absent bytes were filled");
  if (absent.reader.applicationStatus !== "absent") failures.push("absent application status was implied");
  const evidence = failures.length === 0
    ? ["absent fields stayed absent and optics stayed UNAVAILABLE"]
    : ["absent fields were filled"];
  return gate("absent_fields", "PARTIAL", "UNAVAILABLE", failures, evidence);
}

function evaluateOrigin(map) {
  const failures = [];
  const imported = map.get("imported");
  const claimed = map.get("claimed_local");
  const simulated = map.get("simulated_demo");
  const future = map.get("future_canonical");
  const cli = map.get("legacy_cli");
  if (!imported || !claimed || !simulated || !future || !cli) {
    pushMissing(failures, "origin");
    return gate("origin_preservation", "READ_ONLY", "READ_ONLY", failures, ["origin entries missing"]);
  }
  if (!opticsClean(imported) || imported.reader.originLabel !== "IMPORTED" || imported.reader.recordOrigin !== "IMPORTED") {
    failures.push("imported origin was not preserved");
  }
  if (imported.reader.originalOrigin !== "LEGACY_UNMARKED" && imported.markers.originalOrigin !== "LEGACY_UNMARKED") {
    failures.push("imported original origin moved");
  }
  if (imported.reader.mentionsLocalObservation) failures.push("imported record became local observation");
  if (claimed.markers.origin !== "LOCAL_OBSERVATION") failures.push("claimed source marker was rewritten");
  if (claimed.reader.originLabel !== "LEGACY_UNMARKED" || claimed.reader.mentionsLocalObservation) {
    failures.push("claimed local without provenance was accepted");
  }
  if (!claimed.bytesIdentical) failures.push("claimed file was rewritten");
  if (!simulated.reader.eventOrigins.includes("SIMULATED_DEMO")) failures.push("demo observation lost SIMULATED_DEMO");
  if (simulated.reader.originLabel !== "LEGACY_UNMARKED" || simulated.reader.mentionsLocalObservation) {
    failures.push("demo envelope was promoted");
  }
  if (future.reader.recordOrigin !== "LOCAL_OBSERVATION") failures.push("provenanced local origin was dropped");
  if (cli.reader.mentionsLocalObservation) failures.push("legacy cli origin was promoted");
  const evidence = failures.length === 0
    ? ["origins stayed on the labels the source and provenance support"]
    : ["origin preservation failed"];
  return gate("origin_preservation", "READ_ONLY", "READ_ONLY", failures, evidence);
}

function evaluateFallback(map, side) {
  const failures = [];
  const newer = map.get("newer_schema");
  const corrupt = map.get("corrupt");
  const unknown = map.get("unknown_status");
  if (!newer || !corrupt || !unknown) {
    pushMissing(failures, "fallback");
    return gate("reader_fallback", "UNSUPPORTED", "NON_WRITING_FALLBACK", failures, ["fallback entries missing"]);
  }
  if (!newer.bytesIdentical || newer.markers.schemaVersion !== 99 || newer.markers.schemaStatus !== "stable-v9") {
    failures.push("newer schema source marker was rewritten");
  }
  if (newer.reader.schemaVersion !== 0) failures.push("detached newer reading did not keep contract schema_version 0");
  if (newer.reader.opticsSuccess || newer.reader.writerActivated) failures.push("newer schema fallback showed success or a writer");
  if (newer.reader.unitsDE !== boundary.UNITS_D_E) failures.push("newer schema fallback authorized a writer");
  if (!corrupt.bytesIdentical || corrupt.reader.opticsHealth !== "OPTICS_ERROR") failures.push("corrupt fallback was not OPTICS_ERROR");
  if (corrupt.reader.recordEmitted || corrupt.reader.opticsHealth === "NOT_OBSERVED" || corrupt.reader.opticsSuccess) {
    failures.push("corrupt bytes became a success record");
  }
  if (!side.absent || side.absent.opticsHealth !== "UNAVAILABLE" || side.absent.reasonCode !== "ABSENT_FILE") {
    failures.push("absent path was not UNAVAILABLE");
  }
  if (side.absentCreated) failures.push("absent path was created");
  if (side.absent && (side.absent.opticsHealth === "NOT_OBSERVED" || side.absent.opticsSuccess)) {
    failures.push("absent path became NOT_OBSERVED or SUCCESS");
  }
  if (unknown.reader.opticsHealth === "SUCCESS" || unknown.echoedRawOptics) failures.push("unknown token fallback was success");
  const evidence = failures.length === 0
    ? ["unreadable, newer, unknown, and absent inputs fell back without a write"]
    : ["reader fallback wrote or succeeded"];
  return gate("reader_fallback", "UNSUPPORTED", "NON_WRITING_FALLBACK", failures, evidence);
}

function evaluateNoSuccess(map) {
  const failures = [];
  const roles = Array.from(map.keys());
  for (let i = 0; i < roles.length; i += 1) {
    const entry = map.get(roles[i]);
    if (!entry.reader || entry.reader.opticsSuccess) failures.push(entry.role + " showed optics SUCCESS");
  }
  const unknown = map.get("unknown_status");
  const future = map.get("future_canonical");
  if (unknown && (unknown.reader.opticsHealth === "SUCCESS" || unknown.reader.recordOptics === "SUCCESS")) {
    failures.push("unknown token became optics SUCCESS");
  }
  if (future && future.reader.applicationStatus === "SUCCESS" && future.reader.recordOptics === "SUCCESS") {
    failures.push("application SUCCESS was copied into optics_status");
  }
  if (future && future.reader.recordOptics !== "OBSERVED") failures.push("explicit OBSERVED was replaced");
  const evidence = failures.length === 0
    ? ["no unknown or legacy optics token displayed as SUCCESS"]
    : ["an optics token displayed as SUCCESS"];
  return gate("no_unknown_to_success", "REJECT_WITH_EXPLANATION", "UNAVAILABLE", failures, evidence);
}

function evaluateFrozen(map, frozen) {
  const failures = [];
  const sdk = map.get("node_sdk");
  if (!frozen.present) failures.push("frozen display oracle missing");
  if (frozen.present && frozen.opticsStatus !== "SUCCESS") {
    failures.push("frozen display did not return SUCCESS, so this force will not treat the CLI as updated");
  }
  if (!frozen.honestUnsupported) failures.push("frozen pairing was not marked unsupported");
  if (frozen.sourceOptics === "SUCCESS" || frozen.sourceOptics == null) failures.push("future source optics was not an explicit non-success token");
  if (!sdk) {
    pushMissing(failures, "node sdk");
  } else if (sdk.markers.runLog || sdk.reader.recordEmitted || sdk.reader.mentionsLocalObservation || sdk.reader.opticsSuccess) {
    failures.push("node sdk 0.2.4 ingest became a local record");
  } else if (!sdk.bytesIdentical || sdk.reader.opticsHealth === "SUCCESS") {
    failures.push("node sdk ingest was rewritten or shown as success");
  }
  const evidence = failures.length === 0
    ? ["frozen CLI display of a future call stays SUCCESS and is classified unsupported"]
    : ["frozen CLI was not classified honestly"];
  return gate("frozen_cli_honestly_unsupported", "UNSUPPORTED", "UNSUPPORTED", failures, evidence);
}

function evaluateRollback(map, side) {
  const failures = [];
  const future = map.get("future_canonical");
  const newer = map.get("newer_schema");
  if (!future || !newer) {
    pushMissing(failures, "rollback");
    return gate("rollback_without_record_rewriting", "UNSUPPORTED", "UNSUPPORTED", failures, ["rollback entries missing"]);
  }
  if (!future.bytesIdentical || !newer.bytesIdentical) failures.push("rollback rewrote a record");
  if (future.markers.origin !== "LOCAL_OBSERVATION") failures.push("rollback changed future origin");
  if (newer.markers.schemaVersion !== 99 || newer.markers.schemaStatus !== "stable-v9") {
    failures.push("rollback cleared the newer schema marker");
  }
  if (!side.writerRefusal || side.writerRefusal.reasonCode !== "WRITER_INACTIVE" || side.writerRefusal.writerActivated) {
    failures.push("writer rollback option was accepted");
  }
  if (!side.writerBytesIdentical) failures.push("writer option rewrote the future file");
  if (!side.frozenHonest) failures.push("rolled-back reader was not disclosed as unsupported");
  if (side.directoryMutated) failures.push("rollback created or removed a file");
  const evidence = failures.length === 0
    ? ["records stayed in place and the frozen reader stays unsupported"]
    : ["rollback rewrote a record"];
  return gate("rollback_without_record_rewriting", "UNSUPPORTED", "UNSUPPORTED", failures, evidence);
}

function evaluatePromotion(map, side) {
  const failures = [];
  const claimed = map.get("claimed_local");
  const imported = map.get("imported");
  const simulated = map.get("simulated_demo");
  const field = map.get("future_field");
  const cli = map.get("legacy_cli");
  if (!claimed || !imported || !simulated || !field || !cli) {
    pushMissing(failures, "promotion");
    return gate("reader_refuses_unsafe_promotion", "READ_ONLY", "READ_ONLY", failures, ["promotion entries missing"]);
  }
  if (claimed.reader.mentionsLocalObservation || claimed.reader.originLabel === "LOCAL_OBSERVATION") {
    failures.push("claimed local was promoted");
  }
  if (!side.promoteBytesIdentical || !side.promote || side.promote.originLabel === "LOCAL_OBSERVATION" || side.promote.mentionsLocalObservation) {
    failures.push("promote option upgraded origin or rewrote bytes");
  }
  if (imported.reader.recordOrigin !== "IMPORTED" || imported.reader.mentionsLocalObservation) {
    failures.push("imported evidence was promoted");
  }
  if (!simulated.reader.eventOrigins.includes("SIMULATED_DEMO") || simulated.reader.mentionsLocalObservation) {
    failures.push("demo evidence was promoted");
  }
  if (cli.reader.mentionsLocalObservation) failures.push("legacy file was promoted");
  if (!field.bytesIdentical || field.reader.prohibitedEcho || field.reader.mentionsLocalObservation) {
    failures.push("future or prohibited fields were promoted");
  }
  if (field.reader.opticsSuccess) failures.push("prohibited field read became optics SUCCESS");
  if (!side.writerRefusal || side.writerRefusal.reasonCode !== "WRITER_INACTIVE") {
    failures.push("write option was not refused");
  }
  const evidence = failures.length === 0
    ? ["reader kept legacy, imported, and demo labels and refused field promotion"]
    : ["reader promoted a record"];
  return gate("reader_refuses_unsafe_promotion", "READ_ONLY", "READ_ONLY", failures, evidence);
}

function finish(entries, side, frozen, directoryUnchanged) {
  const map = byRole(entries);
  const gates = [
    evaluateMixed(map),
    evaluateLegacy(map),
    evaluateFuture(map, frozen),
    evaluateUnknown(map),
    evaluateAbsent(map),
    evaluateOrigin(map),
    evaluateFallback(map, side),
    evaluateNoSuccess(map),
    evaluateFrozen(map, frozen),
    evaluateRollback(map, side),
    evaluatePromotion(map, side),
  ];
  let bytesRewritten = directoryUnchanged === false;
  for (let i = 0; i < entries.length; i += 1) {
    if (!entries[i].bytesIdentical) bytesRewritten = true;
  }
  if (bytesRewritten || side.absentCreated || side.directoryMutated) {
    for (let i = 0; i < gates.length; i += 1) {
      if (!gates[i].failures.includes("record bytes changed")) gates[i].failures.push("record bytes changed");
      gates[i].passed = false;
    }
  }
  const passed = gates.every((item) => item.passed);
  return {
    achievement: boundary.ACHIEVEMENT,
    activates_unit_d: false,
    activates_unit_e: false,
    audience: boundary.AUDIENCE,
    blocked_reason: passed ? null : "GATE_FAILED",
    bytes_rewritten: bytesRewritten,
    council_verdict: null,
    directory_unchanged: directoryUnchanged && !side.absentCreated,
    entries: entries.map(publicEntry),
    frozen_cli_modified: false,
    gates,
    live_emission: false,
    merges_pull_request: false,
    posture: boundary.POSTURE,
    producer_classification: passed ? boundary.CLASSIFICATION_READY : boundary.CLASSIFICATION_BLOCKED,
    producer_ready_for_council: passed,
    schema_status: boundary.SCHEMA_STATUS,
    schema_version: boundary.SCHEMA_VERSION,
    stable_schema: false,
    units_d_e: boundary.UNITS_D_E,
    write_back: false,
    writer_activated: false,
  };
}

function frozenOracle(display, futureEntry) {
  const present = Boolean(display) && typeof display === "object" && !Array.isArray(display);
  const opticsStatus = present && typeof display.opticsStatus === "string" ? display.opticsStatus : null;
  const sourceOptics = futureEntry && futureEntry.storedOptics.includes("OBSERVED") ? "OBSERVED" : null;
  const honestUnsupported = present && opticsStatus === "SUCCESS" && sourceOptics === "OBSERVED";
  return {
    honestUnsupported,
    opticsStatus,
    present,
    sourceOptics,
  };
}

function sideChannel(root, namesBefore, claimed, future, absentName) {
  const absentFull = resolveInside(root, absentName);
  let absentCreated = false;
  let absent = null;
  if (absentFull) {
    let exists = false;
    try {
      exists = lstatSync(absentFull).isFile() || lstatSync(absentFull).isSymbolicLink();
    } catch (err) {
      exists = !(err && err.code === "ENOENT");
    }
    if (exists) absentCreated = true;
    const explained = readRunFile(absentFull);
    absent = summarizeExplanation(explained);
    try {
      if (lstatSync(absentFull).isFile() || lstatSync(absentFull).isSymbolicLink()) absentCreated = true;
    } catch (err) {
      if (!(err && err.code === "ENOENT")) absentCreated = true;
    }
  }
  let promote = null;
  let promoteBytesIdentical = false;
  if (claimed) {
    const explained = readRunFile(resolveInside(root, claimed.name), { promote: true, upgradeOrigin: "LOCAL_OBSERVATION" });
    promote = summarizeExplanation(explained);
    promoteBytesIdentical = rereadUnchanged(root, claimed.name, claimed.buffer);
  }
  let writerRefusal = null;
  let writerBytesIdentical = false;
  if (future) {
    const explained = readRunFile(resolveInside(root, future.name), {
      activate: true,
      migrate: true,
      path: "refused",
      write: true,
    });
    writerRefusal = summarizeExplanation(explained);
    writerBytesIdentical = rereadUnchanged(root, future.name, future.buffer);
  }
  let directoryMutated = false;
  try {
    directoryMutated = !sameNames(namesBefore, directoryNames(root));
  } catch {
    directoryMutated = true;
  }
  return {
    absent,
    absentCreated,
    directoryMutated,
    frozenHonest: false,
    promote,
    promoteBytesIdentical,
    writerBytesIdentical,
    writerRefusal,
  };
}

function evaluateEntryGates(request) {
  if (!request || typeof request !== "object" || Array.isArray(request)) return blockedReport("REQUEST_REFUSED");
  if (typeof request.directory !== "string" || request.directory.length === 0) return blockedReport("DIRECTORY_REFUSED");
  if (typeof request.absentName !== "string") return blockedReport("NAME_REFUSED");
  const roleProblem = roleSetProblem(request.entries);
  if (roleProblem) return blockedReport(roleProblem);
  const root = path.resolve(request.directory);
  let rootStat;
  try {
    rootStat = lstatSync(root);
  } catch {
    return blockedReport("DIRECTORY_REFUSED");
  }
  if (rootStat.isSymbolicLink() || !rootStat.isDirectory()) return blockedReport("DIRECTORY_REFUSED");
  if (!resolveInside(root, request.absentName)) return blockedReport("NAME_REFUSED");
  let namesBefore;
  try {
    namesBefore = directoryNames(root);
  } catch {
    return blockedReport("DIRECTORY_REFUSED");
  }
  const internal = [];
  for (let i = 0; i < request.entries.length; i += 1) {
    const read = readClean(root, request.entries[i]);
    if (read.problem) return blockedReport(read.problem);
    internal.push(read);
  }
  const map = byRole(internal);
  const side = sideChannel(root, namesBefore, map.get("claimed_local"), map.get("future_canonical"), request.absentName);
  const frozen = frozenOracle(request.frozenDisplay, map.get("future_canonical"));
  side.frozenHonest = frozen.honestUnsupported;
  let directoryUnchanged = true;
  try {
    directoryUnchanged = sameNames(namesBefore, directoryNames(root));
  } catch {
    directoryUnchanged = false;
  }
  return finish(internal, side, frozen, directoryUnchanged);
}

module.exports = {
  evaluateEntryGates,
};
