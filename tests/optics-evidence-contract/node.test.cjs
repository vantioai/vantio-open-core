"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");
const test = require("node:test");

const ROOT = path.resolve(__dirname, "..", "..");
const CONTRACT = path.join(ROOT, "packages", "optics-evidence-contract");
const { validateEvidence, validateBytes, canonicalJson } = require(path.join(CONTRACT, "src", "validate.cjs"));
const corpus = JSON.parse(fs.readFileSync(path.join(__dirname, "corpus.json"), "utf8"));
const REMEDIATION = new Set([
  "NONE",
  "REVIEW_DESTINATION_SHAPE",
  "REVIEW_SESSION_ID",
  "REVIEW_TRACE_CONTEXT",
  "REMOVE_PROHIBITED_CONTENT",
  "ORIGIN_UNMARKED",
  "DEMO_NOT_OPERATIONAL",
  "ENFORCEMENT_NOT_OPTICS",
  "VALIDATOR_INTERNAL",
]);

function materialize(item) {
  if (item.input) return structuredClone(item.input);
  const data = structuredClone(corpus.bases[item.base]);
  for (const key of item.omit || []) delete data[key];
  for (const [key, value] of Object.entries(item.patch || {})) data[key] = structuredClone(value);
  return data;
}

function assertResult(item, result) {
  const expect = item.expect;
  const canon = canonicalJson(result);
  assert.equal(result.schema_status, "unstable-pre-1.0");
  assert.equal(result.schema_version, 0);
  assert.equal(result.diagnostics.scope_complete, false);
  assert.equal(result.completeness_inputs.scope_complete, false);
  assert.equal(result.completeness_inputs.integrity_state, "UNKNOWN");
  assert.equal(result.completeness_inputs.sampling, "UNSAMPLED");
  assert.equal(result.compatibility.live_writer_modified, false);
  assert.equal(result.disposition, expect.disposition, item.id);
  assert.equal(result.reason_code, expect.reason_code, item.id);
  assert.equal(result.issue_location, expect.issue_location, item.id);
  assert.equal(result.optics_health_impact, expect.optics_health_impact, item.id);
  assert.deepEqual(result.completeness_impact, expect.completeness_impact, item.id);
  assert.equal(result.remediation_code, expect.remediation_code, item.id);
  assert.ok(REMEDIATION.has(result.remediation_code), item.id);
  assert.equal(result.record_emitted, expect.record_emitted, item.id);
  assert.equal(result.issue_location_label === "Provider fault", false);
  if (Object.prototype.hasOwnProperty.call(expect, "reader_origin_label")) {
    assert.equal(result.reader_origin_label, expect.reader_origin_label, item.id);
  }
  if (expect.issue_location_label) assert.equal(result.issue_location_label, expect.issue_location_label, item.id);
  if (expect.health_impact) assert.deepEqual(result.health_impact, expect.health_impact, item.id);
  if (expect.stripped) assert.deepEqual(result.fields.stripped, expect.stripped, item.id);
  if (expect.rejected) assert.deepEqual(result.fields.rejected, expect.rejected, item.id);
  if (expect.compatibility) assert.deepEqual(result.compatibility, expect.compatibility, item.id);
  if (expect.diagnostics) {
    for (const [key, value] of Object.entries(expect.diagnostics)) {
      assert.deepEqual(result.diagnostics[key], value, item.id + " " + key);
    }
  }
  if (expect.record_emitted) {
    for (const [key, value] of Object.entries(expect.record || {})) {
      assert.deepEqual(result.record[key], value, item.id + " " + key);
    }
    for (const key of expect.record_absent || []) {
      assert.equal(Object.prototype.hasOwnProperty.call(result.record, key), false, item.id + " absent " + key);
    }
  } else {
    assert.equal(result.record, null, item.id);
  }
  if (expect.event0) {
    const child = result.events[0];
    assert.ok(child, item.id);
    if (expect.event0.disposition) assert.equal(child.disposition, expect.event0.disposition, item.id);
    if (expect.event0.reason_code) assert.equal(child.reason_code, expect.event0.reason_code, item.id);
    if (expect.event0.reader_origin_label) assert.equal(child.reader_origin_label, expect.event0.reader_origin_label, item.id);
    for (const [key, value] of Object.entries(expect.event0.record || {})) {
      assert.deepEqual(child.record[key], value, item.id + " event " + key);
    }
  }
  for (const token of expect.forbidden || []) {
    assert.equal(canon.includes(token), false, item.id + " leaked " + token);
  }
}

