/**
 * Try to rebuild the Phantom Engine OCI archive and compare it to WORKING_SEAL.
 * A missing source tree is NOT_PERFORMED. It is not a match and not a mismatch.
 * formal_reproducibility stays NOT_CLAIMED. The label is Lab-only.
 */

import { createHash } from "node:crypto";
import { existsSync, readFileSync, statSync, unlinkSync, writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { laneSeal } from "./pe_canonical_seal.mjs";

const ENGINE_REMOTE = "https://github.com/vantioai/vantio-phantom-engine.git";

export function workingSeal(root) {
  return laneSeal(root);
}

export function classify(seal, probe) {
  const base = {
    formal_reproducibility: "NOT_CLAIMED",
    label: "Lab-only",
    working_seal: seal,
  };
  if (!probe.source_present) {
    return { ...base, comparison: "NOT_PERFORMED", match: null, reason: "source_unavailable", rebuilt_sha256: null };
  }
  if (!probe.build_completed || typeof probe.rebuilt_sha256 !== "string") {
    return {
      ...base,
      comparison: "NOT_PERFORMED",
      match: null,
      reason: probe.build_reason || "build_failed",
      rebuilt_sha256: null,
    };
  }
  const match = probe.rebuilt_sha256 === seal;
  return {
    ...base,
    comparison: match ? "MATCH" : "MISMATCH",
    match,
    reason: match ? "digest_equal" : "digest_differs",
    rebuilt_sha256: probe.rebuilt_sha256,
  };
}

export function sourceLooksLikeEngine(dir) {
  if (!dir || !existsSync(join(dir, "Cargo.toml"))) return false;
  const dockerfiles = ["Dockerfile", "deploy/Dockerfile", "vantio-loader/Dockerfile"];
  return dockerfiles.some((rel) => {
    const path = join(dir, rel);
    if (!existsSync(path) || !statSync(path).isFile()) return false;
    const text = readFileSync(path, "utf8");
    return text.includes("vantio-loader") || text.includes("bpf-linker");
  });
}

export function candidateDirs(root) {
  const extra = process.env.VANTIO_ENGINE_SRC ? [process.env.VANTIO_ENGINE_SRC] : [];
  return [
    ...extra,
    join(root, "..", "vantio-phantom-engine"),
    "/home/zach_vantio/vantio-phantom-engine",
  ];
}

export function findSource(root) {
  for (const dir of candidateDirs(root)) {
    if (sourceLooksLikeEngine(dir)) return dir;
  }
  return "";
}

export function remoteProbe() {
  const proc = spawnSync("git", ["ls-remote", ENGINE_REMOTE, "HEAD"], {
    encoding: "utf8",
    timeout: 20000,
  });
  const stderr = redact(proc.stderr || proc.error?.message || "");
  return {
    exit_code: proc.status,
    ok: proc.status === 0 && /^[0-9a-f]{40}\s+HEAD$/m.test(proc.stdout || ""),
    stderr: stderr.slice(0, 300),
  };
}

export function attempt(root) {
  const seal = workingSeal(root);
  const remote = remoteProbe();
  const source = findSource(root);
  const probe = {
    build_completed: false,
    build_reason: "",
    rebuilt_sha256: null,
    source_present: Boolean(source),
  };
  if (!source) probe.build_reason = "source_unavailable";
  else Object.assign(probe, buildArchive(source));
  const body = classify(seal, probe);
  return {
    ...body,
    remote_exit_code: remote.exit_code,
    remote_ok: remote.ok,
    remote_stderr: remote.stderr,
    source_dir_found: Boolean(source),
  };
}

function engineDockerfile(dir) {
  for (const rel of ["Dockerfile", "deploy/Dockerfile", "vantio-loader/Dockerfile"]) {
    const path = join(dir, rel);
    if (!existsSync(path) || !statSync(path).isFile()) continue;
    const text = readFileSync(path, "utf8");
    if (text.includes("vantio-loader") || text.includes("bpf-linker")) return path;
  }
  return "";
}

export function buildArchive(sourceDir) {
  const dockerfile = engineDockerfile(sourceDir);
  if (!dockerfile) return { source_present: true, build_completed: false, build_reason: "dockerfile_missing", rebuilt_sha256: null };
  const version = spawnSync("docker", ["version", "--format", "{{.Server.Version}}"], { encoding: "utf8", timeout: 20000 });
  if (version.status !== 0) return { source_present: true, build_completed: false, build_reason: "docker_unavailable", rebuilt_sha256: null };
  const tag = "vantio-engine-rebuild:local";
  const built = spawnSync("docker", ["build", "--file", dockerfile, "--tag", tag, sourceDir], { encoding: "utf8" });
  if (built.status !== 0) return { source_present: true, build_completed: false, build_reason: "docker_build_failed", rebuilt_sha256: null };
  const archive = join(tmpdir(), "vantio-engine-rebuild.oci.tar");
  const saved = spawnSync("docker", ["save", "--output", archive, tag], { encoding: "utf8" });
  spawnSync("docker", ["rmi", tag], { encoding: "utf8", timeout: 60000 });
  if (saved.status !== 0) return { source_present: true, build_completed: false, build_reason: "docker_save_failed", rebuilt_sha256: null };
  const rebuilt = sha256File(archive);
  unlinkSync(archive);
  return { source_present: true, build_completed: true, build_reason: "built", rebuilt_sha256: rebuilt };
}

function redact(text) {
  return String(text).replace(/x-access-token:[^@\s]+/g, "x-access-token:redacted").trim();
}

function sha256File(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

export function hashArchive(path) {
  if (!existsSync(path) || !statSync(path).isFile()) return null;
  return sha256File(path);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const root = join(import.meta.dirname, "..", "..");
  const body = attempt(root);
  const outDir = join(root, "docs/planning/engine-archive-rebuild");
  writeFileSync(join(outDir, "RESULT.json"), `${JSON.stringify(body, null, 2)}\n`);
  process.stdout.write(`${body.comparison} ${body.reason}\n`);
}
