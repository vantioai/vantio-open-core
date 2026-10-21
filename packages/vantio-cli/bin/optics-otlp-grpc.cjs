"use strict";

// Minimal OTLP unary gRPC over Node's HTTP/2 client. Field numbers follow
// opentelemetry-proto v1.7.0. No collector is started here.

const http2 = require("node:http2");

const TRACE_PATH = "/opentelemetry.proto.collector.trace.v1.TraceService/Export";
const METRICS_PATH = "/opentelemetry.proto.collector.metrics.v1.MetricsService/Export";
const LOGS_PATH = "/opentelemetry.proto.collector.logs.v1.LogsService/Export";

function varint(value) {
  let n = typeof value === "bigint" ? value : BigInt(value);
  if (n < 0n) throw new Error("varint must be non-negative");
  const out = [];
  while (n > 127n) {
    out.push(Number((n & 127n) | 128n));
    n >>= 7n;
  }
  out.push(Number(n));
  return Buffer.from(out);
}

function tag(field, wire) {
  return varint((BigInt(field) << 3n) | BigInt(wire));
}

function concat(parts) {
  return Buffer.concat(parts.filter((part) => part && part.length));
}

function fieldBytes(field, buf) {
  return concat([tag(field, 2), varint(buf.length), buf]);
}

function fieldString(field, value) {
  return fieldBytes(field, Buffer.from(String(value), "utf8"));
}

function fieldVarint(field, value) {
  return concat([tag(field, 0), varint(value)]);
}

function fieldFixed64(field, value) {
  const buf = Buffer.alloc(8);
  buf.writeBigUInt64LE(BigInt(value));
  return concat([tag(field, 1), buf]);
}

function anyValue(value) {
  if (typeof value === "number" && Number.isFinite(value)) return fieldVarint(3, Math.trunc(value));
  return fieldString(1, value == null ? "" : value);
}

function keyValue(key, value) {
  return concat([fieldString(1, key), fieldBytes(2, anyValue(value))]);
}

function encodeAttribute(attr) {
  if (!attr || attr.key == null) return Buffer.alloc(0);
  const value = attr.value || {};
  if (value.intValue != null && value.intValue !== "") return keyValue(attr.key, Number(value.intValue));
  if (value.stringValue != null) return keyValue(attr.key, value.stringValue);
  return Buffer.alloc(0);
}

function encodeResource(resource) {
  const parts = [];
  for (const attr of (resource && resource.attributes) || []) parts.push(fieldBytes(1, encodeAttribute(attr)));
  return concat(parts);
}

function encodeSpan(span) {
  const parts = [
    fieldBytes(1, Buffer.from(String(span.traceId || ""), "hex")),
    fieldBytes(2, Buffer.from(String(span.spanId || ""), "hex")),
    fieldString(5, span.name || "connect"),
    fieldVarint(6, span.kind == null ? 3 : span.kind),
    fieldFixed64(7, span.startTimeUnixNano || "0"),
    fieldFixed64(8, span.endTimeUnixNano || span.startTimeUnixNano || "0"),
  ];
  for (const attr of span.attributes || []) parts.push(fieldBytes(9, encodeAttribute(attr)));
  if (span.status && span.status.code) parts.push(fieldBytes(15, fieldVarint(3, span.status.code)));
  return concat(parts);
}

function encodeScopeSpans(scopeSpans) {
  const scope = scopeSpans.scope || {};
  const parts = [fieldBytes(1, fieldString(1, scope.name || "vantio.optics"))];
  for (const span of scopeSpans.spans || []) parts.push(fieldBytes(2, encodeSpan(span)));
  return concat(parts);
}

function encodeResourceSpans(resourceSpans) {
  const parts = [fieldBytes(1, encodeResource(resourceSpans.resource))];
  for (const scope of resourceSpans.scopeSpans || []) parts.push(fieldBytes(2, encodeScopeSpans(scope)));
  return concat(parts);
}

function encodeNumberPoint(point) {
  const parts = [fieldFixed64(3, point.timeUnixNano || "0"), fieldFixed64(6, point.asInt || "0")];
  for (const attr of point.attributes || []) parts.push(fieldBytes(7, encodeAttribute(attr)));
  return concat(parts);
}

function encodeMetric(metric) {
  const points = ((metric.gauge && metric.gauge.dataPoints) || []).map((point) => fieldBytes(1, encodeNumberPoint(point)));
  return concat([
    fieldString(1, metric.name || "vantio.optics.bytes"),
    fieldString(3, metric.unit || "By"),
    fieldBytes(5, concat(points)),
  ]);
}

function encodeScopeMetrics(scopeMetrics) {
  const scope = scopeMetrics.scope || {};
  const parts = [fieldBytes(1, fieldString(1, scope.name || "vantio.optics"))];
  for (const metric of scopeMetrics.metrics || []) parts.push(fieldBytes(2, encodeMetric(metric)));
  return concat(parts);
}

function encodeResourceMetrics(resourceMetrics) {
  const parts = [fieldBytes(1, encodeResource(resourceMetrics.resource))];
  for (const scope of resourceMetrics.scopeMetrics || []) parts.push(fieldBytes(2, encodeScopeMetrics(scope)));
  return concat(parts);
}

