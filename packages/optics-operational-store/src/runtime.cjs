"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const boundary = require("./boundary.cjs");
const { canonicalJson } = require("../../optics-evidence-contract/src/canonical.cjs");
const { validateEvidence } = require("../../optics-evidence-contract/src/validate.cjs");
const { loadNodeSqliteSession, selectedBindingSupported } = require("./runtime-gate.cjs");

const QUERY_LIMIT_DEFAULT = 100;
const QUERY_LIMIT_MAX = 500;
const STORE_NAME = "store.sqlite";
const UNREADABLE_STORE_ID = "store-id-unreadable";
const RECOVERY_FALLBACK_NAME = "optics-recovery";
const LIMITATION = "Operational store page. Not a portable proof.";
const TIMESTAMP_RE = /^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z$/;
const SAFE_ID_RE = /^[0-9a-f]{32}$/;
const ABSENT = new Set(["ENOENT", "ENOTDIR", "EBADF", "ELOOP"]);
const DENIED = new Set(["EACCES", "EPERM"]);
const MAX_INT = 9007199254740991;

const EXCLUDED_ORIGINS = Object.freeze([
  "LEGACY_UNMARKED",
  "SIMULATED_DEMO",
  "IMPORTED",
  "TEST_FIXTURE",
  "PRODUCT_HEALTH",
  "DERIVED_DIAGNOSTIC",
]);
const KNOWN_ORIGINS = new Set(["LOCAL_OBSERVATION", ...EXCLUDED_ORIGINS]);
const REQUEST_FIELDS = Object.freeze([
  "time_start",
  "time_end",
  "run_id",
  "session_id",
  "trace_id",
  "process_id",
  "provider_id",
  "destination_host",
  "application_status",
  "optics_status",
  "issue_location",
  "http_status",
  "duration_min_ms",
  "duration_max_ms",
  "lifecycle",
  "coverage",
  "origin",
  "freshness",
  "limit",
  "cursor",
  "sort",
]);
const REQUEST_FIELD_SET = new Set(REQUEST_FIELDS);
const SQL_FIELDS = new Set(["sql", "statement", "where", "query"]);
const REGEX_FIELDS = new Set(["regex", "regexp", "pattern"]);
const ENVELOPE_KEYS = Object.freeze([
  "record_type",
  "schema_status",
  "safe_store_id",
  "schema_version",
  "product_version",
  "failure_timestamp",
  "integrity_result",
  "recovery_state",
  "last_known_successful_integrity_check",
  "remediation_code",
  "backup_availability",
  "preserved_bytes_sha256",
  "replacement_store_id",
]);
const IDENTITY_FIELDS = Object.freeze([
  "record_type",
  "event_id",
  "run_id",
  "trace_id",
  "destination_host",
  "producer_id",
  "evidence_origin",
]);
const FILTER_SQL = Object.freeze({
  run_id: "run_id = ?",
  session_id: "session_id = ?",
  trace_id: "trace_id = ?",
  process_id: "process_id = ?",
  provider_id: "provider_id = ?",
  destination_host: "destination_host = ?",
  application_status: "application_status = ?",
  optics_status: "optics_status = ?",
  issue_location: "issue_location = ?",
  http_status: "http_status = ?",
  lifecycle: "lifecycle = ?",
  coverage: "coverage = ?",
  origin: "evidence_origin = ?",
});
const SCHEMA_STATEMENTS = Object.freeze([
  `CREATE TABLE IF NOT EXISTS store_meta (
          meta_key TEXT PRIMARY KEY,
          meta_value TEXT NOT NULL
        )`,
  `CREATE TABLE IF NOT EXISTS records (
          row_id INTEGER PRIMARY KEY,
          record_type TEXT NOT NULL,
          operational_schema_version INTEGER NOT NULL,
          privacy_generation INTEGER NOT NULL,
          body_json TEXT NOT NULL,
          identity_hash TEXT NOT NULL,
          event_id TEXT,
          run_id TEXT,
          session_id TEXT,
          trace_id TEXT,
          process_id TEXT,
          provider_id TEXT,
          destination_host TEXT,
          application_status TEXT,
          optics_status TEXT,
          issue_location TEXT,
          http_status INTEGER,
          lifecycle TEXT,
          evidence_origin TEXT,
          coverage TEXT,
          started_at TEXT,
          duration_ms INTEGER,
          producer_id TEXT,
          producer_sequence INTEGER,
          sampling TEXT
        )`,
  `CREATE TABLE IF NOT EXISTS drops (
          drop_id INTEGER PRIMARY KEY,
          dropped_at TEXT NOT NULL,
          drop_count INTEGER NOT NULL
        )`,
  "CREATE INDEX IF NOT EXISTS records_started_at ON records (started_at, producer_id, producer_sequence, event_id, row_id)",
  "CREATE INDEX IF NOT EXISTS records_run_id ON records (run_id)",
  "CREATE INDEX IF NOT EXISTS records_event_id ON records (event_id)",
  "CREATE INDEX IF NOT EXISTS records_origin_time ON records (evidence_origin, started_at)",
  "CREATE INDEX IF NOT EXISTS drops_dropped_at ON drops (dropped_at)",
]);

function nowStamp() {
  return new Date().toISOString();
}

function detach(value) {
  if (value === undefined || value === null) return null;
  try {
    return JSON.parse(JSON.stringify(value));
  } catch {
    return null;
  }
}

function expandUser(input) {
  if (input === "~") return os.homedir();
  if (input.startsWith("~/")) return path.join(os.homedir(), input.slice(2));
  return input;
}

function evidenceRoot(explicit) {
  if (typeof explicit === "string" && explicit.length > 0) return path.resolve(expandUser(explicit));
  if (typeof process.env.VANTIO_HOME === "string" && process.env.VANTIO_HOME.length > 0) {
    return path.resolve(expandUser(process.env.VANTIO_HOME));
  }
  return path.join(os.homedir(), ".vantio");
}

function isDenied(err) {
  return Boolean(err) && DENIED.has(err.code);
}

function lstatKind(filePath) {
  try {
    const stat = fs.lstatSync(filePath);
    if (stat.isSymbolicLink()) return "symlink";
    return "present";
  } catch (err) {
    if (ABSENT.has(err.code)) return "absent";
    if (isDenied(err)) return "denied";
    throw err;
  }
}

function chmodFile(filePath) {
  if (lstatKind(filePath) !== "present") return;
  try {
    fs.chmodSync(filePath, 0o600);
  } catch {
    // Unix mode is best effort. Windows ACL detail stays Founder decision 8.
  }
}

function chmodDir(filePath) {
  if (lstatKind(filePath) !== "present") return;
  try {
    fs.chmodSync(filePath, 0o700);
  } catch {
    // Same best-effort mode rule as the file helper.
  }
}

function writeNew(filePath, data) {
  const flags = fs.constants.O_WRONLY | fs.constants.O_CREAT | fs.constants.O_EXCL;
  const fd = fs.openSync(filePath, flags, 0o600);
  try {
    fs.writeSync(fd, data);
  } finally {
    fs.closeSync(fd);
  }
  try {
    fs.chmodSync(filePath, 0o600);
  } catch {
    // The exclusive create already asked for 0600. A later chmod failure stays fail-open.
  }
}

function sha256File(filePath) {
  const digest = crypto.createHash("sha256");
  const fd = fs.openSync(filePath, "r");
  try {
    const buffer = Buffer.alloc(65536);
    let read = 0;
    do {
      read = fs.readSync(fd, buffer, 0, buffer.length, null);
      if (read > 0) digest.update(buffer.subarray(0, read));
    } while (read > 0);
  } finally {
    fs.closeSync(fd);
  }
  return digest.digest("hex");
}

function pathsFor(root) {
  const optics = path.join(root, "optics");
  const store = path.join(optics, STORE_NAME);
  return {
    root,
    optics,
    store,
    store_id: path.join(optics, "store.id"),
    backup: path.join(optics, "store.sqlite.backup"),
    recovery_dir: path.join(optics, "recovery"),
    wal: `${store}-wal`,
    shm: `${store}-shm`,
    fallback_recovery: path.join(root, RECOVERY_FALLBACK_NAME),
  };
}

