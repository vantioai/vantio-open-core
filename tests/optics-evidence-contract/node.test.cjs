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

function accessorInput() {
  const input = { record_type: "observation_event" };
  Object.defineProperty(input, "boom", {
    enumerable: true,
    get() {
      accessorInput.calls += 1;
      return "getter-secret";
    },
  });
  return input;
}
accessorInput.calls = 0;

function proxyInput() {
  return new Proxy({ record_type: "observation_event" }, {
    get(target, key) {
      proxyInput.calls += 1;
      return target[key];
    },
  });
}
proxyInput.calls = 0;

function classInput() {
  class Box {
    constructor() {
      this.record_type = "observation_event";
    }
  }
  return new Box();
}

function plainFn() {
  return "CANARYFUNC0001";
}

function functionFieldInput() {
  return { record_type: "observation_event", note: plainFn };
}

function workerResult(command, args) {
  const proc = spawnSync(command, args, { encoding: "utf8", timeout: 2000 });
  assert.equal(proc.status, 0, proc.stderr || (proc.error && proc.error.message));
  const newline = proc.stdout.indexOf("\n");
  assert.equal(proc.stdout.slice(0, newline), "CALLS 0");
  return JSON.parse(proc.stdout.slice(newline + 1));
}

function runCase(item) {
  if (item.harness === "accessor") {
    accessorInput.calls = 0;
    const result = validateEvidence(accessorInput());
    assert.equal(accessorInput.calls, 0, item.id);
    return result;
  }
  if (item.harness === "proxy") {
    proxyInput.calls = 0;
    const result = validateEvidence(proxyInput());
    assert.equal(proxyInput.calls, 0, item.id);
    return result;
  }
  if (item.harness === "class") return validateEvidence(classInput());
  if (item.harness === "function") return validateEvidence(plainFn);
  if (item.harness === "function-field") return validateEvidence(functionFieldInput());
  if (item.harness === "nonreturning") {
    return workerResult(process.execPath, [path.join(__dirname, "hostile_worker.cjs"), "validate"]);
  }
  return validateEvidence(materialize(item));
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
  if (expect.accepted) assert.deepEqual(result.fields.accepted, expect.accepted, item.id);
  if (expect.normalized) assert.deepEqual(result.fields.normalized, expect.normalized, item.id);
  if (item.utf8) {
    const data = materialize(item);
    for (const spec of item.utf8) {
      if (Object.prototype.hasOwnProperty.call(spec, "field")) {
        assert.equal(Buffer.byteLength(String(data[spec.field]), "utf8"), spec.bytes, item.id + " " + spec.field);
      }
      if (Object.prototype.hasOwnProperty.call(spec, "field_name_bytes")) {
        const hit = Object.keys(data).some((key) => Buffer.byteLength(key, "utf8") === spec.field_name_bytes);
        assert.equal(hit, true, item.id + " field name bytes");
      }
    }
  }
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
  for (const item of corpus.cases) out[item.id] = canonicalJson(runCase(item));
  return out;
}

if (process.argv.includes("--dump")) {
  const payload = JSON.stringify(dumpCanonical());
  if (process.env.PKG01_DUMP_PATH) fs.writeFileSync(process.env.PKG01_DUMP_PATH, payload);
  else process.stdout.write(payload);
  process.exit(0);
}

