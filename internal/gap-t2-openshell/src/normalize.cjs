"use strict";

const {
  MAX_BINDINGS,
  MAX_HOST,
  MAX_ID,
  MAX_PATH,
  MAX_UNIX_MS,
  MAX_WINDOW_MS,
  MIN_UNIX_MS,
  RUN_SCHEMA,
} = require("./boundary.cjs");

const ID_PATTERN = /^[A-Za-z0-9._-]{1,128}$/;
const CGROUP_PATTERN = /^[0-9]{1,20}$/;
const NETWORK_TYPES = new Set(["TLS_EGRESS", "NETWORK_BLOCK", "SYSCALL_CONNECT"]);
const FILE_TYPES = new Set(["SYSCALL_OPENAT", "SYSCALL_OPEN"]);
const PROCESS_TYPES = new Set(["SYSCALL_EXECVE", "SYSCALL_EXECVEAT"]);

function fail(reasonCode, detail) {
  return { ok: false, reason_code: reasonCode, detail };
}

function pass(value) {
  return { ok: true, value };
}

function isPlainObject(value) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}

function own(record, names) {
  for (const name of names) {
    if (Object.prototype.hasOwnProperty.call(record, name) && record[name] != null) {
      return record[name];
    }
  }
  return undefined;
}

function actionClass(eventType) {
  if (NETWORK_TYPES.has(eventType)) {
    return "network";
  }
  if (FILE_TYPES.has(eventType)) {
    return "file";
  }
  if (PROCESS_TYPES.has(eventType)) {
    return "process";
  }
  return null;
}

function canonicalTrace(value) {
  if (value == null || value === "") {
    return pass(null);
  }
  if (typeof value !== "string") {
    return fail("trace");
  }
  let text = value.trim().toLowerCase();
  if (text.startsWith("0x")) {
    text = text.slice(2);
  }
  if (!/^[0-9a-f]{1,16}$/.test(text)) {
    return fail("trace");
  }
  return pass(text.padStart(16, "0"));
}

function unixMillis(value) {
  if (typeof value !== "number" || !Number.isSafeInteger(value)) {
    return null;
  }
  if (value < MIN_UNIX_MS || value > MAX_UNIX_MS) {
    return null;
  }
  return value;
}

function normalizeHost(value) {
  if (typeof value !== "string") {
    return fail("host");
  }
  let host = value.trim().toLowerCase();
  if (host.startsWith("[") && host.endsWith("]") && host.length > 2) {
    host = host.slice(1, -1);
  }
  if (host.endsWith(".")) {
    host = host.slice(0, -1);
  }
  if (host.length < 1 || host.length > MAX_HOST) {
    return fail("host");
  }
  if (/[\s/@\\]/.test(host)) {
    return fail("host");
  }
  return pass(host);
}

function normalizePort(value) {
  let port = value;
  if (typeof port === "string" && /^[0-9]{1,5}$/.test(port)) {
    port = Number(port);
  }
  if (typeof port !== "number" || !Number.isInteger(port) || port < 1 || port > 65535) {
    return fail("port");
  }
  return pass(port);
}

function normalizePath(value) {
  if (typeof value !== "string" || value.length < 1 || value.length > MAX_PATH) {
    return fail("path");
  }
  if (value.includes("\0")) {
    return fail("path");
  }
  return pass(value);
}

function networkSubject(hostValue, portValue) {
  const host = normalizeHost(hostValue);
  if (!host.ok) {
    return host;
  }
  const port = normalizePort(portValue);
  if (!port.ok) {
    return port;
  }
  return pass({ kind: "network", host: host.value, port: port.value });
}

