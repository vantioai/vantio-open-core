"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const { execFileSync } = require("node:child_process");
const test = require("node:test");

const ROOT = path.resolve(__dirname, "../..");
const HOME = path.join(ROOT, "docs/planning/shared-health-vocabulary");

function readJson(rel) {
  return JSON.parse(fs.readFileSync(path.join(ROOT, rel), "utf8"));
}

function readText(rel) {
  return fs.readFileSync(path.join(ROOT, rel), "utf8");
}

const catalog = readJson("docs/planning/shared-health-vocabulary/HEALTH-VOCABULARY.json");
const matrix = readJson("docs/planning/shared-health-vocabulary/COLLISION-MATRIX.json");
const pe = readJson("docs/planning/phantom-engine-production/HEALTH-VOCABULARY.json");
const tokens = readJson("docs/governance/STATUS-TOKENS.json");

function checkFact(fact) {
  const errors = [];
  const fields = catalog.fields;
  if (fact.record_type !== "SHARED_HEALTH_FACT") errors.push("RECORD_TYPE");
  if (!catalog.subjects.includes(fact.subject)) errors.push("SUBJECT_ENUM");
  if (!catalog.fact_kinds.includes(fact.fact_kind)) errors.push("FACT_KIND_ENUM");
  if (fact.freshness !== "UNKNOWN") errors.push("FRESHNESS_EMITTED");

  for (const [field, gate] of Object.entries(catalog.fact_rules.field_gates)) {
    const value = fact[field];
    if (fact.fact_kind === gate.fact_kind) {
      if (gate.subjects && !gate.subjects.includes(fact.subject)) errors.push(gate.subject_error);
      if (Object.prototype.hasOwnProperty.call(gate, "exact") && value !== gate.exact) {
        errors.push(gate.exact_error);
      }
      if (gate.enum_field && !fields[gate.enum_field].values.includes(value)) errors.push(gate.enum_error);
    } else if (value !== null) {
      errors.push(gate.null_error);
    }
  }

  for (const [field, code] of Object.entries(catalog.fact_rules.optional_enums)) {
    const value = fact[field];
    if (value !== null && !fields[field].values.includes(value)) errors.push(code);
  }

  const control = catalog.fact_rules.control_plane;
  if (fact.fact_kind === control.fact_kind) {
    if (fact.subject !== control.subject) errors.push(control.subject_error);
    if (fact.interval_s !== control.interval_s) errors.push(control.interval_error);
  } else if (fact.interval_s !== null) {
    errors.push(control.null_error);
  }

  return errors.sort();
}

test("catalog is a design draft and does not bind the PE packet", () => {
  assert.equal(catalog.schema_status, "0.1.0-design");
  assert.equal(catalog.stable_schema, false);
  assert.equal(catalog.producer_classification, "SHARED_HEALTH_VOCABULARY_READY_FOR_COUNCIL");
  assert.equal(catalog.vocabulary_status, "WS4_CATALOG_DRAFT");
  assert.equal(catalog.bound_into_pe_packet, false);
  assert.equal(catalog.pe_packet_vocabulary_status, "PENDING_WS4");
  assert.equal(catalog.pe_packet_workstream_4, "DEFINITION_NOT_RETRIEVED");
  assert.equal(catalog.subject_extension, "NONE");
  assert.equal(catalog.hard_stops.live_probe, false);
  assert.equal(catalog.hard_stops.live_ebpf_load, false);
  assert.equal(catalog.hard_stops.stranger_host_execution, false);
  assert.equal(catalog.hard_stops.customer_deploy, false);
  assert.equal(catalog.hard_stops.unit_d_writer, false);
  assert.equal(catalog.hard_stops.unit_e_writer, false);
  assert.equal(catalog.hard_stops.optics_store_write, false);
  assert.equal(catalog.hard_stops.i3_otel_adapter, false);
  assert.equal(catalog.hard_stops.customer_confidential_bodies_copied, false);
  assert.equal(catalog.hard_stops.merge_authorized, false);
  assert.equal(catalog.hard_stops.self_certified_council_pass, false);
  assert.equal(catalog.frozen_surfaces.unit_d, "NOT_AUTHORIZED");
  assert.equal(catalog.frozen_surfaces.unit_e, "NOT_AUTHORIZED");
  assert.equal(catalog.frozen_surfaces.o7, "NOT_AUTHORIZED");
  assert.equal(catalog.frozen_surfaces.i3, "NOT_AUTHORIZED");
});

