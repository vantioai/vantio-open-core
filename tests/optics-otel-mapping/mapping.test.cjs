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

const api = require("../../packages/optics-otel-mapping/src/index.cjs");

const ROOT = path.resolve(__dirname, "../..");
const PUBLIC_SKETCH = path.join(ROOT, "docs/optics-otel-mapping.md");

test("mapping identity stays unstable and unpublished", () => {
  const doc = api.mappingDocument();
  assert.equal(doc.mapping_id, "WS7-I2");
  assert.equal(doc.mapping_version, 0);
  assert.equal(doc.schema_status, "unstable-pre-1.0");
  assert.equal(doc.stable_schema, false);
  assert.equal(doc.public_shipped_support, false);
  assert.equal(doc.otlp_export_authorized, false);
  assert.equal(doc.adapters_default_enabled, false);
  assert.equal(doc.i3_status, "NOT_AUTHORIZED");
  assert.equal(doc.founder_decision_12, "unresolved");
  assert.equal(doc.schema_url, null);
  assert.equal(doc.producer_classification, "OTEL_MAPPING_DESIGN_REVISION_READY_FOR_COUNCIL");
  assert.equal(api.POSTURE.producer_classification, "OTEL_MAPPING_DESIGN_REVISION_READY_FOR_COUNCIL");
  assert.deepEqual(doc.canonical_candidate_origins, ["LOCAL_OBSERVATION"]);
});

test("every adapter defaults disabled and has no implementation", () => {
  const adapters = api.adapters();
  assert.deepEqual(adapters.map((adapter) => adapter.id), ["otlp_traces", "otlp_metrics", "otlp_logs"]);
  for (const adapter of adapters) {
    assert.equal(adapter.enabled, false);
    assert.equal(adapter.default_enabled, false);
    assert.equal(adapter.implementation, "NOT_PRESENT");
    assert.equal(adapter.network, false);
  }
});

test("export stays disabled when a caller asks to enable it", () => {
  const prompt = "do-not-copy-this-prompt";
  const result = api.exportOpticsRecords(
    [{ prompt, source_shape: "canonical_observation" }],
    { enabled: true, adapter: "otlp_traces", endpoint: "https://collector.example" },
  );
  assert.equal(result.exported, false);
  assert.equal(result.reason, "ADAPTERS_DISABLED");
  assert.equal(result.network, false);
  assert.equal(result.bytes_sent, 0);
  assert.equal(result.records_seen, 1);
  assert.equal(JSON.stringify(result).includes(prompt), false);
  assert.equal(JSON.stringify(result).includes("collector.example"), false);
  for (const adapter of result.adapters) assert.equal(adapter.enabled, false);
});

test("prohibited GenAI targets are never map dispositions", () => {
  const doc = api.mappingDocument();
  for (const target of api.PROHIBITED_TARGETS) {
    const rows = doc.rows.filter((row) => row.target === target);
    assert.ok(rows.length >= 1, target);
    for (const row of rows) {
      assert.equal(row.disposition, "DO_NOT_MAP");
      assert.equal(row.emitted_by_this_package, false);
    }
  }
});

test("crosswalk is a subset of the v1.37.0 well-known provider names", () => {
  const doc = api.mappingDocument();
  const wellKnown = new Set(doc.gen_ai_provider_name_well_known_v1_37_0);
  for (const entry of doc.provider_crosswalk) {
    assert.equal(wellKnown.has(entry.gen_ai_provider_name), true, entry.gen_ai_provider_name);
  }
  assert.equal(doc.provider_crosswalk.some((entry) => entry.optics_provider_id === "google"), false);
  assert.equal(doc.unmapped_provider_ids.includes("google"), true);
  assert.equal(doc.unmapped_provider_ids.includes("ollama"), true);
});

test("internal manifest matches the mapping document", () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, "docs/internal/ws7-otel-mapping/MAPPING-MANIFEST.json"), "utf8"));
  const doc = api.mappingDocument();
  for (const key of [
    "mapping_id",
    "mapping_version",
    "schema_status",
    "stable_schema",
    "schema_url",
    "public_shipped_support",
    "otlp_export_authorized",
    "adapters_default_enabled",
    "i3_status",
    "founder_decision_12",
    "producer_classification",
  ]) {
    assert.deepEqual(manifest[key], doc[key], key);
  }
  assert.equal(manifest.council, "PENDING_COUNCIL");
  assert.equal(manifest.source, "packages/optics-otel-mapping/mapping/otel-semantic-mapping.json");
});

