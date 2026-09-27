"use strict";

const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const { BASE, REGISTERS, assess, withoutAuthority } = require("./assess.cjs");

const ROOT = path.resolve(__dirname, "../..");
const ENTRY = path.join(ROOT, "docs/programs/production-readiness/authority/WAVE2-AUTHORITY.json");

function loadAuthority() {
  return JSON.parse(fs.readFileSync(ENTRY, "utf8"));
}

function expectCode(mutate, code) {
  const copy = structuredClone(loadAuthority());
  mutate(copy);
  const errors = assess(copy);
  assert.equal(errors.includes(code), true, `${code} missing from ${errors.join(",")}`);
}

function truth(copy, id) {
  return copy.truths.find((item) => item.id === id);
}

test("a HOLD on the published 3.1.0 cut fails", () => {
  expectCode((copy) => {
    truth(copy, "python-3.1.0-exact-hash-publication").hold = true;
  }, "PYTHON_HOLD");
  expectCode((copy) => {
    truth(copy, "python-3.1.0-exact-hash-publication").authority = "HOLD";
  }, "PYTHON_AUTHORITY");
});

test("a fresh publication proof or a further cut fails", () => {
  expectCode((copy) => {
    truth(copy, "python-3.1.0-exact-hash-publication").new_registry_observation = true;
  }, "PYTHON_OBSERVATION");
  expectCode((copy) => {
    truth(copy, "python-3.1.0-exact-hash-publication").another_cut_authorized = true;
  }, "PYTHON_CUT");
  expectCode((copy) => {
    truth(copy, "python-3.1.0-exact-hash-publication").bytes_mutated = true;
  }, "PYTHON_BYTES");
});

test("founder-blocking Units D and E, or calling the reader-compat gate passed, fails", () => {
  expectCode((copy) => {
    truth(copy, "units-d-e").founder_blocked = true;
  }, "UNITS_FOUNDER_BLOCK");
  expectCode((copy) => {
    truth(copy, "units-d-e").gate = "founder";
  }, "UNITS_GATE");
  expectCode((copy) => {
    truth(copy, "units-d-e").gate_adjudicated = true;
  }, "UNITS_ADJUDICATED");
  expectCode((copy) => {
    copy.reader_compat_evidence.gate_passed = true;
  }, "UNITS_ADJUDICATED");
  expectCode((copy) => {
    truth(copy, "units-d-e").writers_activated = true;
  }, "UNITS_ACTIVATED");
});

test("founder-blocking O7, or claiming Option C revalidation, fails", () => {
  expectCode((copy) => {
    truth(copy, "o7").founder_blocked = true;
  }, "O7_FOUNDER_BLOCK");
  expectCode((copy) => {
    truth(copy, "o7").revalidation_adjudicated = true;
  }, "O7_ADJUDICATED");
  expectCode((copy) => {
    truth(copy, "o7").store_created = true;
  }, "O7_STORE");
  expectCode((copy) => {
    truth(copy, "o7").gate_8_opened = true;
  }, "O7_GATE8");
});

test("closing the internal demo, enabling I3, or granting live customer authority fails", () => {
  expectCode((copy) => {
    truth(copy, "investor-demo-wave-2").authority = "NOT_AUTHORIZED";
  }, "DEMO_AUTHORITY");
  expectCode((copy) => {
    truth(copy, "investor-demo-wave-2").readiness_reclassified = true;
  }, "DEMO_READINESS");
  expectCode((copy) => {
    truth(copy, "i3").default = "ENABLED";
  }, "I3_DEFAULT");
  expectCode((copy) => {
    truth(copy, "i3").enabled = true;
  }, "I3_ENABLED");
  expectCode((copy) => {
    truth(copy, "enterprise-e1-e3").live_customer_authority = true;
  }, "ENTERPRISE_CUSTOMER");
  expectCode((copy) => {
    truth(copy, "enterprise-e1-e3").customer_deploy = true;
  }, "CUSTOMER_DEPLOY");
  expectCode((copy) => {
    truth(copy, "enterprise-e1-e3").council_pass_claimed = true;
  }, "COUNCIL");
});