function normalizeRun(run) {
  if (!isPlainObject(run)) {
    return fail("SCHEMA", "run");
  }
  if (run.schema !== RUN_SCHEMA) {
    return fail("SCHEMA", "run.schema");
  }
  if (typeof run.host_id !== "string" || !ID_PATTERN.test(run.host_id) || run.host_id.length > MAX_ID) {
    return fail("SCHEMA", "run.host_id");
  }
  if (typeof run.window_ms !== "number" || !Number.isInteger(run.window_ms)) {
    return fail("SCHEMA", "run.window_ms");
  }
  if (run.window_ms < 0 || run.window_ms > MAX_WINDOW_MS) {
    return fail("SCHEMA", "run.window_ms");
  }
  if (!Array.isArray(run.bindings) || run.bindings.length < 1 || run.bindings.length > MAX_BINDINGS) {
    return fail("SCHEMA", "run.bindings");
  }
  const bindings = new Map();
  for (let index = 0; index < run.bindings.length; index += 1) {
    const row = run.bindings[index];
    if (!isPlainObject(row)) {
      return fail("SCHEMA", `run.bindings[${index}]`);
    }
    if (typeof row.cgroup_id !== "string" || !CGROUP_PATTERN.test(row.cgroup_id)) {
      return fail("SCHEMA", `run.bindings[${index}].cgroup_id`);
    }
    if (typeof row.sandbox_id !== "string" || !ID_PATTERN.test(row.sandbox_id)) {
      return fail("SCHEMA", `run.bindings[${index}].sandbox_id`);
    }
    if (bindings.has(row.cgroup_id)) {
      return fail("AMBIGUOUS_BINDING", `run.bindings[${index}].cgroup_id`);
    }
    bindings.set(row.cgroup_id, row.sandbox_id);
  }
  return pass({
    host_id: run.host_id,
    window_ms: run.window_ms,
    bindings,
  });
}

function kernelSubject(record, kind) {
  if (kind === "network") {
    const host = own(record, ["destination_host", "dst_host", "host"]);
    const port = own(record, ["destination_port", "dst_port", "port"]);
    if (host == null && port == null) {
      return pass(null);
    }
    if (host == null || port == null) {
      return fail("KERNEL_RECORD", "kernel.subject");
    }
    const subject = networkSubject(host, port);
    if (!subject.ok) {
      return fail("KERNEL_RECORD", "kernel.subject");
    }
    return subject;
  }
  if (kind === "file") {
    const pathValue = own(record, ["PathAttempted", "path_attempted", "path"]);
    if (pathValue == null) {
      return pass(null);
    }
    const subject = normalizePath(pathValue);
    if (!subject.ok) {
      return fail("KERNEL_RECORD", "kernel.subject");
    }
    return pass({ kind: "file", path: subject.value });
  }
  if (kind === "process") {
    const pathValue = own(record, ["exe", "executable", "path"]);
    if (pathValue == null) {
      return pass(null);
    }
    const subject = normalizePath(pathValue);
    if (!subject.ok) {
      return fail("KERNEL_RECORD", "kernel.subject");
    }
    if (!subject.value.startsWith("/")) {
      return pass(null);
    }
    return pass({ kind: "process", path: subject.value });
  }
  return pass(null);
}