test("shared corpus dispositions and canary absence", () => {
  assert.equal(corpus.cases.length >= 110, true);
  for (const item of corpus.cases) assertResult(item, runCase(item));
  const banned = ["CANARY", "sk-", "AKIA", "ghp_", "AIza", "BEGIN PRIVATE", "canary.person", "sk-CANARYKEYNAME0001"];
  const dumped = dumpCanonical();
  for (const [id, canon] of Object.entries(dumped)) {
    for (const token of banned) assert.equal(canon.includes(token), false, id + " " + token);
  }
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

test("fail-open returns a detached application result", () => {
  const app = { ok: true, token: "APP_RESULT", nested: { n: 1 } };
  const secret = validateEvidence(
    { ...materialize(corpus.cases.find((item) => item.id === "path-openai")), path: "/sk-CANARYOPENAI0001" },
    { applicationResult: app },
  );
  assert.deepEqual(secret.application_result, { ok: true, token: "APP_RESULT", nested: { n: 1 } });
  assert.notStrictEqual(secret.application_result, app);
  assert.notStrictEqual(secret.application_result.nested, app.nested);
  app.nested.n = 2;
  assert.equal(secret.application_result.nested.n, 1);
  secret.application_result.nested.n = 9;
  assert.equal(app.nested.n, 2);
  assert.equal(canonicalJson(secret).includes("CANARYOPENAI"), false);
  const dropped = validateEvidence({ record_type: "observation_event", prompt: "sk-CANARYPROMPT0001" }, { applicationResult: app });
  assert.deepEqual(dropped.application_result.token, "APP_RESULT");
  assert.notStrictEqual(dropped.application_result, app);
  assert.equal(dropped.record, null);
  const fault = validateEvidence({ record_type: "observation_event" }, { applicationResult: app, injectFault: true });
  assert.equal(fault.disposition, "REJECT_RECORD");
  assert.equal(fault.reason_code, "VALIDATOR_FAULT");
  assert.deepEqual(fault.application_result.token, "APP_RESULT");
  assert.notStrictEqual(fault.application_result, app);
  assert.equal(canonicalJson(fault).includes("injected"), false);
  const bytes = validateBytes(Buffer.from([0xff, 0xfe, 0xfd]), { applicationResult: app });
  assert.equal(bytes.reason_code, "MALFORMED_UTF8");
  assert.deepEqual(bytes.application_result.token, "APP_RESULT");
  assert.notStrictEqual(bytes.application_result, app);
  const huge = "x".repeat(2000000);
  const started = Date.now();
  const bounded = validateEvidence(huge, { applicationResult: app });
  assert.equal(Date.now() - started < 2000, true);
  assert.equal(bounded.reason_code, "INPUT_BOUND");
  assert.deepEqual(bounded.application_result.token, "APP_RESULT");
  assert.notStrictEqual(bounded.application_result, app);
  assert.equal(canonicalJson(bounded).includes("xxxx"), false);
});

test("hostile getter, cycle, nesting, and freeze do not escape", () => {
  const input = { record_type: "observation_event", producer: "node_interceptor" };
  let calls = 0;
  Object.defineProperty(input, "boom", {
    enumerable: true,
    get() {
      calls += 1;
      throw new Error("getter-secret");
    },
  });
  const hostile = validateEvidence(input);
  assert.equal(calls, 0);
  assert.equal(hostile.reason_code, "ACCESSOR_PROPERTY_FORBIDDEN");
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

test("input mutation does not change a finished result", () => {
  const input = materialize(corpus.cases.find((item) => item.id === "mutable-nested-input"));
  input.nested = { n: 1 };
  const snapshot = structuredClone(input);
  const result = validateEvidence(input);
  assert.deepEqual(input, snapshot);
  input.destination_host = "changed.example";
  input.nested.n = 4;
  assert.equal(result.record.destination_host, "api.example.com");
  assert.equal(canonicalJson(result).includes("changed.example"), false);
  assert.equal(canonicalJson(result).includes("\"n\""), false);
});

test("isolated nonreturning getter terminates", () => {
  const started = Date.now();
  const proc = spawnSync(process.execPath, [path.join(__dirname, "hostile_worker.cjs"), "validate"], {
    encoding: "utf8",
    timeout: 2000,
  });
  assert.equal(proc.status, 0, proc.stderr);
  assert.equal(Date.now() - started < 2000, true);
  assert.equal(proc.stdout.startsWith("CALLS 0\n"), true);
  assert.equal(proc.stdout.includes("ACCESSOR_PROPERTY_FORBIDDEN"), true);
  const hang = spawnSync(process.execPath, [path.join(__dirname, "hostile_worker.cjs"), "hang"], {
    encoding: "utf8",
    timeout: 500,
  });
  assert.equal(hang.status, null);
  assert.equal(hang.error && hang.error.code, "ETIMEDOUT");
});

test("validator sources do not open network clients", () => {
  const files = ["validate.cjs", "privacy.cjs", "walk.cjs", "canonical.cjs"].map((name) =>
    fs.readFileSync(path.join(CONTRACT, "src", name), "utf8"));
  const py = ["validate.py", "privacy.py", "walk.py", "canonical.py"].map((name) =>
    fs.readFileSync(path.join(CONTRACT, "src", name), "utf8"));
  const joined = files.concat(py).join("\n");
  assert.equal(joined.includes("require(\"http\")"), false);
  assert.equal(joined.includes("require(\"net\")"), false);
  assert.equal(joined.includes("import urllib"), false);
  assert.equal(joined.includes("import socket"), false);
  assert.equal(joined.includes("import requests"), false);
  const detectors = [
    fs.readFileSync(path.join(CONTRACT, "src", "privacy.cjs"), "utf8"),
    fs.readFileSync(path.join(CONTRACT, "src", "privacy.py"), "utf8"),
  ].join("\n");
  for (const token of ["isalpha", "isalnum", "casefold", "toLowerCase", "toUpperCase", ".lower(", ".upper(", "toLocale"]) {
    assert.equal(detectors.includes(token), false, token);
  }
  const classes = JSON.parse(fs.readFileSync(path.join(CONTRACT, "contract", "detector-classes.json"), "utf8"));
  const bounds = JSON.parse(fs.readFileSync(path.join(CONTRACT, "contract", "normalization.json"), "utf8"));
  assert.equal(classes.length_unit, "UTF-8_BYTES");
  assert.equal(bounds.length_unit, "UTF-8_BYTES");
  assert.equal(classes.max_scan_bytes, bounds.bounds.max_string_chars);
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
