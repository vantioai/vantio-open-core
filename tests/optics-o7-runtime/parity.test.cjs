"use strict";

const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const store = require("../../packages/optics-operational-store/src/index.cjs");
const gate = require("../../packages/optics-operational-store/src/runtime-gate.cjs");

const ROOT = path.resolve(__dirname, "../..");
const CORPUS = path.join(ROOT, "tests/optics-evidence-contract/corpus.json");
const CANARY = "sk-CANARYPROMPT0001";
const SUPPORTED = gate.selectedBindingSupported(process.versions.node);
const FLOOR_SKIP = SUPPORTED ? false : "below node:sqlite@24.15.0";

function cleanRecord(patch) {
  const body = JSON.parse(fs.readFileSync(CORPUS, "utf8")).bases.observation;
  return { ...body, ...patch };
}

function tempDir(name) {
  return fs.mkdtempSync(path.join(os.tmpdir(), name));
}

function floorTest(name, fn) {
  test(name, { skip: FLOOR_SKIP }, fn);
}

function cell(row) {
  return Object.values(row)[0];
}

function mode(filePath) {
  return fs.statSync(filePath).mode & 0o777;
}

function window(extra) {
  return {
    time_start: "2026-07-01T00:00:00.000Z",
    time_end: "2026-07-01T01:00:00.000Z",
    ...extra,
  };
}

