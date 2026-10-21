"use strict";

// Coverage map, new-destination flags, and monitoring export for local Optics records.
// Prompts, completions, bodies, headers, and query strings are not fields here.

const { createHash } = require("node:crypto");
const { homedir, hostname: osHostname, platform: osPlatform } = require("node:os");
const {
  appendFileSync,
  closeSync,
  existsSync,
  mkdirSync,
  openSync,
  readFileSync,
  readdirSync,
  readSync,
  renameSync,
  rmSync,
  statSync,
  writeFileSync,
} = require("node:fs");
const { dirname, join } = require("node:path");
const { request: httpRequest } = require("node:http");
const { request: httpsRequest } = require("node:https");
const dgram = require("node:dgram");
const net = require("node:net");
const { parseArgs } = require("node:util");

const { SCHEMA_STATUS, normalizeHttpStatus, withSchema } = require("./optics-cx.cjs");
const { LLM_HOSTS, catalogInScope } = require("./llm-hosts.cjs");
const { discoverUncovered } = require("./optics-proc.cjs");
const { deliverOtlpGrpc } = require("./optics-otlp-grpc.cjs");

const COVERAGE_SCHEMA = "vantio.optics.coverage.v1";
const ALLOWLIST_SCHEMA = "vantio.optics.allowlist.v1";
const SEEN_SCHEMA = "vantio.optics.seen_destinations.v1";
const EXPORT_SCHEMA = "vantio.optics.export.v1";
const ALERT_SCHEMA = "vantio.optics.new_destination.v1";
const LIVE_SCHEMA = "vantio.optics.live.v1";
const LIVE_BUFFER_MAX = 1000;

const SINCE_VALUES = new Set(["all", "24h", "7d", "30d"]);
const ALLOWLIST_KEYS = new Set(["schema", "destinations", "mcp_tools", "alert_on_allowlist"]);
const SPAWN_TOOLS = Object.freeze({
  node_curl: "curl",
  node_wget: "wget",
  node_httpie: "httpie",
  node_aria2c: "aria2c",
  python_curl: "curl",
  python_wget: "wget",
  python_httpie: "httpie",
  python_aria2c: "aria2c",
});

const NOT_COVERED = Object.freeze([
  {
    id: "unwrapped_process",
    summary: "A process outside the wrap is marked not covered when the local process table shows it.",
  },
  {
    id: "browser",
    summary: "Browser paths stay outside this wrap.",
  },
  {
    id: "not_intercepted",
    summary: "A socket missed between samples, and a call on a process outside this wrap, is not recorded.",
  },
  {
    id: "other_machines",
    summary: "This command reads records on this system. It does not connect to other machines.",
  },
]);

const COVERAGE_HELP = `\
vantio coverage — processes and connections recorded on this system

Prints every AI process and connection in the local Optics records, and
whether each path is on the allowlist a person wrote. Paths on that list
are under authority. Paths that were seen and are not on the list are
outside authority. On Linux, the local process table and sockets are read
and a process outside the wrap is marked not covered. The read is local
and does not change the process.

The map is this system. A record that stored another hostname is shown
under that name. This command does not connect to other machines.

Prompts and completions are never stored.

Usage:
  vantio coverage [options]

Options:
  --since=all|24h|7d|30d   Window (default: all)
  --allowlist=<file>       Allowlist JSON. Default: ~/.vantio/allowlist.json when that file exists
  --json                   Unstable JSON (schema_status unstable-pre-1.0; may change without notice)
  -h, --help               Show this help

Exit status: 0 completed, including an empty result. 1 bad arguments, or a file that exists but cannot be read or parsed.

Examples:
  vantio coverage
  vantio coverage --json
  vantio coverage --allowlist=./allowlist.json --since=7d
`;

const DESTINATIONS_HELP = `\
vantio destinations — flag a destination the first time a program connects to it

Reads local Optics records in time order. The first connection from a
program to a destination is flagged New destination, unless that
destination is on the allowlist. A later connection to the same
destination by the same program is not flagged again.

The memory is seen-destinations.json under VANTIO_HOME when that is set,
otherwise ~/.vantio. The first full run flags every destination that is
not on the allowlist. --since does not forget an older connection: a
destination used before the window is not flagged again. Set
alert_on_allowlist to true to flag an approved destination the first
time as well.

Prompts and completions are never stored. This command does not stop the call.

Usage:
  vantio destinations [options]

Options:
  --since=all|24h|7d|30d   Which new flags to report (default: all). The first-seen check still uses every local record.
  --allowlist=<file>       Allowlist JSON. Default: ~/.vantio/allowlist.json when that file exists
  --dry-run                Print flags and do not write the seen-destination file
  --json                   Unstable JSON (schema_status unstable-pre-1.0; may change without notice)
  -h, --help               Show this help

Exit status: 0 completed, including no new destination. 1 bad arguments, or a file that exists but cannot be read or parsed.

Examples:
  vantio destinations
  vantio destinations --json
  vantio destinations --allowlist=./allowlist.json --dry-run
`;

const EXPORT_HELP = `\
vantio export — send recorded events to a tool you already run

Sends projected Optics events. Choose one or more destinations:

  --otlp=<base>            OTLP/HTTP JSON. POSTs /v1/traces, /v1/metrics, and /v1/logs
  --otlp-grpc=<url>        OTLP unary gRPC over HTTP/2. grpc:// is plaintext loopback
  --jsonl=<file|->         One JSON object per line
  --syslog=<file|-|url>    RFC 5424 lines. url is udp://host:port or tcp://host:port
  --webhook=<url>          POST a JSON envelope
  --follow                 Stream live events as they are recorded. Retries with backoff.

Plaintext http and grpc are accepted only for loopback. https and grpcs are
used for other hosts. Optics does not start a collector. --follow keeps a
bounded buffer and retries a failed send. A one-shot export still exits
non-zero when a destination does not accept the batch.

The Optics trace id is kept on the event. The OTLP traceId is a 32-hex digest
of that id, because an Optics trace id is not a W3C trace id.

Prompts and completions are never stored. Query strings are dropped.
A new destination flagged by the same rules as vantio destinations is included.
The seen-destination file is written only after every destination accepts the batch.

VANTIO_EXPORT_WEBHOOK_TOKEN, when set, is sent as a bearer token on the webhook.
The CLI does not print that value.

Usage:
  vantio export [options]

Options:
  --since=all|24h|7d|30d   Records to send (default: all)
  --allowlist=<file>       Same allowlist as vantio coverage and vantio destinations
  --dry-run                Build the batch and do not connect or write
  --json                   Unstable JSON summary on stdout
  -h, --help               Show this help

--json cannot be combined with --jsonl=- or --syslog=-.

Exit status: 0 when every selected destination accepted the batch, including an empty batch that is not sent. 1 bad arguments, an unreadable file, or a destination that did not accept the batch.

Examples:
  vantio export --otlp=http://127.0.0.1:4318
  vantio export --jsonl=./optics.jsonl --syslog=udp://127.0.0.1:514
  vantio export --webhook=https://collector.example/optics
`;

function detailOf(err) {
  if (!err) return "failed";
  const message = err.message ? String(err.message) : String(err);
  return message.split("\n")[0] || "failed";
}

function fail(command, message) {
  process.stderr.write(`vantio ${command}: ${message}\n`);
  process.exit(1);
}

function parseArgsSafe(command, config) {
  try {
    return parseArgs(config);
  } catch (err) {
    fail(command, detailOf(err));
  }
  return { values: {}, positionals: [] };
}

function configHome() {
  return join(homedir(), ".vantio");
}

function primaryHome() {
  const extra = process.env.VANTIO_HOME;
  if (typeof extra === "string" && extra.trim()) return extra.trim();
  return configHome();
}

function dataRoots(env) {
  const home = configHome();
  const roots = [home];
  const extra = env && typeof env.VANTIO_HOME === "string" ? env.VANTIO_HOME : "";
  if (extra && extra !== home) roots.push(extra);
  return roots;
}

function programLabelFromArgv(argv) {
  const args = Array.isArray(argv) ? argv : [];
  const interp = String(args[0] || "unknown").split(/[\\/]/).pop().replace(/\.exe$/i, "") || "unknown";
  const skipValue = new Set(["-e", "--eval", "-c", "--command"]);
  for (let i = 1; i < args.length; i += 1) {
    const part = String(args[i] || "");
    if (part === "-m" || part === "--module") {
      const name = String(args[i + 1] || "").split(/[\\/]/).pop();
      return name || interp;
    }
    if (skipValue.has(part)) {
      i += 1;
      continue;
    }
    if (!part || part.startsWith("-")) continue;
    const base = part.split(/[\\/]/).pop();
    if (base) return base;
  }
  return interp;
}

function cleanToken(value, max) {
  if (typeof value !== "string") return null;
  const text = value.trim();
  if (!text || text.length > max || /[\r\n]/.test(text)) return null;
  return text;
}

