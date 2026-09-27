"use strict";

const assert = require("node:assert/strict");
const { describe, it } = require("node:test");
const { RESULT_LIST, evaluate } = require("../../packages/pe-egress-authority");
const { decide, hostObservation } = require("./fixture.cjs");

function run(fields) {
  const decision = decide(evaluate, fields);
  assert.equal(decision.fault, false);
  assert.equal(RESULT_LIST.includes(decision.result), true);
  assert.equal(decision.optimistic_allow, false);
  assert.equal(decision.this_force_executed_host, false);
  assert.equal(decision.this_force_executed_network, false);
  return decision;
}

function assertClosed(decision, result, reason) {
  assert.equal(decision.optimistic_allow, false);
  assert.notEqual(decision.result, "ALLOWED");
  assert.equal(decision.result, result);
  if (reason) assert.equal(decision.reason, reason);
}

const tlsControl = {
  control_applied: true,
  evidence: "supplied",
  control_id: "case-tls-peer",
};

describe("revision holds", () => {
  it("does not allow a matching TLS peer the application path did not verify", () => {
    const decision = run({
      policy: { require_tls_peer: true },
      attempt: { tls: { peer_name: "api.openai.com" } },
    });
    assertClosed(decision, "ENFORCEMENT_GAP", "tls_peer_not_visible");
    assert.equal(decision.dimensions.tls.state, "gap");
    assert.equal(decision.dimensions.tls.detail, "supplied_not_path_observed");
  });

  it("does not allow a matching TLS peer on an enrolled host that did not verify it", () => {
    const decision = run({
      path: "host_tc_enrolled",
      policy: { require_tls_peer: true },
      attempt: {
        destination: { hostname: "api.openai.com", ip: "203.0.113.10", port: "443", protocol: "tcp" },
        tls: { peer_name: "api.openai.com" },
        host_observation: hostObservation({ dropped: false }),
      },
    });
    assertClosed(decision, "ENFORCEMENT_GAP", "tls_peer_not_visible");
    assert.equal(decision.dimensions.tls.detail, "supplied_not_path_observed");
  });

  it("allows a matching TLS peer only when a supplied control applied", () => {
    const decision = run({
      policy: { require_tls_peer: true },
      attempt: { tls: Object.assign({ peer_name: "api.openai.com" }, tlsControl) },
    });
    assert.equal(decision.result, "ALLOWED");
    assert.equal(decision.optimistic_allow, false);
    assert.equal(decision.dimensions.tls.state, "clear");
  });

  it("keeps a TLS name without control evidence from allowing", () => {
    const decision = run({
      policy: { require_tls_peer: true },
      attempt: { tls: { peer_name: "api.openai.com", control_applied: true, control_id: "case-tls-peer" } },
    });
    assertClosed(decision, "ENFORCEMENT_GAP", "tls_peer_not_visible");
  });

  it("does not deny a TLS mismatch the host path cannot see", () => {
    const dropped = run({
      path: "host_tc_enrolled",
      policy: { require_tls_peer: true },
      attempt: {
        destination: { hostname: "api.openai.com", ip: "203.0.113.10", port: "443", protocol: "tcp" },
        tls: { peer_name: "evil.example" },
        host_observation: hostObservation({ dropped: true }),
      },
    });
    assertClosed(dropped, "ENFORCEMENT_GAP", "tls_peer_not_visible");
    assert.notEqual(dropped.reason, "tls_destination_mismatch");

    const quiet = run({
      path: "host_tc_enrolled",
      policy: { require_tls_peer: true },
      attempt: {
        destination: { hostname: "api.openai.com", ip: "203.0.113.10", port: "443", protocol: "tcp" },
        tls: { peer_name: "evil.example" },
        host_observation: hostObservation({ dropped: false }),
      },
    });
    assertClosed(quiet, "ENFORCEMENT_GAP", "host_did_not_drop");
    assert.equal(quiet.authority_disposition, "DENIED");
    assert.equal(quiet.would_result, "DENIED");

    const controlled = run({
      path: "host_tc_enrolled",
      policy: { require_tls_peer: true },
      attempt: {
        destination: { hostname: "api.openai.com", ip: "203.0.113.10", port: "443", protocol: "tcp" },
        tls: Object.assign({ peer_name: "evil.example" }, tlsControl),
        host_observation: hostObservation({ dropped: false }),
      },
    });
    assertClosed(controlled, "ENFORCEMENT_GAP", "host_did_not_drop");
  });

  it("denies a TLS mismatch when the supplied control applied and the path is not a quiet host", () => {
    const decision = run({
      policy: { require_tls_peer: true },
      attempt: { tls: Object.assign({ peer_name: "evil.example" }, tlsControl) },
    });
    assert.equal(decision.result, "DENIED");
    assert.equal(decision.reason, "tls_destination_mismatch");
    assert.equal(decision.optimistic_allow, false);
  });

  it("does not allow an unresolved address on an application path that cannot see it", () => {
    const absent = run({
      policy: { blocked_ips: ["203.0.113.9"] },
      attempt: {
        destination: { hostname: "api.openai.com", ip: "198.51.100.10", port: "443", protocol: "https", in_product_scope: true },
      },
    });
    assertClosed(absent, "ENFORCEMENT_GAP", "destination_ip_not_visible");

    const listed = run({
      policy: { blocked_ips: ["203.0.113.9"] },
      attempt: {
        destination: { hostname: "api.openai.com", ip: "203.0.113.9", port: "443", protocol: "https", in_product_scope: true },
      },
    });
    assertClosed(listed, "ENFORCEMENT_GAP", "destination_ip_not_visible");

    const allowed = run({
      policy: { allowed_ips: ["198.51.100.10"] },
      attempt: {
        destination: { hostname: "api.openai.com", ip: "198.51.100.10", port: "443", protocol: "https", in_product_scope: true },
      },
    });
    assertClosed(allowed, "ENFORCEMENT_GAP", "destination_ip_not_visible");
  });

  it("does not allow a safe DNS answer the application path cannot see", () => {
    const mixed = run({
      policy: { blocked_ips: ["198.51.100.9"] },
      attempt: {
        dns: { answers: ["203.0.113.10", "198.51.100.9"], selected: "203.0.113.10" },
      },
    });
    assertClosed(mixed, "ENFORCEMENT_GAP", "dns_answer_not_visible");
    assert.equal(mixed.dimensions.dns.state, "gap");

    const single = run({
      policy: { blocked_ips: ["198.51.100.9"] },
      attempt: { dns: { answers: ["203.0.113.10"] } },
    });
    assertClosed(single, "ENFORCEMENT_GAP", "destination_ip_not_visible");
    assert.equal(single.optimistic_allow, false);
  });

  it("does not clear an empty redirect list or a hop that is not the destination", () => {
    const empty = run({
      attempt: { redirect: { hops: [] } },
    });
    assertClosed(empty, "EVIDENCE_UNAVAILABLE", "redirect_evidence_absent");
    assert.notEqual(empty.dimensions.redirect.state, "clear");

    const mismatch = run({
      policy: { blocked_hosts: ["evil.example"] },
      attempt: { redirect: { hops: [{ hostname: "evil.example" }] } },
    });
    assertClosed(mismatch, "UNKNOWN", "redirect_unclassifiable");
    assert.equal(mismatch.dimensions.redirect.detail, "chain_mismatch");

    const otherChain = run({
      attempt: { redirect: { hops: [{ hostname: "evil.example" }, { hostname: "api.openai.com" }] } },
    });
    assertClosed(otherChain, "UNKNOWN", "redirect_unclassifiable");
  });

  it("does not clear a blocked redirect when the destination has no hostname", () => {
    const quiet = run({
      path: "host_tc_enrolled",
      policy: { blocked_hosts: ["evil.example"] },
      attempt: {
        destination: { ip: "203.0.113.10", port: "443", protocol: "tcp" },
        redirect: { hops: [{ hostname: "evil.example" }] },
        host_observation: hostObservation({ dropped: false, saw: ["destination_ip", "port", "protocol", "redirect"] }),
      },
    });
    assertClosed(quiet, "ENFORCEMENT_GAP", "host_did_not_drop");
    assert.notEqual(quiet.reason, "policy_permits");
    assert.notEqual(quiet.dimensions.redirect.state, "clear");
    assert.notEqual(quiet.dimensions.redirect.detail, "single_hop");

    const dropped = run({
      path: "host_tc_enrolled",
      policy: { blocked_hosts: ["evil.example"] },
      attempt: {
        destination: { ip: "203.0.113.10", port: "443", protocol: "tcp" },
        redirect: { hops: [{ hostname: "evil.example" }] },
        host_observation: hostObservation({ dropped: true, saw: ["destination_ip", "port", "protocol", "redirect"] }),
      },
    });
    assertClosed(dropped, "UNKNOWN", "host_drop_unexplained");
    assert.equal(dropped.dimensions.redirect.state, "unknown");
    assert.notEqual(dropped.dimensions.redirect.state, "clear");
    assert.notEqual(dropped.dimensions.redirect.detail, "single_hop");

    const app = run({
      policy: { blocked_hosts: ["evil.example"] },
      attempt: {
        destination: { ip: "203.0.113.10", port: "443", protocol: "https", in_product_scope: true },
        redirect: { hops: [{ hostname: "evil.example" }] },
      },
    });
    assert.notEqual(app.result, "ALLOWED");
    assert.notEqual(app.reason, "policy_permits");
    assert.equal(app.result, "UNKNOWN");
    assert.equal(app.reason, "redirect_unclassifiable");
    assert.notEqual(app.dimensions.redirect.state, "clear");
    assert.notEqual(app.dimensions.redirect.detail, "single_hop");

    const classified = run({
      path: "host_tc_enrolled",
      policy: { blocked_hosts: ["evil.example"] },
      attempt: {
        destination: { hostname: "api.openai.com", port: "443", protocol: "https" },
        redirect: { hops: [{ hostname: "api.openai.com" }, { hostname: "evil.example" }] },
        host_observation: hostObservation({ dropped: true, saw: ["destination_ip", "port", "protocol", "redirect"] }),
      },
    });
    assert.equal(classified.result, "DENIED");
    assert.equal(classified.reason, "redirect_hop_denied");
    assert.equal(classified.optimistic_allow, false);
  });

  it("does not allow an observed two-hop chain that is not anchored to a hostname", () => {
    const observed = run({
      path: "host_tc_enrolled",
      attempt: {
        destination: { ip: "203.0.113.10", port: "443", protocol: "tcp" },
        redirect: { hops: [{ hostname: "cdn.example" }, { hostname: "img.example" }] },
        host_observation: hostObservation({ dropped: false, saw: ["destination_ip", "port", "protocol", "redirect"] }),
      },
    });
    assertClosed(observed, "UNKNOWN", "redirect_unclassifiable");
    assert.notEqual(observed.reason, "policy_permits");
    assert.notEqual(observed.dimensions.redirect.state, "clear");

    const app = run({
      attempt: {
        destination: { ip: "203.0.113.10", port: "443", protocol: "https", in_product_scope: true },
        redirect: { hops: [{ hostname: "cdn.example" }, { hostname: "img.example" }] },
      },
    });
    assertClosed(app, "UNKNOWN", "redirect_unclassifiable");
  });

  it("keeps a hostname mismatch and an empty hop list off the allow path", () => {
    const mismatch = run({
      policy: { blocked_hosts: ["evil.example"] },
      attempt: {
        destination: { hostname: "203.0.113.10", port: "443", protocol: "https", in_product_scope: true },
        redirect: { hops: [{ hostname: "evil.example" }] },
      },
    });
    assertClosed(mismatch, "UNKNOWN", "redirect_unclassifiable");
    assert.equal(mismatch.dimensions.redirect.detail, "chain_mismatch");

    const empty = run({
      attempt: {
        destination: { hostname: "203.0.113.10", port: "443", protocol: "https", in_product_scope: true },
        redirect: { hops: [] },
      },
    });
    assertClosed(empty, "EVIDENCE_UNAVAILABLE", "redirect_evidence_absent");
    assert.notEqual(empty.dimensions.redirect.state, "clear");
  });

  it("does not treat an allow-list DNS split with no destination IP as missing evidence", () => {
    const destination = { hostname: "api.openai.com", port: "443", protocol: "https", in_product_scope: true };
    const selected = run({
      policy: { allowed_ips: ["203.0.113.9"] },
      attempt: {
        destination,
        dns: { answers: ["203.0.113.9", "198.51.100.9"], selected: "203.0.113.9" },
      },
    });
    assertClosed(selected, "ENFORCEMENT_GAP", "dns_answer_not_visible");
    assert.notEqual(selected.reason, "destination_ip_absent");
    assert.equal(selected.dimensions.dns.state, "gap");

    const open = run({
      policy: { allowed_ips: ["203.0.113.9"] },
      attempt: {
        destination,
        dns: { answers: ["203.0.113.9", "198.51.100.9"] },
      },
    });
    assertClosed(open, "ENFORCEMENT_GAP", "dns_answer_not_visible");
    assert.notEqual(open.reason, "destination_ip_absent");

    const padded = run({
      policy: { blocked_ips: ["203.0.113.9"] },
      attempt: {
        destination: { hostname: "api.openai.com", ip: "203.0.113.009", port: "443", protocol: "https", in_product_scope: true },
      },
    });
    assertClosed(padded, "ENFORCEMENT_GAP", "destination_ip_not_visible");

    const mapped = run({
      policy: { allowed_ips: ["198.51.100.10"] },
      attempt: {
        destination: { hostname: "api.openai.com", ip: "::ffff:198.51.100.10", port: "443", protocol: "https", in_product_scope: true },
      },
    });
    assertClosed(mapped, "ENFORCEMENT_GAP", "destination_ip_not_visible");
  });

  it("still allows a single hop that is the destination", () => {
    const decision = run({
      attempt: { redirect: { hops: [{ hostname: "api.openai.com" }] } },
    });
    assert.equal(decision.result, "ALLOWED");
    assert.equal(decision.optimistic_allow, false);
    assert.equal(decision.dimensions.redirect.state, "clear");
    assert.equal(decision.dimensions.redirect.detail, "single_hop");
  });

  it("denies normalized spellings of an exact blocked address when the host dropped", () => {
    for (const ip of ["203.0.113.009", "::ffff:203.0.113.9", "::FFFF:203.0.113.009"]) {
      const decision = run({
        path: "host_tc_enrolled",
        policy: { blocked_ips: ["203.0.113.9"] },
        attempt: {
          destination: { ip, port: "443", protocol: "tcp" },
          host_observation: hostObservation({ dropped: true }),
        },
      });
      assert.equal(decision.result, "DENIED", ip);
      assert.equal(decision.reason, "host_not_permitted");
      assert.equal(decision.optimistic_allow, false);
      assert.notEqual(decision.result, "ALLOWED");
    }
  });

  it("does not allow a normalized blocked address when the host did not drop", () => {
    const canonical = run({
      path: "host_tc_enrolled",
      policy: { blocked_ips: ["203.0.113.9"] },
      attempt: {
        destination: { ip: "203.0.113.9", port: "443", protocol: "tcp" },
        host_observation: hostObservation({ dropped: false }),
      },
    });
    for (const ip of ["203.0.113.009", "::ffff:203.0.113.9"]) {
      const decision = run({
        path: "host_tc_enrolled",
        policy: { blocked_ips: ["203.0.113.9"] },
        attempt: {
          destination: { ip, port: "443", protocol: "tcp" },
          host_observation: hostObservation({ dropped: false }),
        },
      });
      assertClosed(decision, canonical.result, canonical.reason);
      assert.equal(decision.reason, "host_did_not_drop");
    }
  });

  it("matches a mapped address against the same CIDR integer", () => {
    const decision = run({
      path: "host_tc_enrolled",
      policy: { blocked_ips: ["203.0.113.0/25"] },
      attempt: {
        destination: { ip: "::ffff:203.0.113.127", port: "443", protocol: "tcp" },
        host_observation: hostObservation({ dropped: true }),
      },
    });
    assert.equal(decision.result, "DENIED");
    assert.equal(decision.reason, "host_not_permitted");
    assert.equal(decision.optimistic_allow, false);
  });

  it("does not record a host deny when the observation did not drop", () => {
    const redirect = run({
      path: "host_tc_enrolled",
      policy: { blocked_hosts: ["evil.example"] },
      attempt: {
        destination: { hostname: "api.openai.com", port: "443", protocol: "https" },
        redirect: { hops: [{ hostname: "api.openai.com" }, { hostname: "evil.example" }] },
        host_observation: hostObservation({ dropped: false, saw: ["destination_ip", "port", "protocol", "redirect"] }),
      },
    });
    assertClosed(redirect, "ENFORCEMENT_GAP", "host_did_not_drop");
    assert.notEqual(redirect.reason, "redirect_hop_denied");

    const port = run({
      path: "host_tc_enrolled",
      policy: { denied_ports: ["443"] },
      attempt: {
        destination: { hostname: "api.openai.com", port: "443", protocol: "tcp" },
        host_observation: hostObservation({ dropped: false }),
      },
    });
    assertClosed(port, "ENFORCEMENT_GAP", "host_did_not_drop");
    assert.notEqual(port.reason, "port_not_permitted");

    const protocol = run({
      path: "host_tc_enrolled",
      policy: { denied_protocols: ["tcp"] },
      attempt: {
        destination: { hostname: "api.openai.com", port: "443", protocol: "tcp" },
        host_observation: hostObservation({ dropped: false }),
      },
    });
    assertClosed(protocol, "ENFORCEMENT_GAP", "host_did_not_drop");
  });

  it("catches the optimistic allows while optimistic_allow stays false", () => {
    const cases = [
      {
        policy: { require_tls_peer: true },
        attempt: { tls: { peer_name: "api.openai.com" } },
      },
      {
        path: "host_tc_enrolled",
        policy: { require_tls_peer: true },
        attempt: {
          destination: { hostname: "api.openai.com", ip: "203.0.113.10", port: "443", protocol: "tcp" },
          tls: { peer_name: "api.openai.com" },
          host_observation: hostObservation({ dropped: false }),
        },
      },
      {
        policy: { blocked_ips: ["203.0.113.9"] },
        attempt: {
          destination: { hostname: "api.openai.com", ip: "198.51.100.10", port: "443", protocol: "https", in_product_scope: true },
        },
      },
      {
        policy: { allowed_ips: ["198.51.100.10"] },
        attempt: {
          destination: { hostname: "api.openai.com", ip: "198.51.100.10", port: "443", protocol: "https", in_product_scope: true },
        },
      },
      {
        policy: { blocked_ips: ["198.51.100.9"] },
        attempt: { dns: { answers: ["203.0.113.10", "198.51.100.9"], selected: "203.0.113.10" } },
      },
      {
        policy: { blocked_ips: ["198.51.100.9"] },
        attempt: { dns: { answers: ["203.0.113.10"] } },
      },
      { attempt: { redirect: { hops: [] } } },
      {
        policy: { blocked_hosts: ["evil.example"] },
        attempt: { redirect: { hops: [{ hostname: "evil.example" }] } },
      },
      {
        path: "host_tc_enrolled",
        policy: { blocked_ips: ["203.0.113.9"] },
        attempt: {
          destination: { ip: "203.0.113.009", port: "443", protocol: "tcp" },
          host_observation: hostObservation({ dropped: false }),
        },
      },
      {
        path: "host_tc_enrolled",
        policy: { blocked_ips: ["203.0.113.9"] },
        attempt: {
          destination: { ip: "::ffff:203.0.113.9", port: "443", protocol: "tcp" },
          host_observation: hostObservation({ dropped: false }),
        },
      },
      {
        path: "host_tc_enrolled",
        policy: { blocked_hosts: ["evil.example"] },
        attempt: {
          destination: { ip: "203.0.113.10", port: "443", protocol: "tcp" },
          redirect: { hops: [{ hostname: "evil.example" }] },
          host_observation: hostObservation({ dropped: false, saw: ["destination_ip", "port", "protocol", "redirect"] }),
        },
      },
      {
        policy: { blocked_hosts: ["evil.example"] },
        attempt: {
          destination: { ip: "203.0.113.10", port: "443", protocol: "https", in_product_scope: true },
          redirect: { hops: [{ hostname: "evil.example" }] },
        },
      },
      {
        path: "host_tc_enrolled",
        attempt: {
          destination: { ip: "203.0.113.10", port: "443", protocol: "tcp" },
          redirect: { hops: [{ hostname: "cdn.example" }, { hostname: "img.example" }] },
          host_observation: hostObservation({ dropped: false, saw: ["destination_ip", "port", "protocol", "redirect"] }),
        },
      },
      {
        policy: { allowed_ips: ["203.0.113.9"] },
        attempt: {
          destination: { hostname: "api.openai.com", port: "443", protocol: "https", in_product_scope: true },
          dns: { answers: ["203.0.113.9", "198.51.100.9"], selected: "203.0.113.9" },
        },
      },
      {
        policy: { allowed_ips: ["203.0.113.9"] },
        attempt: {
          destination: { hostname: "api.openai.com", port: "443", protocol: "https", in_product_scope: true },
          dns: { answers: ["203.0.113.9", "198.51.100.9"] },
        },
      },
    ];
    for (const fields of cases) {
      const decision = run(fields);
      assert.equal(decision.optimistic_allow, false);
      assert.notEqual(decision.result, "ALLOWED");
    }
  });
});
