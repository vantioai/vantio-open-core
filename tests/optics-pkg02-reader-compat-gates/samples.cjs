"use strict";

const fs = require("node:fs");
const path = require("node:path");

const CANARY = "sk-PKG02GATECANARY01";
const ABSENT_NAME = "absent-run.json";

const FILES = Object.freeze([
  ["legacy_cli", "legacy-cli.json"],
  ["legacy_python", "legacy-python.json"],
  ["future_canonical", "future-canonical.json"],
  ["unknown_status", "unknown-status.json"],
  ["absent_fields", "absent-fields.json"],
  ["imported", "imported.json"],
  ["claimed_local", "claimed-local.json"],
  ["simulated_demo", "simulated-demo.json"],
  ["newer_schema", "newer-schema.json"],
  ["corrupt", "corrupt.json"],
  ["node_sdk", "node-sdk.json"],
  ["future_field", "future-field.json"],
]);

function futureRecord() {
  return {
    action: "OBSERVED",
    evidence_origin: "LOCAL_OBSERVATION",
    http_status: 200,
    optics_status: "OBSERVED",
    producer: "node_interceptor",
    producer_version: "PKG02-FUTURE-CLI-UNASSIGNED",
    record_type: "observation_event",
    schema_status: "unstable-pre-1.0",
    schema_version: 0,
  };
}

function syntheticLegacyCli() {
  return {
    calls: [
      {
        action: "OBSERVED",
        bytes: 12,
        hostname: "api.example.com",
        status: 200,
      },
    ],
    cli_version: "0.3.24",
    schema_version: 2,
    trace_id: "0xabc",
    vantio_run_log: "1",
  };
}

function syntheticLegacyPython() {
  return {
    calls: [
      {
        applicationStatus: "SUCCESS",
        hostname: "api.example.com",
        opticsStatus: "SUCCESS",
        status: 200,
      },
    ],
    runtime: "python",
    schema_version: 2,
    vantio_run_log: "1",
  };
}

function bodies() {
  return {
    absent_fields: {
      destination_host: "api.example.com",
      producer: "node_interceptor",
      producer_version: "PKG02-FUTURE-CLI-UNASSIGNED",
      record_type: "observation_event",
    },
    claimed_local: {
      calls: [
        {
          hostname: "api.example.com",
          status: 200,
        },
      ],
      cli_version: "0.3.24",
      evidence_origin: "LOCAL_OBSERVATION",
      record_type: "run_envelope",
      schema_version: 2,
      vantio_run_log: "1",
    },
    corrupt: Buffer.from("{"),
    future_canonical: futureRecord(),
    future_field: {
      calls: [
        {
          hostname: "api.example.com",
          prompt: CANARY,
          status: 200,
        },
      ],
      cli_version: "0.3.24",
      cost: 1,
      est_spend_usd: 1,
      freshness: "CURRENT",
      prompt: CANARY,
      schema_version: 2,
      vantio_run_log: "1",
      widget_hint: "later",
    },
    imported: {
      calls: [
        {
          hostname: "api.example.com",
          status: 204,
        },
      ],
      evidence_origin: "IMPORTED",
      original_evidence_origin: "LEGACY_UNMARKED",
      producer: "node_interceptor",
      producer_version: "0.3.24",
      record_type: "run_envelope",
      schema_status: "unstable-pre-1.0",
      schema_version: 2,
      vantio_run_log: "1",
    },
    legacy_cli: syntheticLegacyCli(),
    legacy_python: syntheticLegacyPython(),
    newer_schema: {
      action: "OBSERVED",
      evidence_origin: "LOCAL_OBSERVATION",
      http_status: 200,
      optics_status: "OBSERVED",
      producer: "node_interceptor",
      producer_version: "PKG02-FUTURE-CLI-UNASSIGNED",
      record_type: "observation_event",
      schema_status: "stable-v9",
      schema_version: 99,
    },
    node_sdk: {
      auditMode: true,
      eventPayload: {
        action_taken: "SEVERED",
        target_host: "example.com",
      },
      traceId: "6f1d7a2e-3c4b-4d5e-8f90-a1b2c3d4e5f6",
    },
    simulated_demo: {
      calls: [
        {
          action: "OBSERVED",
          bytes: 0,
          hostname: "optics-demo.invalid",
          status: 200,
        },
      ],
      cli_version: "0.3.24",
      schema_version: 2,
      vantio_run_log: "1",
    },
    unknown_status: {
      http_status: 200,
      optics_status: "SUPER_SUCCESS",
      record_type: "observation_event",
    },
  };
}

function asBuffer(value) {
  if (Buffer.isBuffer(value)) return value;
  return Buffer.from(JSON.stringify(value));
}

function writeCorpus(directory, overrides) {
  const chosen = bodies();
  const extra = overrides || {};
  if (extra.legacy_cli) chosen.legacy_cli = extra.legacy_cli;
  if (extra.legacy_python) chosen.legacy_python = extra.legacy_python;
  const entries = [];
  for (let i = 0; i < FILES.length; i += 1) {
    const role = FILES[i][0];
    const name = FILES[i][1];
    fs.writeFileSync(path.join(directory, name), asBuffer(chosen[role]));
    entries.push({ name, role });
  }
  return {
    absentName: ABSENT_NAME,
    entries,
  };
}

module.exports = {
  ABSENT_NAME,
  CANARY,
  futureRecord,
  syntheticLegacyCli,
  syntheticLegacyPython,
  writeCorpus,
};