test("new otel mapping files match the documentation-release stale-name gate", async () => {
  const { countPatterns } = await import("../../docs/scripts/docs-release-lib.mjs");
  const spec = JSON.parse(fs.readFileSync(path.join(ROOT, "docs/governance/STALE-NAMES.json"), "utf8"));
  assert.ok(Array.isArray(spec.patterns) && spec.patterns.length > 0);
  const scanned = [];
  const extensions = [".md", ".txt", ".js", ".cjs", ".mjs", ".py", ".ts", ".json", ".yml", ".yaml", ".toml"];
  function visit(directory) {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const absolute = path.join(directory, entry.name);
      if (entry.isDirectory()) visit(absolute);
      else if (extensions.some((ext) => entry.name.endsWith(ext))) scanned.push(absolute);
    }
  }
  for (const relative of [
    "docs/internal/ws7-otel-mapping",
    "packages/optics-otel-mapping",
    "tests/optics-otel-mapping",
  ]) {
    visit(path.join(ROOT, relative));
  }
  const relatives = scanned.map((file) => path.relative(ROOT, file));
  assert.ok(relatives.includes(path.join("tests", "optics-otel-mapping", "mapping.test.cjs")));
  for (const file of scanned) {
    const count = countPatterns(fs.readFileSync(file, "utf8"), spec.patterns);
    assert.equal(count, 0, path.relative(ROOT, file));
  }
});

test("public sketch still says Optics does not export OTLP", () => {
  const text = fs.readFileSync(PUBLIC_SKETCH, "utf8");
  assert.match(text, /Optics does not export OTLP/);
  assert.equal(text.includes("OTEL_MAPPING_DESIGN_READY_FOR_COUNCIL"), false);
  assert.equal(text.includes("OTEL_MAPPING_DESIGN_REVISION_READY_FOR_COUNCIL"), false);
  assert.equal(text.includes("shipped support"), false);
  assert.equal(text.includes("public OTLP"), false);
});

test("canonical chat observation previews candidates and does not emit them", () => {
  const preview = api.preview({
    source_shape: "canonical_observation",
    record_type: "observation_event",
    evidence_origin: "LOCAL_OBSERVATION",
    provider_id: "openai",
    provider_confidence: "CATALOG",
    destination_host: "API.OpenAI.com",
    destination_port: 443,
    scheme: "https",
    method: "POST",
    path: "/v1/chat/completions",
    http_status: 200,
    application_status: "SUCCESS",
    optics_status: "UNAVAILABLE",
    request_bytes: 120,
    response_bytes: 80,
    duration_ms: 40,
    trace_id: "abc",
    trace_id_basis: "OPTICS_GENERATED",
    run_id: "run_1",
    ok: true,
    action: "OBSERVED",
  });
  assert.equal(preview.emitted, false);
  assert.equal(preview.reason, "ADAPTERS_DISABLED");
  assert.equal(preview.would_be_operational_if_i3_enabled, true);
  assert.equal(preview.span.client, "OK");
  assert.equal(preview.span.instrumentation, null);
  assert.equal(preview.trace_context, null);
  assert.deepEqual(preview.candidates, {
    "gen_ai.operation.name": "chat",
    "gen_ai.provider.name": "openai",
    "http.request.method": "POST",
    "http.response.status_code": 200,
    "server.address": "api.openai.com",
    "server.port": 443,
    "url.path": "/v1/chat/completions",
    "url.scheme": "https",
  });
  const codes = preview.omitted.map((item) => item.code);
  assert.ok(codes.includes("NOT_TOKEN_COUNTS"));
  assert.ok(codes.includes("CORRESPONDENCE_ONLY"));
  assert.ok(codes.includes("TRACE_BASIS_NOT_ELIGIBLE"));
  assert.ok(codes.includes("RUN_ID_IS_NOT_TRACE_ID"));
  assert.ok(codes.includes("OK_BOOLEAN_IGNORED"));
  assert.ok(codes.includes("OPTICS_STATUS_NO_SPAN"));
  assert.equal(Object.hasOwn(preview.candidates, "gen_ai.usage.input_tokens"), false);
  assert.equal(Object.hasOwn(preview.candidates, "gen_ai.request.model"), false);
});