function normalizeHost(value) {
  if (typeof value !== "string") return null;
  let host = value.trim();
  if (!host || host.length > 512) return null;
  if (host.includes("://") || host.includes("/") || host.includes("?") || host.includes("#") || host.includes("@")) {
    try {
      const parsed = new URL(host.includes("://") ? host : `https://${host}`);
      host = parsed.hostname;
    } catch {
      return null;
    }
  }
  host = host.replace(/^\[|\]$/g, "").toLowerCase();
  if (!host || host.length > 253 || /[\s/?#]/.test(host)) return null;
  return host;
}

function stripPath(value) {
  if (typeof value !== "string" || !value.trim()) return null;
  const path = value.split("#")[0].split("?")[0];
  if (!path) return null;
  return path.length > 512 ? path.slice(0, 512) : path;
}

function cleanBytes(value) {
  const number = typeof value === "number" ? value : null;
  if (number == null || !Number.isFinite(number) || number < 0) return null;
  return Math.trunc(number);
}

function callBytes(call) {
  if (!call || typeof call !== "object") return null;
  if (call.bytes != null) return cleanBytes(call.bytes);
  if (call.bytes_observed != null) return cleanBytes(call.bytes_observed);
  return null;
}

function programFromLog(log) {
  const named = cleanToken(log && log.program, 256);
  if (named) return named;
  if (log && log.runtime === "python") return "python";
  if (log && log.node_version) return "node";
  return "unknown";
}

function cutoffFromSince(since, now) {
  if (!SINCE_VALUES.has(since)) return { error: `invalid --since value '${since}'. Use all, 24h, 7d, or 30d.` };
  if (since === "all") return { cutoff: null };
  const count = Number(since.slice(0, -1));
  const unit = since.endsWith("h") ? 3600000 : 86400000;
  return { cutoff: now - count * unit };
}

function inWindow(time, cutoff) {
  if (cutoff == null) return true;
  const parsed = Date.parse(time || "");
  if (!Number.isFinite(parsed)) return false;
  return parsed >= cutoff;
}

function emptyAllowlist() {
  return {
    schema: ALLOWLIST_SCHEMA,
    destinations: [],
    mcpTools: [],
    alertOnAllowlist: false,
  };
}

function parseAllowlistEntry(value, field) {
  if (typeof value === "string") {
    const destination = field === "destinations" ? normalizeHost(value) : cleanToken(value, 128);
    if (!destination) return { error: `${field} entry is empty or not a host or tool name` };
    if (field === "destinations" && destination === "*") return { error: "destination '*' is not an allowlist entry" };
    return { entry: { destination, alert: null } };
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return { error: `${field} entry must be a string or an object` };
  }
  const raw = field === "destinations" ? value.destination : value.name;
  const destination = field === "destinations" ? normalizeHost(raw) : cleanToken(raw, 128);
  if (!destination) return { error: `${field} entry needs a ${field === "destinations" ? "destination" : "name"}` };
  if (value.alert != null && typeof value.alert !== "boolean") return { error: `${field} alert must be true or false` };
  const keys = Object.keys(value);
  const allowed = field === "destinations" ? new Set(["destination", "alert"]) : new Set(["name", "alert"]);
  for (const key of keys) {
    if (!allowed.has(key)) return { error: `${field} entry has unknown field '${key}'` };
  }
  return { entry: { destination, alert: value.alert == null ? null : value.alert } };
}

function parseAllowlist(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return { error: "allowlist must be a JSON object" };
  }
  for (const key of Object.keys(value)) {
    if (!ALLOWLIST_KEYS.has(key)) return { error: `unknown field '${key}'` };
  }
  if (value.schema != null && value.schema !== ALLOWLIST_SCHEMA) {
    return { error: `schema must be ${ALLOWLIST_SCHEMA}` };
  }
  if (value.alert_on_allowlist != null && typeof value.alert_on_allowlist !== "boolean") {
    return { error: "alert_on_allowlist must be true or false" };
  }
  const allowlist = emptyAllowlist();
  allowlist.alertOnAllowlist = value.alert_on_allowlist === true;
  for (const field of ["destinations", "mcp_tools"]) {
    const list = value[field];
    if (list == null) continue;
    if (!Array.isArray(list)) return { error: `${field} must be an array` };
    for (const item of list) {
      const parsed = parseAllowlistEntry(item, field);
      if (parsed.error) return parsed;
      if (field === "destinations") allowlist.destinations.push(parsed.entry);
      else allowlist.mcpTools.push(parsed.entry);
    }
  }
  return { allowlist };
}

function readJsonObject(path) {
  let text;
  try {
    text = readFileSync(path, "utf8");
  } catch (err) {
    return { error: err, missing: err && err.code === "ENOENT" };
  }
  try {
    return { json: JSON.parse(text) };
  } catch (err) {
    return { error: err, corrupt: true };
  }
}

function allowlistCandidates(explicitPath) {
  if (explicitPath) return [explicitPath];
  const paths = [join(primaryHome(), "allowlist.json")];
  const fallback = join(configHome(), "allowlist.json");
  if (!paths.includes(fallback)) paths.push(fallback);
  return paths;
}

function loadAllowlist(explicitPath) {
  const paths = allowlistCandidates(explicitPath);
  let sawMissing = true;
  for (const path of paths) {
    const loaded = readJsonObject(path);
    if (loaded.missing) continue;
    sawMissing = false;
    if (loaded.error) return { error: `could not read allowlist ${path}: ${detailOf(loaded.error)}` };
    const parsed = parseAllowlist(loaded.json);
    if (parsed.error) return { error: `allowlist ${path}: ${parsed.error}` };
    return { allowlist: parsed.allowlist, path };
  }
  if (explicitPath && sawMissing) return { error: `allowlist file not found: ${explicitPath}` };
  return { allowlist: emptyAllowlist(), path: null };
}

function matchPattern(value, entry) {
  const pattern = entry.destination;
  if (pattern.startsWith("*.")) {
    const suffix = pattern.slice(1);
    if (!value.endsWith(suffix) || value.length <= suffix.length) return false;
    const label = value.slice(0, -suffix.length);
    return label.length > 0 && !label.includes(".");
  }
  return value === pattern;
}

function matchAllowlist(observation, allowlist) {
  if (!allowlist || !observation) return null;
  if (observation.kind === "mcp_tool") {
    return allowlist.mcpTools.find((entry) => entry.destination === observation.destination) || null;
  }
  const host = observation.destination;
  return allowlist.destinations.find((entry) => matchPattern(host, entry)) || null;
}

function entryAlerts(entry, alertOnAllowlist) {
  if (entry && typeof entry.alert === "boolean") return entry.alert;
  return alertOnAllowlist === true;
}

function readMachineId() {
  try {
    const text = readFileSync("/etc/machine-id", "utf8").trim();
    return /^[a-f0-9]{32}$/.test(text) ? text : null;
  } catch {
    return null;
  }
}

function listRunLogs(roots) {
  const logs = [];
  const seen = new Set();
  for (const root of roots) {
    const dir = join(root, "runs");
    let names;
    try {
      names = readdirSync(dir);
    } catch (err) {
      if (err && err.code === "ENOENT") continue;
      return { error: `could not read ${dir}: ${detailOf(err)}` };
    }
    for (const name of names) {
      if (!name.endsWith(".json")) continue;
      const path = join(dir, name);
      if (seen.has(path)) continue;
      seen.add(path);
      const loaded = readJsonObject(path);
      if (loaded.error) return { error: `could not read ${path}: ${detailOf(loaded.error)}` };
      const log = loaded.json;
      if (!log || log.vantio_run_log !== "1" || !Array.isArray(log.calls)) continue;
      logs.push(log);
    }
  }
  return { logs };
}

function listMcpRecords(roots) {
  const records = [];
  const seen = new Set();
  for (const root of roots) {
    const path = join(root, "mcp-observations.jsonl");
    if (seen.has(path)) continue;
    seen.add(path);
    let text;
    try {
      text = readFileSync(path, "utf8");
    } catch (err) {
      if (err && err.code === "ENOENT") continue;
      return { error: `could not read ${path}: ${detailOf(err)}` };
    }
    const lines = text.split(/\n/);
    for (let i = 0; i < lines.length; i += 1) {
      if (!lines[i].trim()) continue;
      let json;
      try {
        json = JSON.parse(lines[i]);
      } catch (err) {
        return { error: `could not read ${path}:${i + 1}: ${detailOf(err)}` };
      }
      if (json && json.schema === "vantio.mcp_observation.v1") records.push(json);
    }
  }
  return { records };
}

function observationFromCall(log, call, seq, localHost) {
  const destination = normalizeHost(call && call.hostname);
  const time = cleanToken(call && call.ts, 64) || cleanToken(log.generated_at, 64) || cleanToken(log.started_at, 64);
  const callPid = Number.isInteger(call && call.pid) ? call.pid : null;
  const program = cleanToken(call && call.program, 256) || programFromLog(log);
  const pid = callPid != null ? callPid : (Number.isInteger(log.pid) ? log.pid : null);
  const ppid = callPid != null
    ? (Number.isInteger(call && call.ppid) ? call.ppid : null)
    : (Number.isInteger(log.ppid) ? log.ppid : null);
  return {
    seq,
    kind: "connection",
    program,
    pid,
    ppid,
    trace_id: cleanToken(log.trace_id, 128),
    started_at: cleanToken(log.started_at, 64),
    system_hostname: cleanToken(log.system_hostname, 253) || localHost,
    host_recorded: Boolean(cleanToken(log.system_hostname, 253)),
    runtime: cleanToken(log.runtime, 32) || (log.node_version ? "node" : null),
    destination: destination || "unknown",
    display: destination || "unknown",
    method: cleanToken(call && call.method, 16),
    path: stripPath(call && call.path),
    bytes: callBytes(call),
    http_status: normalizeHttpStatus(call && (call.status != null ? call.status : call.httpStatus)),
    time,
    mediation: cleanToken(call && call.mediation, 64),
    provider: cleanToken(call && call.provider, 64),
  };
}

function observationFromMcp(record, seq, localHost) {
  const tool = cleanToken(record && record.tool_name, 128);
  return {
    seq,
    kind: "mcp_tool",
    program: "mcp",
    pid: null,
    ppid: null,
    trace_id: null,
    started_at: null,
    system_hostname: localHost,
    host_recorded: false,
    runtime: "mcp",
    destination: tool || "",
    display: tool ? `mcp ${tool}` : "mcp (tool name not retained)",
    method: cleanToken(record && record.method, 64),
    path: null,
    bytes: null,
    http_status: null,
    time: null,
    mediation: null,
    provider: null,
    tool_name_retained: Boolean(tool),
  };
}

function treeRows(log, localHost) {
  const listed = Array.isArray(log.processes)
    ? log.processes.filter((proc) => proc && typeof proc === "object")
    : [];
  if (!listed.length) return [];
  const byPid = new Map();
  for (const proc of listed) {
    if (Number.isInteger(proc.pid)) byPid.set(proc.pid, proc);
  }
  return listed.map((proc) => {
    const parent = Number.isInteger(proc.ppid) ? byPid.get(proc.ppid) : null;
    return {
      kind: "process",
      program: cleanToken(proc.program, 256) || programFromLog(log),
      pid: Number.isInteger(proc.pid) ? proc.pid : null,
      ppid: Number.isInteger(proc.ppid) ? proc.ppid : null,
      parent_program: parent ? cleanToken(parent.program, 256) : null,
      trace_id: cleanToken(log.trace_id, 128),
      started_at: cleanToken(log.started_at, 64),
      system_hostname: cleanToken(log.system_hostname, 253) || localHost,
      host_recorded: Boolean(cleanToken(log.system_hostname, 253)),
      runtime: cleanToken(log.runtime, 32) || (log.node_version ? "node" : null),
      destination: "",
      display: "",
      method: null,
      path: null,
      bytes: null,
      http_status: null,
      time: cleanToken(log.started_at, 64) || cleanToken(log.generated_at, 64),
      mediation: null,
      provider: null,
    };
  });
}

function collectObservations(logs, mcpRecords, localHost, cutoff) {
  const observations = [];
  let seq = 0;
  let undatedExcluded = 0;
  for (const log of logs) {
    const calls = Array.isArray(log.calls) ? log.calls : [];
    const tree = treeRows(log, localHost);
    if (tree.length) {
      for (const row of tree) {
        row.seq = seq;
        seq += 1;
        if (!inWindow(row.time, cutoff)) {
          if (!row.time) undatedExcluded += 1;
          continue;
        }
        observations.push(row);
      }
    } else if (calls.length === 0 && inWindow(log.started_at || log.generated_at, cutoff)) {
      observations.push({
        seq,
        kind: "process",
        program: programFromLog(log),
        pid: Number.isInteger(log.pid) ? log.pid : null,
        ppid: Number.isInteger(log.ppid) ? log.ppid : null,
        parent_program: null,
        trace_id: cleanToken(log.trace_id, 128),
        started_at: cleanToken(log.started_at, 64),
        system_hostname: cleanToken(log.system_hostname, 253) || localHost,
        host_recorded: Boolean(cleanToken(log.system_hostname, 253)),
        runtime: cleanToken(log.runtime, 32) || (log.node_version ? "node" : null),
        destination: "",
        display: "",
        method: null,
        path: null,
        bytes: null,
        http_status: null,
        time: cleanToken(log.started_at, 64) || cleanToken(log.generated_at, 64),
        mediation: null,
        provider: null,
      });
      seq += 1;
    }
    for (const call of calls) {
      const observation = observationFromCall(log, call, seq, localHost);
      seq += 1;
      if (!inWindow(observation.time, cutoff)) {
        if (!observation.time) undatedExcluded += 1;
        continue;
      }
      observations.push(observation);
    }
  }
  for (const record of mcpRecords) {
    const observation = observationFromMcp(record, seq, localHost);
    seq += 1;
    if (!inWindow(observation.time, cutoff)) {
      undatedExcluded += 1;
      continue;
    }
    observations.push(observation);
  }
  return { observations, undatedExcluded };
}

function spawnProgram(mediation) {
  return SPAWN_TOOLS[mediation] || null;
}

function authorityFor(observation, allowlist) {
  if (observation.kind === "mcp_tool" && !observation.tool_name_retained) return "outside_authority";
  return matchAllowlist(observation, allowlist) ? "under_authority" : "outside_authority";
}

function buildCoverage(input) {
  const localHost = input.localHost || "unknown";
  const allowlist = input.allowlist || emptyAllowlist();
  const observations = input.observations || [];
  const systems = new Map();
  const processes = [];
  const processKeys = new Set();

  function systemBucket(name, recorded) {
    const key = name || localHost;
    if (!systems.has(key)) {
      systems.set(key, {
        hostname: key,
        host_source: recorded ? "record" : "command",
        platform: key === localHost ? (input.platform || null) : null,
        processes: [],
        connections: [],
        under_authority: [],
        outside_authority: [],
      });
    }
    return systems.get(key);
  }

  function addProcess(bucket, row) {
    const base = [bucket.hostname, row.program, row.pid == null ? "" : row.pid, row.trace_id || ""].join("\n");
    const key = row.pid == null ? `${base}\n${row.parent_program || ""}` : base;
    if (processKeys.has(key)) return;
    processKeys.add(key);
    bucket.processes.push(row);
    processes.push(Object.assign({ system_hostname: bucket.hostname }, row));
  }

  const pathBuckets = new Map();
  const connections = [];
  for (const observation of observations) {
    const bucket = systemBucket(observation.system_hostname, observation.host_recorded);
    if (observation.kind === "process") {
      addProcess(bucket, {
        program: observation.program,
        pid: observation.pid,
        ppid: observation.ppid,
        trace_id: observation.trace_id,
        started_at: observation.started_at || observation.time,
        runtime: observation.runtime,
        parent_program: observation.parent_program || null,
        covered: true,
        source: "run_log",
      });
      continue;
    }
    const authority = authorityFor(observation, allowlist);
    const connection = {
      program: observation.program,
      pid: observation.pid,
      trace_id: observation.trace_id,
      destination: observation.display,
      kind: observation.kind,
      method: observation.method,
      path: observation.path,
      bytes: observation.bytes,
      time: observation.time,
      authority,
      mediation: observation.mediation,
      system_hostname: bucket.hostname,
      tool_name_retained: observation.kind === "mcp_tool" ? observation.tool_name_retained : undefined,
    };
    connections.push(connection);
    bucket.connections.push(connection);
    if (observation.kind !== "mcp_tool") {
      addProcess(bucket, {
        program: observation.program,
        pid: observation.pid,
        ppid: observation.ppid,
        trace_id: observation.trace_id,
        started_at: observation.started_at || observation.time,
        runtime: observation.runtime,
        parent_program: null,
        covered: true,
        source: "run_log",
      });
    }
    const pathKey = `${bucket.hostname}\n${observation.kind}\n${observation.display}`;
    if (!pathBuckets.has(pathKey)) {
      pathBuckets.set(pathKey, {
        system_hostname: bucket.hostname,
        destination: observation.display,
        kind: observation.kind,
        authority,
        programs: [],
        calls: 0,
        bytes: 0,
        first_time: observation.time,
        bytes_known: false,
        source: "record",
      });
    }
    const path = pathBuckets.get(pathKey);
    path.calls += 1;
    if (observation.bytes != null) {
      path.bytes += observation.bytes;
      path.bytes_known = true;
    }
    if (observation.program && !path.programs.includes(observation.program)) path.programs.push(observation.program);
    if (observation.time && (!path.first_time || observation.time < path.first_time)) path.first_time = observation.time;

    const child = spawnProgram(observation.mediation);
    if (child) {
      addProcess(bucket, {
        program: child,
        pid: null,
        ppid: observation.pid,
        trace_id: observation.trace_id,
        started_at: observation.time,
        runtime: null,
        parent_program: observation.program,
        covered: true,
        source: "recorded_spawn",
      });
    }
  }

  for (const gap of input.procGaps || []) {
    const bucket = systemBucket(input.localHost, false);
    const observation = {
      kind: "connection",
      program: gap.program,
      destination: gap.destination,
      display: gap.destination,
    };
    const authority = authorityFor(observation, allowlist);
    const connection = {
      program: gap.program,
      pid: gap.pid,
      trace_id: null,
      destination: gap.destination,
      kind: "connection",
      method: null,
      path: null,
      bytes: null,
      time: null,
      authority,
      mediation: null,
      system_hostname: bucket.hostname,
      source: "proc",
      covered: false,
      reason: gap.reason,
    };
    connections.push(connection);
    bucket.connections.push(connection);
    const pathKey = `${bucket.hostname}\nproc\n${gap.destination}`;
    if (!pathBuckets.has(pathKey)) {
      pathBuckets.set(pathKey, {
        system_hostname: bucket.hostname,
        destination: gap.destination,
        kind: "connection",
        authority,
        programs: [],
        calls: 0,
        bytes: 0,
        first_time: null,
        bytes_known: false,
        source: "proc",
      });
    }
    const path = pathBuckets.get(pathKey);
    path.calls += 1;
    if (gap.program && !path.programs.includes(gap.program)) path.programs.push(gap.program);
    addProcess(bucket, {
      program: gap.program,
      pid: gap.pid,
      ppid: null,
      trace_id: null,
      started_at: null,
      runtime: null,
      parent_program: null,
      covered: false,
      source: "proc",
    });
  }

  for (const path of pathBuckets.values()) {
    const row = {
      destination: path.destination,
      kind: path.kind,
      programs: path.programs,
      calls: path.calls,
      bytes: path.bytes_known ? path.bytes : null,
      first_time: path.first_time,
      source: path.source || "record",
    };
    const bucket = systems.get(path.system_hostname);
    if (path.authority === "under_authority") bucket.under_authority.push(row);
    else bucket.outside_authority.push(row);
  }

  const systemList = [...systems.values()].map((bucket) => {
    bucket.under_authority.sort((a, b) => a.destination.localeCompare(b.destination));
    bucket.outside_authority.sort((a, b) => a.destination.localeCompare(b.destination));
    bucket.processes.sort((a, b) => String(a.started_at || "").localeCompare(String(b.started_at || "")) || a.program.localeCompare(b.program));
    return bucket;
  }).sort((a, b) => a.hostname.localeCompare(b.hostname));

  return {
    schema: COVERAGE_SCHEMA,
    system: {
      hostname: localHost,
      platform: input.platform || null,
      machine_id: input.machineId || null,
      scope: "this_system",
    },
    since: input.since || "all",
    allowlist: {
      path: input.allowlistPath || null,
      destinations: allowlist.destinations.map((entry) => entry.destination),
      mcp_tools: allowlist.mcpTools.map((entry) => entry.destination),
      alert_on_allowlist: allowlist.alertOnAllowlist,
    },
    systems: systemList,
    processes,
    connections,
    not_covered: NOT_COVERED.map((row) => ({ id: row.id, summary: row.summary })).concat(input.procNote ? [input.procNote] : []),
    proc: input.proc || { readable: false },
    undated_excluded: input.undatedExcluded || 0,
    counts: {
      processes: processes.length,
      connections: connections.length,
      under_authority: systemList.reduce((sum, bucket) => sum + bucket.under_authority.length, 0),
      outside_authority: systemList.reduce((sum, bucket) => sum + bucket.outside_authority.length, 0),
    },
  };
}

function formatPathRow(row) {
  const programs = row.programs.length ? row.programs.join(", ") : "unknown";
  const bytes = row.bytes == null ? "size not recorded" : `${row.bytes} bytes`;
  const time = row.first_time || "time not recorded";
  return `  ${row.destination}\n    program ${programs}  calls ${row.calls}  ${bytes}  first ${time}`;
}

function formatCoverageText(coverage) {
  const lines = [
    "Vantio Optics | Coverage map",
    "Prompts and completions are never stored.",
    "",
    `System: ${coverage.system.hostname} (${coverage.system.platform || "unknown"})`,
  ];
  if (coverage.system.machine_id) lines.push(`Machine id: ${coverage.system.machine_id}`);
  lines.push("Scope: this system. Processes that never entered the wrap are named below and are not listed as covered.");
  lines.push("");
  if (coverage.systems.length === 0) {
    lines.push("Under authority");
    lines.push("  None.");
    lines.push("");
    lines.push("Outside authority");
    lines.push("  None.");
    lines.push("");
    lines.push("Processes");
    lines.push("  None recorded.");
  }
  for (const system of coverage.systems) {
    if (coverage.systems.length > 1 || system.hostname !== coverage.system.hostname) {
      lines.push(`Recorded system: ${system.hostname}`);
    }
    lines.push("Under authority");
    if (system.under_authority.length === 0) lines.push("  None.");
    else {
      for (const row of system.under_authority) lines.push(formatPathRow(row));
      lines.push("  These paths are on the list a person approved.");
    }
    lines.push("");
    lines.push("Outside authority");
    if (system.outside_authority.length === 0) lines.push("  None.");
    else {
      for (const row of system.outside_authority) lines.push(formatPathRow(row));
      lines.push("  These paths are still outside that list.");
    }
    lines.push("");
    lines.push("Processes");
    if (system.processes.length === 0) lines.push("  None recorded.");
    for (const processRow of system.processes) {
      const parent = processRow.parent_program ? `, from ${processRow.parent_program}` : "";
      const pid = processRow.pid == null ? "pid not recorded" : `pid ${processRow.pid}`;
      const covered = processRow.covered === false ? "  not covered" : "";
      lines.push(`  ${processRow.program}${parent}  ${pid}  ${processRow.started_at || "time not recorded"}${covered}`);
    }
    lines.push("");
  }
  lines.push("Not covered");
  for (const row of coverage.not_covered) lines.push(`  ${row.summary}`);
  if (coverage.undated_excluded) lines.push(`Undated records outside this window: ${coverage.undated_excluded}`);
  lines.push("");
  lines.push(`Processes seen: ${coverage.counts.processes}`);
  lines.push(`Connections seen: ${coverage.counts.connections}`);
  lines.push("");
  return `${lines.join("\n")}\n`;
}

function sortObservations(observations) {
  return observations.slice().sort((left, right) => {
    const leftTime = Date.parse(left.time || "");
    const rightTime = Date.parse(right.time || "");
    const leftKey = Number.isFinite(leftTime) ? leftTime : Number.POSITIVE_INFINITY;
    const rightKey = Number.isFinite(rightTime) ? rightTime : Number.POSITIVE_INFINITY;
    if (leftKey !== rightKey) return leftKey - rightKey;
    return left.seq - right.seq;
  });
}

function pairKey(observation) {
  return `${observation.kind}\n${observation.program}\n${observation.destination}`;
}

function evaluateNewDestinations(observations, seenPairs, allowlist) {
  const seen = new Map();
  for (const pair of seenPairs || []) {
    if (!pair || typeof pair.destination !== "string" || typeof pair.program !== "string") continue;
    const key = `${pair.kind || "connection"}\n${pair.program}\n${pair.destination}`;
    seen.set(key, pair);
  }
  const alerts = [];
  for (const observation of sortObservations(observations)) {
    if (!observation.destination || observation.destination === "unknown") continue;
    if (observation.kind === "mcp_tool" && !observation.tool_name_retained) continue;
    const key = pairKey(observation);
    if (seen.has(key)) continue;
    const match = matchAllowlist(observation, allowlist);
    const alert = match ? entryAlerts(match, allowlist.alertOnAllowlist) : true;
    const pair = {
      kind: observation.kind,
      program: observation.program,
      destination: observation.destination,
      display: observation.display,
      first_ts: observation.time,
      trace_id: observation.trace_id,
      alerted: alert,
    };
    seen.set(key, pair);
    if (!alert) continue;
    alerts.push({
      schema: ALERT_SCHEMA,
      flag: "new_destination",
      flag_label: "New destination",
      destination: observation.display,
      program: observation.program,
      first_connection: observation.time,
      trace_id: observation.trace_id,
      authority: match ? "under_authority" : "outside_authority",
      kind: observation.kind,
    });
  }
  return { alerts, pairs: [...seen.values()] };
}

function formatDestinationText(alerts) {
  if (!alerts.length) {
    return "Vantio Optics | New destination\nPrompts and completions are never stored.\n\nNo new destination.\n";
  }
  const lines = [
    "Vantio Optics | New destination",
    "Prompts and completions are never stored.",
    "",
  ];
  for (const alert of alerts) {
    lines.push("Flag");
    lines.push(`  ${alert.flag_label}`);
    lines.push("Destination");
    lines.push(`  ${alert.destination}`);
    lines.push("Program");
    lines.push(`  ${alert.program}`);
    lines.push("First connection");
    lines.push(`  ${alert.first_connection || "time not recorded"}`);
    if (alert.trace_id) {
      lines.push("Trace id");
      lines.push(`  ${alert.trace_id}`);
    }
    lines.push("");
  }
  return `${lines.join("\n")}\n`;
}

function loadSeenFile(path) {
  const loaded = readJsonObject(path);
  if (loaded.missing) return { missing: true };
  if (loaded.error) return { error: `could not read ${path}: ${detailOf(loaded.error)}` };
  const json = loaded.json;
  if (!json || typeof json !== "object" || !Array.isArray(json.pairs)) {
    return { error: `seen destinations ${path}: expected an object with pairs` };
  }
  if (json.schema != null && json.schema !== SEEN_SCHEMA) {
    return { error: `seen destinations ${path}: schema must be ${SEEN_SCHEMA}` };
  }
  return { pairs: json.pairs };
}

function loadSeen() {
  const paths = seenCandidates();
  for (let i = 0; i < paths.length; i += 1) {
    const loaded = loadSeenFile(paths[i]);
    if (loaded.missing) continue;
    return loaded;
  }
  return { pairs: [] };
}

function writeJsonAtomic(path, value) {
  mkdirSync(dirname(path), { recursive: true, mode: 0o700 });
  const tmp = `${path}.tmp`;
  writeFileSync(tmp, `${JSON.stringify(value, null, 2)}\n`, { mode: 0o600 });
  renameSync(tmp, path);
}

function otelHex(seed, width) {
  const hex = createHash("sha256").update(String(seed)).digest("hex").slice(0, width);
  return /^0+$/.test(hex) ? `1${"0".repeat(width - 1)}` : hex;
}

function unixNano(iso) {
  const ms = Date.parse(iso || "");
  if (!Number.isFinite(ms)) return "0";
  return `${ms}000000`;
}

function attribute(key, value) {
  if (value == null) return null;
  if (typeof value === "number") return { key, value: { intValue: String(value) } };
  return { key, value: { stringValue: String(value) } };
}

function attributesOf(pairs) {
  return pairs.map(([key, value]) => attribute(key, value)).filter(Boolean);
}

function exportEventFromObservation(observation, allowlist, alertKeys, flaggedAlready) {
  const authority = authorityFor(observation, allowlist);
  const key = pairKey(observation);
  const flagged = alertKeys.has(key) && !flaggedAlready.has(key);
  if (flagged) flaggedAlready.add(key);
  return {
    schema: EXPORT_SCHEMA,
    kind: "observation",
    time: observation.time,
    program: observation.program,
    destination: observation.display,
    method: observation.method,
    path: observation.path,
    bytes: observation.bytes,
    http_status: observation.http_status,
    optics_status: "OBSERVED",
    authority,
    trace_id: observation.trace_id,
    otel_trace_id: otelHex(observation.trace_id || `${observation.program}\n${observation.seq}`, 32),
    otel_span_id: otelHex(`${observation.trace_id}\nobservation\n${observation.seq}`, 16),
    flag: flagged ? "new_destination" : null,
    flag_label: flagged ? "New destination" : null,
    mediation: observation.mediation,
    pid: observation.pid,
    provider: observation.provider,
    system_hostname: observation.system_hostname,
  };
}

function exportEventFromAlert(alert, observation) {
  return {
    schema: EXPORT_SCHEMA,
    kind: "new_destination",
    time: alert.first_connection,
    program: alert.program,
    destination: alert.destination,
    method: observation ? observation.method : null,
    path: observation ? observation.path : null,
    bytes: observation ? observation.bytes : null,
    http_status: observation ? observation.http_status : null,
    optics_status: "OBSERVED",
    authority: alert.authority,
    trace_id: alert.trace_id,
    otel_trace_id: otelHex(alert.trace_id || `${alert.program}\n${alert.destination}`, 32),
    otel_span_id: otelHex(`${alert.trace_id}\nnew_destination\n${alert.destination}`, 16),
    flag: "new_destination",
    flag_label: "New destination",
    mediation: observation ? observation.mediation : null,
    pid: observation ? observation.pid : null,
    provider: observation ? observation.provider : null,
    system_hostname: observation ? observation.system_hostname : null,
  };
}

function buildExportBundle(observations, alerts, allowlist) {
  const ordered = sortObservations(observations);
  const alertKeys = new Set();
  for (const alert of alerts) {
    const sample = ordered.find((observation) => (
      observation.display === alert.destination
      && observation.program === alert.program
      && observation.kind === alert.kind
    ));
    if (sample) alertKeys.add(pairKey(sample));
  }
  const flaggedAlready = new Set();
  const events = [];
  for (const observation of ordered) {
    if (observation.kind === "process") continue;
    events.push(exportEventFromObservation(observation, allowlist, alertKeys, flaggedAlready));
  }
  for (const alert of alerts) {
    const sample = ordered.find((observation) => (
      observation.display === alert.destination
      && observation.program === alert.program
      && observation.kind === alert.kind
    ));
    events.push(exportEventFromAlert(alert, sample || null));
  }
  return events;
}

function resourceAttributes(resource) {
  return attributesOf([
    ["service.name", "vantio.optics"],
    ["host.name", resource.hostname || null],
    ["host.id", resource.machineId || null],
    ["os.type", resource.platform || null],
  ]);
}

function eventAttributes(event) {
  return attributesOf([
    ["server.address", event.destination],
    ["vantio.program", event.program],
    ["vantio.trace_id", event.trace_id],
    ["vantio.authority", event.authority],
    ["vantio.flag", event.flag],
    ["http.request.method", event.method],
    ["url.path", event.path],
    ["http.response.status_code", event.http_status],
    ["vantio.bytes", event.bytes],
    ["gen_ai.provider.name", event.provider],
    ["vantio.mediation", event.mediation],
  ]);
}

function otlpPayloads(events, resource) {
  const observations = events.filter((event) => event.kind === "observation");
  const spans = observations.map((event) => {
    const start = unixNano(event.time);
    return {
      traceId: event.otel_trace_id,
      spanId: event.otel_span_id,
      name: `${event.method || "connect"} ${event.destination}`.slice(0, 128),
      kind: 3,
      startTimeUnixNano: start,
      endTimeUnixNano: start,
      attributes: eventAttributes(event),
      status: {
        code: event.http_status == null ? 0 : (event.http_status >= 400 ? 2 : 1),
      },
    };
  });
  const totals = new Map();
  for (const event of observations) {
    if (event.bytes == null) continue;
    const key = `${event.destination}\n${event.program}`;
    const row = totals.get(key) || {
      destination: event.destination,
      program: event.program,
      bytes: 0,
      time: event.time,
    };
    row.bytes += event.bytes;
    if (event.time && (!row.time || event.time > row.time)) row.time = event.time;
    totals.set(key, row);
  }
  const points = [...totals.values()].map((row) => ({
    timeUnixNano: unixNano(row.time),
    asInt: String(row.bytes),
    attributes: attributesOf([
      ["server.address", row.destination],
      ["vantio.program", row.program],
    ]),
  }));
  const logRecords = events.map((event) => ({
    timeUnixNano: unixNano(event.time),
    observedTimeUnixNano: unixNano(event.time),
    severityNumber: event.flag === "new_destination" && event.kind === "new_destination" ? 13 : 9,
    severityText: event.flag === "new_destination" && event.kind === "new_destination" ? "WARN" : "INFO",
    body: { stringValue: event.kind === "new_destination" ? "New destination" : "Observed" },
    attributes: eventAttributes(event),
    traceId: event.otel_trace_id,
    spanId: event.otel_span_id,
  }));
  const resourceBlock = { attributes: resourceAttributes(resource || {}) };
  return {
    traces: {
      resourceSpans: [{
        resource: resourceBlock,
        scopeSpans: [{ scope: { name: "vantio.optics" }, spans }],
      }],
    },
    metrics: {
      resourceMetrics: [{
        resource: resourceBlock,
        scopeMetrics: [{
          scope: { name: "vantio.optics" },
          metrics: [{
            name: "vantio.optics.bytes",
            unit: "By",
            gauge: { dataPoints: points },
          }],
        }],
      }],
    },
    logs: {
      resourceLogs: [{
        resource: resourceBlock,
        scopeLogs: [{ scope: { name: "vantio.optics" }, logRecords }],
      }],
    },
  };
}

function publicExportEvent(event) {
  return {
    schema: event.schema,
    kind: event.kind,
    time: event.time,
    program: event.program,
    destination: event.destination,
    method: event.method,
    path: event.path,
    bytes: event.bytes,
    http_status: event.http_status,
    optics_status: event.optics_status,
    authority: event.authority,
    trace_id: event.trace_id,
    otel_trace_id: event.otel_trace_id,
    flag: event.flag,
    flag_label: event.flag_label,
    mediation: event.mediation,
    pid: event.pid,
    system_hostname: event.system_hostname,
  };
}

function formatJsonLines(events) {
  return events.map((event) => `${JSON.stringify(publicExportEvent(event))}\n`).join("");
}

function syslogToken(value, fallback) {
  const text = cleanToken(value, 255);
  if (!text) return fallback;
  return text.replace(/[^\x21-\x7e]/g, "_");
}

function formatSyslogLines(events, meta) {
  const host = syslogToken(meta && meta.hostname, "localhost");
  return events.map((event) => {
    const alert = event.kind === "new_destination";
    const severity = alert ? 4 : 6;
    const pri = 16 * 8 + severity;
    const time = syslogToken(event.time, "-");
    const proc = event.pid == null ? "-" : String(event.pid);
    const msgid = alert ? "new_destination" : "observation";
    return `<${pri}>1 ${time} ${host} vantio ${proc} ${msgid} - ${JSON.stringify(publicExportEvent(event))}\n`;
  }).join("");
}

function assertExportUrl(raw, label) {
  let parsed;
  try {
    parsed = new URL(raw);
  } catch {
    throw new Error(`${label} URL is not valid`);
  }
  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
    throw new Error(`${label} URL must be http or https`);
  }
  if (parsed.username || parsed.password) throw new Error(`${label} URL must not contain credentials`);
  if (parsed.protocol === "http:") {
    const host = parsed.hostname.replace(/^\[|\]$/g, "").toLowerCase();
    const loopback = host === "localhost" || host === "127.0.0.1" || host === "::1";
    if (!loopback) throw new Error(`${label} refuses plaintext to a remote host`);
  }
  return parsed;
}

