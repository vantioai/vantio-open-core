/**
 * Wave 3 Track 8 performance qualification.
 * Measures the in-process integrated runtime or records NOT_MEASURED.
 * Writes nothing unless invoked with --write.
 */

import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { arch, hostname, release, type } from "node:os";
import { basename, dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { validatePerformance } from "../../../../planning/benchmark-framework/scripts/check-framework.mjs";
import { METRIC_IDS } from "../../../../planning/benchmark-framework/scripts/framework-lib.mjs";
import peRuntime from "../../../../../internal/pe-integrated-runtime/src/index.cjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "../../../../..");
const STARTING_REF = "0cd36cf1d01c4db83a0a6999db0a322441f61c98";
const PRODUCER_CLASSIFICATION = "W3_PERFORMANCE_QUALIFICATION_READY_FOR_COUNCIL";
const SCAFFOLD_PATH = join(ROOT, "docs/planning/benchmark-framework/PERFORMANCE-SCAFFOLD.json");
const PROGRAM_REGISTER = join(ROOT, "docs/programs/production-readiness/wave3/PERFORMANCE-REGISTER.json");
const INTERNAL_REGISTER = join(ROOT, "docs/internal/wave3/performance/PERFORMANCE-REGISTER.json");
const ENVIRONMENT_DOC = join(ROOT, "docs/internal/wave3/performance/02-ENVIRONMENT.md");

const FROZEN_VERSIONS = Object.freeze({
  "@vantio/cli": "0.3.24",
  "@vantio/agent-sdk": "0.2.4",
  "vantio-agent-sdk": "3.1.0",
});

const PRODUCER = Object.freeze({
  agent: "bc-82b879c7-90f4-57f8-a61f-140ee17ec643",
  model: "Grok 4.7",
  reasoning: "xhigh",
  url: "https://cursor.com/agents/bc-82b879c7-90f4-57f8-a61f-140ee17ec643",
});

export const OFFICIAL_PLAN = Object.freeze({
  latencyWarmup: 30,
  latencySamples: 200,
  throughputWindows: 5,
  throughputTargetNs: 200_000_000,
  evidenceDecisions: 100,
  evidenceRepetitions: 5,
});

const MEASURED_IDS = Object.freeze(["decision_latency", "throughput", "evidence_growth"]);

export const UNMEASURED_REASONS = Object.freeze({
  cpu: "The metric asks for processor time added while the product is active. This run did not attach the product. The selected eligible plane is NONE. process.cpuUsage of the qualifier process was not used as this metric.",
  memory: "The metric asks for resident memory added while the product is active. This run did not attach the product. The selected eligible plane is NONE. process.memoryUsage of the qualifier process was not used as this metric.",
  disk: "The metric asks for disk bytes added while the product is active. This run did not attach the product and did not write a product data directory. A zero was not recorded.",
  startup: "The metric asks for time until the wrapped workload is usable. The integrated runtime does not wrap a workload. createRuntime was not timed as a substitute.",
  policy_load: "The metric asks for time to load the policy under test. The runtime receives a caller-supplied policy object and records policy versions in memory. It does not load a policy. No load was timed.",
  connection_latency: "The metric asks for time to establish the connection under test. The runtime does not open a connection. this_force_executed_network stays false. No connection was opened.",
  event_loss: "The metric asks for events the design says were dropped or never written. This run did not execute a drop-inducing workload. A zero taken from the successful egress path would restate that path. It was not recorded.",
  backpressure: "The metric asks for queue depth or refused inserts under a named load. The runtime has no queue and no refused-insert counter. Queue depth was not observed. A zero was not recorded.",
  reboot_recovery: "The metric asks for time and outcome after a reboot of the host under test. No reboot was performed. The eligible plane is NONE. W3-INFRA-REQ-1 was not provisioned.",
  degradation_recovery: "The metric asks for time and outcome after a stated degradation. No degradation was executed.",
  rollback: "The metric asks for time and outcome of the named rollback procedure. rollback_ingress records rolled_back_not_granted and does not apply a host rollback. That call was not timed as the procedure.",
  uninstall: "The metric asks for time and outcome of the named removal procedure. The uninstall operation records RECORDED_NOT_PERFORMED and refuses performed execution. The removal was not executed and was not timed.",
});

const BANNED_FIGURES = ["<5", "less than 5", "5 milliseconds"];

function assertClassification() {
  const measured = new Set(MEASURED_IDS);
  const reasons = Object.keys(UNMEASURED_REASONS);
  for (const id of METRIC_IDS) {
    const hasReason = Object.prototype.hasOwnProperty.call(UNMEASURED_REASONS, id);
    if (measured.has(id) === hasReason) {
      throw new Error(`metric classification overlap ${id}`);
    }
  }
  for (const id of reasons) {
    if (!METRIC_IDS.includes(id)) throw new Error(`unknown unmeasured metric ${id}`);
  }
  if (measured.size + reasons.length !== METRIC_IDS.length) {
    throw new Error("metric classification count");
  }
}

assertClassification();

export function denyRequest() {
  return {
    op: "egress",
    input: {
      policy: {
        enforce: true,
        dry_run: false,
        scope: "llm_and_named",
        blocked_hosts: ["evil.example"],
      },
      path: { id: "app_fetch" },
      attempt: {
        policy_loaded: true,
        destination: {
          hostname: "evil.example",
          port: "443",
          protocol: "https",
          in_product_scope: true,
        },
      },
    },
  };
}

export function nearestRank(sorted, percentile) {
  const count = sorted.length;
  if (count === 0) throw new Error("nearest rank of an empty sample");
  const rank = Math.ceil((percentile / 100) * count);
  const index = Math.min(count, Math.max(1, rank)) - 1;
  return sorted[index];
}

export function formatEt(date) {
  const parts = Object.fromEntries(new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
    timeZoneName: "longOffset",
  }).formatToParts(date).map((part) => [part.type, part.value]));
  const offset = parts.timeZoneName.replace("GMT", "");
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}:${parts.second}${offset}`;
}

function stamp(date = new Date()) {
  return {
    started_at_utc: date.toISOString(),
    started_at_et: formatEt(date),
  };
}

function cloneRequest(request) {
  return {
    op: request.op,
    input: {
      policy: {
        ...request.input.policy,
        blocked_hosts: request.input.policy.blocked_hosts.slice(),
      },
      path: { ...request.input.path },
      attempt: {
        ...request.input.attempt,
        destination: { ...request.input.attempt.destination },
      },
    },
  };
}

function workloadProblem(result) {
  if (!result || result.ok !== true) return "not_ok";
  if (result.host_attachment !== false) return "host_attachment";
  if (result.ebpf_loaded !== false) return "ebpf_loaded";
  if (result.kernel_executed !== false) return "kernel_executed";
  if (result.active_protection !== false) return "active_protection";
  if (result.applied_to_host !== false) return "applied_to_host";
  if (!result.quote || result.quote.result !== "DENIED") return "disposition";
  if (result.quote.would_wire_applied !== false) return "would_wire_applied";
  if (result.quote.this_force_executed_host !== false) return "executed_host";
  if (result.quote.this_force_executed_network !== false) return "executed_network";
  if (!result.planes || !result.planes.DECISION || result.planes.DECISION.status !== "DENIED") return "plane";
  if (!result.planes.APPLICATION_ENFORCEMENT || result.planes.APPLICATION_ENFORCEMENT.applied !== false) {
    return "application_applied";
  }
  if (!result.planes.HOST_ENFORCEMENT || result.planes.HOST_ENFORCEMENT.applied !== false) return "host_applied";
  if (result.planes.HOST_ENFORCEMENT.kernel_executed !== false) return "host_kernel";
  return null;
}

function requireWorkload(result, metricId) {
  const problem = workloadProblem(result);
  if (problem) throw new Error(`${metricId} workload rejected: ${problem}`);
}

function asSafeInteger(value, label) {
  const number = Number(value);
  if (!Number.isSafeInteger(number) || number < 0) throw new Error(`${label} is not a safe non-negative integer`);
  return number;
}

function loadScaffold() {
  const scaffold = JSON.parse(readFileSync(SCAFFOLD_PATH, "utf8"));
  const ids = scaffold.metrics.map((metric) => metric.id);
  if (ids.join(",") !== METRIC_IDS.join(",")) throw new Error("scaffold metric order");
  return new Map(scaffold.metrics.map((metric) => [metric.id, metric]));
}

function readFrozenVersions() {
  const cli = JSON.parse(readFileSync(join(ROOT, "packages/vantio-cli/package.json"), "utf8")).version;
  const sdk = JSON.parse(readFileSync(join(ROOT, "packages/vantio-agent-sdk/package.json"), "utf8")).version;
  const python = readFileSync(join(ROOT, "packages/vantio-agent-sdk-py/pyproject.toml"), "utf8");
  const match = python.match(/^version = "([^"]+)"$/m);
  return {
    "@vantio/cli": cli,
    "@vantio/agent-sdk": sdk,
    "vantio-agent-sdk": match ? match[1] : "UNPARSED",
  };
}

function hashRuntimeFiles(files) {
  const hash = createHash("sha256");
  for (const file of files) {
    hash.update(file.name);
    hash.update("\0");
    hash.update(file.body);
    hash.update("\0");
  }
  return hash.digest("hex");
}

function worktreeRuntimeFiles() {
  const dir = join(ROOT, "internal/pe-integrated-runtime/src");
  return readdirSync(dir).filter((name) => name.endsWith(".cjs")).sort().map((name) => ({
    name,
    body: readFileSync(join(dir, name)),
  }));
}

function gitRuntimeFiles() {
  const listed = execFileSync("git", ["ls-tree", "-r", "--name-only", STARTING_REF, "internal/pe-integrated-runtime/src"], {
    cwd: ROOT,
    encoding: "utf8",
  }).trim();
  const names = listed.split("\n").filter((name) => name.endsWith(".cjs")).sort();
  return names.map((name) => ({
    name: basename(name),
    body: execFileSync("git", ["show", `${STARTING_REF}:${name}`], { cwd: ROOT }),
  }));
}

function envOrUnobserved(name) {
  const value = process.env[name];
  if (typeof value === "string" && value.length > 0) return value;
  return "NOT_OBSERVED";
}

function probeEnvironment() {
  const cgroup = existsSync("/proc/1/cgroup") ? readFileSync("/proc/1/cgroup", "utf8").trim() : "UNREADABLE";
  const podMatch = cgroup.match(/pod-([^/]+)/);
  const podId = podMatch ? `pod-${podMatch[1]}` : "UNPARSED";
  let osRelease = "UNREADABLE";
  if (existsSync("/etc/os-release")) {
    const pretty = readFileSync("/etc/os-release", "utf8").match(/^PRETTY_NAME="(.*)"$/m);
    osRelease = pretty ? pretty[1] : "UNPARSED";
  }
  const porcelain = execFileSync("git", ["status", "--porcelain"], { cwd: ROOT, encoding: "utf8" }).replace(/\n$/, "");
  const worktreeHash = hashRuntimeFiles(worktreeRuntimeFiles());
  const startingHash = hashRuntimeFiles(gitRuntimeFiles());
  const environmentPublicId = envOrUnobserved("CURSOR_ENVIRONMENT_PUBLIC_ID");
  const btfPresent = existsSync("/sys/kernel/btf/vmlinux");
  const modulesPresent = existsSync(`/lib/modules/${release()}`);
  const absent = [];
  if (!btfPresent) absent.push("/sys/kernel/btf/vmlinux");
  if (!modulesPresent) absent.push(`/lib/modules/${release()}`);
  const producerPodVerdict = absent.length > 0 ? "INELIGIBLE" : "NOT_SELECTED";
  const producerPodVerdictBasis = absent.length > 0
    ? `Observed absent: ${absent.join(", ")}. This force did not select the producer pod.`
    : "The kernel files named here were present. This force did not select the producer pod and did not attach.";
  return {
    plane_class: "cursor-coding-pod",
    selected_plane_id: "NONE",
    producer_pod_verdict: producerPodVerdict,
    producer_pod_verdict_basis: producerPodVerdictBasis,
    pod_id: podId,
    cgroup,
    hostname: hostname(),
    uname: `${type()} ${release()} ${arch()}`,
    os_release: osRelease,
    node: process.version,
    btf_vmlinux: btfPresent,
    kernel_modules_dir: modulesPresent,
    cursor_environment_public_id: environmentPublicId,
    cursor_environment_public_id_source: environmentPublicId === "NOT_OBSERVED" ? "NOT_OBSERVED" : "CURSOR_ENVIRONMENT_PUBLIC_ID",
    cursor_environment_version_public_id: envOrUnobserved("CURSOR_ENVIRONMENT_VERSION_PUBLIC_ID"),
    cursor_environment_build_id: envOrUnobserved("CURSOR_ENVIRONMENT_BUILD_ID"),
    host_attachment: false,
    runtime_sources_sha256: worktreeHash,
    runtime_tree_matches_starting_ref: worktreeHash === startingHash,
    measured_tree_sha: execFileSync("git", ["rev-parse", "HEAD"], { cwd: ROOT, encoding: "utf8" }).trim(),
    worktree_dirty: porcelain.length > 0,
    worktree_porcelain: porcelain,
  };
}

function measureLatency(request, plan, scaffold) {
  for (let index = 0; index < plan.latencyWarmup; index += 1) {
    const runtime = peRuntime.createRuntime();
    requireWorkload(peRuntime.integrate(runtime, cloneRequest(request)), "decision_latency");
  }
  const started = stamp();
  const samples = [];
  for (let index = 0; index < plan.latencySamples; index += 1) {
    const runtime = peRuntime.createRuntime();
    const input = cloneRequest(request);
    const begin = process.hrtime.bigint();
    const result = peRuntime.integrate(runtime, input);
    const elapsed = asSafeInteger(process.hrtime.bigint() - begin, "decision_latency");
    requireWorkload(result, "decision_latency");
    samples.push(elapsed);
  }
  const sorted = samples.slice().sort((left, right) => left - right);
  const percentiles = {
    method: "nearest_rank",
    population: "this_sample_only",
    p50: nearestRank(sorted, 50),
    p90: nearestRank(sorted, 90),
    p99: nearestRank(sorted, 99),
  };
  return {
    id: "decision_latency",
    result: "MEASURED",
    dimensions: scaffold.get("decision_latency").dimensions,
    unit: "ns",
    workload: "egress_application_deny_on_fresh_runtime",
    instrument: "process.hrtime.bigint",
    instrument_overhead_subtracted: false,
    started_at_utc: started.started_at_utc,
    started_at_et: started.started_at_et,
    sample_count: samples.length,
    warmup_excluded: plan.latencyWarmup,
    percentiles,
    result_value: percentiles.p50,
    result_statistic: "p50",
    estimate: "PROHIBITED",
    production_slo: false,
    binds_claim_stage: false,
    host_attachment: false,
    eligible_plane_id: "NONE",
    samples,
    note: "Wall-clock nanoseconds for one in-process egress application DENIED decision on a fresh runtime. The timer wraps integrate only. The decision does not apply a wire action. Sample percentiles describe this run. This is not an SLO and it does not move a claim stage.",
  };
}

function runWindow(request, targetNs) {
  const runtime = peRuntime.createRuntime();
  const input = cloneRequest(request);
  const target = BigInt(targetNs);
  const begin = process.hrtime.bigint();
  let completed = 0;
  while (process.hrtime.bigint() - begin < target) {
    const result = peRuntime.integrate(runtime, input);
    completed += 1;
    requireWorkload(result, "throughput");
  }
  return {
    completed,
    window_ns: asSafeInteger(process.hrtime.bigint() - begin, "throughput window"),
  };
}

function compareRate(left, right) {
  const leftProduct = BigInt(left.completed) * BigInt(right.window_ns);
  const rightProduct = BigInt(right.completed) * BigInt(left.window_ns);
  if (leftProduct < rightProduct) return -1;
  if (leftProduct > rightProduct) return 1;
  return 0;
}

function measureThroughput(request, plan, scaffold) {
  runWindow(request, plan.throughputTargetNs);
  const started = stamp();
  const samples = [];
  for (let index = 0; index < plan.throughputWindows; index += 1) {
    samples.push(runWindow(request, plan.throughputTargetNs));
  }
  const sorted = samples.slice().sort(compareRate);
  const percentiles = {
    method: "nearest_rank",
    population: "this_sample_only",
    p50: nearestRank(sorted, 50),
    p90: nearestRank(sorted, 90),
    p99: nearestRank(sorted, 99),
  };
  return {
    id: "throughput",
    result: "MEASURED",
    dimensions: scaffold.get("throughput").dimensions,
    unit: "decisions",
    workload: "egress_application_deny_until_target_window",
    instrument: "process.hrtime.bigint",
    instrument_overhead_subtracted: false,
    started_at_utc: started.started_at_utc,
    started_at_et: started.started_at_et,
    sample_count: samples.length,
    warmup_excluded: 1,
    window_target_ns: plan.throughputTargetNs,
    window_rule: "The loop stops after the integrate call that crosses the target. window_ns is the actual elapsed time and includes that call. A disposition guard runs inside the window.",
    percentiles,
    result_value: percentiles.p50.completed,
    window_ns: percentiles.p50.window_ns,
    result_statistic: "p50_window_completed_decisions",
    estimate: "PROHIBITED",
    production_slo: false,
    binds_claim_stage: false,
    host_attachment: false,
    eligible_plane_id: "NONE",
    samples,
    note: `Completed in-process egress application DENIED decisions in one measured window. Nearest-rank percentiles use these ${plan.throughputWindows} windows only. They are sample percentiles, not a population tail, not network throughput, and not an SLO.`,
  };
}

function measureEvidence(request, plan, scaffold) {
  const started = stamp();
  const samples = [];
  for (let repetition = 0; repetition < plan.evidenceRepetitions; repetition += 1) {
    const runtime = peRuntime.createRuntime();
    for (let index = 0; index < plan.evidenceDecisions; index += 1) {
      requireWorkload(peRuntime.integrate(runtime, cloneRequest(request)), "evidence_growth");
    }
    if (runtime.evidence.length !== plan.evidenceDecisions) {
      throw new Error(`evidence_growth count ${runtime.evidence.length}`);
    }
    let bytes = 0;
    for (const row of runtime.evidence) {
      if (row.active_protection !== false) throw new Error("evidence_growth active_protection");
      if (row.independent_verification_status !== "NOT_INDEPENDENTLY_VERIFIED") {
        throw new Error("evidence_growth verification");
      }
      bytes += Buffer.byteLength(JSON.stringify(row), "utf8");
    }
    samples.push(bytes);
  }
  if (new Set(samples).size !== 1) {
    throw new Error(`evidence_growth varied across repetitions: ${samples.join(",")}`);
  }
  const sorted = samples.slice().sort((left, right) => left - right);
  const percentiles = {
    method: "nearest_rank",
    population: "this_sample_only",
    p50: nearestRank(sorted, 50),
    p90: nearestRank(sorted, 90),
    p99: nearestRank(sorted, 99),
  };
  return {
    id: "evidence_growth",
    result: "MEASURED",
    dimensions: scaffold.get("evidence_growth").dimensions,
    unit: "bytes",
    workload: "in_memory_evidence_rows_from_fixed_egress_deny_count",
    instrument: "Buffer.byteLength(JSON.stringify(evidence_row), utf8)",
    instrument_overhead_subtracted: false,
    started_at_utc: started.started_at_utc,
    started_at_et: started.started_at_et,
    sample_count: samples.length,
    warmup_excluded: 0,
    decisions_per_repetition: plan.evidenceDecisions,
    runtime_clock: "createRuntime default, which returns 0",
    storage: "in_memory_evidence_list",
    percentiles,
    result_value: percentiles.p50,
    result_statistic: "p50",
    estimate: "PROHIBITED",
    production_slo: false,
    binds_claim_stage: false,
    host_attachment: false,
    eligible_plane_id: "NONE",
    samples,
    note: "UTF-8 JSON bytes of the in-memory evidence rows appended by a fixed count of egress application DENIED decisions. The runtime clock returns 0, so the bytes do not include a wall-clock timestamp. This is not disk growth and not an independent verification.",
  };
}

function unmeasuredRow(id, scaffold) {
  return {
    id,
    result: "NOT_MEASURED",
    dimensions: scaffold.get(id).dimensions,
    unit: null,
    workload: "NOT_DEFINED",
    instrument: "NOT_DEFINED",
    started_at_utc: null,
    started_at_et: null,
    sample_count: "NOT_MEASURED",
    percentiles: "NOT_MEASURED",
    result_value: null,
    estimate: "PROHIBITED",
    production_slo: false,
    binds_claim_stage: false,
    host_attachment: false,
    eligible_plane_id: "NONE",
    reason: UNMEASURED_REASONS[id],
  };
}

export function measure(plan = OFFICIAL_PLAN) {
  const scaffold = loadScaffold();
  const request = denyRequest();
  const environment = probeEnvironment();
  const runStarted = stamp();
  const measured = {
    decision_latency: measureLatency(request, plan, scaffold),
    throughput: measureThroughput(request, plan, scaffold),
    evidence_growth: measureEvidence(request, plan, scaffold),
  };
  const metrics = METRIC_IDS.map((id) => (measured[id] ? measured[id] : unmeasuredRow(id, scaffold)));
  const measuredCount = metrics.filter((metric) => metric.result === "MEASURED").length;
  const versions = readFrozenVersions();
  return {
    schema: "vantio.wave3.performance-register/v1",
    document: "PERFORMANCE-REGISTER",
    audience: "INTERNAL_RESTRICTED",
    schema_status: "unstable-pre-1.0",
    producer_classification: PRODUCER_CLASSIFICATION,
    success_token: PRODUCER_CLASSIFICATION,
    council_status: "PENDING_INDEPENDENT_COUNCIL",
    council_verdict: null,
    self_certified_council_pass: false,
    disposition: measuredCount > 0 ? "MEASURED" : "NOT_MEASURED",
    disposition_meaning: "MEASURED means at least one scaffold metric has a measurement record from this run. NOT_MEASURED means every scaffold metric lacks one. Neither value is a production SLO, a customer proof, or a claim-stage pass.",
    binds_claim_stage: false,
    production_slo: false,
    customer_proof: false,
    host_attachment: false,
    host_attachment_status: "HOST_ATTACHMENT_FALSE",
    host_attachment_action: "NOT_PERFORMED",
    ebpf_loaded: false,
    kernel_executed: false,
    active_protection: false,
    eligible_plane_id: "NONE",
    proved_external: false,
    clean_host_internal_proof: false,
    stranger_host_executed: false,
    customer_deployed: false,
    announced: false,
    credentials_issued: false,
    money_spent: false,
    frozen_cli_reopened: false,
    python_sdk_mutated: false,
    node_sdk_mutated: false,
    w3_infra_req_1: {
      id: "W3-INFRA-REQ-1",
      provisioned_by_this_force: false,
      money_spent_by_this_force: false,
      credentials_issued_by_this_force: false,
    },
    frozen_versions: versions,
    frozen_versions_reopened: false,
    producer: PRODUCER,
    subject: {
      repository: "vantioai/vantio-open-core",
      runtime_module: "internal/pe-integrated-runtime",
      runtime_producer_classification: "W3_PE_INTEGRATED_RUNTIME_READY_FOR_COUNCIL",
      starting_ref: STARTING_REF,
      measured_tree_sha: environment.measured_tree_sha,
      runtime_sources_sha256: environment.runtime_sources_sha256,
      runtime_tree_matches_starting_ref: environment.runtime_tree_matches_starting_ref,
      worktree_dirty: environment.worktree_dirty,
      worktree_porcelain: environment.worktree_porcelain,
    },
    environment: {
      plane_class: environment.plane_class,
      selected_plane_id: environment.selected_plane_id,
      producer_pod_verdict: environment.producer_pod_verdict,
      producer_pod_verdict_basis: environment.producer_pod_verdict_basis,
      pod_id: environment.pod_id,
      cgroup: environment.cgroup,
      hostname: environment.hostname,
      uname: environment.uname,
      os_release: environment.os_release,
      node: environment.node,
      btf_vmlinux: environment.btf_vmlinux,
      kernel_modules_dir: environment.kernel_modules_dir,
      cursor_environment_public_id: environment.cursor_environment_public_id,
      cursor_environment_public_id_source: environment.cursor_environment_public_id_source,
      cursor_environment_version_public_id: environment.cursor_environment_version_public_id,
      cursor_environment_build_id: environment.cursor_environment_build_id,
      host_attachment: false,
    },
    run_started_at_utc: runStarted.started_at_utc,
    run_started_at_et: runStarted.started_at_et,
    framework: {
      scaffold: "docs/planning/benchmark-framework/PERFORMANCE-SCAFFOLD.json",
      result_rule: "A metric is MEASURED only when the record has an instrument, a workload, a start time, a sample count, and a result value taken from that run.",
      scaffold_left_not_measured: true,
      percentile_method: "nearest_rank",
      percentile_rank: "ceil(p/100*n), then that ordered sample",
    },
    plan: {
      latency_warmup: plan.latencyWarmup,
      latency_samples: plan.latencySamples,
      throughput_warmup_windows: 1,
      throughput_windows: plan.throughputWindows,
      throughput_target_ns: plan.throughputTargetNs,
      evidence_decisions: plan.evidenceDecisions,
      evidence_repetitions: plan.evidenceRepetitions,
    },
    workload_request: request,
    metrics,
  };
}

function sameWindow(left, right) {
  return left && right && left.completed === right.completed && left.window_ns === right.window_ns;
}

function percentilesMatch(metric) {
  if (metric.id === "throughput") {
    const sorted = metric.samples.slice().sort(compareRate);
    const expected = {
      method: "nearest_rank",
      population: "this_sample_only",
      p50: nearestRank(sorted, 50),
      p90: nearestRank(sorted, 90),
      p99: nearestRank(sorted, 99),
    };
    return sameWindow(metric.percentiles.p50, expected.p50)
      && sameWindow(metric.percentiles.p90, expected.p90)
      && sameWindow(metric.percentiles.p99, expected.p99)
      && metric.percentiles.method === "nearest_rank"
      && metric.percentiles.population === "this_sample_only"
      && metric.result_value === expected.p50.completed
      && metric.window_ns === expected.p50.window_ns;
  }
  const sorted = metric.samples.slice().sort((left, right) => left - right);
  const expected = {
    p50: nearestRank(sorted, 50),
    p90: nearestRank(sorted, 90),
    p99: nearestRank(sorted, 99),
  };
  return metric.percentiles.method === "nearest_rank"
    && metric.percentiles.population === "this_sample_only"
    && metric.percentiles.p50 === expected.p50
    && metric.percentiles.p90 === expected.p90
    && metric.percentiles.p99 === expected.p99
    && metric.result_value === expected.p50;
}

export function validateRegister(register) {
  const errors = [];
  if (!register || register.producer_classification !== PRODUCER_CLASSIFICATION) errors.push("classification");
  if (register.success_token !== PRODUCER_CLASSIFICATION) errors.push("success token");
  if (register.council_status !== "PENDING_INDEPENDENT_COUNCIL") errors.push("council");
  if (register.council_verdict !== null) errors.push("verdict");
  if (register.self_certified_council_pass !== false) errors.push("self certified");
  if (register.audience !== "INTERNAL_RESTRICTED") errors.push("audience");
  if (register.binds_claim_stage !== false) errors.push("binds claim stage");
  if (register.production_slo !== false) errors.push("slo");
  if (register.customer_proof !== false) errors.push("customer proof");
  if (register.host_attachment !== false) errors.push("host attachment");
  if (register.host_attachment_status !== "HOST_ATTACHMENT_FALSE") errors.push("host attachment status");
  if (register.host_attachment_action !== "NOT_PERFORMED") errors.push("host attachment action");
  if (register.ebpf_loaded !== false) errors.push("ebpf");
  if (register.kernel_executed !== false) errors.push("kernel");
  if (register.active_protection !== false) errors.push("active protection");
  if (register.eligible_plane_id !== "NONE") errors.push("plane");
  if (register.proved_external !== false) errors.push("proved external");
  if (register.clean_host_internal_proof !== false) errors.push("clean host");
  if (register.stranger_host_executed !== false) errors.push("stranger host");
  if (register.customer_deployed !== false) errors.push("customer deploy");
  if (register.announced !== false) errors.push("announced");
  if (register.credentials_issued !== false) errors.push("credentials");
  if (register.money_spent !== false) errors.push("money");
  if (register.frozen_cli_reopened !== false) errors.push("cli reopened");
  if (register.python_sdk_mutated !== false) errors.push("python mutated");
  if (register.node_sdk_mutated !== false) errors.push("node sdk mutated");
  const infra = register.w3_infra_req_1;
  if (!infra || infra.id !== "W3-INFRA-REQ-1") errors.push("infra id");
  if (!infra || infra.provisioned_by_this_force !== false) errors.push("infra provisioned");
  if (!infra || infra.money_spent_by_this_force !== false) errors.push("infra money");
  if (!infra || infra.credentials_issued_by_this_force !== false) errors.push("infra credentials");
  if (register.subject.starting_ref !== STARTING_REF) errors.push("starting ref");
  if (!/^[0-9a-f]{40}$/.test(register.subject.measured_tree_sha)) errors.push("measured sha");
  if (register.subject.runtime_tree_matches_starting_ref !== true) errors.push("runtime drift");
  const worktreeHash = hashRuntimeFiles(worktreeRuntimeFiles());
  const startingHash = hashRuntimeFiles(gitRuntimeFiles());
  if (worktreeHash !== startingHash) errors.push("runtime bytes differ from starting ref");
  if (register.subject.runtime_sources_sha256 !== worktreeHash) errors.push("runtime hash");
  if (register.environment.selected_plane_id !== "NONE") errors.push("environment plane");
  if (register.environment.producer_pod_verdict !== "INELIGIBLE" && register.environment.producer_pod_verdict !== "NOT_SELECTED") {
    errors.push("pod verdict");
  }
  if (typeof register.environment.btf_vmlinux !== "boolean") errors.push("btf type");
  if (typeof register.environment.kernel_modules_dir !== "boolean") errors.push("modules type");
  if (register.environment.host_attachment !== false) errors.push("environment attachment");
  if (register.framework.scaffold_left_not_measured !== true) errors.push("scaffold flag");
  const versions = readFrozenVersions();
  for (const [name, version] of Object.entries(FROZEN_VERSIONS)) {
    if (versions[name] !== version) errors.push(`package ${name}`);
    if (register.frozen_versions[name] !== version) errors.push(`register version ${name}`);
  }
  if (register.frozen_versions_reopened !== false) errors.push("versions reopened");
  if (JSON.stringify(register.workload_request) !== JSON.stringify(denyRequest())) errors.push("workload request");
  const ids = register.metrics.map((metric) => metric.id);
  if (ids.join(",") !== METRIC_IDS.join(",")) errors.push("metric order");
  const scaffold = loadScaffold();
  let measuredCount = 0;
  for (const metric of register.metrics) {
    if (JSON.stringify(metric.dimensions) !== JSON.stringify(scaffold.get(metric.id).dimensions)) {
      errors.push(`${metric.id} dimensions`);
    }
    if (metric.estimate !== "PROHIBITED") errors.push(`${metric.id} estimate`);
    if (metric.production_slo !== false) errors.push(`${metric.id} slo`);
    if (metric.binds_claim_stage !== false) errors.push(`${metric.id} stage`);
    if (metric.host_attachment !== false) errors.push(`${metric.id} attachment`);
    if (metric.eligible_plane_id !== "NONE") errors.push(`${metric.id} plane`);
    if (metric.result === "NOT_MEASURED") {
      if (metric.result_value !== null) errors.push(`${metric.id} value`);
      if (typeof metric.result_value === "number") errors.push(`${metric.id} numeric`);
      if (metric.sample_count !== "NOT_MEASURED") errors.push(`${metric.id} sample count`);
      if (metric.percentiles !== "NOT_MEASURED") errors.push(`${metric.id} percentiles`);
      if (metric.unit !== null) errors.push(`${metric.id} unit`);
      if (metric.workload !== "NOT_DEFINED") errors.push(`${metric.id} workload`);
      if (metric.instrument !== "NOT_DEFINED") errors.push(`${metric.id} instrument`);
      if (metric.started_at_utc !== null || metric.started_at_et !== null) errors.push(`${metric.id} clock`);
      if (metric.reason !== UNMEASURED_REASONS[metric.id]) errors.push(`${metric.id} reason`);
      if (Object.prototype.hasOwnProperty.call(metric, "samples")) errors.push(`${metric.id} samples`);
      continue;
    }
    if (metric.result !== "MEASURED") {
      errors.push(`${metric.id} result ${metric.result}`);
      continue;
    }
    measuredCount += 1;
    if (!MEASURED_IDS.includes(metric.id)) errors.push(`${metric.id} unexpectedly measured`);
    if (typeof metric.instrument !== "string" || metric.instrument === "NOT_DEFINED") errors.push(`${metric.id} instrument`);
    if (typeof metric.workload !== "string" || metric.workload === "NOT_DEFINED") errors.push(`${metric.id} workload`);
    if (typeof metric.started_at_utc !== "string" || Number.isNaN(Date.parse(metric.started_at_utc))) {
      errors.push(`${metric.id} utc`);
    }
    if (typeof metric.started_at_et !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$/.test(metric.started_at_et)) {
      errors.push(`${metric.id} et`);
    }
    if (!Number.isSafeInteger(metric.sample_count) || metric.sample_count < 1) errors.push(`${metric.id} sample count`);
    if (!Array.isArray(metric.samples) || metric.samples.length !== metric.sample_count) errors.push(`${metric.id} samples`);
    if (metric.instrument_overhead_subtracted !== false) errors.push(`${metric.id} overhead`);
    if (!percentilesMatch(metric)) errors.push(`${metric.id} recomputation`);
  }
  if (register.disposition === "MEASURED" && measuredCount < 1) errors.push("disposition measured empty");
  if (register.disposition === "NOT_MEASURED" && measuredCount !== 0) errors.push("disposition hid measurements");
  if (register.disposition !== "MEASURED" && register.disposition !== "NOT_MEASURED") errors.push("disposition");
  const serialized = JSON.stringify(register);
  for (const figure of BANNED_FIGURES) {
    if (serialized.includes(figure)) errors.push(`banned figure ${figure}`);
  }
  const scaffoldDocument = JSON.parse(readFileSync(SCAFFOLD_PATH, "utf8"));
  for (const error of validatePerformance(scaffoldDocument)) errors.push(`scaffold ${error}`);
  const latency = register.metrics.find((metric) => metric.id === "decision_latency");
  const throughput = register.metrics.find((metric) => metric.id === "throughput");
  const evidence = register.metrics.find((metric) => metric.id === "evidence_growth");
  if (latency.result === "MEASURED" && latency.sample_count !== register.plan.latency_samples) errors.push("latency plan");
  if (throughput.result === "MEASURED" && throughput.sample_count !== register.plan.throughput_windows) errors.push("throughput plan");
  if (evidence.result === "MEASURED" && evidence.decisions_per_repetition !== register.plan.evidence_decisions) {
    errors.push("evidence plan");
  }
  if (evidence.result === "MEASURED" && evidence.sample_count !== register.plan.evidence_repetitions) {
    errors.push("evidence repetitions");
  }
  if (evidence.result === "MEASURED" && evidence.storage !== "in_memory_evidence_list") errors.push("evidence storage");
  return errors;
}

function environmentMarkdown(register) {
  const lines = [
    "# Qualification environment",
    "",
    "Audience: INTERNAL_RESTRICTED",
    "",
    "This file is written by `scripts/qualify.mjs --write` from the same object as `PERFORMANCE-REGISTER.json`.",
    "",
    `| Field | Value |`,
    `| --- | --- |`,
    `| Pod | \`${register.environment.pod_id}\` |`,
    `| Cgroup | \`${register.environment.cgroup}\` |`,
    `| Hostname | \`${register.environment.hostname}\` |`,
    `| uname | \`${register.environment.uname}\` |`,
    `| OS | ${register.environment.os_release} |`,
    `| Node | \`${register.environment.node}\` |`,
    `| /sys/kernel/btf/vmlinux | ${register.environment.btf_vmlinux} |`,
    `| Kernel module directory | ${register.environment.kernel_modules_dir} |`,
    `| Selected plane | \`${register.environment.selected_plane_id}\` |`,
    `| Producer pod verdict | \`${register.environment.producer_pod_verdict}\` |`,
    `| Measured tree | \`${register.subject.measured_tree_sha}\` |`,
    `| Starting ref | \`${register.subject.starting_ref}\` |`,
    `| Runtime matches starting ref | ${register.subject.runtime_tree_matches_starting_ref} |`,
    `| Worktree dirty at measurement | ${register.subject.worktree_dirty} |`,
    `| Run start (ET) | \`${register.run_started_at_et}\` |`,
    `| Run start (UTC) | \`${register.run_started_at_utc}\` |`,
    `| Cursor environment public id | \`${register.environment.cursor_environment_public_id}\` |`,
    `| Cursor environment id source | \`${register.environment.cursor_environment_public_id_source}\` |`,
    `| Cursor environment version | \`${register.environment.cursor_environment_version_public_id}\` |`,
    `| Cursor environment build | \`${register.environment.cursor_environment_build_id}\` |`,
    "",
    register.environment.producer_pod_verdict_basis,
    "",
    "Host attachment action: `NOT_PERFORMED`.",
    "",
    `| Metric | Result | Value | ET start |`,
    `| --- | --- | --- | --- |`,
  ];
  for (const metric of register.metrics) {
    if (metric.result === "MEASURED") {
      const value = metric.id === "throughput"
        ? `${metric.result_value} ${metric.unit} in ${metric.window_ns} ns`
        : `${metric.result_value} ${metric.unit}`;
      lines.push(`| \`${metric.id}\` | \`MEASURED\` | ${value} | \`${metric.started_at_et}\` |`);
    } else {
      lines.push(`| \`${metric.id}\` | \`NOT_MEASURED\` |  |  |`);
    }
  }
  lines.push("");
  lines.push("Reasons for `NOT_MEASURED` rows are on those metrics in `PERFORMANCE-REGISTER.json`.");
  lines.push("");
  return `${lines.join("\n")}\n`;
}

export function writeOutputs(register) {
  const json = `${JSON.stringify(register, null, 2)}\n`;
  writeFileSync(PROGRAM_REGISTER, json);
  writeFileSync(INTERNAL_REGISTER, json);
  writeFileSync(ENVIRONMENT_DOC, environmentMarkdown(register));
}

function main() {
  const register = measure(OFFICIAL_PLAN);
  const errors = validateRegister(register);
  if (errors.length > 0) {
    for (const error of errors) console.error(error);
    process.exit(1);
  }
  if (process.argv.includes("--write")) writeOutputs(register);
  console.log(register.producer_classification);
  console.log(register.disposition);
  console.log(register.subject.measured_tree_sha);
  console.log(register.run_started_at_et);
  console.log(register.environment.pod_id);
  for (const metric of register.metrics) {
    if (metric.result === "MEASURED") {
      const extra = metric.id === "throughput" ? ` window_ns=${metric.window_ns}` : "";
      console.log(`${metric.id} ${metric.result_value} ${metric.unit}${extra}`);
    } else {
      console.log(`${metric.id} NOT_MEASURED`);
    }
  }
}

const isMain = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (isMain) main();
