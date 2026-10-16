"use strict";

const {
  FINDING_REASONS,
  INDICATORS,
  LABEL,
  LIVE_STACK,
  MAX_RECORDS,
  REASON_CODES,
  RESULT_SCHEMA,
  assertListed,
} = require("./boundary.cjs");
const {
  normalizeGate,
  normalizeKernel,
  normalizeOpenshell,
  normalizeRun,
} = require("./normalize.cjs");
const { copyValue } = require("./scan.cjs");

function emptyCounts() {
  return {
    kernel: 0,
    openshell: 0,
    gate: 0,
    bypass: 0,
    reconciled: 0,
    unattributed: 0,
    out_of_scope: 0,
  };
}

function rejected(reasonCode, detail) {
  assertListed(reasonCode, REASON_CODES, "reason_code");
  const result = {
    schema: RESULT_SCHEMA,
    status: "rejected",
    reason_code: reasonCode,
    findings: Object.freeze([]),
    counts: Object.freeze(emptyCounts()),
    label: LABEL,
    live_stack: LIVE_STACK,
  };
  if (detail) {
    result.detail = detail;
  }
  return Object.freeze(result);
}

function copySubject(subject) {
  if (subject == null) {
    return null;
  }
  switch (subject.kind) {
    case "network":
      return Object.freeze({ kind: "network", host: subject.host, port: subject.port });
    case "file":
      return Object.freeze({ kind: "file", path: subject.path });
    case "process":
      return Object.freeze({ kind: "process", path: subject.path });
    default: {
      const neverKind = subject.kind;
      throw new Error(`unhandled subject ${neverKind}`);
    }
  }
}

function subjectKey(subject) {
  const copy = copySubject(subject);
  switch (copy.kind) {
    case "network":
      return `network\0${copy.host}\0${copy.port}`;
    case "file":
      return `file\0${copy.path}`;
    case "process":
      return `process\0${copy.path}`;
    default: {
      const neverKind = copy.kind;
      throw new Error(`unhandled subject ${neverKind}`);
    }
  }
}

function sameSubject(left, right) {
  if (left == null || right == null) {
    return false;
  }
  if (left.kind !== right.kind) {
    return false;
  }
  return subjectKey(left) === subjectKey(right);
}

function withinWindow(left, right, windowMs) {
  return Math.abs(left - right) <= windowMs;
}

function indexOpenshell(rows) {
  const index = new Map();
  for (const row of rows) {
    if (row.action_class == null || row.subject == null) {
      continue;
    }
    const key = `${row.sandbox_id}\0${row.action_class}\0${subjectKey(row.subject)}`;
    const list = index.get(key);
    if (list) {
      list.push(row);
    } else {
      index.set(key, [row]);
    }
  }
  return index;
}

function indexGate(rows) {
  const index = new Map();
  for (const row of rows) {
    const list = index.get(row.trace_id);
    if (list) {
      list.push(row);
    } else {
      index.set(row.trace_id, [row]);
    }
  }
  return index;
}

// One OpenShell network row can sit behind several kernel writes on that
// destination. The indicator is a missing row, not a count comparison.
function matchOpenshell(kernel, sandboxId, index, windowMs) {
  if (kernel.action_class == null || kernel.subject == null || kernel.observed_at_ms == null) {
    return null;
  }
  const key = `${sandboxId}\0${kernel.action_class}\0${subjectKey(kernel.subject)}`;
  const candidates = index.get(key);
  if (!candidates) {
    return null;
  }
  for (const candidate of candidates) {
    if (withinWindow(kernel.observed_at_ms, candidate.observed_at_ms, windowMs)) {
      return candidate;
    }
  }
  return null;
}

function matchGate(kernel, run, index) {
  if (kernel.trace_id == null) {
    return null;
  }
  const candidates = index.get(kernel.trace_id);
  if (!candidates) {
    return null;
  }
  for (const candidate of candidates) {
    if (candidate.host_id != null && candidate.host_id !== run.host_id) {
      continue;
    }
    if (candidate.subject != null && kernel.subject != null && !sameSubject(candidate.subject, kernel.subject)) {
      continue;
    }
    if (
      candidate.observed_at_ms != null &&
      kernel.observed_at_ms != null &&
      !withinWindow(kernel.observed_at_ms, candidate.observed_at_ms, run.window_ms)
    ) {
      continue;
    }
    return candidate;
  }
  return null;
}

function decisionMismatch(kernel, openshell, gate) {
  const kernelDrop = kernel.action_taken === "NETWORK_BLOCK" || kernel.action_taken === "BLOCKED";
  if (!kernelDrop) {
    return false;
  }
  const shellAllow = openshell != null && openshell.disposition === "Allowed";
  const gateAllow = gate != null && gate.action_taken === "ALLOWED";
  return shellAllow || gateAllow;
}