function joinUrl(base, suffix) {
  const url = new URL(base);
  const prefix = url.pathname.replace(/\/$/, "");
  url.pathname = `${prefix}${suffix}`;
  url.search = "";
  url.hash = "";
  return url;
}

function postJson(url, body, headers) {
  const payload = Buffer.from(JSON.stringify(body));
  const lib = url.protocol === "https:" ? httpsRequest : httpRequest;
  return new Promise((resolve, reject) => {
    const req = lib({
      protocol: url.protocol,
      hostname: url.hostname,
      port: url.port || undefined,
      path: `${url.pathname}${url.search}`,
      method: "POST",
      headers: Object.assign({
        "content-type": "application/json",
        "content-length": String(payload.length),
      }, headers || {}),
      timeout: 10000,
    }, (res) => {
      res.on("data", () => {});
      res.on("end", () => resolve({ status: res.statusCode || 0 }));
    });
    req.on("error", reject);
    req.on("timeout", () => {
      req.destroy(new Error("timeout"));
    });
    req.end(payload);
  });
}

function parseSyslogTarget(value) {
  if (value == null || value === "" || value === "-") return { kind: "stdio" };
  if (!String(value).includes("://")) return { kind: "file", path: String(value) };
  let parsed;
  try {
    parsed = new URL(value);
  } catch {
    throw new Error("syslog target is not a valid URL or file path");
  }
  if (parsed.username || parsed.password) throw new Error("syslog URL must not contain credentials");
  if (parsed.protocol !== "udp:" && parsed.protocol !== "tcp:") {
    throw new Error("syslog URL must be udp or tcp, or a file path");
  }
  if (!parsed.port) throw new Error("syslog URL needs a port");
  const port = Number(parsed.port);
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error("syslog port is not valid");
  return { kind: parsed.protocol === "udp:" ? "udp" : "tcp", host: parsed.hostname, port };
}

