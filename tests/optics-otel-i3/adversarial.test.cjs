"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const api = require("../../packages/optics-otel-i3/src/index.cjs");
const { assertNoLeak, goodRecord, traceEnable } = require("./helpers.cjs");

test("prompts, credentials, kernel details, company ops, and proof claims are withheld", async () => {
  const prompt = "do-not-export-this-prompt";
  const password = "do-not-export-this-password";
  const kernel = "ssl_write offset 12";
  const pipeline = "do-not-export-this-pipeline";
  const proof = "do-not-export-this-attestation";
  const records = [
    goodRecord({ prompt, messages: [{ role: "user", content: prompt }] }),
    goodRecord({ span_id: "0000000000000002", password }),
    goodRecord({ span_id: "0000000000000003", kernel }),
    goodRecord({ span_id: "0000000000000004", pipeline }),
    goodRecord({ span_id: "0000000000000005", slsa: proof }),
  ];
  let calls = 0;
  const result = await api.exportOpticsRecords(records, traceEnable({
    transport() {
      calls += 1;
      return { status: 200 };
    },
  }));
  assert.equal(calls, 0);
  assert.equal(result.reason, "NOTHING_TO_EXPORT");
  assert.equal(result.bytes_sent, 0);
  assert.deepEqual(result.authority.map((item) => item.operational_block), [
    "PROHIBITED_INPUT_IGNORED",
    "CREDENTIAL_FIELD",
    "KERNEL_DETAIL_EXCLUDED",
    "COMPANY_OPS_EXCLUDED",
    "UNSUPPORTED_PROOF_EXCLUDED",
  ]);
  for (const item of result.authority) assert.deepEqual(item.candidates, {});
  assertNoLeak(assert, result, [prompt, password, kernel, pipeline, proof]);
});

test("a credential-shaped path is not exported beside an otherwise valid observation", async () => {
  const secret = "sk-live-abcdefghij";
  const bodies = [];
  const result = await api.exportOpticsRecords([
    goodRecord({ path: "/v1/" + secret }),
    goodRecord({ span_id: "0000000000000002" }),
  ], traceEnable({
    transport(request) {
      bodies.push(request.body);
      return { status: 200 };
    },
  }));
  assert.equal(result.eligibility[0].reason, "CREDENTIAL_PATTERN_REJECTED");
  assert.equal(result.eligibility[1].export_eligible, true);
  assert.equal(bodies.length, 1);
  assert.equal(bodies[0].includes(secret), false);
  assert.equal(JSON.parse(bodies[0]).resourceSpans[0].scopeSpans[0].spans.length, 1);
  assertNoLeak(assert, result, [secret]);
});

test("credential options and endpoint secrets are not copied or sent", async () => {
  const header = "Bearer do-not-forward-this-token";
  const userinfo = "do-not-keep-this-userinfo";
  const query = "do-not-keep-this-query";
  let calls = 0;
  const transport = () => {
    calls += 1;
    return { status: 200 };
  };
  const withHeader = await api.exportOpticsRecords([goodRecord()], traceEnable({
    headers: { authorization: header },
    transport,
  }));
  assert.equal(withHeader.reason, "CREDENTIAL_OPTION_REJECTED");
  assert.equal(withHeader.network, false);
  assertNoLeak(assert, withHeader, [header]);

  const withUserinfo = await api.exportOpticsRecords([goodRecord()], traceEnable({
    endpoint: "https://user:" + userinfo + "@collector.example/v1/traces",
    transport,
  }));
  assert.equal(withUserinfo.reason, "ENDPOINT_USERINFO_REJECTED");
  assertNoLeak(assert, withUserinfo, [userinfo, "collector.example"]);

  const withQuery = await api.exportOpticsRecords([goodRecord()], traceEnable({
    endpoint: "https://collector.example/v1/traces?token=" + query,
    transport,
  }));
  assert.equal(withQuery.reason, "ENDPOINT_QUERY_REJECTED");
  assertNoLeak(assert, withQuery, [query]);
  assert.equal(calls, 0);
});

test("unsafe field names and thrown getters are not echoed", async () => {
  const sentence = "export this prompt sentence please";
  const named = goodRecord();
  named[sentence] = "x";
  const namedResult = await api.exportOpticsRecords([named], traceEnable());
  assert.equal(namedResult.authority[0].operational_block, "FIELD_NAME_REJECTED");
  assert.equal(namedResult.authority[0].rejected_field_names, 1);
  assert.equal(namedResult.exported, false);
  assertNoLeak(assert, namedResult, [sentence]);

  const throwing = {};
  Object.defineProperty(throwing, "source_shape", {
    enumerable: true,
    get() {
      throw new Error("secret-getter-text");
    },
  });
  const thrown = await api.exportOpticsRecords([throwing], traceEnable());
  assert.equal(thrown.authority[0].operational_block, "RECORD_UNREADABLE");
  assertNoLeak(assert, thrown, ["secret-getter-text"]);
});

test("prototype pollution and transport echoes are ignored", async () => {
  const polluted = "prompt-via-prototype";
  const echoed = "transport-echoed-prompt";
  Object.prototype.polluted = polluted;
  try {
    const bodies = [];
    const result = await api.exportOpticsRecords([goodRecord()], traceEnable({
      transport(request) {
        bodies.push(request.body);
        return { status: 200, body: echoed, prompt: echoed };
      },
    }));
    assert.equal(result.exported, true);
    assert.equal(bodies[0].includes(polluted), false);
    assertNoLeak(assert, result, [polluted, echoed]);
    assert.equal(Object.hasOwn(result, "polluted"), false);
  } finally {
    delete Object.prototype.polluted;
  }
});

test("a frozen record is not mutated and the result is frozen", async () => {
  const record = Object.freeze(goodRecord());
  const result = await api.exportOpticsRecords([record], traceEnable());
  assert.equal(Object.isFrozen(result), true);
  assert.throws(() => {
    result.exported = false;
  });
  assert.equal(result.exported, true);
});

test("non-objects are drop evidence and not sent", async () => {
  let calls = 0;
  const result = await api.exportOpticsRecords([null, "prompt-string", 4], traceEnable({
    transport() {
      calls += 1;
      return { status: 200 };
    },
  }));
  assert.equal(calls, 0);
  assert.deepEqual(result.drops.map((drop) => drop.reason), [
    "RECORD_NOT_OBJECT",
    "RECORD_NOT_OBJECT",
    "RECORD_NOT_OBJECT",
  ]);
  assertNoLeak(assert, result, ["prompt-string"]);
});