function dumpCanonical() {
  const out = {};
  for (const item of corpus.cases) out[item.id] = canonicalJson(validateEvidence(materialize(item)));
  return out;
}

if (process.argv.includes("--dump")) {
  const payload = JSON.stringify(dumpCanonical());
  if (process.env.PKG01_DUMP_PATH) fs.writeFileSync(process.env.PKG01_DUMP_PATH, payload);
  else process.stdout.write(payload);
  process.exit(0);
}

test("shared corpus dispositions and canary absence", () => {
  assert.equal(corpus.cases.length >= 70, true);
  for (const item of corpus.cases) assertResult(item, validateEvidence(materialize(item)));
});

test("node and python canonical JSON match", () => {
  const dumpFile = path.join("/tmp", "pkg01-python-dump.json");
  const py = spawnSync("python3", [path.join(__dirname, "python_test.py"), "--dump"], {
    encoding: "utf8",
    env: { ...process.env, PKG01_DUMP_PATH: dumpFile },
  });
  assert.equal(py.status, 0, py.stderr);
  const theirs = JSON.parse(fs.readFileSync(dumpFile, "utf8"));
  const ours = dumpCanonical();
  for (const id of Object.keys(ours)) assert.equal(theirs[id], ours[id], id);
});

test("fail-open keeps the application result", () => {
  const app = { ok: true, token: "APP_RESULT" };
  const secret = validateEvidence(
    { ...materialize(corpus.cases.find((item) => item.id === "path-openai")), path: "/sk-CANARYOPENAI0001" },
    { applicationResult: app },
  );
  assert.equal(secret.application_result, app);
  assert.equal(canonicalJson(secret).includes("CANARYOPENAI"), false);
  const dropped = validateEvidence({ record_type: "observation_event", prompt: "sk-CANARYPROMPT0001" }, { applicationResult: app });
  assert.equal(dropped.application_result, app);
  assert.equal(dropped.record, null);
  const fault = validateEvidence({ record_type: "observation_event" }, { applicationResult: app, injectFault: true });
  assert.equal(fault.disposition, "REJECT_RECORD");
  assert.equal(fault.reason_code, "VALIDATOR_FAULT");
  assert.equal(fault.application_result, app);
  assert.equal(canonicalJson(fault).includes("injected"), false);
  const bytes = validateBytes(Buffer.from([0xff, 0xfe, 0xfd]), { applicationResult: app });
  assert.equal(bytes.reason_code, "MALFORMED_UTF8");
  assert.equal(bytes.application_result, app);
  const huge = "x".repeat(2000000);
  const started = Date.now();
  const bounded = validateEvidence(huge, { applicationResult: app });
  assert.equal(Date.now() - started < 2000, true);
  assert.equal(bounded.reason_code, "INPUT_BOUND");
  assert.equal(bounded.application_result, app);
  assert.equal(canonicalJson(bounded).includes("xxxx"), false);
});

test("hostile getter, cycle, nesting, and freeze do not escape", () => {
  const input = { record_type: "observation_event", producer: "node_interceptor" };
  Object.defineProperty(input, "boom", {
    enumerable: true,
    get() {
      throw new Error("getter-secret");
    },
  });
  const hostile = validateEvidence(input);
  assert.equal(hostile.reason_code, "HOSTILE_INPUT");
  assert.equal(canonicalJson(hostile).includes("getter-secret"), false);
  const cycle = {};
  cycle.self = cycle;
  const cycled = validateEvidence(cycle);
  assert.equal(cycled.reason_code, "CYCLE_REJECTED");
  let nested = { leaf: true };
  for (let i = 0; i < 20; i += 1) nested = { child: nested };
  const deep = validateEvidence(nested);
  assert.equal(deep.reason_code, "EXCESSIVE_NESTING");
  const frozen = Object.freeze({ record_type: "nope" });
  validateEvidence(frozen);
  assert.deepEqual(frozen, { record_type: "nope" });
  const lone = validateEvidence({
    record_type: "observation_event",
    schema_status: "unstable-pre-1.0",
    schema_version: 0,
    session_id: "\uD800",
    session_id_basis: "APPLICATION_SUPPLIED",
  });
  assert.equal(lone.reason_code, "SESSION_ID_REJECTED");
  assert.equal(lone.record == null || lone.record.session_id == null, true);
});

