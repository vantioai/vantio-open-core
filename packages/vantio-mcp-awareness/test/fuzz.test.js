import assert from "node:assert/strict";
import test from "node:test";
import { MAX_FRAME, ACTIONS } from "../src/bounds.js";
import { createFramer, parseJson } from "../src/parse.js";
import { createRuntimeWithKey } from "../src/test-key.js";

const CANARY = "CANARY_SECRET_t4_9f3a";
const SEED = 0x54440004;
const ITERATIONS = 2000;

function mulberry32(seed) {
  let a = seed >>> 0;
  return function next() {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function stringsOf(value) {
  const out = [];
  const walk = (node) => {
    if (typeof node === "string") out.push(node);
    else if (Array.isArray(node)) node.forEach(walk);
    else if (node && typeof node === "object") Object.values(node).forEach(walk);
  };
  walk(value);
  return out;
}

function mutate(rand, buffer) {
  const copy = Buffer.from(buffer);
  const roll = rand();
  if (copy.length === 0) return Buffer.from("{");
  if (roll < 0.2) {
    const at = Math.floor(rand() * copy.length);
    copy[at] ^= 1 + Math.floor(rand() * 255);
    return copy;
  }
  if (roll < 0.35) return copy.subarray(0, Math.floor(rand() * copy.length));
  if (roll < 0.5) {
    const extra = Buffer.from(CANARY);
    return Buffer.concat([copy, extra]);
  }
  if (roll < 0.65) return Buffer.concat([copy, copy]);
  if (roll < 0.8) return Buffer.from(`{"a":${"{".repeat(40)}${"}".repeat(40)}}`);
  return Buffer.concat([Buffer.from([0xff, 0xfe]), copy]);
}

test("parser and observe path survive a deterministic fuzz corpus", () => {
  const rand = mulberry32(SEED);
  const runtime = createRuntimeWithKey(Buffer.alloc(32, 4));
  const seeds = [
    Buffer.from('{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"read_file","arguments":{"path":"/data/a"}}}\n'),
    Buffer.from(`{"jsonrpc":"2.0","id":"x","method":"tools/list","params":{}}\n`),
    Buffer.from(`event: message\ndata: {"jsonrpc":"2.0","method":"ping","id":1}\n\n`),
    Buffer.from("POST /mcp HTTP/1.1\r\nContent-Type: application/json\r\nContent-Length: 2\r\n\r\n{}"),
    Buffer.from(`Content-Length: 2\r\n\r\n{}`),
  ];
  for (let i = 0; i < ITERATIONS; i += 1) {
    const seed = seeds[Math.floor(rand() * seeds.length)];
    const chunk = mutate(rand, seed);
    const transport = ["stdio", "sse", "http"][Math.floor(rand() * 3)];
    const framer = createFramer(transport);
    let frames = [];
    assert.doesNotThrow(() => {
      frames = [...framer.push(chunk), ...framer.finish()];
    });
    assert.ok(framer.buffered() <= MAX_FRAME);
    for (const frame of frames) {
      assert.ok(["json", "ignore", "oversize", "invalid_utf8", "malformed_frame"].includes(frame.kind));
      if (frame.kind === "json" && typeof frame.text === "string") {
        let parsed;
        assert.doesNotThrow(() => {
          parsed = parseJson(frame.text);
        });
        assert.equal(typeof parsed.ok, "boolean");
      }
    }
    const observed = runtime.observeBuffer(chunk, {
      transport,
      direction: i % 2 === 0 ? "client_to_server" : "server_to_client",
      serverId: "files",
      policy: {
        mode: i % 5 === 0 ? "enforce" : "observe",
        servers: {
          files: {
            default: "deny",
            class_defaults: { read: "allow", write: "deny" },
            tools: { read_file: { class: "read" }, write_file: { class: "write" } },
          },
        },
      },
    });
    for (const record of observed.records) {
      assert.ok(ACTIONS.includes(record.decision.action));
      assert.equal(record.retention.payload, false);
      assert.equal(stringsOf(record).some((item) => item.includes(CANARY)), false);
    }
    assert.equal(stringsOf(observed.session).some((item) => item.includes(CANARY)), false);
  }
});
