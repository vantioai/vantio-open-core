import { lstatSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const fixturePath = join(scriptDir, "../../../../scripts/fixtures/minimal-agent.js");

function fail(reason) {
  process.stderr.write(`clean-host: run rejected: ${reason}\n`);
  process.exit(27);
}

const runPath = process.argv[2];
if (!runPath) fail("run file argument is required");

let info;
try {
  info = lstatSync(runPath);
} catch {
  fail("run file is missing");
}
if (!info.isFile() || info.isSymbolicLink()) fail("run file must be a regular file");

const raw = readFileSync(runPath, "utf8");
let log;
try {
  log = JSON.parse(raw);
} catch {
  fail("run file is not JSON");
}

const fixture = readFileSync(fixturePath, "utf8");
const modelMatch = /model:\s*"([^"]+)"/.exec(fixture);
if (!modelMatch) fail("fixture model string was not found");
if (raw.includes(modelMatch[1])) fail("fixture model string is present in the run file");

if (log.vantio_run_log !== "1") fail("vantio_run_log");
if (log.schema_version !== 2) fail("schema_version");
if (log.plane !== "optics") fail("plane");
if (log.free_mode !== true) fail("free_mode");
if (Object.prototype.hasOwnProperty.call(log, "evidence_tier")) fail("run file carries an evidence tier");
if (Object.prototype.hasOwnProperty.call(log, "workflow")) fail("workflow field is present");
if (!Array.isArray(log.calls) || log.calls.length !== 1) fail("call count");

const call = log.calls[0];
if (call.action !== "OBSERVED") fail("action");
if (call.hostname !== "127.0.0.1") fail("hostname");
if (call.method !== "POST") fail("method");
if (call.path !== "/v1/chat/completions") fail("path");
if (call.ok !== true) fail("ok");
if (call.status !== 200) fail("status");
if (call.error != null) fail("error");
if (typeof call.request_bytes !== "number" || call.request_bytes <= 0) fail("request_bytes");
if (typeof call.bytes !== "number" || call.bytes <= 0) fail("bytes");

const summary = log.summary;
if (!summary || typeof summary !== "object") fail("summary");
if (summary.blocked !== 0) fail("blocked");
if (summary.redacted !== 0) fail("redacted");
if (summary.total_calls !== 1) fail("total_calls");
if (summary.est_spend_usd !== null) fail("est_spend_usd");

const hosts = summary.hosts;
if (!Array.isArray(hosts) || hosts.length !== 1 || hosts[0] !== "127.0.0.1") fail("summary hosts");

process.stdout.write("accepted\n");