function normalizeKernel(record, index) {
  const where = `kernel[${index}]`;
  if (!isPlainObject(record)) {
    return fail("KERNEL_RECORD", where);
  }
  if (typeof record.host_id !== "string" || !ID_PATTERN.test(record.host_id)) {
    return fail("KERNEL_RECORD", `${where}.host_id`);
  }
  const cgroupRaw = own(record, ["cgroup_id", "cgroup"]);
  const cgroupId = typeof cgroupRaw === "number" && Number.isSafeInteger(cgroupRaw)
    ? String(cgroupRaw)
    : cgroupRaw;
  if (typeof cgroupId !== "string" || !CGROUP_PATTERN.test(cgroupId)) {
    return fail("KERNEL_RECORD", `${where}.cgroup_id`);
  }
  const eventRaw = own(record, ["EventType", "event_type"]);
  if (typeof eventRaw !== "string" || eventRaw.length < 1 || eventRaw.length > 64) {
    return fail("KERNEL_RECORD", `${where}.event_type`);
  }
  const eventType = eventRaw.toUpperCase();
  const kind = actionClass(eventType);
  const trace = canonicalTrace(own(record, ["TraceId", "trace_id"]));
  if (!trace.ok) {
    return fail("KERNEL_RECORD", `${where}.trace_id`);
  }
  const explicitTime = own(record, ["observed_at_ms"]);
  const eventTimestamp = own(record, ["EventTimestamp", "event_timestamp"]);
  let observedAt = null;
  if (explicitTime != null) {
    observedAt = unixMillis(explicitTime);
    if (observedAt == null) {
      return fail("KERNEL_RECORD", `${where}.observed_at_ms`);
    }
  } else if (eventTimestamp != null && unixMillis(eventTimestamp) != null) {
    observedAt = unixMillis(eventTimestamp);
  }
  const subject = kernelSubject(record, kind);
  if (!subject.ok) {
    return fail("KERNEL_RECORD", `${where}.subject`);
  }
  const actionRaw = own(record, ["ActionTaken", "action_taken"]);
  const actionTaken = actionRaw == null ? null : String(actionRaw).toUpperCase();
  if (actionTaken != null && !/^[A-Z_]{1,32}$/.test(actionTaken)) {
    return fail("KERNEL_RECORD", `${where}.action_taken`);
  }
  return pass({
    host_id: record.host_id,
    cgroup_id: cgroupId,
    event_type: eventType,
    action_class: kind,
    action_taken: actionTaken,
    trace_id: trace.value,
    observed_at_ms: observedAt,
    subject: subject.value,
  });
}

function openshellSubject(record, kind) {
  if (kind === "network") {
    const endpoint = record.dst_endpoint;
    if (endpoint == null) {
      return pass(null);
    }
    if (!isPlainObject(endpoint)) {
      return fail("OPENSHELL_RECORD", "openshell.dst_endpoint");
    }
    const host = own(endpoint, ["domain", "ip"]);
    const port = own(endpoint, ["port"]);
    if (host == null && port == null) {
      return pass(null);
    }
    if (host == null || port == null) {
      return fail("OPENSHELL_RECORD", "openshell.dst_endpoint");
    }
    const subject = networkSubject(host, port);
    if (!subject.ok) {
      return fail("OPENSHELL_RECORD", "openshell.dst_endpoint");
    }
    return subject;
  }
  if (kind === "process") {
    const actor = record.actor;
    const process = isPlainObject(actor) ? actor.process : undefined;
    if (process == null) {
      return pass(null);
    }
    if (!isPlainObject(process) || process.name == null) {
      return fail("OPENSHELL_RECORD", "openshell.actor.process");
    }
    const subject = normalizePath(process.name);
    if (!subject.ok) {
      return fail("OPENSHELL_RECORD", "openshell.actor.process.name");
    }
    if (!subject.value.startsWith("/")) {
      return pass(null);
    }
    return pass({ kind: "process", path: subject.value });
  }
  return pass(null);
}

function classKind(classUid) {
  if (classUid === 4001 || classUid === 4002) {
    return "network";
  }
  if (classUid === 1007) {
    return "process";
  }
  return null;
}