test("application error sets error.type and does not read the ok boolean", () => {
  const preview = api.preview({
    source_shape: "canonical_observation",
    evidence_origin: "LOCAL_OBSERVATION",
    provider_id: "anthropic",
    provider_confidence: "CATALOG",
    destination_host: "api.anthropic.com",
    method: "POST",
    path: "/v1/messages",
    http_status: 500,
    application_status: "APPLICATION_ERROR",
    optics_status: "UNAVAILABLE",
    ok: true,
  });
  assert.equal(preview.candidates["error.type"], "application_error");
  assert.equal(preview.candidates["http.response.status_code"], 500);
  assert.equal(preview.candidates["gen_ai.provider.name"], "anthropic");
  assert.equal(Object.hasOwn(preview.candidates, "gen_ai.operation.name"), false);
  assert.equal(preview.span.client, "ERROR");
  assert.equal(preview.span.instrumentation, null);
  assert.equal(preview.emitted, false);
});

test("both error dimensions are a conflict and neither error.type is chosen", () => {
  const preview = api.preview({
    source_shape: "canonical_observation",
    evidence_origin: "LOCAL_OBSERVATION",
    http_status: 500,
    application_status: "APPLICATION_ERROR",
    optics_status: "OPTICS_ERROR",
  });
  assert.equal(Object.hasOwn(preview.candidates, "error.type"), false);
  assert.equal(preview.span.client, null);
  assert.equal(preview.span.instrumentation, null);
  assert.equal(preview.would_be_operational_if_i3_enabled, false);
  assert.ok(preview.omitted.some((item) => item.code === "STATUS_DIMENSION_CONFLICT"));
  assert.equal(preview.candidates["http.response.status_code"], 500);
});

test("live display does not promote provider or a hex-looking trace id", () => {
  const preview = api.preview({
    source_shape: "live_display",
    provider: "openai",
    hostname: "api.openai.com",
    method: "POST",
    path: "/v1/chat/completions",
    httpStatus: 200,
    applicationStatus: "SUCCESS",
    opticsStatus: "SUCCESS",
    bytes: 10,
    trace_id: "0123456789abcdef0123456789abcdef",
    duration_ms: 0,
  });
  assert.equal(Object.hasOwn(preview.candidates, "gen_ai.provider.name"), false);
  assert.equal(preview.candidates["gen_ai.operation.name"], "chat");
  assert.equal(preview.span.client, "OK");
  assert.equal(preview.span.instrumentation, null);
  assert.equal(preview.trace_context, null);
  assert.equal(preview.would_be_operational_if_i3_enabled, false);
  assert.equal(preview.operational_block, "LIVE_DISPLAY_IS_NOT_PROVENANCE");
  assert.ok(preview.omitted.some((item) => item.code === "OPTIMISTIC_DEFAULT_FORBIDDEN"));
  assert.ok(preview.omitted.some((item) => item.code === "LIVE_TRACE_ID_IS_RUN_BOUNDARY"));
  assert.ok(preview.omitted.some((item) => item.code === "LIVE_PROVIDER_NOT_PROMOTED"));
  assert.ok(preview.omitted.some((item) => item.code === "NOT_TOKEN_COUNTS"));
});

test("provider confidence and ambiguous catalog ids stay unmapped", () => {
  const missing = api.preview({
    source_shape: "canonical_observation",
    evidence_origin: "LOCAL_OBSERVATION",
    provider_id: "openai",
    destination_host: "api.openai.com",
  });
  assert.equal(Object.hasOwn(missing.candidates, "gen_ai.provider.name"), false);
  assert.equal(missing.candidates["server.address"], "api.openai.com");

  const google = api.preview({
    source_shape: "canonical_observation",
    evidence_origin: "LOCAL_OBSERVATION",
    provider_id: "google",
    provider_confidence: "CATALOG",
    destination_host: "generativelanguage.googleapis.com",
  });
  assert.equal(Object.hasOwn(google.candidates, "gen_ai.provider.name"), false);
});

