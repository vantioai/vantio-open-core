"use strict";

const { spawnSync } = require("node:child_process");
const { existsSync, readdirSync, readFileSync } = require("node:fs");
const path = require("node:path");
const {
  CLI_VERSION,
  DEMO_SENTENCE,
  FORBIDDEN_RUN_TOKENS,
  HOSTNAME,
  TRACE_RE,
} = require("./constants.cjs");

function cliEnv(demoHome) {
  const env = { ...process.env, HOME: demoHome, VANTIO_TELEMETRY_DISABLED: "1" };
  delete env.VANTIO_TELEMETRY;
  delete env.VANTIO_API_KEY;
  delete env.VANTIO_HOME;
  return env;
}

function runCli(repoRoot, demoHome, cliPath, args) {
  const forbidden = args.some((arg) => arg === "--check-registry" || arg.startsWith("--from"));
  if (forbidden) {
    const error = new Error("REFUSED_CLI_FLAG");
    error.code = "REFUSED_CLI_FLAG";
    throw error;
  }
  const res = spawnSync(process.execPath, [cliPath, ...args], {
    cwd: repoRoot,
    env: cliEnv(demoHome),
    encoding: "utf8",
    timeout: 20000,
  });
  return {
    args: [...args],
    status: res.status,
    stdout: res.stdout || "",
    stderr: res.stderr || "",
    error: res.error ? String(res.error.message) : null,
  };
}

function readRunFiles(demoHome) {
  const dir = path.join(demoHome, ".vantio", "runs");
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter((name) => name.endsWith(".json"))
    .sort()
    .map((name) => {
      const filePath = path.join(dir, name);
      const text = readFileSync(filePath, "utf8");
      let json = null;
      try {
        json = JSON.parse(text);
      } catch {
        json = null;
      }
      return { name, text, json };
    });
}

function classifyRun(file) {
  const call = file.json && Array.isArray(file.json.calls) ? file.json.calls[0] : null;
  const hostname = call && typeof call.hostname === "string" ? call.hostname : null;
  const origin = file.json && file.json.evidence_origin ? file.json.evidence_origin : null;
  if (hostname === HOSTNAME) {
    return {
      class: "SIMULATED_DEMO",
      hostname,
      origin,
      missing_origin: origin == null,
      trace_id: file.json.trace_id || null,
    };
  }
  if (origin === "SIMULATED_DEMO") {
    return { class: "SIMULATED_DEMO", hostname, origin, missing_origin: false, trace_id: file.json.trace_id || null };
  }
  return {
    class: "UNLABELED_SYNTHETIC",
    hostname,
    origin,
    missing_origin: origin == null,
    trace_id: file.json && file.json.trace_id ? file.json.trace_id : null,
  };
}

function scanRuns(demoHome) {
  const files = readRunFiles(demoHome);
  const rows = files.map((file) => ({ name: file.name, ...classifyRun(file) }));
  const forbiddenPresent = files.some((file) => FORBIDDEN_RUN_TOKENS.some((token) => file.text.includes(token)));
  const localObservation = files.some((file) => file.text.includes("LOCAL_OBSERVATION"));
  return {
    files: rows,
    simulated_demo_rows: rows.filter((row) => row.class === "SIMULATED_DEMO").length,
    unlabeled_synthetic_rows: rows.filter((row) => row.class === "UNLABELED_SYNTHETIC").length,
    customer_activity_total: 0,
    forbidden_tokens_present: forbiddenPresent,
    local_observation_present: localObservation,
  };
}

function offlineTranscript() {
  return {
    schema: "vantio.investor-demo.offline-cli-transcript/v1",
    simulation_label: "SIMULATED_DEMO",
    proof_class: "OFFLINE_FALLBACK",
    counted_in_customer_activity: false,
    network: "none",
    cli_version: CLI_VERSION,
    demo_sentence: DEMO_SENTENCE,
    hostname: HOSTNAME,
    action: "OBSERVED",
    bytes: 0,
    duration_ms: 0,
    content: null,
    evidence_origin_on_cli_file: "ABSENT",
    producer_on_cli_file: "ABSENT",
    note: "Committed fallback for this session. Not a live CLI transcript. Not a customer call.",
  };
}

