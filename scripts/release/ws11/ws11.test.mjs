import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { findForbiddenClaims, loadRequirements } from "./claims.mjs";
import { allGenerated, characterizeOptics } from "./characterize.mjs";
import { evaluateDossier, exitCodeFor } from "./evaluate.mjs";
import { REPO_ROOT, actionUses, buildSbom, classifyActionUse, privateManualPaths, readSealedPypi, scanManifestLicenses } from "./inventory.mjs";
import { stableStringify } from "./stable.mjs";
import { assemblePeCustomerBundle, packageVersionProblems, readText } from "../../../docs/scripts/docs-release-lib.mjs";

const ROOT = REPO_ROOT;
const PROGRAM = "docs/programs/release-engineering";
const DOSSIERS = ["optics-public.json", "phantom-engine-private.json", "private-customer.json"];

function readJson(rel) {
  return JSON.parse(readFileSync(join(ROOT, rel), "utf8"));
}

function digest(text) {
  return createHash("sha256").update(text).digest("hex");
}

function requirement(result, id) {
  return result.requirements.find((item) => item.id === id);
}

const SEALED = Buffer.from("vantio-ws11-sealed-artifact");
const SEALED_SHA = digest(SEALED);
const PREVIOUS_SHA = digest("vantio-ws11-previous-artifact");

function authorized() {
  return {
    schema: "vantio.ws11.release-dossier/v1",
    disposition_requested: "READY_TO_PUBLISH",
    subject: { product: "optics", package: "example-sealed", distribution: "public" },
    pins: [
      { name: "artifact", kind: "integrity-hash", value: SEALED_SHA, required_for_publish: true, accepted_as_pin: true },
      { name: "optional-note", kind: "unpinned", value: "floating-tool", required_for_publish: false, accepted_as_pin: false },
    ],
    reproducibility: {
      status: "BYTE_MATCH_OBSERVED",
      formal_claim: false,
      builds: [
        { id: "build-a", sha256: SEALED_SHA },
        { id: "build-b", sha256: SEALED_SHA },
      ],
    },
    units: [
      {
        package: "example-sealed",
        version: "1.2.3",
        distribution: "public",
        artifacts: [
          {
            filename: "example-sealed-1.2.3.bin",
            role: "tarball",
            version: "1.2.3",
            byte_length: SEALED.length,
            sha256: SEALED_SHA,
            hash_status: "RECORDED",
            source_commit: "a".repeat(40),
            distribution: "public",
            content_base64: SEALED.toString("base64"),
            custody: {
              selector: { kind: "sha256", value: SEALED_SHA },
              selector_is_integrity: true,
              hash_status: "RECORDED",
            },
          },
        ],
        clean_env: {
          status: "PASSED",
          exit_code: 0,
          environment_digest: `sha256:${digest("environment")}`,
          environment_characterized: true,
          artifact_sha256: SEALED_SHA,
        },
        upgrade: {
          verified: true,
          from_version: "1.2.2",
          to_version: "1.2.3",
          from_sha256: PREVIOUS_SHA,
          to_sha256: SEALED_SHA,
          rollback_sha256: PREVIOUS_SHA,
        },
        registry: {
          status: "BYTE_MATCH",
          observed_sha256: SEALED_SHA,
          observed_bytes: SEALED.length,
          client: "ordinary-curl",
        },
        ordinary_client: { status: "PROVED", client_identity: "ordinary-curl", sha256: SEALED_SHA },
        docs_gate: { status: "MATCH", manifest_version: "1.2.3", docs_version: "1.2.3" },
      },
    ],
    provenance: {
      characterization: "NONE",
      slsa_level: null,
      certification: null,
      hardware_backed: false,
      reproducible_build_claimed: false,
      verified: false,
    },
    sbom: {
      status: "PRESENT",
      format: "cyclonedx-1.5-json",
      sha256: digest("example-sbom"),
      completeness: "direct-manifests",
      bound_to_artifact: true,
      dependency_graph: "present",
    },
    scans: {
      vulnerability: { status: "CLEAN", tool_name: "fixture-vuln", tool_version: "1", scope: "sealed-bytes", findings: [] },
      license: { status: "CLEAN", tool_name: "fixture-license", tool_version: "1", scope: "sealed-bytes", findings: [] },
    },
    retention: {
      class: "sealed-bytes",
      location: "fixture custody",
      minimum_days: 730,
      customer_body_in_public_repo: false,
      demonstrated: true,
      witness: "witness-1",
    },
    private_distribution: {
      applicable: true,
      public_distribution_of_customer_manual: false,
      customer_body_in_public_repo: false,
      body_class: "absent",
    },
    emergency: { invoked: false },
    partial: { state: "CLEAR", expected_artifacts: 1, published_artifacts: 1, recovery: "NOT_REQUIRED" },
    roles: {
      roles_are_slots: false,
      approver_recorded: true,
      author: "author-1",
      builder: "builder-1",
      custodian: "custodian-1",
      publisher: "publisher-1",
      approver: "approver-1",
      verifier: "verifier-1",
    },
  };
}