function filledCanonical(origin) {
  return {
    source_shape: "canonical_observation",
    record_type: "observation_event",
    evidence_origin: origin,
    provider_id: "openai",
    provider_confidence: "CATALOG",
    destination_host: "api.openai.com",
    destination_port: 443,
    scheme: "https",
    method: "POST",
    path: "/v1/chat/completions",
    http_status: 200,
    application_status: "SUCCESS",
    optics_status: "UNAVAILABLE",
  };
}

test("product health and derived diagnostic produce no GenAI or HTTP candidates", () => {
  const blocked = [
    "gen_ai.provider.name",
    "gen_ai.operation.name",
    "http.request.method",
    "url.path",
    "http.response.status_code",
  ];
  const health = api.preview(filledCanonical("PRODUCT_HEALTH"));
  assert.deepEqual(health.candidates, {});
  assert.equal(health.span.client, null);
  assert.equal(health.span.instrumentation, null);
  assert.equal(health.trace_context, null);
  assert.equal(health.emitted, false);
  assert.equal(health.would_be_operational_if_i3_enabled, false);
  assert.equal(health.operational_block, "ORIGIN_NOT_OPERATIONAL");
  for (const name of blocked) assert.equal(Object.hasOwn(health.candidates, name), false, name);

  const derived = api.preview(filledCanonical("DERIVED_DIAGNOSTIC"));
  assert.deepEqual(derived.candidates, {});
  assert.equal(Object.hasOwn(derived.candidates, "gen_ai.provider.name"), false);
  assert.equal(derived.span.client, null);
  assert.equal(derived.emitted, false);
  assert.equal(derived.would_be_operational_if_i3_enabled, false);
  assert.equal(derived.operational_block, "ORIGIN_NOT_OPERATIONAL");

  for (const origin of ["TEST_FIXTURE", "IMPORTED"]) {
    const preview = api.preview(filledCanonical(origin));
    assert.deepEqual(preview.candidates, {});
    assert.equal(preview.span.client, null);
    assert.equal(preview.emitted, false);
    assert.equal(preview.would_be_operational_if_i3_enabled, false);
    assert.equal(preview.operational_block, "ORIGIN_NOT_OPERATIONAL");
  }
});

test("HTTP and URL names are not cited from the GenAI span page", () => {
  const doc = api.mappingDocument();
  const citations = doc.upstream.attribute_citations;
  const absent = ["http.request.method", "http.response.status_code", "url.path", "url.scheme"];
  assert.equal(citations.genai_client_span.document, "docs/gen-ai/gen-ai-spans.md");
  for (const name of absent) {
    assert.equal(citations.genai_client_span.includes.includes(name), false, name);
    assert.equal(citations.genai_client_span.excludes.includes(name), true, name);
    const entry = citations.definitions.find((item) => item.attribute === name);
    assert.ok(entry, name);
    assert.equal(entry.defined_in.includes("gen-ai-spans"), false, name);
    assert.equal(entry.cited_by.includes("docs/gen-ai/gen-ai-spans.md"), false, name);
    assert.equal(entry.cited_by.includes("docs/http/http-spans.md"), true, name);
  }
  assert.equal(citations.definitions.find((item) => item.attribute === "url.path").span_table, "http_server");
  const note = fs.readFileSync(path.join(ROOT, "docs/internal/ws7-otel-mapping/01-SEMANTIC-MAPPING.md"), "utf8");
  assert.equal(note.includes("by the v1.37.0 GenAI span table"), false);
  assert.match(note, /are not on that GenAI span page/);
  assert.match(note, /docs\/registry\/attributes\/http\.md/);
  assert.match(note, /docs\/registry\/attributes\/url\.md/);
  assert.match(note, /docs\/http\/http-spans\.md/);
  assert.match(note, /Optics does not export OTLP/);
});

