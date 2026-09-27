import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { checkPack } from "../../docs/planning/benchmark-framework/scripts/check-framework.mjs";
import { METRIC_IDS } from "../../docs/planning/benchmark-framework/scripts/framework-lib.mjs";
import {
  OFFICIAL_PLAN,
  UNMEASURED_REASONS,
  denyRequest,
  formatEt,
  measure,
  nearestRank,
  validateRegister,
} from "../../docs/internal/wave3/performance/scripts/qualify.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "../..");

const SMALL_PLAN = Object.freeze({
  latencyWarmup: 2,
  latencySamples: 11,
  throughputWindows: 3,
  throughputTargetNs: 20_000_000,
  evidenceDecisions: 4,
  evidenceRepetitions: 3,
});

function gitHead() {
  return execFileSync("git", ["rev-parse", "HEAD"], { cwd: ROOT, encoding: "utf8" }).trim();
}

test("nearest rank selects an observed sample", () => {
  assert.equal(nearestRank([1, 2, 3, 4, 5], 50), 3);
  assert.equal(nearestRank([1, 2, 3, 4, 5], 99), 5);
  const twoHundred = Array.from({ length: 200 }, (_value, index) => index + 1);
  assert.equal(nearestRank(twoHundred, 50), 100);
  assert.equal(nearestRank(twoHundred, 99), 198);
});

test("Eastern time keeps the September offset", () => {
  assert.equal(formatEt(new Date("2026-09-27T15:00:00.000Z")), "2026-09-27T11:00:00-04:00");
});

test("the Wave 2 scaffold stays unmeasured", () => {
  assert.deepEqual(checkPack(), []);
});

test("a small in-process run validates and rejects smuggled numbers", () => {
  const register = measure(SMALL_PLAN);
  assert.deepEqual(validateRegister(register), []);
  assert.equal(register.disposition, "MEASURED");
  assert.equal(register.subject.measured_tree_sha, gitHead());
  assert.equal(register.subject.runtime_tree_matches_starting_ref, true);
  assert.equal(register.environment.btf_vmlinux, false);
  assert.equal(register.environment.kernel_modules_dir, false);
  assert.equal(register.environment.producer_pod_verdict, "INELIGIBLE");
  assert.equal(register.eligible_plane_id, "NONE");
  assert.equal(register.host_attachment, false);
  assert.equal(register.production_slo, false);
  assert.equal(register.proved_external, false);
  assert.equal(register.w3_infra_req_1.provisioned_by_this_force, false);
  assert.deepEqual(register.workload_request, denyRequest());
  assert.deepEqual(register.metrics.map((metric) => metric.id), METRIC_IDS);

  const measuredIds = register.metrics.filter((metric) => metric.result === "MEASURED").map((metric) => metric.id);
  assert.deepEqual(measuredIds, ["evidence_growth", "decision_latency", "throughput"]);
  for (const metric of register.metrics) {
    if (metric.result === "NOT_MEASURED") {
      assert.equal(metric.result_value, null);
      assert.equal(metric.reason, UNMEASURED_REASONS[metric.id]);
    }
  }

  const latency = register.metrics.find((metric) => metric.id === "decision_latency");
  assert.equal(latency.unit, "ns");
  assert.equal(latency.sample_count, SMALL_PLAN.latencySamples);
  assert.equal(latency.instrument_overhead_subtracted, false);

  const smuggled = structuredClone(register);
  smuggled.metrics.find((metric) => metric.id === "cpu").result_value = 1;
  assert.ok(validateRegister(smuggled).some((error) => error.includes("cpu")));

  const edited = structuredClone(register);
  edited.metrics.find((metric) => metric.id === "decision_latency").result_value = 1;
  assert.ok(validateRegister(edited).some((error) => error.includes("decision_latency")));

  const attached = structuredClone(register);
  attached.host_attachment = true;
  assert.ok(validateRegister(attached).some((error) => error.includes("host attachment")));

  const slo = structuredClone(register);
  slo.production_slo = true;
  assert.ok(validateRegister(slo).some((error) => error.includes("slo")));

  const proved = structuredClone(register);
  proved.proved_external = true;
  assert.ok(validateRegister(proved).some((error) => error.includes("proved external")));

  const spent = structuredClone(register);
  spent.w3_infra_req_1.money_spent_by_this_force = true;
  assert.ok(validateRegister(spent).some((error) => error.includes("infra money")));
});

test("method text keeps each unmeasured reason", () => {
  const method = readFileSync(join(ROOT, "docs/internal/wave3/performance/01-METHOD.md"), "utf8");
  for (const reason of Object.values(UNMEASURED_REASONS)) {
    assert.equal(method.includes(reason), true, reason.slice(0, 48));
  }
  assert.equal(OFFICIAL_PLAN.latencySamples, 200);
  assert.equal(OFFICIAL_PLAN.throughputWindows, 5);
  assert.equal(OFFICIAL_PLAN.evidenceDecisions, 100);
});
