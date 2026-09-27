"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const composition = require("../../internal/enterprise-runtime-integration/src/index.cjs");
const eg = require("../../internal/enterprise-governance/src/index.cjs");
const { envelope, grantInput, world } = require("../enterprise-e1-e3/fixture.cjs");
const { attempt, policy } = require("../pe-egress/fixture.cjs");
const { baseInput, OPTIONS } = require("../shared-health-runtime/helpers.cjs");

function opened() {
  const { store } = world();
  return composition.createComposition({ store, now: () => 5000 });
}

test("promotion flags are refused before the record store changes", () => {
  const comp = composition.createComposition({ now: () => 5000 });
  const flags = [
    "live_customer_authority",
    "customer_deploy",
    "promote_record",
    "host_attachment",
    "attach_host",
    "enroll",
    "load_ebpf",
    "publish",
    "announce",
    "issue_credentials",
    "reopen_frozen",
    "frozen_cli_reopened",
    "mark_host_enrolled",
  ];
  for (const flag of flags) {
    const request = { op: "accept_identity", input: { id: "root-a", kind: "customer" } };
    request[flag] = true;
    const refused = composition.integrate(comp, request);
    assert.equal(refused.ok, false, flag);
    assert.equal(refused.code, "PROMOTION_REFUSED", flag);
    assert.equal(refused.live_customer_authority, false, flag);
    assert.equal(comp.store.identities.size, 0, flag);
    assert.equal(comp.published, false, flag);
    assert.equal(comp.announced, false, flag);
    assert.equal(comp.frozen_version_reopened, false, flag);
    assert.equal(comp.credentials_issued, false, flag);
  }
});

test("an enroll intent that asks to set enrolled is refused before the intent list grows", () => {
  const comp = opened();
  const before = comp.store.host_intents.length;
  const refused = composition.integrate(comp, {
    op: "host_intent",
    input: {
      class: "ROOT",
      parties: ["root-a"],
      intent: "enroll",
      host_id: "h1",
      enrolled: true,
    },
  });
  assert.equal(refused.code, "PROMOTION_REFUSED");
  assert.equal(comp.store.host_intents.length, before);
  assert.equal(comp.pe.host_attachment, false);
  assert.equal(comp.pe.ebpf_loaded, false);
});

