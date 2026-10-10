"use strict";

const assert = require("node:assert/strict");
const { test } = require("node:test");
const { project, textHasCanary } = require("../src/privacy.cjs");
const { acceptsVersion } = require("../src/schema.cjs");

const TRACE = "ab".repeat(16);
const SPAN = "cd".repeat(8);
const DIGEST = `sha256:${"12".repeat(32)}`;
const CANARY = "CANARY-PROMPTTEXT";

function base(extra = {}) {
  return {
    kind: "optics.observation",
    trace_id: TRACE,
    span_id: SPAN,
    destination_host: "api.openai.com",
    destination_port: 443,
    coverage_state: "OBSERVED",
    ...extra,
  };
}

const FIELDS = ["destination_host", "executable", "workload_id", "path", "optics_status", "application_status"];

test("encoded and split canaries are refused in every exported field", () => {
  const encoded = [...Buffer.from(CANARY)].map((byte) => `%${byte.toString(16).toUpperCase().padStart(2, "0")}`).join("");
  const b64 = Buffer.from(CANARY, "utf8").toString("base64");
  assert.equal(textHasCanary(encoded), true);
  assert.equal(textHasCanary(b64), true);
  for (const field of FIELDS) {
    for (const value of [CANARY, encoded, b64, `%25${encoded.slice(3)}`]) {
      const result = project(base({ [field]: value }));
      if (result.ok) {
        const blob = JSON.stringify(result.event).toLowerCase();
        assert.equal(blob.includes("canary"), false, `${field} leaked ${value}`);
      } else {
        assert.equal(result.reason, "PRIVACY");
      }
    }
  }
  const split = project(base({ destination_host: "canary-", path: "prompttext" }));
  assert.equal(split.ok, false);
  assert.equal(split.reason, "PRIVACY");
  const halves = project(base({ workload_id: "cana", path: "ry-prompttext" }));
  assert.equal(halves.ok, false);
  const triple = project(base({ workload_id: "can", executable: "ary", path: "-prompttext" }));
  assert.equal(triple.ok, false);
  assert.equal(triple.reason, "PRIVACY");
  const lowerHost = Buffer.from(CANARY, "utf8").toString("base64").toLowerCase();
  const lowered = project(base({ destination_host: lowerHost }));
  assert.equal(lowered.ok, false);
  assert.equal(lowered.reason, "PRIVACY");
  const mixed = Buffer.from("Canary-prompttextXYZ", "utf8").toString("base64");
  const mixedHost = project(base({ destination_host: mixed }));
  assert.equal(mixedHost.ok, false);
  assert.equal(mixedHost.reason, "PRIVACY");
  const mixedPath = project(base({ path: `/${mixed}` }));
  assert.equal(mixedPath.ok, false);
  assert.equal(mixedPath.reason, "PRIVACY");
});

test("forbidden payload fields never reach the projection", () => {
  const result = project(base({
    prompt: CANARY,
    completion: CANARY,
    body: CANARY,
    headers: { authorization: CANARY, cookie: CANARY },
    query: CANARY,
    request_body: CANARY,
    response_body: CANARY,
  }));
  assert.equal(result.ok, true);
  const blob = JSON.stringify(result.event);
  assert.equal(blob.toLowerCase().includes("canary"), false);
  assert.equal(Object.hasOwn(result.event, "prompt"), false);
  assert.equal(Object.hasOwn(result.event, "headers"), false);
});