function pathProbe(paths) {
  let denied = false;
  for (const key of ["optics", "store", "store_id", "backup", "recovery_dir", "wal", "shm"]) {
    const kind = lstatKind(paths[key]);
    if (kind === "symlink") return "symlink";
    if (kind === "denied") denied = true;
  }
  if (denied) return "denied";
  return "clear";
}

function isSqliteError(err) {
  return Boolean(err) && err.code === "ERR_SQLITE_ERROR";
}

function cannotLoad(err) {
  return Boolean(err) && err.code === "NODE_BINDING_CANNOT_LOAD";
}

function firstCell(row) {
  if (!row || typeof row !== "object") return undefined;
  const key = Object.keys(row)[0];
  if (key === undefined) return undefined;
  return row[key];
}

function asInt(value) {
  if (typeof value === "boolean" || value == null) return null;
  if (typeof value === "bigint") {
    const asNumber = Number(value);
    return Number.isSafeInteger(asNumber) ? asNumber : null;
  }
  if (typeof value === "number") return Number.isInteger(value) ? value : null;
  if (typeof value === "string" && /^-?\d+$/.test(value)) {
    const parsed = Number(value);
    return Number.isSafeInteger(parsed) ? parsed : null;
  }
  return null;
}

function unlinkCreated(filePath) {
  if (lstatKind(filePath) !== "present") return;
  try {
    fs.unlinkSync(filePath);
  } catch {
    // A failed create still fail-opens. Leftover bytes are reported by the caller.
  }
}

function connect(session, filePath, readOnly) {
  const before = lstatKind(filePath);
  try {
    return session.openDatabase(filePath, readOnly === true);
  } catch (err) {
    if (!readOnly && before === "absent") {
      unlinkCreated(filePath);
      unlinkCreated(`${filePath}-wal`);
      unlinkCreated(`${filePath}-shm`);
    }
    throw err;
  }
}

function journalIsWal(db) {
  const row = db.prepare("PRAGMA journal_mode=WAL").get();
  const value = firstCell(row);
  return value != null && String(value).toLowerCase() === "wal";
}

function integrityOk(db) {
  try {
    const rows = db.prepare("PRAGMA integrity_check").all();
    if (rows.length !== 1) return false;
    return String(firstCell(rows[0])).toLowerCase() === "ok";
  } catch (err) {
    if (isSqliteError(err)) return false;
    throw err;
  }
}

function readUserVersion(db) {
  try {
    const row = db.prepare("PRAGMA user_version").get();
    if (!row) return null;
    return asInt(firstCell(row));
  } catch (err) {
    if (isSqliteError(err)) return null;
    throw err;
  }
}

function setUserVersion(db) {
  const version = boundary.OPERATIONAL_SCHEMA_VERSION;
  if (!Number.isInteger(version) || version < 0 || version > 2147483647) {
    throw new Error("operational schema version is not a pragma integer");
  }
  db.prepare(`PRAGMA user_version = ${version}`).run();
}

function tableNames(db) {
  const rows = db.prepare(
    "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'",
  ).all();
  const names = new Set();
  for (const row of rows) names.add(String(row.name));
  return names;
}

function readMeta(db) {
  if (!tableNames(db).has("store_meta")) return null;
  const rows = db.prepare("SELECT meta_key, meta_value FROM store_meta").all();
  const meta = {};
  for (const row of rows) meta[String(row.meta_key)] = String(row.meta_value);
  return meta;
}

function installSchema(db, storeId, checkedAt) {
  for (const statement of SCHEMA_STATEMENTS) db.exec(statement);
  const meta = {
    schema_status: boundary.SCHEMA_STATUS,
    operational_schema_version: String(boundary.OPERATIONAL_SCHEMA_VERSION),
    privacy_generation: String(boundary.PRIVACY_GENERATION),
    safe_store_id: storeId,
    migration_state: "IDLE",
    last_known_successful_integrity_check: checkedAt,
  };
  const insert = db.prepare(
    "INSERT INTO store_meta (meta_key, meta_value) VALUES (?, ?) ON CONFLICT(meta_key) DO UPDATE SET meta_value = excluded.meta_value",
  );
  for (const [key, value] of Object.entries(meta)) insert.run(key, value);
  setUserVersion(db);
}

function beginImmediate(db) {
  db.exec("BEGIN IMMEDIATE");
}

function commit(db) {
  db.exec("COMMIT");
}

function rollback(db) {
  try {
    db.exec("ROLLBACK");
  } catch (err) {
    if (!isSqliteError(err)) throw err;
  }
}

function closeQuiet(db) {
  if (!db) return;
  try {
    db.close();
  } catch {
    // Closing a failed connection still returns control to the caller.
  }
}

function isDirectory(filePath) {
  try {
    return fs.statSync(filePath).isDirectory();
  } catch (err) {
    if (isDenied(err)) {
      const denied = new Error("denied");
      denied.code = "EACCES";
      throw denied;
    }
    throw err;
  }
}

function isFile(filePath) {
  try {
    return fs.statSync(filePath).isFile();
  } catch (err) {
    if (isDenied(err)) {
      const denied = new Error("denied");
      denied.code = "EACCES";
      throw denied;
    }
    throw err;
  }
}

function existsFollow(filePath) {
  try {
    fs.statSync(filePath);
    return true;
  } catch (err) {
    if (ABSENT.has(err.code)) return false;
    throw err;
  }
}

function readStoreId(filePath) {
  if (lstatKind(filePath) !== "present") return null;
  try {
    const text = fs.readFileSync(filePath, "utf8").trim();
    return SAFE_ID_RE.test(text) ? text : null;
  } catch {
    return null;
  }
}

function writeStoreId(filePath, storeId) {
  const kind = lstatKind(filePath);
  if (kind === "present") return readStoreId(filePath) === storeId;
  if (kind !== "absent") return false;
  writeNew(filePath, Buffer.from(`${storeId}\n`, "ascii"));
  return true;
}

function safeStoreId(storeId) {
  if (storeId && SAFE_ID_RE.test(storeId)) return storeId;
  return UNREADABLE_STORE_ID;
}

function envelopeBody(safeId, schemaVersion, integrityResult, recoveryState, remediationCode, preservedHash, backupAvailability, lastCheck) {
  return {
    record_type: "recovery_envelope",
    schema_status: boundary.SCHEMA_STATUS,
    safe_store_id: safeId,
    schema_version: schemaVersion,
    product_version: boundary.PACKAGE_VERSION,
    failure_timestamp: nowStamp(),
    integrity_result: integrityResult,
    recovery_state: recoveryState,
    last_known_successful_integrity_check: lastCheck,
    remediation_code: remediationCode,
    backup_availability: backupAvailability,
    preserved_bytes_sha256: preservedHash,
    replacement_store_id: null,
  };
}

function sameEnvelopeKeys(body) {
  const keys = Object.keys(body);
  if (keys.length !== ENVELOPE_KEYS.length) return false;
  const present = new Set(keys);
  return ENVELOPE_KEYS.every((key) => present.has(key));
}

