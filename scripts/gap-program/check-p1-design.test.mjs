import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
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

function copyPacket(dir) {
  const source = path.join(REPO, "docs", "gap-program");
  const dest = path.join(dir, "docs", "gap-program");
  mkdirSync(dest, { recursive: true });
  for (const name of readdirSync(source)) {
    if (!name.endsWith(".md")) continue;
    writeFileSync(path.join(dest, name), readFileSync(path.join(source, name)));
  }
  return dest;
}

test("a price in a track file fails the fence", () => {
  const dir = mkdtempSync(path.join(tmpdir(), "gap-p1-"));
  try {
    const dest = copyPacket(dir);
    const t6 = path.join(dest, "T6-identity-interop.md");
    writeFileSync(t6, `${readFileSync(t6, "utf8")}\nPrice leak $499 and 1200 USD\n`);
    const evidence = checkDesign(dir);
    assert.equal(evidence.ok, false);
    assert.ok(evidence.errors.some((line) => line.includes("dollar-amount")));
    assert.ok(evidence.errors.some((line) => line.includes("usd")));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("a GAP word later in the row does not satisfy the status column", () => {
  const dir = mkdtempSync(path.join(tmpdir(), "gap-p1-"));
  try {
    const dest = copyPacket(dir);
    const t13 = path.join(dest, "T13-fedramp-fips-gap.md");
    const text = readFileSync(t13, "utf8").replace(
      "| Assessment and authorization | GAP |",
      "| Assessment and authorization | PASS |",
    );
    writeFileSync(t13, text);
    const evidence = checkDesign(dir);
    assert.equal(evidence.ok, false);
    assert.ok(evidence.errors.some((line) => line.includes("Assessment and authorization")));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("a FedRAMP authorized sentence fails the fence", () => {
  const dir = mkdtempSync(path.join(tmpdir(), "gap-p1-"));
  try {
    const dest = copyPacket(dir);
    const t13 = path.join(dest, "T13-fedramp-fips-gap.md");
    writeFileSync(t13, `${readFileSync(t13, "utf8")}\nVantio is FedRAMP authorized.\n`);
    const evidence = checkDesign(dir);
    assert.equal(evidence.ok, false);
    assert.ok(evidence.errors.some((line) => line.includes("fedramp-authorized")));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