test("a nested PE attachment flag does not run the runtime", () => {
  const comp = opened();
  const before = comp.pe.contributions.length;
  const refused = composition.integrate(comp, {
    op: "pe",
    pe: {
      op: "egress",
      load_ebpf: true,
      input: {
        policy: policy({ blocked_hosts: ["evil.example"] }),
        path: { id: "app_fetch" },
        attempt: attempt({
          destination: { hostname: "evil.example", port: "443", protocol: "https", in_product_scope: true },
        }),
      },
    },
  });
  assert.equal(refused.code, "PROMOTION_REFUSED");
  assert.equal(comp.pe.contributions.length, before);
  assert.equal(comp.pe.ebpf_loaded, false);
  assert.equal(composition.snapshot(comp).planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
});

test("a joint call that asks for live authority does not run the PE step", () => {
  const comp = opened();
  const version = comp.store.root.policy_version;
  const joined = composition.compose(comp, {
    enterprise: {
      op: "policy",
      live_customer_authority: true,
      input: {
        class: "NARROW",
        parties: ["root-a"],
        next_policy: envelope({ spend_cap: 20 }),
      },
    },
    pe: {
      op: "health",
      input: baseInput(),
      options: OPTIONS,
    },
  });
  assert.equal(joined.ok, false);
  assert.equal(joined.code, "PROMOTION_REFUSED");
  assert.equal(comp.store.root.policy_version, version);
  assert.equal(comp.pe.contributions.length, 0);
  assert.equal(comp.live_customer_authority, false);
});

test("vantio cannot found the root through the composition", () => {
  const comp = composition.createComposition({ now: () => 5000 });
  composition.integrate(comp, { op: "accept_identity", input: { id: "vantio", kind: "vantio" } });
  const founded = composition.integrate(comp, {
    op: "found_root",
    input: {
      root_identity: "vantio",
      authority_ceiling: envelope(),
      initial_policy: envelope(),
    },
  });
  assert.equal(founded.ok, true);
  assert.equal(founded.quote.outcome, "REJECTED");
  assert.equal(founded.child.reason, "VANTIO_NOT_IN_ROOT_SET");
  assert.equal(founded.child.live_customer_authority, false);
  assert.equal(comp.store.root, null);
  assert.equal(founded.planes.HOST_ENFORCEMENT.applied, false);
});

test("a rejected host mark and an enterprise writer quote do not verify a host", () => {
  const comp = opened();
  const version = comp.store.root.policy_version;
  const marked = composition.integrate(comp, {
    op: "policy",
    input: {
      act: "mark_host_protected",
      class: "NARROW",
      parties: ["root-a"],
      next_policy: envelope({ spend_cap: 40 }),
    },
  });
  assert.equal(marked.quote.outcome, "REJECTED");
  assert.equal(marked.child.reason, "MARK_HOST_PROTECTED");
  assert.equal(comp.store.root.policy_version, version);
  assert.equal(marked.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
  const granted = composition.integrate(comp, { op: "grant", input: grantInput() });
  assert.equal(granted.ok, true);
  const quoted = composition.integrate(comp, {
    op: "quote_host",
    input: {
      source: "enterprise_writer",
      subject_id: granted.child.grant_id,
      quoted_outcome: "ACTIVE",
      envelope_version: granted.child.grant_id ? comp.store.root.policy_version : 1,
    },
  });
  assert.equal(quoted.quote.outcome, "REJECTED");
  assert.equal(quoted.child.verified_on_host, false);
  assert.equal(quoted.child.host_contacted, false);
  assert.equal(quoted.planes.DECISION.status, "REJECTED");
  assert.equal(quoted.planes.HOST_ENFORCEMENT.applied, false);
});

test("a foreign store and a second composition stay isolated", () => {
  const comp = opened();
  const other = eg.createCustomerHeldStore();
  const mismatch = composition.integrate(comp, {
    op: "freeze",
    input: { store: other, parties: ["root-a"] },
  });
  assert.equal(mismatch.code, "STORE_MISMATCH");
  assert.equal(comp.store.freeze, null);
  const left = composition.createComposition({ now: () => 1 });
  const right = composition.createComposition({ now: () => 1 });
  composition.integrate(left, { op: "accept_identity", input: { id: "root-a", kind: "customer" } });
  assert.equal(right.store.identities.has("root-a"), false);
  assert.equal(left.live_customer_authority, false);
  assert.equal(right.host_attachment, false);
});

test("the honesty gate rejects a smuggled live-authority flag", () => {
  const problems = composition.sealEnterpriseChild({
    live_customer_authority: true,
    execution: "EVALUATE_ONLY",
    intent: { enrolled: true, protected: false, enforced: false },
  });
  assert.equal(problems.includes("live_customer_authority"), true);
  assert.equal(problems.includes("intent.enrolled"), true);
  assert.deepEqual(composition.sealEnterpriseChild({
    live_customer_authority: false,
    host_contacted: false,
    verified_on_host: false,
    kernel_executed: false,
    host_attachment: false,
    applied_to_host: false,
    active_protection: false,
  }), []);
});

test("an enforcement gap stays a gap beside an approved record", () => {
  const comp = opened();
  const joined = composition.compose(comp, {
    enterprise: {
      op: "policy",
      input: {
        class: "NARROW",
        parties: ["root-a"],
        next_policy: envelope({ spend_cap: 25 }),
      },
    },
    pe: {
      op: "egress",
      input: { policy: policy(), path: { id: "app_raw_syscall" }, attempt: attempt() },
    },
  });
  assert.equal(joined.ok, true);
  assert.equal(joined.enterprise.quote.outcome, "APPROVED");
  assert.equal(joined.pe.quote.result, "ENFORCEMENT_GAP");
  assert.equal(joined.planes.DECISION.status, "SEPARATED");
  assert.equal(joined.planes.APPLICATION_ENFORCEMENT.status, "GAP");
  assert.equal(joined.planes.APPLICATION_ENFORCEMENT.applied, false);
  assert.equal(joined.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(joined.active_protection, false);
  assert.equal(joined.live_customer_authority, false);
});

test("integrateAll stops after a promotion refusal", () => {
  const comp = composition.createComposition({ now: () => 5000 });
  const batch = composition.integrateAll(comp, [
    { op: "accept_identity", input: { id: "root-a", kind: "customer" } },
    { op: "accept_identity", publish: true, input: { id: "cust-b", kind: "customer" } },
    { op: "accept_identity", input: { id: "cust-c", kind: "customer" } },
  ]);
  assert.equal(batch.ok, false);
  assert.equal(batch.contributions.length, 2);
  assert.equal(batch.live_customer_authority, false);
  assert.equal(comp.store.identities.has("root-a"), true);
  assert.equal(comp.store.identities.has("cust-b"), false);
  assert.equal(comp.store.identities.has("cust-c"), false);
  assert.equal(batch.snapshot.published, false);
  assert.equal(batch.snapshot.planes.HOST_ENFORCEMENT.applied, false);
});
