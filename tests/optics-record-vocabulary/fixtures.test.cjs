"use strict";

const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const path = require("node:path");
const test = require("node:test");

const {
  canonicalJson,
  evaluateFixture,
  evaluateFixtures,
  loadFixtures,
  loadVocabulary,
} = require("../../packages/optics-record-vocabulary/src/index.cjs");
const { requiredProtectiveRules } = require("../../packages/optics-record-vocabulary/src/evaluate-fixture.cjs");
const { REQUIRED_SCENARIOS } = require("../../packages/optics-record-vocabulary/src/fixture-contract.cjs");
const { fixtures: authoredFixtures } = require("../../packages/optics-record-vocabulary/tools/emit-fixtures.cjs");

const PYTHON = path.join(__dirname, "canonical_json.py");

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

test("fixtures match the authored list and cover the force scenarios", () => {
  const loaded = loadFixtures();
  assert.equal(canonicalJson(loaded), canonicalJson(authoredFixtures));
  assert.equal(loaded.length, 34);
  const scenarios = new Set(loaded.map((fixture) => fixture.scenario));
  for (const scenario of REQUIRED_SCENARIOS) assert.equal(scenarios.has(scenario), true, scenario);
  for (const fixture of loaded) {
    assert.equal(fixture.writes_live_run_directory, false);
    assert.equal(fixture.achievement, "NOT_SHIPPED");
    assert.equal(fixture.stable_schema, false);
  }
});

test("fixture evaluation is deterministic and does not mutate the caller", () => {
  const vocabulary = loadVocabulary();
  const fixtures = loadFixtures();
  const first = evaluateFixtures(fixtures, vocabulary);
  const second = evaluateFixtures(fixtures, vocabulary);
  assert.equal(first.ok, true, first.errors.join("\n"));
  assert.equal(canonicalJson(first.comparisons), canonicalJson(second.comparisons));

  const raw = clone(fixtures[0]);
  raw.touched = false;
  const before = canonicalJson(raw);
  const result = evaluateFixture(raw, vocabulary);
  assert.equal(result.ok, false);
  assert.equal(canonicalJson(raw), before);
});

test("cyclic input stops at a bounded error", () => {
  const vocabulary = loadVocabulary();
  const cyclic = { id: "cyclic" };
  cyclic.self = cyclic;
  const result = evaluateFixture(cyclic, vocabulary);
  assert.equal(result.ok, false);
  assert.deepEqual(result.errors, ["CYCLE_REJECTED"]);
  assert.equal(result.comparison, null);
});

test("a bare record is not converted", () => {
  const vocabulary = loadVocabulary();
  const result = evaluateFixture({ hostname: "api.example.com", status: 200, opticsStatus: "SUCCESS" }, vocabulary);
  assert.equal(result.ok, false);
  assert.equal(result.comparison, null);
});

