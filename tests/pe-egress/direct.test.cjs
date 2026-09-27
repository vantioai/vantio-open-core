"use strict";

const assert = require("node:assert/strict");
const { describe, it } = require("node:test");
const { DIMENSIONS, RESULT_LIST, evaluate, listPaths } = require("../../packages/pe-egress-authority");
const { decide, hostObservation } = require("./fixture.cjs");

function expectResult(fields, result, reason) {
  const decision = decide(evaluate, fields);
  assert.equal(decision.fault, false);
  assert.equal(decision.result, result);
  if (reason) assert.equal(decision.reason, reason);
  assert.equal(RESULT_LIST.includes(decision.result), true);
  assert.equal(decision.this_force_executed_host, false);
  assert.equal(decision.this_force_executed_network, false);
  assert.equal(decision.optimistic_allow, false);
  assert.equal(decision.vocabulary, "PE_EGRESS_V1");
  for (const name of DIMENSIONS) {
    assert.equal(typeof decision.dimensions[name].state, "string");
  }
  assert.equal(JSON.stringify(decision).includes("SUCCESS"), false);
  return decision;
}

describe("direct dispositions", () => {
  it("allows a scoped fetch when the policy permits it", () => {
    const decision = expectResult({}, "ALLOWED", "policy_permits");
    assert.equal(decision.live_wire_action, "ALLOWED");
    assert.equal(decision.authority_disposition, "ALLOWED");
  });

  it("denies a blocked hostname", () => {
    const decision = expectResult({
      policy: { blocked_hosts: ["evil.example"] },
      attempt: { destination: { hostname: "evil.example", port: "443", protocol: "https", in_product_scope: true } },
    }, "DENIED", "host_not_permitted");
    assert.equal(decision.live_wire_action, "BLOCKED_HOST");
  });

  it("denies a suffix of a listed DNS name and ignores a bare token", () => {
    expectResult({
      policy: { blocked_hosts: ["evil.example"] },
      attempt: { destination: { hostname: "a.evil.example", port: "443", protocol: "https", in_product_scope: false } },
    }, "DENIED", "host_not_permitted");
    expectResult({
      policy: { blocked_hosts: ["com"] },
      attempt: { destination: { hostname: "api.openai.com", port: "443", protocol: "https", in_product_scope: true } },
    }, "ALLOWED", "policy_permits");
  });

  it("denies a host outside the allow list", () => {
    expectResult({
      policy: { allowed_hosts: ["api.openai.com"] },
      attempt: { destination: { hostname: "api.anthropic.com", port: "443", protocol: "https", in_product_scope: true } },
    }, "DENIED", "not_in_allowed_hosts");
  });

  it("redacts materialized email text", () => {
    const decision = expectResult({
      policy: { redact_pii: true, pii_types: ["email"] },
      attempt: { body: { kind: "text", text: "contact user@example.com" } },
    }, "REDACTED", "sensitive_redacted");
    assert.equal(decision.live_wire_action, "REDACTED");
  });

  it("contains an exfil pattern when a supplied control stopped it", () => {
    expectResult({
      attempt: {
        pattern: { kind: "exfil", contained: true, evidence: "supplied", control_id: "case-sink" },
      },
    }, "CONTAINED", "pattern_contained");
  });

  it("revokes a credential when a supplied control applied", () => {
    expectResult({
      policy: { credential_required: true },
      attempt: {
        credential: {
          present: true,
          revoked: true,
          permitted: false,
          control_applied: true,
          evidence: "supplied",
          control_id: "case-revoke",
        },
      },
    }, "REVOKED", "credential_revoked");
  });

  it("declares browser, quic, and unmanaged cloud unsupported", () => {
    expectResult({ path: "app_browser" }, "UNSUPPORTED", "path_declared_unsupported");
    expectResult({ path: "app_quic" }, "UNSUPPORTED", "path_declared_unsupported");
    expectResult({ path: "host_managed_cloud" }, "UNSUPPORTED", "path_declared_unsupported");
  });

  it("declares a destination outside product scope unsupported", () => {
    expectResult({
      attempt: { destination: { hostname: "example.com", port: "443", protocol: "https", in_product_scope: false } },
    }, "UNSUPPORTED", "destination_outside_product_scope");
  });

  it("returns enforcement gap for a raw syscall path", () => {
    expectResult({ path: "app_raw_syscall" }, "ENFORCEMENT_GAP", "application_path_bypass");
  });

  it("returns evidence unavailable when destination evidence is absent", () => {
    expectResult({ attempt: { destination: { in_product_scope: true } } }, "EVIDENCE_UNAVAILABLE", "destination_evidence_absent");
  });

  it("returns unknown for a malformed case and for unresolved DNS answers", () => {
    const malformed = evaluate(null);
    assert.equal(malformed.result, "UNKNOWN");
    assert.equal(malformed.reason, "malformed_case");
    expectResult({
      attempt: { dns: { answers: ["203.0.113.10", "203.0.113.11"] } },
    }, "UNKNOWN", "dns_answers_unresolved");
  });

  it("denies a protocol and a port", () => {
    expectResult({
      policy: { denied_protocols: ["http"] },
      attempt: { destination: { hostname: "api.openai.com", port: "80", protocol: "http", in_product_scope: true } },
    }, "DENIED", "protocol_not_permitted");
    expectResult({
      policy: { denied_ports: ["25"] },
      attempt: { destination: { hostname: "api.openai.com", port: 25, protocol: "smtp", in_product_scope: true } },
    }, "DENIED", "port_not_permitted");
  });

  it("denies an HTTP method and path when the path can see them", () => {
    expectResult({
      policy: { denied_methods: ["PUT"] },
      attempt: { http: { method: "put", path: "/v1/chat" } },
    }, "DENIED", "method_not_permitted");
    expectResult({
      policy: { denied_path_prefixes: ["/v1/files"] },
      attempt: { http: { method: "POST", path: "/v1/files/upload" } },
    }, "DENIED", "path_not_permitted");
  });

  it("denies a later call once the supplied spend counter reaches the cap", () => {
    const decision = expectResult({
      policy: { spend_cap_usd: 1 },
      attempt: { spend: { phase: "subsequent", spent_usd: 1 } },
    }, "DENIED", "spend_cap");
    assert.equal(decision.live_wire_action, "BLOCKED_SPEND");
  });

  it("denies an oversized materialized body", () => {
    const decision = expectResult({
      policy: { max_request_bytes: 4 },
      attempt: { size: { bytes: 8 }, body: { kind: "empty" } },
    }, "DENIED", "payload_size");
    assert.equal(decision.live_wire_action, "BLOCKED_SIZE");
  });

  it("denies a blocked IP on a host observation that records a drop", () => {
    const decision = expectResult({
      path: "host_tc_enrolled",
      policy: { blocked_ips: ["203.0.113.0/24"] },
      attempt: {
        destination: { ip: "203.0.113.9", port: "443", protocol: "tcp" },
        host_observation: hostObservation({ dropped: true }),
      },
    }, "DENIED", "host_not_permitted");
    assert.equal(decision.evidence_class, "SUPPLIED_CASE_EVIDENCE");
    assert.equal(decision.this_force_executed_host, false);
  });

  it("evaluates every catalog path to a vocabulary token", () => {
    for (const id of listPaths()) {
      const decision = decide(evaluate, {
        path: id,
        attempt: id.startsWith("host_") ? { host_observation: hostObservation() } : {},
      });
      assert.equal(decision.fault, false);
      assert.equal(RESULT_LIST.includes(decision.result), true);
      assert.equal(decision.result === "SUCCESS", false);
    }
  });
});