function phantomPublishCandidate(distribution) {
  const dossier = authorized();
  dossier.subject = {
    product: "phantom-engine",
    package: "vantio-phantom-engine",
    distribution,
  };
  dossier.units[0].package = "ghcr.io/vantioai/vantio-phantom-engine";
  dossier.units[0].distribution = distribution;
  dossier.units[0].artifacts[0].distribution = distribution;
  dossier.private_distribution = {
    applicable: true,
    public_distribution: false,
    channel: "private",
    body_class: "absent",
    customer_body_in_public_repo: false,
  };
  dossier.retention.class = "phantom-private";
  return dossier;
}

function runVerifier(args, dossier) {
  const dir = mkdtempSync(join(tmpdir(), "ws11-"));
  const dossierPath = join(dir, "dossier.json");
  if (dossier) writeFileSync(dossierPath, JSON.stringify(dossier));
  const argv = [join(ROOT, "scripts/release/ws11/verify.mjs"), ...args];
  if (dossier) argv.push("--dossier", dossierPath);
  return spawnSync(process.execPath, argv, { cwd: ROOT, encoding: "utf8" });
}

test("requirement catalog is R1 through R18", () => {
  const catalog = loadRequirements(ROOT);
  assert.deepEqual(catalog.ids, ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "R11", "R12", "R13", "R14", "R15", "R16", "R17", "R18"]);
  const manifest = readJson(`${PROGRAM}/WS11-MANIFEST.json`);
  assert.equal(manifest.producer_classification, "WS11_RELEASE_ENGINEERING_REVISION_READY_FOR_COUNCIL");
  assert.equal(manifest.prior_council, "WS11_RELEASE_ENGINEERING_NEEDS_REVISION");
  assert.equal(manifest.prior_council_tip, "2e20cb018590dff720e2c209ad2b41ee2b9a0035");
  assert.equal(manifest.council_status, "PENDING_INDEPENDENT_COUNCIL");
  assert.equal(manifest.council_pass, false);
  assert.equal(manifest.release_success, false);
  assert.equal(manifest.base_commit, "89f95099d0dce463307eb75d78e7fcf2ef99feb2");
  for (const key of ["formal_slsa_level", "formal_certification", "formal_reproducibility", "hardware_backed_provenance"]) {
    assert.equal(manifest[key], "NOT_CLAIMED");
  }
});

test("committed process artifacts match the generator", () => {
  const { artifacts, evaluations } = allGenerated(ROOT);
  const expected = new Map([
    [`${PROGRAM}/generated/pin-report.json`, artifacts["pin-report.json"]],
    [`${PROGRAM}/generated/open-core-sbom.cdx.json`, artifacts["open-core-sbom.cdx.json"]],
    [`${PROGRAM}/generated/manifest-license-scan.json`, artifacts["manifest-license-scan.json"]],
    [`${PROGRAM}/generated/evaluations.json`, evaluations],
    [`${PROGRAM}/dossiers/optics-public.json`, artifacts["optics-public.json"]],
    [`${PROGRAM}/dossiers/phantom-engine-private.json`, artifacts["phantom-engine-private.json"]],
    [`${PROGRAM}/dossiers/private-customer.json`, artifacts["private-customer.json"]],
  ]);
  for (const [rel, value] of expected) {
    assert.equal(readFileSync(join(ROOT, rel), "utf8"), stableStringify(value), rel);
  }
});

