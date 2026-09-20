import { test } from "node:test";
import assert from "node:assert/strict";
import { createOpticsMcpServer } from "../src/server.js";

// Helpers
function getRegisteredTool(server, name) {
  return server._registeredTools[name];
}

async function callTool(server, name, args = {}) {
  const t = getRegisteredTool(server, name);
  assert.ok(t, `Tool '${name}' not registered`);
  const result = await t.handler(args);
  return JSON.parse(result.content[0].text);
}

test("optics_list_runs upgrade field names Phantom Engine, not Gate", async () => {
  const server = createOpticsMcpServer();
  const body = await callTool(server, "optics_list_runs");
  assert.ok(typeof body.upgrade === "string", "upgrade field must be a string");
  assert.match(body.upgrade, /Phantom Engine/, "upgrade must name Phantom Engine");
  assert.doesNotMatch(body.upgrade, /\bGate\b/i, "upgrade must not name Gate as product");
  assert.match(body.upgrade, /optics_upgrade_path/, "upgrade must reference optics_upgrade_path");
});

test("optics_explain does_not entry names Phantom Engine for enforcement, not Gate", async () => {
  const server = createOpticsMcpServer();
  const body = await callTool(server, "optics_explain");
  assert.ok(Array.isArray(body.does_not), "does_not must be an array");
  const enforceLine = body.does_not.find((s) => /block.*redact.*cap spend/i.test(s));
  assert.ok(enforceLine, "does_not must include block/redact/cap spend entry");
  assert.match(enforceLine, /Phantom Engine/, "enforcement does_not entry must name Phantom Engine");
  assert.doesNotMatch(enforceLine, /\bVantio Gate\b/i, "enforcement does_not entry must not name Vantio Gate");
});

test("optics_upgrade_path tool description names Phantom Engine and Vantio Enterprise, not Gate as tier", () => {
  const server = createOpticsMcpServer();
  const tool = getRegisteredTool(server, "optics_upgrade_path");
  const desc = tool.description;
  assert.ok(typeof desc === "string", "description must be a string");
  assert.match(desc, /Phantom Engine/, "description must mention Phantom Engine");
  assert.match(desc, /Vantio Enterprise|Enterprise/, "description must mention Enterprise");
  assert.doesNotMatch(desc, /→\s*Gate\b/i, "description must not present Gate as an upgrade ladder step");
});

test("optics_upgrade_path response body ladder is Optics → Phantom Engine → Enterprise", async () => {
  const server = createOpticsMcpServer();
  const body = await callTool(server, "optics_upgrade_path");
  assert.ok(Array.isArray(body.next), "UPGRADE_PATH.next must be an array");
  assert.equal(body.next[0].brand, "Vantio Phantom Engine", "first step must be Vantio Phantom Engine");
  assert.match(body.next[1].brand, /Enterprise/, "second step must be Enterprise");
  assert.doesNotMatch(JSON.stringify(body.next), /\bGate\b/i, "ladder steps must not include Gate");
});