function writeEnvelopeDir(directory, storeId, schemaVersion, integrityResult, recoveryState, remediationCode, preservedHash, backupAvailability, lastCheck) {
  const parentKind = lstatKind(path.dirname(directory));
  const dirKind = lstatKind(directory);
  if (parentKind === "symlink" || dirKind === "symlink") return { envelope: null, target: null, status: "refused" };
  if (parentKind === "denied" || dirKind === "denied") return { envelope: null, target: null, status: "denied" };
  try {
    if (dirKind === "absent") fs.mkdirSync(directory, { mode: 0o700 });
    else if (!isDirectory(directory)) return { envelope: null, target: null, status: "refused" };
  } catch (err) {
    if (isDenied(err)) return { envelope: null, target: null, status: "denied" };
    return { envelope: null, target: null, status: "refused" };
  }
  const after = lstatKind(directory);
  if (after !== "present") return { envelope: null, target: null, status: after === "denied" ? "denied" : "refused" };
  chmodDir(directory);
  const safeId = safeStoreId(storeId);
  const target = path.join(directory, `${safeId}.recovery.json`);
  const targetKind = lstatKind(target);
  if (targetKind === "symlink") return { envelope: null, target: null, status: "refused" };
  if (targetKind === "denied") return { envelope: null, target: null, status: "denied" };
  const envelope = envelopeBody(
    safeId,
    schemaVersion,
    integrityResult,
    recoveryState,
    remediationCode,
    preservedHash,
    backupAvailability,
    lastCheck,
  );
  if (!sameEnvelopeKeys(envelope)) return { envelope: null, target: null, status: "refused" };
  const payload = Buffer.from(canonicalJson(envelope), "utf8");
  const temporary = path.join(directory, `.${safeId}.recovery.json.tmp`);
  const temporaryKind = lstatKind(temporary);
  if (temporaryKind === "denied") return { envelope: null, target: null, status: "denied" };
  if (temporaryKind !== "absent") return { envelope: null, target: null, status: "refused" };
  try {
    writeNew(temporary, payload);
    fs.renameSync(temporary, target);
  } catch (err) {
    if (isDenied(err)) return { envelope: null, target: null, status: "denied" };
    return { envelope: null, target: null, status: "refused" };
  }
  chmodFile(target);
  return { envelope, target, status: "written" };
}

function writeEnvelope(paths, storeId, schemaVersion, integrityResult, recoveryState, remediationCode, preservedHash, backupAvailability, lastCheck) {
  const primary = writeEnvelopeDir(
    paths.recovery_dir,
    storeId,
    schemaVersion,
    integrityResult,
    recoveryState,
    remediationCode,
    preservedHash,
    backupAvailability,
    lastCheck,
  );
  if (primary.status !== "denied") return primary;
  return writeEnvelopeDir(
    paths.fallback_recovery,
    storeId,
    schemaVersion,
    integrityResult,
    recoveryState,
    remediationCode,
    preservedHash,
    backupAvailability,
    lastCheck,
  );
}

function copyStoreFile(paths) {
  const sourceKind = lstatKind(paths.store);
  const targetKind = lstatKind(paths.backup);
  if (sourceKind !== "present" || targetKind === "symlink" || targetKind === "denied") return "UNKNOWN";
  if (targetKind === "present") return "AVAILABLE";
  try {
    writeNew(paths.backup, fs.readFileSync(paths.store));
  } catch {
    return "UNKNOWN";
  }
  return "AVAILABLE";
}

function chmodSidecars(paths) {
  for (const key of ["store", "wal", "shm", "store_id", "backup"]) chmodFile(paths[key]);
}

function createHandle(paths) {
  const handle = {
    paths,
    opened: false,
    healthy: false,
    writes_enabled: false,
    application_continues: true,
    application_result: null,
    default_write_path: false,
    evidence_tier: boundary.EVIDENCE_TIER,
    node_binding: boundary.NODE_BINDING,
    founder_decision_9: boundary.FOUNDER_DECISION_9,
    schema_status: boundary.SCHEMA_STATUS,
    reason_code: null,
    file_created: false,
    conn: null,
    safe_store_id: null,
    user_version: null,
    privacy_generation: null,
    integrity: "UNKNOWN",
    recovery: null,
    recovery_path: null,
    recovery_state: null,
    diagnostic_failures: 0,
    _last_check: null,
    evidence_root: paths.root,
    store_path: paths.store,
    pkg02_flags_ignored: true,
    stored: false,
    record: null,
    records: [],
    rows: [],
  };
  handle.close = () => closeHandle(handle);
  handle.put = (record, options) => put(handle, record, options);
  handle.get = (options) => getRecord(handle, options);
  handle.query = (request) => query(handle, request);
  handle.salvage = () => salvage(handle);
  return handle;
}

function closeHandle(handle) {
  if (handle.conn) {
    closeQuiet(handle.conn);
    handle.conn = null;
  }
  if (handle.paths) chmodSidecars(handle.paths);
}

function bareStopped(reason, applicationResult) {
  return {
    application_continues: true,
    application_result: detach(applicationResult),
    default_write_path: false,
    evidence_tier: boundary.EVIDENCE_TIER,
    file_created: false,
    founder_decision_9: boundary.FOUNDER_DECISION_9,
    node_binding: boundary.NODE_BINDING,
    opened: false,
    reason_code: reason,
    record: null,
    records: [],
    rows: [],
    schema_status: boundary.SCHEMA_STATUS,
    stored: false,
    writes_enabled: false,
  };
}

function stoppedHandle(paths, reason, integrity) {
  const handle = createHandle(paths);
  handle.reason_code = reason;
  if (integrity) handle.integrity = integrity;
  return handle;
}

function noteEnvelope(handle, written) {
  handle.recovery = written.envelope;
  handle.recovery_path = written.target;
  handle.recovery_state = written.envelope ? written.envelope.recovery_state : null;
  return handle;
}

function backupVisibility(paths) {
  const kind = lstatKind(paths.backup);
  if (kind === "present") return "AVAILABLE";
  if (kind === "absent") return "ABSENT";
  return "UNKNOWN";
}

function permissionDeniedOpen(paths) {
  const handle = createHandle(paths);
  let written = { envelope: null, target: null };
  try {
    written = writeEnvelope(
      paths,
      readStoreId(paths.store_id),
      null,
      "UNREADABLE",
      "STOPPED_PRESERVED",
      "INTEGRITY_FAILED",
      null,
      backupVisibility(paths),
      null,
    );
  } catch (err) {
    if (!isDenied(err)) throw err;
  }
  noteEnvelope(handle, written);
  handle.recovery_state = "STOPPED_PRESERVED";
  handle.reason_code = "INTEGRITY_FAILED";
  handle.integrity = "UNREADABLE";
  return handle;
}

function unreadableOpen(paths) {
  const handle = createHandle(paths);
  const written = writeEnvelope(
    paths,
    readStoreId(paths.store_id),
    null,
    "UNREADABLE",
    "STOPPED_PRESERVED",
    "INTEGRITY_FAILED",
    null,
    backupVisibility(paths),
    null,
  );
  noteEnvelope(handle, written);
  handle.recovery_state = "STOPPED_PRESERVED";
  handle.reason_code = "INTEGRITY_FAILED";
  handle.integrity = "UNREADABLE";
  return handle;
}

function sqlRejected(value) {
  if (!value || typeof value !== "object") return false;
  if (Object.prototype.hasOwnProperty.call(value, "sql")) return true;
  if (Object.prototype.hasOwnProperty.call(value, "statement")) return true;
  return false;
}

function settingsOf(options) {
  if (!options || typeof options !== "object" || Array.isArray(options)) return {};
  return options;
}

function writerPrivacy(settings) {
  const value = Object.prototype.hasOwnProperty.call(settings, "writerPrivacyGeneration")
    ? settings.writerPrivacyGeneration
    : settings.writer_privacy_generation;
  if (value === undefined) return boundary.PRIVACY_GENERATION;
  if (typeof value !== "number" || typeof value === "boolean" || !Number.isInteger(value)) {
    return boundary.PRIVACY_GENERATION;
  }
  return value;
}

function openStore(options) {
  const settings = settingsOf(options);
  if (typeof options === "string" || sqlRejected(settings)) {
    return bareStopped("SQL_REJECTED", settings.applicationResult);
  }
  const root = evidenceRoot(settings.evidenceRoot);
  const paths = pathsFor(root);
  if (!selectedBindingSupported(process.versions.node)) {
    return stoppedHandle(paths, boundary.REASON_NODE_BINDING_CANNOT_LOAD);
  }
  const session = loadNodeSqliteSession();
  if (!session) return stoppedHandle(paths, boundary.REASON_NODE_BINDING_CANNOT_LOAD);
  if (lstatKind(root) === "symlink") return stoppedHandle(paths, "SYMLINK_REFUSED");
  try {
    return openLocated(paths, root, settings, session);
  } catch (err) {
    if (isDenied(err)) return permissionDeniedOpen(paths);
    if (cannotLoad(err)) return stoppedHandle(paths, boundary.REASON_NODE_BINDING_CANNOT_LOAD);
    if (isSqliteError(err)) return stoppedHandle(paths, "STORE_UNAVAILABLE");
    throw err;
  }
}