function countBucket(indicator) {
  switch (indicator) {
    case "BYPASS_INDICATOR":
      return "bypass";
    case "RECONCILED_OK":
      return "reconciled";
    case "UNATTRIBUTED":
      return "unattributed";
    case "OUT_OF_SCOPE":
      return "out_of_scope";
    default: {
      const neverIndicator = indicator;
      throw new Error(`unhandled indicator ${neverIndicator}`);
    }
  }
}

function makeFinding(fields) {
  assertListed(fields.indicator, INDICATORS, "indicator");
  assertListed(fields.reason, FINDING_REASONS, "finding_reason");
  const finding = {
    indicator: fields.indicator,
    reason: fields.reason,
    kernel_index: fields.kernel_index,
    action_class: fields.action_class,
    subject: copySubject(fields.subject),
    matched_openshell: fields.matched_openshell,
    matched_gate: fields.matched_gate,
    decision_mismatch: fields.decision_mismatch,
    trace_id: fields.trace_id,
  };
  return Object.freeze(finding);
}

function unattributedReason(kernel) {
  if (kernel.action_class == null) {
    return "missing_action_class";
  }
  if (kernel.subject == null) {
    return "missing_subject";
  }
  return "kernel_time_not_unix";
}

function mapRows(rows, normalize, limitDetail) {
  if (rows.length > MAX_RECORDS) {
    return failRows("LIMIT_EXCEEDED", limitDetail);
  }
  const normalized = [];
  for (let index = 0; index < rows.length; index += 1) {
    const row = normalize(rows[index], index);
    if (!row.ok) {
      return row;
    }
    normalized.push(row.value);
  }
  return { ok: true, value: normalized };
}

function failRows(reasonCode, detail) {
  return { ok: false, reason_code: reasonCode, detail };
}

function reconcile(input) {
  if (input == null || typeof input !== "object") {
    return rejected("SCHEMA", "input");
  }
  const copied = copyValue(input, "");
  if (!copied.ok) {
    return rejected(copied.reason_code, copied.detail);
  }
  const snapshot = copied.value;
  if (!Array.isArray(snapshot.kernel) || !Array.isArray(snapshot.openshell) || !Array.isArray(snapshot.gate)) {
    return rejected("SCHEMA", "input.arrays");
  }
  const run = normalizeRun(snapshot.run);
  if (!run.ok) {
    return rejected(run.reason_code, run.detail);
  }
  const kernel = mapRows(snapshot.kernel, normalizeKernel, "kernel");
  if (!kernel.ok) {
    return rejected(kernel.reason_code, kernel.detail);
  }
  const openshell = mapRows(snapshot.openshell, normalizeOpenshell, "openshell");
  if (!openshell.ok) {
    return rejected(openshell.reason_code, openshell.detail);
  }
  const gate = mapRows(snapshot.gate, normalizeGate, "gate");
  if (!gate.ok) {
    return rejected(gate.reason_code, gate.detail);
  }

  const shellIndex = indexOpenshell(openshell.value);
  const gateIndex = indexGate(gate.value);
  const findings = [];
  const counts = emptyCounts();
  counts.kernel = kernel.value.length;
  counts.openshell = openshell.value.length;
  counts.gate = gate.value.length;

  for (let index = 0; index < kernel.value.length; index += 1) {
    const row = kernel.value[index];
    let indicator;
    let reason;
    let matchedShell = null;
    let matchedGate = null;
    if (row.host_id !== run.value.host_id) {
      indicator = "OUT_OF_SCOPE";
      reason = "out_of_scope_host";
    } else if (!run.value.bindings.has(row.cgroup_id)) {
      indicator = "OUT_OF_SCOPE";
      reason = "out_of_scope_cgroup";
    } else {
      const sandboxId = run.value.bindings.get(row.cgroup_id);
      matchedShell = matchOpenshell(row, sandboxId, shellIndex, run.value.window_ms);
      matchedGate = matchGate(row, run.value, gateIndex);
      if (matchedShell || matchedGate) {
        indicator = "RECONCILED_OK";
        if (matchedShell && matchedGate) {
          reason = "matched_both";
        } else if (matchedShell) {
          reason = "matched_openshell";
        } else {
          reason = "matched_gate";
        }
      } else if (row.action_class == null || row.subject == null || row.observed_at_ms == null) {
        indicator = "UNATTRIBUTED";
        reason = unattributedReason(row);
      } else {
        indicator = "BYPASS_INDICATOR";
        reason = "no_matching_openshell_or_gate_record";
      }
    }
    counts[countBucket(indicator)] += 1;
    findings.push(makeFinding({
      indicator,
      reason,
      kernel_index: index,
      action_class: row.action_class,
      subject: row.subject,
      matched_openshell: matchedShell != null,
      matched_gate: matchedGate != null,
      decision_mismatch: decisionMismatch(row, matchedShell, matchedGate),
      trace_id: row.trace_id,
    }));
  }

  return Object.freeze({
    schema: RESULT_SCHEMA,
    status: "ok",
    findings: Object.freeze(findings),
    counts: Object.freeze(counts),
    label: LABEL,
    live_stack: LIVE_STACK,
  });
}

module.exports = {
  reconcile,
};
