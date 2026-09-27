"use strict";

const fs = require("node:fs");
const path = require("node:path");

const { POSTURE } = require("./boundary.cjs");

const MAPPING_PATH = path.join(__dirname, "..", "mapping", "otel-semantic-mapping.json");

const ALLOWED_MAP_TARGETS = new Set([
  "gen_ai.provider.name",
  "gen_ai.operation.name",
  "http.request.method",
  "http.response.status_code",
  "url.path",
  "url.scheme",
  "server.address",
  "server.port",
  "error.type",
]);

const PROHIBITED_TARGETS = new Set([
  "gen_ai.input.messages",
  "gen_ai.output.messages",
  "gen_ai.system_instructions",
  "gen_ai.usage.input_tokens",
  "gen_ai.usage.output_tokens",
  "gen_ai.request.model",
  "gen_ai.response.model",
  "gen_ai.system",
  "gen_ai.conversation.id",
  "url.full",
  "host.name",
  "process.command",
  "process.command_line",
]);

const MAP_DISPOSITIONS = new Set(["MAP_WHEN_PRESENT", "MAP_ENUM"]);

function freezeDeep(value) {
  if (value === null || typeof value !== "object") return value;
  if (Array.isArray(value)) {
    for (const item of value) freezeDeep(item);
    return Object.freeze(value);
  }
  for (const key of Object.keys(value)) freezeDeep(value[key]);
  return Object.freeze(value);
}

function fail(message) {
  throw new Error("optics-otel-mapping: " + message);
}

const HTTP_URL_ATTRIBUTES = [
  "http.request.method",
  "http.response.status_code",
  "url.path",
  "url.scheme",
];

function validateAttributeCitations(doc) {
  const citations = doc.upstream && doc.upstream.attribute_citations;
  if (!citations || citations.tag !== "v1.37.0") fail("attribute_citations");
  const genai = citations.genai_client_span;
  if (!genai || genai.document !== "docs/gen-ai/gen-ai-spans.md") fail("genai_client_span");
  const includes = new Set(genai.includes || []);
  const excludes = new Set(genai.excludes || []);
  for (const name of HTTP_URL_ATTRIBUTES) {
    if (includes.has(name)) fail("genai span page lists " + name);
    if (!excludes.has(name)) fail("genai span page exclude missing " + name);
  }
  for (const name of ["server.address", "server.port", "error.type", "gen_ai.provider.name", "gen_ai.operation.name"]) {
    if (!includes.has(name)) fail("genai span page missing " + name);
    if (excludes.has(name)) fail("genai span page excludes " + name);
  }
  if (!Array.isArray(citations.definitions)) fail("attribute citation definitions");
  const defined = new Map();
  for (const entry of citations.definitions) {
    defined.set(entry.attribute, entry);
  }
  for (const name of HTTP_URL_ATTRIBUTES) {
    const entry = defined.get(name);
    if (!entry) fail("missing citation " + name);
    if (entry.defined_in == null || entry.defined_in === genai.document) fail("citation document " + name);
    if (String(entry.defined_in).includes("gen-ai-spans")) fail("citation document " + name);
    const citedBy = entry.cited_by || [];
    for (const document of citedBy) {
      if (document === genai.document || String(document).includes("gen-ai-spans")) fail("cited by genai span page " + name);
    }
    if (!citedBy.includes("docs/http/http-spans.md")) fail("http span citation " + name);
  }
  const method = defined.get("http.request.method");
  const status = defined.get("http.response.status_code");
  const path = defined.get("url.path");
  const scheme = defined.get("url.scheme");
  if (method.defined_in !== "docs/registry/attributes/http.md") fail("http.request.method definition");
  if (status.defined_in !== "docs/registry/attributes/http.md") fail("http.response.status_code definition");
  if (path.defined_in !== "docs/registry/attributes/url.md") fail("url.path definition");
  if (scheme.defined_in !== "docs/registry/attributes/url.md") fail("url.scheme definition");
  if (path.span_table !== "http_server") fail("url.path span table");
  if (method.span_table !== "http_client_and_server") fail("http.request.method span table");
  if (status.span_table !== "http_client_and_server") fail("http.response.status_code span table");
  if (scheme.span_table !== "http_client_and_server") fail("url.scheme span table");
}