function openLocated(paths, root, settings, session) {
  const probe = pathProbe(paths);
  if (probe === "symlink") return stoppedHandle(paths, "SYMLINK_REFUSED");
  if (probe === "denied") return permissionDeniedOpen(paths);
  const storeKind = lstatKind(paths.store);
  if (storeKind === "denied") return permissionDeniedOpen(paths);
  if (storeKind === "absent") {
    if (settings.create !== true) return stoppedHandle(paths, "STORE_ABSENT");
    const rootKind = lstatKind(root);
    if (rootKind !== "present") return stoppedHandle(paths, "STORE_ROOT_ABSENT");
    try {
      if (!isDirectory(root)) return stoppedHandle(paths, "STORE_ROOT_ABSENT");
    } catch (err) {
      if (isDenied(err)) return permissionDeniedOpen(paths);
      throw err;
    }
    return createStore(paths, session);
  }
  if (storeKind !== "present") return stoppedHandle(paths, "STORE_NOT_A_FILE");
  try {
    if (!isFile(paths.store)) return stoppedHandle(paths, "STORE_NOT_A_FILE");
  } catch (err) {
    if (isDenied(err)) return permissionDeniedOpen(paths);
    throw err;
  }
  let before;
  try {
    before = sha256File(paths.store);
  } catch (err) {
    if (isDenied(err)) return unreadableOpen(paths);
    return unreadableOpen(paths);
  }
  return openExisting(paths, before, writerPrivacy(settings), settings.injectMigrationFault === true || settings.inject_migration_fault === true, session);
}

function createStore(paths, session) {
  const handle = createHandle(paths);
  try {
    if (lstatKind(paths.optics) === "absent") fs.mkdirSync(paths.optics, { mode: 0o700 });
  } catch {
    handle.reason_code = "STORE_UNAVAILABLE";
    return handle;
  }
  if (lstatKind(paths.optics) === "symlink" || existsFollow(paths.store) || lstatKind(paths.store) === "symlink") {
    handle.reason_code = lstatKind(paths.store) === "symlink" ? "SYMLINK_REFUSED" : "STORE_UNAVAILABLE";
    return handle;
  }
  chmodDir(paths.optics);
  const storeId = crypto.randomBytes(16).toString("hex");
  let db;
  try {
    db = connect(session, paths.store, false);
  } catch (err) {
    if (cannotLoad(err)) {
      handle.reason_code = boundary.REASON_NODE_BINDING_CANNOT_LOAD;
      return handle;
    }
    if (isSqliteError(err)) {
      handle.reason_code = "STORE_UNAVAILABLE";
      return handle;
    }
    throw err;
  }
  handle.file_created = true;
  chmodFile(paths.store);
  let checkedAt;
  try {
    if (!journalIsWal(db)) {
      closeQuiet(db);
      handle.reason_code = "WAL_UNAVAILABLE";
      return handle;
    }
    checkedAt = nowStamp();
    beginImmediate(db);
    installSchema(db, storeId, checkedAt);
    commit(db);
  } catch (err) {
    if (isSqliteError(err) || cannotLoad(err)) {
      rollback(db);
      closeQuiet(db);
      handle.reason_code = isSqliteError(err) ? "STORE_UNAVAILABLE" : boundary.REASON_NODE_BINDING_CANNOT_LOAD;
      return handle;
    }
    rollback(db);
    closeQuiet(db);
    throw err;
  }
  if (!writeStoreId(paths.store_id, storeId)) {
    closeQuiet(db);
    handle.reason_code = "STORE_UNAVAILABLE";
    return handle;
  }
  return finishOpen(handle, db, storeId, boundary.OPERATIONAL_SCHEMA_VERSION, boundary.PRIVACY_GENERATION, checkedAt);
}

function finishOpen(handle, db, storeId, version, privacy, checkedAt) {
  handle.conn = db;
  handle.opened = true;
  handle.healthy = true;
  handle.writes_enabled = true;
  handle.safe_store_id = storeId;
  handle.user_version = version;
  handle.privacy_generation = privacy;
  handle.integrity = "OK";
  handle._last_check = checkedAt;
  handle.reason_code = "OK";
  chmodSidecars(handle.paths);
  return handle;
}

function openExisting(paths, beforeHash, writerPrivacyGeneration, injectMigrationFault, session) {
  const handle = createHandle(paths);
  let probe;
  try {
    probe = connect(session, paths.store, true);
  } catch (err) {
    if (isDenied(err)) return unreadableOpen(paths);
    if (cannotLoad(err)) return stoppedHandle(paths, boundary.REASON_NODE_BINDING_CANNOT_LOAD);
    let after;
    try {
      after = sha256File(paths.store);
    } catch {
      return unreadableOpen(paths);
    }
    const preserved = after === beforeHash ? beforeHash : null;
    // Python sqlite3.connect leaves a readable torn file for PRAGMA integrity_check,
    // which records FAILED. node:sqlite can reject that file at open. A malformed
    // image is the same host-file outcome: bytes stay, disclosure is STOPPED_PRESERVED.
    const malformed = isSqliteError(err) && /not a database|malformed|disk image/i.test(String(err.message || ""));
    const written = writeEnvelope(
      paths,
      readStoreId(paths.store_id),
      null,
      malformed ? "FAILED" : "UNREADABLE",
      "STOPPED_PRESERVED",
      "INTEGRITY_FAILED",
      preserved,
      backupVisibility(paths),
      null,
    );
    noteEnvelope(handle, written);
    handle.recovery_state = "STOPPED_PRESERVED";
    handle.reason_code = "INTEGRITY_FAILED";
    handle.integrity = malformed ? "FAILED" : "UNREADABLE";
    return handle;
  }
  let version = null;
  let intact = false;
  let meta = null;
  let names = new Set();
  try {
    version = readUserVersion(probe);
    intact = integrityOk(probe);
    meta = intact ? readMeta(probe) : null;
    names = intact ? tableNames(probe) : new Set();
  } catch (err) {
    if (!isSqliteError(err)) {
      closeQuiet(probe);
      throw err;
    }
    intact = false;
    version = null;
    meta = null;
    names = new Set();
  }
  closeQuiet(probe);
  const after = sha256File(paths.store);
  if (after !== beforeHash) {
    handle.reason_code = "BYTES_CHANGED";
    handle.integrity = "FAILED";
    return handle;
  }
  const sidecarId = readStoreId(paths.store_id);
  const lastCheck = meta ? meta.last_known_successful_integrity_check : null;
  const allowed = new Set(["store_meta", "records", "drops"]);
  let foreign = false;
  if (intact) {
    for (const name of names) {
      if (!allowed.has(name)) foreign = true;
    }
  }
  if (intact && foreign) return migrationStopped(paths, handle, beforeHash, sidecarId, version, lastCheck);
  if (!intact) {
    const written = writeEnvelope(
      paths,
      sidecarId,
      version,
      "FAILED",
      "STOPPED_PRESERVED",
      "INTEGRITY_FAILED",
      beforeHash,
      backupVisibility(paths),
      lastCheck,
    );
    noteEnvelope(handle, written);
    handle.recovery_state = "STOPPED_PRESERVED";
    handle.reason_code = "INTEGRITY_FAILED";
    handle.integrity = "FAILED";
    handle.user_version = version;
    return handle;
  }
  if (version != null && version > boundary.OPERATIONAL_SCHEMA_VERSION) {
    return newerSchema(paths, handle, beforeHash, sidecarId, version, lastCheck);
  }
  const needsMigration = version == null || version < boundary.OPERATIONAL_SCHEMA_VERSION || !names.has("store_meta");
  if (needsMigration) return migrate(paths, handle, beforeHash, sidecarId, lastCheck, injectMigrationFault, session);
  if (!meta) return migrationStopped(paths, handle, beforeHash, sidecarId, version, lastCheck);
  const storedPrivacy = asInt(meta.privacy_generation);
  const storedOperational = asInt(meta.operational_schema_version);
  if (storedPrivacy == null || storedOperational == null) {
    return migrationStopped(paths, handle, beforeHash, sidecarId, version, lastCheck);
  }
  if (storedOperational > boundary.OPERATIONAL_SCHEMA_VERSION) {
    return newerSchema(paths, handle, beforeHash, sidecarId || meta.safe_store_id, version, lastCheck);
  }
  if (writerPrivacyGeneration < storedPrivacy) {
    const written = writeEnvelope(
      paths,
      sidecarId || meta.safe_store_id,
      version,
      "OK",
      "RECOVERY_REQUIRED",
      "WEAKER_WRITER_REFUSED",
      beforeHash,
      backupVisibility(paths),
      lastCheck,
    );
    noteEnvelope(handle, written);
    handle.recovery_state = "RECOVERY_REQUIRED";
    handle.reason_code = "WEAKER_WRITER_REFUSED";
    handle.integrity = "OK";
    handle.user_version = version;
    handle.privacy_generation = storedPrivacy;
    return handle;
  }
  const metaId = meta.safe_store_id;
  if (!metaId || !SAFE_ID_RE.test(metaId)) return migrationStopped(paths, handle, beforeHash, sidecarId, version, lastCheck);
  if (sidecarId != null && sidecarId !== metaId) return migrationStopped(paths, handle, beforeHash, sidecarId, version, lastCheck);
  let db;
  try {
    db = connect(session, paths.store, false);
    if (!journalIsWal(db)) {
      closeQuiet(db);
      handle.reason_code = "WAL_UNAVAILABLE";
      handle.integrity = "OK";
      return handle;
    }
  } catch (err) {
    if (cannotLoad(err)) return stoppedHandle(paths, boundary.REASON_NODE_BINDING_CANNOT_LOAD);
    handle.reason_code = "STORE_UNAVAILABLE";
    handle.integrity = "OK";
    return handle;
  }
  if (!writeStoreId(paths.store_id, metaId)) {
    closeQuiet(db);
    handle.reason_code = "STORE_UNAVAILABLE";
    return handle;
  }
  const checkedAt = nowStamp();
  try {
    beginImmediate(db);
    db.prepare("UPDATE store_meta SET meta_value = ? WHERE meta_key = ?").run(checkedAt, "last_known_successful_integrity_check");
    commit(db);
  } catch (err) {
    if (!isSqliteError(err)) {
      rollback(db);
      closeQuiet(db);
      throw err;
    }
    rollback(db);
    closeQuiet(db);
    handle.reason_code = "STORE_UNAVAILABLE";
    return handle;
  }
  return finishOpen(handle, db, metaId, version, storedPrivacy, checkedAt);
}