function writeLines(target, text) {
  if (target === "-") {
    process.stdout.write(text);
    return;
  }
  mkdirSync(dirname(target), { recursive: true, mode: 0o700 });
  appendFileSync(target, text, { mode: 0o600 });
}

function sendUdp(host, port, text) {
  const lines = String(text).split("\n").filter((line) => line.length > 0);
  const family = host.includes(":") ? "udp6" : "udp4";
  return new Promise((resolve, reject) => {
    const socket = dgram.createSocket(family);
    let settled = false;
    const timer = setTimeout(() => {
      finish(new Error("syslog udp timeout"));
    }, 10000);
    let index = 0;
    const finish = (err) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      try { socket.close(); } catch { /* already closed */ }
      if (err) reject(err);
      else resolve();
    };
    const next = (err) => {
      if (err) {
        finish(err);
        return;
      }
      if (index >= lines.length) {
        finish();
        return;
      }
      const line = lines[index];
      index += 1;
      socket.send(Buffer.from(`${line}\n`), port, host, next);
    };
    socket.once("error", finish);
    next();
  });
}

function sendTcp(host, port, text) {
  return new Promise((resolve, reject) => {
    const socket = net.connect({ host, port });
    const timer = setTimeout(() => {
      socket.destroy();
      reject(new Error("syslog tcp timeout"));
    }, 10000);
    socket.once("error", (err) => {
      clearTimeout(timer);
      reject(err);
    });
    socket.once("connect", () => {
      socket.end(text, () => {
        clearTimeout(timer);
        resolve();
      });
    });
  });
}