test("live display with each blocked evidence origin returns an empty candidate set", () => {
  const blockedNames = [
    "gen_ai.provider.name",
    "gen_ai.operation.name",
    "http.request.method",
    "url.path",
    "server.address",
    "http.response.status_code",
  ];
  const origins = [
    "PRODUCT_HEALTH",
    "DERIVED_DIAGNOSTIC",
    "SIMULATED_DEMO",
    "TEST_FIXTURE",
    "IMPORTED",
    "OTHER_ORIGIN",
  ];
  for (const origin of origins) {
    const preview = api.preview({
      source_shape: "live_display",
      evidence_origin: origin,
      provider: "openai",
      hostname: "api.openai.com",
      method: "POST",
      path: "/v1/chat/completions",
      httpStatus: 200,
      applicationStatus: "SUCCESS",
      opticsStatus: "SUCCESS",
    });
    assert.deepEqual(preview.candidates, {}, origin);
    assert.equal(preview.span.client, null, origin);
    assert.equal(preview.span.instrumentation, null, origin);
    assert.equal(preview.emitted, false, origin);
    assert.equal(preview.would_be_operational_if_i3_enabled, false, origin);
    assert.equal(preview.trace_context, null, origin);
    const expectedBlock = origin === "SIMULATED_DEMO" ? "SIMULATED_DEMO_EXCLUDED" : "ORIGIN_NOT_OPERATIONAL";
    assert.equal(preview.operational_block, expectedBlock, origin);
    for (const name of blockedNames) {
      assert.equal(Object.hasOwn(preview.candidates, name), false, origin + " " + name);
    }
  }

  const unmarked = api.preview({
    source_shape: "live_display",
    hostname: "api.openai.com",
    method: "POST",
    path: "/v1/chat/completions",
    httpStatus: 200,
    applicationStatus: "SUCCESS",
  });
  assert.equal(unmarked.candidates["http.request.method"], "POST");
  assert.equal(unmarked.candidates["url.path"], "/v1/chat/completions");
  assert.equal(unmarked.candidates["gen_ai.operation.name"], "chat");
  assert.equal(unmarked.candidates["server.address"], "api.openai.com");
  assert.equal(unmarked.candidates["http.response.status_code"], 200);
  assert.equal(unmarked.span.client, "OK");
  assert.equal(unmarked.emitted, false);
  assert.equal(unmarked.would_be_operational_if_i3_enabled, false);
  assert.equal(unmarked.operational_block, "LIVE_DISPLAY_IS_NOT_PROVENANCE");

  const local = api.preview({
    source_shape: "live_display",
    evidence_origin: "LOCAL_OBSERVATION",
    hostname: "api.openai.com",
    method: "POST",
    path: "/v1/chat/completions",
    httpStatus: 200,
    applicationStatus: "SUCCESS",
  });
  assert.equal(local.candidates["http.request.method"], "POST");
  assert.equal(local.candidates["server.address"], "api.openai.com");
  assert.equal(local.span.client, "OK");
  assert.equal(local.emitted, false);
  assert.equal(local.would_be_operational_if_i3_enabled, false);
  assert.equal(local.operational_block, "LIVE_DISPLAY_IS_NOT_PROVENANCE");

  const note = fs.readFileSync(path.join(ROOT, "docs/internal/ws7-otel-mapping/01-SEMANTIC-MAPPING.md"), "utf8");
  assert.match(note, /both `live_display` and `canonical_observation`/);
  assert.match(note, /keeps its non-operational field candidates/);
});

test("simulated demo and missing origin produce no candidates", () => {
  const demo = api.preview({
    source_shape: "canonical_observation",
    evidence_origin: "SIMULATED_DEMO",
    provider_id: "openai",
    provider_confidence: "CATALOG",
    destination_host: "optics-demo.invalid",
    method: "POST",
    path: "/v1/chat/completions",
    http_status: 200,
    application_status: "SUCCESS",
  });
  assert.deepEqual(demo.candidates, {});
  assert.equal(demo.span.client, null);
  assert.equal(demo.would_be_operational_if_i3_enabled, false);
  assert.equal(demo.operational_block, "SIMULATED_DEMO_EXCLUDED");

  const missing = api.preview({
    source_shape: "canonical_observation",
    provider_id: "openai",
    provider_confidence: "CATALOG",
  });
  assert.deepEqual(missing.candidates, {});
  assert.equal(missing.operational_block, "ORIGIN_ABSENT_NOT_LOCAL");
});