function pythonSqlite(file, statements) {
  const lines = [
    "import sqlite3, pathlib",
    `path = pathlib.Path(${JSON.stringify(file)})`,
    "path.parent.mkdir(parents=True, exist_ok=True)",
    "conn = sqlite3.connect(path)",
  ];
  for (const statement of statements) lines.push(`conn.execute(${JSON.stringify(statement)})`);
  lines.push("conn.commit()", "conn.close()");
  const result = spawnSync("python3", ["-c", lines.join("\n")], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
}

function assertOffPage(handle, reason) {
  const full = handle.query(window());
  const page = handle.query(window({ limit: 1 }));
  assert.equal(full.matchingRecords, 2);
  assert.equal(full.hasMore, false);
  assert.equal(full.completeness, "PARTIAL");
  assert.deepEqual(full.completenessReasons, [reason]);
  assert.equal(page.matchingRecords, 2);
  assert.equal(page.hasMore, true);
  assert.equal(page.returnedRecords, 1);
  assert.equal(page.rows[0].event_id, "e.12.prod_clean_1.0");
  assert.equal(page.completeness, "PARTIAL");
  assert.deepEqual(page.completenessReasons, full.completenessReasons);
}

floorTest("python parity: round trip, pagination, and fixture origins", () => {
  const dir = tempDir("o7-parity-round-");
  const opened = store.openStore({ evidenceRoot: dir, create: true });
  try {
    assert.equal(opened.healthy, true);
    assert.equal(opened.schema_status, "unstable-pre-1.0");
    assert.equal(opened.privacy_generation, 1);
    assert.equal(opened.integrity, "OK");
    assert.equal(Number(cell(opened.conn.prepare("PRAGMA user_version").get())), 1);
    assert.equal(opened.conn.prepare("SELECT meta_value FROM store_meta WHERE meta_key = ?").get("privacy_generation").meta_value, "1");
    assert.equal(opened.conn.prepare("SELECT meta_value FROM store_meta WHERE meta_key = ?").get("schema_status").meta_value, "unstable-pre-1.0");
    assert.equal(fs.readFileSync(path.join(dir, "optics", "store.id"), "utf8").trim(), opened.safe_store_id);
    assert.equal(mode(path.join(dir, "optics", "store.id")), 0o600);
    const stored = opened.put(cleanRecord(), { applicationResult: { token: "APP" } });
    assert.equal(stored.stored, true);
    assert.equal(stored.record.schema_status, "unstable-pre-1.0");
    assert.equal(Object.hasOwn(stored.record, "prompt"), false);
    const page = opened.query(window());
    assert.equal(page.completeness, "COMPLETE");
    assert.deepEqual(page.completenessReasons, []);
    assert.equal(page.freshness, "UNKNOWN");
    assert.equal(page.dropState, "NO_DROPS");
    assert.equal(page.samplingState, "UNSAMPLED");
    assert.equal(page.matchingRecords, 1);
    assert.equal(page.declaredScope.origins_included[0], "LOCAL_OBSERVATION");
    assert.equal(page.declaredScope.origins_excluded.includes("TEST_FIXTURE"), true);
    assert.equal(Number(cell(opened.conn.prepare("SELECT operational_schema_version FROM records").get())), 1);
    assert.equal(mode(`${path.join(dir, "optics", "store.sqlite")}-wal`), 0o600);
    const fixture = opened.put(cleanRecord({
      evidence_origin: "TEST_FIXTURE",
      event_id: "e.12.prod_clean_1.1",
      producer_sequence: 1,
      sequence: 1,
    }));
    assert.equal(fixture.stored, true);
    assert.equal(opened.query(window()).matchingRecords, 1);
    const explicit = opened.query(window({ origin: "TEST_FIXTURE" }));
    assert.equal(explicit.matchingRecords, 1);
    assert.equal(explicit.rows[0].evidence_origin, "TEST_FIXTURE");
    const second = opened.put(cleanRecord({
      event_id: "e.12.prod_clean_1.2",
      producer_sequence: 2,
      sequence: 2,
      started_at: "2026-07-01T00:00:01.000Z",
    }));
    assert.equal(second.stored, true);
    const first = opened.query(window({ limit: 1, sort: "started_at_asc" }));
    assert.equal(first.hasMore, true);
    assert.equal(first.matchingRecords, 2);
    assert.equal(first.completeness, "COMPLETE");
    assert.equal(first.next_cursor.includes("SELECT"), false);
    const next = opened.query(window({ limit: 1, cursor: first.next_cursor }));
    assert.equal(next.returnedRecords, 1);
    assert.notEqual(next.rows[0].event_id, first.rows[0].event_id);
    assert.equal(next.hasMore, false);
  } finally {
    opened.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

floorTest("python parity: caller sql, drops, duplicates, and conflicts", () => {
  const dir = tempDir("o7-parity-sql-");
  const opened = store.openStore({ evidenceRoot: dir, create: true });
  try {
    const rejected = opened.put("DROP TABLE records");
    assert.equal(rejected.stored, false);
    assert.equal(rejected.reason_code, "SQL_REJECTED");
    assert.equal(opened.put(cleanRecord(), { sql: "DELETE FROM records" }).reason_code, "SQL_REJECTED");
    assert.equal(opened.put({ ...cleanRecord(), sql: `DROP TABLE records; ${CANARY}` }).reason_code, "SQL_REJECTED");
    const page = opened.query({ sql: "SELECT * FROM records" });
    assert.equal(page.reason_code, "SQL_REJECTED");
    assert.deepEqual(page.rows, []);
    assert.notEqual(page.completeness, "COMPLETE");
    assert.equal(opened.query(window({ pattern: ".*" })).reason_code, "REGEX_REJECTED");
    const current = opened.query(window({ freshness: "CURRENT" }));
    assert.equal(current.reason_code, "CURRENT_NOT_EMITTED");
    assert.notEqual(current.freshness, "CURRENT");
    assert.equal(opened.query({ destination_host: "api.example.com" }).reason_code, "TIME_RANGE_REQUIRED");
    assert.equal(opened.query(window({ limit: 501 })).reason_code, "LIMIT_REJECTED");
    assert.equal(opened.put(cleanRecord()).stored, true);
    const dropped = opened.put({ ...cleanRecord(), prompt: CANARY }, { applicationResult: { token: "APP" } });
    assert.equal(dropped.stored, false);
    assert.equal(dropped.application_result.token, "APP");
    const storePath = path.join(dir, "optics", "store.sqlite");
    let blob = fs.readFileSync(storePath);
    const wal = `${storePath}-wal`;
    if (fs.existsSync(wal)) blob = Buffer.concat([blob, fs.readFileSync(wal)]);
    assert.equal(blob.includes(Buffer.from(CANARY)), false);
    assert.equal(blob.includes(Buffer.from("DROP TABLE")), false);
    const drops = opened.query({
      time_start: "2026-09-27T00:00:00.000Z",
      time_end: "2026-09-27T23:59:59.000Z",
    });
    assert.equal(drops.dropState, "DROPS_IN_SCOPE");
    assert.equal(drops.completeness, "PARTIAL");
    assert.equal(drops.completenessReasons.includes("DROPS_IN_SCOPE"), true);
    assert.deepEqual(drops.rows, []);
    const duplicate = opened.put(cleanRecord());
    assert.equal(duplicate.duplicate, true);
    assert.equal(Number(cell(opened.conn.prepare("SELECT COUNT(*) AS n FROM records").get())), 1);
    const conflict = opened.put(cleanRecord({ destination_host: "api.example.org" }));
    assert.equal(conflict.stored, true);
    assert.equal(conflict.duplicate, false);
    const rows = opened.get({ event_id: "e.12.prod_clean_1.0" }).records;
    assert.equal(rows.length, 2);
    assert.deepEqual(new Set(rows.map((row) => row.identity_conflict)), new Set(["PRODUCER_SEQUENCE"]));
  } finally {
    opened.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

floorTest("python parity: torn, newer schema, weaker writer, and migration", () => {
  const tornDir = tempDir("o7-parity-torn-");
  try {
    const optics = path.join(tornDir, "optics");
    fs.mkdirSync(optics);
    const target = path.join(optics, "store.sqlite");
    const original = Buffer.from("not-a-database-torn-bytes");
    fs.writeFileSync(target, original);
    fs.chmodSync(target, 0o600);
    const torn = store.openStore({ evidenceRoot: tornDir, create: true });
    try {
      assert.equal(torn.writes_enabled, false);
      assert.equal(torn.reason_code, "INTEGRITY_FAILED");
      assert.equal(torn.integrity, "FAILED");
      assert.equal(torn.recovery_state, "STOPPED_PRESERVED");
      assert.equal(fs.readFileSync(target).equals(original), true);
      assert.equal(torn.recovery.record_type, "recovery_envelope");
      assert.equal(torn.recovery.integrity_result, "FAILED");
      assert.equal(torn.recovery.remediation_code, "INTEGRITY_FAILED");
      assert.equal(torn.recovery.replacement_store_id, null);
      assert.equal(Object.hasOwn(torn.recovery, "prompt"), false);
      assert.equal(mode(torn.recovery_path), 0o600);
      assert.equal(fs.readFileSync(torn.recovery_path).includes(Buffer.from("hostname")), false);
      const page = torn.query(window());
      assert.equal(page.completeness, "UNAVAILABLE");
      assert.deepEqual(page.rows, []);
      const salvaged = torn.salvage();
      assert.notEqual(salvaged.completeness, "COMPLETE");
      assert.deepEqual(salvaged.rows, []);
      assert.equal(fs.readFileSync(target).equals(original), true);
      assert.equal(torn.recovery.recovery_state, "READ_ONLY_SALVAGE");
    } finally {
      torn.close();
    }
  } finally {
    fs.rmSync(tornDir, { recursive: true, force: true });
  }

  const newerDir = tempDir("o7-parity-newer-");
  const created = store.openStore({ evidenceRoot: newerDir, create: true });
  assert.equal(created.put(cleanRecord()).stored, true);
  created.close();
  const db = path.join(newerDir, "optics", "store.sqlite");
  pythonSqlite(db, ["PRAGMA user_version = 2"]);
  const before = fs.readFileSync(db);
  const newer = store.openStore({ evidenceRoot: newerDir });
  try {
    assert.equal(newer.reason_code, "NEWER_SCHEMA_REFUSED");
    assert.equal(newer.writes_enabled, false);
    assert.equal(newer.recovery.remediation_code, "NEWER_SCHEMA_REFUSED");
    assert.equal(newer.recovery.recovery_state, "RECOVERY_REQUIRED");
    assert.equal(newer.recovery.integrity_result, "OK");
    assert.equal(newer.put(cleanRecord()).stored, false);
  } finally {
    newer.close();
  }
  assert.equal(fs.readFileSync(db).equals(before), true);
  pythonSqlite(db, [
    "PRAGMA user_version = 1",
    "UPDATE store_meta SET meta_value = '2' WHERE meta_key = 'privacy_generation'",
  ]);
  const beforePrivacy = fs.readFileSync(db);
  const weaker = store.openStore({ evidenceRoot: newerDir, writerPrivacyGeneration: 1 });
  try {
    assert.equal(weaker.reason_code, "WEAKER_WRITER_REFUSED");
    assert.equal(weaker.writes_enabled, false);
    assert.equal(weaker.recovery.remediation_code, "WEAKER_WRITER_REFUSED");
    assert.equal(weaker.put(cleanRecord()).stored, false);
    assert.equal(fs.readFileSync(db).equals(beforePrivacy), true);
  } finally {
    weaker.close();
    fs.rmSync(newerDir, { recursive: true, force: true });
  }

  const faultDir = tempDir("o7-parity-fault-");
  try {
    const faultDb = path.join(faultDir, "optics", "store.sqlite");
    pythonSqlite(faultDb, ["PRAGMA user_version = 0"]);
    const faultBefore = fs.readFileSync(faultDb);
    const failed = store.openStore({ evidenceRoot: faultDir, injectMigrationFault: true });
    try {
      assert.equal(failed.reason_code, "MIGRATION_FAILED");
      assert.equal(failed.writes_enabled, false);
      assert.equal(failed.recovery.remediation_code, "MIGRATION_FAILED");
      assert.equal(failed.recovery.backup_availability, "AVAILABLE");
      assert.equal(failed.recovery.replacement_store_id, null);
    } finally {
      failed.close();
    }
    assert.equal(fs.readFileSync(faultDb).equals(faultBefore), true);
    const backup = path.join(faultDir, "optics", "store.sqlite.backup");
    assert.equal(mode(backup), 0o600);
    assert.equal(fs.readFileSync(backup).equals(faultBefore), true);
    assert.equal(fs.existsSync(path.join(faultDir, "optics", "store.sqlite.new")), false);
  } finally {
    fs.rmSync(faultDir, { recursive: true, force: true });
  }
});

floorTest("python parity: foreign tables stay, empty databases migrate, scope stays partial", () => {
  const foreignDir = tempDir("o7-parity-foreign-");
  try {
    const foreignDb = path.join(foreignDir, "optics", "store.sqlite");
    pythonSqlite(foreignDb, [
      "CREATE TABLE evil (secret TEXT)",
      "INSERT INTO evil (secret) VALUES ('keep')",
    ]);
    const before = fs.readFileSync(foreignDb);
    const failed = store.openStore({ evidenceRoot: foreignDir });
    try {
      assert.equal(failed.reason_code, "MIGRATION_FAILED");
      assert.equal(failed.writes_enabled, false);
    } finally {
      failed.close();
    }
    assert.equal(fs.readFileSync(foreignDb).equals(before), true);
    assert.equal(fs.existsSync(path.join(foreignDir, "optics", "store.sqlite.new")), false);
  } finally {
    fs.rmSync(foreignDir, { recursive: true, force: true });
  }

  const emptyDir = tempDir("o7-parity-empty-");
  const empty = store.openStore({ evidenceRoot: emptyDir });
  try {
    const emptyDb = path.join(emptyDir, "optics", "store.sqlite");
    pythonSqlite(emptyDb, ["PRAGMA user_version = 0"]);
    const original = fs.readFileSync(emptyDb);
    empty.close();
    const migrated = store.openStore({ evidenceRoot: emptyDir });
    try {
      assert.equal(migrated.healthy, true, migrated.reason_code);
      assert.equal(migrated.user_version, 1);
      assert.equal(migrated.put(cleanRecord()).stored, true);
    } finally {
      migrated.close();
    }
    assert.equal(fs.readFileSync(path.join(emptyDir, "optics", "store.sqlite.backup")).equals(original), true);
    assert.equal(fs.statSync(emptyDb).size >= original.length, true);
  } finally {
    fs.rmSync(emptyDir, { recursive: true, force: true });
  }

  const scopeDir = tempDir("o7-parity-scope-");
  const scoped = store.openStore({ evidenceRoot: scopeDir, create: true });
  try {
    assert.equal(scoped.put(cleanRecord()).stored, true);
    const gap = scoped.put(cleanRecord({
      producer_sequence: 1,
      sequence: 1,
      started_at: "2026-07-01T00:00:01.000Z",
      coverage_gap: "EVIDENCED",
    }));
    assert.equal(gap.stored, true, gap.reason_code);
    assert.equal(gap.record.issue_location, "COVERAGE");
    assertOffPage(scoped, "COVERAGE_GAP_IN_SCOPE");
    const run = scoped.put({
      record_type: "run_envelope",
      schema_status: "unstable-pre-1.0",
      schema_version: 0,
      producer: "node_interceptor",
      cli_or_sdk_version: "0.3.24",
      evidence_origin: "LOCAL_OBSERVATION",
      producer_id: "prod_clean_1",
      run_id: "run_clean_1",
      started_at: "2026-07-01T00:00:03.000Z",
      lifecycle: "PARTIAL",
      identity_conflict: "NONE",
    });
    assert.equal(run.stored, true, run.reason_code);
    assert.equal(run.record.lifecycle, "PARTIAL");
  } finally {
    scoped.close();
    fs.rmSync(scopeDir, { recursive: true, force: true });
  }
});

floorTest("python parity: corrupt bodies and unreadable files stay fail-open", () => {
  const dir = tempDir("o7-parity-corrupt-");
  const opened = store.openStore({ evidenceRoot: dir, create: true });
  try {
    assert.equal(opened.put(cleanRecord()).stored, true);
    opened.conn.prepare("UPDATE records SET body_json = ?").run("not-json");
    const again = opened.put(cleanRecord(), { applicationResult: { token: "APP" } });
    assert.equal(again.stored, false);
    assert.equal(again.duplicate, false);
    assert.equal(again.reason_code, "REQUIRED_EVIDENCE_CORRUPT");
    assert.equal(again.application_result.token, "APP");
    assert.equal(opened.conn.prepare("SELECT body_json FROM records").get().body_json, "not-json");
    const followed = opened.put(cleanRecord({
      producer_sequence: 1,
      sequence: 1,
      started_at: "2026-07-01T00:00:01.000Z",
    }), { applicationResult: { token: "APP" } });
    assert.equal(followed.stored, true, followed.reason_code);
  } finally {
    opened.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }

  const hidden = tempDir("o7-parity-mode-");
  const created = store.openStore({ evidenceRoot: hidden, create: true });
  created.close();
  const target = path.join(hidden, "optics", "store.sqlite");
  const original = fs.readFileSync(target);
  const before = fs.statSync(target);
  fs.chmodSync(target, 0);
  const unreadable = store.openStore({ evidenceRoot: hidden });
  try {
    assert.equal(unreadable.reason_code, "INTEGRITY_FAILED");
    assert.equal(unreadable.integrity, "UNREADABLE");
    assert.equal(unreadable.recovery_state, "STOPPED_PRESERVED");
    assert.equal(unreadable.file_created, false);
    assert.equal(unreadable.recovery.integrity_result, "UNREADABLE");
    assert.equal(unreadable.recovery.preserved_bytes_sha256, null);
    assert.equal(mode(target), 0);
    assert.equal(fs.statSync(target).ino, before.ino);
    const page = unreadable.query(window());
    assert.equal(page.completeness, "UNAVAILABLE");
    const salvaged = unreadable.salvage();
    assert.notEqual(salvaged.completeness, "COMPLETE");
    assert.deepEqual(salvaged.rows, []);
    fs.chmodSync(target, 0o600);
    assert.equal(fs.readFileSync(target).equals(original), true);
  } finally {
    unreadable.close();
    fs.chmodSync(target, 0o600);
    fs.rmSync(hidden, { recursive: true, force: true });
  }
});

floorTest("python parity: an unsearchable optics directory uses the fallback envelope", () => {
  const dir = tempDir("o7-parity-optics-");
  const created = store.openStore({ evidenceRoot: dir, create: true });
  assert.equal(created.put(cleanRecord()).stored, true);
  created.close();
  const optics = path.join(dir, "optics");
  const target = path.join(optics, "store.sqlite");
  const original = fs.readFileSync(target);
  const before = fs.statSync(target);
  fs.chmodSync(optics, 0);
  const opened = store.openStore({ evidenceRoot: dir });
  try {
    assert.equal(opened.reason_code, "INTEGRITY_FAILED");
    assert.equal(opened.integrity, "UNREADABLE");
    assert.equal(opened.recovery_state, "STOPPED_PRESERVED");
    assert.equal(opened.recovery.safe_store_id, "store-id-unreadable");
    assert.equal(path.basename(path.dirname(opened.recovery_path)), "optics-recovery");
    assert.equal(path.basename(opened.recovery_path), "store-id-unreadable.recovery.json");
    assert.equal(mode(opened.recovery_path), 0o600);
    assert.equal(mode(path.dirname(opened.recovery_path)), 0o700);
    assert.equal(opened.query(window()).completeness, "UNAVAILABLE");
    const salvaged = opened.salvage();
    assert.notEqual(salvaged.completeness, "COMPLETE");
    const again = store.openStore({ evidenceRoot: dir, create: true });
    try {
      assert.equal(again.recovery_state, "STOPPED_PRESERVED");
      assert.equal(again.file_created, false);
      assert.equal(again.writes_enabled, false);
    } finally {
      again.close();
    }
  } finally {
    opened.close();
    fs.chmodSync(optics, 0o700);
  }
  assert.equal(fs.statSync(target).ino, before.ino);
  assert.equal(fs.readFileSync(target).equals(original), true);
  assert.equal(fs.existsSync(path.join(optics, "recovery")), false);
  fs.rmSync(dir, { recursive: true, force: true });
});
