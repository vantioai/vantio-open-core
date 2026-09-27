"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");

const api = require("../../packages/vantio-cli-pkg02/src/index.cjs");
const { composeCanonical } = require("../../packages/vantio-cli-pkg02/src/record.cjs");
const support = require("./support.cjs");

test("proof order is adapter byte identity, then unknown status, then a future write", () => {
  const home = support.homeDir("unit-d-order-");
  try {
    const frozen = support.runFrozen(home, ["run", "node", "-e", "process.exit(0)"]);
    assert.equal(frozen.status, 0, frozen.stderr || frozen.stdout);
    const file = support.runFiles(home)[0];
    const before = fs.readFileSync(file);
    assert.equal(api.proveAdapterByteIdentity(file), true);
    assert.equal(fs.readFileSync(file).equals(before), true);

    const unknown = api.proveUnknownOpticsNotSuccess();
    assert.equal(unknown.unknown_becomes_success, false);
    assert.equal(unknown.optimistic_default_forbidden, true);

    const written = composeCanonical({
      calls: [{
        action: "OBSERVED",
        hostname: "api.openai.com",
        method: "GET",
        path: "/v1/responses",
        scheme: "https",
        status: 200,
      }],
      cli_version: "0.3.24",
      platform: "linux",
      schema_version: 2,
      trace_id: "0xordered",
      vantio_run_log: "1",
    }, [{ lengthPresent: true, mediation: "node_fetch", responseBytes: 8 }], {});
    assert.equal(written.record_emitted, true);
    assert.equal(written.document.cli_or_sdk_version, api.FUTURE_CLI_VERSION);
    assert.equal(written.document.events[0].optics_status, "OBSERVED");
    assert.equal(written.document.events[0].response_bytes, 8);
    assert.notEqual(written.document.cli_or_sdk_version, "0.3.24");
    support.assertNoOpticsSuccess(assert, written.document);
    assert.equal(fs.readFileSync(file).equals(before), true);
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
});
