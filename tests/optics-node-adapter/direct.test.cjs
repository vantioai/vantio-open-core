"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const { canonicalJson } = require("../../packages/optics-evidence-contract/src/canonical.cjs");
const { adaptFixture } = require("../../packages/optics-node-adapter/src/adapt.cjs");
const fixtures = require("../../packages/optics-record-vocabulary/fixtures/conformance-fixtures.json");

function hasOwn(object, key) {
  return Object.prototype.hasOwnProperty.call(object, key);
}

function same(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function valuesFor(result, key) {
  const values = [];
  function take(object) {
    if (object && hasOwn(object, key)) values.push(object[key]);
  }
  take(result.record);
  for (const event of result.events) take(event.record);
  if (key === "reader_origin_label") {
    if (result.reader_origin_label) values.push(result.reader_origin_label);
    for (const event of result.events) {
      if (event.reader_origin_label) values.push(event.reader_origin_label);
    }
  }
  return values;
}

function originMatches(result, expected) {
  if (expected == null) return true;
  if (result.reader_origin_label === expected) return true;
  if (result.record && result.record.evidence_origin === expected) return true;
  for (const event of result.events) {
    if (event.reader_origin_label === expected) return true;
    if (event.record && event.record.evidence_origin === expected) return true;
  }
  return false;
}

function score(fixture, result) {
  const problems = [];
  if (result.writes_live_run_directory !== false) problems.push("writes");
  if (result.live_emission !== false) problems.push("emission");
  if (result.writer_activated !== false) problems.push("writer");
  if (result.stable_schema !== false) problems.push("stable schema");
  if (result.schema_version !== 0) problems.push("schema_version");
  if (result.schema_status !== "unstable-pre-1.0") problems.push("schema_status");
  if (result.live_writer_modified !== false) problems.push("live writer modified");
  if (result.record_emitted !== fixture.record_emitted) {
    problems.push("record_emitted " + String(result.record_emitted));
  }
  if (!originMatches(result, fixture.evidence_origin)) problems.push("origin " + String(fixture.evidence_origin));
  if (result.optics_health === "SUCCESS") problems.push("optics health SUCCESS");
  if (fixture.expected_canonical) {
    for (const [key, value] of Object.entries(fixture.expected_canonical)) {
      const found = valuesFor(result, key);
      if (!found.some((item) => same(item, value))) {
        problems.push(key + " expected " + JSON.stringify(value) + " found " + JSON.stringify(found));
      }
    }
  } else if (result.record_emitted) {
    problems.push("emitted without an expected canonical record");
  }
  if (Array.isArray(fixture.expected_events)) {
    if (result.events.length !== fixture.expected_events.length) {
      problems.push("event count " + String(result.events.length));
    }
    for (let i = 0; i < fixture.expected_events.length; i += 1) {
      const expected = fixture.expected_events[i];
      const record = result.events[i] && result.events[i].record;
      for (const [key, value] of Object.entries(expected)) {
        if (!record || !same(record[key], value)) {
          problems.push("event " + i + " " + key + " found " + JSON.stringify(record && record[key]));
        }
      }
    }
  }
  const blob = JSON.stringify({ events: result.events, record: result.record });
  for (const name of fixture.fields_not_promoted) {
    if (blob.includes(JSON.stringify(name))) problems.push("promoted " + name);
  }
  for (const item of fixture.prohibited_optimistic_interpretations) {
    const path = item.path.startsWith("canonical.") ? item.path.slice("canonical.".length) : item.path;
    if (path.startsWith("reading.")) {
      if (path === "reading.optics_health" && result.optics_health === item.forbidden_value) {
        problems.push("reading " + result.optics_health);
      }
      continue;
    }
    if (valuesFor(result, path).some((value) => same(value, item.forbidden_value))) {
      problems.push("prohibited " + path + "=" + JSON.stringify(item.forbidden_value));
    }
  }
  if (result.record_emitted && result.diagnostics.unicode_profile_id !== "PKG01-UCD-16.0.0") {
    problems.push("unicode profile");
  }
  if (fixture.input_parse === "MALFORMED_JSON" || fixture.input_parse === "UNREADABLE") {
    if (result.optics_health !== "OPTICS_ERROR") problems.push("optics " + result.optics_health);
    if (result.optics_health === "NOT_OBSERVED") problems.push("corrupt as NOT_OBSERVED");
  }
  if (fixture.input_parse === "ABSENT_FILE" && result.optics_health === "NOT_OBSERVED") {
    problems.push("absent file as NOT_OBSERVED");
  }
  return problems;
}

test("shared Unit A fixtures score on the inert Node adapter", () => {
  const failures = [];
  for (const fixture of fixtures) {
    const result = adaptFixture(fixture);
    const problems = score(fixture, result);
    if (problems.length > 0) failures.push(fixture.id + ": " + problems.join("; "));
  }
  assert.deepEqual(failures, []);
});

test("repeated adaptation of one fixture is the same canonical bytes", () => {
  const fixture = fixtures.find((item) => item.id === "cli-0-3-24");
  const left = adaptFixture(fixture);
  const right = adaptFixture(fixture);
  assert.equal(canonicalJson(left.record), canonicalJson(right.record));
  assert.equal(canonicalJson(left.events), canonicalJson(right.events));
});

test("absent, null, unknown, and byte distinctions stay apart", () => {
  const byId = Object.fromEntries(fixtures.map((fixture) => [fixture.id, adaptFixture(fixture)]));
  const missing = byId["bytes-missing"].events[0].record;
  const legacy = byId["legacy-bytes-zero"].events[0].record;
  const explicit = byId["explicit-response-bytes-zero"].events[0].record;
  assert.equal(hasOwn(missing, "response_bytes"), false);
  assert.equal(legacy.response_bytes, null);
  assert.equal(explicit.response_bytes, 0);
  assert.equal(byId["missing-status"].events[0].record.optics_status, "UNAVAILABLE");
  assert.equal(hasOwn(byId["missing-status"].events[0].record, "http_status"), false);
  assert.equal(hasOwn(byId["missing-action"].events[0].record, "action"), false);
  assert.equal(byId["unknown-status"].optics_health, "UNAVAILABLE");
  assert.equal(byId["unknown-status"].optimistic_default_forbidden, true);
  assert.equal(byId["no-file"].optics_health, "UNAVAILABLE");
  assert.equal(byId["cli-empty-call-file"].optics_health, "NOT_OBSERVED");
  assert.equal(byId["cli-empty-call-file"].record.optics_status, "NOT_OBSERVED");
  assert.equal(byId["corrupt-record"].optics_health, "OPTICS_ERROR");
  assert.equal(byId["corrupt-record"].record, null);
  assert.equal(byId["unreadable-record"].optics_health, "OPTICS_ERROR");
});

test("status dimensions and origin stay on their own fields", () => {
  const http500 = adaptFixture(fixtures.find((item) => item.id === "provider-http-error"));
  const event = http500.events[0].record;
  assert.equal(event.http_status, 500);
  assert.equal(event.application_status, "APPLICATION_ERROR");
  assert.equal(event.optics_status, "UNAVAILABLE");
  assert.equal(event.issue_location, "PROVIDER_INTERACTION");
  assert.equal(hasOwn(event, "ok"), false);

  const partial = adaptFixture(fixtures.find((item) => item.id === "partial-run"));
  assert.equal(partial.record.lifecycle, "PARTIAL");
  assert.equal(partial.events[0].record.application_status, "SUCCESS");
  assert.equal(partial.events[1].record.application_status, "APPLICATION_ERROR");
  assert.equal(partial.events[0].record.optics_status, "UNAVAILABLE");
  assert.notEqual(partial.record.application_status, "PARTIAL");

  const imported = adaptFixture(fixtures.find((item) => item.id === "imported-evidence"));
  assert.equal(imported.record.evidence_origin, "IMPORTED");
  assert.equal(imported.record.original_evidence_origin, "LEGACY_UNMARKED");
  assert.notEqual(imported.record.evidence_origin, "LOCAL_OBSERVATION");

  const inherited = adaptFixture(fixtures.find((item) => item.id === "inherited-trace"));
  assert.equal(inherited.record.run_id, "0xinherited");
  assert.equal(inherited.record.trace_id_basis, "ASSERTED_CONTEXT");
  assert.equal(inherited.record.optics_status, "UNAVAILABLE");
  assert.equal(hasOwn(inherited.record, "trace_id"), false);

  const witnessed = adaptFixture(fixtures.find((item) => item.id === "witnessed-trace"));
  assert.equal(witnessed.record.trace_id_basis, "OPTICS_GENERATED");
  assert.equal(hasOwn(witnessed.record, "optics_trace_witness"), false);
  assert.equal(JSON.stringify(witnessed).includes("PKG01_OPTICS_GENERATED_WITNESS"), false);
});