function newerSchema(paths, handle, beforeHash, storeId, version, lastCheck) {
  const written = writeEnvelope(
    paths,
    storeId,
    version,
    "OK",
    "RECOVERY_REQUIRED",
    "NEWER_SCHEMA_REFUSED",
    beforeHash,
    backupVisibility(paths),
    lastCheck,
  );
  noteEnvelope(handle, written);
  handle.recovery_state = "RECOVERY_REQUIRED";
  handle.reason_code = "NEWER_SCHEMA_REFUSED";
  handle.integrity = "OK";
  handle.user_version = version;
  return handle;
}

function migrationStopped(paths, handle, beforeHash, storeId, version, lastCheck) {
  const backup = copyStoreFile(paths);
  const after = sha256File(paths.store);
  const preserved = after === beforeHash ? beforeHash : null;
  const written = writeEnvelope(
    paths,
    storeId,
    version,
    "OK",
    "RECOVERY_REQUIRED",
    "MIGRATION_FAILED",
    preserved,
    backup,
    lastCheck,
  );
  noteEnvelope(handle, written);
  handle.recovery_state = "RECOVERY_REQUIRED";
  handle.reason_code = "MIGRATION_FAILED";
  handle.integrity = "OK";
  handle.user_version = version;
  return handle;
}

function migrationFailure(paths, handle, beforeHash, storeId, lastCheck, session) {
  const after = sha256File(paths.store);
  const preserved = after === beforeHash ? beforeHash : null;
  let version = null;
  try {
    const probe = connect(session, paths.store, true);
    version = readUserVersion(probe);
    closeQuiet(probe);
  } catch (err) {
    if (!isSqliteError(err) && !cannotLoad(err)) throw err;
    version = null;
  }
  const written = writeEnvelope(
    paths,
    storeId,
    version,
    "OK",
    "RECOVERY_REQUIRED",
    "MIGRATION_FAILED",
    preserved,
    backupVisibility(paths),
    lastCheck,
  );
  noteEnvelope(handle, written);
  handle.recovery_state = "RECOVERY_REQUIRED";
  handle.reason_code = "MIGRATION_FAILED";
  handle.integrity = "OK";
  handle.user_version = version;
  return handle;
}

function migrate(paths, handle, beforeHash, storeId, lastCheck, injectMigrationFault, session) {
  const backup = copyStoreFile(paths);
  if (backup !== "AVAILABLE") {
    const written = writeEnvelope(
      paths,
      storeId,
      0,
      "OK",
      "RECOVERY_REQUIRED",
      "MIGRATION_FAILED",
      beforeHash,
      backup,
      lastCheck,
    );
    noteEnvelope(handle, written);
    handle.recovery_state = "RECOVERY_REQUIRED";
    handle.reason_code = "MIGRATION_FAILED";
    handle.integrity = "OK";
    return handle;
  }
  let db;
  try {
    db = connect(session, paths.store, false);
  } catch (err) {
    if (cannotLoad(err)) return stoppedHandle(paths, boundary.REASON_NODE_BINDING_CANNOT_LOAD);
    return migrationFailure(paths, handle, beforeHash, storeId, lastCheck, session);
  }
  try {
    if (injectMigrationFault) {
      closeQuiet(db);
      return migrationFailure(paths, handle, beforeHash, storeId, lastCheck, session);
    }
    const names = tableNames(db);
    for (const name of names) {
      if (name !== "store_meta" && name !== "records" && name !== "drops") {
        closeQuiet(db);
        return migrationFailure(paths, handle, beforeHash, storeId, lastCheck, session);
      }
    }
    if (!journalIsWal(db)) {
      closeQuiet(db);
      return migrationFailure(paths, handle, beforeHash, storeId, lastCheck, session);
    }
    const minted = storeId || crypto.randomBytes(16).toString("hex");
    const checkedAt = nowStamp();
    beginImmediate(db);
    installSchema(db, minted, checkedAt);
    commit(db);
    if (!writeStoreId(paths.store_id, minted)) {
      closeQuiet(db);
      return migrationFailure(paths, handle, beforeHash, storeId, lastCheck, session);
    }
    return finishOpen(handle, db, minted, boundary.OPERATIONAL_SCHEMA_VERSION, boundary.PRIVACY_GENERATION, checkedAt);
  } catch (err) {
    if (!isSqliteError(err)) {
      rollback(db);
      closeQuiet(db);
      throw err;
    }
    rollback(db);
    closeQuiet(db);
    return migrationFailure(paths, handle, beforeHash, storeId, lastCheck, session);
  }
}

function putResult(stored, reason, applicationResult, record, duplicate) {
  return {
    application_continues: true,
    application_result: detach(applicationResult),
    default_write_path: false,
    duplicate: duplicate === true,
    evidence_tier: boundary.EVIDENCE_TIER,
    reason_code: reason,
    record: record === undefined ? null : record,
    schema_status: boundary.SCHEMA_STATUS,
    stored,
    writes_enabled: stored === true,
  };
}

function columnText(record, name) {
  const value = record[name];
  if (value == null) return null;
  return typeof value === "string" ? value : null;
}

function columnInt(record, name) {
  const value = record[name];
  if (typeof value === "boolean" || typeof value !== "number" || !Number.isInteger(value)) return null;
  return value;
}

function identityHash(record) {
  const payload = {};
  for (const name of IDENTITY_FIELDS) payload[name] = Object.prototype.hasOwnProperty.call(record, name) ? record[name] : null;
  return crypto.createHash("sha256").update(canonicalJson(payload), "utf8").digest("hex");
}

function loadStoredBody(text) {
  try {
    const loaded = JSON.parse(text);
    if (!loaded || typeof loaded !== "object" || Array.isArray(loaded)) return null;
    return loaded;
  } catch {
    return null;
  }
}

