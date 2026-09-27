"use strict";

function bindWild(bind) {
  return bind == null || bind === "*" || bind === "0.0.0.0" || bind === "::" || bind === "";
}

function usableListenerRow(row) {
  return row != null && typeof row === "object" && !Array.isArray(row);
}

function listenerMatches(observed, expected) {
  if (!usableListenerRow(expected) || !observed || typeof observed !== "object") return false;
  const observedPort = Number(observed.local_port);
  const expectedPort = Number(expected.port);
  if (!Number.isInteger(observedPort) || observedPort !== expectedPort) return false;
  const expectedProto = String(expected.protocol || expected.proto || "").toLowerCase();
  if (expectedProto && String(observed.proto || "").toLowerCase() !== expectedProto) return false;
  const bind = expected.bind == null ? "*" : String(expected.bind);
  if (!bindWild(bind) && String(observed.local_addr || "") !== bind) return false;
  const workload = String(expected.workload || expected.container_name || "");
  if (workload && String(observed.workload || "") !== workload) return false;
  const comm = String(expected.comm || "");
  if (comm && String(observed.comm || "") !== comm) return false;
  return true;
}

function classifyListeners(observed, envelope) {
  const raw = envelope && Array.isArray(envelope.expected_listeners) ? envelope.expected_listeners : [];
  const expected = raw.filter(usableListenerRow);
  const used = new Set();
  const listeners = [];

  for (const observedRow of observed) {
    const workload = String(observedRow.workload || "");
    const candidates = [];
    expected.forEach((row, index) => {
      const expectedWorkload = String(row.workload || row.container_name || "");
      if (expectedWorkload && workload && expectedWorkload !== workload) return;
      candidates.push(index);
    });

    let listenerState = candidates.length === 0 ? "undeclared" : "unexpected";
    let envelopeIndex = null;
    for (const index of candidates) {
      if (used.has(index)) continue;
      if (listenerMatches(observedRow, expected[index])) {
        listenerState = "expected";
        envelopeIndex = index;
        used.add(index);
        break;
      }
    }

    listeners.push({
      ...observedRow,
      listener_state: listenerState,
      envelope_index: envelopeIndex,
    });
  }

  const workloadsHere = new Set(observed.map((row) => String(row.workload || "")));
  const missing = [];
  expected.forEach((row, index) => {
    if (used.has(index)) return;
    const expectedWorkload = String(row.workload || row.container_name || "");
    if (expectedWorkload && !workloadsHere.has(expectedWorkload)) return;
    missing.push({
      listener_state: "missing",
      port: row.port,
      bind: row.bind,
      protocol: row.protocol || row.proto,
      workload: row.workload || row.container_name,
      comm: row.comm,
    });
  });

  return { listeners, missing };
}

module.exports = {
  classifyListeners,
  listenerMatches,
  usableListenerRow,
};
