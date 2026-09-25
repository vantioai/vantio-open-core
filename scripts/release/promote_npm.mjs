#!/usr/bin/env node
// Promote one sealed npm tarball. This script never packs or rebuilds.
//
// Exit 0 — gate checks passed, or the sealed file was published and the
//          registry download matched it byte for byte.
// Exit 2 — VERSION_ALREADY_EXISTS. This is not a successful publication.
// Exit 1 — any other rejection.

import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, basename } from "node:path";

function scratchDir(prefix) {
  const preferred = tmpdir();
  const base = existsSync(preferred) ? preferred : "/tmp";
  return mkdtempSync(join(base, prefix));
}

const ALLOWLIST = new Map([
  ["@vantio/cli", "packages/vantio-cli"],
  ["@vantio/agent-sdk", "packages/vantio-agent-sdk"],
  ["@vantio/optics-mcp", "packages/vantio-optics-mcp"],
  ["@vantio/gate-mcp", "packages/vantio-gate-mcp"],
]);

const VERSION_RE = /^[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9.-]+)?$/;
const SHA_RE = /^[a-f0-9]{40}$/;
const HEX64_RE = /^[a-f0-9]{64}$/;
const SECRET_KEYS = ["NODE_AUTH_TOKEN", "NPM_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"];

function redact(value) {
  let out = String(value ?? "");
  for (const key of SECRET_KEYS) {
    const secret = process.env[key];
    if (secret && secret.length >= 6) out = out.split(secret).join("[REDACTED]");
  }
  return out;
}

function emit(status, extra = {}) {
  const line = JSON.stringify({ status, ...extra });
  process.stdout.write(`RELEASE_RESULT ${redact(line)}\n`);
}

function fail(status, message, code = 1, extra = {}) {
  process.stderr.write(`vantio-release: ${redact(message)}\n`);
  emit(status, extra);
  process.exit(code);
}

function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith("--")) {
      out._.push(token);
      continue;
    }
    const key = token.slice(2);
    const next = argv[i + 1];
    if (next === undefined || next.startsWith("--")) out[key] = true;
    else {
      out[key] = next;
      i += 1;
    }
  }
  return out;
}

function sha256(buf) {
  return createHash("sha256").update(buf).digest("hex");
}

function sha1(buf) {
  return createHash("sha1").update(buf).digest("hex");
}

function integrity(buf) {
  return `sha512-${createHash("sha512").update(buf).digest("base64")}`;
}

function run(bin, args, opts = {}) {
  const result = spawnSync(bin, args, {
    encoding: "utf8",
    env: process.env,
    cwd: opts.cwd,
    timeout: opts.timeout ?? 120000,
  });
  return {
    status: result.status === null ? 1 : result.status,
    stdout: result.stdout || "",
    stderr: result.stderr || "",
  };
}

function apiBase() {
  if (process.env.VANTIO_RELEASE_TEST === "1" && process.env.VANTIO_RELEASE_GITHUB_API) {
    return String(process.env.VANTIO_RELEASE_GITHUB_API).replace(/\/$/, "");
  }
  return "https://api.github.com";
}

function githubHeaders() {
  const token = process.env.GH_TOKEN || process.env.GITHUB_TOKEN;
  if (!token) fail("APPROVAL_UNAVAILABLE", "GitHub token is not available to confirm approval", 1);
  return {
    Accept: "application/vnd.github+json",
    Authorization: `Bearer ${token}`,
    "User-Agent": "vantio-release-promote",
    "X-GitHub-Api-Version": "2022-11-28",
  };
}

async function githubJson(pathname) {
  const response = await fetch(`${apiBase()}${pathname}`, { headers: githubHeaders() });
  const text = await response.text();
  if (!response.ok) {
    fail("APPROVAL_UNAVAILABLE", `GitHub approval lookup failed (${response.status})`, 1);
  }
  return JSON.parse(text);
}

