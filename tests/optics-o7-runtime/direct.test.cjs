"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { test: privateTreeSkipTest } = require("node:test");

if (!fs.existsSync(path.resolve(__dirname, "../../docs/internal"))) {
  privateTreeSkipTest("docs/internal", { skip: "PRIVATE_TREE_REMOVED_FROM_PUBLIC_TIP" }, () => {});
} else {
"use strict";

const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const store = require("../../packages/optics-operational-store/src/index.cjs");
const gate = require("../../packages/optics-operational-store/src/runtime-gate.cjs");

const ROOT = path.resolve(__dirname, "../..");
const PACKAGE = path.join(ROOT, "packages/optics-operational-store/src");
const CORPUS = path.join(ROOT, "tests/optics-evidence-contract/corpus.json");
const SUPPORTED = gate.selectedBindingSupported(process.versions.node);
const FLOOR_SKIP = SUPPORTED ? false : "below node:sqlite@24.15.0";

function read(rel) {
  return fs.readFileSync(path.join(ROOT, rel), "utf8");
}

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

test("the version gate admits only Node.js 24.15.0+ and Node.js 26", () => {
  const cases = [
    ["18.20.4", false],
    ["20.18.1", false],
    ["22.14.0", false],
    ["22.16.0", false],
    ["22.23.3", false],
    ["24.0.0", false],
    ["24.14.9", false],
    ["24.15.0", true],
    ["24.15.1", true],
    ["24.19.0", true],
    ["25.7.0", false],
    ["26.0.0", true],
    ["26.8.1", true],
    ["27.0.0", false],
    ["v24.15.0", true],
    ["", false],
    ["24.15", false],
  ];
  for (const [version, expected] of cases) {
    assert.equal(gate.selectedBindingSupported(version), expected, version);
  }
});

test("the selected module is required in one session file and the fallback package is absent", () => {
  const files = fs.readdirSync(PACKAGE).filter((name) => name.endsWith(".cjs"));
  const bindingCall = "require(" + '"node:sqlite"' + ")";
  const hits = [];
  for (const name of files) {
    const text = fs.readFileSync(path.join(PACKAGE, name), "utf8");
    assert.equal(text.includes("better-sqlite"), false, name);
    assert.equal(/require\(\s*["']sqlite3["']\)/.test(text), false, name);
    if (text.includes(bindingCall)) hits.push(name);
  }
  assert.deepEqual(hits, ["node-sqlite-session.cjs"]);
  const session = fs.readFileSync(path.join(PACKAGE, "node-sqlite-session.cjs"), "utf8");
  const runtime = fs.readFileSync(path.join(PACKAGE, "runtime.cjs"), "utf8");
  assert.match(session, /readOnly:\s*true/);
  assert.match(session, /timeout:\s*0/);
  assert.match(session, /enableForeignKeyConstraints:\s*false/);
  assert.match(session, /allowExtension:\s*false/);
  assert.match(session, /PRAGMA busy_timeout/);
  assert.match(session, /PRAGMA foreign_keys/);
  assert.equal(session.includes("allowExtension: true"), false);
  assert.match(runtime, /PRAGMA journal_mode=WAL/);
  assert.match(runtime, /BEGIN IMMEDIATE/);
  assert.match(runtime, /exec\("COMMIT"\)/);
  assert.match(runtime, /exec\("ROLLBACK"\)/);
  assert.match(runtime, /PRAGMA user_version/);
  assert.match(runtime, /PRAGMA integrity_check/);
  assert.match(runtime, /ON CONFLICT\(meta_key\)/);
  for (const banned of ["STRICT", "loadExtension", "createSession", "applyChangeset", "createTagStore", "setAuthorizer", ".backup(", "ATTACH", ".function(", ".aggregate("]) {
    assert.equal(session.includes(banned), false, banned);
    assert.equal(runtime.includes(banned), false, banned);
  }
  const pkg = JSON.parse(read("packages/optics-operational-store/package.json"));
  assert.equal(pkg.private, true);
  assert.equal(pkg.version, "0.0.0-unstable-pre-1.0");
  assert.equal(pkg.engines.node, ">=24.15.0");
  for (const field of ["dependencies", "devDependencies", "optionalDependencies", "peerDependencies"]) {
    assert.equal(Object.hasOwn(pkg, field), false, field);
  }
});

test("frozen releases, the closed gate, and the integration record stay honest", () => {
  assert.equal(JSON.parse(read("packages/vantio-cli/package.json")).version, "0.3.24");
  assert.equal(JSON.parse(read("packages/vantio-cli/package.json")).engines.node, ">=18.3.0");
  assert.equal(JSON.parse(read("packages/vantio-agent-sdk/package.json")).version, "0.2.4");
  assert.match(read("packages/vantio-agent-sdk-py/pyproject.toml"), /^version = "3.1.0"$/m);
  assert.match(read("docs/architecture/optics-foundation/09-IMPLEMENTATION-GATES.md"), /\| 8 \| Implementation Force \|.*\| \*\*Closed\. Not started\*\* \|/);
  assert.match(read("docs/architecture/optics-foundation/08-ARCHITECTURE-DECISION-PACK.md"), /9\. Node SQLite binding\. Not selected\./);
  const record = JSON.parse(read("docs/internal/optics-o7/RUNTIME-INTEGRATION.json"));
  assert.equal(record.classification, "O7_RUNTIME_INTEGRATION_READY_FOR_COUNCIL");
  assert.equal(store.CLASSIFICATION, record.classification);
  assert.equal(record.selected_binding_at_version, "node:sqlite@24.15.0");
  assert.equal(record.fallback_installed, false);
  assert.equal(record.load_fallback_on_failure, false);
  assert.equal(record.honesty.evidence_tier, "UNSET");
  assert.equal(record.honesty.gate_8, "CLOSED");
  assert.equal(record.honesty.external_proof, "NOT_CLAIMED");
  assert.equal(record.honesty.runtime_proof, false);
  assert.equal(record.honesty.default_write_path, false);
  assert.equal(record.below_floor_reason, "NODE_BINDING_CANNOT_LOAD");
  assert.equal(record.below_floor_creates_file, false);
  const manifest = JSON.parse(read("docs/planning/optics-o7-store/STORE-MANIFEST.json"));
  assert.equal(manifest.founder_decision_9, "UNRESOLVED");
  assert.equal(manifest.node_binding, "UNSELECTED");
});

test("writer flags without create do not create a file", () => {
  const dir = tempDir("o7-flags-");
  try {
    const opened = store.openStore({
      evidenceRoot: dir,
      activate: true,
      emit: true,
      migrate: true,
      publish: true,
      seal: true,
      sqlite: true,
      write: true,
    });
    assert.equal(opened.file_created, false);
    assert.equal(opened.default_write_path, false);
    assert.equal(fs.existsSync(path.join(dir, "optics", "store.sqlite")), false);
    if (!SUPPORTED) assert.equal(opened.reason_code, "NODE_BINDING_CANNOT_LOAD");
    else assert.equal(opened.reason_code, "STORE_ABSENT");
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("an evidence-root symlink is not followed", () => {
  const dir = tempDir("o7-root-link-");
  const outside = path.join(dir, "outside");
  const link = path.join(dir, "link");
  fs.mkdirSync(outside);
  fs.symlinkSync(outside, link);
  try {
    const opened = store.openStore({ evidenceRoot: link, create: true });
    assert.equal(opened.file_created, false);
    assert.equal(fs.existsSync(path.join(outside, "optics", "store.sqlite")), false);
    assert.equal(fs.readdirSync(outside).length, 0);
    if (SUPPORTED) assert.equal(opened.reason_code, "SYMLINK_REFUSED");
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("opening the store does not load node:sqlite below the floor", () => {
  const dir = tempDir("o7-load-");
  const indexPath = path.join(PACKAGE, "index.cjs");
  const sessionPath = path.join(PACKAGE, "node-sqlite-session.cjs");
  const script = `
    const fs = require("node:fs");
    const store = require(${JSON.stringify(indexPath)});
    const session = ${JSON.stringify(sessionPath)};
    const opened = store.openStore({ evidenceRoot: ${JSON.stringify(dir)}, create: true, sqlite: true });
    const loadedSession = Object.prototype.hasOwnProperty.call(require.cache, session);
    const loadedBuiltin = (process.moduleLoadList || []).some((item) => {
      const text = String(item);
      return text.includes("node:sqlite") || text === "NativeModule sqlite" || text === "Internal Binding sqlite";
    });
    if (typeof opened.close === "function") opened.close();
    process.stdout.write(JSON.stringify({
      reason: opened.reason_code,
      created: opened.file_created,
      exists: fs.existsSync(${JSON.stringify(path.join(dir, "optics", "store.sqlite"))}),
      loadedSession,
      loadedBuiltin,
      continues: opened.application_continues,
    }));
  `;
  try {
    const child = spawnSync(process.execPath, ["-e", script], { encoding: "utf8" });
    assert.equal(child.status, 0, child.stderr);
    const body = JSON.parse(child.stdout);
    assert.equal(body.continues, true);
    if (SUPPORTED) {
      assert.equal(body.reason, "OK");
      assert.equal(body.exists, true);
      assert.equal(body.loadedBuiltin, true);
    } else {
      assert.equal(body.reason, "NODE_BINDING_CANNOT_LOAD");
      assert.equal(body.created, false);
      assert.equal(body.exists, false);
      assert.equal(body.loadedSession, false);
      assert.equal(body.loadedBuiltin, false);
    }
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

function runPython(root, action, extra) {
  const script = `
import json, os, sys
sys.path.insert(0, ${JSON.stringify(path.join(ROOT, "packages/optics-operational-store/src"))})
from optics_operational_store.store import open_store
root = os.environ["O7_ROOT"]
action = os.environ["O7_ACTION"]
if action == "create":
    handle = open_store(root, create=True)
    record = json.loads(os.environ["O7_RECORD"])
    stored = handle.put(record)
    print(json.dumps({"stored": stored["stored"], "reason": stored["reason_code"], "id": handle.safe_store_id}))
    handle.close()
elif action == "read":
    handle = open_store(root)
    fetched = handle.get(event_id=os.environ["O7_EVENT"])
    mode = None
    version = None
    if handle.conn is not None:
        mode = handle.conn.execute("PRAGMA journal_mode").fetchone()[0]
        version = handle.conn.execute("PRAGMA user_version").fetchone()[0]
    print(json.dumps({
        "reason": handle.reason_code,
        "opened": handle.opened,
        "count": len(fetched["records"]),
        "host": None if not fetched["records"] else fetched["records"][0].get("destination_host"),
        "mode": None if mode is None else str(mode).lower(),
        "version": version,
    }))
    handle.close()
`;
  return spawnSync("python3", ["-c", script], {
    encoding: "utf8",
    env: {
      ...process.env,
      O7_ROOT: root,
      O7_ACTION: action,
      O7_RECORD: extra && extra.record ? JSON.stringify(extra.record) : "",
      O7_EVENT: extra && extra.event ? extra.event : "",
    },
  });
}

test("below the floor, node open leaves a python store unchanged", { skip: SUPPORTED ? "supported run uses the shared-file test" : false }, () => {
  const dir = tempDir("o7-py-freeze-");
  try {
    const created = runPython(dir, "create", { record: cleanRecord() });
    assert.equal(created.status, 0, created.stderr);
    const storePath = path.join(dir, "optics", "store.sqlite");
    const before = crypto.createHash("sha256").update(fs.readFileSync(storePath)).digest("hex");
    const opened = store.openStore({ evidenceRoot: dir, create: true });
    assert.equal(opened.reason_code, "NODE_BINDING_CANNOT_LOAD");
    assert.equal(opened.file_created, false);
    const after = crypto.createHash("sha256").update(fs.readFileSync(storePath)).digest("hex");
    assert.equal(after, before);
    const readBack = runPython(dir, "read", { event: "e.12.prod_clean_1.0" });
    assert.equal(readBack.status, 0, readBack.stderr);
    const body = JSON.parse(readBack.stdout);
    assert.equal(body.count, 1);
    assert.equal(body.host, "api.example.com");
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

floorTest("a supported open creates a wal file python can read", () => {
  const dir = tempDir("o7-floor-create-");
  const opened = store.openStore({ evidenceRoot: dir, create: true });
  try {
    assert.equal(opened.reason_code, "OK");
    assert.equal(opened.file_created, true);
    assert.equal(opened.writes_enabled, true);
    assert.equal(opened.default_write_path, false);
    assert.equal(opened.evidence_tier, "UNSET");
    assert.equal(opened.user_version, 1);
    const storePath = path.join(dir, "optics", "store.sqlite");
    assert.equal(fs.statSync(storePath).mode & 0o777, 0o600);
    assert.equal(fs.statSync(path.join(dir, "optics")).mode & 0o777, 0o700);
    const busy = opened.conn.prepare("PRAGMA busy_timeout").get();
    const foreignKeys = opened.conn.prepare("PRAGMA foreign_keys").get();
    const journal = opened.conn.prepare("PRAGMA journal_mode").get();
    assert.equal(Object.values(busy)[0], 0);
    assert.equal(Object.values(foreignKeys)[0], 0);
    assert.equal(String(Object.values(journal)[0]).toLowerCase(), "wal");
    const master = opened.conn.prepare("SELECT sql FROM sqlite_master").all().map((row) => row.sql || "").join("\n");
    assert.equal(/STRICT/i.test(master), false);
    assert.equal(/FOREIGN KEY/i.test(master), false);
    const stored = opened.put(cleanRecord(), { applicationResult: { token: "APP" } });
    assert.equal(stored.stored, true);
    assert.equal(stored.reason_code, "OK");
    assert.equal(stored.application_result.token, "APP");
    assert.equal(stored.record.schema_version, 0);
    opened.close();
    const readBack = runPython(dir, "read", { event: "e.12.prod_clean_1.0" });
    assert.equal(readBack.status, 0, readBack.stderr);
    const body = JSON.parse(readBack.stdout);
    assert.equal(body.opened, true);
    assert.equal(body.count, 1);
    assert.equal(body.host, "api.example.com");
    assert.equal(body.mode, "wal");
    assert.equal(body.version, 1);
  } finally {
    if (opened && opened.conn) opened.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

floorTest("node reads a python-created wal file and does not replace it", () => {
  const dir = tempDir("o7-floor-read-");
  try {
    const created = runPython(dir, "create", { record: cleanRecord() });
    assert.equal(created.status, 0, created.stderr);
    const opened = store.openStore({ evidenceRoot: dir });
    try {
      assert.equal(opened.reason_code, "OK");
      assert.equal(opened.file_created, false);
      const fetched = opened.get({ event_id: "e.12.prod_clean_1.0" });
      assert.equal(fetched.records.length, 1);
      assert.equal(fetched.records[0].destination_host, "api.example.com");
      const second = opened.put(cleanRecord({
        event_id: "e.12.prod_clean_1.1",
        producer_sequence: 1,
        sequence: 1,
        started_at: "2026-07-01T00:00:01.000Z",
      }));
      assert.equal(second.stored, true);
    } finally {
      opened.close();
    }
    const readBack = runPython(dir, "read", { event: "e.12.prod_clean_1.1" });
    assert.equal(readBack.status, 0, readBack.stderr);
    const body = JSON.parse(readBack.stdout);
    assert.equal(body.count, 1);
    assert.equal(body.version, 1);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

floorTest("caller sql, a missing read-only path, rollback, and a torn file stay fail-open", () => {
  const dir = tempDir("o7-floor-guard-");
  try {
    const missing = store.openStore({ evidenceRoot: path.join(dir, "missing") });
    assert.equal(missing.reason_code, "STORE_ABSENT");
    assert.equal(missing.file_created, false);
    assert.equal(fs.existsSync(path.join(dir, "missing")), false);
    const createMissing = store.openStore({ evidenceRoot: path.join(dir, "missing-root"), create: true });
    assert.equal(createMissing.reason_code, "STORE_ROOT_ABSENT");
    assert.equal(createMissing.file_created, false);
    assert.equal(fs.existsSync(path.join(dir, "missing-root")), false);
    const opened = store.openStore({ evidenceRoot: dir, create: true });
    assert.equal(opened.reason_code, "OK");
    const rejected = opened.put("DROP TABLE records", { applicationResult: { token: "APP" } });
    assert.equal(rejected.reason_code, "SQL_REJECTED");
    assert.equal(rejected.stored, false);
    const page = opened.query({ sql: "SELECT * FROM records" });
    assert.equal(page.reason_code, "SQL_REJECTED");
    assert.equal(page.completeness, "UNAVAILABLE");
    const injected = opened.query({
      time_start: "2026-07-01T00:00:00.000Z",
      time_end: "2026-07-01T01:00:00.000Z",
      destination_host: "' OR '1'='1",
    });
    assert.equal(injected.matchingRecords, 0);
    opened.conn.exec("BEGIN IMMEDIATE");
    opened.conn.prepare("INSERT INTO drops (dropped_at, drop_count) VALUES (?, ?)").run("2026-07-01T00:00:00.000Z", 1);
    opened.conn.exec("ROLLBACK");
    const drops = opened.conn.prepare("SELECT COUNT(*) AS n FROM drops").get();
    assert.equal(Number(drops.n), 0);
    opened.close();
    const tornDir = tempDir("o7-floor-torn-");
    try {
      const optics = path.join(tornDir, "optics");
      fs.mkdirSync(optics);
      const target = path.join(optics, "store.sqlite");
      const original = Buffer.from("not-a-database-torn-bytes");
      fs.writeFileSync(target, original);
      const torn = store.openStore({ evidenceRoot: tornDir, create: true });
      assert.equal(torn.reason_code, "INTEGRITY_FAILED");
      assert.equal(torn.writes_enabled, false);
      assert.equal(torn.recovery_state, "STOPPED_PRESERVED");
      assert.equal(fs.readFileSync(target).equals(original), true);
      assert.equal(fs.existsSync(path.join(optics, "store.sqlite.new")), false);
      const salvaged = torn.salvage();
      assert.notEqual(salvaged.completeness, "COMPLETE");
      assert.deepEqual(salvaged.rows, []);
      assert.equal(fs.readFileSync(target).equals(original), true);
    } finally {
      fs.rmSync(tornDir, { recursive: true, force: true });
    }
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

floorTest("a lock does not wait and a symlink store path is refused", () => {
  const dir = tempDir("o7-floor-lock-");
  const holder = store.openStore({ evidenceRoot: dir, create: true });
  const other = store.openStore({ evidenceRoot: dir });
  try {
    holder.conn.exec("BEGIN IMMEDIATE");
    const started = Date.now();
    const result = other.put(cleanRecord(), { applicationResult: { token: "APP" } });
    assert.equal(result.stored, false);
    assert.equal(result.reason_code, "WRITE_STOPPED");
    assert.equal(result.application_continues, true);
    assert.equal(result.application_result.token, "APP");
    assert.equal(JSON.stringify(result).toLowerCase().includes("locked"), false);
    assert.ok(Date.now() - started < 1000);
    holder.conn.exec("ROLLBACK");
  } finally {
    other.close();
    holder.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
  const linkDir = tempDir("o7-floor-symlink-");
  const outside = path.join(linkDir, "outside");
  const evidence = path.join(linkDir, "evidence");
  fs.mkdirSync(outside);
  fs.mkdirSync(evidence);
  fs.symlinkSync(outside, path.join(evidence, "optics"));
  try {
    const refused = store.openStore({ evidenceRoot: evidence, create: true });
    assert.equal(refused.reason_code, "SYMLINK_REFUSED");
    assert.equal(fs.existsSync(path.join(outside, "store.sqlite")), false);
    assert.equal(fs.readdirSync(outside).length, 0);
  } finally {
    fs.rmSync(linkDir, { recursive: true, force: true });
  }
});
}
