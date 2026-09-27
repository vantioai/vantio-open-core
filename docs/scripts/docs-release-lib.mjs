import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join, relative, sep } from "node:path";

const SKIP_DIRS = new Set([".git", "node_modules", "__pycache__", ".pytest_cache", "dist"]);

export function readJson(root, rel) {
  return JSON.parse(readFileSync(join(root, rel), "utf8"));
}

export function readText(root, rel) {
  return readFileSync(join(root, rel), "utf8");
}

function posix(rel) {
  return rel.split(sep).join("/");
}

function sameSet(left, right) {
  const a = [...left].sort();
  const b = [...right].sort();
  if (a.length !== b.length) return false;
  return a.every((item, index) => item === b[index]);
}

function setDiff(expected, actual) {
  const exp = new Set(expected);
  const act = new Set(actual);
  return {
    missing: [...exp].filter((item) => !act.has(item)).sort(),
    unexpected: [...act].filter((item) => !exp.has(item)).sort(),
  };
}

function hasToken(text, name) {
  const re = new RegExp(`(^|[^A-Za-z0-9_])${name}([^A-Za-z0-9_]|$)`);
  return re.test(text);
}

function walkFiles(dir, out = []) {
  if (!existsSync(dir)) return out;
  for (const ent of readdirSync(dir, { withFileTypes: true })) {
    if (SKIP_DIRS.has(ent.name) || ent.name.endsWith(".egg-info")) continue;
    const abs = join(dir, ent.name);
    if (ent.isDirectory()) walkFiles(abs, out);
    else if (ent.isFile()) out.push(abs);
  }
  return out;
}

function relFiles(dir) {
  return walkFiles(dir).map((abs) => posix(relative(dir, abs)));
}

export function checkManifestShape(manifest, schema) {
  const missing = schema.required.filter((key) => manifest[key] === undefined);
  const extra = Object.keys(manifest).filter((key) => !schema.required.includes(key) && !schema.properties?.[key]);
  const problems = [];
  if (manifest.schema !== "vantio.docs-release/v1") problems.push("schema must be vantio.docs-release/v1");
  if (missing.length) problems.push(`missing keys: ${missing.join(", ")}`);
  if (extra.length) problems.push(`unexpected keys: ${extra.join(", ")}`);
  if (manifest.base_commit !== "d7299a35be0d9a70ec306ca672aa1359e09f1515") {
    problems.push("base_commit is not d7299a35be0d9a70ec306ca672aa1359e09f1515");
  }
  return problems.join("; ");
}

function readDeclaredVersion(root, pkg) {
  const text = readText(root, pkg.manifest);
  if (pkg.manifest.endsWith(".json")) return JSON.parse(text).version;
  const match = text.match(/^version\s*=\s*"([^"]+)"/m);
  return match ? match[1] : undefined;
}

export function packageVersionProblems(root, packages) {
  const problems = [];
  for (const pkg of packages) {
    const declared = readDeclaredVersion(root, pkg);
    if (declared !== pkg.version) {
      problems.push(`${pkg.name} manifest version ${declared} != ${pkg.version}`);
    }
    for (const extra of pkg.also || []) {
      const text = readText(root, extra.file);
      if (!text.includes(extra.contains)) {
        problems.push(`${pkg.name} missing ${extra.contains} in ${extra.file}`);
      }
    }
  }
  return problems.join("; ");
}

export function readmeBoundaryProblems(readme, boundary) {
  const problems = [];
  for (const phrase of boundary.required_phrases) {
    if (!readme.includes(phrase)) problems.push(`missing required phrase: ${phrase}`);
  }
  for (const phrase of boundary.forbidden_phrases) {
    if (readme.includes(phrase)) problems.push(`forbidden phrase: ${phrase}`);
  }
  return problems.join("; ");
}

function tsExportNames(source) {
  return [...source.matchAll(/^export (?:async )?(?:function|const|class|type|interface|enum) ([A-Za-z0-9_]+)/gm)].map((match) => match[1]);
}

