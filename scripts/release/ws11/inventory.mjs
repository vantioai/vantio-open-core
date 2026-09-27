import { createHash } from "node:crypto";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

export const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "../../..");

const SKIP_DIRS = new Set([".git", "node_modules", "dist", "__pycache__", ".pytest_cache"]);
const BINDING_ACTION = /@(?:[0-9a-f]{40}|sha256:[0-9a-f]{64})$/i;

export function sha256Text(text) {
  return createHash("sha256").update(text).digest("hex");
}

export function sha256File(path) {
  return sha256Text(readFileSync(path));
}

function readText(root, rel) {
  return readFileSync(join(root, rel), "utf8");
}

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    if (SKIP_DIRS.has(name)) continue;
    const abs = join(dir, name);
    const info = statSync(abs);
    if (info.isDirectory()) walk(abs, out);
    else if (info.isFile()) out.push(abs);
  }
  return out;
}

export function repoFiles(root) {
  return walk(root).map((abs) => relative(root, abs).split(sep).join("/")).sort();
}

export function triggerHasPush(text) {
  const lines = text.split("\n").filter((line) => !line.trim().startsWith("#"));
  const start = lines.findIndex((line) => line === "on:");
  if (start < 0) return false;
  const body = [];
  for (const line of lines.slice(start + 1)) {
    if (line.length > 0 && !/^\s/.test(line)) break;
    body.push(line);
  }
  return body.some((line) => /^\s*push:/.test(line));
}

export function actionUses(text) {
  return [...text.matchAll(/^\s*uses:\s*(\S+)\s*$/gm)].map((match) => match[1]);
}

function constString(source, name) {
  const match = source.match(new RegExp(`^${name} = "([^"]*)"`, "m"));
  if (!match) throw new Error(`missing ${name} in stage_sealed_pypi.py`);
  return match[1];
}

function constInt(source, name) {
  const match = source.match(new RegExp(`^${name} = ([0-9]+)`, "m"));
  if (!match) throw new Error(`missing ${name} in stage_sealed_pypi.py`);
  return Number(match[1]);
}

export function readSealedPypi(root) {
  const source = readText(root, "scripts/release/stage_sealed_pypi.py");
  return {
    package: constString(source, "PACKAGE"),
    version: constString(source, "VERSION"),
    wheel_name: constString(source, "WHEEL_NAME"),
    sdist_name: constString(source, "SDIST_NAME"),
    wheel_sha256: constString(source, "WHEEL_SHA256"),
    sdist_sha256: constString(source, "SDIST_SHA256"),
    wheel_bytes: constInt(source, "WHEEL_BYTES"),
    sdist_bytes: constInt(source, "SDIST_BYTES"),
  };
}

export function parsePackageManager(raw) {
  const match = /^pnpm@([^+]+)\+sha512\.([A-Za-z0-9+/=]+)$/.exec(raw);
  if (!match) return { name: "unknown", version: null, integrity: null, raw };
  return { name: "pnpm", version: match[1], integrity: `sha512.${match[2]}`, raw };
}

export function parsePnpmPackages(text) {
  const lines = text.split("\n");
  const start = lines.findIndex((line) => line === "packages:");
  if (start < 0) return [];
  const packages = [];
  let current = null;
  for (const line of lines.slice(start + 1)) {
    if (/^[A-Za-z0-9]/.test(line)) break;
    const key = /^ {2}'([^']+)':$/.exec(line) || /^ {2}"([^"]+)":$/.exec(line) || /^ {2}([^'":]+):$/.exec(line);
    if (key) {
      const raw = key[1];
      const at = raw.lastIndexOf("@");
      current = { name: raw.slice(0, at), version: raw.slice(at + 1), integrity: null };
      packages.push(current);
      continue;
    }
    if (!current) continue;
    const integrity = /integrity:\s*(sha(?:256|512)-[A-Za-z0-9+/=]+)/.exec(line);
    if (integrity && !current.integrity) current.integrity = integrity[1];
  }
  return packages;
}

function npmPurl(name, version) {
  const encoded = name.startsWith("@") ? `%40${name.slice(1)}` : name;
  return `pkg:npm/${encoded}@${version}`;
}