test("subjects and layer enums match the PE packet already on main", () => {
  assert.deepEqual(catalog.subjects, pe.subjects);
  assert.deepEqual(catalog.fields.protection_state.values, pe.protection_state);
  assert.deepEqual(catalog.fields.verifier_result.values, pe.verifier_result);
  assert.deepEqual(catalog.fields.evidence_class.values, pe.evidence_class);
  assert.deepEqual(catalog.fields.platform_scope.values, pe.platform_scope);
  assert.deepEqual(catalog.fields.platform_status.values, pe.platform_status);
  assert.deepEqual(catalog.fields.deployment_profile.values, pe.deployment_profile);
  assert.equal(catalog.heartbeat.age_limit_s, pe.heartbeat_age_limit_s);
  assert.equal(catalog.heartbeat.path_in_manifests, pe.heartbeat_path_in_manifests);
  assert.equal(pe.vocabulary_status, "c1de02538f66df94d58aef58bf0ec8459ae797ad");
  assert.equal(pe.workstream_4, pe.vocabulary_status);
  assert.equal(pe.binding_classification, "PE_WS4_VOCABULARY_BINDING_READY_FOR_COUNCIL");
  assert.equal(pe.binding.vocabulary_status_meaning, "BOUND_TO_WS4_CATALOG");
  assert.equal(pe.binding.workstream_4_meaning, "RETRIEVED_AND_BOUND");
  assert.equal(pe.binding.catalog_path, "docs/planning/shared-health-vocabulary/");
  assert.equal(pe.binding.catalog_commit, pe.vocabulary_status);
  assert.equal(pe.binding.catalog_merge_commit, "52274708e2620cbd37b0d10d67561eac642e2aee");
  assert.equal(pe.binding.catalog_pull_request, 82);
  assert.equal(pe.binding.catalog_council, "SHARED_HEALTH_VOCABULARY_COUNCIL_PASSED");
  assert.equal(pe.binding.catalog_council_agent, "bc-84572b17");
  assert.equal(pe.binding.catalog_merge_classification, "SHARED_HEALTH_VOCABULARY_MERGED_CATALOG_ONLY");
  assert.equal(pe.binding.bound_into_pe_packet_at_cited_commit, false);
  assert.equal(pe.binding.freshness_rule, "FRESHNESS_WINDOW_NOT_SET_EMIT_UNKNOWN");
  assert.equal(pe.freshness, "UNKNOWN");
  assert.deepEqual(pe.collision_rules.slice(0, 6), [
    "verifier_result BLOCKED is a separate field from ledger ActionTaken BLOCKED",
    "wire ActionTaken OBSERVED is not protection_state protected",
    "OPTIONAL_COMPONENT_ABSENT is not verifier_result PASS",
    "coverage_unknown is not protection_state protected",
    "KIND_LOCAL is not MANAGED_CLOUD",
    "internally_proven is not STRANGER_HOST",
  ]);
  assert.equal(
    pe.collision_rules[6],
    "freshness stays UNKNOWN under FRESHNESS_WINDOW_NOT_SET_EMIT_UNKNOWN",
  );
  const peManifest = readJson("docs/planning/phantom-engine-production/PLANNING-MANIFEST.json");
  assert.equal(peManifest.vocabulary_status, pe.vocabulary_status);
  assert.equal(peManifest.workstream_4, pe.workstream_4);
  for (const [rel, expected] of Object.entries(peManifest.files_sha256)) {
    const digest = crypto.createHash("sha256").update(fs.readFileSync(path.join(ROOT, rel))).digest("hex");
    assert.equal(digest, expected, rel);
  }
  const peHash = crypto.createHash("sha256").update(fs.readFileSync(path.join(ROOT, catalog.pe_packet_path))).digest("hex");
  assert.equal(catalog.pe_packet_sha256, "a2592a2496f65897c3258106f3bc187d8efb16e9b3d6c53a54c099163e8e3cd1");
  assert.notEqual(peHash, catalog.pe_packet_sha256);
  execFileSync("git", ["merge-base", "--is-ancestor", pe.vocabulary_status, "HEAD"], { cwd: ROOT, stdio: "ignore" });
});

