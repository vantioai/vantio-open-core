"use strict";

const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const {
  ALLOWED,
  BASE,
  ENTRY,
  POINTER,
  REGISTERS,
  assess,
  withoutAuthority,
} = require("./assess.cjs");

const ROOT = path.resolve(__dirname, "../..");
const TIP = "47b29adaba8015efdf8321a03c689c5c9dcdc382";

function readText(rel) {
  return fs.readFileSync(path.join(ROOT, rel), "utf8");
}

function readJson(rel) {
  return JSON.parse(readText(rel));
}

function git(args) {
  return execFileSync("git", args, {
    cwd: ROOT,
    encoding: "utf8",
  }).trim();
}

function gitShow(rel) {
  return execFileSync("git", ["show", `${BASE}:${rel}`], {
    cwd: ROOT,
    encoding: "utf8",
  });
}

function gitShowAt(sha, rel) {
  return execFileSync("git", ["show", `${sha}:${rel}`], {
    cwd: ROOT,
    encoding: "utf8",
  });
}

function parentsOf(sha) {
  const listed = git(["rev-parse", `${sha}^@`]);
  return listed ? listed.split(/\s+/) : [];
}

function mergeHead() {
  const rel = git(["rev-parse", "--git-path", "MERGE_HEAD"]);
  const abs = path.isAbsolute(rel) ? rel : path.join(ROOT, rel);
  if (!fs.existsSync(abs)) return null;
  return fs.readFileSync(abs, "utf8").trim();
}

function integrationParent() {
  const merging = mergeHead();
  if (merging === TIP) return git(["rev-parse", "HEAD"]);
  const head = git(["rev-parse", "HEAD"]);
  if (head === TIP) return BASE;
  const parents = parentsOf(head);
  if (parents.includes(TIP)) return parents[0];
  const merges = git(["rev-list", "--merges", `${TIP}..${head}`]);
  for (const sha of merges.split("\n").filter(Boolean)) {
    const mergeParents = parentsOf(sha);
    if (mergeParents.includes(TIP)) return mergeParents[0];
  }
  return BASE;
}

function pathLimitApplies() {
  if (mergeHead() === TIP) return true;
  const head = git(["rev-parse", "HEAD"]);
  if (head === TIP) return true;
  return parentsOf(head).includes(TIP);
}

const authority = readJson(ENTRY);
const inventory = readText("docs/programs/production-readiness/authority/00-INVENTORY.md");
const boundary = readText("docs/programs/production-readiness/authority/01-BOUNDARY.md");
const notes = readText("docs/programs/production-readiness/authority/02-ARCHITECTURE-COUNCIL-NOTES.md");

test("the superseding entry matches the founder authority contract", () => {
  assert.deepEqual(assess(authority), []);
});

test("the current authority file matches the council tip", () => {
  assert.equal(readText(ENTRY), gitShowAt(TIP, ENTRY));
});

test("each register carries the same pointer and keeps the sealed main body", () => {
  const parent = integrationParent();
  for (const rel of REGISTERS) {
    const current = readJson(rel);
    const sealed = JSON.parse(gitShowAt(parent, rel));
    assert.deepEqual(current.superseding_authority, POINTER);
    assert.deepEqual(withoutAuthority(current), sealed);
    assert.equal(current.refresh.classification, "MASTER_CONTROL_PLANE_REFRESH_READY_FOR_COUNCIL");
    assert.equal(current.refresh.recorded_main_sha, "601342f08a59798ce207840cfb75293c3c22f45c");
  }
});

test("historical sentences named by the entry are still in the registers", () => {
  for (const reading of authority.historical_readings) {
    assert.equal(readText(reading.register).includes(reading.sentence), true, reading.sentence);
  }
});

test("adjacent historical packets stay byte-identical to the accepted main", () => {
  for (const packet of authority.out_of_scope_historical_packets) {
    assert.equal(readText(packet.path), gitShow(packet.path));
    assert.equal(readText(packet.path).includes(packet.sentence), true, packet.path);
  }
});

test("the diff is limited to the authority reconciliation paths", (t) => {
  if (!pathLimitApplies()) {
    t.skip("later main commits are outside this force");
    return;
  }
  const against = integrationParent();
  const tracked = execFileSync("git", ["diff", "--name-only", against], {
    cwd: ROOT,
    encoding: "utf8",
  }).split("\n").filter(Boolean);
  const untracked = execFileSync("git", ["ls-files", "--others", "--exclude-standard"], {
    cwd: ROOT,
    encoding: "utf8",
  }).split("\n").filter(Boolean);
  const changed = [...tracked, ...untracked].sort();
  assert.deepEqual(changed, [...ALLOWED].sort());
});

test("prose records the same classification, base, and reading rule", () => {
  for (const text of [inventory, boundary, notes]) {
    assert.equal(text.includes("WAVE2_AUTHORITY_RECONCILED_READY_FOR_COUNCIL"), true);
    assert.equal(text.includes(BASE), true);
  }
  assert.equal(notes.includes(POINTER.reading_rule), true);
  for (const item of authority.truths) {
    assert.equal(inventory.includes(item.id), true, item.id);
  }
  assert.equal(authority.truths[6].status, "DEFINED");
  const ws11 = authority.truths.find((item) => item.id === "ws11");
  assert.equal(inventory.includes(ws11.status), true);
});
