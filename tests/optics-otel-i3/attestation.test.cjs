"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const api = require("../../packages/optics-otel-i3/src/index.cjs");
const { goodRecord, sourceRecord, traceEnable } = require("./helpers.cjs");

test("an enabled export rejects an unsigned canonical observation", async () => {
  for (let run = 0; run < 3; run += 1) {
    let calls = 0;
    const forged = goodRecord();
    const signed = goodRecord({ signature: "caller-signed", span_id: "00000000000000c1" });
    const labeled = goodRecord({ attestation: "producer", span_id: "00000000000000c2" });
    const result = await api.exportOpticsRecords([forged, signed, labeled], traceEnable({
      transport() {
        calls += 1;
        return { status: 200 };
      },
    }));
    assert.equal(calls, 0, `run ${run}`);
    assert.equal(result.enabled, true);
    assert.equal(result.exported, false);
    assert.equal(result.reason, "NOTHING_TO_EXPORT");
    assert.equal(result.network, false);
    assert.equal(result.bytes_sent, 0);
    assert.equal(result.product_otlp_export_authorized, false);
    assert.equal(result.authority[0].attestation, "unattested");
    assert.equal(result.eligibility[0].export_eligible, false);
    assert.equal(result.eligibility[0].reason, "UNATTESTED");
    assert.equal(result.eligibility[0].attestation, "unattested");
    assert.equal(result.eligibility[1].export_eligible, false);
    assert.equal(result.eligibility[1].reason, "UNATTESTED");
    assert.equal(result.authority[2].operational_block, "UNSUPPORTED_PROOF_EXCLUDED");
    assert.equal(result.eligibility[2].export_eligible, false);
    assert.equal(JSON.stringify(result).includes("caller-signed"), false);
  }
});

test("a source-attested observation is sent and a copy is not", async () => {
  for (let run = 0; run < 3; run += 1) {
    const record = sourceRecord({ span_id: "00000000000000ab" });
    const copy = structuredClone(record);
    const bodies = [];
    const result = await api.exportOpticsRecords([record, copy], traceEnable({
      transport(request) {
        bodies.push(request.body);
        return { status: 200 };
      },
    }));
    assert.equal(result.exported, true, `run ${run}`);
    assert.equal(result.authority[0].attestation, "producer");
    assert.equal(result.eligibility[0].attestation, "producer");
    assert.equal(result.eligibility[0].export_eligible, true);
    assert.equal(result.authority[1].attestation, "unattested");
    assert.equal(result.eligibility[1].reason, "UNATTESTED");
    assert.equal(bodies.length, 1);
    const spans = JSON.parse(bodies[0]).resourceSpans[0].scopeSpans[0].spans;
    assert.equal(spans.length, 1);
    assert.equal(spans[0].spanId, "00000000000000ab");
    assert.equal(result.product_otlp_export_authorized, false);
  }
});

test("a bound record whose bytes change is not sent", async () => {
  let note = "before";
  const record = goodRecord();
  Object.defineProperty(record, "customer_note", {
    enumerable: true,
    configurable: true,
    get() {
      return note;
    },
  });
  assert.equal(api.attestSourceRecord(record).ok, true);
  note = "after";
  let calls = 0;
  const result = await api.exportOpticsRecords([record], traceEnable({
    transport() {
      calls += 1;
      return { status: 200 };
    },
  }));
  assert.equal(calls, 0);
  assert.equal(result.exported, false);
  assert.equal(result.reason, "NOTHING_TO_EXPORT");
  assert.equal(result.authority[0].attestation, "unattested");
  assert.equal(result.eligibility[0].reason, "ATTESTATION_MISMATCH");
});

test("a disabled adapter still does not export an attested record", async () => {
  let calls = 0;
  const result = await api.exportOpticsRecords([sourceRecord()], {
    enabled: false,
    adapter: "otlp_traces",
    endpoint: "http://127.0.0.1:9/v1/traces",
    transport() {
      calls += 1;
      return { status: 200 };
    },
  });
  assert.equal(calls, 0);
  assert.equal(result.exported, false);
  assert.equal(result.reason, "ADAPTER_DISABLED");
  assert.equal(result.network, false);
});