test("current surfaces characterize with gaps and withhold release success", () => {
  for (const name of DOSSIERS) {
    const dossier = readJson(`${PROGRAM}/dossiers/${name}`);
    const result = evaluateDossier(dossier, { root: ROOT });
    assert.equal(result.disposition, "CHARACTERIZED", name);
    assert.equal(result.release_success, false, name);
    assert.equal(result.council_pass, false, name);
    assert.equal(result.formal_slsa_level, "NOT_CLAIMED");
    assert.equal(result.formal_reproducibility, "NOT_CLAIMED");
    assert.equal(result.hardware_backed_provenance, "NOT_CLAIMED");
    assert.equal(result.requirements.length, 18);
    assert.equal(result.requirements.some((item) => item.status === "REJECTED"), false, name);
    assert.equal(result.requirements.some((item) => item.status === "GAP"), true, name);
  }
  const optics = readJson(`${PROGRAM}/dossiers/optics-public.json`);
  const python = optics.units.find((unit) => unit.package === "vantio-agent-sdk");
  assert.equal(python.registry.status, "NOT_FETCHED");
  assert.equal(python.registry.this_force_refetched, false);
  assert.equal(python.registry.historical_register_state, "PUBLISHED_REGISTRY_BYTES_VERIFIED_CLIENT_PROVED");
  const cli = optics.units.find((unit) => unit.package === "@vantio/cli");
  assert.equal(cli.version, "0.3.25");
  assert.equal(cli.artifacts[0].custody.selector.kind, "git-tag");
  assert.equal(cli.artifacts[0].custody.selector_is_integrity, false);
  const contract = optics.units.find((unit) => unit.package === "@vantio/optics-evidence-contract");
  assert.equal(contract.distribution, "private");
  const phantom = readJson(`${PROGRAM}/dossiers/phantom-engine-private.json`);
  assert.equal(phantom.private_distribution.public_distribution, false);
  assert.equal(phantom.private_distribution.this_force_refetched, false);
  assert.equal(phantom.subject.distribution, "private");
  assert.equal(phantom.units.every((unit) => unit.distribution === "private"), true);
  assert.equal(phantom.units.every((unit) => unit.artifacts.every((artifact) => artifact.distribution === "private")), true);
  assert.equal(requirement(evaluateDossier(phantom, { root: ROOT }), "R13").status, "SATISFIED");
  assert.equal(requirement(evaluateDossier(phantom, { root: ROOT }), "R13").detail, "phantom distribution stays private");
});

test("workspace SBOM and license scan stay bounded to what the tree shows", () => {
  const sbom = buildSbom(ROOT);
  assert.equal(sbom.bomFormat, "CycloneDX");
  assert.equal(sbom.specVersion, "1.5");
  assert.ok(sbom.components.length > 20);
  assert.ok(sbom.components.some((item) => item.name === "@vantio/cli" && item.version === "0.3.25"));
  assert.ok(sbom.components.some((item) => item.purl === "pkg:pypi/vantio-agent-sdk@3.1.1"));
  assert.ok(sbom.components.some((item) => item.name === "undici" && item.hashes));
  const completeness = sbom.properties.find((item) => item.name === "vantio:completeness");
  assert.equal(completeness.value, "pnpm-lockfile-packages-section-plus-workspace-manifests");
  assert.equal(sbom.properties.find((item) => item.name === "vantio:bound-to-sealed-artifact").value, "false");
  assert.equal(sbom.properties.find((item) => item.name === "vantio:formal-provenance-level").value, "NOT_CLAIMED");
  const scan = scanManifestLicenses(ROOT);
  assert.equal(scan.status, "FINDINGS");
  assert.equal(scan.bound_to_sealed_bytes, false);
  assert.ok(scan.findings.some((item) => item.path === "packages/optics-evidence-contract/package.json"));
  assert.equal(scan.findings.some((item) => item.path === "packages/vantio-cli/package.json"), false);
});

