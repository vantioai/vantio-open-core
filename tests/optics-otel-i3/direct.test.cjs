"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { test: privateTreeSkipTest } = require("node:test");

if (!fs.existsSync(path.resolve(__dirname, "../../docs/internal"))) {
  privateTreeSkipTest("docs/internal", { skip: "PRIVATE_TREE_REMOVED_FROM_PUBLIC_TIP" }, () => {});
} else {
"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const api = require("../../packages/optics-otel-i3/src/index.cjs");
const { payloadAccepted, revalidateCandidates } = require("../../packages/optics-otel-i3/src/encode.cjs");
const { identityProblem, doc } = require("../../packages/optics-otel-i3/src/mapping_ref.cjs");
const { assertNoLeak, goodRecord, traceEnable } = require("./helpers.cjs");

const ROOT = path.resolve(__dirname, "../..");

test("status is default disabled and names the council token", () => {
  const status = api.adapterStatus();
  assert.equal(status.producer_classification, "OTEL_I3_ADAPTER_READY_FOR_COUNCIL_DEFAULT_DISABLED");
  assert.equal(status.default_enabled, false);
  assert.equal(status.active, false);
  assert.equal(status.network_on_load, false);
  assert.equal(status.public_shipped_support, false);
  assert.equal(status.product_otlp_export_authorized, false);
  assert.equal(status.founder_decision_12, "unresolved");
  assert.equal(status.schema_url, null);
  assert.equal(status.mapping_version, 0);
  assert.equal(status.otlp_protobuf, false);
  assert.equal(status.signals.otlp_traces, "EXPLICIT_ENABLE_ONLY");
  assert.equal(status.signals.otlp_metrics, "NOT_AUTHORIZED");
  assert.equal(status.signals.otlp_logs, "NOT_AUTHORIZED");
  assert.equal(status.council, "PENDING_COUNCIL");
  assert.equal(api.LIMITS.hardMaxAttempts, 5);
  assert.equal(api.LIMITS.hardMaxQueue, 32);
});

test("public exports stay small", () => {
  assert.deepEqual(Object.keys(api).sort(), [
    "LIMITS",
    "POSTURE",
    "adapterStatus",
    "attestSourceRecord",
    "evaluateRecords",
    "exportOpticsRecords",
    "parseCustomerEndpoint",
  ]);
});

test("manifest matches the adapter posture and the approved mapping", () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, "docs/internal/ws7-otel-i3/ADAPTER-MANIFEST.json"), "utf8"));
  for (const key of [
    "adapter_id",
    "producer_classification",
    "mapping_id",
    "mapping_version",
    "schema_status",
    "stable_schema",
    "schema_url",
    "public_shipped_support",
    "product_otlp_export_authorized",
    "founder_decision_12",
    "default_enabled",
    "reads_environment",
    "otlp_json",
    "otlp_protobuf",
    "council",
  ]) {
    assert.deepEqual(manifest[key], api.POSTURE[key], key);
  }
  assert.deepEqual(manifest.signals, api.adapterStatus().signals);
  assert.equal(manifest.starting_main, "89f95099d0dce463307eb75d78e7fcf2ef99feb2");
  assert.equal(identityProblem(doc), "");
  assert.equal(doc.i3_status, "NOT_AUTHORIZED");
  assert.equal(identityProblem({ ...doc, i3_status: "AUTHORIZED" }), "i3_status");
  assert.equal(identityProblem({ ...doc, otlp_export_authorized: true }), "otlp_export_authorized");
  assert.equal(identityProblem({ ...doc, mapping_version: 1 }), "mapping_version");
});

test("customer endpoint accepts only an http(s) traces URL", () => {
  const accepted = api.parseCustomerEndpoint("https://collector.example/v1/traces");
  assert.equal(accepted.ok, true);
  assert.equal(accepted.url, "https://collector.example/v1/traces");
  assert.equal(accepted.origin, "https://collector.example");

  const rooted = api.parseCustomerEndpoint("http://127.0.0.1:4318");
  assert.equal(rooted.ok, true);
  assert.equal(rooted.url, "http://127.0.0.1:4318/v1/traces");

  const cases = [
    ["", "ENDPOINT_REQUIRED"],
    ["not a url", "ENDPOINT_REJECTED"],
    ["file:///tmp/out", "ENDPOINT_SCHEME_REJECTED"],
    ["https://user:super-secret-pass@collector.example/v1/traces", "ENDPOINT_USERINFO_REJECTED"],
    ["https://collector.example/v1/traces?api_key=super-secret-query", "ENDPOINT_QUERY_REJECTED"],
    ["https://collector.example/v1/traces#fragment-secret", "ENDPOINT_QUERY_REJECTED"],
    ["https://collector.example/v1/logs", "ENDPOINT_PATH_REJECTED"],
    ["https://collector.example/v1/traces/", "ENDPOINT_PATH_REJECTED"],
  ];
  for (const [value, reason] of cases) {
    const parsed = api.parseCustomerEndpoint(value);
    assert.equal(parsed.ok, false, value);
    assert.equal(parsed.reason, reason, value);
    assert.equal(JSON.stringify(parsed).includes("super-secret"), false, value);
  }
});