function writeSyslog(target, text) {
  if (target.kind === "stdio") writeLines("-", text);
  else if (target.kind === "file") writeLines(target.path, text);
  else if (target.kind === "udp") return sendUdp(target.host, target.port, text);
  return sendTcp(target.host, target.port, text);
}

function sinkDone(completed, name) {
  return completed instanceof Set && completed.has(name);
}

function sinkMark(completed, name) {
  if (completed instanceof Set) completed.add(name);
}

async function deliverExport(events, options) {
  const sinks = [];
  const completed = options.completed;
  const syslogText = options.syslog
    ? formatSyslogLines(events, { hostname: options.resource && options.resource.hostname })
    : "";
  const syslogTarget = options.syslog ? parseSyslogTarget(options.syslog) : null;
  if (options.otlpGrpc && !sinkDone(completed, "otlp-grpc")) {
    const payloads = otlpPayloads(events, options.resource);
    await deliverOtlpGrpc(options.otlpGrpc, payloads, completed);
    sinkMark(completed, "otlp-grpc");
    sinks.push("otlp-grpc");
  }
  if (options.otlp && !sinkDone(completed, "otlp")) {
    assertExportUrl(options.otlp, "otlp");
    const payloads = otlpPayloads(events, options.resource);
    const signals = [
      ["traces", payloads.traces],
      ["metrics", payloads.metrics],
      ["logs", payloads.logs],
    ];
    for (const [signal, body] of signals) {
      const key = `otlp:${signal}`;
      if (sinkDone(completed, key)) continue;
      const response = await postJson(joinUrl(options.otlp, `/v1/${signal}`), body);
      if (response.status < 200 || response.status > 299) {
        throw new Error(`otlp ${signal} returned ${response.status}`);
      }
      sinkMark(completed, key);
    }
    sinkMark(completed, "otlp");
    sinks.push("otlp");
  }
  if (options.webhook && !sinkDone(completed, "webhook")) {
    assertExportUrl(options.webhook, "webhook");
    const headers = {};
    if (options.webhookToken) headers.authorization = `Bearer ${options.webhookToken}`;
    const response = await postJson(new URL(options.webhook), {
      schema: EXPORT_SCHEMA,
      schema_status: SCHEMA_STATUS,
      events: events.map(publicExportEvent),
    }, headers);
    if (response.status < 200 || response.status > 299) {
      throw new Error(`webhook returned ${response.status}`);
    }
    sinkMark(completed, "webhook");
    sinks.push("webhook");
  }
  if (syslogTarget && (syslogTarget.kind === "udp" || syslogTarget.kind === "tcp") && !sinkDone(completed, "syslog")) {
    await writeSyslog(syslogTarget, syslogText);
    sinkMark(completed, "syslog");
    sinks.push("syslog");
  }
  if (options.jsonl && !sinkDone(completed, "jsonl")) {
    writeLines(options.jsonl, formatJsonLines(events));
    sinkMark(completed, "jsonl");
    sinks.push("jsonl");
  }
  if (syslogTarget && syslogTarget.kind !== "udp" && syslogTarget.kind !== "tcp" && !sinkDone(completed, "syslog")) {
    writeSyslog(syslogTarget, syslogText);
    sinkMark(completed, "syslog");
    sinks.push("syslog");
  }
  return sinks;
}