test("actionUses keeps SHA pins that carry a tag comment", () => {
  const text = [
    "        uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4",
    "      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4",
    "        uses: actions/setup-node@v4",
    "        uses: pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33 # release/v1",
  ].join("\n");
  assert.deepEqual(actionUses(text), [
    "actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4",
    "actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4",
    "actions/setup-node@v4",
    "pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33 # release/v1",
  ]);
});

test("pin report records SHA-pinned workflow and composite actions and the sealed Python hashes", () => {
  const { artifacts } = allGenerated(ROOT);
  const report = artifacts["pin-report.json"];
  assert.equal(report.package_manager.name, "pnpm");
  assert.equal(report.package_manager.version, "11.13.0");
  assert.match(report.package_manager.integrity, /^sha512\./);
  const floating = report.actions.filter((action) => action.pin_kind === "floating");
  const approvedMain = report.actions.filter((action) => action.pin_kind === "same_repo_refs_heads_main");
  const pinned = report.actions.filter((action) => action.digest_pinned === true);
  assert.deepEqual(
    floating.map((action) => `${action.file} ${action.uses}`),
    [],
  );
  assert.deepEqual(
    approvedMain.map((action) => `${action.file} ${action.uses}`),
    [
      ".github/workflows/w3-lab-auto-provision.yml vantioai/vantio-open-core/.github/workflows/w3-lab-auto-cost-gate.yml@refs/heads/main # oidc-trust",
    ],
  );
  assert.ok(approvedMain.every((action) => action.digest_pinned === false));
  assert.ok(pinned.length > 0);
  assert.equal(pinned.length + approvedMain.length, report.actions.length);
  assert.ok(pinned.every((action) => /@[0-9a-f]{40} # \S+$/.test(action.uses)));
  assert.equal(classifyActionUse("actions/checkout@main").pin_kind, "floating");
  assert.equal(classifyActionUse("actions/checkout@refs/heads/main").pin_kind, "floating");
  assert.equal(
    classifyActionUse("vantioai/vantio-open-core/.github/workflows/other.yml@refs/heads/main # oidc-trust").pin_kind,
    "floating",
  );
  assert.equal(
    report.provenance_workflow.attest_action,
    "actions/attest-build-provenance@e8998f949152b193b063cb0ec769d69d929409be # v2",
  );
  assert.equal(report.workflow_triggers_push["npm-publish.yml"], false);
  assert.equal(report.workflow_triggers_push["pypi-publish.yml"], false);
  assert.equal(report.workflow_triggers_push["mcp-registry-publish.yml"], false);
  assert.equal(report.workflow_triggers_push["ci.yml"], true);
  assert.equal(report.python_build_requires_pinned, false);
  assert.deepEqual(report.sealed_pypi, readSealedPypi(ROOT));
  assert.equal(report.provenance_workflow.formal_slsa_level, "NOT_CLAIMED");
  assert.equal(report.provenance_workflow.historical_log_contains_level_assertion, true);
  assert.equal(report.provenance_workflow.apps_web_present, false);
  assert.equal(report.provenance_workflow.edge_proxy_present, false);
  assert.equal(report.release_success, false);
  assert.deepEqual(privateManualPaths(ROOT), ["docs/scripts/fixtures/pe-customer-bundle/PRIVATE-MANUAL.md"]);
});

test("version-matched docs gate and the customer test double agree with the tree", () => {
  const metadata = readJson("docs/governance/VERSION-METADATA.json");
  assert.equal(packageVersionProblems(ROOT, metadata.packages), "");
  const manual = readText(ROOT, "docs/scripts/fixtures/pe-customer-bundle/PRIVATE-MANUAL.md");
  assert.equal(assemblePeCustomerBundle({ version: "0.0.0-test", manualText: manual }).ok, true);
  assert.equal(assemblePeCustomerBundle({ version: "9.9.9", manualText: manual }).ok, false);
  const cli = JSON.parse(readFileSync(join(ROOT, "packages/vantio-cli/package.json"), "utf8"));
  const pyproject = readFileSync(join(ROOT, "packages/vantio-agent-sdk-py/pyproject.toml"), "utf8");
  assert.equal(cli.version, "0.3.25");
  assert.match(pyproject, /version = "3.1.1"/);
  assert.equal(readFileSync(join(ROOT, ".github/workflows/ci.yml"), "utf8").includes("scripts/release/ws11/ws11.test.mjs"), true);
});

test("a complete dossier can authorize a release while claim tokens stay unclaimed", () => {
  const result = evaluateDossier(authorized(), { root: ROOT });
  assert.equal(result.disposition, "RELEASE_AUTHORIZED");
  assert.equal(result.release_success, true);
  assert.equal(result.requirements.every((item) => item.status === "SATISFIED"), true);
  assert.equal(result.formal_slsa_level, "NOT_CLAIMED");
  assert.equal(result.formal_certification, "NOT_CLAIMED");
  assert.equal(result.formal_reproducibility, "NOT_CLAIMED");
  assert.equal(result.hardware_backed_provenance, "NOT_CLAIMED");
  assert.equal(result.council_pass, false);
  const characterized = authorized();
  characterized.disposition_requested = "CHARACTERIZED";
  const held = evaluateDossier(characterized, { root: ROOT });
  assert.equal(held.disposition, "CHARACTERIZED");
  assert.equal(held.release_success, false);
});

test("public Phantom subject, unit, and artifact with a false public flag do not authorize release", () => {
  const opened = phantomPublishCandidate("public");
  const openedResult = evaluateDossier(opened, { root: ROOT });
  assert.notEqual(openedResult.disposition, "RELEASE_AUTHORIZED");
  assert.equal(requirement(openedResult, "R13").status, "REJECTED");
  assert.match(requirement(openedResult, "R13").detail, /do not agree on private distribution/);
  assert.equal(openedResult.release_success, false);
  assert.equal(openedResult.council_pass, false);
  for (const key of ["formal_slsa_level", "formal_certification", "formal_reproducibility", "hardware_backed_provenance"]) {
    assert.equal(openedResult[key], "NOT_CLAIMED");
  }

  const openLayer = {
    subject(dossier) { dossier.subject.distribution = "public"; },
    unit(dossier) { dossier.units[0].distribution = "public"; },
    artifact(dossier) { dossier.units[0].artifacts[0].distribution = "public"; },
  };
  for (const [layer, open] of Object.entries(openLayer)) {
    const dossier = phantomPublishCandidate("private");
    open(dossier);
    const result = evaluateDossier(dossier, { root: ROOT });
    assert.notEqual(result.disposition, "RELEASE_AUTHORIZED", layer);
    assert.equal(requirement(result, "R13").status, "REJECTED", layer);
    assert.match(requirement(result, "R13").detail, /do not agree on private distribution/, layer);
    assert.equal(result.release_success, false, layer);
    assert.equal(result.council_pass, false, layer);
  }

  const mixed = phantomPublishCandidate("private");
  mixed.subject.distribution = "mixed";
  const mixedResult = evaluateDossier(mixed, { root: ROOT });
  assert.notEqual(mixedResult.disposition, "RELEASE_AUTHORIZED");
  assert.equal(requirement(mixedResult, "R13").status, "REJECTED");
  assert.equal(mixedResult.release_success, false);
  assert.equal(mixedResult.council_pass, false);

  const split = phantomPublishCandidate("private");
  const publicArtifact = JSON.parse(JSON.stringify(split.units[0].artifacts[0]));
  publicArtifact.filename = "vantio-phantom-engine-public.bin";
  publicArtifact.distribution = "public";
  split.units[0].artifacts.push(publicArtifact);
  const splitResult = evaluateDossier(split, { root: ROOT });
  assert.notEqual(splitResult.disposition, "RELEASE_AUTHORIZED");
  assert.equal(requirement(splitResult, "R13").status, "REJECTED");
  assert.equal(splitResult.release_success, false);
  assert.equal(splitResult.council_pass, false);

  const extraUnitDossier = phantomPublishCandidate("private");
  const extraUnit = JSON.parse(JSON.stringify(extraUnitDossier.units[0]));
  extraUnit.package = "ghcr.io/vantioai/vantio-phantom-engine-extra";
  extraUnit.distribution = "public";
  extraUnitDossier.units.push(extraUnit);
  const extraUnitResult = evaluateDossier(extraUnitDossier, { root: ROOT });
  assert.notEqual(extraUnitResult.disposition, "RELEASE_AUTHORIZED");
  assert.equal(requirement(extraUnitResult, "R13").status, "REJECTED");
  assert.equal(extraUnitResult.release_success, false);
  assert.equal(extraUnitResult.council_pass, false);

  const closed = phantomPublishCandidate("private");
  const closedResult = evaluateDossier(closed, { root: ROOT });
  assert.equal(closedResult.disposition, "RELEASE_AUTHORIZED");
  assert.equal(requirement(closedResult, "R13").status, "SATISFIED");
  assert.equal(requirement(closedResult, "R13").detail, "phantom distribution stays private");
  assert.equal(closedResult.release_success, true);
  assert.equal(closedResult.council_pass, false);
  for (const key of ["formal_slsa_level", "formal_certification", "formal_reproducibility", "hardware_backed_provenance"]) {
    assert.equal(closedResult[key], "NOT_CLAIMED");
  }
});

test("program prose and generated records avoid forbidden claim phrases", () => {
  const { patterns } = loadRequirements(ROOT);
  const files = [
    `${PROGRAM}/00-INVENTORY.md`,
    `${PROGRAM}/01-BOUNDARY.md`,
    `${PROGRAM}/02-ARCHITECTURE.md`,
    `${PROGRAM}/03-REQUIREMENTS.md`,
    `${PROGRAM}/04-INDEPENDENT-COUNCIL.md`,
    `${PROGRAM}/WS11-MANIFEST.json`,
    `${PROGRAM}/generated/evaluations.json`,
    `${PROGRAM}/generated/pin-report.json`,
    `${PROGRAM}/generated/open-core-sbom.cdx.json`,
    ...DOSSIERS.map((name) => `${PROGRAM}/dossiers/${name}`),
  ];
  for (const rel of files) {
    const text = readFileSync(join(ROOT, rel), "utf8");
    const value = rel.endsWith(".json") ? JSON.parse(text) : text;
    const hits = findForbiddenClaims(value, patterns);
    assert.deepEqual(hits, [], rel);
  }
  const samples = [
    "SLSA Level 3",
    "SLSA L3",
    "certified build",
    "passed certification",
    "hardware-backed provenance",
    "hardware backed key",
    "reproducible build",
    "formally reproducible",
  ];
  for (const sample of samples) assert.equal(findForbiddenClaims(sample, patterns).length > 0, true, sample);
});

test("direct release paths authorize, record, or stop", () => {
  const emergency = authorized();
  emergency.disposition_requested = "EMERGENCY";
  emergency.emergency = { invoked: true, reason: "registry metadata corruption", authorization_ref: "founder-ref-1", skip_hash: false };
  assert.equal(evaluateDossier(emergency, { root: ROOT }).disposition, "RELEASE_AUTHORIZED");

  const revocation = authorized();
  revocation.disposition_requested = "REVOCATION";
  revocation.emergency = {
    invoked: true,
    reason: "wrong bytes",
    authorization_ref: "founder-ref-2",
    skip_hash: false,
    revocation: { status: "OBSERVED", method: "yank", sha256: SEALED_SHA, observed_at: "2026-09-27T00:00:00Z" },
  };
  const revoked = evaluateDossier(revocation, { root: ROOT });
  assert.equal(revoked.disposition, "REVOCATION_RECORDED");
  assert.equal(revoked.release_success, false);

  const missing = authorized();
  missing.scans.vulnerability.status = "NOT_RUN";
  missing.scans.vulnerability.reason = "scanner unavailable";
  const withheld = evaluateDossier(missing, { root: ROOT });
  assert.equal(withheld.disposition, "EVIDENCE_MISSING");
  assert.equal(withheld.release_success, false);
  assert.equal(exitCodeFor(withheld), 2);

  const partial = authorized();
  partial.partial = { state: "PARTIAL", expected_artifacts: 2, published_artifacts: 1, recovery: "DO_NOT_REPLACE_BYTES" };
  const partialResult = evaluateDossier(partial, { root: ROOT });
  assert.equal(partialResult.disposition, "PARTIAL_PUBLICATION");
  assert.equal(partialResult.release_success, false);
  assert.equal(exitCodeFor(partialResult), 2);
});

test("adversarial dossiers are rejected or withheld", () => {
  const cases = [
    ["formal level phrase", (dossier) => { dossier.note = "SLSA Level 3"; }, "REJECTED"],
    ["conformance phrase", (dossier) => { dossier.note = "passed certification"; }, "REJECTED"],
    ["hardware phrase", (dossier) => { dossier.note = "hardware-backed provenance"; }, "REJECTED"],
    ["byte-identity phrase", (dossier) => { dossier.note = "reproducible build"; }, "REJECTED"],
    ["hardware flag", (dossier) => { dossier.provenance.hardware_backed = true; }, "REJECTED"],
    ["formal claim flag", (dossier) => { dossier.reproducibility.formal_claim = true; }, "REJECTED"],
    ["one build match", (dossier) => { dossier.reproducibility.builds = [{ id: "only", sha256: SEALED_SHA }]; }, "REJECTED"],
    ["different build digests", (dossier) => { dossier.reproducibility.builds[1].sha256 = PREVIOUS_SHA; }, "REJECTED"],
    ["tag treated as integrity", (dossier) => {
      dossier.units[0].artifacts[0].custody.selector = { kind: "git-tag", value: "v1.2.3" };
      dossier.units[0].artifacts[0].custody.selector_is_integrity = true;
    }, "REJECTED"],
    ["custody hash drift", (dossier) => { dossier.units[0].artifacts[0].custody.selector.value = PREVIOUS_SHA; }, "REJECTED"],
    ["manifest byte drift", (dossier) => { dossier.units[0].artifacts[0].byte_length += 1; }, "REJECTED"],
    ["clean result with findings", (dossier) => { dossier.scans.license.findings = [{ id: "x", accepted: false }]; }, "REJECTED"],
    ["clean result without a tool version", (dossier) => { dossier.scans.vulnerability.tool_version = ""; }, "REJECTED"],
    ["passed install without an environment digest", (dossier) => { dossier.units[0].clean_env.environment_digest = null; }, "REJECTED"],
    ["publisher posed as the ordinary client", (dossier) => { dossier.units[0].ordinary_client.client_identity = "publisher-1"; }, "REJECTED"],
    ["publisher workflow posed as the registry observer", (dossier) => { dossier.units[0].registry.client = "publisher-workflow"; }, "REJECTED"],
    ["registry hash drift", (dossier) => { dossier.units[0].registry.observed_sha256 = PREVIOUS_SHA; }, "REJECTED"],
    ["collapsed roles", (dossier) => {
      for (const name of ["author", "builder", "custodian", "publisher", "approver", "verifier"]) dossier.roles[name] = "same";
    }, "REJECTED"],
    ["verifier is the publisher", (dossier) => { dossier.roles.verifier = "publisher-1"; }, "REJECTED"],
    ["approver is the publisher", (dossier) => { dossier.roles.approver = "publisher-1"; }, "REJECTED"],
    ["unpinned input accepted as a pin", (dossier) => { dossier.pins.push({ name: "floating", kind: "unpinned", value: "@v4", required_for_publish: true, accepted_as_pin: true }); }, "REJECTED"],
    ["rollback points at the new bytes", (dossier) => { dossier.units[0].upgrade.rollback_sha256 = SEALED_SHA; }, "REJECTED"],
    ["self-assigned release success", (dossier) => { dossier.release_success = true; }, "REJECTED"],
    ["self-assigned council pass", (dossier) => { dossier.council_pass = true; }, "REJECTED"],
    ["program classification on a package dossier", (dossier) => { dossier.program_classification = "WS11_RELEASE_ENGINEERING_READY_FOR_COUNCIL"; }, "REJECTED"],
    ["revision classification on a package dossier", (dossier) => { dossier.program_classification = "WS11_RELEASE_ENGINEERING_REVISION_READY_FOR_COUNCIL"; }, "REJECTED"],
    ["replacement bytes for an existing version", (dossier) => { dossier.partial.recovery = "REUPLOAD_DIFFERENT_BYTES"; }, "REJECTED"],
    ["customer manual text", (dossier) => { dossier.private_distribution.manual_text = "manual body"; }, "REJECTED"],
    ["customer manual class", (dossier) => { dossier.private_distribution.body_class = "customer-manual"; }, "REJECTED"],
  ];
  for (const [name, change, disposition] of cases) {
    const dossier = authorized();
    change(dossier);
    const result = evaluateDossier(dossier, { root: ROOT });
    assert.equal(result.disposition, disposition, name);
    assert.equal(result.release_success, false, name);
    assert.equal(result.council_pass, false, name);
  }
});

test("private distribution, docs drift, and emergency bypasses stop", () => {
  const phantom = readJson(`${PROGRAM}/dossiers/phantom-engine-private.json`);
  phantom.private_distribution.public_distribution = true;
  assert.equal(evaluateDossier(phantom, { root: ROOT }).disposition, "REJECTED");

  const customer = readJson(`${PROGRAM}/dossiers/private-customer.json`);
  customer.disposition_requested = "READY_TO_PUBLISH";
  customer.roles.roles_are_slots = false;
  customer.roles.approver_recorded = true;
  assert.equal(requirement(evaluateDossier(customer, { root: ROOT }), "R13").status, "REJECTED");

  customer.disposition_requested = "CHARACTERIZED";
  customer.private_distribution.manual_version = "9.9.9";
  assert.equal(requirement(evaluateDossier(customer, { root: ROOT }), "R13").status, "REJECTED");

  const drifted = characterizeOptics(ROOT);
  const cli = drifted.units.find((unit) => unit.package === "@vantio/cli");
  cli.version = "9.9.9";
  cli.docs_gate.manifest_version = "9.9.9";
  cli.docs_gate.docs_version = "9.9.9";
  cli.artifacts[0].version = "9.9.9";
  assert.equal(requirement(evaluateDossier(drifted, { root: ROOT }), "R14").status, "REJECTED");

  const emergency = authorized();
  emergency.disposition_requested = "EMERGENCY";
  emergency.emergency = { invoked: true, reason: "outage", authorization_ref: "founder-ref-3", skip_hash: true };
  assert.equal(requirement(evaluateDossier(emergency, { root: ROOT }), "R15").status, "REJECTED");

  const unobserved = authorized();
  unobserved.disposition_requested = "REVOCATION";
  unobserved.emergency = {
    invoked: true,
    reason: "wrong bytes",
    authorization_ref: "founder-ref-4",
    skip_hash: false,
    revocation: { status: "NOT_PERFORMED" },
  };
  const result = evaluateDossier(unobserved, { root: ROOT });
  assert.equal(result.release_success, false);
  assert.equal(requirement(result, "R15").status, "GAP");
  assert.notEqual(result.disposition, "RELEASE_AUTHORIZED");
});

test("the verifier command withholds success and does not publish", () => {
  const characterized = runVerifier([], readJson(`${PROGRAM}/dossiers/optics-public.json`));
  assert.equal(characterized.status, 0, characterized.stderr);
  const characterizedResult = JSON.parse(characterized.stdout);
  assert.equal(characterizedResult.release_success, false);
  assert.equal(characterizedResult.disposition, "CHARACTERIZED");

  const rejected = runVerifier([], { schema: "vantio.ws11.release-dossier/v1" });
  assert.equal(rejected.status, 1);
  assert.equal(JSON.parse(rejected.stdout).release_success, false);

  const missing = authorized();
  missing.units[0].registry.status = "NOT_FETCHED";
  const withheld = runVerifier([], missing);
  assert.equal(withheld.status, 2, withheld.stdout);
  assert.equal(JSON.parse(withheld.stdout).release_success, false);

  const inventory = runVerifier(["--inventory"]);
  assert.equal(inventory.status, 0, inventory.stderr);
  assert.equal(JSON.parse(inventory.stdout).formal_slsa_level, "NOT_CLAIMED");

  for (const rel of ["verify.mjs", "evaluate.mjs", "characterize.mjs", "inventory.mjs"]) {
    const source = readFileSync(join(ROOT, "scripts/release/ws11", rel), "utf8");
    assert.equal(/\bnpm publish\b|\bpnpm publish\b|\btwine\b|\bdocker push\b|\bgh release create\b/.test(source), false, rel);
  }
});