test("no fixture stores an optimistic default", () => {
  const vocabulary = loadVocabulary();
  const fixtures = loadFixtures();
  const result = evaluateFixtures(fixtures, vocabulary);
  assert.equal(result.ok, true, result.errors.join("\n"));
  for (const fixture of fixtures) {
    const objects = [fixture.expected_canonical, ...(fixture.expected_events || [])].filter(Boolean);
    for (const object of objects) {
      assert.notEqual(object.optics_status, "SUCCESS", fixture.id);
      assert.notEqual(object.application_status, "PARTIAL", fixture.id);
      assert.notEqual(object.evidence_origin, "LOCAL_OBSERVATION", fixture.id);
    }
    assert.notEqual(fixture.evidence_origin, "LOCAL_OBSERVATION", fixture.id);
    assert.notEqual(fixture.semantic_dimension_readings.optics_health, "SUCCESS", fixture.id);
  }

  const missing = fixtures.find((fixture) => fixture.id === "missing-status");
  assert.equal(missing.expected_canonical.optics_status, "UNAVAILABLE");
  assert.equal("action" in missing.expected_canonical, false);
  assert.equal("http_status" in missing.expected_canonical, false);
  assert.equal("response_bytes" in missing.expected_canonical, false);

  const unknown = fixtures.find((fixture) => fixture.id === "unknown-status");
  assert.equal(unknown.expected_canonical.optics_status, "UNAVAILABLE");
  assert.match(unknown.diagnostic_limitations.join(" "), /OPTIMISTIC_DEFAULT_FORBIDDEN/);

  const legacyZero = fixtures.find((fixture) => fixture.id === "legacy-bytes-zero");
  const explicitZero = fixtures.find((fixture) => fixture.id === "explicit-response-bytes-zero");
  assert.equal(legacyZero.expected_canonical.response_bytes, null);
  assert.equal(explicitZero.expected_canonical.response_bytes, 0);

  const inherited = fixtures.find((fixture) => fixture.id === "inherited-trace");
  assert.equal(inherited.expected_canonical.trace_id_basis, "ASSERTED_CONTEXT");
  assert.equal("trace_id" in inherited.expected_canonical, false);

  const corrupt = fixtures.find((fixture) => fixture.id === "corrupt-record");
  assert.equal(corrupt.record_emitted, false);
  assert.equal(corrupt.expected_canonical, null);
  assert.equal(corrupt.semantic_dimension_readings.optics_health, "OPTICS_ERROR");

  const unreadable = fixtures.find((fixture) => fixture.id === "unreadable-record");
  const absent = fixtures.find((fixture) => fixture.id === "no-file");
  assert.notEqual(unreadable.semantic_dimension_readings.optics_health, "NOT_OBSERVED");
  assert.notEqual(absent.semantic_dimension_readings.optics_health, "NOT_OBSERVED");
  assert.equal(absent.semantic_dimension_readings.optics_health, "UNAVAILABLE");

  const forced = clone(fixtures.find((fixture) => fixture.id === "successful-http-response"));
  forced.expected_canonical.optics_status = "SUCCESS";
  const rejected = evaluateFixture(forced, vocabulary);
  assert.equal(rejected.ok, false);

  const sampling = fixtures.find((fixture) => fixture.id === "sampling-not-success");
  assert.equal("sampling" in sampling.expected_canonical, false);
  assert.notEqual(sampling.semantic_dimension_readings.sampling, "UNSAMPLED");
  const rewritten = clone(sampling);
  rewritten.expected_canonical.sampling = "UNSAMPLED";
  const samplingRejected = evaluateFixture(rewritten, vocabulary);
  assert.equal(samplingRejected.ok, false);

  for (const id of ["cli-0-3-24", "python-3-1-0", "cli-empty-call-file"]) {
    const fixture = fixtures.find((item) => item.id === id);
    assert.equal(fixture.input_record.envelope.schema_version, 2);
    assert.equal(fixture.expected_canonical.schema_version, 0);
    assert.match(fixture.diagnostic_limitations.join(" "), /compatibility\.legacy_schema_version/);
    const copied = clone(fixture);
    copied.expected_canonical.schema_version = 2;
    const versionRejected = evaluateFixture(copied, vocabulary);
    assert.equal(versionRejected.ok, false, id);
  }
});

test("status readings do not collapse workload success into optics success", () => {
  const fixtures = loadFixtures();
  const http = fixtures.find((fixture) => fixture.id === "successful-http-response");
  assert.equal(http.expected_canonical.application_status, "SUCCESS");
  assert.equal(http.expected_canonical.optics_status, "UNAVAILABLE");
  assert.equal(http.semantic_dimension_readings.workload_outcome, "SUCCESS");
  assert.equal(http.semantic_dimension_readings.optics_health, "UNAVAILABLE");

  const provider = fixtures.find((fixture) => fixture.id === "provider-http-error");
  assert.equal(provider.expected_canonical.http_status, 500);
  assert.equal(provider.expected_canonical.application_status, "APPLICATION_ERROR");
  assert.equal(provider.expected_canonical.issue_location, "PROVIDER_INTERACTION");
  assert.notEqual(provider.expected_canonical.optics_status, "SUCCESS");

  const partial = fixtures.find((fixture) => fixture.id === "partial-run");
  assert.equal(partial.expected_canonical.lifecycle, "PARTIAL");
  assert.equal(partial.expected_canonical.application_status, undefined);
  for (const event of partial.expected_events) assert.notEqual(event.application_status, "PARTIAL");

  const customer = fixtures.find((fixture) => fixture.id === "customer-application-exception");
  assert.equal(customer.expected_canonical.issue_location, "CUSTOMER_APPLICATION");
  assert.notEqual(customer.expected_canonical.issue_location, "PROVIDER_INTERACTION");
  assert.equal(customer.semantic_dimension_readings.dependency_outcome, "ABSENT");

  const nodeSdk = fixtures.find((fixture) => fixture.id === "node-sdk-0-2-4");
  assert.equal(nodeSdk.record_emitted, false);
  assert.equal(nodeSdk.expected_unsupported_state, "UNSUPPORTED");
  assert.equal(nodeSdk.expected_canonical, null);
});