function encodeLog(record) {
  const body = record.body && record.body.stringValue != null ? record.body.stringValue : "";
  const parts = [
    fieldFixed64(1, record.timeUnixNano || "0"),
    fieldVarint(2, record.severityNumber == null ? 9 : record.severityNumber),
    fieldString(3, record.severityText || "INFO"),
    fieldBytes(5, fieldString(1, body)),
  ];
  for (const attr of record.attributes || []) parts.push(fieldBytes(6, encodeAttribute(attr)));
  if (record.traceId) parts.push(fieldBytes(9, Buffer.from(String(record.traceId), "hex")));
  if (record.spanId) parts.push(fieldBytes(10, Buffer.from(String(record.spanId), "hex")));
  parts.push(fieldFixed64(11, record.observedTimeUnixNano || record.timeUnixNano || "0"));
  return concat(parts);
}

function encodeScopeLogs(scopeLogs) {
  const scope = scopeLogs.scope || {};
  const parts = [fieldBytes(1, fieldString(1, scope.name || "vantio.optics"))];
  for (const record of scopeLogs.logRecords || []) parts.push(fieldBytes(2, encodeLog(record)));
  return concat(parts);
}

function encodeResourceLogs(resourceLogs) {
  const parts = [fieldBytes(1, encodeResource(resourceLogs.resource))];
  for (const scope of resourceLogs.scopeLogs || []) parts.push(fieldBytes(2, encodeScopeLogs(scope)));
  return concat(parts);
}

function encodeRepeated(items, encode) {
  return concat(items.map((item) => fieldBytes(1, encode(item))));
}

function encodeOtlpGrpc(payloads) {
  const traces = payloads && payloads.traces ? payloads.traces.resourceSpans || [] : [];
  const metrics = payloads && payloads.metrics ? payloads.metrics.resourceMetrics || [] : [];
  const logs = payloads && payloads.logs ? payloads.logs.resourceLogs || [] : [];
  return {
    traces: encodeRepeated(traces, encodeResourceSpans),
    metrics: encodeRepeated(metrics, encodeResourceMetrics),
    logs: encodeRepeated(logs, encodeResourceLogs),
  };
}

function grpcOrigin(raw) {
  const url = new URL(raw);
  let protocol = url.protocol;
  if (protocol === "grpc:") protocol = "http:";
  else if (protocol === "grpcs:") protocol = "https:";
  else if (protocol !== "http:" && protocol !== "https:") {
    throw new Error("otlp grpc URL must be grpc, grpcs, http, or https");
  }
  if (url.username || url.password) throw new Error("otlp grpc URL must not contain credentials");
  if (protocol === "http:") {
    const host = url.hostname.replace(/^\[|\]$/g, "").toLowerCase();
    if (host !== "localhost" && host !== "127.0.0.1" && host !== "::1") {
      throw new Error("otlp grpc refuses plaintext to a remote host");
    }
  }
  return { origin: `${protocol}//${url.host}`, secure: protocol === "https:" };
}

function grpcCall(origin, path, message) {
  const frame = Buffer.concat([
    Buffer.from([0]),
    Buffer.alloc(4),
    message,
  ]);
  frame.writeUInt32BE(message.length, 1);
  return new Promise((resolve, reject) => {
    const client = http2.connect(origin);
    let settled = false;
    const finish = (err) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      try { client.close(); } catch { /* already closed */ }
      if (err) reject(err);
      else resolve();
    };
    const timer = setTimeout(() => finish(new Error("otlp grpc timeout")), 10000);
    client.once("error", finish);
    const req = client.request({
      ":method": "POST",
      ":path": path,
      "content-type": "application/grpc",
      te: "trailers",
    });
    let status = null;
    const takeStatus = (headers) => {
      if (headers && headers["grpc-status"] != null) status = String(headers["grpc-status"]);
    };
    const finishStatus = () => {
      if (status == null) finish(new Error("otlp grpc returned no grpc-status"));
      else if (status === "0") finish();
      else finish(new Error(`otlp grpc returned ${status}`));
    };
    req.on("response", takeStatus);
    req.on("trailers", (headers) => {
      takeStatus(headers);
      finishStatus();
    });
    req.on("data", () => {});
    req.on("error", finish);
    req.on("end", () => {
      if (status != null) finishStatus();
    });
    req.on("close", () => {
      if (!settled) finishStatus();
    });
    req.end(frame);
  });
}

async function deliverOtlpGrpc(rawUrl, payloads, completed) {
  const target = grpcOrigin(rawUrl);
  const encoded = encodeOtlpGrpc(payloads);
  const calls = [
    [TRACE_PATH, encoded.traces, "traces"],
    [METRICS_PATH, encoded.metrics, "metrics"],
    [LOGS_PATH, encoded.logs, "logs"],
  ];
  const done = completed instanceof Set ? completed : null;
  for (const [path, message, name] of calls) {
    const key = `otlp-grpc:${name}`;
    if (done && done.has(key)) continue;
    try {
      await grpcCall(target.origin, path, message);
    } catch (err) {
      const detail = err && err.message ? err.message.split("\n")[0] : "failed";
      throw new Error(`otlp grpc ${name}: ${detail}`);
    }
    if (done) done.add(key);
  }
}

module.exports = {
  LOGS_PATH,
  METRICS_PATH,
  TRACE_PATH,
  deliverOtlpGrpc,
  encodeOtlpGrpc,
  grpcOrigin,
};
