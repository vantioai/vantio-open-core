/**
 * gate_explain URL-field compatibility tests.
 * Ensures `phantom` (current) and `gate` (legacy alias) both point at Phantom Engine.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join, dirname } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const serverSrc = readFileSync(join(root, "src", "server.js"), "utf8");
const readme = readFileSync(join(root, "README.md"), "utf8");

test("gate_explain includes phantom URL field pointing to /phantom", () => {
  assert.ok(
    /phantom:\s*"https:\/\/vantio\.ai\/phantom"/.test(serverSrc),
    'gate_explain must include phantom: "https://vantio.ai/phantom"',
  );
});

test("gate_explain retains gate as legacy alias to same Phantom Engine URL", () => {
  assert.ok(
    /gate:\s*"https:\/\/vantio\.ai\/phantom"/.test(serverSrc),
    'gate_explain must retain gate: "https://vantio.ai/phantom" as legacy compatibility alias',
  );
});

test("gate_explain brand remains Phantom Engine (not Gate SKU)", () => {
  const block = serverSrc.match(/"gate_explain"[\s\S]*?async \(\) =>\s*text\(\{([\s\S]*?)\}\)/);
  assert.ok(block, "gate_explain handler block not found");
  const body = block[1];
  assert.ok(
    /brand:\s*"Phantom Engine"/.test(body),
    `gate_explain brand must be Phantom Engine, block: ${body.slice(0, 200)}`,
  );
  assert.ok(!/brand:\s*"Vantio Gate"/.test(body), "gate_explain must not brand as Vantio Gate");
  assert.ok(!/gate \$499/i.test(body), "gate_explain must not mention Gate $499");
});

test("README documents gate as legacy compatibility alias", () => {
  assert.ok(
    /legacy compatibility alias/i.test(readme),
    "README should document gate as legacy compatibility alias",
  );
  assert.ok(!/gate \$499/i.test(readme), "README must not market Gate $499");
});
