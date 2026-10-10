"use strict";

const { SCHEMA_VERSION } = require("./schema.cjs");

function syslogLine(event, host) {
  const stamp = new Date().toISOString();
  const proc = event.pid == null ? "-" : String(event.pid);
  const structured = [
    `schema="${SCHEMA_VERSION}"`,
    `kind="${event.kind}"`,
    `trace="${event.trace_id}"`,
    `span="${event.span_id}"`,
    event.policy_digest ? `policy="${event.policy_digest}"` : null,
    event.decision ? `decision="${event.decision}"` : null,
  ].filter(Boolean).join(" ");
  const msg = JSON.stringify({
    schema_version: SCHEMA_VERSION,
    kind: event.kind,
    trace_id: event.trace_id,
    span_id: event.span_id,
    destination_host: event.destination_host,
    destination_port: event.destination_port,
    coverage_state: event.coverage_state,
    decision: event.decision,
    policy_digest: event.policy_digest,
  });
  return `<134>1 ${stamp} ${host || "vantio"} vantio-optics ${proc} - [${structured}] ${msg}`;
}

module.exports = { syslogLine };
