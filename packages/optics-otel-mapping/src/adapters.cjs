"use strict";

const DISABLED = Object.freeze({
  exported: false,
  reason: "ADAPTERS_DISABLED",
  network: false,
  bytes_sent: 0,
});

function listAdapters(mapping) {
  return mapping.adapters.map((adapter) => Object.freeze({
    id: adapter.id,
    signal: adapter.signal,
    enabled: false,
    default_enabled: false,
    implementation: "NOT_PRESENT",
    network: false,
    i3: "LATER",
  }));
}

function exportRecords(mapping, records, _options) {
  const seen = Array.isArray(records) ? records.length : 0;
  return Object.freeze({
    exported: DISABLED.exported,
    reason: DISABLED.reason,
    network: DISABLED.network,
    bytes_sent: DISABLED.bytes_sent,
    mapping_id: mapping.mapping_id,
    mapping_version: mapping.mapping_version,
    records_seen: seen,
    adapters: listAdapters(mapping),
  });
}

module.exports = {
  exportRecords,
  listAdapters,
};