function alertsInWindow(alerts, cutoff) {
  if (cutoff == null) return alerts;
  return alerts.filter((alert) => inWindow(alert.first_connection, cutoff));
}

function loadBundle(since, explicitAllowlist, now) {
  const window = cutoffFromSince(since, now);
  if (window.error) return { error: window.error };
  const allow = loadAllowlist(explicitAllowlist);
  if (allow.error) return { error: allow.error };
  const roots = dataRoots(process.env);
  const logs = listRunLogs(roots);
  if (logs.error) return { error: logs.error };
  const mcp = listMcpRecords(roots);
  if (mcp.error) return { error: mcp.error };
  const localHost = osHostname();
  const all = collectObservations(logs.logs, mcp.records, localHost, null);
  const collected = window.cutoff == null
    ? all
    : collectObservations(logs.logs, mcp.records, localHost, window.cutoff);
  return {
    allowlist: allow.allowlist,
    allowlistPath: allow.path,
    observations: collected.observations,
    allObservations: all.observations,
    undatedExcluded: collected.undatedExcluded,
    cutoff: window.cutoff,
    localHost,
    platform: osPlatform(),
    machineId: readMachineId(),
    since,
  };
}

function coverageCommand(args) {
  const { values } = parseArgsSafe("coverage", {
    args,
    options: {
      since: { type: "string", default: "all" },
      allowlist: { type: "string" },
      json: { type: "boolean", default: false },
      help: { type: "boolean", short: "h", default: false },
    },
    allowPositionals: false,
  });
  if (values.help) {
    process.stdout.write(COVERAGE_HELP);
    return;
  }
  const bundle = loadBundle(values.since, values.allowlist, Date.now());
  if (bundle.error) fail("coverage", bundle.error);
  const proc = procGapsForCoverage(bundle);
  const coverage = buildCoverage({
    observations: bundle.observations,
    allowlist: bundle.allowlist,
    allowlistPath: bundle.allowlistPath,
    localHost: bundle.localHost,
    platform: bundle.platform,
    machineId: bundle.machineId,
    since: bundle.since,
    undatedExcluded: bundle.undatedExcluded,
    procGaps: proc.processes,
    proc: { readable: proc.readable },
    procNote: proc.readable ? null : { id: "proc_unreadable", summary: proc.reason },
  });
  if (values.json) {
    process.stdout.write(`${JSON.stringify(withSchema(Object.assign({ command: "coverage" }, coverage)), null, 2)}\n`);
    return;
  }
  process.stdout.write(formatCoverageText(coverage));
}

function seenPath() {
  return join(primaryHome(), "seen-destinations.json");
}

function seenCandidates() {
  const paths = [seenPath()];
  const fallback = join(configHome(), "seen-destinations.json");
  if (!paths.includes(fallback)) paths.push(fallback);
  return paths;
}

function destinationsCommand(args) {
  const { values } = parseArgsSafe("destinations", {
    args,
    options: {
      since: { type: "string", default: "all" },
      allowlist: { type: "string" },
      "dry-run": { type: "boolean", default: false },
      json: { type: "boolean", default: false },
      help: { type: "boolean", short: "h", default: false },
    },
    allowPositionals: false,
  });
  if (values.help) {
    process.stdout.write(DESTINATIONS_HELP);
    return;
  }
  const bundle = loadBundle(values.since, values.allowlist, Date.now());
  if (bundle.error) fail("destinations", bundle.error);
  const path = seenPath();
  const seen = loadSeen();
  if (seen.error) fail("destinations", seen.error);
  const evaluated = evaluateNewDestinations(bundle.allObservations, seen.pairs, bundle.allowlist);
  evaluated.alerts = alertsInWindow(evaluated.alerts, bundle.cutoff);
  if (!values["dry-run"]) {
    try {
      writeJsonAtomic(path, { schema: SEEN_SCHEMA, pairs: evaluated.pairs });
    } catch (err) {
      fail("destinations", `could not write ${path}: ${detailOf(err)}`);
    }
  }
  const report = withSchema({
    command: "destinations",
    schema: ALERT_SCHEMA,
    dry_run: values["dry-run"] === true,
    alerts: evaluated.alerts,
  });
  if (values.json) {
    process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
    return;
  }
  process.stdout.write(formatDestinationText(evaluated.alerts));
}

function validateWebhookToken(token) {
  if (token == null || token === "") return "";
  if (typeof token !== "string" || /[\r\n]/.test(token) || token.length > 4096) {
    return { error: "webhook token is not valid" };
  }
  return token;
}

function webhookToken() {
  const token = validateWebhookToken(process.env.VANTIO_EXPORT_WEBHOOK_TOKEN);
  if (token && typeof token === "object") fail("export", token.error);
  return token;
}

