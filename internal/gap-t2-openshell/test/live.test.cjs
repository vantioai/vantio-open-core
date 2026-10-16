"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const { reconcile } = require("../src/index.cjs");
const { applyClock, joinFiles } = require("../harness/live.cjs");

const ROOT = path.resolve(__dirname, "..");
const FIXTURE = JSON.parse(fs.readFileSync(path.join(ROOT, "fixtures", "bypass-drill.json"), "utf8"));

function writeNdjson(dir, name, rows) {
  const file = path.join(dir, name);
  fs.writeFileSync(file, rows.map((row) => JSON.stringify(row)).join("\n") + "\n");
  return file;
}

function options(dir, extra) {
  return {
    hostClass: "vantio-owned",
    kernelPath: path.join(dir, "kernel.ndjson"),
    openshellPath: path.join(dir, "openshell.ndjson"),
    gatePath: path.join(dir, "gate.ndjson"),
    run: FIXTURE.run,
    ...extra,
  };
}

test("the file join matches the closed snapshot and stays off the live stack", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "t2-live-"));
  writeNdjson(dir, "kernel.ndjson", FIXTURE.kernel);
  writeNdjson(dir, "openshell.ndjson", FIXTURE.openshell);
  writeNdjson(dir, "gate.ndjson", FIXTURE.gate);
  const first = joinFiles(options(dir));
  const second = joinFiles(options(dir));
  const direct = reconcile(FIXTURE);
  assert.equal(first.status, "ok");
  assert.equal(first.label, "LAB_ONLY");
  assert.equal(first.live_stack, "ROADMAP");
  assert.equal(first.openshell_runtime, "not-executed");
  assert.equal(first.findings[0].indicator, direct.findings[0].indicator);
  assert.deepEqual(first.findings, second.findings);
  fs.rmSync(dir, { recursive: true, force: true });
});

test("a monotonic kernel clock stays unattributed until an offset makes it a bypass", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "t2-clock-"));
  const monotonic = 5000000000;
  const offset = FIXTURE.kernel[0].observed_at_ms - Math.floor(monotonic / 1000000);
  const kernel = { ...FIXTURE.kernel[0] };
  delete kernel.observed_at_ms;
  kernel.kernel_monotonic_ns = monotonic;
  writeNdjson(dir, "kernel.ndjson", [kernel]);
  writeNdjson(dir, "openshell.ndjson", FIXTURE.openshell);
  writeNdjson(dir, "gate.ndjson", FIXTURE.gate);
  const unbound = joinFiles(options(dir));
  assert.equal(unbound.findings[0].indicator, "UNATTRIBUTED");
  assert.equal(unbound.findings[0].reason, "kernel_time_not_unix");
  const bound = joinFiles(options(dir, { clockOffsetMs: offset }));
  assert.equal(bound.findings[0].indicator, "BYPASS_INDICATOR");
  assert.equal(bound.findings[0].reason, "no_matching_openshell_or_gate_record");
  assert.equal(bound.clock_offset_applied, true);
  const converted = applyClock(kernel, offset);
  assert.equal(converted.observed_at_ms, FIXTURE.kernel[0].observed_at_ms);
  assert.equal(converted.kernel_monotonic_ns, undefined);
  fs.rmSync(dir, { recursive: true, force: true });
});

test("the harness refuses another host class and a Navera path", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "t2-refuse-"));
  writeNdjson(dir, "kernel.ndjson", FIXTURE.kernel);
  writeNdjson(dir, "openshell.ndjson", FIXTURE.openshell);
  writeNdjson(dir, "gate.ndjson", FIXTURE.gate);
  const foreign = joinFiles(options(dir, { hostClass: "customer" }));
  assert.equal(foreign.status, "rejected");
  assert.equal(foreign.detail, "host_class");
  const named = path.join(dir, "navera-kernel.ndjson");
  fs.writeFileSync(named, "{}\n");
  const blocked = joinFiles(options(dir, { kernelPath: named }));
  assert.equal(blocked.status, "rejected");
  assert.equal(blocked.detail, "navera");
  fs.rmSync(dir, { recursive: true, force: true });
});

test("the harness does not open a socket or spawn a process", () => {
  const source = fs.readFileSync(path.join(ROOT, "harness", "live.cjs"), "utf8");
  for (const token of ["net", "http", "https", "child_process", "dgram"]) {
    assert.equal(source.includes(`require("node:${token}")`), false, token);
    assert.equal(source.includes(`require("${token}")`), false, token);
  }
  assert.equal(source.includes("bpf"), false);
});
