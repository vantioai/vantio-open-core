"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const { adaptFixture } = require("../../packages/optics-node-adapter/src/adapt.cjs");
const { composeCanonical } = require("../../packages/vantio-cli-pkg02/src/record.cjs");
const fixtures = require("../../packages/optics-record-vocabulary/fixtures/conformance-fixtures.json");
const support = require("./support.cjs");

test("Unit A fixtures do not become optics SUCCESS through the inert adapter", () => {
  assert.equal(fixtures.length, 34);
  for (const fixture of fixtures) {
    const adapted = adaptFixture(fixture);
    const tokens = support.opticsTokens(adapted, []);
    assert.equal(tokens.includes("SUCCESS"), false, fixture.id + " " + tokens.join(","));
  }
  const unknown = fixtures.find((fixture) => fixture.id === "unknown-status");
  const adapted = adaptFixture(unknown);
  assert.equal(adapted.optimistic_default_forbidden, true);
  assert.equal(support.opticsTokens(adapted, []).includes("UNAVAILABLE"), true);
});

test("a future write of the CLI fixture workload stores OBSERVED where the legacy reading stays UNAVAILABLE", () => {
  const fixture = fixtures.find((item) => item.id === "cli-0-3-24");
  const legacy = Object.assign({}, fixture.input_record.envelope, {
    calls: [fixture.input_record.call],
  });
  const adapted = adaptFixture(fixture);
  const tokens = support.opticsTokens(adapted, []);
  assert.equal(tokens.includes("UNAVAILABLE"), true);
  assert.equal(tokens.includes("SUCCESS"), false);
  const written = composeCanonical(legacy, [{
    lengthPresent: true,
    mediation: "node_fetch",
    networkError: false,
    port: null,
    responseBytes: 12,
  }], { applicationResult: null });
  assert.equal(written.record_emitted, true);
  assert.equal(written.document.optics_status, "OBSERVED");
  assert.equal(written.document.events[0].optics_status, "OBSERVED");
  assert.equal(written.document.events[0].response_bytes, 12);
  assert.equal(written.document.events[0].application_status, "SUCCESS");
  assert.equal(written.document.run_id, "0xabc123");
  assert.equal(written.document.schema_version, 0);
  assert.equal(written.document.compatibility.legacy_schema_version, 2);
  assert.equal(support.hasOwn(written.document, "trace_id"), false);
  support.assertNoOpticsSuccess(assert, written.document);
});

test("the writer omits a missing length, keeps an explicit zero, and drops enforcement actions", () => {
  const legacy = {
    arch: "x64",
    calls: [
      {
        action: "OBSERVED",
        bytes: 0,
        hostname: "api.openai.com",
        method: "GET",
        path: "/",
        scheme: "https",
        status: 200,
      },
      {
        action: "BLOCKED_HOST",
        hostname: "api.openai.com",
      },
      {
        action: "OBSERVED",
        bytes: 0,
        hostname: "api.openai.com",
        method: "POST",
        optics_status: "SUPER_SUCCESS",
        path: "/",
        scheme: "https",
        status: 204,
      },
    ],
    cli_version: "0.3.24",
    platform: "linux",
    schema_version: 2,
    trace_id: "0xbytes",
    vantio_run_log: "1",
  };
  const written = composeCanonical(legacy, [
    { lengthPresent: false, mediation: "node_fetch" },
    { lengthPresent: true, mediation: "node_fetch", responseBytes: 0 },
  ], { applicationResult: { marker: "kept" } });
  assert.equal(written.application_result.marker, "kept");
  assert.equal(support.hasOwn(written.document.events[0], "response_bytes"), false);
  assert.equal(written.document.events[1].response_bytes, 0);
  assert.equal(written.document.events[1].optics_status, "UNAVAILABLE");
  assert.equal(written.document.diagnostics.optimistic_default_forbidden, true);
  assert.equal(JSON.stringify(written.document).includes("BLOCKED_HOST"), false);
  assert.equal(JSON.stringify(written.document).includes("ALLOWED"), false);
  support.assertNoOpticsSuccess(assert, written.document);
});
