import { test } from "node:test";
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync, chmodSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "node:http";
const TEMP_ROOT = "/tmp/vantio-release-tests";
mkdirSync(TEMP_ROOT, { recursive: true });
function tempDir(prefix) {
  return mkdtempSync(join(TEMP_ROOT, prefix));
}

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "../..");
const PROMOTE = join(ROOT, "scripts/release/promote_npm.mjs");
const COMMIT = "d9b163361683a70c2560c0d164424d3875dcf4a5";
const CANARY = "super-secret-canary-token-xyz";

function sha256(buf) {
  return createHash("sha256").update(buf).digest("hex");
}

function sha1(buf) {
  return createHash("sha1").update(buf).digest("hex");
}

function integrity(buf) {
  return `sha512-${createHash("sha512").update(buf).digest("base64")}`;
}

function writeExecutable(path, body) {
  writeFileSync(path, body);
  chmodSync(path, 0o755);
}

function runNode(args, env = {}) {
  return new Promise((resolve) => {
    const child = spawn(process.execPath, [PROMOTE, ...args], {
      env: { ...process.env, NODE_AUTH_TOKEN: CANARY, NPM_TOKEN: CANARY, ...env },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => (stdout += chunk));
    child.stderr.on("data", (chunk) => (stderr += chunk));
    child.on("close", (code) => resolve({ code, stdout, stderr }));
  });
}

function fixtureRepo(version = "0.3.22") {
  const root = tempDir("vantio-release-repo-");
  const pkg = join(root, "packages/vantio-cli");
  mkdirSync(pkg, { recursive: true });
  writeFileSync(join(pkg, "package.json"), JSON.stringify({ name: "@vantio/cli", version }));
  return root;
}

function makeTarball(dir, version = "0.3.22", name = "@vantio/cli") {
  const pack = join(dir, "pack");
  mkdirSync(join(pack, "package"), { recursive: true });
  writeFileSync(join(pack, "package/package.json"), JSON.stringify({ name, version }));
  const artifact = join(dir, `cli-${version}.tgz`);
  const tar = spawnSyncTar(pack, artifact);
  if (tar !== 0) throw new Error("tar failed");
  return artifact;
}

function spawnSyncTar(cwd, artifact) {
  const { status } = spawnSync("tar", ["-czf", artifact, "package"], { cwd });
  return status;
}

function mockBins(dir, mode) {
  const log = join(dir, "npm.log");
  const published = join(dir, "published.txt");
  const count = join(dir, "count");
  writeFileSync(count, "0");
  const download = join(dir, "download-body.bin");
  writeExecutable(join(dir, "npm"), `#!/bin/sh
echo "$@" >> "${log}"
if [ "$1" = "view" ]; then
  n=$(cat "${count}")
  n=$((n+1))
  echo "$n" > "${count}"
  if [ "${mode}" = "exists" ]; then
    printf '%s\\n' '{"version":"0.3.22","dist":{"tarball":"https://registry.npmjs.org/@vantio/cli/-/cli-0.3.22.tgz","shasum":"abc","integrity":"sha512-abc"}}'
    exit 0
  fi
  if [ "${mode}" = "timeout" ]; then
    echo "npm error code E404" >&2
    exit 1
  fi
  if [ "${mode}" = "conflict" ] || [ "${mode}" = "publish" ] || [ "${mode}" = "mismatch" ] || [ "${mode}" = "delay" ] || [ "${mode}" = "http202" ]; then
    lag="\${VANTIO_MOCK_LAG:-0}"
    if [ "$n" = "1" ]; then
      echo "npm error code E404" >&2
      exit 1
    fi
    seen=$((n-1))
    if [ "$seen" -le "$lag" ]; then
      echo "npm error code E404" >&2
      exit 1
    fi
    printf '%s\\n' '{"version":"0.3.22","dist":{"tarball":"https://registry.npmjs.org/@vantio/cli/-/cli-0.3.22.tgz","shasum":"'"$MOCK_SHA1"'","integrity":"'"$MOCK_INTEGRITY"'"}}'
    exit 0
  fi
  echo "npm error code E404" >&2
  exit 1
fi
if [ "$1" = "publish" ]; then
  echo "$2" >> "${published}"
  if [ "${mode}" = "conflict" ]; then
    echo "EPUBLISHCONFLICT You cannot publish over the previously published versions" >&2
    echo "${CANARY}" >&2
    exit 1
  fi
  if [ "${mode}" = "http202" ]; then
    echo "npm notice Your package is being processed and may take a few minutes to become available."
    echo "http fetch PUT 202 https://registry.npmjs.org/@vantio%2fcli"
    exit 0
  fi
  echo "${CANARY}"
  exit 0
fi
echo "unexpected npm $1" >&2
exit 1
`);
  writeExecutable(join(dir, "curl"), `#!/bin/sh
out=""
url=""
while [ $# -gt 0 ]; do
  case "$1" in
    -o) out="$2"; shift 2 ;;
    -fsSL) shift ;;
    *) url="$1"; shift ;;
  esac
done
cp "${download}" "$out"
`);
  return { log, published, download };
}

function baseArgs(repo, artifact, digest) {
  return [
    "--package", "@vantio/cli",
    "--version", "0.3.22",
    "--source-commit", COMMIT,
    "--checkout-sha", COMMIT,
    "--repo-root", repo,
    "--artifact", artifact,
    "--expected-sha256", digest,
  ];
}

test("workflow files do not publish on an ordinary push", () => {
  const code = (text) => text.split("\n").filter((line) => !line.trim().startsWith("#")).join("\n");
  const npm = code(readFileSync(join(ROOT, ".github/workflows/npm-publish.yml"), "utf8"));
  const pypi = code(readFileSync(join(ROOT, ".github/workflows/pypi-publish.yml"), "utf8"));
  const mcp = code(readFileSync(join(ROOT, ".github/workflows/mcp-registry-publish.yml"), "utf8"));
  const ci = code(readFileSync(join(ROOT, ".github/workflows/ci.yml"), "utf8"));
  for (const text of [npm, pypi, mcp]) {
    assert.equal(text.includes("\n  push:"), false);
    assert.match(text, /workflow_dispatch:/);
  }
  assert.doesNotMatch(npm, /npm publish|pnpm publish|NPM_TOKEN|secrets\./);
  assert.match(npm, /environment: npm-publish/);
  assert.match(npm, /promote_npm\.mjs --gate/);
  assert.doesNotMatch(npm, /--publish/);
  assert.match(npm, /artifact_sha256/);
  assert.match(npm, /source_commit/);
  assert.doesNotMatch(pypi, /python -m build|skip-existing:\s*true/);
  assert.match(pypi, /skip-existing is false/);
  assert.match(pypi, /environment: pypi/);
  assert.match(pypi, /promote_pypi\.py --publish/);
  assert.match(pypi, /id-token: write/);
  assert.match(mcp, /VERSION_ALREADY_EXISTS/);
  assert.match(mcp, /environment: mcp-registry-publish/);
  assert.doesNotMatch(mcp, /expected on re-runs/);
  assert.match(ci, /pull_request:/);
  assert.match(ci, /governance\.test\.mjs/);
  assert.match(ci, /npm pack/);
  assert.match(ci, /python3 -m build/);
  assert.doesNotMatch(ci, /NPM_TOKEN|twine upload|pypa\/gh-action-pypi-publish|npm publish/);
});

test("ordinary gate rejects an unrelated package and a bad commit", async () => {
  const repo = fixtureRepo();
  try {
    const unrelated = await runNode([
      "--gate", "--package", "@vantio/not-a-package", "--version", "0.3.22",
      "--source-commit", COMMIT, "--checkout-sha", COMMIT, "--repo-root", repo,
    ]);
    assert.equal(unrelated.code, 1);
    assert.match(unrelated.stdout, /PACKAGE_NOT_ALLOWED/);
    assert.doesNotMatch(`${unrelated.stdout}\n${unrelated.stderr}`, new RegExp(CANARY));

    const bad = await runNode([
      "--gate", "--package", "@vantio/cli", "--version", "0.3.22",
      "--source-commit", "abc", "--checkout-sha", "abc", "--repo-root", repo,
    ]);
    assert.equal(bad.code, 1);
    assert.match(bad.stdout, /SOURCE_COMMIT_MISMATCH/);
  } finally {
    rmSync(repo, { recursive: true, force: true });
  }
});

test("existing version is VERSION_ALREADY_EXISTS and does not publish", async () => {
  const dir = tempDir("vantio-npm-mock-");
  const repo = fixtureRepo();
  const { log, published } = mockBins(dir, "exists");
  try {
    const result = await runNode([
      "--gate", "--package", "@vantio/cli", "--version", "0.3.22",
      "--source-commit", COMMIT, "--checkout-sha", COMMIT, "--repo-root", repo,
      "--npm-bin", join(dir, "npm"),
    ]);
    assert.equal(result.code, 2);
    assert.match(result.stdout, /VERSION_ALREADY_EXISTS/);
    assert.equal(readFileSync(log, "utf8").includes("publish"), false);
    assert.throws(() => readFileSync(published, "utf8"));
    assert.doesNotMatch(`${result.stdout}\n${result.stderr}`, new RegExp(CANARY));
  } finally {
    rmSync(dir, { recursive: true, force: true });
    rmSync(repo, { recursive: true, force: true });
  }
});

test("wrong artifact hash and missing approval cannot publish", async () => {
  const dir = tempDir("vantio-npm-mock-");
  const repo = fixtureRepo();
  const artifact = makeTarball(dir);
  const digest = sha256(readFileSync(artifact));
  const { published } = mockBins(dir, "publish");
  try {
    const wrong = await runNode([
      "--publish", ...baseArgs(repo, artifact, "a".repeat(64)),
      "--npm-bin", join(dir, "npm"),
      "--allow-local-approval",
      "--approval-file", join(dir, "missing.json"),
    ]);
    assert.equal(wrong.code, 1);
    assert.match(wrong.stdout, /ARTIFACT_HASH_MISMATCH/);

    const approval = {
      approved: true,
      package: "@vantio/cli",
      version: "0.3.22",
      source_commit: COMMIT,
      artifact_sha256: digest,
    };
    writeFileSync(join(dir, "approval.json"), JSON.stringify(approval));
    const unapproved = await runNode([
      "--publish", ...baseArgs(repo, artifact, digest),
      "--npm-bin", join(dir, "npm"),
      "--approval-file", join(dir, "approval.json"),
    ]);
    assert.equal(unapproved.code, 1);
    assert.match(unapproved.stdout, /APPROVAL_MISSING/);
    assert.throws(() => readFileSync(published, "utf8"));
  } finally {
    rmSync(dir, { recursive: true, force: true });
    rmSync(repo, { recursive: true, force: true });
  }
});

test("EPUBLISHCONFLICT is VERSION_ALREADY_EXISTS and not a green publish", async () => {
  const dir = tempDir("vantio-npm-mock-");
  const repo = fixtureRepo();
  const artifact = makeTarball(dir);
  const bytes = readFileSync(artifact);
  const digest = sha256(bytes);
  writeFileSync(join(dir, "download-body.bin"), bytes);
  const { published } = mockBins(dir, "conflict");
  const approval = join(dir, "approval.json");
  writeFileSync(approval, JSON.stringify({
    approved: true, package: "@vantio/cli", version: "0.3.22",
    source_commit: COMMIT, artifact_sha256: digest,
  }));
  try {
    const result = await runNode([
      "--publish", ...baseArgs(repo, artifact, digest),
      "--npm-bin", join(dir, "npm"),
      "--curl-bin", join(dir, "curl"),
      "--allow-local-approval",
      "--approval-file", approval,
    ], { MOCK_SHA1: sha1(bytes) });
    assert.equal(result.code, 2);
    assert.match(result.stdout, /VERSION_ALREADY_EXISTS/);
    assert.doesNotMatch(result.stdout, /PUBLISHED/);
    assert.equal(readFileSync(published, "utf8").trim(), artifact);
    assert.doesNotMatch(`${result.stdout}\n${result.stderr}`, new RegExp(CANARY));
  } finally {
    rmSync(dir, { recursive: true, force: true });
    rmSync(repo, { recursive: true, force: true });
  }
});

test("approved publish promotes only the sealed tarball and rejects a registry mismatch", async () => {
  const dir = tempDir("vantio-npm-mock-");
  const repo = fixtureRepo();
  const artifact = makeTarball(dir);
  const bytes = readFileSync(artifact);
  const digest = sha256(bytes);
  writeFileSync(join(dir, "download-body.bin"), Buffer.from("not-the-artifact"));
  const { published, log } = mockBins(dir, "mismatch");
  const approval = join(dir, "approval.json");
  writeFileSync(approval, JSON.stringify({
    approved: true, package: "@vantio/cli", version: "0.3.22",
    source_commit: COMMIT, artifact_sha256: digest,
  }));
  try {
    const mismatch = await runNode([
      "--publish", ...baseArgs(repo, artifact, digest),
      "--npm-bin", join(dir, "npm"),
      "--curl-bin", join(dir, "curl"),
      "--allow-local-approval",
      "--approval-file", approval,
    ], { MOCK_SHA1: sha1(bytes), MOCK_INTEGRITY: integrity(bytes) });
    assert.equal(mismatch.code, 1);
    assert.match(mismatch.stdout, /HASH_MISMATCH/);
    assert.equal(readFileSync(published, "utf8").trim(), artifact);
    const calls = readFileSync(log, "utf8");
    assert.equal(calls.split("\n").filter((line) => line.startsWith("publish ")).length, 1);
    assert.doesNotMatch(calls, /@vantio\/gate-mcp|@vantio\/optics-mcp|@vantio\/agent-sdk/);
    assert.doesNotMatch(`${mismatch.stdout}\n${mismatch.stderr}`, new RegExp(CANARY));
  } finally {
    rmSync(dir, { recursive: true, force: true });
    rmSync(repo, { recursive: true, force: true });
  }
});

test("approved publish records registry hash equality", async () => {
  const dir = tempDir("vantio-npm-mock-");
  const repo = fixtureRepo();
  const artifact = makeTarball(dir);
  const bytes = readFileSync(artifact);
  const digest = sha256(bytes);
  writeFileSync(join(dir, "download-body.bin"), bytes);
  mockBins(dir, "publish");
  const approval = join(dir, "approval.json");
  writeFileSync(approval, JSON.stringify({
    approved: true, package: "@vantio/cli", version: "0.3.22",
    source_commit: COMMIT, artifact_sha256: digest,
  }));
  try {
    const result = await runNode([
      "--publish", ...baseArgs(repo, artifact, digest),
      "--npm-bin", join(dir, "npm"),
      "--curl-bin", join(dir, "curl"),
      "--allow-local-approval",
      "--approval-file", approval,
    ], { MOCK_SHA1: sha1(bytes), MOCK_INTEGRITY: integrity(bytes) });
    assert.equal(result.code, 0, result.stderr + result.stdout);
    assert.match(result.stdout, /"status":"PUBLISHED_VERIFIED"/);
    assert.match(result.stdout, new RegExp(digest));
    assert.doesNotMatch(`${result.stdout}\n${result.stderr}`, new RegExp(CANARY));
  } finally {
    rmSync(dir, { recursive: true, force: true });
    rmSync(repo, { recursive: true, force: true });
  }
});

async function publishCase(mode, { lag = 0, attempts = 6, interval = 0, testSwitch = true } = {}) {
  const dir = tempDir("vantio-npm-poll-");
  const repo = fixtureRepo();
  const artifact = makeTarball(dir);
  const bytes = readFileSync(artifact);
  const digest = sha256(bytes);
  writeFileSync(join(dir, "download-body.bin"), bytes);
  const { published, log } = mockBins(dir, mode);
  const approval = join(dir, "approval.json");
  writeFileSync(approval, JSON.stringify({
    approved: true, package: "@vantio/cli", version: "0.3.22",
    source_commit: COMMIT, artifact_sha256: digest,
  }));
  const env = {
    MOCK_SHA1: sha1(bytes),
    MOCK_INTEGRITY: integrity(bytes),
    VANTIO_MOCK_LAG: String(lag),
  };
  if (testSwitch) {
    env.VANTIO_RELEASE_TEST = "1";
    env.VANTIO_REGISTRY_POLL_INTERVAL_MS = String(interval);
    env.VANTIO_REGISTRY_POLL_MAX_ATTEMPTS = String(attempts);
  }
  const result = await runNode([
    "--publish", ...baseArgs(repo, artifact, digest),
    "--npm-bin", join(dir, "npm"),
    "--curl-bin", join(dir, "curl"),
    "--allow-local-approval",
    "--approval-file", approval,
  ], env);
  return { dir, repo, result, published, log, bytes };
}

function publishCount(log) {
  return readFileSync(log, "utf8").split("\n").filter((line) => line.startsWith("publish ")).length;
}

test("delayed registry visibility resolves to the sealed hash without a second upload", async () => {
  const { dir, repo, result, log } = await publishCase("delay", { lag: 2, attempts: 6, interval: 0 });
  try {
    assert.equal(result.code, 0, result.stderr + result.stdout);
    assert.match(result.stdout, /PUBLISHED_VERIFIED/);
    assert.match(result.stderr, /REGISTRY_PROCESSING/);
    assert.equal(publishCount(log), 1);
    assert.match(result.stdout, /"upload_repeated":false/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
    rmSync(repo, { recursive: true, force: true });
  }
});

test("HTTP 202 followed by eventual visibility verifies once and does not publish again", async () => {
  const { dir, repo, result, log } = await publishCase("http202", { lag: 2, attempts: 6, interval: 0 });
  try {
    assert.equal(result.code, 0, result.stderr + result.stdout);
    assert.match(result.stdout, /PUBLISHED_VERIFIED/);
    assert.match(result.stderr, /REGISTRY_PROCESSING/);
    assert.equal(publishCount(log), 1);
    assert.doesNotMatch(`${result.stdout}\n${result.stderr}`, new RegExp(CANARY));
  } finally {
    rmSync(dir, { recursive: true, force: true });
    rmSync(repo, { recursive: true, force: true });
  }
});

test("registry processing timeout stops without a second upload", async () => {
  const { dir, repo, result, log } = await publishCase("timeout", { attempts: 3, interval: 0 });
  try {
    assert.equal(result.code, 1, result.stdout);
    assert.match(result.stdout, /REGISTRY_TIMEOUT/);
    assert.doesNotMatch(result.stdout, /PUBLISHED_VERIFIED/);
    assert.equal(publishCount(log), 1);
    assert.match(result.stdout, /"upload_repeated":false/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
    rmSync(repo, { recursive: true, force: true });
  }
});

test("documented production poll bounds ignore a shortened override", async () => {
  const source = readFileSync(PROMOTE, "utf8");
  assert.match(source, /REGISTRY_POLL_INTERVAL_MS = 5000/);
  assert.match(source, /REGISTRY_POLL_MAX_ATTEMPTS = 60/);
  const dir = tempDir("vantio-npm-bound-");
  const repo = fixtureRepo();
  const artifact = makeTarball(dir);
  const bytes = readFileSync(artifact);
  const digest = sha256(bytes);
  writeFileSync(join(dir, "download-body.bin"), bytes);
  mockBins(dir, "timeout");
  const approval = join(dir, "approval.json");
  writeFileSync(approval, JSON.stringify({
    approved: true, package: "@vantio/cli", version: "0.3.22",
    source_commit: COMMIT, artifact_sha256: digest,
  }));
  const child = spawn(process.execPath, [PROMOTE, "--publish", ...baseArgs(repo, artifact, digest),
    "--npm-bin", join(dir, "npm"), "--curl-bin", join(dir, "curl"),
    "--allow-local-approval", "--approval-file", approval], {
    stdio: "ignore",
    env: {
      ...process.env,
      MOCK_SHA1: sha1(bytes),
      MOCK_INTEGRITY: integrity(bytes),
      VANTIO_REGISTRY_POLL_INTERVAL_MS: "0",
      VANTIO_REGISTRY_POLL_MAX_ATTEMPTS: "1",
    },
  });
  let finished = false;
  child.on("close", () => { finished = true; });
  await new Promise((resolve) => setTimeout(resolve, 1500));
  try {
    assert.equal(finished, false);
  } finally {
    child.kill("SIGKILL");
    rmSync(dir, { recursive: true, force: true });
    rmSync(repo, { recursive: true, force: true });
  }
});

function zipStore(files) {
  const chunks = [];
  let offset = 0;
  const central = [];
  for (const [name, data] of files) {
    const nameBuf = Buffer.from(name);
    const checksum = crc32(data);
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt16LE(0, 6);
    local.writeUInt16LE(0, 8);
    local.writeUInt32LE(checksum, 14);
    local.writeUInt32LE(data.length, 18);
    local.writeUInt32LE(data.length, 22);
    local.writeUInt16LE(nameBuf.length, 26);
    local.writeUInt16LE(0, 28);
    chunks.push(local, nameBuf, data);
    const centralHeader = Buffer.alloc(46);
    centralHeader.writeUInt32LE(0x02014b50, 0);
    centralHeader.writeUInt16LE(20, 4);
    centralHeader.writeUInt16LE(20, 6);
    centralHeader.writeUInt32LE(checksum, 16);
    centralHeader.writeUInt32LE(data.length, 20);
    centralHeader.writeUInt32LE(data.length, 24);
    centralHeader.writeUInt16LE(nameBuf.length, 28);
    centralHeader.writeUInt32LE(offset, 42);
    central.push(Buffer.concat([centralHeader, nameBuf]));
    offset += local.length + nameBuf.length + data.length;
  }
  const centralDir = Buffer.concat(central);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(files.length, 8);
  end.writeUInt16LE(files.length, 10);
  end.writeUInt32LE(centralDir.length, 12);
  end.writeUInt32LE(offset, 16);
  return Buffer.concat([...chunks, centralDir, end]);
}

function crc32(buf) {
  let crc = ~0;
  for (const byte of buf) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
  }
  return (~crc) >>> 0;
}

test("github gate approval is required and must match the sealed hash", async () => {
  const dir = tempDir("vantio-npm-gh-");
  const repo = fixtureRepo();
  const artifact = makeTarball(dir);
  const bytes = readFileSync(artifact);
  const digest = sha256(bytes);
  writeFileSync(join(dir, "download-body.bin"), bytes);
  mockBins(dir, "publish");
  const approval = {
    approved: true,
    package: "@vantio/cli",
    version: "0.3.22",
    source_commit: COMMIT,
    artifact_sha256: digest,
  };
  const zip = zipStore([["release-approval.json", Buffer.from(JSON.stringify(approval))]]);
  const server = createServer((req, res) => {
    if (req.url === "/repos/vantioai/vantio-open-core/actions/runs/77") {
      res.setHeader("content-type", "application/json");
      res.end(JSON.stringify({
        event: "workflow_dispatch",
        conclusion: "success",
        head_sha: COMMIT,
        path: ".github/workflows/npm-publish.yml",
      }));
      return;
    }
    if (req.url === "/repos/vantioai/vantio-open-core/actions/runs/77/artifacts") {
      res.setHeader("content-type", "application/json");
      res.end(JSON.stringify({
        artifacts: [{
          name: "release-approval",
          expired: false,
          archive_download_url: `http://127.0.0.1:${server.address().port}/zip`,
        }],
      }));
      return;
    }
    if (req.url === "/zip") {
      res.end(zip);
      return;
    }
    res.statusCode = 404;
    res.end("no");
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  try {
    const result = await runNode([
      "--publish", ...baseArgs(repo, artifact, digest),
      "--npm-bin", join(dir, "npm"),
      "--curl-bin", join(dir, "curl"),
      "--github-run-id", "77",
    ], {
      MOCK_SHA1: sha1(bytes),
      MOCK_INTEGRITY: integrity(bytes),
      VANTIO_RELEASE_TEST: "1",
      VANTIO_RELEASE_GITHUB_API: `http://127.0.0.1:${server.address().port}`,
      GH_TOKEN: CANARY,
    });
    assert.equal(result.code, 0, result.stderr + result.stdout);
    assert.match(result.stdout, /PUBLISHED/);
    assert.doesNotMatch(`${result.stdout}\n${result.stderr}`, new RegExp(CANARY));
  } finally {
    server.close();
    rmSync(dir, { recursive: true, force: true });
    rmSync(repo, { recursive: true, force: true });
  }
});

test("custody fetch refuses a non-custody tag and a glob asset name", async () => {
  const script = join(ROOT, "scripts/release/fetch_custody_release.py");
  const badTag = await runPy(script, ["--tag", "v0.3.22", "--version", "0.3.22", "--wheel-name", "vantio_agent_sdk-0.3.22-py3-none-any.whl", "--sdist-name", "vantio_agent_sdk-0.3.22.tar.gz", "--dest", "/tmp", "--dry-run"]);
  assert.equal(badTag.code, 1);
  const badName = await runPy(script, ["--tag", "custody-py-3.0.15", "--version", "3.0.15", "--wheel-name", "vantio_agent_sdk-3.0.15-*.whl", "--sdist-name", "vantio_agent_sdk-3.0.15.tar.gz", "--dest", "/tmp", "--dry-run"]);
  assert.equal(badName.code, 1);
  const ok = await runPy(script, ["--tag", "custody-py-3.0.15", "--version", "3.0.15", "--wheel-name", "vantio_agent_sdk-3.0.15-py3-none-any.whl", "--sdist-name", "vantio_agent_sdk-3.0.15.tar.gz", "--dest", "/tmp", "--dry-run"]);
  assert.equal(ok.code, 0, ok.stderr);
  assert.match(ok.stdout, /vantio_agent_sdk-3\.0\.15-py3-none-any\.whl/);
  assert.match(ok.stdout, /vantio_agent_sdk-3\.0\.15\.tar\.gz/);
  assert.doesNotMatch(ok.stdout, /gh release download v/);
});

function runPy(script, args) {
  return new Promise((resolve) => {
    const child = spawn("python3", [script, ...args], { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => (stdout += chunk));
    child.stderr.on("data", (chunk) => (stderr += chunk));
    child.on("close", (code) => resolve({ code, stdout, stderr }));
  });
}
