import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

import { MAX_FRAME } from "../src/bounds.js";
import { COPY_LIMIT, HEADER_BYTES, classifyCopy } from "../src/hostCopy.js";

test("the copy cap is far below the parser frame cap", () => {
  assert.equal(MAX_FRAME, 256 * 1024);
  assert.ok(COPY_LIMIT < MAX_FRAME);
  assert.equal(COPY_LIMIT, 4096);
  assert.equal(HEADER_BYTES, 32);
});

test("a short complete buffer may be parsed and is not an allow", () => {
  const row = classifyCopy({ registered: true, ciphertext: false, copiedBytes: 120, frameLength: 120 });
  assert.equal(row.capture, "complete");
  assert.equal(row.decision, "HAND_TO_PARSER");
  assert.equal(row.parse, true);
  assert.notEqual(row.decision, "ALLOW");
  assert.equal(row.host_attach, "Roadmap");
  assert.equal(row.label, "Lab-only");
});

test("a frame longer than the copy, or a short copy, is a gap", () => {
  const over = classifyCopy({ registered: true, copiedBytes: 4096, frameLength: 4097 });
  const short = classifyCopy({ registered: true, copiedBytes: 10, frameLength: 40 });
  const empty = classifyCopy({ registered: true, copiedBytes: 0, frameLength: 0 });
  const huge = classifyCopy({ registered: true, copiedBytes: 4097, frameLength: 4097 });
  for (const row of [over, short, empty, huge]) {
    assert.equal(row.capture, "truncated_capture");
    assert.equal(row.decision, "GAP");
    assert.equal(row.parse, false);
  }
});

test("ciphertext and an unregistered descriptor are not parsed", () => {
  const hidden = classifyCopy({ registered: true, ciphertext: true, copiedBytes: 20, frameLength: 20 });
  const missing = classifyCopy({ registered: false, ciphertext: false, copiedBytes: 20, frameLength: 20 });
  assert.equal(hidden.capture, "ciphertext");
  assert.equal(missing.capture, "unregistered_fd");
  assert.equal(hidden.parse, false);
  assert.equal(missing.parse, false);
});

test("the package entry does not export the host-copy helper", () => {
  const entry = fs.readFileSync(new URL("../src/index.js", import.meta.url), "utf8");
  const source = fs.readFileSync(new URL("../src/hostCopy.js", import.meta.url), "utf8");
  assert.equal(entry.includes("hostCopy"), false);
  assert.equal(entry.includes("classifyCopy"), false);
  assert.equal(source.includes("ALLOW"), false);
  for (const token of ["node:net", "node:child_process", "node:http"]) {
    assert.equal(source.includes(token), false);
  }
});
