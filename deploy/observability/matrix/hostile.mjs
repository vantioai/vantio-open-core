import http from "node:http";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { docker, event, makeExporter, send, sleep, waitForPort } from "./lib.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function listen(port, handler) {
  return new Promise((resolve) => {
    const server = http.createServer(handler);
    server.listen(port, "0.0.0.0", () => resolve(server));
  });
}

function compose(file, args) {
  docker(["compose", "-p", "hostile", "-f", file, ...args], { timeout: 180000 });
}

const slow = await listen(18081, (req, res) => {
  req.resume();
  setTimeout(() => {
    res.writeHead(200);
    res.end("late");
  }, 5000);
});
const fail = await listen(18082, (req, res) => {
  req.resume();
  res.writeHead(500);
  res.end("no");
});

async function probe(name, endpoint, protocol = "otlp-http-json") {
  const exporter = makeExporter({
    endpoint,
    protocol,
    timeoutMs: 80,
    maxDelayMs: 60000,
    maxQueue: 4,
    maxBatch: 10,
  });
  const started = process.hrtime.bigint();
  const offered = send(exporter, event(`${name}-hostile`));
  const offerMs = Number(process.hrtime.bigint() - started) / 1e6;
  await exporter.flush();
  const status = exporter.status();
  exporter.stop();
  return {
    name,
    offer_accepted: offered.accepted === true,
    offer_ms: Number(offerMs.toFixed(3)),
    health: status.health,
    sent: status.sent,
    queued: status.queued,
    last_error: status.lastError,
  };
}

const rows = [];
compose(path.join(root, "collector/compose-hostile.yaml"), ["up", "-d", "--force-recreate"]);
await waitForPort(4718, "127.0.0.1", 80);
await sleep(1500);
rows.push(await probe("collector-slow", "http://127.0.0.1:4718"));
let collectorLog = "";
try {
  collectorLog = docker(["logs", "hostile-collector-1"]);
} catch {
  collectorLog = "";
}

compose(path.join(root, "collector/compose-hostile.yaml"), ["down"]);
const failCompose = path.join(root, "collector/compose-hostile.yaml");
docker([
  "run", "-d", "--name", "vantio-collector-fail",
  "--add-host", "host.docker.internal:host-gateway",
  "-p", "4718:4318",
  "-v", `${path.join(root, "collector/config-fail.yaml")}:/etc/otel/config.yaml:ro`,
  "otel/opentelemetry-collector-contrib:0.136.0@sha256:45392d534c1edcc809c2d112394029246bc679d2ae5ea7081414a1fc74f2c621",
  "--config=/etc/otel/config.yaml",
]);
await waitForPort(4718, "127.0.0.1", 80);
await sleep(1500);
rows.push(await probe("collector-500", "http://127.0.0.1:4718"));
let failLog = "";
try {
  failLog = docker(["logs", "vantio-collector-fail"]);
} catch {
  failLog = "";
}
docker(["rm", "-f", "vantio-collector-fail"]);

const reset = net.createServer((socket) => socket.destroy());
await new Promise((resolve) => reset.listen(18083, "127.0.0.1", resolve));
rows.push(await probe("tcp-reset", "http://127.0.0.1:18083"));

const garbage = await listen(18084, (req, res) => {
  req.resume();
  res.writeHead(200, { "content-type": "text/html" });
  res.end("<html>not otlp</html>");
});
rows.push(await probe("html-body", "http://127.0.0.1:18084"));

const hookSlow = await listen(18085, (req, res) => {
  req.resume();
  setTimeout(() => {
    res.writeHead(500);
    res.end("hook");
  }, 5000);
});
const hookExporter = makeExporter({
  endpoint: "http://127.0.0.1:18084",
  protocol: "otlp-http-json",
  webhook: "http://127.0.0.1:18085/hook",
  timeoutMs: 80,
  maxDelayMs: 60000,
  maxQueue: 4,
});
const hookStart = process.hrtime.bigint();
const hookOffered = send(hookExporter, event("webhook-slow"));
const hookOfferMs = Number(process.hrtime.bigint() - hookStart) / 1e6;
await hookExporter.flush();
rows.push({
  name: "webhook-slow-500",
  offer_accepted: hookOffered.accepted === true,
  offer_ms: Number(hookOfferMs.toFixed(3)),
  health: hookExporter.status().health,
  sent: hookExporter.status().sent,
  queued: hookExporter.status().queued,
  last_error: hookExporter.status().lastError,
});
hookExporter.stop();

const summary = {
  rows,
  collector_log_has_error: /error/i.test(collectorLog),
  fail_log_tail: failLog.split("\n").slice(-8),
};
console.log(JSON.stringify(summary, null, 2));
slow.close();
fail.close();
reset.close();
garbage.close();
hookSlow.close();
try {
  compose(failCompose, ["down"]);
} catch {
  /* already down */
}