function normalizeOpenshell(record, index) {
  const where = `openshell[${index}]`;
  if (!isPlainObject(record)) {
    return fail("OPENSHELL_RECORD", where);
  }
  const container = record.container;
  const sandboxId = isPlainObject(container) ? container.uid : undefined;
  if (typeof sandboxId !== "string" || !ID_PATTERN.test(sandboxId)) {
    return fail("OPENSHELL_RECORD", `${where}.container.uid`);
  }
  if (typeof record.class_uid !== "number" || !Number.isInteger(record.class_uid)) {
    return fail("OPENSHELL_RECORD", `${where}.class_uid`);
  }
  const kind = classKind(record.class_uid);
  if (record.time == null) {
    return fail("OPENSHELL_RECORD", `${where}.time`);
  }
  const observedAt = unixMillis(record.time);
  if (observedAt == null) {
    return fail("OPENSHELL_RECORD", `${where}.time`);
  }
  const subject = openshellSubject(record, kind);
  if (!subject.ok) {
    return subject;
  }
  const dispositionRaw = own(record, ["action", "disposition"]);
  const disposition = dispositionRaw == null ? null : String(dispositionRaw);
  if (disposition != null && !/^[A-Za-z_]{1,32}$/.test(disposition)) {
    return fail("OPENSHELL_RECORD", `${where}.action`);
  }
  let eventId = null;
  if (isPlainObject(record.metadata) && record.metadata.uid != null) {
    if (typeof record.metadata.uid !== "string" || record.metadata.uid.length > MAX_ID) {
      return fail("OPENSHELL_RECORD", `${where}.metadata.uid`);
    }
    eventId = record.metadata.uid;
  }
  return pass({
    sandbox_id: sandboxId,
    event_id: eventId,
    class_uid: record.class_uid,
    action_class: kind,
    disposition,
    observed_at_ms: observedAt,
    subject: subject.value,
  });
}

function gateSubject(record) {
  const host = own(record, ["destination_host", "host"]);
  const port = own(record, ["destination_port", "port"]);
  if (host != null || port != null) {
    if (host == null || port == null) {
      return fail("GATE_RECORD", "gate.subject");
    }
    const subject = networkSubject(host, port);
    if (!subject.ok) {
      return fail("GATE_RECORD", "gate.subject");
    }
    return subject;
  }
  const executable = own(record, ["exe", "executable"]);
  if (executable != null) {
    const subject = normalizePath(executable);
    if (!subject.ok) {
      return fail("GATE_RECORD", "gate.exe");
    }
    if (!subject.value.startsWith("/")) {
      return pass(null);
    }
    return pass({ kind: "process", path: subject.value });
  }
  const pathValue = own(record, ["PathAttempted", "path_attempted", "path"]);
  if (pathValue == null) {
    return pass(null);
  }
  const subject = normalizePath(pathValue);
  if (!subject.ok) {
    return fail("GATE_RECORD", "gate.path");
  }
  return pass({ kind: "file", path: subject.value });
}

function normalizeGate(record, index) {
  const where = `gate[${index}]`;
  if (!isPlainObject(record)) {
    return fail("GATE_RECORD", where);
  }
  const trace = canonicalTrace(own(record, ["TraceId", "trace_id"]));
  if (!trace.ok || trace.value == null) {
    return fail("GATE_RECORD", `${where}.trace_id`);
  }
  const hostId = record.host_id == null ? null : record.host_id;
  if (hostId != null && (typeof hostId !== "string" || !ID_PATTERN.test(hostId))) {
    return fail("GATE_RECORD", `${where}.host_id`);
  }
  let observedAt = null;
  if (record.observed_at_ms != null) {
    observedAt = unixMillis(record.observed_at_ms);
    if (observedAt == null) {
      return fail("GATE_RECORD", `${where}.observed_at_ms`);
    }
  }
  const subject = gateSubject(record);
  if (!subject.ok) {
    return fail(subject.reason_code, `${where}.subject`);
  }
  const actionRaw = own(record, ["action", "ActionTaken", "action_taken"]);
  const actionTaken = actionRaw == null ? null : String(actionRaw).toUpperCase();
  if (actionTaken != null && !/^[A-Z_]{1,32}$/.test(actionTaken)) {
    return fail("GATE_RECORD", `${where}.action`);
  }
  return pass({
    host_id: hostId,
    trace_id: trace.value,
    action_taken: actionTaken,
    observed_at_ms: observedAt,
    subject: subject.value,
  });
}

module.exports = {
  isPlainObject,
  normalizeGate,
  normalizeKernel,
  normalizeOpenshell,
  normalizeRun,
};
