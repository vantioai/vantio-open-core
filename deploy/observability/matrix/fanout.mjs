import { rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  cell,
  deliverRows,
  docker,
  leakHits,
  makeExporter,
  pushPrivacyAndForged,
  readText,
  sleep,
  traceId,
  trio,
  waitForPort,
  writeResult,
} from "./lib.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const hecFile = "/tmp/vantio-matrix/hec.jsonl";
const ddFile = "/tmp/vantio-matrix/datadog.jsonl";
rmSync(hecFile, { force: true });
rmSync(ddFile, { force: true });
writeFileSync(hecFile, "");
writeFileSync(ddFile, "");

docker(["compose", "-f", path.join(root, "fanout/compose.yaml"), "up", "-d", "--force-recreate"], { inherit: true });
if (!(await waitForPort(4328))) {
  console.error(docker(["logs", "--tail", "40", "fanout-fanout-1"]));
  process.exit(1);
}
await sleep(1000);

function judge(name, blob, tag, extra) {
  const trace = traceId(tag);
  const hits = leakHits(blob);
  const stored = blob.includes("1.0.0") && blob.includes(trace);
  const forgedAbsent = !blob.includes("FORGED-WORKLOAD-9f3a");
  return {
    destination: name,
    label: "protocol-verified, not product-verified",
    bind: "attestObservation+token",
    rows: {
      1: cell(stored ? "PASS" : "FAIL", stored ? `schema and trace ${trace}` : "missing schema or trace"),
      2: cell(stored && blob.includes("phantom.decision") && blob.includes("enterprise.evidence") ? "PASS" : "FAIL", "three kinds"),
      3: cell(stored && blob.includes("BLOCK") && blob.includes("sha256:abababababababababababababababababababababababababababababababab") ? "PASS" : "FAIL", "BLOCK and digest"),
      4: cell(stored && hits.length === 0 ? "PASS" : (stored ? "FAIL" : "GAP"), hits.join(",") || "no canary"),
      10: cell(stored && forgedAbsent && extra.forged.reason === "UNATTESTED" && extra.unbound.reason === "UNATTESTED" ? "PASS" : "GAP", `forged ${extra.forged.reason}`),
    },
    hits,
    bytes: blob.length,
  };
}

const exporter = makeExporter({ endpoint: "http://127.0.0.1:4328", protocol: "otlp-http-json", compression: "gzip" });
const hecMain = await deliverRows(exporter, trio("splunk-hec"));
const hecExtra = await pushPrivacyAndForged(exporter, "splunk-hec");
const ddMain = await deliverRows(exporter, trio("datadog-mock"));
const ddExtra = await pushPrivacyAndForged(exporter, "datadog-mock");
exporter.stop();
await sleep(2000);
const hec = judge("splunk-hec-mock", readText(hecFile), "splunk-hec", hecExtra);
hec.health = hecMain.status;
const dd = judge("datadog-mock", readText(ddFile), "datadog-mock", ddExtra);
dd.health = ddMain.status;
writeResult("/tmp/vantio-matrix", "splunk-hec", hec);
writeResult("/tmp/vantio-matrix", "datadog-mock", dd);
console.log("HEC", JSON.stringify(hec.rows), hec.health);
console.log("DD", JSON.stringify(dd.rows), dd.health);