function validateMapping(doc) {
  if (!doc || typeof doc !== "object") fail("mapping document is not an object");
  if (doc.mapping_id !== POSTURE.mapping_id) fail("mapping_id");
  if (doc.mapping_version !== POSTURE.mapping_version) fail("mapping_version");
  if (doc.schema_status !== POSTURE.schema_status) fail("schema_status");
  if (doc.stable_schema !== false) fail("stable_schema");
  if (doc.public_shipped_support !== false) fail("public_shipped_support");
  if (doc.otlp_export_authorized !== false) fail("otlp_export_authorized");
  if (doc.adapters_default_enabled !== false) fail("adapters_default_enabled");
  if (doc.i3_status !== "NOT_AUTHORIZED") fail("i3_status");
  if (doc.founder_decision_12 !== "unresolved") fail("founder_decision_12");
  if (doc.producer_classification !== POSTURE.producer_classification) fail("producer_classification");
  if (doc.schema_url !== null) fail("schema_url");
  if (!Array.isArray(doc.adapters) || doc.adapters.length !== 3) fail("adapters");
  const adapterIds = new Set();
  for (const adapter of doc.adapters) {
    if (adapter.default_enabled !== false) fail("adapter default_enabled " + adapter.id);
    if (adapter.implementation !== "NOT_PRESENT") fail("adapter implementation " + adapter.id);
    if (adapter.network !== false) fail("adapter network " + adapter.id);
    if (adapter.i3 !== "LATER") fail("adapter i3 " + adapter.id);
    adapterIds.add(adapter.id);
  }
  for (const id of ["otlp_traces", "otlp_metrics", "otlp_logs"]) {
    if (!adapterIds.has(id)) fail("missing adapter " + id);
  }
  if (!Array.isArray(doc.rows) || doc.rows.length < 1) fail("rows");
  const rowIds = new Set();
  for (const row of doc.rows) {
    if (rowIds.has(row.id)) fail("duplicate row " + row.id);
    rowIds.add(row.id);
    if (row.emitted_by_this_package !== false) fail("row emitted " + row.id);
    if (PROHIBITED_TARGETS.has(row.target) && row.disposition !== "DO_NOT_MAP") {
      fail("prohibited target mapped " + row.id);
    }
    if (MAP_DISPOSITIONS.has(row.disposition) && !ALLOWED_MAP_TARGETS.has(row.target)) {
      fail("map target not allowlisted " + row.id);
    }
  }
  for (const target of PROHIBITED_TARGETS) {
    if (!doc.rows.some((row) => row.target === target && row.disposition === "DO_NOT_MAP")) {
      fail("prohibited target has no DO_NOT_MAP row " + target);
    }
  }
  if (!Array.isArray(doc.provider_crosswalk) || doc.provider_crosswalk.length < 1) fail("crosswalk");
  const wellKnown = new Set(doc.gen_ai_provider_name_well_known_v1_37_0);
  const seenOptics = new Set();
  for (const entry of doc.provider_crosswalk) {
    if (seenOptics.has(entry.optics_provider_id)) fail("duplicate crosswalk " + entry.optics_provider_id);
    seenOptics.add(entry.optics_provider_id);
    if (!wellKnown.has(entry.gen_ai_provider_name)) fail("crosswalk outside v1.37.0 " + entry.gen_ai_provider_name);
    if (entry.well_known_in !== "v1.37.0") fail("crosswalk pin " + entry.optics_provider_id);
  }
  for (const id of doc.unmapped_provider_ids) {
    if (seenOptics.has(id)) fail("unmapped id is also mapped " + id);
  }
  if (!Array.isArray(doc.canonical_candidate_origins) || doc.canonical_candidate_origins.length !== 1) {
    fail("canonical_candidate_origins");
  }
  if (doc.canonical_candidate_origins[0] !== "LOCAL_OBSERVATION") fail("canonical_candidate_origins");
  validateAttributeCitations(doc);
  if (!Array.isArray(doc.operation_rules) || doc.operation_rules.length !== 1) fail("operation_rules");
  const operation = doc.operation_rules[0];
  if (operation.method !== "POST" || operation.path !== "/v1/chat/completions" || operation.gen_ai_operation_name !== "chat") {
    fail("operation rule");
  }
  if (!Array.isArray(doc.methods) || !doc.methods.includes("POST") || doc.methods.includes("unknown") === false) {
    fail("methods");
  }
  return doc;
}

function loadMapping() {
  const parsed = JSON.parse(fs.readFileSync(MAPPING_PATH, "utf8"));
  return freezeDeep(validateMapping(parsed));
}

module.exports = {
  ALLOWED_MAP_TARGETS,
  MAPPING_PATH,
  PROHIBITED_TARGETS,
  loadMapping,
  validateMapping,
};
