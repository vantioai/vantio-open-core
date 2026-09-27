"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const ROOT = path.resolve(__dirname, "../..");

function readJson(rel) {
  return JSON.parse(fs.readFileSync(path.join(ROOT, rel), "utf8"));
}

const catalog = readJson("docs/planning/shared-health-vocabulary/HEALTH-VOCABULARY.json");
const matrix = readJson("docs/planning/shared-health-vocabulary/COLLISION-MATRIX.json");

function spellingIndex() {
  const index = new Map();
  function add(field, values) {
    for (const value of values) {
      if (!index.has(value)) index.set(value, new Set());
      index.get(value).add(field);
    }
  }
  add("subject", catalog.subjects);
  add("freshness", catalog.freshness.emitted_values);
  for (const [name, spec] of Object.entries(catalog.fields)) add(name, spec.values);
  return index;
}

function allowedField(name) {
  if (Object.hasOwn(catalog.fields, name)) return true;
  if (name === "subject" || name === "freshness") return true;
  if (catalog.absent_fields.includes(name)) return true;
  if (matrix.absent_fields.includes(name)) return true;
  if (matrix.rule_names.includes(name)) return true;
  return false;
}

test("section 2 rows are present and not collapsed", () => {
  assert.equal(matrix.collapsed, false);
  assert.equal(matrix.preserved_section_2, true);
  const required = ["BLOCKED", "OBSERVED", "ALLOWED", "PARTIAL", "SUCCESS", "UNKNOWN_FAMILY", "CURRENT"];
  for (const id of required) {
    const row = matrix.rows.find((item) => item.id === id);
    assert.ok(row, id);
    assert.equal(row.origin, "WS3_SECTION_2", id);
  }
  const current = matrix.rows.find((item) => item.id === "CURRENT");
  assert.equal(current.emitted, false);
  assert.deepEqual(current.may_hold, []);
  assert.equal(current.must_not_hold.some((item) => item.field === "freshness"), true);
  assert.ok(current.must_not_hold.some((item) => String(item.when).includes("60")));
});

test("shared spellings name every field that holds them", () => {
  const index = spellingIndex();
  for (const spelling of catalog.freshness.reserved_not_emitted) {
    assert.equal(index.has(spelling), false, spelling);
    const row = matrix.rows.find((item) => item.spellings.includes(spelling));
    assert.ok(row, spelling);
    assert.equal(row.emitted, false, spelling);
    assert.equal(row.may_hold.length, 0, spelling);
  }
  for (const [spelling, fields] of index) {
    if (fields.size < 2) continue;
    const rows = matrix.rows.filter((item) => item.spellings.includes(spelling));
    assert.ok(rows.length > 0, spelling);
    const held = new Set();
    for (const row of rows) {
      for (const entry of row.may_hold) held.add(entry.field);
    }
    for (const field of fields) {
      assert.equal(held.has(field), true, `${spelling} missing ${field}`);
    }
  }
});

test("collision fields exist and a row does not both allow and ban the same field", () => {
  const ids = new Set();
  for (const row of matrix.rows) {
    assert.equal(ids.has(row.id), false, row.id);
    ids.add(row.id);
    const may = new Set(row.may_hold.map((entry) => entry.field));
    const banned = new Set(row.must_not_hold.map((entry) => entry.field));
    for (const field of may) assert.equal(allowedField(field), true, `${row.id} may ${field}`);
    for (const field of banned) assert.equal(allowedField(field), true, `${row.id} ban ${field}`);
    for (const field of may) assert.equal(banned.has(field), false, `${row.id} ${field}`);
  }
  for (const name of catalog.absent_fields) {
    assert.equal(Object.hasOwn(catalog.fields, name), false, name);
  }
});

test("P24 named gaps point at collision rows", () => {
  for (const gap of matrix.p24_named_gaps) {
    if (gap.not_a_token) {
      assert.equal(gap.row_id, null);
      continue;
    }
    assert.ok(matrix.rows.some((row) => row.id === gap.row_id), gap.gap);
  }
  const worm = matrix.rows.find((row) => row.id === "LOCAL_NDJSON_NOT_WORM");
  assert.equal(worm.emitted, false);
  assert.equal(worm.spellings.includes("WORM"), true);
});

test("catalog files do not carry a live probe command", () => {
  const home = path.join(ROOT, "docs/planning/shared-health-vocabulary");
  for (const name of fs.readdirSync(home)) {
    const text = fs.readFileSync(path.join(home, name), "utf8");
    assert.equal(text.includes("bpftool"), false, name);
    assert.equal(text.includes("kubectl apply"), false, name);
    assert.equal(text.includes("Sight Loop"), false, name);
    assert.equal(text.includes("Shadow AI"), false, name);
  }
});
