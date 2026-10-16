import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const TRACKS = [
  ["T6", "docs/gap-program/T6-identity-interop.md", "Roadmap"],
  ["T7", "docs/gap-program/T7-credential-keep-out.md", "Roadmap"],
  ["T8", "docs/gap-program/T8-ocsf-otlp-siem.md", "Roadmap"],
  ["T9", "docs/gap-program/T9-owasp-agentic-matrix.md", "Roadmap"],
  ["T10", "docs/gap-program/T10-live-human-approval.md", "Roadmap"],
  ["T11", "docs/gap-program/T11-coding-agent-supply-chain.md", "Roadmap"],
  ["T12", "docs/gap-program/T12-policy-preview.md", "Roadmap"],
  ["T13", "docs/gap-program/T13-fedramp-fips-gap.md", "Roadmap"],
  ["T14", "docs/gap-program/T14-eu-ai-act-evidence-outline.md", "Roadmap"],
];

const SECTIONS = [
  "## Threat model",
  "## Failure modes",
  "## Edge cases",
  "## Memory footprint",
  "## eBPF verifier limits",
  "## Dependencies on T0–T5",
  "## Rollback",
  "## Approval gates",
  "## Risks",
  "## Council",
];

const CELL = /^(Verified|Lab-only|Roadmap|Not addressed)$/;

const FORBIDDEN = [
  { name: "unbreakable", re: /unbreakable/i },
  { name: "audited", re: /audited/i },
  { name: "unbypassable", re: /unbypassable/i },
  { name: "price", re: /\$\s?\d/ },
  { name: "retired-499", re: /\b499\b/ },
  { name: "retired-799", re: /\b799\b/ },
];

function read(repoRoot, rel) {
  return readFileSync(path.join(repoRoot, rel), "utf8");
}

function sha256(text) {
  return createHash("sha256").update(text).digest("hex");
}

function headSha(repoRoot) {
  try {
    return execFileSync("git", ["rev-parse", "HEAD"], {
      cwd: repoRoot,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return "UNCOMMITTED";
  }
}

function matrixCounts(text) {
  const counts = { Verified: 0, "Lab-only": 0, Roadmap: 0, "Not addressed": 0 };
  for (const line of text.split("\n")) {
    if (!line.startsWith("| ASI")) continue;
    const cells = line.split("|").map((part) => part.trim()).filter(Boolean);
    const marks = cells.slice(1);
    if (marks.length !== 4) {
      throw new Error(`ASI row does not have 4 marks: ${line}`);
    }
    for (const mark of marks) {
      if (!CELL.test(mark)) {
        throw new Error(`bad cell mark ${mark}`);
      }
      counts[mark] += 1;
    }
  }
  return counts;
}

export function checkDesign(repoRoot) {
  const errors = [];
  const files = [];

  for (const [id, rel, label] of TRACKS) {
    let text;
    try {
      text = read(repoRoot, rel);
    } catch {
      errors.push(`${id} missing ${rel}`);
      continue;
    }
    if (!text.includes(`Track label: ${label}`)) {
      errors.push(`${id} label is not ${label}`);
    }
    for (const section of SECTIONS) {
      if (!text.includes(section)) errors.push(`${id} missing ${section}`);
    }
    for (const rule of FORBIDDEN) {
      if (rule.re.test(text)) errors.push(`${id} contains forbidden ${rule.name}`);
    }
    files.push({ path: rel, sha256: sha256(text) });
  }

  let t8 = "";
  let t9 = "";
  let t13 = "";
  let t14 = "";
  try {
    t8 = read(repoRoot, "docs/gap-program/T8-ocsf-otlp-siem.md");
    t9 = read(repoRoot, "docs/gap-program/T9-owasp-agentic-matrix.md");
    t13 = read(repoRoot, "docs/gap-program/T13-fedramp-fips-gap.md");
    t14 = read(repoRoot, "docs/gap-program/T14-eu-ai-act-evidence-outline.md");
  } catch {
    errors.push("required track text missing");
  }

  if (t8 && !t8.includes("ef3a33a")) errors.push("T8 does not cite the inherited observability head");
  if (t8 && !t8.includes("product_otlp_export_authorized")) {
    errors.push("T8 does not keep the OTLP authorization flag");
  }
  if (t8 && !t8.includes("MUTABLE_LOCAL_LEDGER")) errors.push("T8 missing WORM failure token");

  if (t9) {
    try {
      const counts = matrixCounts(t9);
      if (counts.Verified !== 0) errors.push("T9 marks a cell Verified");
      if (counts["Lab-only"] !== 0) errors.push("T9 marks a cell Lab-only");
      const total = Object.values(counts).reduce((sum, n) => sum + n, 0);
      if (total !== 40) errors.push(`T9 cell count ${total} is not 40`);
    } catch (err) {
      errors.push(`T9 matrix: ${err.message}`);
    }
  }

  if (t13 && !t13.includes("GAP")) errors.push("T13 has no GAP row");
  if (t13 && /FedRAMP authorized/i.test(t13)) errors.push("T13 claims FedRAMP authorization");
  if (t14 && !t14.includes("2 December 2027")) errors.push("T14 missing the program date");
  if (t14 && !t14.includes("2 August 2028")) errors.push("T14 collapses the application dates");
  if (t14 && /fulfills the regulation/i.test(t14) && !/fulfills the regulation/.test(t14)) {
    errors.push("T14 conformity sentence");
  }

  const evidence = {
    generated_at_utc: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
    phase: 1,
    feature_code: false,
    base_note: "design packet checker",
    head_sha: headSha(repoRoot),
    track_label: "Roadmap",
    inherited_observability_head: "ef3a33a",
    product_otlp_export_authorized: false,
    files,
    ok: errors.length === 0,
    errors,
  };

  return evidence;
}

function main() {
  const repoRoot = process.cwd();
  const evidence = checkDesign(repoRoot);
  const outDir = path.join(repoRoot, "evidence", "gap-program");
  mkdirSync(outDir, { recursive: true });
  const outPath = path.join(outDir, "T6-T14-P1.json");
  writeFileSync(outPath, `${JSON.stringify(evidence, null, 2)}\n`);
  if (!evidence.ok) {
    console.error(evidence.errors.join("\n"));
    process.exit(1);
  }
  console.log(`wrote ${outPath}`);
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  main();
}
