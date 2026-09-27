"use strict";

const assert = require("assert");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");
const test = require("node:test");

const ROOT = path.resolve(__dirname, "..", "..");
const CONTRACT = path.join(ROOT, "packages", "optics-evidence-contract");
const { validateEvidence, validateBytes, canonicalJson } = require(path.join(CONTRACT, "src", "validate.cjs"));
const privacy = require(path.join(CONTRACT, "src", "privacy.cjs"));
const unicodeProfile = require(path.join(CONTRACT, "src", "unicode_profile.cjs"));
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
  if (item.harness === "binary-buffer") return validateEvidence(Buffer.from([9, 8, 7]));
  if (item.harness === "binary-uint8array") return validateEvidence(new Uint8Array([9, 8, 7]));
  if (item.harness === "binary-memoryview") return validateEvidence(new Uint8Array([9, 8, 7]).subarray(1, 3));
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
  if (expect.completeness_inputs) {
    for (const [key, value] of Object.entries(expect.completeness_inputs)) {
      assert.deepEqual(result.completeness_inputs[key], value, item.id + " " + key);
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
  assert.equal(corpus.cases.length, 220);
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
  const names = [
    "validate.cjs", "privacy.cjs", "walk.cjs", "canonical.cjs", "unicode_profile.cjs",
    "validate.py", "privacy.py", "walk.py", "canonical.py", "unicode_profile.py",
  ];
  const joined = names.map((name) => fs.readFileSync(path.join(CONTRACT, "src", name), "utf8")).join("\n");
  assert.equal(joined.includes("require(\"http\")"), false);
  assert.equal(joined.includes("require(\"net\")"), false);
  assert.equal(joined.includes("import urllib"), false);
  assert.equal(joined.includes("import socket"), false);
  assert.equal(joined.includes("import requests"), false);
  const detectors = ["privacy.cjs", "privacy.py", "unicode_profile.cjs", "unicode_profile.py"].map((name) =>
    fs.readFileSync(path.join(CONTRACT, "src", name), "utf8")).join("\n");
  for (const token of [
    "isalpha", "isalnum", "casefold", "toLowerCase", "toUpperCase", ".lower(", ".upper(", "toLocale",
    ".normalize(", "unicodedata", "\\p{L}", "\\p{N}", "Intl.",
  ]) {
    assert.equal(detectors.includes(token), false, token);
  }
  const generator = fs.readFileSync(path.join(CONTRACT, "tools", "generate_unicode_profile.py"), "utf8");
  for (const token of ["urllib", "import socket", "requests", "import unicodedata", "unicodedata."]) {
    assert.equal(generator.includes(token), false, token);
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

function sha256File(file) {
  return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
}

function observationWith(pathValue) {
  const input = materialize(corpus.cases.find((item) => item.id === "clean-observation"));
  input.path = pathValue;
  return input;
}

test("pinned unicode tables match metadata and both languages", () => {
  const contractDir = path.join(CONTRACT, "contract");
  const meta = JSON.parse(fs.readFileSync(path.join(contractDir, "unicode-profile-metadata.json"), "utf8"));
  assert.equal(meta.profile_id, "PKG01-UCD-16.0.0");
  assert.equal(meta.profile_version, "16.0.0");
  assert.equal(unicodeProfile.profileId(), meta.profile_id);
  assert.equal(unicodeProfile.profileVersion(), meta.profile_version);
  const hashes = {};
  for (const item of meta.outputs) {
    const file = path.join(contractDir, item.name);
    const data = fs.readFileSync(file);
    assert.ok(data.length > 0 && data.length <= meta.max_file_bytes, item.name);
    hashes[item.name] = sha256File(file);
    assert.equal(hashes[item.name], item.sha256, item.name);
  }
  for (const item of meta.sources) {
    const file = path.join(contractDir, "unicode-source", item.name);
    const data = fs.readFileSync(file);
    assert.ok(data.length > 0 && data.length <= meta.max_file_bytes, item.name);
    assert.equal(sha256File(file), item.sha256, item.name);
  }
  const profile = JSON.parse(fs.readFileSync(path.join(contractDir, "unicode-profile.json"), "utf8"));
  const nodeVectors = profile.verification_vectors.map((vector) => {
    const normalized = unicodeProfile.normalizeCodes(vector.input, vector.form);
    assert.equal(normalized.ok, true, vector.form);
    assert.deepEqual(normalized.codes, vector.output);
    const category = vector.input.length === 1 ? unicodeProfile.categoryOf(vector.input[0]) : null;
    if (vector.input.length === 1 && vector.category) assert.equal(category, vector.category);
    return { codes: normalized.codes, category };
  });
  const flipped = Buffer.from(fs.readFileSync(path.join(contractDir, "unicode-profile.json")));
  flipped[0] ^= 0xff;
  const corrupt = crypto.createHash("sha256").update(flipped).digest("hex");
  assert.notEqual(corrupt, hashes["unicode-profile.json"]);
  const py = spawnSync("python3", ["-c", [
    "import json, sys",
    "sys.path.insert(0, " + JSON.stringify(path.join(CONTRACT, "src")) + ")",
    "import unicode_profile",
    "profile = json.load(open(" + JSON.stringify(path.join(contractDir, "unicode-profile.json")) + ", encoding='utf-8'))",
    "out = []",
    "for vector in profile['verification_vectors']:",
    "    normalized = unicode_profile.normalize_codes(vector['input'], vector['form'])",
    "    category = unicode_profile.category_of(vector['input'][0]) if len(vector['input']) == 1 else None",
    "    out.append({'ok': normalized['ok'], 'codes': normalized.get('codes'), 'category': category})",
    "print(json.dumps(out))",
  ].join("\n")], { encoding: "utf8" });
  assert.equal(py.status, 0, py.stderr);
  const pythonVectors = JSON.parse(py.stdout);
  assert.equal(pythonVectors.length, nodeVectors.length);
  for (let index = 0; index < nodeVectors.length; index += 1) {
    assert.equal(pythonVectors[index].ok, true);
    assert.deepEqual(pythonVectors[index].codes, nodeVectors[index].codes);
    assert.equal(pythonVectors[index].category, nodeVectors[index].category);
  }
  const generated = spawnSync("python3", [path.join(CONTRACT, "tools", "generate_unicode_profile.py")], { encoding: "utf8" });
  assert.equal(generated.status, 0, generated.stderr);
  for (const item of meta.outputs) assert.equal(sha256File(path.join(contractDir, item.name)), item.sha256, item.name);
});

test("unavailable unicode profile fails closed", () => {
  privacy.setProfileUnavailableForTest(true);
  try {
    const result = validateEvidence(observationWith("/pay/4111111111111111"));
    assert.equal(result.disposition, "REJECT_RECORD");
    assert.equal(result.reason_code, "VALIDATOR_FAULT");
    assert.equal(result.issue_location, "CONFIGURATION");
    assert.equal(result.record, null);
    assert.equal(result.diagnostics.scan_state, "UNAVAILABLE");
    assert.equal(result.diagnostics.privacy_event, null);
    assert.equal(result.diagnostics.unicode_profile_id, null);
    assert.equal(result.diagnostics.unicode_profile_version, null);
    assert.equal(result.completeness_inputs.privacy_invariant, "UNKNOWN");
    assert.equal(canonicalJson(result).includes("4111111111111111"), false);
  } finally {
    privacy.setProfileUnavailableForTest(false);
  }
  assert.equal(privacy.profileReady(), true);
});

test("independent probes outside the corpus", () => {
  const pan = validateEvidence(observationWith("/pay/4111\u200e111111111111"));
  assert.equal(pan.disposition, "REJECT_FIELD");
  assert.equal(pan.reason_code, "REDACTION_DROP");
  assert.equal(pan.diagnostics.privacy_event, "DESTINATION_COMPONENT_REDACTED");
  assert.equal(pan.diagnostics.scan_state, "FULL");
  assert.equal(Object.prototype.hasOwnProperty.call(pan.record, "path"), false);
  assert.equal(canonicalJson(pan).includes("4111111111111111"), false);
  assert.equal(canonicalJson(pan).includes("\u200e"), false);
  const secret = validateEvidence({
    record_type: "import_quarantine",
    schema_status: "unstable-pre-1.0",
    schema_version: 0,
    evidence_origin: "IMPORTED",
    original_evidence_origin: "LOCAL_OBSERVATION",
    accepted: false,
    imported_at: "2026-07-01T00:00:00.000Z",
    source_label: "s\u200b\u200bk-abcdefgh",
  });
  assert.equal(secret.disposition, "REJECT_FIELD");
  assert.equal(secret.reason_code, "DETECTOR_MATCH");
  assert.equal(secret.diagnostics.privacy_event, "DETECTOR_MATCH");
  assert.equal(Object.prototype.hasOwnProperty.call(secret.record, "source_label"), false);
  assert.equal(canonicalJson(secret).includes("sk-"), false);
  const unknown = validateEvidence(observationWith("/a\u0379@b.co"));
  assert.equal(unknown.disposition, "REJECT_FIELD");
  assert.equal(unknown.reason_code, "REDACTION_DROP");
  assert.equal(unknown.diagnostics.privacy_event, "DESTINATION_COMPONENT_REDACTED");
  assert.equal(Object.prototype.hasOwnProperty.call(unknown.record, "path"), false);
  assert.equal(canonicalJson(unknown).includes("\u0379"), false);
  const nested = validateEvidence({ record_type: "observation_event", payload: Buffer.from([9, 8, 7]) });
  assert.equal(nested.disposition, "REJECT_FIELD");
  assert.equal(nested.reason_code, "UNSUPPORTED_COMPLEX_VALUE");
  assert.equal(nested.record, null);
  assert.equal(canonicalJson(nested).includes("Buffer"), false);
});