function packageJsonFromTarball(tarBin, artifact) {
  const listed = run(tarBin, ["-tzf", artifact]);
  if (listed.status !== 0) fail("ARTIFACT_UNREADABLE", "sealed tarball cannot be listed", 1);
  const names = listed.stdout.split("\n").map((line) => line.trim()).filter(Boolean);
  for (const name of names) {
    if (name.startsWith("/") || name.split("/").includes("..")) {
      fail("UNSAFE_ARCHIVE_MEMBER", `unsafe archive member ${name}`, 1);
    }
  }
  const member = names.find((name) => name === "package/package.json");
  if (!member) fail("ARTIFACT_IDENTITY_MISMATCH", "sealed tarball has no package/package.json", 1);
  const extracted = run(tarBin, ["-xOzf", artifact, member]);
  if (extracted.status !== 0) fail("ARTIFACT_UNREADABLE", "could not read package.json from the sealed tarball", 1);
  try {
    return JSON.parse(extracted.stdout);
  } catch {
    fail("ARTIFACT_IDENTITY_MISMATCH", "sealed package.json is not JSON", 1);
  }
  return null;
}

function lookupRegistry(npmBin, spec) {
  const result = run(npmBin, ["view", spec, "version", "dist", "--json"]);
  const text = `${result.stdout}\n${result.stderr}`;
  if (result.status === 0 && result.stdout.trim()) {
    try {
      return { exists: true, body: JSON.parse(result.stdout) };
    } catch {
      fail("REGISTRY_LOOKUP_FAILED", "npm view returned unreadable JSON", 1);
    }
  }
  if (/E404|404 Not Found|not in this registry|No match found/i.test(text)) {
    return { exists: false, body: null };
  }
  fail("REGISTRY_LOOKUP_FAILED", "npm view failed for a reason other than version absence", 1);
  return { exists: false, body: null };
}

function classifyPublish(result) {
  const text = `${result.stdout}\n${result.stderr}`;
  if (result.status === 0) return { ok: true };
  if (/EPUBLISHCONFLICT|cannot publish over|You cannot publish over|previously published versions/i.test(text)) {
    return { ok: false, status: "VERSION_ALREADY_EXISTS", code: 2 };
  }
  return { ok: false, status: "PUBLISH_FAILED", code: 1 };
}