async function exportCommand(args) {
  const { values } = parseArgsSafe("export", {
    args,
    options: {
      otlp: { type: "string" },
      "otlp-grpc": { type: "string" },
      jsonl: { type: "string" },
      syslog: { type: "string" },
      webhook: { type: "string" },
      since: { type: "string", default: "all" },
      allowlist: { type: "string" },
      follow: { type: "boolean", default: false },
      "dry-run": { type: "boolean", default: false },
      json: { type: "boolean", default: false },
      help: { type: "boolean", short: "h", default: false },
    },
    allowPositionals: false,
  });
  if (values.help) {
    process.stdout.write(EXPORT_HELP);
    return;
  }
  const sinks = resolveExportSinks(values);
  const sinksRequested = Object.keys(sinks);
  if (sinksRequested.length === 0) {
    fail("export", "no destination. Set --otlp, --otlp-grpc, --jsonl, --syslog, or --webhook.");
  }
  if (values.follow && values["dry-run"]) fail("export", "--follow cannot be combined with --dry-run");
  if (values.follow && values.json) fail("export", "--follow cannot be combined with --json");
  if (values.json && (values.jsonl === "-" || values.syslog === "-")) {
    fail("export", "--json cannot be combined with stdout --jsonl or --syslog");
  }
  if (values.jsonl === "-" && values.syslog === "-") {
    fail("export", "--jsonl=- and --syslog=- both write to stdout");
  }
  if (values.follow) {
    await runFollowExport(sinks);
    return;
  }
  const bundle = loadBundle(values.since, values.allowlist, Date.now());
  if (bundle.error) fail("export", bundle.error);
  const path = seenPath();
  const seen = loadSeen();
  if (seen.error) fail("export", seen.error);
  const evaluated = evaluateNewDestinations(bundle.allObservations, seen.pairs, bundle.allowlist);
  evaluated.alerts = alertsInWindow(evaluated.alerts, bundle.cutoff);
  const events = buildExportBundle(bundle.observations, evaluated.alerts, bundle.allowlist);
  const resource = {
    hostname: bundle.localHost,
    platform: bundle.platform,
    machineId: bundle.machineId,
  };
  if (values["dry-run"] || events.length === 0) {
    const report = withSchema({
      command: "export",
      schema: EXPORT_SCHEMA,
      dry_run: values["dry-run"] === true,
      events: events.length,
      alerts: evaluated.alerts.length,
      sinks: sinksRequested,
      delivered: false,
    });
    if (values.json) process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
    else if (events.length === 0) process.stdout.write("No events.\n");
    else process.stdout.write(`Dry run. ${events.length} event(s), ${evaluated.alerts.length} new destination flag(s). Nothing was sent.\n`);
    return;
  }
  let delivered;
  try {
    delivered = await deliverExport(events, Object.assign({
      webhookToken: sinks.webhook ? webhookToken() : "",
      resource,
    }, sinks));
  } catch (err) {
    fail("export", detailOf(err));
  }
  try {
    writeJsonAtomic(path, { schema: SEEN_SCHEMA, pairs: evaluated.pairs });
  } catch (err) {
    fail("export", `could not write ${path}: ${detailOf(err)}`);
  }
  const report = withSchema({
    command: "export",
    schema: EXPORT_SCHEMA,
    dry_run: false,
    events: events.length,
    alerts: evaluated.alerts.length,
    sinks: delivered,
    delivered: true,
  });
  if (values.json) process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
  else process.stdout.write(`Exported ${events.length} event(s) to ${delivered.join(", ")}.\n`);
}

function connectionDepth(conn, byPid) {
  let depth = 0;
  let current = conn && Number.isInteger(conn.pid) ? conn.pid : null;
  const seen = new Set();
  while (current != null && !seen.has(current)) {
    seen.add(current);
    depth += 1;
    const proc = byPid.get(current);
    const parent = proc && Number.isInteger(proc.ppid) ? proc.ppid : null;
    if (parent == null || !byPid.has(parent)) break;
    current = parent;
  }
  return depth;
}

function runLogFile(traceId) {
  const safe = String(traceId || "unknown").replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 80);
  return join(primaryHome(), "runs", `${safe}.json`);
}

function recordWrappedRun(input) {
  const traceId = input.traceId;
  const path = runLogFile(traceId);
  mkdirSync(dirname(path), { recursive: true, mode: 0o700 });
  let existing = null;
  if (existsSync(path)) {
    const loaded = readJsonObject(path);
    if (loaded.error) throw new Error(`could not read ${path}: ${detailOf(loaded.error)}`);
    if (loaded.json && loaded.json.vantio_run_log === "1") existing = loaded.json;
  }
  const calls = existing && Array.isArray(existing.calls) ? existing.calls.map((call) => ({ ...call })) : [];
  const seenDest = new Set(calls.map((call) => normalizeHost(call.hostname)).filter(Boolean));
  const byPid = new Map();
  for (const proc of input.processes || []) {
    if (proc && Number.isInteger(proc.pid)) byPid.set(proc.pid, proc);
  }
  const ordered = (input.connections || []).slice().sort((left, right) => (
    connectionDepth(right, byPid) - connectionDepth(left, byPid)
  ));
  const stamp = new Date().toISOString();
  for (const conn of ordered) {
    const destination = normalizeHost(conn.destination) || cleanToken(conn.destination, 253);
    if (!destination || seenDest.has(destination)) continue;
    seenDest.add(destination);
    calls.push({
      hostname: destination,
      provider: null,
      method: null,
      path: null,
      scheme: null,
      request_bytes: null,
      bytes: 0,
      status: null,
      ok: null,
      content_type: null,
      duration_ms: null,
      action: "OBSERVED",
      ts: stamp,
      mediation: "proc_socket",
      port: Number.isInteger(conn.port) ? conn.port : null,
      pid: Number.isInteger(conn.pid) ? conn.pid : null,
      ppid: Number.isInteger(conn.ppid) ? conn.ppid : null,
      program: cleanToken(conn.program, 256),
    });
  }
  const processes = [];
  const seenPid = new Set();
  const root = {
    pid: Number.isInteger(input.pid) ? input.pid : null,
    ppid: Number.isInteger(input.ppid) ? input.ppid : null,
    program: cleanToken(input.program, 256) || "unknown",
  };
  if (root.pid != null) {
    processes.push(root);
    seenPid.add(root.pid);
  }
  for (const proc of input.processes || []) {
    if (proc.pid == null || seenPid.has(proc.pid)) continue;
    seenPid.add(proc.pid);
    processes.push({
      pid: proc.pid,
      ppid: Number.isInteger(proc.ppid) ? proc.ppid : null,
      program: cleanToken(proc.program, 256) || "unknown",
    });
  }
  const hosts = [...seenDest];
  const log = Object.assign({}, existing || {}, {
    vantio_run_log: "1",
    schema_version: existing && existing.schema_version ? existing.schema_version : 2,
    plane: "optics",
    data_note: "Metadata only. Prompts and completions are never stored.",
    trace_id: traceId,
    program: (existing && existing.program) || root.program,
    pid: (existing && existing.pid) || root.pid,
    ppid: existing && existing.ppid != null ? existing.ppid : root.ppid,
    system_hostname: (existing && existing.system_hostname) || osHostname(),
    platform: (existing && existing.platform) || osPlatform(),
    started_at: (existing && existing.started_at) || input.startedAt || stamp,
    generated_at: stamp,
    calls,
    processes,
    summary: Object.assign({}, existing && existing.summary, {
      total_calls: calls.length,
      hosts,
    }),
    socket_observation: "read_only_proc",
  });
  writeJsonAtomic(path, log);
  return { path, log };
}

function readProcGaps(observations, options) {
  const covered = [];
  for (const observation of observations || []) {
    if (observation.pid == null || !observation.program) continue;
    covered.push({ pid: observation.pid, program: observation.program });
  }
  const opts = options || {};
  const procRoot = opts.procRoot || (process.platform === "linux" ? "/proc" : null);
  if (!procRoot) {
    return {
      readable: false,
      reason: "This system has no local process table to read.",
      processes: [],
    };
  }
  return discoverUncovered({
    procRoot,
    hostsPath: opts.hostsPath || "/etc/hosts",
    covered,
    selfPid: opts.selfPid != null ? opts.selfPid : process.pid,
    isAiHost: opts.isAiHost || ((host, port) => catalogInScope(host, port, LLM_HOSTS)),
  });
}

function procGapsForCoverage(bundle, options) {
  const source = bundle && Array.isArray(bundle.allObservations)
    ? bundle.allObservations
    : (bundle && bundle.observations) || [];
  return readProcGaps(source, options);
}

function localClock(value) {
  const date = value instanceof Date ? value : new Date(value || Date.now());
  if (Number.isNaN(date.getTime())) return null;
  const part = (number) => String(number).padStart(2, "0");
  return `${part(date.getHours())}:${part(date.getMinutes())}:${part(date.getSeconds())}`;
}

function formatLiveAlert(event) {
  return [
    "New destination",
    `  First connection: ${event.clock || "time not recorded"}`,
    `  Destination: ${event.destination}`,
    `  Program: ${event.program}`,
    "",
  ].join("\n");
}

function liveJournalPath() {
  return join(primaryHome(), "live.jsonl");
}

function withSeenLock(fn) {
  const lock = join(primaryHome(), "seen.lock");
  mkdirSync(primaryHome(), { recursive: true, mode: 0o700 });
  const started = Date.now();
  while (true) {
    try {
      mkdirSync(lock);
      break;
    } catch (err) {
      if (!err || err.code !== "EEXIST") throw err;
      if (Date.now() - started > 2000) throw new Error("seen destination file is busy");
    }
  }
  try {
    return fn();
  } finally {
    try { rmSync(lock, { recursive: true }); } catch { /* lock already gone */ }
  }
}

function noteLiveCall(call, meta) {
  if (!call || typeof call !== "object") return null;
  const host = normalizeHost(call.hostname);
  if (!host) return null;
  const source = meta || {};
  return withSeenLock(() => {
    const allow = loadAllowlist(null);
    if (allow.error) throw new Error(allow.error);
    const seen = loadSeen();
    if (seen.error) throw new Error(seen.error);
    const when = call.ts || new Date().toISOString();
    const observation = {
      seq: 0,
      kind: "connection",
      program: source.program || "unknown",
      destination: host,
      display: host,
      time: when,
      trace_id: source.trace_id || null,
      pid: Number.isInteger(source.pid) ? source.pid : null,
      method: cleanToken(call.method, 16),
      path: stripPath(call.path),
      bytes: callBytes(call),
      http_status: normalizeHttpStatus(call.status != null ? call.status : call.httpStatus),
      mediation: cleanToken(call.mediation, 64),
      provider: cleanToken(call.provider, 64),
      system_hostname: cleanToken(source.system_hostname, 253),
    };
    const evaluated = evaluateNewDestinations([observation], seen.pairs, allow.allowlist);
    writeJsonAtomic(seenPath(), { schema: SEEN_SCHEMA, pairs: evaluated.pairs });
    const alert = evaluated.alerts[0] || null;
    const event = {
      schema: LIVE_SCHEMA,
      kind: alert ? "new_destination" : "observation",
      flag: alert ? "new_destination" : null,
      flag_label: alert ? "New destination" : null,
      clock: localClock(when),
      time: when,
      program: observation.program,
      destination: observation.display,
      trace_id: observation.trace_id,
      pid: observation.pid,
      method: observation.method,
      path: observation.path,
      bytes: observation.bytes,
      http_status: observation.http_status,
      authority: alert ? alert.authority : authorityFor(observation, allow.allowlist),
      system_hostname: observation.system_hostname,
    };
    const path = liveJournalPath();
    mkdirSync(dirname(path), { recursive: true, mode: 0o700 });
    appendFileSync(path, `${JSON.stringify(event)}\n`, { mode: 0o600 });
    return event;
  });
}