export function buildSbom(root) {
  const lockText = readText(root, "pnpm-lock.yaml");
  const lockPackages = parsePnpmPackages(lockText);
  const rootPackage = JSON.parse(readText(root, "package.json"));
  const components = [];
  const seen = new Set();
  function add(component) {
    const key = `${component.name}@${component.version}`;
    if (seen.has(key)) return;
    seen.add(key);
    components.push(component);
  }
  for (const file of repoFiles(root).filter((rel) => rel.endsWith("package.json"))) {
    const manifest = JSON.parse(readText(root, file));
    if (!manifest.name || !manifest.version) continue;
    const component = {
      type: "library",
      name: manifest.name,
      version: manifest.version,
      purl: npmPurl(manifest.name, manifest.version),
      scope: file === "package.json" ? "root" : "workspace-manifest",
    };
    if (typeof manifest.license === "string") component.licenses = [{ license: { id: manifest.license } }];
    add(component);
  }
  const pyproject = readText(root, "packages/vantio-agent-sdk-py/pyproject.toml");
  const pyName = /^name = "([^"]+)"/m.exec(pyproject);
  const pyVersion = /^version = "([^"]+)"/m.exec(pyproject);
  if (pyName && pyVersion) {
    add({
      type: "library",
      name: pyName[1],
      version: pyVersion[1],
      purl: `pkg:pypi/${pyName[1]}@${pyVersion[1]}`,
      scope: "python-manifest",
      licenses: [{ license: { id: "MIT" } }],
    });
  }
  for (const item of lockPackages) {
    const component = {
      type: "library",
      name: item.name,
      version: item.version,
      purl: npmPurl(item.name, item.version),
      scope: "pnpm-lockfile-packages",
    };
    if (item.integrity) component.hashes = [{ alg: item.integrity.split("-")[0].toUpperCase(), content: item.integrity }];
    add(component);
  }
  return {
    bomFormat: "CycloneDX",
    specVersion: "1.5",
    version: 1,
    metadata: {
      component: {
        type: "application",
        name: rootPackage.name,
        version: rootPackage.version,
      },
    },
    components,
    properties: [
      { name: "vantio:completeness", value: "pnpm-lockfile-packages-section-plus-workspace-manifests" },
      { name: "vantio:bound-to-sealed-artifact", value: "false" },
      { name: "vantio:formal-provenance-level", value: "NOT_CLAIMED" },
      { name: "vantio:formal-reproducibility", value: "NOT_CLAIMED" },
      { name: "vantio:hardware-provenance", value: "NOT_CLAIMED" },
      { name: "vantio:lockfile-sha256", value: sha256Text(lockText) },
    ],
  };
}

export function scanManifestLicenses(root) {
  const findings = [];
  const scanned = [];
  for (const file of repoFiles(root)) {
    if (file.endsWith("package.json")) {
      const manifest = JSON.parse(readText(root, file));
      if (!manifest.name) continue;
      scanned.push(file);
      if (typeof manifest.license !== "string" || manifest.license.length === 0) {
        findings.push({ id: `license-missing:${file}`, path: file, name: manifest.name, accepted: false });
      }
    }
    if (file.endsWith("pyproject.toml")) {
      const text = readText(root, file);
      scanned.push(file);
      if (!/^license = "[^"]+"/m.test(text)) {
        findings.push({ id: `license-missing:${file}`, path: file, name: file, accepted: false });
      }
    }
  }
  return {
    schema: "vantio.ws11.manifest-license-scan/v1",
    tool_name: "ws11-manifest-license-scan",
    tool_version: "1",
    scope: "workspace-manifests",
    bound_to_sealed_bytes: false,
    status: findings.length === 0 ? "CLEAN" : "FINDINGS",
    scanned,
    findings,
  };
}

export function privateManualPaths(root) {
  return repoFiles(root).filter((rel) => rel.includes("PRIVATE-MANUAL") || rel.includes("CUSTOMER-MANUAL"));
}

