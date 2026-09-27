"use strict";

const assert = require("node:assert/strict");
const { describe, it } = require("node:test");
const { RESULT_LIST, evaluate } = require("../../packages/pe-egress-authority");
const { decide, hostObservation } = require("./fixture.cjs");

function run(fields) {
  const decision = decide(evaluate, fields);
  assert.equal(decision.fault, false);
  assert.equal(RESULT_LIST.includes(decision.result), true);
  assert.equal(decision.result === "SUCCESS", false);
  assert.equal(decision.optimistic_allow, false);
  assert.equal(decision.this_force_executed_host, false);
  assert.equal(decision.this_force_executed_network, false);
  return decision;
}

describe("adversarial egress", () => {
  it("does not allow a blocked host because the case smuggles ALLOWED", () => {
    const decision = run({
      policy: { blocked_hosts: ["evil.example"] },
      attempt: {
        result: "ALLOWED",
        destination: { hostname: "evil.example", port: "443", protocol: "https", in_product_scope: true },
      },
    });
    assert.equal(decision.result, "UNKNOWN");
    assert.equal(decision.reason, "smuggled_result");
  });

  it("does not allow a cleared NODE_OPTIONS bypass of a blocked host", () => {
    const decision = run({
      policy: { blocked_hosts: ["evil.example"] },
      attempt: {
        bypass: { kind: "cleared_node_options" },
        destination: { hostname: "evil.example", port: "443", protocol: "https", in_product_scope: true },
      },
    });
    assert.equal(decision.result, "ENFORCEMENT_GAP");
    assert.equal(decision.reason, "application_path_bypass");
    assert.equal(decision.authority_disposition, "DENIED");
  });

  it("does not allow a redirect chain the application path never rechecks", () => {
    const decision = run({
      attempt: {
        redirect: {
          hops: [
            { hostname: "api.openai.com" },
            { hostname: "evil.example" },
          ],
        },
      },
      policy: { blocked_hosts: ["evil.example"] },
    });
    assert.equal(decision.result, "ENFORCEMENT_GAP");
    assert.equal(decision.reason, "redirect_not_reevaluated");
    assert.equal(decision.authority_disposition, "DENIED");
    assert.notEqual(decision.result, "ALLOWED");
  });

  it("denies a rechecked redirect hop on a host observation", () => {
    const decision = run({
      path: "host_tc_enrolled",
      policy: { blocked_hosts: ["evil.example"] },
      attempt: {
        destination: { hostname: "api.openai.com", port: "443", protocol: "https" },
        redirect: { hops: [{ hostname: "api.openai.com" }, { hostname: "evil.example" }] },
        host_observation: hostObservation({ dropped: true, saw: ["destination_ip", "port", "protocol", "redirect"] }),
      },
    });
    assert.equal(decision.result, "DENIED");
    assert.equal(decision.reason, "redirect_hop_denied");
  });

  it("does not allow a DNS change the application path cannot recheck", () => {
    const decision = run({
      policy: { blocked_ips: ["198.51.100.9"] },
      attempt: {
        dns: { answers: ["203.0.113.10", "198.51.100.9"], selected: "203.0.113.10", at_connect: "198.51.100.9", rechecked: false },
      },
    });
    assert.equal(decision.result, "ENFORCEMENT_GAP");
    assert.equal(decision.reason, "dns_change_not_rechecked");
    assert.notEqual(decision.result, "ALLOWED");
  });

  it("denies a resolved IP the host observation dropped", () => {
    const decision = run({
      path: "host_tc_enrolled",
      policy: { blocked_ips: ["198.51.100.9"] },
      attempt: {
        destination: { hostname: "api.openai.com", ip: "198.51.100.9", port: "443", protocol: "tcp" },
        dns: { answers: ["198.51.100.9"], selected: "198.51.100.9", at_connect: "198.51.100.9", rechecked: true },
        host_observation: hostObservation({ dropped: true }),
      },
    });
    assert.equal(decision.result, "DENIED");
    assert.equal(decision.reason, "host_not_permitted");
  });

  it("does not treat an open-socket retry as a new gated request", () => {
    const decision = run({
      policy: { blocked_hosts: ["evil.example"] },
      attempt: {
        retry: { channel: "open_socket" },
        destination: { hostname: "evil.example", port: "443", protocol: "https", in_product_scope: true },
      },
    });
    assert.equal(decision.result, "ENFORCEMENT_GAP");
    assert.equal(decision.reason, "retry_on_open_socket");
  });

  it("does not allow a retry when the spend counter is missing", () => {
    const decision = run({
      policy: { spend_cap_usd: 2 },
      attempt: { retry: { channel: "new_request" } },
    });
    assert.equal(decision.result, "EVIDENCE_UNAVAILABLE");
    assert.equal(decision.reason, "spend_evidence_absent");
  });

  it("does not block the current stream when the cap is crossed mid-body", () => {
    const decision = run({
      policy: { spend_cap_usd: 1 },
      attempt: { spend: { phase: "mid_stream", spent_usd: 3 } },
    });
    assert.equal(decision.result, "ENFORCEMENT_GAP");
    assert.equal(decision.reason, "spend_cap_cannot_block_mid_stream");
    assert.equal(decision.would_result, "DENIED");
  });

  it("keeps a dry-run deny from being recorded as allowed", () => {
    const decision = run({
      policy: { dry_run: true, blocked_hosts: ["evil.example"] },
      attempt: { destination: { hostname: "evil.example", port: "443", protocol: "https", in_product_scope: true } },
    });
    assert.equal(decision.result, "ENFORCEMENT_GAP");
    assert.equal(decision.reason, "dry_run_pass_through");
    assert.equal(decision.would_result, "DENIED");
    assert.equal(decision.live_wire_action, "DRY_RUN_BLOCKED_HOST");
  });

  it("does not coerce a bad size cap into an allow", () => {
    const decision = run({ policy: { max_request_bytes: "4" }, attempt: { size: { bytes: 100 } } });
    assert.equal(decision.result, "UNKNOWN");
    assert.equal(decision.reason, "policy_field_unclassifiable");
  });

  it("does not allow a streaming body when redaction is required", () => {
    const decision = run({
      policy: { redact_pii: true, pii_types: ["email"] },
      attempt: { body: { kind: "stream" } },
    });
    assert.equal(decision.result, "ENFORCEMENT_GAP");
    assert.equal(decision.reason, "unscanned_body");
    assert.equal(decision.live_wire_action, "ENFORCEMENT_GAP");
  });

  it("does not claim the application path can deny on sensitive text", () => {
    const decision = run({
      policy: { sensitive_action: "deny", pii_types: ["email"] },
      attempt: { body: { kind: "text", text: "user@example.com" } },
    });
    assert.equal(decision.result, "ENFORCEMENT_GAP");
    assert.equal(decision.reason, "sensitive_deny_not_enforced");
    assert.equal(decision.authority_disposition, "DENIED");
  });

  it("denies sensitive text only when a supplied control applied", () => {
    const decision = run({
      policy: { sensitive_action: "deny", pii_types: ["email"] },
      attempt: {
        body: { kind: "text", text: "user@example.com" },
        sensitive: { present: true, control_applied: true, evidence: "supplied", control_id: "case-deny" },
      },
    });
    assert.equal(decision.result, "DENIED");
    assert.equal(decision.reason, "sensitive_denied");
  });

  it("does not redact a TLS socket payload the wrap does not parse", () => {
    const decision = run({
      path: "app_node_tls",
      policy: { redact_pii: true, pii_types: ["ssn"] },
      attempt: { body: { kind: "text", text: "123-45-6789" } },
    });
    assert.equal(decision.result, "ENFORCEMENT_GAP");
    assert.equal(decision.reason, "redact_not_visible");
  });

  it("does not invent an HTTP method decision on a direct socket", () => {
    const decision = run({
      path: "app_node_net",
      policy: { allowed_methods: ["GET"] },
      attempt: { http: { method: "GET", path: "/" } },
    });
    assert.equal(decision.result, "ENFORCEMENT_GAP");
    assert.equal(decision.reason, "http_method_not_visible");
  });

  it("does not allow a grandchild or an unwrapped child binary", () => {
    const grandchild = run({
      attempt: { descendant: { binary: "curl", depth: 2 } },
    });
    assert.equal(grandchild.result, "ENFORCEMENT_GAP");
    assert.equal(grandchild.reason, "grandchild_not_visible");
    const bash = run({
      path: "app_child_tool",
      attempt: { descendant: { binary: "bash", depth: 1, inherits_wrap: false } },
    });
    assert.equal(bash.result, "ENFORCEMENT_GAP");
    assert.equal(bash.reason, "descendant_binary_outside_wrap");
  });

  it("denies a direct curl spawn to a blocked host", () => {
    const decision = run({
      path: "app_child_tool",
      policy: { blocked_hosts: ["evil.example"] },
      attempt: {
        descendant: { binary: "curl", depth: 1 },
        destination: { hostname: "evil.example", port: "443", protocol: "https", in_product_scope: true },
      },
    });
    assert.equal(decision.result, "DENIED");
    assert.equal(decision.reason, "host_not_permitted");
  });

  it("does not treat a claimed wrap inheritance as an allow of the child call", () => {
    const decision = run({
      attempt: { descendant: { binary: "node", depth: 1, inherits_wrap: true } },
    });
    assert.equal(decision.result, "ENFORCEMENT_GAP");
    assert.equal(decision.reason, "descendant_call_not_in_this_decision");
  });

  it("keeps an uncontained proxy, relay, callback, and scanner from being allowed", () => {
    for (const kind of ["scanner", "proxy", "relay", "callback", "exfil"]) {
      const decision = run({ attempt: { pattern: { kind, contained: false } } });
      assert.equal(decision.result, "ENFORCEMENT_GAP");
      assert.equal(decision.reason, "pattern_not_contained");
    }
  });

  it("does not accept a containment flag without control evidence", () => {
    const decision = run({
      attempt: { pattern: { kind: "callback", contained: true } },
    });
    assert.equal(decision.result, "EVIDENCE_UNAVAILABLE");
    assert.equal(decision.reason, "containment_control_absent");
  });

  it("does not allow a revoked credential the application path cannot revoke", () => {
    const decision = run({
      attempt: { credential: { present: true, revoked: true, permitted: true } },
    });
    assert.equal(decision.result, "ENFORCEMENT_GAP");
    assert.equal(decision.reason, "revocation_not_enforced");
    assert.equal(decision.authority_disposition, "REVOKED");
  });

  it("does not allow when credential evidence is required and absent", () => {
    const decision = run({ policy: { credential_required: true } });
    assert.equal(decision.result, "EVIDENCE_UNAVAILABLE");
    assert.equal(decision.reason, "credential_evidence_absent");
  });

  it("does not allow a TLS name mismatch the application path cannot see", () => {
    const decision = run({
      policy: { require_tls_peer: true },
      attempt: { tls: { peer_name: "evil.example" } },
    });
    assert.equal(decision.result, "ENFORCEMENT_GAP");
    assert.equal(decision.reason, "tls_peer_not_visible");
    assert.equal(decision.authority_disposition, "DENIED");
  });

  it("does not allow when a required TLS peer name is absent", () => {
    const decision = run({ policy: { require_tls_peer: true } });
    assert.equal(decision.result, "ENFORCEMENT_GAP");
    assert.equal(decision.reason, "tls_peer_not_visible");
  });

  it("returns evidence unavailable for a host path with no observation", () => {
    const decision = run({ path: "host_tc_enrolled" });
    assert.equal(decision.result, "EVIDENCE_UNAVAILABLE");
    assert.equal(decision.reason, "host_observation_absent");
  });

  it("rejects a claim that this force executed the host", () => {
    const decision = run({
      path: "host_tc_enrolled",
      attempt: { host_observation: hostObservation({ this_force_executed: true, dropped: true }) },
    });
    assert.equal(decision.result, "UNKNOWN");
    assert.equal(decision.reason, "host_execution_claim_rejected");
    assert.equal(decision.this_force_executed_host, false);
  });

  it("records a cgroup attach gap and an uprobe observe-only gap", () => {
    const cgroup = run({
      path: "host_cgroup_skb",
      policy: { blocked_ips: ["203.0.113.9"] },
      attempt: {
        destination: { ip: "203.0.113.9", port: "443", protocol: "tcp" },
        host_observation: hostObservation({ attach: "none", dropped: false, forwarded_cgroup0: true }),
      },
    });
    assert.equal(cgroup.result, "ENFORCEMENT_GAP");
    assert.equal(cgroup.reason, "cgroup_skb_not_attached");
    const uprobe = run({
      path: "host_uprobe_tls",
      attempt: {
        destination: { ip: "203.0.113.10", port: "443", protocol: "tcp" },
        host_observation: hostObservation({ attach: "uprobe", dropped: false }),
      },
    });
    assert.equal(uprobe.result, "ENFORCEMENT_GAP");
    assert.equal(uprobe.reason, "uprobe_observe_only");
    assert.equal(uprobe.authority_disposition, "ALLOWED");
  });

  it("does not explain a drop the observation says did not attach", () => {
    const decision = run({
      path: "host_cgroup_skb",
      attempt: {
        destination: { ip: "203.0.113.9", port: "443", protocol: "tcp" },
        host_observation: hostObservation({ attach: "none", dropped: true }),
      },
    });
    assert.equal(decision.result, "UNKNOWN");
    assert.equal(decision.reason, "host_drop_unexplained");
  });

  it("matches an IPv4 prefix boundary and an IPv6 prefix", () => {
    const inside = run({
      path: "host_tc_enrolled",
      policy: { blocked_ips: ["203.0.113.0/25"] },
      attempt: {
        destination: { ip: "203.0.113.127", port: "443", protocol: "tcp" },
        host_observation: hostObservation({ dropped: true }),
      },
    });
    assert.equal(inside.result, "DENIED");
    const outside = run({
      path: "host_tc_enrolled",
      policy: { blocked_ips: ["203.0.113.0/25"] },
      attempt: {
        destination: { ip: "203.0.113.128", port: "443", protocol: "tcp" },
        host_observation: hostObservation({ dropped: false }),
      },
    });
    assert.equal(outside.result, "ALLOWED");
    const v6 = run({
      path: "host_tc_enrolled",
      policy: { blocked_ips: ["2001:db8::/32"] },
      attempt: {
        destination: { ip: "2001:db8::1", port: "443", protocol: "tcp" },
        host_observation: hostObservation({ dropped: true }),
      },
    });
    assert.equal(v6.result, "DENIED");
    const v6out = run({
      path: "host_tc_enrolled",
      policy: { blocked_ips: ["2001:db8::/32"] },
      attempt: {
        destination: { ip: "2001:db9::1", port: "443", protocol: "tcp" },
        host_observation: hostObservation({ dropped: false }),
      },
    });
    assert.equal(v6out.result, "ALLOWED");
  });

  it("contains a child-process resource breach only when the control is supplied", () => {
    const gap = run({
      policy: { resource: { max_child_processes: 1 } },
      attempt: { resource: { child_processes: 4, control_applied: false } },
    });
    assert.equal(gap.result, "ENFORCEMENT_GAP");
    assert.equal(gap.reason, "resource_not_contained");
    const held = run({
      policy: { resource: { max_child_processes: 1 } },
      attempt: { resource: { child_processes: 4, control_applied: true, evidence: "supplied", control_id: "case-rlimit" } },
    });
    assert.equal(held.result, "CONTAINED");
    assert.equal(held.reason, "resource_contained");
  });

  it("records fail-open when the policy latch is not loaded", () => {
    const decision = run({
      policy: { blocked_hosts: ["evil.example"] },
      attempt: {
        policy_loaded: false,
        destination: { hostname: "evil.example", port: "443", protocol: "https", in_product_scope: true },
      },
    });
    assert.equal(decision.result, "ENFORCEMENT_GAP");
    assert.equal(decision.reason, "fail_open_policy_not_loaded");
  });

  it("does not throw when a case field throws", () => {
    const nasty = {};
    Object.defineProperty(nasty, "path", { get() { throw new Error("boom"); } });
    const decision = evaluate(nasty);
    assert.equal(decision.result, "UNKNOWN");
    assert.equal(decision.reason, "evaluator_fault");
    assert.equal(decision.fault, true);
  });

  it("contradicts a sensitive flag that disagrees with the text", () => {
    const decision = run({
      policy: { redact_pii: true, pii_types: ["email"] },
      attempt: {
        body: { kind: "text", text: "hello" },
        sensitive: { present: true },
      },
    });
    assert.equal(decision.result, "UNKNOWN");
    assert.equal(decision.reason, "sensitive_evidence_contradicts");
  });

  it("does not pass general egress through an application path that only sees named scope", () => {
    const decision = run({
      policy: { scope: "all_egress" },
      attempt: { destination: { hostname: "example.com", port: "443", protocol: "https", in_product_scope: false } },
    });
    assert.equal(decision.result, "ENFORCEMENT_GAP");
    assert.equal(decision.reason, "out_of_scope_pass_through");
    assert.equal(decision.authority_disposition, "ALLOWED");
  });
});
