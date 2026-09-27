import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  assemblePeCustomerBundle,
  checkRelease,
  countPatterns,
  denialHits,
  diffHitLists,
  npmPackPaths,
  parseLlmsPaths,
  pythonCandidatePaths,
  readmeBoundaryProblems,
  removedExportViolations,
  roadmapViolations,
} from "./docs-release-lib.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "../..");

const CHECK_IDS = [
  "manifest-schema",
  "package-version-matches-metadata",
  "readme-matches-product-boundary",
  "public-exports-documented",
  "removed-exports-not-current",
  "examples-execute",
  "env-vars-documented",
  "status-tokens-documented",
  "supported-paths-match-catalogs",
  "known-limitations-exist",
  "changelog-entry-exists",
  "ai-guide-version-matches",
  "llms-txt-canonical-only",
  "llms-full-regenerable",
  "public-artifacts-exclude-pe-customer-docs",
  "public-packages-exclude-internal-docs",
  "private-packages-stay-private",
  "pe-customer-bundle-includes-matching-manual",
  "stale-product-names-rejected",
  "roadmap-features-not-current",
  "legacy-stale-name-inventory-frozen",
];

test("repository documentation release checks pass", () => {
  const result = checkRelease(ROOT);
  assert.deepEqual(result.checks.map((check) => check.id), CHECK_IDS);
  assert.equal(result.ok, true, JSON.stringify(result.failures, null, 2));
});

test("readme boundary rejects a missing phrase and a stale name", () => {
  const boundary = {
    required_phrases: ["Vantio Optics"],
    forbidden_phrases: ["Sight Loop"],
  };
  assert.equal(readmeBoundaryProblems("Vantio Optics is current.", boundary), "");
  assert.match(readmeBoundaryProblems("hello", boundary), /missing required phrase/);
  assert.match(readmeBoundaryProblems("Vantio Optics Sight Loop", boundary), /forbidden phrase/);
});

test("removed exports may appear only under a historical heading", () => {
  const removed = ["VantioSession"];
  const pattern = "removed|breaking|migrate|old \\(v2";
  const current = "# API\n\nUse VantioSession.\n";
  const historical = "# API\n\n## Breaking change\n\nVantioSession is removed.\n";
  assert.deepEqual(removedExportViolations(current, removed, pattern), ["VantioSession"]);
  assert.deepEqual(removedExportViolations(historical, removed, pattern), []);
});

test("llms.txt parser keeps only canonical path lines", () => {
  const text = "# title\n\nREADME.md\n\n# note\ndocs/sight-loop.md\n";
  assert.deepEqual(parseLlmsPaths(text), ["README.md", "docs/sight-loop.md"]);
});

test("roadmap features fail unless the line is an explicit absence", () => {
  const features = [
    { id: "ui", forbidden: "vantio ui" },
    { id: "otlp", forbidden: "OTLP exporter", allowed_line: "no OTLP exporter" },
  ];
  assert.deepEqual(roadmapViolations("There is no OTLP exporter.\n", features), []);
  assert.equal(roadmapViolations("Run vantio ui locally.\n", features).length, 1);
});

test("stale-name counter finds retired wording", () => {
  const patterns = [{ id: "sight-loop-words", regex: "Sight Loop" }];
  assert.equal(countPatterns("Sight Loop and Sight Loop", patterns), 2);
  assert.equal(countPatterns("current optics", patterns), 0);
});

test("legacy inventory diff reports a new file", () => {
  const diff = diffHitLists([{ path: "docs/new.md", count: 1 }], []);
  assert.deepEqual(diff.unexpected, ["docs/new.md"]);
});

test("PE customer bundle requires a matching private manual and stays non-public", () => {
  const manual = "manual_version: 0.0.0-test\n";
  const ok = assemblePeCustomerBundle({ version: "0.0.0-test", manualText: manual });
  assert.equal(ok.ok, true);
  assert.equal(ok.bundle.public_distribution, false);
  assert.ok(ok.bundle.members.some((member) => member.role === "private-manual"));
  const mismatch = assemblePeCustomerBundle({ version: "9.9.9", manualText: manual });
  assert.equal(mismatch.ok, false);
  const missing = assemblePeCustomerBundle({ version: "0.0.0-test", manualText: "no header" });
  assert.equal(missing.ok, false);
});

test("public npm pack excludes a customer manual fixture", () => {
  const dir = mkdtempSync(join(tmpdir(), "vantio-docs-pack-"));
  try {
    writeFileSync(join(dir, "package.json"), JSON.stringify({
      name: "governance-fixture",
      version: "0.0.0",
      files: ["CUSTOMER-MANUAL.md", "README.md"],
    }));
    writeFileSync(join(dir, "README.md"), "# fixture\n");
    writeFileSync(join(dir, "CUSTOMER-MANUAL.md"), "manual_version: 0.0.0-test\n");
    const paths = npmPackPaths(dir);
    const hits = denialHits(paths, ["CUSTOMER-MANUAL", "PRIVATE-MANUAL", "docs/internal/"]);
    assert.ok(hits.some((hit) => hit.includes("CUSTOMER-MANUAL")));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("python package candidates exclude internal and customer docs", () => {
  const dir = mkdtempSync(join(tmpdir(), "vantio-docs-py-"));
  try {
    mkdirSync(join(dir, "vantio"), { recursive: true });
    mkdirSync(join(dir, "docs/internal"), { recursive: true });
    writeFileSync(join(dir, "pyproject.toml"), "[tool.hatch.build.targets.wheel]\npackages = [\"vantio\"]\n");
    writeFileSync(join(dir, "vantio/__init__.py"), "");
    writeFileSync(join(dir, "docs/internal/secret.md"), "internal\n");
    writeFileSync(join(dir, "vantio/PRIVATE-MANUAL.md"), "manual_version: 0.0.0-test\n");
    const candidates = pythonCandidatePaths(dir);
    assert.deepEqual(candidates.packages, ["vantio"]);
    const hits = denialHits([...candidates.wheel, ...candidates.sdist], [
      "docs/internal/",
      "PRIVATE-MANUAL",
      "CUSTOMER-MANUAL",
    ]);
    assert.ok(hits.some((hit) => hit.includes("docs/internal/")));
    assert.ok(hits.some((hit) => hit.includes("PRIVATE-MANUAL")));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