function pythonAllNames(source) {
  const block = source.match(/__all__\s*=\s*\[([\s\S]*?)\]/);
  if (!block) return [];
  return [...block[1].matchAll(/["']([A-Za-z0-9_]+)["']/g)].map((match) => match[1]);
}

export function publicExportProblems(root, spec) {
  const problems = [];
  const doc = readText(root, spec.doc);
  for (const pkg of spec.packages) {
    const source = readText(root, pkg.source);
    const found = pkg.kind === "python-all" ? pythonAllNames(source) : tsExportNames(source);
    const diff = setDiff(pkg.names, found);
    if (diff.missing.length || diff.unexpected.length) {
      problems.push(
        `${pkg.id} exports drifted; missing [${diff.missing.join(", ")}] unexpected [${diff.unexpected.join(", ")}]`,
      );
    }
    for (const name of pkg.names) {
      if (!hasToken(doc, name)) problems.push(`${pkg.id} export ${name} is not in ${spec.doc}`);
    }
    for (const removed of spec.removed) {
      if (found.includes(removed)) problems.push(`${pkg.id} still exports removed name ${removed}`);
    }
  }
  return problems.join("; ");
}

export function removedExportViolations(text, removedNames, headingPattern) {
  const historical = new RegExp(headingPattern, "i");
  let heading = "";
  const hits = [];
  for (const line of text.split("\n")) {
    const match = /^(#{1,6})\s+(.*)$/.exec(line);
    if (match) {
      heading = match[2];
      continue;
    }
    if (historical.test(heading)) continue;
    for (const name of removedNames) {
      if (line.includes(name)) hits.push(name);
    }
  }
  return [...new Set(hits)];
}

export function examplesProblems(root, examples) {
  const problems = [];
  for (const example of examples) {
    if (!example.feasible) {
      if (!example.reason || !String(example.reason).trim()) problems.push(`${example.id} needs a reason`);
      else if (!example.path || !existsSync(join(root, example.path))) problems.push(`${example.id} path missing`);
      continue;
    }
    if (!Array.isArray(example.run) || example.run.length === 0) {
      problems.push(`${example.id} missing run`);
      continue;
    }
    const [cmd, ...args] = example.run;
    const exe = cmd === "node" ? process.execPath : cmd;
    const result = spawnSync(exe, args, { cwd: root, encoding: "utf8", timeout: 20000 });
    if (result.status !== 0) {
      const output = (result.stderr || result.stdout || "").trim();
      problems.push(`${example.id} exit ${result.status}: ${output}`);
    }
  }
  return problems.join("; ");
}

function scannedEnvNames(root, directories) {
  const names = new Set();
  const re = /(?:process\.env\.([A-Z][A-Z0-9_]*)|process\.env\[\s*["']([A-Z][A-Z0-9_]*)["']\s*\]|os\.environ(?:\.get|\.setdefault)\(\s*["']([A-Z][A-Z0-9_]*)["']|os\.environ\[\s*["']([A-Z][A-Z0-9_]*)["']\s*\])/g;
  for (const dir of directories) {
    for (const abs of walkFiles(join(root, dir))) {
      const text = readFileSync(abs, "utf8");
      for (const match of text.matchAll(re)) {
        const name = match[1] || match[2] || match[3] || match[4];
        if (name.startsWith("VANTIO_") || name === "DO_NOT_TRACK") names.add(name);
      }
    }
  }
  return names;
}

export function envVarProblems(root, spec) {
  const found = scannedEnvNames(root, spec.scan_directories);
  const catalog = new Map(spec.vars.map((item) => [item.name, item]));
  const problems = [];
  const diff = setDiff([...catalog.keys()], [...found]);
  if (diff.missing.length) problems.push(`catalog names not read in runtime code: ${diff.missing.join(", ")}`);
  if (diff.unexpected.length) problems.push(`runtime env vars missing from catalog: ${diff.unexpected.join(", ")}`);
  const doc = readText(root, spec.doc);
  for (const item of spec.vars) {
    if (item.audience === "internal") {
      if (!item.reason) problems.push(`${item.name} internal var needs a reason`);
      continue;
    }
    if (item.audience !== "public") problems.push(`${item.name} has unknown audience ${item.audience}`);
    else if (!hasToken(doc, item.name)) problems.push(`${item.name} is not documented in ${spec.doc}`);
  }
  return problems.join("; ");
}

function quotedStrings(block) {
  return [...block.matchAll(/"([^"]+)"/g)].map((match) => match[1]);
}

function dictKeys(block) {
  return [...block.matchAll(/"([^"]+)"\s*:/g)].map((match) => match[1]);
}

function extractBlock(source, start, end) {
  const from = source.indexOf(start);
  if (from < 0) return null;
  const to = source.indexOf(end, from + start.length);
  if (to < 0) return null;
  return source.slice(from + start.length, to);
}

export function hostCatalogProblems(root, spec) {
  const problems = [];
  for (const source of spec.sources) {
    const text = readText(root, source.file);
    const block = extractBlock(text, source.start, source.end);
    if (block == null) {
      problems.push(`could not extract ${source.id} from ${source.file}`);
      continue;
    }
    const found = source.extract === "dict-keys" ? dictKeys(block) : quotedStrings(block);
    const diff = setDiff(spec.hosts, found);
    if (diff.missing.length || diff.unexpected.length) {
      problems.push(
        `${source.id} host catalog drifted; missing [${diff.missing.join(", ")}] unexpected [${diff.unexpected.join(", ")}]`,
      );
    }
  }
  return problems.join("; ");
}

function collapseWs(text) {
  return text.replace(/\s+/g, " ").trim();
}

function leadingProse(source) {
  const text = source.replace(/^\uFEFF/, "");
  const doc = text.match(/^"""([\s\S]*?)"""/) || text.match(/^'''([\s\S]*?)'''/);
  if (doc) return doc[1];
  const lines = text.split("\n");
  const buf = [];
  for (const line of lines) {
    if (line.startsWith("//")) buf.push(line.replace(/^\/\/\s?/, ""));
    else if (buf.length === 0 && line.trim() === "") continue;
    else break;
  }
  return buf.join("\n");
}

function isPathContinuation(after) {
  const s = after.replace(/^\s+/, "");
  if (!s) return false;
  if (s.startsWith("|") || s.startsWith("/")) return true;
  if (s.startsWith("()")) return true;
  const and = s.match(/^and\s+([A-Za-z_][A-Za-z0-9_]*)/);
  if (and) {
    const prose = new Set(["observe", "the", "a", "an", "not", "file", "inline"]);
    if (!prose.has(and[1])) return true;
  }
  if (/^,\s*(?:and\s+)?(?:curl|wget|httpie|aria2c)\b/.test(s)) return true;
  const word = s.match(/^([A-Za-z_][A-Za-z0-9_]*)/);
  if (!word) return false;
  const rest = s.slice(word[1].length);
  if (rest.startsWith("/")) return true;
  if (rest.startsWith(".") && /^[A-Za-z_]/.test(rest.slice(1))) return true;
  if (rest.startsWith("()")) return true;
  return false;
}

function boundedIndex(haystack, needle, from) {
  let at = from;
  while (at < haystack.length) {
    const index = haystack.indexOf(needle, at);
    if (index < 0) return -1;
    const prev = index === 0 ? "" : haystack[index - 1];
    if (!/[A-Za-z0-9_]/.test(prev)) return index;
    at = index + 1;
  }
  return -1;
}

function needleHaystack(source, needle) {
  const collapsedNeedle = collapseWs(needle);
  const prose = collapseWs(leadingProse(source));
  if (boundedIndex(prose, collapsedNeedle, 0) >= 0) return prose;
  return collapseWs(source);
}

// Reject a needle when every bounded match is only the start of a longer path clause.
export function needleIsTruncatedPrefix(source, needle) {
  const collapsedNeedle = collapseWs(needle);
  if (!collapsedNeedle) return true;
  const haystack = needleHaystack(source, needle);
  let from = 0;
  let matches = 0;
  while (from < haystack.length) {
    const at = boundedIndex(haystack, collapsedNeedle, from);
    if (at < 0) break;
    matches += 1;
    if (!isPathContinuation(haystack.slice(at + collapsedNeedle.length))) return false;
    from = at + 1;
  }
  return matches > 0;
}

function sourceHasNeedle(source, needle) {
  const collapsedNeedle = collapseWs(needle);
  return boundedIndex(needleHaystack(source, needle), collapsedNeedle, 0) >= 0;
}

export function supportedPathProblems(root, spec) {
  const doc = readText(root, spec.doc);
  const problems = [];
  const paths = spec.paths;
  for (const path of paths) {
    const source = readText(root, path.source);
    if (!sourceHasNeedle(source, path.source_needle)) {
      problems.push(`${path.id} source needle missing in ${path.source}`);
    } else if (needleIsTruncatedPrefix(source, path.source_needle)) {
      problems.push(`${path.id} source needle is a prefix of a longer path sentence in ${path.source}`);
    }
    if (!doc.includes(path.doc_phrase)) problems.push(`${path.id} doc phrase missing`);
    if (path.state !== "supported" && path.state !== "unsupported") {
      problems.push(`${path.id} has unknown state ${path.state}`);
    }
  }
  for (const path of paths) {
    const needle = collapseWs(path.source_needle);
    for (const other of paths) {
      if (path.source !== other.source || path.id === other.id) continue;
      const longer = collapseWs(other.source_needle);
      if (needle === longer) continue;
      if (longer.startsWith(needle) && isPathContinuation(longer.slice(needle.length))) {
        problems.push(`${path.id} source needle is a prefix of ${other.id}`);
      }
    }
  }
  return problems.join("; ");
}

function extractVocabulary(source) {
  const block = source.match(/const VOCABULARY = Object\.freeze\(\[([\s\S]*?)\]\)/);
  if (!block) return [];
  return quotedStrings(block[1]);
}

function extractActionTokens(source) {
  const block = source.match(/export type VantioActionTaken =([\s\S]*?);/);
  if (!block) return [];
  return quotedStrings(block[1]);
}

export function statusTokenProblems(root, spec) {
  const doc = readText(root, spec.doc);
  const problems = [];
  const display = extractVocabulary(readText(root, spec.display_source));
  const actions = extractActionTokens(readText(root, spec.action_source));
  const displayDiff = setDiff(spec.display_tokens, display);
  const actionDiff = setDiff(spec.action_tokens, actions);
  if (displayDiff.missing.length || displayDiff.unexpected.length) {
    problems.push(
      `display tokens drifted; missing [${displayDiff.missing.join(", ")}] unexpected [${displayDiff.unexpected.join(", ")}]`,
    );
  }
  if (actionDiff.missing.length || actionDiff.unexpected.length) {
    problems.push(
      `action tokens drifted; missing [${actionDiff.missing.join(", ")}] unexpected [${actionDiff.unexpected.join(", ")}]`,
    );
  }
  if (!doc.includes(spec.schema_status)) problems.push(`doc missing schema_status ${spec.schema_status}`);
  for (const token of [...spec.display_tokens, ...spec.action_tokens]) {
    if (!hasToken(doc, token)) problems.push(`status token ${token} is not documented`);
  }
  return problems.join("; ");
}

export function knownLimitationProblems(doc, phrases) {
  const problems = [];
  if (!doc || !doc.trim()) return "known limitations document is empty";
  for (const phrase of phrases) {
    if (!doc.includes(phrase)) problems.push(`missing limitation: ${phrase}`);
  }
  return problems.join("; ");
}

export function changelogProblems(root, packages) {
  const problems = [];
  for (const pkg of packages) {
    const text = readText(root, pkg.changelog);
    const lines = text.split("\n");
    if (!lines.includes(pkg.changelog_heading)) {
      problems.push(`${pkg.name} changelog ${pkg.changelog} missing ${pkg.changelog_heading}`);
    }
  }
  return problems.join("; ");
}

export function aiGuideProblems(text, packages) {
  const blocks = [...text.matchAll(/```json\n([\s\S]*?)```/g)];
  let versions = null;
  for (const block of blocks) {
    const parsed = JSON.parse(block[1]);
    if (parsed && parsed.ai_guide_versions) versions = parsed.ai_guide_versions;
  }
  if (!versions) return "AI guide is missing an ai_guide_versions JSON block";
  const expected = Object.fromEntries(packages.map((pkg) => [pkg.name, pkg.version]));
  const diff = setDiff(Object.keys(expected), Object.keys(versions));
  const problems = [];
  if (diff.missing.length || diff.unexpected.length) {
    problems.push(`AI guide version keys drifted; missing [${diff.missing.join(", ")}] unexpected [${diff.unexpected.join(", ")}]`);
  }
  for (const [name, version] of Object.entries(expected)) {
    if (versions[name] !== version) problems.push(`AI guide ${name} is ${versions[name]} != ${version}`);
  }
  return problems.join("; ");
}

export function parseLlmsPaths(text) {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"));
}

export function llmsTxtProblems(text, canonicalDocs) {
  const listed = parseLlmsPaths(text);
  const diff = setDiff(canonicalDocs, listed);
  const problems = [];
  if (diff.missing.length) problems.push(`llms.txt missing ${diff.missing.join(", ")}`);
  if (diff.unexpected.length) problems.push(`llms.txt points outside canonical docs: ${diff.unexpected.join(", ")}`);
  if (listed.length !== canonicalDocs.length) problems.push("llms.txt path count does not match the canonical set");
  return problems.join("; ");
}

export function renderLlmsFull(root, canonicalDocs) {
  const parts = ["# llms-full.txt\n", "Generated from canonical docs listed in docs/governance/MANIFEST.json. Do not edit by hand.\n"];
  for (const rel of canonicalDocs) {
    const body = readText(root, rel);
    parts.push(`\n# BEGIN ${rel}\n`);
    parts.push(body.endsWith("\n") ? body : `${body}\n`);
    parts.push(`# END ${rel}\n`);
  }
  return parts.join("");
}

export function npmPackPaths(pkgDir) {
  const result = spawnSync("npm", ["pack", "--dry-run", "--json", "--ignore-scripts"], {
    cwd: pkgDir,
    encoding: "utf8",
    timeout: 30000,
  });
  if (result.status !== 0) {
    throw new Error((result.stderr || result.stdout || "npm pack --dry-run failed").trim());
  }
  const start = result.stdout.indexOf("[");
  const parsed = JSON.parse(start >= 0 ? result.stdout.slice(start) : result.stdout);
  const entry = Array.isArray(parsed) ? parsed[0] : parsed;
  return entry.files.map((file) => file.path);
}

function tomlStringList(text, key) {
  const match = text.match(new RegExp(`${key}\\s*=\\s*\\[([^\\]]*)\\]`));
  if (!match) return [];
  return [...match[1].matchAll(/"([^"]+)"/g)].map((item) => item[1]);
}

export function pythonCandidatePaths(pkgDir) {
  const pyprojectPath = join(pkgDir, "pyproject.toml");
  const pyproject = existsSync(pyprojectPath) ? readFileSync(pyprojectPath, "utf8") : "";
  const packages = tomlStringList(pyproject, "packages");
  const all = relFiles(pkgDir);
  const wheel = all.filter((rel) => packages.some((name) => rel === name || rel.startsWith(`${name}/`)));
  return { packages, wheel, sdist: all };
}

export function denialHits(paths, denies) {
  const hits = [];
  for (const rel of paths) {
    const normalized = posix(rel);
    if (normalized.split("/").includes("..")) hits.push(`${normalized} escapes the package`);
    for (const deny of denies) {
      if (normalized.includes(deny)) hits.push(`${normalized} matches ${deny}`);
    }
  }
  return hits;
}

export function assemblePeCustomerBundle({ version, manualText, manualPath = "PRIVATE-MANUAL.md" }) {
  const match = /^manual_version:\s*(\S+)\s*$/m.exec(manualText || "");
  if (!match) return { ok: false, error: "private manual missing manual_version header" };
  if (match[1] !== version) {
    return { ok: false, error: `manual version ${match[1]} != bundle version ${version}` };
  }
  const members = [
    { path: "bundle.json", role: "manifest" },
    { path: manualPath, role: "private-manual" },
  ];
  const roles = members.map((member) => member.role);
  if (!roles.includes("manifest") || !roles.includes("private-manual")) {
    return { ok: false, error: "bundle is missing manifest or private-manual" };
  }
  return {
    ok: true,
    bundle: {
      version,
      public_distribution: false,
      members,
    },
  };
}

export function countPatterns(text, patterns) {
  let count = 0;
  for (const pattern of patterns) {
    const matches = text.match(new RegExp(pattern.regex, "g"));
    if (matches) count += matches.length;
  }
  return count;
}

export function roadmapViolations(text, features) {
  const hits = [];
  for (const feature of features) {
    const re = new RegExp(feature.forbidden, "gi");
    for (const line of text.split("\n")) {
      re.lastIndex = 0;
      if (!re.test(line)) continue;
      if (feature.allowed_line && new RegExp(feature.allowed_line, "i").test(line)) continue;
      hits.push(`${feature.id}: ${line.trim()}`);
    }
  }
  return hits;
}

function excludedPath(rel, prefixes) {
  return prefixes.some((prefix) => rel === prefix.replace(/\/$/, "") || rel.startsWith(prefix));
}

export function collectLegacyHits(root, scan, patterns) {
  const hits = [];
  function visit(rel) {
    const abs = join(root, rel);
    if (!existsSync(abs)) return;
    for (const ent of readdirSync(abs, { withFileTypes: true })) {
      if (SKIP_DIRS.has(ent.name)) continue;
      const child = rel ? `${rel}/${ent.name}` : ent.name;
      if (excludedPath(child, scan.exclude_prefixes)) continue;
      const childAbs = join(root, child);
      if (ent.isDirectory()) visit(child);
      else if (ent.isFile() && scan.extensions.some((ext) => child.endsWith(ext))) {
        const count = countPatterns(readFileSync(childAbs, "utf8"), patterns);
        if (count > 0) hits.push({ path: child, count });
      }
    }
  }
  visit("");
  hits.sort((left, right) => left.path.localeCompare(right.path));
  return hits;
}

export function diffHitLists(actual, expected) {
  const actualMap = new Map(actual.map((hit) => [hit.path, hit.count]));
  const expectedMap = new Map(expected.map((hit) => [hit.path, hit.count]));
  const unexpected = [];
  const missing = [];
  const changed = [];
  for (const [path, count] of actualMap) {
    if (!expectedMap.has(path)) unexpected.push(path);
    else if (expectedMap.get(path) !== count) changed.push(`${path} count ${count} != ${expectedMap.get(path)}`);
  }
  for (const path of expectedMap.keys()) {
    if (!actualMap.has(path)) missing.push(path);
  }
  return { unexpected, missing, changed };
}

export const OPTICS_INTENTIONAL_LEFTOVER_PATHS = [
  "docs/products/optics/AI-GUIDE.md",
  "docs/products/optics/CHANGELOG-GUIDE.md",
  "docs/products/optics/KNOWN-LIMITATIONS.md",
  "docs/products/optics/PYTHON-GUIDE.md",
  "docs/products/optics/README.md",
  "docs/products/optics/RECORD-REFERENCE.md",
  "docs/products/optics/USER-MANUAL.md",
  "docs/products/optics/llms-full.txt",
  "docs/products/optics/llms.txt",
];

export const UNIT_A_RECORD_VOCABULARY_PATH =
  "packages/optics-record-vocabulary/vocabulary/record-vocabulary.json";

export function legacyDebtHitsForTree(root, hits) {
  return hits.filter((hit) => {
    if (hit.path !== UNIT_A_RECORD_VOCABULARY_PATH) return true;
    return existsSync(join(root, hit.path));
  });
}

export function diffLegacyInventory(actual, debtHits, leftoverHits) {
  const problems = [];
  const leftoverSet = new Set(leftoverHits.map((hit) => hit.path));
  for (const hit of debtHits) {
    if (leftoverSet.has(hit.path)) problems.push(`path is both debt and intentional leftover: ${hit.path}`);
  }
  const debtActual = actual.filter((hit) => !leftoverSet.has(hit.path));
  const leftActual = actual.filter((hit) => leftoverSet.has(hit.path));
  const debtDiff = diffHitLists(debtActual, debtHits);
  const leftDiff = diffHitLists(leftActual, leftoverHits);
  if (debtDiff.unexpected.length) problems.push(`new stale-name files: ${debtDiff.unexpected.join(", ")}`);
  if (debtDiff.missing.length) problems.push(`stale-name files no longer present: ${debtDiff.missing.join(", ")}`);
  if (debtDiff.changed.length) problems.push(`stale-name counts changed: ${debtDiff.changed.join(", ")}`);
  if (leftDiff.unexpected.length) problems.push(`new intentional leftover files: ${leftDiff.unexpected.join(", ")}`);
  if (leftDiff.missing.length) problems.push(`intentional leftover files no longer present: ${leftDiff.missing.join(", ")}`);
  if (leftDiff.changed.length) problems.push(`intentional leftover counts changed: ${leftDiff.changed.join(", ")}`);
  return problems;
}

export function opticsLeftoverRuleProblems(legacy, readPath) {
  const problems = [];
  const rule = legacy?.intentional_leftovers;
  if (!rule || typeof rule.rule !== "string") return "intentional leftover rule is missing";
  if (!rule.rule.includes("Vantio Optics")) problems.push("intentional leftover rule does not name Vantio Optics");
  if (!rule.rule.includes("leftover")) problems.push("intentional leftover rule does not say leftover");
  if (!rule.rule.includes("PR #64")) problems.push("intentional leftover rule does not keep PR #64 visible");
  if (!rule.rule.includes("d7299a35be0d9a70ec306ca672aa1359e09f1515")) {
    problems.push("intentional leftover rule does not pin the Optics manual commit");
  }
  if (!rule.rule.includes("not new debt")) problems.push("intentional leftover rule does not say these are not new debt");
  for (const rel of OPTICS_INTENTIONAL_LEFTOVER_PATHS) {
    if (!rule.rule.includes(rel)) problems.push(`intentional leftover rule does not name ${rel}`);
  }
  const hits = rule.hits || [];
  const diff = setDiff(OPTICS_INTENTIONAL_LEFTOVER_PATHS, hits.map((hit) => hit.path));
  if (diff.missing.length || diff.unexpected.length) {
    problems.push(
      `intentional leftover paths drifted; missing [${diff.missing.join(", ")}] unexpected [${diff.unexpected.join(", ")}]`,
    );
  }
  for (const hit of hits) {
    if (!hit.disclaimer) {
      problems.push(`${hit.path} intentional leftover has no disclaimer`);
      continue;
    }
    if (!readPath) continue;
    const body = readPath(hit.path);
    if (!body.includes(hit.disclaimer)) problems.push(`${hit.path} missing leftover disclaimer`);
    const namesProduct = body.includes("Vantio Optics")
      || body.includes("not the product name")
      || body.includes("Not the product name")
      || body.includes("not current product terminology")
      || body.includes("Do not use Sight Loop as the product name");
    if (!namesProduct) problems.push(`${hit.path} does not keep the product-name instruction`);
    if (!body.includes("sight_loop") && !body.includes("Sight Loop")) {
      problems.push(`${hit.path} does not name the leftover string`);
    }
  }
  return problems.join("; ");
}

export const COLLISION_TEST_INVENTORY_PATH = "tests/shared-health-vocabulary/collision.test.cjs";

function prefixHidesPath(rel, prefix) {
  const normalized = prefix.replace(/\/$/, "");
  return rel === normalized || rel.startsWith(prefix);
}

export function collisionTestInventoryProblems({ manifest, legacy, liveHits }) {
  const problems = [];
  const rel = COLLISION_TEST_INVENTORY_PATH;
  const updates = Array.isArray(legacy?.reviewed_updates) ? legacy.reviewed_updates : [];
  const matches = updates.filter((item) => item && item.path === rel);
  if (matches.length !== 1) {
    problems.push(`collision test reviewed_updates count ${matches.length} != 1`);
  }
  const review = matches[0];
  if (review && review.disposition !== "FROZEN_DEBT") {
    problems.push(`collision test disposition ${review.disposition} is not FROZEN_DEBT`);
  }
  if (review && (typeof review.reason !== "string" || review.reason.trim() === "")) {
    problems.push("collision test review has no reason");
  }
  const hit = (legacy?.hits || []).find((item) => item.path === rel);
  if (!hit) problems.push("collision test is missing from hits");
  if (hit && review && hit.count !== review.count) {
    problems.push(`collision test hits count ${hit.count} != reviewed count ${review.count}`);
  }
  const leftovers = legacy?.intentional_leftovers?.hits || [];
  if (leftovers.some((item) => item.path === rel)) {
    problems.push("collision test is an intentional leftover");
  }
  const prefixes = manifest?.legacy_scan?.exclude_prefixes || [];
  for (const prefix of prefixes) {
    if (prefixHidesPath(rel, prefix)) problems.push(`collision test hidden by exclude prefix ${prefix}`);
  }
  const live = (liveHits || []).find((item) => item.path === rel);
  if (!live) problems.push("legacy scan does not see the collision test");
  else if (hit && live.count !== hit.count) {
    problems.push(`collision test live count ${live.count} != hits count ${hit.count}`);
  }
  return problems.join("; ");
}

function staleProblems(root, canonicalDocs, patterns) {
  const problems = [];
  for (const rel of canonicalDocs) {
    const count = countPatterns(readText(root, rel), patterns);
    if (count > 0) problems.push(`${rel} contains ${count} stale-name match(es)`);
  }
  return problems.join("; ");
}

function record(checks, id, detail) {
  checks.push({ id, ok: detail === "", detail });
}

export function checkRelease(root) {
  const checks = [];
  const schema = readJson(root, "docs/governance/schema/documentation-release.schema.json");
  const manifest = readJson(root, "docs/governance/MANIFEST.json");
  record(checks, "manifest-schema", checkManifestShape(manifest, schema));

  const versions = readJson(root, manifest.version_metadata);
  const boundary = readJson(root, manifest.product_boundary);
  const exportsSpec = readJson(root, manifest.public_exports);
  const envSpec = readJson(root, manifest.env_vars);
  const statusSpec = readJson(root, manifest.status_tokens);
  const pathsSpec = readJson(root, manifest.supported_paths);
  const hostsSpec = readJson(root, manifest.llm_hosts);
  const staleSpec = readJson(root, manifest.stale_names);
  const roadmapSpec = readJson(root, manifest.roadmap_not_current);
  const packaging = readJson(root, manifest.packaging_exclusion);
  const bundleSpec = readJson(root, manifest.pe_customer_bundle);
  const limitations = readJson(root, manifest.known_limitations);
  const legacy = readJson(root, manifest.legacy_stale_names);

  record(checks, "package-version-matches-metadata", packageVersionProblems(root, versions.packages));
  record(
    checks,
    "readme-matches-product-boundary",
    readmeBoundaryProblems(readText(root, boundary.readme), boundary),
  );
  record(checks, "public-exports-documented", publicExportProblems(root, exportsSpec));
  record(checks, "removed-exports-not-current", (() => {
    const problems = [];
    for (const rel of manifest.canonical_docs) {
      const hits = removedExportViolations(readText(root, rel), exportsSpec.removed, exportsSpec.historical_heading);
      if (hits.length) problems.push(`${rel}: ${hits.join(", ")}`);
    }
    return problems.join("; ");
  })());
  record(checks, "examples-execute", examplesProblems(root, manifest.examples));
  record(checks, "env-vars-documented", envVarProblems(root, envSpec));
  record(checks, "status-tokens-documented", statusTokenProblems(root, statusSpec));
  record(checks, "supported-paths-match-catalogs", [
    supportedPathProblems(root, pathsSpec),
    hostCatalogProblems(root, hostsSpec),
  ].filter(Boolean).join("; "));
  record(
    checks,
    "known-limitations-exist",
    knownLimitationProblems(readText(root, limitations.doc), limitations.required_phrases),
  );
  record(checks, "changelog-entry-exists", changelogProblems(root, versions.packages));
  record(checks, "ai-guide-version-matches", aiGuideProblems(readText(root, manifest.ai_guide), versions.packages));
  record(checks, "llms-txt-canonical-only", (() => {
    const problems = [];
    const listed = parseLlmsPaths(readText(root, manifest.llms_txt));
    problems.push(llmsTxtProblems(readText(root, manifest.llms_txt), manifest.canonical_docs));
    for (const rel of listed) {
      if (!existsSync(join(root, rel))) problems.push(`missing canonical file ${rel}`);
    }
    return problems.filter(Boolean).join("; ");
  })());
  record(checks, "llms-full-regenerable", (() => {
    const rendered = renderLlmsFull(root, manifest.canonical_docs);
    const committed = readText(root, manifest.llms_full_txt);
    return rendered === committed ? "" : "llms-full.txt does not match regeneration from canonical docs";
  })());

  const packLists = [];
  const packProblems = [];
  for (const pkg of packaging.public_packages) {
    const dir = join(root, pkg.path);
    if (pkg.kind === "npm") {
      const paths = npmPackPaths(dir);
      packLists.push({ id: pkg.id, paths });
      const hits = denialHits(paths, packaging.path_denies);
      if (hits.length) packProblems.push(`${pkg.id}: ${hits.join(", ")}`);
    } else if (pkg.kind === "python") {
      const candidates = pythonCandidatePaths(dir);
      if (!sameSet(candidates.packages, pkg.wheel_packages)) {
        packProblems.push(`${pkg.id} wheel packages [${candidates.packages.join(", ")}] != [${pkg.wheel_packages.join(", ")}]`);
      }
      packLists.push({ id: `${pkg.id}-wheel`, paths: candidates.wheel });
      packLists.push({ id: `${pkg.id}-sdist`, paths: candidates.sdist });
      const hits = denialHits([...candidates.wheel, ...candidates.sdist], packaging.path_denies);
      if (hits.length) packProblems.push(`${pkg.id}: ${hits.join(", ")}`);
    } else {
      packProblems.push(`${pkg.id} unknown kind ${pkg.kind}`);
    }
  }
  const customerDenies = ["CUSTOMER-MANUAL", "PRIVATE-MANUAL", "phantom-engine/customer/", "pe-customer/"];
  const customerHits = [];
  for (const pack of packLists) {
    const hits = denialHits(pack.paths, customerDenies);
    if (hits.length) customerHits.push(`${pack.id}: ${hits.join(", ")}`);
  }
  record(checks, "public-artifacts-exclude-pe-customer-docs", customerHits.join("; "));
  record(checks, "public-packages-exclude-internal-docs", packProblems.join("; "));
  record(checks, "private-packages-stay-private", (() => {
    const problems = [];
    for (const pkg of packaging.private_packages) {
      const meta = readJson(root, join(pkg.path, "package.json"));
      if (pkg.require_private && meta.private !== true) problems.push(`${pkg.id} is not private`);
    }
    return problems.join("; ");
  })());
  record(checks, "pe-customer-bundle-includes-matching-manual", (() => {
    if (bundleSpec.public_distribution !== false) return "PE customer bundle design is marked public";
    for (const role of ["manifest", "private-manual"]) {
      if (!bundleSpec.required_roles.includes(role)) return `bundle design missing role ${role}`;
    }
    for (const pkg of packaging.public_packages) {
      if (bundleSpec.fixture.startsWith(`${pkg.path}/`)) return `fixture lives inside public package ${pkg.id}`;
    }
    const assembled = assemblePeCustomerBundle({
      version: bundleSpec.fixture_version,
      manualText: readText(root, bundleSpec.fixture),
    });
    if (!assembled.ok) return assembled.error;
    if (assembled.bundle.public_distribution !== false) return "assembled bundle is public";
    const roles = assembled.bundle.members.map((member) => member.role);
    if (!roles.includes("private-manual") || !roles.includes("manifest")) return "assembled bundle missing required roles";
    if (assembled.bundle.version !== bundleSpec.fixture_version) return "assembled bundle version drifted";
    return "";
  })());
  record(checks, "stale-product-names-rejected", staleProblems(root, manifest.canonical_docs, staleSpec.patterns));
  record(checks, "roadmap-features-not-current", (() => {
    const problems = [];
    for (const rel of manifest.canonical_docs) {
      const hits = roadmapViolations(readText(root, rel), roadmapSpec.features);
      if (hits.length) problems.push(`${rel}: ${hits.join(" | ")}`);
    }
    return problems.join("; ");
  })());
  const legacyActual = collectLegacyHits(root, manifest.legacy_scan, staleSpec.patterns);
  record(checks, "legacy-stale-name-inventory-frozen", (() => {
    const leftoverHits = legacy.intentional_leftovers?.hits || [];
    const problems = [
      ...diffLegacyInventory(legacyActual, legacyDebtHitsForTree(root, legacy.hits), leftoverHits),
      opticsLeftoverRuleProblems(legacy, (rel) => readText(root, rel)),
    ];
    for (const rel of manifest.canonical_docs) {
      if (legacy.hits.some((hit) => hit.path === rel)) problems.push(`canonical doc is listed as legacy debt: ${rel}`);
      if (leftoverHits.some((hit) => hit.path === rel)) problems.push(`canonical doc is listed as an intentional leftover: ${rel}`);
    }
    return problems.filter(Boolean).join("; ");
  })());
  record(checks, "collision-test-inventory-reviewed", collisionTestInventoryProblems({
    manifest,
    legacy,
    liveHits: legacyActual,
  }));

  const failures = checks.filter((check) => !check.ok);
  return { ok: failures.length === 0, checks, failures };
}
