#!/usr/bin/env node
"use strict";

const path = require("node:path");
const { proposePolicy, runSession, uninstallSession, verifyExport } = require("../src/index.cjs");

function arg(name) {
  const index = process.argv.indexOf(name);
  if (index === -1) return null;
  return process.argv[index + 1] || null;
}

function fail(error) {
  const code = error && error.code ? error.code : "ERROR";
  process.stderr.write(`${code}\n`);
  process.exit(1);
}

const command = process.argv[2];
const repoRoot = arg("--repo") || path.join(__dirname, "..", "..", "..");

if (command === "run") {
  try {
    const result = runSession({
      repoRoot,
      forceOffline: process.argv.includes("--offline"),
      injectUnlabeled: process.argv.includes("--inject-unlabeled"),
      traceId: arg("--trace-id") || undefined,
      startedAt: arg("--started-at") || undefined,
      sessionRoot: arg("--session-root") || undefined,
      operatorHome: arg("--operator-home") || undefined,
    });
    process.stdout.write(result.report);
    process.stdout.write(`export=${result.exportPath}\n`);
    process.stdout.write(`sentinel=${result.sentinelPath}\n`);
    process.stdout.write(`producer_classification=${result.producer_classification}\n`);
  } catch (error) {
    fail(error);
  }
} else if (command === "verify") {
  const target = process.argv[3];
  if (!target) fail(new Error("MISSING_EXPORT"));
  const result = verifyExport(target);
  process.stdout.write(`${JSON.stringify({ ok: result.ok, producer_classification: result.producer_classification, external_proof: result.external_proof, problems: result.problems })}\n`);
  if (!result.ok) process.exit(1);
} else if (command === "uninstall") {
  try {
    const result = uninstallSession(process.argv[3]);
    process.stdout.write(`producer_classification=${result.producer_classification}\n`);
  } catch (error) {
    fail(error);
  }
} else if (command === "propose") {
  try {
    const proposal = proposePolicy(process.argv[3]);
    process.stdout.write(`${JSON.stringify(proposal)}\n`);
  } catch (error) {
    fail(error);
  }
} else {
  process.stderr.write("usage: investor-demo.cjs run|verify|uninstall|propose\n");
  process.exit(1);
}