test("revalidation rejects prohibited targets and credential-shaped values", () => {
  const banned = revalidateCandidates({
    "gen_ai.provider.name": "openai",
    "gen_ai.input.messages": "hidden",
  });
  assert.equal(banned.ok, false);
  assert.equal(banned.reason, "CANDIDATE_REJECTED");

  const marked = revalidateCandidates({
    "url.path": "/v1/sk-live-secretvalue",
  });
  assert.equal(marked.ok, false);
  assert.equal(marked.reason, "CREDENTIAL_PATTERN_REJECTED");
  assert.equal(JSON.stringify(marked).includes("sk-live"), false);

  const chat = revalidateCandidates({
    "gen_ai.operation.name": "chat",
    "http.request.method": "POST",
    "url.path": "/v1/chat/completions",
    "gen_ai.provider.name": "openai",
  });
  assert.equal(chat.ok, true);
  assert.equal(chat.attributes["gen_ai.provider.name"], "openai");

  const mismatched = revalidateCandidates({
    "gen_ai.operation.name": "chat",
    "url.path": "/v1/messages",
    "http.request.method": "POST",
  });
  assert.equal(mismatched.ok, false);

  const handBuilt = JSON.stringify({
    resourceSpans: [{
      resource: { attributes: [{ key: "gen_ai.input.messages", value: { stringValue: "x" } }] },
      scopeSpans: [],
    }],
  });
  assert.equal(payloadAccepted(handBuilt), false);
});

test("omitted options and inherited enable flags stay disabled", async () => {
  let calls = 0;
  const disabled = await api.exportOpticsRecords([goodRecord()], {
    endpoint: "http://203.0.113.10/v1/traces",
    transport() {
      calls += 1;
      return { status: 200 };
    },
  });
  assert.equal(disabled.enabled, false);
  assert.equal(disabled.exported, false);
  assert.equal(disabled.reason, "ADAPTER_DISABLED");
  assert.equal(disabled.network, false);
  assert.equal(disabled.bytes_sent, 0);
  assert.equal(disabled.delivery.attempted, false);
  assert.equal(disabled.records_seen, 1);
  assert.equal(calls, 0);
  assertNoLeak(assert, disabled, ["203.0.113.10"]);

  const textFlag = await api.exportOpticsRecords([goodRecord()], traceEnable({ enabled: "true" }));
  assert.equal(textFlag.reason, "ADAPTER_DISABLED");
  assert.equal(textFlag.bytes_sent, 0);

  const inherited = Object.create({ enabled: true, adapter: "otlp_traces" });
  inherited.transport = () => {
    calls += 1;
    return { status: 200 };
  };
  const inheritedResult = await api.exportOpticsRecords([goodRecord()], inherited);
  assert.equal(inheritedResult.reason, "ADAPTER_DISABLED");
  assert.equal(calls, 0);

  const empty = await api.exportOpticsRecords();
  assert.equal(empty.reason, "ADAPTER_DISABLED");
  assert.equal(empty.records_seen, 0);
});

test("metrics and logs cannot be selected", async () => {
  let calls = 0;
  for (const adapter of ["otlp_metrics", "otlp_logs"]) {
    const result = await api.exportOpticsRecords([goodRecord()], traceEnable({
      adapter,
      transport() {
        calls += 1;
        return { status: 200 };
      },
    }));
    assert.equal(result.reason, "SIGNAL_NOT_AUTHORIZED", adapter);
    assert.equal(result.enabled, false);
    assert.equal(result.bytes_sent, 0);
  }
  const missing = await api.exportOpticsRecords([goodRecord()], { enabled: true, endpoint: "https://collector.example/v1/traces" });
  assert.equal(missing.reason, "ADAPTER_NOT_SELECTED");
  assert.equal(calls, 0);
});

test("a disabled call does not open a customer endpoint", async () => {
  const result = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("disabled call waited on the network")), 200);
    api.exportOpticsRecords([goodRecord()], {
      enabled: false,
      endpoint: "http://203.0.113.10/v1/traces",
    }).then((value) => {
      clearTimeout(timer);
      resolve(value);
    }, (error) => {
      clearTimeout(timer);
      reject(error);
    });
  });
  assert.equal(result.reason, "ADAPTER_DISABLED");
  assert.equal(result.network, false);
});

test("mapping package export stays disabled", () => {
  const mapping = require("../../packages/optics-otel-mapping/src/index.cjs");
  const prompt = "mapping-package-must-not-copy";
  const result = mapping.exportOpticsRecords(
    [{ prompt, source_shape: "canonical_observation" }],
    { enabled: true, adapter: "otlp_traces", endpoint: "https://collector.example/v1/traces" },
  );
  assert.equal(result.exported, false);
  assert.equal(result.reason, "ADAPTERS_DISABLED");
  assert.equal(result.bytes_sent, 0);
  assert.equal(result.network, false);
  assert.equal(JSON.stringify(result).includes(prompt), false);
  assert.equal(mapping.mappingDocument().i3_status, "NOT_AUTHORIZED");
});
}