function probeCli(options) {
  const invocations = [];
  if (options.forceOffline || !existsSync(options.cliPath)) {
    return {
      mode: "OFFLINE_FALLBACK",
      reason: options.forceOffline ? "FORCED" : "CLI_MISSING",
      invocations,
      transcript: offlineTranscript(),
      live: null,
    };
  }

  const version = runCli(options.repoRoot, options.demoHome, options.cliPath, ["--version"]);
  invocations.push(version);
  const versionLine = version.stdout.trim();
  if (version.error || version.status !== 0 || versionLine !== CLI_VERSION) {
    return {
      mode: "OFFLINE_FALLBACK",
      reason: versionLine && versionLine !== CLI_VERSION ? "VERSION_MISMATCH" : "VERSION_UNAVAILABLE",
      invocations,
      transcript: offlineTranscript(),
      live: null,
    };
  }

  const status = runCli(options.repoRoot, options.demoHome, options.cliPath, ["status"]);
  invocations.push(status);
  const demo = runCli(options.repoRoot, options.demoHome, options.cliPath, ["demo"]);
  invocations.push(demo);
  const traceMatch = demo.stdout.match(/trace_id: (0x[0-9a-f]{16})/);
  const traceId = traceMatch ? traceMatch[1] : null;
  const runsAfterDemo = scanRuns(options.demoHome);
  const stub = runsAfterDemo.files.find((row) => row.class === "SIMULATED_DEMO");
  let proveList = null;
  let proveMd = null;
  let discover = null;
  if (traceId && TRACE_RE.test(traceId)) {
    proveList = runCli(options.repoRoot, options.demoHome, options.cliPath, ["prove", "--list"]);
    invocations.push(proveList);
    proveMd = runCli(options.repoRoot, options.demoHome, options.cliPath, ["prove", `--run=${traceId}`, "--format=md"]);
    invocations.push(proveMd);
    discover = runCli(options.repoRoot, options.demoHome, options.cliPath, ["discover"]);
    invocations.push(discover);
  }

  const liveOk = status.status === 0
    && status.stdout.includes("not checked")
    && status.stdout.includes("disabled")
    && demo.status === 0
    && demo.stdout.includes(DEMO_SENTENCE)
    && traceId
    && stub
    && stub.hostname === HOSTNAME
    && stub.missing_origin === true
    && proveMd
    && proveMd.status === 0
    && proveMd.stdout.includes(HOSTNAME)
    && !proveMd.stdout.includes("SIMULATED_DEMO")
    && discover
    && discover.status === 0
    && discover.stdout.includes(HOSTNAME)
    && discover.stdout.includes("observed locally")
    && !runsAfterDemo.forbidden_tokens_present
    && !runsAfterDemo.local_observation_present;

  if (!liveOk) {
    return {
      mode: "LIVE_DEVIATION",
      reason: "LIVE_DEVIATION",
      invocations,
      transcript: null,
      live: {
        version: versionLine,
        trace_id: traceId,
        deviation: true,
        demo_sentence_present: demo.stdout.includes(DEMO_SENTENCE),
        hostname: stub ? stub.hostname : null,
      },
    };
  }

  return {
    mode: "LIVE_CLI",
    reason: "CLI_0_3_24",
    invocations,
    transcript: null,
    live: {
      version: versionLine,
      trace_id: traceId,
      status_excerpt_registry: "not checked",
      status_excerpt_telemetry: "disabled",
      demo_sentence: DEMO_SENTENCE,
      hostname: HOSTNAME,
      prove_omits_simulation_label: true,
      discover_observed_locally: true,
      discover_is_customer_total: false,
      cli_file_missing_origin: true,
    },
  };
}

module.exports = {
  classifyRun,
  offlineTranscript,
  probeCli,
  runCli,
  scanRuns,
};