test("canonical comparison bytes match the Python encoder", () => {
  const vocabulary = loadVocabulary();
  const fixtures = loadFixtures();
  const evaluated = evaluateFixtures(fixtures, vocabulary);
  assert.equal(evaluated.ok, true, evaluated.errors.join("\n"));
  const documents = [
    { b: 1, a: 2, nested: { z: true, m: null }, list: [1, "ok"] },
    { text: "line\n\t\"\\", snowman: "café" },
    { empty: {}, none: [], flag: false, zero: 0 },
    ...evaluated.comparisons,
  ];
  const python = spawnSync("python3", [PYTHON], {
    input: JSON.stringify(documents),
    encoding: "utf8",
  });
  assert.equal(python.status, 0, python.stderr);
  const lines = python.stdout.split("\n").filter((line) => line.length > 0);
  assert.equal(lines.length, documents.length);
  documents.forEach((document, index) => {
    assert.equal(lines[index], canonicalJson(document));
  });
  assert.equal(canonicalJson(-0), "0");
  assert.throws(() => canonicalJson(1.5), /NON_INTEGER_REJECTED/);
  assert.throws(() => canonicalJson(Number.MAX_SAFE_INTEGER + 2), /UNSAFE_INTEGER_REJECTED/);
  const maxSafe = 9007199254740991;
  assert.equal(canonicalJson(maxSafe), String(maxSafe));
  assert.equal(canonicalJson(-maxSafe), String(-maxSafe));
  const bounds = spawnSync("python3", [PYTHON], {
    input: JSON.stringify([maxSafe, -maxSafe, 0]),
    encoding: "utf8",
  });
  assert.equal(bounds.status, 0, bounds.stderr);
  assert.equal(bounds.stdout, [String(maxSafe), String(-maxSafe), "0"].join("\n") + "\n");
  const unsafe = spawnSync("python3", [PYTHON], {
    input: "[9007199254740993]",
    encoding: "utf8",
  });
  assert.notEqual(unsafe.status, 0);
  assert.match(unsafe.stderr, /UNSAFE_INTEGER_REJECTED/);
  const fraction = spawnSync("python3", [PYTHON], {
    input: "[1.5]",
    encoding: "utf8",
  });
  assert.notEqual(fraction.status, 0);
  assert.match(fraction.stderr, /NON_INTEGER_REJECTED/);
});

test("mutated fixtures cannot drop protective rules", () => {
  const vocabulary = loadVocabulary();
  const fixtures = loadFixtures();
  let drops = 0;
  for (const fixture of fixtures) {
    const required = requiredProtectiveRules(fixture, vocabulary);
    assert.ok(required.length > 0, fixture.id);
    for (const ruleId of required) {
      assert.equal(fixture.rule_ids.includes(ruleId), true, fixture.id + " " + ruleId);
      const mutated = clone(fixture);
      mutated.rule_ids = mutated.rule_ids.filter((id) => id !== ruleId);
      const result = evaluateFixture(mutated, vocabulary);
      assert.equal(result.ok, false, fixture.id + " dropped " + ruleId);
      assert.equal(
        result.errors.some((error) => error.includes("dropped protective rule " + ruleId)),
        true,
        fixture.id + " " + result.errors.join("; "),
      );
      drops += 1;
    }
    const stripped = clone(fixture);
    stripped.prohibited_optimistic_interpretations = stripped.prohibited_optimistic_interpretations.filter(
      (item) => !(item.path === "optics_status" && item.forbidden_value === "SUCCESS"),
    );
    const banned = evaluateFixture(stripped, vocabulary);
    assert.equal(banned.ok, false, fixture.id);
    drops += 1;
  }
  assert.ok(drops >= fixtures.length);
});