test("Layer A display and action tokens stay the status-token file", () => {
  assert.deepEqual(catalog.fields.optics_display.values, tokens.display_tokens);
  assert.deepEqual(catalog.fields.sdk_action.values, tokens.action_tokens);
  assert.equal(catalog.fields.optics_display.values.includes("SUCCESS"), true);
  assert.equal(catalog.optics_reader_display.renders_success, false);
  assert.equal(catalog.optics_reader_display.stored_success_becomes, "UNAVAILABLE");
  assert.equal(catalog.optics_reader_display.does_not_remove_success_from_optics_display, true);
});

test("protection states stay disjoint from Optics and verifier tokens", () => {
  for (const pair of catalog.disjoint_value_sets) {
    const left = new Set(catalog.fields[pair[0]].values);
    const right = new Set(catalog.fields[pair[1]].values);
    const overlap = [...left].filter((value) => right.has(value));
    assert.deepEqual(overlap, [], pair.join(" "));
  }
  for (const name of catalog.fields.product_health_name.values) {
    assert.equal(catalog.fields.protection_state.values.includes(name), false, name);
  }
});

test("freshness window is NOT_SET and CURRENT is not emitted", () => {
  assert.equal(catalog.freshness.rule_id, "FRESHNESS_WINDOW_NOT_SET_EMIT_UNKNOWN");
  assert.equal(catalog.freshness.window, "NOT_SET");
  assert.equal(catalog.freshness.window_seconds, null);
  assert.deepEqual(catalog.freshness.emitted_values, ["UNKNOWN"]);
  assert.deepEqual(catalog.freshness.reserved_not_emitted, ["CURRENT", "HISTORICAL", "STALE"]);
  assert.equal(catalog.freshness.heartbeat_is_not_freshness, true);
  assert.equal(catalog.heartbeat.age_limit_s, 60);
  assert.equal(catalog.control_plane_heartbeat.interval_s, "NOT_COPIED");
  assert.equal(catalog.ledger_plane.worm_token, "NOT_A_CATALOG_VALUE");
  const values = [];
  for (const spec of Object.values(catalog.fields)) values.push(...spec.values);
  values.push(...catalog.freshness.emitted_values);
  assert.equal(values.includes("WORM"), false);
  assert.equal(values.includes("CURRENT"), false);
  assert.equal(catalog.fields.coverage_percent, undefined);
  assert.equal(catalog.aliases, undefined);
});

test("fact kinds are the closed discriminator set", () => {
  const expected = new Set(
    Object.values(catalog.fact_rules.field_gates).map((gate) => gate.fact_kind),
  );
  expected.add(catalog.fact_rules.control_plane.fact_kind);
  expected.add("EVIDENCE_LABEL");
  expected.add("OTHER");
  assert.deepEqual(catalog.fact_kinds.slice().sort(), [...expected].sort());
  assert.equal(catalog.fact_kinds.includes("OPTICS"), false);
});

test("valid facts pass and rejected facts hit the named rule", () => {
  const seen = new Set();
  for (const example of catalog.examples) {
    assert.equal(seen.has(example.id), false, example.id);
    seen.add(example.id);
    assert.deepEqual(checkFact(example.fact), [], example.id);
  }
  for (const example of catalog.rejected_examples) {
    assert.equal(seen.has(example.id), false, example.id);
    seen.add(example.id);
    assert.deepEqual(checkFact(example.fact), example.violates.slice().sort(), example.id);
  }
});

