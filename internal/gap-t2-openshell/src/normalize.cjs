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
const CGROUP_TEXT = /^[0-9]{1,20}$/;
const CGROUP_MAX = 18446744073709551615n;
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

function stable(value) {
  return JSON.stringify(value);
}

function consistent(record, names, convert, reason, detail) {
  let canonical;
  let saw = false;
  for (const name of names) {
    if (!Object.prototype.hasOwnProperty.call(record, name) || record[name] == null) {
      continue;
    }
    const next = convert(record[name]);
    if (!next.ok) {
      return fail(reason, detail);
    }
    if (!saw) {
      canonical = next.value;
      saw = true;
      continue;
    }
    if (stable(canonical) !== stable(next.value)) {
      return fail(reason, detail);
    }
  }
  return pass(saw ? canonical : undefined);
}

function canonicalCgroup(value) {
  let text;
  if (typeof value === "number" && Number.isSafeInteger(value) && value >= 0) {
    text = String(value);
  } else if (typeof value === "string" && CGROUP_TEXT.test(value)) {
    text = value;
  } else {
    return null;
  }
  const id = BigInt(text);
  if (id > CGROUP_MAX) {
    return null;
  }
  return id.toString();
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
    const cgroupId = canonicalCgroup(row.cgroup_id);
    if (cgroupId == null || typeof row.cgroup_id !== "string") {
      return fail("SCHEMA", `run.bindings[${index}].cgroup_id`);
    }
    if (typeof row.sandbox_id !== "string" || !ID_PATTERN.test(row.sandbox_id)) {
      return fail("SCHEMA", `run.bindings[${index}].sandbox_id`);
    }
    if (bindings.has(cgroupId)) {
      return fail("AMBIGUOUS_BINDING", `run.bindings[${index}].cgroup_id`);
    }
    bindings.set(cgroupId, row.sandbox_id);
  }
  return pass({
    host_id: run.host_id,
    window_ms: run.window_ms,
    bindings,
  });
}

function kernelSubject(record, kind) {
  if (kind === "network") {
    const host = consistent(
      record,
      ["destination_host", "dst_host", "host"],
      normalizeHost,
      "KERNEL_RECORD",
      "kernel.subject",
    );
    const port = consistent(
      record,
      ["destination_port", "dst_port", "port"],
      normalizePort,
      "KERNEL_RECORD",
      "kernel.subject",
    );
    if (!host.ok || !port.ok) {
      return host.ok ? port : host;
    }
    if (host.value == null && port.value == null) {
      return pass(null);
    }
    if (host.value == null || port.value == null) {
      return fail("KERNEL_RECORD", "kernel.subject");
    }
    return pass({ kind: "network", host: host.value, port: port.value });
  }
  if (kind === "file") {
    const pathValue = consistent(
      record,
      ["PathAttempted", "path_attempted", "path"],
      normalizePath,
      "KERNEL_RECORD",
      "kernel.subject",
    );
    if (!pathValue.ok) {
      return pathValue;
    }
    if (pathValue.value == null) {
      return pass(null);
    }
    return pass({ kind: "file", path: pathValue.value });
  }
  if (kind === "process") {
    const pathValue = consistent(
      record,
      ["exe", "executable", "path"],
      normalizePath,
      "KERNEL_RECORD",
      "kernel.subject",
    );
    if (!pathValue.ok) {
      return pathValue;
    }
    if (pathValue.value == null || !pathValue.value.startsWith("/")) {
      return pass(null);
    }
    return pass({ kind: "process", path: pathValue.value });
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
  const cgroupRaw = consistent(
    record,
    ["cgroup_id", "cgroup"],
    (value) => {
      const id = canonicalCgroup(value);
      return id == null ? fail("cgroup") : pass(id);
    },
    "KERNEL_RECORD",
    `${where}.cgroup_id`,
  );
  if (!cgroupRaw.ok || cgroupRaw.value == null) {
    return fail("KERNEL_RECORD", `${where}.cgroup_id`);
  }
  const cgroupId = cgroupRaw.value;
  const eventRaw = consistent(
    record,
    ["EventType", "event_type"],
    (value) => {
      if (typeof value !== "string" || value.length < 1 || value.length > 64) {
        return fail("event");
      }
      return pass(value.toUpperCase());
    },
    "KERNEL_RECORD",
    `${where}.event_type`,
  );
  if (!eventRaw.ok || eventRaw.value == null) {
    return fail("KERNEL_RECORD", `${where}.event_type`);
  }
  const eventType = eventRaw.value;
  const kind = actionClass(eventType);
  const trace = consistent(
    record,
    ["TraceId", "trace_id"],
    canonicalTrace,
    "KERNEL_RECORD",
    `${where}.trace_id`,
  );
  if (!trace.ok) {
    return fail("KERNEL_RECORD", `${where}.trace_id`);
  }
  const explicitTime = own(record, ["observed_at_ms"]);
  let observedAt = null;
  if (explicitTime != null) {
    observedAt = unixMillis(explicitTime);
    if (observedAt == null) {
      return fail("KERNEL_RECORD", `${where}.observed_at_ms`);
    }
  }
  const subject = kernelSubject(record, kind);
  if (!subject.ok) {
    return fail("KERNEL_RECORD", `${where}.subject`);
  }
  const actionRaw = consistent(
    record,
    ["ActionTaken", "action_taken"],
    (value) => {
      const action = String(value).toUpperCase();
      if (!/^[A-Z_]{1,32}$/.test(action)) {
        return fail("action");
      }
      return pass(action);
    },
    "KERNEL_RECORD",
    `${where}.action_taken`,
  );
  if (!actionRaw.ok) {
    return fail("KERNEL_RECORD", `${where}.action_taken`);
  }
  const actionTaken = actionRaw.value == null ? null : actionRaw.value;
  return pass({
    host_id: record.host_id,
    cgroup_id: cgroupId,
    event_type: eventType,
    action_class: kind,
    action_taken: actionTaken,
    trace_id: trace.value == null ? null : trace.value,
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
    const target = isPlainObject(record.process) ? record.process.name : undefined;
    if (target == null) {
      return pass(null);
    }
    const subject = normalizePath(target);
    if (!subject.ok) {
      return fail("OPENSHELL_RECORD", "openshell.process.name");
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
  const dispositionRaw = consistent(
    record,
    ["action", "disposition"],
    (value) => {
      const text = String(value);
      if (!/^[A-Za-z_]{1,32}$/.test(text)) {
        return fail("action");
      }
      return pass(text);
    },
    "OPENSHELL_RECORD",
    `${where}.action`,
  );
  if (!dispositionRaw.ok) {
    return fail("OPENSHELL_RECORD", `${where}.action`);
  }
  const disposition = dispositionRaw.value == null ? null : dispositionRaw.value;
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
  const host = consistent(
    record,
    ["destination_host", "host"],
    normalizeHost,
    "GATE_RECORD",
    "gate.subject",
  );
  const port = consistent(
    record,
    ["destination_port", "port"],
    normalizePort,
    "GATE_RECORD",
    "gate.subject",
  );
  if (!host.ok || !port.ok) {
    return host.ok ? port : host;
  }
  if (host.value != null || port.value != null) {
    if (host.value == null || port.value == null) {
      return fail("GATE_RECORD", "gate.subject");
    }
    return pass({ kind: "network", host: host.value, port: port.value });
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
  const trace = consistent(
    record,
    ["TraceId", "trace_id"],
    canonicalTrace,
    "GATE_RECORD",
    `${where}.trace_id`,
  );
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