test("asserted context is not copied and application-supplied W3C context stays unemitted", () => {
  const asserted = api.preview({
    source_shape: "canonical_observation",
    evidence_origin: "LOCAL_OBSERVATION",
    trace_id: "0123456789abcdef0123456789abcdef",
    trace_id_basis: "ASSERTED_CONTEXT",
    span_id: "0123456789abcdef",
  });
  assert.equal(asserted.trace_context, null);
  assert.ok(asserted.omitted.some((item) => item.code === "NEEDS_FOUNDER_DECISION"));

  const supplied = api.preview({
    source_shape: "canonical_observation",
    evidence_origin: "LOCAL_OBSERVATION",
    trace_id: "0123456789abcdef0123456789abcdef",
    trace_id_basis: "APPLICATION_SUPPLIED",
    span_id: "0123456789abcdef",
    parent_span_id: "fedcba9876543210",
  });
  assert.deepEqual(supplied.trace_context, {
    trace_id: "0123456789abcdef0123456789abcdef",
    span_id: "0123456789abcdef",
    parent_span_id: "fedcba9876543210",
  });
  assert.equal(supplied.emitted, false);
  assert.equal(supplied.would_be_operational_if_i3_enabled, true);
});

test("prohibited content is not copied into candidates", () => {
  const prompt = "secret prompt text";
  const preview = api.preview({
    source_shape: "canonical_observation",
    evidence_origin: "LOCAL_OBSERVATION",
    destination_host: "api.openai.com",
    prompt,
    messages: [{ role: "user", content: prompt }],
  });
  assert.equal(preview.prohibited_input_present, true);
  assert.equal(preview.would_be_operational_if_i3_enabled, false);
  assert.equal(JSON.stringify(preview).includes(prompt), false);
  assert.equal(Object.hasOwn(preview.candidates, "gen_ai.input.messages"), false);
});

test("partial, unavailable, query paths, and call lists are not collapsed", () => {
  const partial = api.preview({
    source_shape: "canonical_observation",
    evidence_origin: "LOCAL_OBSERVATION",
    application_status: "PARTIAL",
    calls: [{ http_status: 200 }, { http_status: 500 }],
  });
  assert.equal(partial.span.client, null);
  assert.equal(Object.hasOwn(partial.candidates, "http.response.status_code"), false);
  assert.equal(partial.would_be_operational_if_i3_enabled, false);
  assert.ok(partial.omitted.some((item) => item.code === "CALL_LIST_NOT_COLLAPSED"));

  const unavailable = api.preview({
    source_shape: "canonical_observation",
    evidence_origin: "LOCAL_OBSERVATION",
    application_status: "UNAVAILABLE",
    optics_status: "UNAVAILABLE",
  });
  assert.equal(unavailable.span.client, null);
  assert.equal(unavailable.span.instrumentation, null);
  assert.equal(Object.hasOwn(unavailable.candidates, "error.type"), false);

  const query = api.preview({
    source_shape: "canonical_observation",
    evidence_origin: "LOCAL_OBSERVATION",
    method: "POST",
    path: "/v1/chat/completions?api_key=secret",
  });
  assert.equal(Object.hasOwn(query.candidates, "url.path"), false);
  assert.equal(Object.hasOwn(query.candidates, "gen_ai.operation.name"), false);
  assert.equal(JSON.stringify(query).includes("api_key"), false);
});

test("string HTTP status is not coerced and default ports are not invented", () => {
  const preview = api.preview({
    source_shape: "canonical_observation",
    evidence_origin: "LOCAL_OBSERVATION",
    http_status: "200",
    application_status: "SUCCESS",
    scheme: "https",
    destination_host: "api.openai.com",
  });
  assert.equal(Object.hasOwn(preview.candidates, "http.response.status_code"), false);
  assert.equal(Object.hasOwn(preview.candidates, "server.port"), false);
  assert.equal(preview.span.client, null);
  assert.equal(preview.candidates["url.scheme"], "https");
});
}