test("boundary values stay inside the schema or are dropped", () => {
  assert.equal(project(base({ destination_port: 0 })).event.destination_port, null);
  assert.equal(project(base({ destination_port: 65535 })).event.destination_port, 65535);
  assert.equal(project(base({ destination_port: 65536 })).event.destination_port, null);
  assert.equal(project(base({ destination_port: 1.5 })).event.destination_port, null);
  assert.equal(project(base({ destination_port: "443" })).event.destination_port, 443);
  assert.equal(project(base({ request_bytes: 0 })).event.request_bytes, 0);
  assert.equal(project(base({ request_bytes: -1 })).event.request_bytes, null);
  assert.equal(project(base({ request_bytes: 1.2 })).event.request_bytes, null);
  assert.equal(project(base({ response_bytes: null })).event.response_bytes, null);
  assert.equal(project(base({ http_status: 99 })).event.http_status, null);
  assert.equal(project(base({ http_status: 100 })).event.http_status, 100);
  assert.equal(project(base({ http_status: 599 })).event.http_status, 599);
  assert.equal(project(base({ http_status: 600 })).event.http_status, null);
  assert.equal(project(base({ pid: -1 })).event.pid, null);
  assert.equal(project(base({ executable: "../agent" })).event.executable, null);
  assert.equal(project(base({ destination_host: "user@api.openai.com" })).event.destination_host, null);
  assert.equal(project(base({ path: "?CANARY-QUERYSTRING=1" })).event.path, "");
  const longLineage = project(base({
    lineage: Array.from({ length: 20 }, (_, i) => ({ pid: i + 1, executable: "agent" })),
  }));
  assert.equal(longLineage.event.lineage.length, 16);
  assert.equal(project(base({ trace_id: "ab" })).ok, false);
  assert.equal(project(base({ trace_id: TRACE.toUpperCase() })).event.trace_id, TRACE);
  assert.equal(project(base({ kind: "Optics.Observation" })).ok, false);
  assert.equal(project(base({ kind: "phantom.decision", decision: "block", policy_digest: DIGEST })).ok, false);
  assert.equal(project(base({ kind: "phantom.decision", decision: "BLOCK", policy_digest: "sha256:abcd" })).ok, false);
  assert.equal(project(null).reason, "MALFORMED");
  assert.equal(project([]).reason, "MALFORMED");
  assert.equal(project(base({ coverage_state: "COMPLETE" })).event.coverage_state, "UNKNOWN");
});

test("schema fuzz and malformed payloads do not throw or leak", () => {
  const samples = [
    {},
    { kind: "optics.observation" },
    { kind: "optics.observation", trace_id: TRACE, span_id: SPAN, __proto__: { admin: true } },
    { kind: "optics.observation", trace_id: TRACE, span_id: SPAN, constructor: { name: "x" } },
    { kind: "optics.observation", trace_id: TRACE, span_id: SPAN, destination_host: "a".repeat(400) },
    { kind: "optics.observation", trace_id: TRACE, span_id: SPAN, workload_id: "ok\nCANARY-PROMPTTEXT" },
    { kind: "enterprise.evidence", trace_id: TRACE, span_id: SPAN },
    { kind: "phantom.decision", trace_id: TRACE, span_id: SPAN, decision: "ALLOW" },
    { kind: 1, trace_id: TRACE, span_id: SPAN },
    { kind: "optics.observation", trace_id: TRACE, span_id: SPAN, request_bytes: Number.NaN },
    { kind: "optics.observation", trace_id: TRACE, span_id: SPAN, request_bytes: Number.POSITIVE_INFINITY },
    { kind: "optics.observation", trace_id: `${TRACE}\u0000`, span_id: SPAN },
  ];
  for (let i = 0; i < 40; i += 1) {
    samples.push({
      kind: "optics.observation",
      trace_id: TRACE,
      span_id: SPAN,
      destination_host: `h${i}.example.com`,
      extra: { nested: { prompt: CANARY, n: i } },
      path: `/v1/${i}?x=${encodeURIComponent(CANARY)}`,
    });
  }
  for (const sample of samples) {
    let result;
    assert.doesNotThrow(() => {
      result = project(sample);
    });
    if (result && result.ok) {
      const blob = JSON.stringify(result.event);
      assert.equal(blob.toLowerCase().includes("canary"), false);
      assert.equal(blob.includes("\u0000"), false);
    }
  }
});

test("major 1 accepts additive versions and rejects a breaking major", () => {
  for (const version of ["1.0.0", "1.0.1", "1.9.0", "1.99.1"]) assert.equal(acceptsVersion(version), true);
  for (const version of ["2.0.0", "0.1.0", "1", "1.0", "v1.0.0", "", null]) assert.equal(acceptsVersion(version), false);
});

test("privacy cases stay stable across repeated runs", () => {
  for (let run = 0; run < 5; run += 1) {
    const result = project(base({ path: `/v1/${encodeURIComponent(CANARY)}` }));
    assert.equal(result.ok, false, `run ${run}`);
    const clean = project(base({ path: "/v1/chat/completions?secret=1" }));
    assert.equal(clean.ok, true);
    assert.equal(clean.event.path, "/v1/chat/completions");
  }
});
