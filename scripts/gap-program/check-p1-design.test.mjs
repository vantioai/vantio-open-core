import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { checkDesign } from "./check-p1-design.mjs";

const REPO = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");

test("the phase-1 packet passes the claim fence", () => {
  const evidence = checkDesign(REPO);
  assert.deepEqual(evidence.errors, []);
  assert.equal(evidence.ok, true);
  assert.equal(evidence.feature_code, false);
  assert.equal(evidence.product_otlp_export_authorized, false);
  assert.equal(evidence.files.length, 9);
});

test("a price in a track file fails the fence", () => {
  const dir = mkdtempSync(path.join(tmpdir(), "gap-p1-"));
  try {
    const source = path.join(REPO, "docs", "gap-program");
    mkdirSync(path.join(dir, "docs", "gap-program"), { recursive: true });
    for (const name of [
      "T6-identity-interop.md",
      "T7-credential-keep-out.md",
      "T8-ocsf-otlp-siem.md",
      "T9-owasp-agentic-matrix.md",
      "T10-live-human-approval.md",
      "T11-coding-agent-supply-chain.md",
      "T12-policy-preview.md",
      "T13-fedramp-fips-gap.md",
      "T14-eu-ai-act-evidence-outline.md",
    ]) {
      writeFileSync(path.join(dir, "docs", "gap-program", name), readFileSync(path.join(source, name)));
    }
    const t6 = path.join(dir, "docs", "gap-program", "T6-identity-interop.md");
    writeFileSync(t6, `${readFileSync(t6, "utf8")}\nPrice leak $499\n`);
    const evidence = checkDesign(dir);
    assert.equal(evidence.ok, false);
    assert.ok(evidence.errors.some((line) => line.includes("forbidden")));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