function noteDrop(handle) {
  if (!handle || !handle.conn || !handle.writes_enabled) {
    if (handle) handle.diagnostic_failures += 1;
    return;
  }
  try {
    beginImmediate(handle.conn);
    handle.conn.prepare("INSERT INTO drops (dropped_at, drop_count) VALUES (?, ?)").run(nowStamp(), 1);
    commit(handle.conn);
  } catch (err) {
    if (!isSqliteError(err)) throw err;
    rollback(handle.conn);
    if (handle.diagnostic_failures === 0) handle.diagnostic_failures = 1;
  }
}

function corruptBody(handle, applicationResult) {
  rollback(handle.conn);
  if (handle.diagnostic_failures === 0) handle.diagnostic_failures = 1;
  return putResult(false, "REQUIRED_EVIDENCE_CORRUPT", applicationResult);
}

function put(handle, record, options) {
  const settings = settingsOf(options);
  const applicationResult = Object.prototype.hasOwnProperty.call(settings, "applicationResult")
    ? settings.applicationResult
    : settings.application_result;
  if (typeof record === "string" || sqlRejected(settings) || sqlRejected(record)) {
    return putResult(false, "SQL_REJECTED", applicationResult);
  }
  if (!handle || typeof handle !== "object" || !handle.writes_enabled || !handle.conn) {
    return putResult(false, (handle && handle.reason_code) || "WRITE_STOPPED", applicationResult);
  }
  if (!record || typeof record !== "object" || Array.isArray(record)) {
    noteDrop(handle);
    return putResult(false, "REJECT_RECORD", applicationResult);
  }
  let validated;
  try {
    validated = validateEvidence(record, { applicationResult });
  } catch {
    if (handle.diagnostic_failures === 0) handle.diagnostic_failures = 1;
    return putResult(false, "VALIDATOR_FAULT", applicationResult);
  }
  const emitted = validated && typeof validated === "object" ? validated.record : null;
  if (!emitted || typeof emitted !== "object" || Array.isArray(emitted)) {
    noteDrop(handle);
    const reason = validated && typeof validated === "object" ? validated.reason_code : "REJECT_RECORD";
    return putResult(false, reason || "REJECT_RECORD", applicationResult);
  }
  let body;
  let identity;
  try {
    body = canonicalJson(emitted);
    identity = identityHash(emitted);
  } catch {
    if (handle.diagnostic_failures === 0) handle.diagnostic_failures = 1;
    return putResult(false, "WRITE_STOPPED", applicationResult);
  }
  const eventId = columnText(emitted, "event_id");
  try {
    beginImmediate(handle.conn);
    const existing = eventId == null
      ? []
      : handle.conn.prepare("SELECT body_json, identity_hash FROM records WHERE event_id = ?").all(eventId);
    const same = existing.filter((row) => row.identity_hash === identity);
    if (same.length > 0) {
      const loaded = loadStoredBody(same[0].body_json);
      if (!loaded) return corruptBody(handle, applicationResult);
      commit(handle.conn);
      return putResult(true, "IDEMPOTENT_DUPLICATE", applicationResult, loaded, true);
    }
    let storedBody = body;
    let storedRecord = emitted;
    let storedIdentity = identity;
    if (existing.length > 0) {
      storedRecord = { ...emitted, identity_conflict: "PRODUCER_SEQUENCE" };
      storedBody = canonicalJson(storedRecord);
      storedIdentity = identityHash(storedRecord);
      for (const row of existing) {
        const previous = loadStoredBody(row.body_json);
        if (!previous) return corruptBody(handle, applicationResult);
        previous.identity_conflict = "PRODUCER_SEQUENCE";
        handle.conn.prepare(
          "UPDATE records SET body_json = ? WHERE event_id = ? AND identity_hash = ?",
        ).run(canonicalJson(previous), eventId, row.identity_hash);
      }
    }
    handle.conn.prepare(
      `INSERT INTO records (
              record_type, operational_schema_version, privacy_generation, body_json, identity_hash,
              event_id, run_id, session_id, trace_id, process_id, provider_id, destination_host,
              application_status, optics_status, issue_location, http_status, lifecycle,
              evidence_origin, coverage, started_at, duration_ms, producer_id, producer_sequence, sampling
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    ).run(
      columnText(storedRecord, "record_type") || "observation_event",
      boundary.OPERATIONAL_SCHEMA_VERSION,
      boundary.PRIVACY_GENERATION,
      storedBody,
      storedIdentity,
      eventId,
      columnText(storedRecord, "run_id"),
      columnText(storedRecord, "session_id"),
      columnText(storedRecord, "trace_id"),
      storedRecord.process_id == null ? null : String(storedRecord.process_id),
      columnText(storedRecord, "provider_id"),
      columnText(storedRecord, "destination_host"),
      columnText(storedRecord, "application_status"),
      columnText(storedRecord, "optics_status"),
      columnText(storedRecord, "issue_location"),
      columnInt(storedRecord, "http_status"),
      columnText(storedRecord, "lifecycle"),
      columnText(storedRecord, "evidence_origin"),
      columnText(storedRecord, "coverage"),
      columnText(storedRecord, "started_at"),
      columnInt(storedRecord, "duration_ms"),
      columnText(storedRecord, "producer_id"),
      columnInt(storedRecord, "producer_sequence"),
      columnText(storedRecord, "sampling"),
    );
    commit(handle.conn);
    chmodSidecars(handle.paths);
    return putResult(true, "OK", applicationResult, JSON.parse(storedBody));
  } catch (err) {
    if (!isSqliteError(err)) {
      rollback(handle.conn);
      throw err;
    }
    rollback(handle.conn);
    if (handle.diagnostic_failures === 0) handle.diagnostic_failures = 1;
    return putResult(false, "WRITE_STOPPED", applicationResult);
  }
}

function getRecord(handle, options) {
  const settings = settingsOf(options);
  if (typeof options === "string" || sqlRejected(settings)) {
    return { application_continues: true, reason_code: "SQL_REJECTED", records: [], writes_enabled: false };
  }
  if (!handle || !handle.healthy || !handle.conn) {
    return {
      application_continues: true,
      completeness: "UNAVAILABLE",
      reason_code: (handle && handle.reason_code) || "STORE_UNAVAILABLE",
      records: [],
      writes_enabled: false,
    };
  }
  const eventId = Object.prototype.hasOwnProperty.call(settings, "event_id") ? settings.event_id : settings.eventId;
  const runId = Object.prototype.hasOwnProperty.call(settings, "run_id") ? settings.run_id : settings.runId;
  const hasEvent = eventId != null;
  const hasRun = runId != null;
  if (hasEvent === hasRun) {
    return { application_continues: true, reason_code: "REJECTED_FIELD", records: [], writes_enabled: true };
  }
  let lookup;
  let value;
  if (hasEvent) {
    if (typeof eventId !== "string") {
      return { application_continues: true, reason_code: "REJECTED_FIELD", records: [], writes_enabled: true };
    }
    lookup = "SELECT body_json FROM records WHERE event_id = ? ORDER BY row_id ASC";
    value = eventId;
  } else {
    if (typeof runId !== "string") {
      return { application_continues: true, reason_code: "REJECTED_FIELD", records: [], writes_enabled: true };
    }
    lookup = "SELECT body_json FROM records WHERE run_id = ? ORDER BY row_id ASC";
    value = runId;
  }
  let rows;
  try {
    rows = handle.conn.prepare(lookup).all(value);
  } catch (err) {
    if (!isSqliteError(err)) throw err;
    return { application_continues: true, reason_code: "WRITE_STOPPED", records: [], writes_enabled: false };
  }
  const records = [];
  for (const row of rows) {
    try {
      records.push(JSON.parse(row.body_json));
    } catch {
      return {
        application_continues: true,
        completeness: "UNAVAILABLE",
        reason_code: "REQUIRED_EVIDENCE_CORRUPT",
        records: [],
        writes_enabled: false,
      };
    }
  }
  return {
    application_continues: true,
    reason_code: "OK",
    records,
    schema_status: boundary.SCHEMA_STATUS,
    writes_enabled: handle.writes_enabled,
  };
}

function queryRejected(reason) {
  return {
    application_continues: true,
    accepted: false,
    completeness: "UNAVAILABLE",
    completenessReasons: ["REQUIRED_EVIDENCE_UNAVAILABLE"],
    declaredScope: null,
    default_write_path: false,
    dropState: "UNKNOWN",
    evidence_tier: boundary.EVIDENCE_TIER,
    freshness: "UNKNOWN",
    hasMore: false,
    integrityState: "UNKNOWN",
    limitation: LIMITATION,
    matchingRecords: null,
    next_cursor: null,
    reason_code: reason,
    returnedRecords: 0,
    rows: [],
    samplingState: "UNKNOWN",
    scanned_bounded: true,
    schema_status: boundary.SCHEMA_STATUS,
  };
}

function boundedInt(value, lower, upper) {
  if (typeof value === "boolean" || typeof value !== "number" || !Number.isInteger(value)) return null;
  if (value < lower || value > upper) return null;
  return value;
}

function encodeCursor(payload) {
  const raw = Buffer.from(canonicalJson(payload), "utf8").toString("base64");
  return raw.replace(/\+/g, "-").replace(/\//g, "_");
}

function decodeCursor(cursor) {
  if (typeof cursor !== "string" || !/^[\x21-\x7e]+$/.test(cursor)) return null;
  const normalized = cursor.replace(/-/g, "+").replace(/_/g, "/");
  const padLength = normalized.length % 4 === 0 ? 0 : 4 - (normalized.length % 4);
  try {
    const text = Buffer.from(normalized + "=".repeat(padLength), "base64").toString("utf8");
    const decoded = JSON.parse(text);
    if (!decoded || typeof decoded !== "object" || Array.isArray(decoded)) return null;
    return decoded;
  } catch {
    return null;
  }
}

function validateRequest(request) {
  let body = request;
  if (body == null) body = {};
  if (typeof body === "string") return { normalized: null, reason: "SQL_REJECTED" };
  if (!body || typeof body !== "object" || Array.isArray(body)) return { normalized: null, reason: "REJECTED_FIELD" };
  const keys = Object.keys(body);
  for (const key of keys) {
    if (SQL_FIELDS.has(key)) return { normalized: null, reason: "SQL_REJECTED" };
    if (REGEX_FIELDS.has(key)) return { normalized: null, reason: "REGEX_REJECTED" };
    if (!REQUEST_FIELD_SET.has(key)) return { normalized: null, reason: "REJECTED_FIELD" };
  }
  if (body.freshness === "CURRENT") return { normalized: null, reason: "CURRENT_NOT_EMITTED" };
  const limit = boundedInt(Object.prototype.hasOwnProperty.call(body, "limit") ? body.limit : QUERY_LIMIT_DEFAULT, 1, QUERY_LIMIT_MAX);
  if (limit == null) return { normalized: null, reason: "LIMIT_REJECTED" };
  const sort = Object.prototype.hasOwnProperty.call(body, "sort") ? body.sort : "started_at_asc";
  if (sort !== "started_at_asc" && sort !== "started_at_desc") return { normalized: null, reason: "REJECTED_FIELD" };
  const timeStart = body.time_start;
  const timeEnd = body.time_end;
  const hasTime = timeStart != null || timeEnd != null;
  if (hasTime && (typeof timeStart !== "string" || typeof timeEnd !== "string" || !TIMESTAMP_RE.test(timeStart) || !TIMESTAMP_RE.test(timeEnd))) {
    return { normalized: null, reason: "TIME_RANGE_REQUIRED" };
  }
  if (!hasTime && typeof body.run_id !== "string") return { normalized: null, reason: "TIME_RANGE_REQUIRED" };
  const origin = Object.prototype.hasOwnProperty.call(body, "origin") ? body.origin : "LOCAL_OBSERVATION";
  if (!KNOWN_ORIGINS.has(origin)) return { normalized: null, reason: "REJECTED_FIELD" };
  for (const name of ["duration_min_ms", "duration_max_ms"]) {
    if (Object.prototype.hasOwnProperty.call(body, name) && boundedInt(body[name], 0, MAX_INT) == null) {
      return { normalized: null, reason: "REJECTED_FIELD" };
    }
  }
  if (Object.prototype.hasOwnProperty.call(body, "http_status") && boundedInt(body.http_status, 0, 999) == null) {
    return { normalized: null, reason: "REJECTED_FIELD" };
  }
  for (const name of ["run_id", "session_id", "trace_id", "provider_id", "destination_host", "application_status", "optics_status", "issue_location", "lifecycle", "coverage"]) {
    if (Object.prototype.hasOwnProperty.call(body, name) && typeof body[name] !== "string") {
      return { normalized: null, reason: "REJECTED_FIELD" };
    }
  }
  if (Object.prototype.hasOwnProperty.call(body, "process_id")) {
    const processId = body.process_id;
    if (typeof processId === "boolean" || (typeof processId !== "string" && typeof processId !== "number")) {
      return { normalized: null, reason: "REJECTED_FIELD" };
    }
  }
  let decoded = null;
  if (body.cursor != null) {
    if (typeof body.cursor !== "string") return { normalized: null, reason: "CURSOR_REJECTED" };
    decoded = decodeCursor(body.cursor);
    if (!decoded) return { normalized: null, reason: "CURSOR_REJECTED" };
    const cursorKeys = Object.keys(decoded);
    const expected = ["started_at", "producer_id", "producer_sequence", "event_id", "row_id"];
    if (cursorKeys.length !== expected.length || expected.some((key) => !Object.prototype.hasOwnProperty.call(decoded, key))) {
      return { normalized: null, reason: "CURSOR_REJECTED" };
    }
  }
  return {
    normalized: {
      ...body,
      limit,
      sort,
      origin,
      _cursor: decoded,
    },
    reason: null,
  };
}

function cursorClause(sort) {
  const started = sort === "started_at_desc" ? "started_at < ?" : "started_at > ?";
  return `(${started} OR (started_at = ? AND producer_id > ?) OR (started_at = ? AND producer_id = ? AND producer_sequence > ?) OR (started_at = ? AND producer_id = ? AND producer_sequence = ? AND event_id > ?) OR (started_at = ? AND producer_id = ? AND producer_sequence = ? AND event_id = ? AND row_id > ?))`;
}

function cursorParams(decoded) {
  return [
    decoded.started_at,
    decoded.started_at,
    decoded.producer_id,
    decoded.started_at,
    decoded.producer_id,
    decoded.producer_sequence,
    decoded.started_at,
    decoded.producer_id,
    decoded.producer_sequence,
    decoded.event_id,
    decoded.started_at,
    decoded.producer_id,
    decoded.producer_sequence,
    decoded.event_id,
    decoded.row_id,
  ];
}

function scopeCompleteness(scopeRows) {
  const reasons = [];
  let sampled = false;
  let unsampled = true;
  for (const row of scopeRows) {
    if (row.sampling != null && row.sampling !== "UNSAMPLED") {
      sampled = true;
      unsampled = false;
      reasons.push("SAMPLING_NOT_UNSAMPLED");
    }
    if (row.record_type === "run_envelope" && row.lifecycle !== "COMPLETE") reasons.push("RUN_LIFECYCLE_NOT_COMPLETE");
    if (row.issue_location === "COVERAGE") reasons.push("COVERAGE_GAP_IN_SCOPE");
    let body;
    try {
      body = JSON.parse(row.body_json);
    } catch {
      reasons.push("REQUIRED_EVIDENCE_CORRUPT");
      continue;
    }
    if (!body || typeof body !== "object" || Array.isArray(body)) {
      reasons.push("REQUIRED_EVIDENCE_CORRUPT");
      continue;
    }
    if (body.identity_conflict === "PARENT") reasons.push("PARENT_CONFLICT");
    else if (body.identity_conflict === "PRODUCER_SEQUENCE") reasons.push("PRODUCER_SEQUENCE_CONFLICT");
  }
  return { reasons, sampled, unsampled };
}

function query(handle, request) {
  const checked = validateRequest(request);
  if (checked.reason) return queryRejected(checked.reason);
  const normalized = checked.normalized;
  if (!handle || !handle.healthy || !handle.conn) {
    const refused = queryRejected((handle && handle.reason_code) || "STORE_UNAVAILABLE");
    refused.integrityState = handle && (handle.integrity === "FAILED" || handle.integrity === "UNREADABLE") ? "FAILED" : "UNKNOWN";
    if (handle && handle.recovery_state === "STOPPED_PRESERVED") {
      refused.completeness = "UNAVAILABLE";
      refused.completenessReasons = ["REQUIRED_EVIDENCE_UNAVAILABLE"];
    }
    return refused;
  }
  const clauses = ["evidence_origin = ?"];
  const params = [normalized.origin];
  for (const [name, sqlText] of Object.entries(FILTER_SQL)) {
    if (name === "origin" || !Object.prototype.hasOwnProperty.call(normalized, name)) continue;
    let value = normalized[name];
    if (name === "process_id") value = String(value);
    clauses.push(sqlText);
    params.push(value);
  }
  if (Object.prototype.hasOwnProperty.call(normalized, "time_start")) {
    clauses.push("started_at >= ?");
    clauses.push("started_at <= ?");
    params.push(normalized.time_start, normalized.time_end);
  }
  if (Object.prototype.hasOwnProperty.call(normalized, "duration_min_ms")) {
    clauses.push("duration_ms >= ?");
    params.push(normalized.duration_min_ms);
  }
  if (Object.prototype.hasOwnProperty.call(normalized, "duration_max_ms")) {
    clauses.push("duration_ms <= ?");
    params.push(normalized.duration_max_ms);
  }
  const scopeSql = clauses.join(" AND ");
  let pageSql = scopeSql;
  const pageParams = params.slice();
  if (normalized._cursor) {
    pageSql = `${pageSql} AND ${cursorClause(normalized.sort)}`;
    pageParams.push(...cursorParams(normalized._cursor));
  }
  const direction = normalized.sort === "started_at_desc" ? "DESC" : "ASC";
  const order = `started_at ${direction}, producer_id ASC, producer_sequence ASC, event_id ASC, row_id ASC`;
  let total;
  let fetched;
  let dropCount;
  let dropsScoped;
  let scopeRows;
  try {
    total = firstCell(handle.conn.prepare(`SELECT COUNT(*) FROM records WHERE ${scopeSql}`).get(...params));
    fetched = handle.conn.prepare(
      `SELECT row_id, body_json, started_at, producer_id, producer_sequence, event_id, sampling, lifecycle, record_type, issue_location FROM records WHERE ${pageSql} ORDER BY ${order} LIMIT ?`,
    ).all(...pageParams, normalized.limit + 1);
    if (Object.prototype.hasOwnProperty.call(normalized, "time_start")) {
      dropCount = firstCell(handle.conn.prepare(
        "SELECT COALESCE(SUM(drop_count), 0) FROM drops WHERE dropped_at >= ? AND dropped_at <= ?",
      ).get(normalized.time_start, normalized.time_end));
      dropsScoped = true;
    } else {
      dropCount = firstCell(handle.conn.prepare("SELECT COALESCE(SUM(drop_count), 0) FROM drops").get());
      dropsScoped = false;
    }
    scopeRows = handle.conn.prepare(
      `SELECT sampling, lifecycle, record_type, issue_location, body_json FROM records WHERE ${scopeSql} ORDER BY started_at ASC, producer_id ASC, producer_sequence ASC, event_id ASC, row_id ASC`,
    ).all(...params);
  } catch (err) {
    if (!isSqliteError(err)) throw err;
    return queryRejected("STORE_UNAVAILABLE");
  }
  const hasMore = fetched.length > normalized.limit;
  const page = fetched.slice(0, normalized.limit);
  const scope = scopeCompleteness(scopeRows);
  const rows = [];
  for (const row of page) {
    const body = loadStoredBody(row.body_json);
    if (body) rows.push(body);
  }
  const reasons = scope.reasons.slice();
  const drops = asInt(dropCount) || 0;
  let dropState;
  if (drops > 0 && dropsScoped) {
    reasons.push("DROPS_IN_SCOPE");
    dropState = "DROPS_IN_SCOPE";
  } else if (drops > 0) {
    reasons.push("EVALUATION_INCOMPLETE");
    dropState = "UNKNOWN";
  } else {
    dropState = "NO_DROPS";
  }
  const uniqueReasons = [];
  for (const token of reasons) {
    if (!uniqueReasons.includes(token)) uniqueReasons.push(token);
  }
  const included = [normalized.origin];
  const excluded = ["LOCAL_OBSERVATION", ...EXCLUDED_ORIGINS].filter((name) => !included.includes(name));
  let nextCursor = null;
  if (hasMore && page.length > 0) {
    const last = page[page.length - 1];
    nextCursor = encodeCursor({
      event_id: last.event_id,
      producer_id: last.producer_id,
      producer_sequence: last.producer_sequence,
      row_id: last.row_id,
      started_at: last.started_at,
    });
  }
  const filters = {};
  for (const key of REQUEST_FIELDS) {
    if (Object.prototype.hasOwnProperty.call(normalized, key) && !key.startsWith("_")) filters[key] = normalized[key];
  }
  return {
    accepted: true,
    application_continues: true,
    completeness: uniqueReasons.length ? "PARTIAL" : "COMPLETE",
    completenessReasons: uniqueReasons,
    declaredScope: {
      filters,
      origins_excluded: excluded,
      origins_included: included,
      time_end: Object.prototype.hasOwnProperty.call(normalized, "time_end") ? normalized.time_end : null,
      time_start: Object.prototype.hasOwnProperty.call(normalized, "time_start") ? normalized.time_start : null,
    },
    default_write_path: false,
    dropState,
    evidence_tier: boundary.EVIDENCE_TIER,
    freshness: "UNKNOWN",
    hasMore,
    integrityState: "OK",
    limitation: LIMITATION,
    matchingRecords: asInt(total) || 0,
    next_cursor: nextCursor,
    reason_code: "OK",
    returnedRecords: rows.length,
    rows,
    samplingState: scope.sampled ? "SAMPLED" : (scope.unsampled ? "UNSAMPLED" : "UNKNOWN"),
    scanned_bounded: true,
    schema_status: boundary.SCHEMA_STATUS,
  };
}

function salvage(handle) {
  if (!handle || handle.recovery_state !== "STOPPED_PRESERVED") {
    const refused = queryRejected("SALVAGE_NOT_CLASSIFIED");
    refused.completeness = "UNAVAILABLE";
    return refused;
  }
  const paths = handle.paths;
  let before = null;
  if (lstatKind(paths.store) === "present") {
    try {
      before = sha256File(paths.store);
    } catch {
      before = null;
    }
  }
  const envelope = { ...(handle.recovery || {}) };
  envelope.recovery_state = "READ_ONLY_SALVAGE";
  envelope.integrity_result = handle.integrity === "FAILED" || handle.integrity === "UNREADABLE" ? handle.integrity : "FAILED";
  const written = writeEnvelope(
    paths,
    envelope.safe_store_id,
    envelope.schema_version,
    envelope.integrity_result,
    "READ_ONLY_SALVAGE",
    envelope.remediation_code || "INTEGRITY_FAILED",
    before,
    envelope.backup_availability || "UNKNOWN",
    envelope.last_known_successful_integrity_check,
  );
  if (written.envelope) {
    handle.recovery = written.envelope;
    handle.recovery_path = written.target;
    handle.recovery_state = "READ_ONLY_SALVAGE";
  }
  let after = null;
  if (before != null) {
    try {
      after = sha256File(paths.store);
    } catch {
      after = null;
    }
  }
  if (before != null && after !== before) return queryRejected("BYTES_CHANGED");
  const answer = queryRejected("SALVAGE_UNAVAILABLE");
  answer.accepted = true;
  answer.completeness = "UNAVAILABLE";
  answer.completenessReasons = ["REQUIRED_EVIDENCE_UNAVAILABLE"];
  answer.integrityState = "FAILED";
  answer.rows = [];
  answer.matchingRecords = null;
  return answer;
}

module.exports = {
  evidenceRoot,
  getRecord,
  openStore,
  put,
  query,
  salvage,
  selectedBindingSupported,
};