test("top-level array is not stored", () => {
  const result = validateEvidence(["sk-CANARYARRAY0001"]);
  assert.equal(result.reason_code, "PROMPT_COMPLETION_EXCLUDED");
  assert.equal(result.record, null);
  assert.equal(canonicalJson(result).includes("CANARYARRAY"), false);
});

test("scope stays off the live runtimes", () => {
  const cli = JSON.parse(fs.readFileSync(path.join(ROOT, "packages", "vantio-cli", "package.json"), "utf8"));
  const pyproject = fs.readFileSync(path.join(ROOT, "packages", "vantio-agent-sdk-py", "pyproject.toml"), "utf8");
  assert.equal(cli.version, "0.3.24");
  assert.match(pyproject, /version = "3.1.0"/);
  const pkg = JSON.parse(fs.readFileSync(path.join(CONTRACT, "package.json"), "utf8"));
  assert.equal(pkg.private, true);
  assert.equal(pkg.dependencies, undefined);
  const meta = JSON.parse(fs.readFileSync(path.join(CONTRACT, "contract", "contract-metadata.json"), "utf8"));
  assert.equal(meta.stable_schema, false);
  assert.equal(meta.schema_version, 0);
  assert.equal(meta.loaded_by_live_cli_0_3_24, false);
  assert.equal(meta.loaded_by_python_3_1_0, false);
  function walk(dir, hits) {
    for (const name of fs.readdirSync(dir)) {
      if (name === "node_modules" || name === ".git") continue;
      const full = path.join(dir, name);
      const stat = fs.statSync(full);
      if (stat.isDirectory()) walk(full, hits);
      else if (/\.(cjs|js|mjs|py|toml|json|md)$/.test(name)) {
        const text = fs.readFileSync(full, "utf8");
        if (text.includes("optics-evidence-contract")) hits.push(full);
      }
    }
  }
  const hits = [];
  walk(path.join(ROOT, "packages", "vantio-cli"), hits);
  walk(path.join(ROOT, "packages", "vantio-agent-sdk-py"), hits);
  assert.deepEqual(hits, []);
  assert.equal(fs.existsSync(path.join(CONTRACT, "store.sqlite")), false);
});

test("compatibility with the frozen display helper", () => {
  const optics = require(path.join(ROOT, "packages", "vantio-cli", "bin", "optics-cx.cjs"));
  assert.equal(optics.SCHEMA_STATUS, "unstable-pre-1.0");
  for (const status of [200, 302, 401, 500, 99, null]) {
    const expected = optics.applicationStatusFromHttp(status);
    const input = materialize(corpus.cases.find((item) => item.id === "clean-observation"));
    if (status == null) delete input.http_status;
    else input.http_status = status;
    if (expected === "NOT_OBSERVED") input.application_status = "NOT_OBSERVED";
    else input.application_status = expected;
    if (status != null && status >= 400 && status <= 599) input.issue_location = "PROVIDER_INTERACTION";
    else if (status != null && (status < 200 || status > 599)) input.issue_location = "UNKNOWN";
    else input.issue_location = "NONE";
    const result = validateEvidence(input);
    if (status == null) assert.equal(result.record.http_status, undefined);
    else if (status >= 100 && status <= 599) assert.equal(result.record.application_status, expected);
  }
  const outcome = fs.readFileSync(path.join(ROOT, "packages", "vantio-agent-sdk-py", "vantio", "_outcome.py"), "utf8");
  assert.match(outcome, /SCHEMA_STATUS = "unstable-pre-1.0"/);
});