test("a changed, dropped, or extra WS11 label fails", () => {
  expectCode((copy) => {
    copy.ws11_items[0].label = "pinning and signing";
  }, "WS11_LABEL");
  expectCode((copy) => {
    copy.ws11_items.pop();
  }, "WS11_ITEMS");
  expectCode((copy) => {
    copy.ws11_items.push({ id: "R19", label: "invented scope" });
  }, "WS11_ITEMS");
  expectCode((copy) => {
    truth(copy, "ws11").status = "NOT_RETRIEVED";
  }, "WS11_STATUS");
  expectCode((copy) => {
    truth(copy, "ws11").implemented = true;
  }, "WS11_IMPLEMENTED");
  expectCode((copy) => {
    copy.ws11_definition_source.expanded_specs_retrieved = true;
  }, "WS11_EXPANDED");
});

test("opening stranger-host execution or announcements fails", () => {
  expectCode((copy) => {
    truth(copy, "stranger-host-execution").state = "AUTHORIZED";
  }, "STRANGER_STATE");
  expectCode((copy) => {
    truth(copy, "stranger-host-execution").pending = ["named_host"];
  }, "STRANGER_PENDING");
  expectCode((copy) => {
    truth(copy, "stranger-host-execution").executed = true;
  }, "STRANGER_EXECUTED");
  expectCode((copy) => {
    truth(copy, "announcements").state = "CLEARED";
  }, "ANNOUNCEMENTS");
  expectCode((copy) => {
    copy.closed.find((item) => item.id === "announcements").state = "CLEARED";
  }, "ANNOUNCEMENTS");
  expectCode((copy) => {
    copy.closed.find((item) => item.id === "customer-deploy").state = "AUTHORIZED";
  }, "CLOSED_OPENED");
});

test("a different Wave 1 pin, titled letters, or a provenance claim fails", () => {
  expectCode((copy) => {
    truth(copy, "wave-1").accepted_main_sha = "601342f08a59798ce207840cfb75293c3c22f45c";
  }, "WAVE1_SHA");
  expectCode((copy) => {
    truth(copy, "wave-1").letters_titled = true;
  }, "WAVE1_LETTERS");
  expectCode((copy) => {
    copy.provenance_claims.formal_slsa = true;
  }, "PROVENANCE");
  expectCode((copy) => {
    copy.provenance_claims.certification = true;
  }, "PROVENANCE");
  expectCode((copy) => {
    copy.provenance_claims.reproducibility_proved = true;
  }, "PROVENANCE");
});

test("rewriting history, merging, inventing WS0, or sitting council fails", () => {
  expectCode((copy) => {
    copy.historical_packets_rewritten = true;
  }, "HISTORY_REWRITTEN");
  expectCode((copy) => {
    copy.merges = true;
  }, "MERGE");
  expectCode((copy) => {
    copy.ws0.title_defined_by_this_entry = true;
  }, "WS0_INVENTED");
  expectCode((copy) => {
    copy.standing_auth_scopes_named_only[0].packet_defined_here = true;
  }, "SCOPE_INVENTED");
  expectCode((copy) => {
    copy.council.status = "PASS";
    copy.council.verdict = "PASS";
  }, "COUNCIL");
  expectCode((copy) => {
    copy.truths.push({ id: "invented", authority: "AUTHORIZED" });
  }, "TRUTH_SET");
});

test("editing a historical decision is drift against the accepted main", () => {
  const raw = execFileSync("git", ["show", `${BASE}:${REGISTERS[2]}`], {
    cwd: ROOT,
    encoding: "utf8",
  });
  const base = JSON.parse(raw);
  const current = structuredClone(base);
  current.superseding_authority = { id: "AUTH-WAVE2-2026-09-27" };
  assert.deepEqual(withoutAuthority(current), base);
  current.decisions.find((item) => item.id === "DEC-009").decision = "WS11 is defined.";
  assert.notDeepEqual(withoutAuthority(current), base);
});