test("forbidden crosswalks keep the Workstream 3 pairs", () => {
  function has(fromField, fromValue, toField, toValue) {
    return catalog.forbidden_crosswalks.some((pair) => {
      return pair.from.field === fromField
        && pair.from.value === fromValue
        && pair.to.field === toField
        && (toValue === undefined || pair.to.value === toValue);
    });
  }
  assert.equal(has("optics_display", "OBSERVED", "protection_state", "protected"), true);
  assert.equal(has("verifier_result", "BLOCKED", "ledger_action_taken", "BLOCKED"), true);
  assert.equal(has("verifier_result", "OPTIONAL_COMPONENT_ABSENT", "verifier_result", "PASS"), true);
  assert.equal(has("platform_scope", "KIND_LOCAL", "platform_scope", "MANAGED_CLOUD"), true);
  assert.equal(has("compatibility_status", "internally_proven", "platform_scope", "STRANGER_HOST"), true);
  assert.equal(has("freshness", "CURRENT", "heartbeat_age_limit_s", 60), true);
  assert.equal(has("protection_state", "coverage_unknown", "protection_state", "protected"), true);
  assert.equal(has("optics_display", "PARTIAL", "coverage_percent"), true);
  assert.equal(has("application_status", "SUCCESS", "optics_display", "SUCCESS"), true);
});

test("cited open-core tokens appear in the source files", () => {
  const a5 = readText("docs/architecture/optics-foundation/06-SELF-OBSERVABILITY-AND-RELIABILITY.md");
  const a4 = readText("docs/architecture/optics-foundation/05-CORRELATION-AND-QUERY-CONTRACT.md");
  const decision = readText("docs/architecture/optics-foundation/08-ARCHITECTURE-DECISION-PACK.md");
  const prose = readText("docs/planning/phantom-engine-production/05-SHARED-HEALTH-VOCABULARY.md");
  for (const name of catalog.fields.product_health_name.values) assert.ok(a5.includes(name), name);
  for (const name of catalog.fields.migration_state.values) assert.ok(a5.includes(name), name);
  for (const name of catalog.fields.telemetry_last_result.values) assert.ok(a5.includes(name), name);
  for (const name of catalog.fields.run_lifecycle.values) assert.ok(a5.includes(name), name);
  for (const name of catalog.freshness.reserved_not_emitted) assert.ok(a5.includes(name), name);
  for (const name of catalog.fields.query_completeness.values) assert.ok(a4.includes(name), name);
  for (const name of catalog.fields.sampling_state.values) assert.ok(a4.includes(name), name);
  for (const name of catalog.fields.drop_state.values) assert.ok(a4.includes(name), name);
  for (const name of catalog.fields.completeness_reason.values) assert.ok(a4.includes(name), name);
  for (const name of catalog.fields.issue_location.values) assert.ok(decision.includes(name), name);
  for (const name of catalog.fields.compatibility_status.values) assert.ok(prose.includes(name), name);
  assert.ok(prose.includes("PENDING_WS4"));
  assert.ok(prose.includes("docs/planning/shared-health-vocabulary/"));
  assert.ok(prose.includes("FRESHNESS_WINDOW_NOT_SET_EMIT_UNKNOWN"));
  assert.ok(prose.includes("c1de02538f66df94d58aef58bf0ec8459ae797ad"));
  assert.ok(prose.includes("COLLISION-MATRIX.json"));
  assert.ok(a5.includes("NOT_SET"));
});

test("frozen package versions and citation commits stay on this base", () => {
  const cli = readJson(catalog.frozen_surfaces.cli.path);
  const nodeSdk = readJson(catalog.frozen_surfaces.node_sdk.path);
  assert.equal(cli.version, catalog.frozen_surfaces.cli.version);
  assert.equal(nodeSdk.version, catalog.frozen_surfaces.node_sdk.version);
  const python = readText(catalog.frozen_surfaces.python_sdk.path);
  assert.match(python, new RegExp(`version = "${catalog.frozen_surfaces.python_sdk.version}"`));
  for (const sha of Object.values(catalog.citations)) {
    if (!/^[0-9a-f]{40}$/.test(sha)) continue;
    execFileSync("git", ["merge-base", "--is-ancestor", sha, "HEAD"], { cwd: ROOT, stdio: "ignore" });
  }
});

