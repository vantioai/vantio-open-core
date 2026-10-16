import assert from "node:assert/strict";
import test from "node:test";
import { pathPrefixMatch } from "../src/path-prefix.js";
import { createRuntimeWithKey } from "../src/test-key.js";

const KEY = Buffer.alloc(32, 7);

function line(value) {
  return `${JSON.stringify(value)}\n`;
}

function call(path, id = 1) {
  return { jsonrpc: "2.0", id, method: "tools/call", params: { name: "read_file", arguments: { path } } };
}

function decide(path, rules) {
  const runtime = createRuntimeWithKey(KEY);
  return runtime.observeBuffer(Buffer.from(line(call(path))), {
    transport: "stdio",
    direction: "client_to_server",
    serverId: "files",
    policy: {
      schema: "vantio.mcp_policy.v1",
      mode: "enforce",
      servers: {
        files: {
          default: "deny",
          tools: { read_file: { effect: "deny" } },
          argument_rules: rules,
        },
      },
    },
  }).records[0].decision;
}

const allowData = [{ id: "data", tool: "read_file", key: "path", op: "prefix", value: "/data/", effect: "allow" }];

test("prefix /data/ allows a path inside that directory", () => {
  assert.equal(decide("/data/notes.txt", allowData).action, "ALLOW");
  assert.equal(decide("/data/notes.txt", allowData).reason, "argument_rule");
});

test("/data/../etc/passwd is not under /data/", () => {
  const decision = decide("/data/../etc/passwd", allowData);
  assert.equal(decision.action, "BLOCK");
  assert.equal(pathPrefixMatch("/data/../etc/passwd", "/data/"), "miss");
});

test("/data/./../x is not under /data/", () => {
  assert.equal(decide("/data/./../x", allowData).action, "BLOCK");
  assert.equal(pathPrefixMatch("/data/./../x", "/data/"), "miss");
});

test("//data//../etc is not under /data/", () => {
  assert.equal(decide("//data//../etc", allowData).action, "BLOCK");
  assert.equal(pathPrefixMatch("//data//../etc", "/data/"), "miss");
});

test("encoded ..%2f is not under /data/ and a second encoding is rejected", () => {
  assert.equal(decide("/data/..%2fetc/passwd", allowData).action, "BLOCK");
  assert.equal(pathPrefixMatch("/data/..%2fetc/passwd", "/data/"), "miss");
  assert.equal(pathPrefixMatch("/data/%2e%2e%2fetc/passwd", "/data/"), "miss");
  assert.equal(decide("/data/%252e%252e%252fetc", allowData).action, "BLOCK");
  assert.equal(decide("/data/%252e%252e%252fetc", allowData).reason, "path_rejected");
});

test("a /data/ prefix does not match /database", () => {
  assert.equal(decide("/database", allowData).action, "BLOCK");
  assert.equal(decide("/database/notes", allowData).action, "BLOCK");
  assert.equal(pathPrefixMatch("/database", "/data/"), "miss");
  assert.equal(pathPrefixMatch("/database", "/data"), "miss");
});

test("trailing-slash variants stay on a segment boundary", () => {
  const allowBare = [{ id: "data", tool: "read_file", key: "path", op: "prefix", value: "/data", effect: "allow" }];
  assert.equal(decide("/data/notes.txt", allowBare).action, "ALLOW");
  assert.equal(decide("/data/", allowData).action, "ALLOW");
  assert.equal(decide("/data", allowData).action, "ALLOW");
  assert.equal(decide("/data/notes/", allowBare).action, "ALLOW");
  assert.equal(pathPrefixMatch("/data/", "/data"), "match");
  assert.equal(pathPrefixMatch("/database", "/data/"), "miss");
});

test("a path that escapes root or contains NUL fails closed", () => {
  const allowRoot = [{ id: "root", tool: "read_file", key: "path", op: "prefix", value: "/", effect: "allow" }];
  assert.equal(decide("/data/../../etc/passwd", allowRoot).action, "BLOCK");
  assert.equal(decide("/data/../../etc/passwd", allowRoot).reason, "path_rejected");
  assert.equal(decide("/data/ok\0/etc", allowRoot).reason, "path_rejected");
  assert.equal(decide("/data/%00/etc", allowRoot).reason, "path_rejected");
});