async function loadGithubApproval(runId, expected) {
  const workflowRun = await githubJson(`/repos/vantioai/vantio-open-core/actions/runs/${runId}`);
  if (workflowRun.event !== "workflow_dispatch") {
    fail("APPROVAL_MISMATCH", "approval run was not a manual dispatch", 1);
  }
  if (workflowRun.conclusion !== "success") {
    fail("APPROVAL_MISSING", "release gate run has not succeeded", 1);
  }
  if (workflowRun.head_sha !== expected.source_commit) {
    fail("APPROVAL_MISMATCH", "approval run commit does not match the sealed source", 1);
  }
  const path = String(workflowRun.path || "");
  if (!path.endsWith("npm-publish.yml") && !path.endsWith("pypi-publish.yml")) {
    fail("APPROVAL_MISMATCH", "approval run is not a package release gate", 1);
  }
  const artifacts = await githubJson(`/repos/vantioai/vantio-open-core/actions/runs/${runId}/artifacts`);
  const match = (artifacts.artifacts || []).find((item) => item.name === "release-approval" && !item.expired);
  if (!match) fail("APPROVAL_MISSING", "approved run has no release-approval artifact", 1);
  const zipResponse = await fetch(match.archive_download_url, { headers: githubHeaders() });
  if (!zipResponse.ok) fail("APPROVAL_UNAVAILABLE", "could not download the approval artifact", 1);
  const bytes = Buffer.from(await zipResponse.arrayBuffer());
  const dir = scratchDir("vantio-approval-");
  const zipPath = join(dir, "approval.zip");
  writeFileSync(zipPath, bytes);
  const unpacked = run("python3", ["-c", "import sys, zipfile\nfrom pathlib import Path\nz=zipfile.ZipFile(sys.argv[1])\nfor info in z.infolist():\n    name=info.filename\n    if name.startswith('/') or '..' in name.split('/'):\n        raise SystemExit(2)\n    if Path(name).name != 'release-approval.json':\n        continue\n    Path(sys.argv[2], 'release-approval.json').write_bytes(z.read(info))\n", zipPath, dir]);
  if (unpacked.status !== 0) {
    rmSync(dir, { recursive: true, force: true });
    fail("APPROVAL_UNAVAILABLE", "approval artifact could not be unpacked", 1);
  }
  let parsed;
  try {
    parsed = JSON.parse(readFileSync(join(dir, "release-approval.json"), "utf8"));
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
  const fields = ["package", "version", "source_commit", "artifact_sha256"];
  for (const field of fields) {
    if (parsed[field] !== expected[field]) {
      fail("APPROVAL_MISMATCH", `approval ${field} does not match the sealed artifact`, 1);
    }
  }
  if (parsed.approved !== true) fail("APPROVAL_MISSING", "approval record is not approved", 1);
  return parsed;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const mode = args.publish ? "publish" : "gate";
  const packageName = String(args.package || "");
  const version = String(args.version || "");
  const sourceCommit = String(args["source-commit"] || "");
  const checkoutSha = String(args["checkout-sha"] || "");
  const repoRoot = String(args["repo-root"] || process.cwd());
  const npmBin = String(args["npm-bin"] || "npm");
  const tarBin = String(args["tar-bin"] || "tar");
  const curlBin = String(args["curl-bin"] || "curl");

  if (!ALLOWLIST.has(packageName)) {
    fail("PACKAGE_NOT_ALLOWED", `package is not on the release allowlist: ${packageName}`, 1);
  }
  if (!VERSION_RE.test(version)) fail("VERSION_REJECTED", "version is empty or not semver-safe", 1);
  if (!SHA_RE.test(sourceCommit) || sourceCommit !== checkoutSha) {
    fail("SOURCE_COMMIT_MISMATCH", "source commit must be the full checkout SHA", 1);
  }

  const manifestPath = join(repoRoot, ALLOWLIST.get(packageName), "package.json");
  if (!existsSync(manifestPath)) fail("SOURCE_PACKAGE_MISSING", "checkout is missing the package manifest", 1);
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  if (manifest.name !== packageName || manifest.version !== version) {
    fail("VERSION_MISMATCH", "checkout package.json name or version does not match the request", 1);
  }

  if (mode === "gate") {
    if (args["expected-sha256"] !== undefined && !HEX64_RE.test(String(args["expected-sha256"]))) {
      fail("HASH_REJECTED", "expected SHA-256 is missing or malformed", 1);
    }
    const lookup = lookupRegistry(npmBin, `${packageName}@${version}`);
    if (lookup.exists) {
      fail("VERSION_ALREADY_EXISTS", `${packageName}@${version} is already on the registry`, 2, {
        package: packageName,
        version,
        source_commit: sourceCommit,
      });
    }
    emit("GATE_OK", {
      package: packageName,
      version,
      source_commit: sourceCommit,
      publish: false,
    });
    return;
  }

  const artifact = String(args.artifact || "");
  const expectedSha = String(args["expected-sha256"] || "");
  if (!existsSync(artifact)) fail("ARTIFACT_MISSING", "sealed artifact file is missing", 1);
  if (!HEX64_RE.test(expectedSha)) fail("HASH_REJECTED", "expected SHA-256 is missing or malformed", 1);
  const bytes = readFileSync(artifact);
  const actualSha = sha256(bytes);
  if (actualSha !== expectedSha) {
    fail("ARTIFACT_HASH_MISMATCH", "sealed artifact SHA-256 does not match the approved hash", 1, {
      package: packageName,
      version,
    });
  }
  const packed = packageJsonFromTarball(tarBin, artifact);
  if (!packed || packed.name !== packageName || packed.version !== version) {
    fail("ARTIFACT_IDENTITY_MISMATCH", "sealed tarball package identity does not match the request", 1);
  }

  const expected = {
    package: packageName,
    version,
    source_commit: sourceCommit,
    artifact_sha256: expectedSha,
  };
  if (args["github-run-id"]) {
    await loadGithubApproval(String(args["github-run-id"]), expected);
  } else if (args["allow-local-approval"] === true && args["approval-file"]) {
    const local = JSON.parse(readFileSync(String(args["approval-file"]), "utf8"));
    if (local.approved !== true) fail("APPROVAL_MISSING", "local approval is not approved", 1);
    for (const [field, value] of Object.entries(expected)) {
      const key = field === "source_commit" ? "source_commit" : field === "artifact_sha256" ? "artifact_sha256" : field;
      if (local[key] !== value) fail("APPROVAL_MISMATCH", `local approval ${key} does not match`, 1);
    }
  } else {
    fail("APPROVAL_MISSING", "publication requires a succeeded release-gate run", 1);
  }

  const lookup = lookupRegistry(npmBin, `${packageName}@${version}`);
  if (lookup.exists) {
    fail("VERSION_ALREADY_EXISTS", `${packageName}@${version} is already on the registry`, 2, expected);
  }

  const publishCwd = scratchDir("vantio-npm-promote-");
  let published;
  try {
    published = run(npmBin, ["publish", artifact, "--access", "public", "--ignore-scripts"], { cwd: publishCwd });
  } finally {
    rmSync(publishCwd, { recursive: true, force: true });
  }
  const classified = classifyPublish(published);
  if (!classified.ok) {
    fail(classified.status, "npm publish did not accept the sealed tarball", classified.code, expected);
  }

  const after = lookupRegistry(npmBin, `${packageName}@${version}`);
  if (!after.exists) fail("REGISTRY_HASH_MISMATCH", "registry did not return the version after publish", 1, expected);
  const dist = after.body && after.body.dist ? after.body.dist : after.body;
  const tarballUrl = dist && (dist.tarball || dist["dist.tarball"]);
  if (!tarballUrl || !String(tarballUrl).startsWith("https://registry.npmjs.org/")) {
    fail("REGISTRY_HASH_MISMATCH", "registry tarball URL is missing or not the public npm registry", 1, expected);
  }
  const downloadDir = scratchDir("vantio-npm-verify-");
  const downloaded = join(downloadDir, basename(String(tarballUrl)));
  try {
    const curled = run(curlBin, ["-fsSL", String(tarballUrl), "-o", downloaded]);
    if (curled.status !== 0) fail("REGISTRY_HASH_MISMATCH", "registry tarball download failed", 1, expected);
    const remote = readFileSync(downloaded);
    const remoteSha = sha256(remote);
    if (remoteSha !== actualSha || remote.length !== bytes.length) {
      fail("REGISTRY_HASH_MISMATCH", "downloaded registry bytes do not match the sealed artifact", 1, {
        ...expected,
        sealed_sha256: actualSha,
        registry_sha256: remoteSha,
      });
    }
    const remoteSha1 = sha1(remote);
    const reportedSha1 = dist.shasum || dist["dist.shasum"];
    if (reportedSha1 && reportedSha1 !== remoteSha1) {
      fail("REGISTRY_HASH_MISMATCH", "registry shasum does not match the downloaded artifact", 1, expected);
    }
    emit("PUBLISHED", {
      ...expected,
      registry_sha256: remoteSha,
      dist_shasum: remoteSha1,
      integrity: integrity(remote),
      size: remote.length,
      tarball: String(tarballUrl),
    });
  } finally {
    rmSync(downloadDir, { recursive: true, force: true });
  }
}

main().catch((err) => {
  fail("PUBLISH_FAILED", err && err.message ? err.message : "promotion failed", 1);
});