test("catalog prose names the freshness rule, subjects, and protection states", () => {
  const body = readText("docs/planning/shared-health-vocabulary/01-CATALOG.md");
  assert.ok(body.includes("FRESHNESS_WINDOW_NOT_SET_EMIT_UNKNOWN"));
  assert.ok(body.includes("NOT_SET"));
  assert.ok(body.includes("heartbeat_age_limit_s"));
  for (const subject of catalog.subjects) assert.ok(body.includes(subject), subject);
  for (const state of catalog.fields.protection_state.values) assert.ok(body.includes(state), state);
  for (const spelling of ["BLOCKED", "OBSERVED", "ALLOWED", "PARTIAL", "SUCCESS", "coverage_unknown", "CURRENT"]) {
    assert.ok(body.includes(spelling), spelling);
  }
});

test("council stub stays pending and access gaps stay gaps", () => {
  const council = readText("docs/planning/shared-health-vocabulary/INDEPENDENT-COUNCIL.md");
  const boundary = readText("docs/planning/shared-health-vocabulary/00-BOUNDARY.md");
  assert.ok(council.includes("PENDING_INDEPENDENT_COUNCIL"));
  assert.ok(council.includes("UNSAT"));
  assert.equal(council.includes("COUNCIL_PASSED"), false);
  assert.equal(boundary.includes("COUNCIL_PASSED"), false);
  assert.ok(boundary.includes("ACCESS_GAP"));
  assert.ok(boundary.includes("SHARED_HEALTH_VOCABULARY_READY_FOR_COUNCIL"));
  const gapIds = catalog.access_gaps.map((gap) => gap.id);
  for (const id of [
    "PE_PROTECTION_STATE_BLOB",
    "PE_VERIFIER_CONTRACT_BLOB",
    "PE_OPERATIONS_GUIDE",
    "LEDGER_ACTION_TAKEN_ENUM",
    "FOUNDER_MASTER_PROGRAM",
  ]) {
    assert.ok(gapIds.includes(id), id);
  }
});

test("manifest hashes the catalog files and not itself", () => {
  const manifest = readJson("docs/planning/shared-health-vocabulary/PLANNING-MANIFEST.json");
  assert.equal(manifest.producer_classification, "SHARED_HEALTH_VOCABULARY_READY_FOR_COUNCIL");
  assert.equal(manifest.council_status, "PENDING_INDEPENDENT_COUNCIL");
  assert.equal(manifest.council_verdict, null);
  assert.equal(manifest.self_certified_council_pass, false);
  assert.equal(manifest.open_core_base, "4b1b85ad6af41b1bb54dc4c55cde16b711ae7dd4");
  assert.equal(manifest.freshness_rule, "FRESHNESS_WINDOW_NOT_SET_EMIT_UNKNOWN");
  assert.equal(manifest.pe_packet.vocabulary_status, "PENDING_WS4");
  assert.equal(manifest.hard_stops.live_probe, false);
  assert.equal(Object.hasOwn(manifest.files_sha256, "docs/planning/shared-health-vocabulary/PLANNING-MANIFEST.json"), false);
  const expected = [
    "docs/planning/shared-health-vocabulary/00-BOUNDARY.md",
    "docs/planning/shared-health-vocabulary/01-CATALOG.md",
    "docs/planning/shared-health-vocabulary/BINDINGS.md",
    "docs/planning/shared-health-vocabulary/COLLISION-MATRIX.json",
    "docs/planning/shared-health-vocabulary/HEALTH-VOCABULARY.json",
    "docs/planning/shared-health-vocabulary/INDEPENDENT-COUNCIL.md",
    "tests/shared-health-vocabulary/catalog.test.cjs",
    "tests/shared-health-vocabulary/collision.test.cjs",
  ];
  assert.deepEqual(Object.keys(manifest.files_sha256).sort(), expected);
  for (const rel of expected) {
    const digest = crypto.createHash("sha256").update(fs.readFileSync(path.join(ROOT, rel))).digest("hex");
    assert.equal(digest, manifest.files_sha256[rel], rel);
  }
  const present = fs.readdirSync(HOME).sort();
  assert.deepEqual(present, [
    "00-BOUNDARY.md",
    "01-CATALOG.md",
    "BINDINGS.md",
    "COLLISION-MATRIX.json",
    "HEALTH-VOCABULARY.json",
    "INDEPENDENT-COUNCIL.md",
    "PLANNING-MANIFEST.json",
  ]);
});
