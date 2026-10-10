"use strict";

const { SCHEMA_ID, SCHEMA_VERSION, SCOPE_NAME } = require("./schema.cjs");
const { bytesField, fixed64Field, messageField, stringField, varintField } = require("./protobuf.cjs");

function kvMessage(keyName, value) {
  const any = typeof value === "number" ? varintField(3, value) : stringField(1, String(value));
  return Buffer.concat([stringField(1, keyName), messageField(2, any)]);
}

function attributes(event) {
  const rows = [
    ["vantio.schema.id", SCHEMA_ID],
    ["vantio.schema.version", SCHEMA_VERSION],
    ["vantio.event.kind", event.kind],
    ["server.address", event.destination_host],
    ["server.port", event.destination_port],
    ["process.pid", event.pid],
    ["process.executable.name", event.executable],
    ["vantio.process.lineage", event.lineage.length ? JSON.stringify(event.lineage) : null],
    ["vantio.bytes.request", event.request_bytes],
    ["vantio.bytes.response", event.response_bytes],
    ["vantio.duration_ms", event.duration_ms],
    ["http.response.status_code", event.http_status],
    ["vantio.optics.status", event.optics_status],
    ["vantio.application.status", event.application_status],
    ["vantio.workload.id", event.workload_id],
    ["vantio.coverage.state", event.coverage_state],
    ["vantio.decision", event.decision],
    ["vantio.policy.digest", event.policy_digest],
    ["url.path", event.path],
    ["vantio.attestation", "producer"],
  ];
  return Buffer.concat(rows.filter(([, value]) => value != null).map(([keyName, value]) => messageField(9, kvMessage(keyName, value))));
}

function jsonAttributes(event) {
  const pairs = [
    ["vantio.schema.id", SCHEMA_ID],
    ["vantio.schema.version", SCHEMA_VERSION],
    ["vantio.event.kind", event.kind],
    ["server.address", event.destination_host],
    ["server.port", event.destination_port],
    ["process.pid", event.pid],
    ["process.executable.name", event.executable],
    ["vantio.process.lineage", event.lineage.length ? JSON.stringify(event.lineage) : null],
    ["vantio.bytes.request", event.request_bytes],
    ["vantio.bytes.response", event.response_bytes],
    ["vantio.duration_ms", event.duration_ms],
    ["http.response.status_code", event.http_status],
    ["vantio.optics.status", event.optics_status],
    ["vantio.application.status", event.application_status],
    ["vantio.workload.id", event.workload_id],
    ["vantio.coverage.state", event.coverage_state],
    ["vantio.decision", event.decision],
    ["vantio.policy.digest", event.policy_digest],
    ["url.path", event.path],
    ["vantio.attestation", "producer"],
  ];
  return pairs.filter(([, value]) => value != null).map(([key, value]) => ({
    key,
    value: typeof value === "number" ? { intValue: String(value) } : { stringValue: String(value) },
  }));
}

function spanJson(event, startNano, endNano) {
  return {
    traceId: event.trace_id,
    spanId: event.span_id,
    parentSpanId: event.parent_span_id || undefined,
    name: event.kind,
    kind: 3,
    startTimeUnixNano: String(startNano),
    endTimeUnixNano: String(endNano),
    attributes: jsonAttributes(event),
    status: { code: 1 },
  };
}

function tracesJson(events, nowNano) {
  return {
    resourceSpans: [{
      resource: {
        attributes: [
          { key: "service.name", value: { stringValue: "vantio-optics" } },
          { key: "vantio.schema.version", value: { stringValue: SCHEMA_VERSION } },
        ],
      },
      scopeSpans: [{
        scope: { name: SCOPE_NAME, version: SCHEMA_VERSION },
        spans: events.map((event) => spanJson(event, nowNano, nowNano + BigInt((event.duration_ms || 0) * 1_000_000))),
      }],
    }],
  };
}

function logsJson(events, nowNano) {
  return {
    resourceLogs: [{
      resource: {
        attributes: [
          { key: "service.name", value: { stringValue: "vantio-optics" } },
          { key: "vantio.schema.version", value: { stringValue: SCHEMA_VERSION } },
        ],
      },
      scopeLogs: [{
        scope: { name: SCOPE_NAME, version: SCHEMA_VERSION },
        logRecords: events.map((event) => ({
          timeUnixNano: String(nowNano),
          observedTimeUnixNano: String(nowNano),
          severityText: "INFO",
          body: { stringValue: event.kind },
          attributes: jsonAttributes(event),
          traceId: event.trace_id,
          spanId: event.span_id,
        })),
      }],
    }],
  };
}

function kv(keyName, value) {
  return kvMessage(keyName, value);
}

function spanProto(event, startNano, endNano) {
  const parts = [
    bytesField(1, Buffer.from(event.trace_id, "hex")),
    bytesField(2, Buffer.from(event.span_id, "hex")),
    stringField(5, event.kind),
    varintField(6, 3),
    fixed64Field(7, startNano),
    fixed64Field(8, endNano),
    attributes(event),
    messageField(15, varintField(3, 1)),
  ];
  if (event.parent_span_id) parts.splice(2, 0, bytesField(4, Buffer.from(event.parent_span_id, "hex")));
  return Buffer.concat(parts);
}

function tracesProto(events, nowNano) {
  const spans = Buffer.concat(events.map((event) => messageField(2, spanProto(
    event,
    nowNano,
    nowNano + BigInt((event.duration_ms || 0) * 1_000_000),
  ))));
  const scope = Buffer.concat([stringField(1, SCOPE_NAME), stringField(2, SCHEMA_VERSION)]);
  const scopeSpans = Buffer.concat([messageField(1, scope), spans]);
  const resource = messageField(1, kv("service.name", "vantio-optics"));
  const resourceSpans = Buffer.concat([messageField(1, resource), messageField(2, scopeSpans)]);
  return messageField(1, resourceSpans);
}

function logRecordProto(event, nowNano) {
  const attrs = [
    ["vantio.schema.version", SCHEMA_VERSION],
    ["vantio.event.kind", event.kind],
    ["vantio.policy.digest", event.policy_digest],
    ["vantio.decision", event.decision],
    ["vantio.coverage.state", event.coverage_state],
  ];
  const attributeBytes = Buffer.concat(attrs.filter(([, value]) => value != null).map(([keyName, value]) => messageField(6, kv(keyName, value))));
  return Buffer.concat([
    fixed64Field(1, nowNano),
    stringField(3, "INFO"),
    messageField(5, stringField(1, event.kind)),
    attributeBytes,
    bytesField(9, Buffer.from(event.trace_id, "hex")),
    bytesField(10, Buffer.from(event.span_id, "hex")),
    fixed64Field(11, nowNano),
  ]);
}

function logsProto(events, nowNano) {
  const records = Buffer.concat(events.map((event) => messageField(2, logRecordProto(event, nowNano))));
  const scope = Buffer.concat([stringField(1, SCOPE_NAME), stringField(2, SCHEMA_VERSION)]);
  const scopeLogs = Buffer.concat([messageField(1, scope), records]);
  const resource = messageField(1, kv("service.name", "vantio-optics"));
  return messageField(1, Buffer.concat([messageField(1, resource), messageField(2, scopeLogs)]));
}

module.exports = {
  logsJson,
  logsProto,
  tracesJson,
  tracesProto,
};
