/**
 * Brand / compatibility-shell tests for @vantio/gate-mcp.
 *
 * Verifies:
 *   - human-readable metadata (title, description, websiteUrl) is Phantom Engine framing
 *   - no brand field returns "Vantio Gate" as a current product
 *   - gate_upgrade_path description is Optics → Phantom Engine → Enterprise (not Optics → Gate → …)
 *   - no Gate $499 / Gate Pro / hosted Gate / four-product ladder anywhere
 *   - package name preserved as @vantio/gate-mcp
 *   - version preserved as 0.1.0
 *   - all required tool names present
 *   - schema / evaluate behavior preserved
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, dirname } from "node:path";
import {
  UPGRADE_PATH,
  evaluateRequest,
  DEFAULT_POLICY,
} from "../src/policy.js";
import { createGateMcpServer } from "../src/server.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");

const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
const serverMeta = JSON.parse(readFileSync(join(root, "server.json"), "utf8"));
const serverSrc = readFileSync(join(root, "src", "server.js"), "utf8");
const policySrc = readFileSync(join(root, "src", "policy.js"), "utf8");
const binSrc = readFileSync(join(root, "bin", "vantio-gate-mcp.js"), "utf8");
const readme = readFileSync(join(root, "README.md"), "utf8");

// ── package.json metadata ──────────────────────────────────────────────────

test("package name preserved as @vantio/gate-mcp", () => {
  assert.equal(pkg.name, "@vantio/gate-mcp");
});

test("version preserved as 0.1.1", () => {
  assert.equal(pkg.version, "0.1.1");
});

test("package homepage points to /phantom not /gate", () => {
  assert.ok(
    pkg.homepage.includes("/phantom"),
    `homepage should point to /phantom, got: ${pkg.homepage}`,
  );
  assert.ok(
    !pkg.homepage.endsWith("/gate"),
    `homepage must not end at /gate, got: ${pkg.homepage}`,
  );
});

test("package description references legacy/compat and not Gate as standalone SKU", () => {
  const desc = pkg.description.toLowerCase();
  assert.ok(
    desc.includes("legacy") || desc.includes("compat"),
    `description should mention legacy or compat, got: ${pkg.description}`,
  );
  assert.ok(!desc.includes("gate $499"), "description must not mention Gate $499");
  assert.ok(!desc.includes("gate pro"), "description must not mention Gate Pro");
});

// ── server.json metadata ───────────────────────────────────────────────────

test("server.json title is Phantom Engine framing (not standalone Gate)", () => {
  const title = serverMeta.title.toLowerCase();
  assert.ok(
    title.includes("phantom"),
    `server.json title should mention Phantom Engine, got: ${serverMeta.title}`,
  );
});

test("server.json websiteUrl points to /phantom", () => {
  assert.ok(
    serverMeta.websiteUrl.includes("/phantom"),
    `websiteUrl should point to /phantom, got: ${serverMeta.websiteUrl}`,
  );
});

test("server.json description is Phantom Engine framing", () => {
  const desc = serverMeta.description.toLowerCase();
  assert.ok(
    desc.includes("phantom"),
    `server.json description should mention Phantom Engine, got: ${serverMeta.description}`,
  );
});

test("server.json registry name preserved as io.github.vantioai/vantio-gate", () => {
  assert.equal(serverMeta.name, "io.github.vantioai/vantio-gate");
});

test("server.json npm package identifier preserved as @vantio/gate-mcp", () => {
  const npmPkg = serverMeta.packages.find((p) => p.registryType === "npm");
  assert.ok(npmPkg, "server.json must have an npm package entry");
  assert.equal(npmPkg.identifier, "@vantio/gate-mcp");
});

// ── UPGRADE_PATH ───────────────────────────────────────────────────────────

test("UPGRADE_PATH has exactly three tiers: Optics, Phantom Engine, Enterprise", () => {
  assert.equal(UPGRADE_PATH.length, 3);
  const brands = UPGRADE_PATH.map((t) => t.brand.toLowerCase());
  assert.ok(brands[0].includes("optics"), `First tier must be Optics, got: ${UPGRADE_PATH[0].brand}`);
  assert.ok(brands[1].includes("phantom"), `Second tier must be Phantom Engine, got: ${UPGRADE_PATH[1].brand}`);
  assert.ok(brands[2].includes("enterprise"), `Third tier must be Enterprise, got: ${UPGRADE_PATH[2].brand}`);
});

test("UPGRADE_PATH has no standalone Gate tier", () => {
  for (const tier of UPGRADE_PATH) {
    assert.ok(
      !tier.brand.toLowerCase().match(/^vantio gate$/) &&
        !tier.brand.toLowerCase().match(/^gate$/),
      `UPGRADE_PATH must not contain a standalone Gate tier, found brand: "${tier.brand}"`,
    );
  }
});

// ── evaluateRequest brand fields ───────────────────────────────────────────

test("evaluateRequest brand field is not 'Vantio Gate'", () => {
  const r = evaluateRequest(DEFAULT_POLICY, { hostname: "api.openai.com" });
  assert.notEqual(r.brand, "Vantio Gate", "evaluateRequest must not return brand 'Vantio Gate'");
});

test("evaluateRequest with enforce=true brand is not 'Vantio Gate'", () => {
  const r = evaluateRequest(
    { ...DEFAULT_POLICY, enforce: true, blocked_hosts: ["evil.example"] },
    { hostname: "evil.example" },
  );
  assert.notEqual(r.brand, "Vantio Gate");
});

// ── No forbidden strings in source files ──────────────────────────────────

const SOURCES = [
  ["src/server.js", serverSrc],
  ["src/policy.js", policySrc],
  ["bin/vantio-gate-mcp.js", binSrc],
  ["README.md", readme],
];

const FORBIDDEN_PATTERNS = [
  ["Gate $499", /gate \$499/i],
  ["Gate Pro", /gate pro/i],
  ["hosted Gate", /hosted gate/i],
  ["Optics → Gate (four-product ladder)", /optics\s*[→\-]+\s*gate/i],
  ["Gate → Phantom (old ladder)", /gate\s*[→\-]+\s*phantom/i],
];

for (const [label, re] of FORBIDDEN_PATTERNS) {
  test(`no forbidden string "${label}" in any source file`, () => {
    for (const [filename, src] of SOURCES) {
      assert.ok(
        !re.test(src),
        `Forbidden string "${label}" found in ${filename}`,
      );
    }
  });
}

// ── vantio.ai/gate must not appear as the product homepage ────────────────

test("vantio.ai/gate is not used as product homepage in server.json", () => {
  assert.ok(
    !serverMeta.websiteUrl.endsWith("/gate"),
    `server.json websiteUrl must not point to /gate, got: ${serverMeta.websiteUrl}`,
  );
});

test("vantio.ai/gate is not used as package homepage", () => {
  assert.ok(
    !pkg.homepage.endsWith("/gate"),
    `package.json homepage must not point to /gate, got: ${pkg.homepage}`,
  );
});

// ── Tool names preserved in server.js ─────────────────────────────────────

const REQUIRED_TOOLS = [
  "gate_evaluate",
  "gate_get_policy",
  "gate_residual_risk",
  "gate_normalize_policy",
  "gate_explain",
  "gate_upgrade_path",
];

for (const toolName of REQUIRED_TOOLS) {
  test(`tool name "${toolName}" is declared in server.js`, () => {
    assert.ok(
      serverSrc.includes(`"${toolName}"`),
      `server.js must declare tool "${toolName}"`,
    );
  });
}

// ── gate_upgrade_path description ─────────────────────────────────────────

test("gate_upgrade_path description mentions Phantom Engine, not → Gate", () => {
  const match = serverSrc.match(/"gate_upgrade_path",\s*"([^"]+)"/);
  assert.ok(match, "gate_upgrade_path tool description not found in server.js");
  const desc = match[1].toLowerCase();
  assert.ok(
    desc.includes("phantom") || desc.includes("enterprise"),
    `gate_upgrade_path description should mention Phantom Engine or Enterprise, got: "${match[1]}"`,
  );
  assert.ok(
    !desc.match(/→\s*gate/),
    `gate_upgrade_path description must not say "→ gate", got: "${match[1]}"`,
  );
});

// ── createGateMcpServer export ─────────────────────────────────────────────

test("createGateMcpServer returns a server object", () => {
  const server = createGateMcpServer();
  assert.ok(server, "createGateMcpServer must return a non-null server");
});

// ── Schema / evaluate compatibility ───────────────────────────────────────

test("evaluate preserves plane=Enforce in output", () => {
  const r = evaluateRequest(DEFAULT_POLICY, { hostname: "x.example" });
  assert.equal(r.plane, "Enforce");
});

test("evaluate preserves primary_action OBSERVED when enforce=false", () => {
  const r = evaluateRequest({ ...DEFAULT_POLICY, enforce: false }, { hostname: "x.example" });
  assert.equal(r.primary_action, "OBSERVED");
  assert.equal(r.would_block, false);
});

test("evaluate preserves DRY_RUN_BLOCKED_HOST when enforce=true and host blocked", () => {
  const r = evaluateRequest(
    { ...DEFAULT_POLICY, enforce: true, blocked_hosts: ["blocked.example"] },
    { hostname: "blocked.example" },
  );
  assert.equal(r.would_block, true);
  assert.equal(r.primary_action, "DRY_RUN_BLOCKED_HOST");
});

test("evaluate preserves DRY_RUN_BLOCKED_SIZE when bytes exceed cap", () => {
  const r = evaluateRequest(
    { ...DEFAULT_POLICY, enforce: true, max_request_bytes: 100 },
    { hostname: "api.example.com", request_bytes: 200 },
  );
  assert.equal(r.would_block, true);
  assert.equal(r.primary_action, "DRY_RUN_BLOCKED_SIZE");
});