function noteWrappedSocket(conn, meta) {
  if (!conn || typeof conn !== "object") return null;
  const destination = normalizeHost(conn.destination) || cleanToken(conn.destination, 253);
  if (!destination) return null;
  return noteLiveCall({
    hostname: destination,
    bytes: 0,
    ts: new Date().toISOString(),
    mediation: "proc_socket",
  }, {
    program: cleanToken(conn.program, 256) || "unknown",
    trace_id: meta && meta.trace_id,
    pid: Number.isInteger(conn.pid) ? conn.pid : null,
    system_hostname: meta && meta.system_hostname,
  });
}

function envText(value) {
  return typeof value === "string" && value.trim() ? value.trim() : "";
}

function resolveExportSinks(values) {
  const sinks = {};
  const otlp = values.otlp || envText(process.env.VANTIO_EXPORT_OTLP);
  const otlpGrpc = values["otlp-grpc"] || envText(process.env.VANTIO_EXPORT_OTLP_GRPC);
  const jsonl = values.jsonl || envText(process.env.VANTIO_EXPORT_JSONL);
  const syslog = values.syslog || envText(process.env.VANTIO_EXPORT_SYSLOG);
  const webhook = values.webhook || envText(process.env.VANTIO_EXPORT_WEBHOOK);
  if (otlp) sinks.otlp = otlp;
  if (otlpGrpc) sinks.otlpGrpc = otlpGrpc;
  if (jsonl) sinks.jsonl = jsonl;
  if (syslog) sinks.syslog = syslog;
  if (webhook) sinks.webhook = webhook;
  return sinks;
}

function backoffMs(attempt) {
  const step = Number.isFinite(attempt) && attempt > 0 ? attempt : 0;
  return Math.min(10000, 250 * (2 ** step));
}

function createFollowBuffer(max) {
  const limit = max || LIVE_BUFFER_MAX;
  const items = [];
  let dropped = 0;
  return {
    push(event) {
      items.push(event);
      while (items.length > limit) {
        items.shift();
        dropped += 1;
      }
      return dropped;
    },
    drain(count) {
      return items.splice(0, count || items.length);
    },
    size() {
      return items.length;
    },
    dropped() {
      return dropped;
    },
  };
}

function liveToExportEvent(event) {
  const trace = event.trace_id || `${event.program}\n${event.destination}`;
  return {
    schema: EXPORT_SCHEMA,
    kind: event.kind === "new_destination" ? "new_destination" : "observation",
    time: event.time,
    program: event.program,
    destination: event.destination,
    method: event.method || null,
    path: event.path || null,
    bytes: event.bytes == null ? null : event.bytes,
    http_status: event.http_status == null ? null : event.http_status,
    optics_status: "OBSERVED",
    authority: event.authority || "outside_authority",
    trace_id: event.trace_id || null,
    otel_trace_id: otelHex(trace, 32),
    otel_span_id: otelHex(`${trace}\n${event.time || ""}\n${event.destination}`, 16),
    flag: event.flag || null,
    flag_label: event.flag_label || null,
    mediation: null,
    pid: event.pid == null ? null : event.pid,
    provider: null,
    system_hostname: event.system_hostname || null,
  };
}

function readLiveChunk(path, offset) {
  if (!existsSync(path)) return { events: [], offset, error: null };
  let size = offset;
  try {
    size = statSync(path).size;
  } catch (err) {
    return { events: [], offset, error: err };
  }
  if (size < offset) offset = 0;
  if (size === offset) return { events: [], offset, error: null };
  let text = "";
  let fd;
  try {
    fd = openSync(path, "r");
    const length = size - offset;
    const buf = Buffer.alloc(length);
    readSync(fd, buf, 0, length, offset);
    text = buf.toString("utf8");
  } catch (err) {
    return { events: [], offset, error: err };
  } finally {
    if (fd != null) {
      try { closeSync(fd); } catch { /* already closed */ }
    }
  }
  const events = [];
  let rest = text;
  let newline = rest.indexOf("\n");
  let consumed = 0;
  while (newline >= 0) {
    const line = rest.slice(0, newline).trim();
    consumed += newline + 1;
    rest = rest.slice(newline + 1);
    newline = rest.indexOf("\n");
    if (!line) continue;
    try {
      events.push(JSON.parse(line));
    } catch (err) {
      events.push({ error: err, raw: line.slice(0, 80) });
    }
  }
  return { events, offset: offset + consumed, error: null };
}

function watchLiveJournal(onEvent) {
  const path = liveJournalPath();
  mkdirSync(dirname(path), { recursive: true, mode: 0o700 });
  let offset = 0;
  try {
    if (existsSync(path)) offset = statSync(path).size;
  } catch {
    offset = 0;
  }
  const timer = setInterval(() => {
    const chunk = readLiveChunk(path, offset);
    offset = chunk.offset;
    if (chunk.error) {
      onEvent({ error: chunk.error });
      return;
    }
    for (const event of chunk.events) onEvent(event);
  }, 200);
  return () => clearInterval(timer);
}

async function stepFollowExport(state) {
  if (state.pending.length === 0) state.pending = state.buffer.drain(100);
  if (state.pending.length === 0) {
    const chunk = readLiveChunk(state.path, state.offset);
    state.offset = chunk.offset;
    state.readError = chunk.error || null;
    if (!chunk.error) {
      for (const event of chunk.events) {
        if (event.error) {
          state.badLine = true;
          continue;
        }
        state.dropped = state.buffer.push(liveToExportEvent(event));
      }
    }
    state.pending = state.buffer.drain(100);
  }
  if (state.pending.length === 0) return "idle";
  try {
    await deliverExport(state.pending, state.deliverOptions);
    state.pending = [];
    state.deliverOptions.completed = new Set();
    state.attempt = 0;
    return "sent";
  } catch (err) {
    state.lastError = err;
    return "retry";
  }
}

async function runFollowExport(sinks) {
  const buffer = createFollowBuffer(LIVE_BUFFER_MAX);
  const resource = {
    hostname: osHostname(),
    platform: osPlatform(),
    machineId: readMachineId(),
  };
  const token = sinks.webhook ? webhookToken() : "";
  let offset = 0;
  const path = liveJournalPath();
  try {
    if (existsSync(path)) offset = statSync(path).size;
  } catch {
    offset = 0;
  }
  const state = {
    path,
    offset,
    buffer,
    pending: [],
    attempt: 0,
    dropped: 0,
    deliverOptions: Object.assign({ webhookToken: token, resource, completed: new Set() }, sinks),
    readError: null,
    badLine: false,
    lastError: null,
  };
  let announced = 0;
  let stopped = false;
  const stop = () => { stopped = true; };
  process.on("SIGINT", stop);
  process.on("SIGTERM", stop);
  process.stderr.write("[ ∅ VANTIO ] Following live events (Ctrl+C to stop)…\n");
  while (!stopped) {
    const outcome = await stepFollowExport(state);
    if (state.readError) {
      process.stderr.write(`vantio export: could not read live events: ${detailOf(state.readError)}\n`);
      state.readError = null;
    }
    if (state.badLine) {
      process.stderr.write("vantio export: skipped a live line that is not JSON\n");
      state.badLine = false;
    }
    if (state.dropped > announced) {
      process.stderr.write(`vantio export: buffer full, dropped ${droppedDelta(announced, state.dropped)}\n`);
      announced = state.dropped;
    }
    if (outcome === "idle") {
      await new Promise((resolve) => setTimeout(resolve, 200));
      continue;
    }
    if (outcome === "retry") {
      const wait = backoffMs(state.attempt);
      state.attempt += 1;
      process.stderr.write(`vantio export: ${detailOf(state.lastError)}. Retrying in ${wait}ms\n`);
      await new Promise((resolve) => setTimeout(resolve, wait));
    }
  }
  if (state.pending.length) {
    try {
      await deliverExport(state.pending, state.deliverOptions);
    } catch (err) {
      fail("export", detailOf(err));
    }
  }
}

function droppedDelta(announced, dropped) {
  return dropped - announced;
}

module.exports = {
  ALLOWLIST_SCHEMA,
  COVERAGE_HELP,
  DESTINATIONS_HELP,
  EXPORT_HELP,
  EXPORT_SCHEMA,
  NOT_COVERED,
  SEEN_SCHEMA,
  assertExportUrl,
  buildCoverage,
  buildExportBundle,
  collectObservations,
  coverageCommand,
  deliverExport,
  destinationsCommand,
  evaluateNewDestinations,
  exportCommand,
  backoffMs,
  createFollowBuffer,
  formatCoverageText,
  formatDestinationText,
  formatJsonLines,
  formatLiveAlert,
  formatSyslogLines,
  liveJournalPath,
  localClock,
  noteLiveCall,
  noteWrappedSocket,
  otlpPayloads,
  parseAllowlist,
  parseSyslogTarget,
  programLabelFromArgv,
  publicExportEvent,
  procGapsForCoverage,
  recordWrappedRun,
  stepFollowExport,
  validateWebhookToken,
  watchLiveJournal,
};