export function buildInventory(root) {
  const packageJson = JSON.parse(readText(root, "package.json"));
  const lockText = readText(root, "pnpm-lock.yaml");
  const lockVersion = /^lockfileVersion:\s*'([^']+)'/m.exec(lockText);
  const workflowPaths = repoFiles(root).filter((rel) => rel.startsWith(".github/workflows/") && rel.endsWith(".yml"));
  const actionPaths = repoFiles(root).filter((rel) => rel.startsWith(".github/") && (rel.endsWith(".yml") || rel.endsWith(".yaml")));
  const actions = [];
  for (const file of actionPaths) {
    for (const uses of actionUses(readText(root, file))) {
      if (uses.startsWith("./")) continue;
      actions.push({ file, uses, digest_pinned: BINDING_ACTION.test(uses) });
    }
  }
  const publish = {};
  for (const file of ["npm-publish.yml", "pypi-publish.yml", "mcp-registry-publish.yml", "ci.yml", "enterprise-slsa-provenance.yml"]) {
    publish[file] = triggerHasPush(readText(root, `.github/workflows/${file}`));
  }
  const architecture = readText(root, "architecture_state.md");
  const sealed = readSealedPypi(root);
  const register = JSON.parse(readText(root, "docs/programs/production-readiness/RELEASE-REGISTER.json"));
  const py = register.releases.find((item) => item.id === "REL-PY-3.1.0");
  const cli = register.releases.find((item) => item.id === "REL-CLI-0.3.24");
  if (!py || !cli) throw new Error("release register is missing the CLI or Python row");
  if (py.wheel_sha256 !== sealed.wheel_sha256 || py.sdist_sha256 !== sealed.sdist_sha256) {
    throw new Error("release register hashes differ from stage_sealed_pypi.py");
  }
  if (py.wheel_bytes !== sealed.wheel_bytes || py.sdist_bytes !== sealed.sdist_bytes) {
    throw new Error("release register byte lengths differ from stage_sealed_pypi.py");
  }
  const pyproject = readText(root, "packages/vantio-agent-sdk-py/pyproject.toml");
  const hatch = /requires = \[(.*)\]/.exec(pyproject);
  const pythonBuildRequires = hatch
    ? hatch[1].replaceAll('"', "").split(",").map((item) => item.trim()).filter(Boolean)
    : [];
  return {
    schema: "vantio.ws11.pin-report/v1",
    audience: "INTERNAL_RESTRICTED",
    formal_slsa_level: "NOT_CLAIMED",
    formal_certification: "NOT_CLAIMED",
    formal_reproducibility: "NOT_CLAIMED",
    hardware_backed_provenance: "NOT_CLAIMED",
    release_success: false,
    package_manager: parsePackageManager(packageJson.packageManager),
    lockfile: {
      path: "pnpm-lock.yaml",
      sha256: sha256Text(lockText),
      lockfile_version: lockVersion ? lockVersion[1] : null,
    },
    actions,
    workflow_triggers_push: publish,
    workflow_count: workflowPaths.length,
    python_build_requires: pythonBuildRequires,
    python_build_requires_pinned: pythonBuildRequires.length > 0 && pythonBuildRequires.every((item) => /[=><]/.test(item)),
    sealed_pypi: sealed,
    release_register: {
      cli_version: cli.version,
      cli_tag: cli.tag,
      cli_tag_commit: cli.tag_commit,
      python_version: py.version,
      python_state: py.state,
      python_publisher_commit: py.publisher_commit,
    },
    provenance_workflow: {
      path: ".github/workflows/enterprise-slsa-provenance.yml",
      attest_action: "actions/attest-build-provenance@v2",
      runs_on_push: publish["enterprise-slsa-provenance.yml"],
      formal_slsa_level: "NOT_CLAIMED",
      historical_log_contains_level_assertion: architecture.includes("SLSA Level"),
      apps_web_present: repoFiles(root).some((rel) => rel.startsWith("apps/web/")),
      edge_proxy_present: repoFiles(root).some((rel) => rel.startsWith("packages/edge-proxy/")),
    },
    versions: JSON.parse(readText(root, "docs/governance/VERSION-METADATA.json")).packages.map((item) => ({
      id: item.id,
      name: item.name,
      version: item.version,
      manifest: item.manifest,
    })),
    manual_paths: privateManualPaths(root),
  };
}
