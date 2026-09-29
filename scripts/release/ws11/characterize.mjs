import { readFileSync } from "node:fs";
import { join } from "node:path";
import { evaluateDossier } from "./evaluate.mjs";
import { buildInventory, buildSbom, privateManualPaths, scanManifestLicenses, sha256File } from "./inventory.mjs";

const PLANNING_DOC = "docs/planning/phantom-engine-production/02-P1-PACKAGE-ARTIFACT-PROVENANCE.md";
const PLANNING_TIP = "631e435315cd780d83d3259e111893c1d0569bc3";
const FIXTURE = "docs/scripts/fixtures/pe-customer-bundle/PRIVATE-MANUAL.md";
const FIXTURE_VERSION = "0.0.0-test";

const ROLE_SLOTS = {
  roles_are_slots: true,
  approver_recorded: false,
  author: "slot:author",
  builder: "slot:builder",
  custodian: "slot:custodian",
  publisher: "slot:publisher",
  approver: "slot:approver",
  verifier: "slot:verifier",
};

function readJson(root, rel) {
  return JSON.parse(readFileSync(join(root, rel), "utf8"));
}

function pin(name, kind, value, required, accepted) {
  return { name, kind, value, required_for_publish: required, accepted_as_pin: accepted };
}

function unrecordedArtifact(pkg, distribution) {
  return {
    filename: `${pkg.name.replace("/", "-")}-${pkg.version}.source`,
    role: "source-tree",
    version: pkg.version,
    byte_length: null,
    sha256: null,
    hash_status: "UNRECORDED",
    source_commit: "UNRECORDED",
    distribution,
    custody: {
      selector: { kind: "unrecorded", value: "UNRECORDED" },
      selector_is_integrity: false,
      hash_status: "UNRECORDED",
    },
  };
}

function recordedArtifact({ filename, role, version, byteLength, sha256, sourceCommit, distribution }) {
  return {
    filename,
    role,
    version,
    byte_length: byteLength,
    sha256,
    hash_status: "RECORDED",
    source_commit: sourceCommit,
    distribution,
    custody: {
      selector: { kind: "sha256", value: sha256 },
      selector_is_integrity: true,
      hash_status: "RECORDED",
    },
  };
}

function openUnit(pkg, distribution, artifact, extras = {}) {
  return {
    package: pkg.name,
    version: pkg.version,
    distribution,
    artifacts: [artifact],
    clean_env: { status: "NOT_RUN" },
    upgrade: {
      verified: false,
      from_version: null,
      to_version: pkg.version,
      from_sha256: null,
      to_sha256: null,
      rollback_sha256: null,
    },
    registry: { status: "NOT_FETCHED", historical_register_state: null },
    ordinary_client: { status: "NOT_RUN" },
    docs_gate: { status: "MATCH", manifest_version: pkg.version, docs_version: pkg.version },
    ...extras,
  };
}

function assessment(reasons) {
  return {
    status: "ASSESSED_NOT_REPRODUCIBLE",
    formal_claim: false,
    builds: [],
    reasons,
  };
}

function provenance(characterization) {
  return {
    characterization,
    slsa_level: null,
    certification: null,
    hardware_backed: false,
    reproducible_build_claimed: false,
    verified: false,
  };
}

function scans(reason) {
  return {
    vulnerability: { status: "NOT_RUN", reason, scope: "sealed-bytes" },
    license: { status: "NOT_RUN", reason, scope: "sealed-bytes" },
  };
}

function baseDossier(subject) {
  return {
    schema: "vantio.ws11.release-dossier/v1",
    disposition_requested: "CHARACTERIZED",
    subject,
    roles: ROLE_SLOTS,
    emergency: { invoked: false },
    partial: { state: "NOT_ASSESSED_THIS_FORCE", recovery: "DO_NOT_REPLACE_BYTES" },
  };
}

export function characterizeOptics(root, inventory = buildInventory(root)) {
  const metadata = readJson(root, "docs/governance/VERSION-METADATA.json");
  const units = metadata.packages.map((pkg) => {
    const manifestText = readFileSync(join(root, pkg.manifest), "utf8");
    const isPrivate = pkg.manifest.endsWith(".json") && JSON.parse(manifestText).private === true;
    const distribution = isPrivate ? "private" : "public";
    if (pkg.id === "python-sdk") {
      const sealed = inventory.sealed_pypi;
      const unit = openUnit(pkg, "public", recordedArtifact({
        filename: sealed.wheel_name,
        role: "wheel",
        version: pkg.version,
        byteLength: sealed.wheel_bytes,
        sha256: sealed.wheel_sha256,
        sourceCommit: inventory.release_register.python_publisher_commit,
        distribution: "public",
      }));
      unit.artifacts.push(recordedArtifact({
        filename: sealed.sdist_name,
        role: "sdist",
        version: pkg.version,
        byteLength: sealed.sdist_bytes,
        sha256: sealed.sdist_sha256,
        sourceCommit: inventory.release_register.python_publisher_commit,
        distribution: "public",
      }));
      unit.registry = {
        status: "NOT_FETCHED",
        historical_register_state: inventory.release_register.python_prior_state ?? inventory.release_register.python_state,
        this_force_refetched: false,
      };
      unit.upgrade = {
        verified: false,
        from_version: "3.0.14",
        to_version: pkg.version,
        from_sha256: null,
        to_sha256: sealed.wheel_sha256,
        rollback_sha256: null,
      };
      return unit;
    }
    if (pkg.id === "cli") {
      const unit = openUnit(pkg, "public", unrecordedArtifact(pkg, "public"));
      unit.artifacts[0].source_commit = inventory.release_register.cli_tag_commit;
      unit.artifacts[0].custody = {
        selector: { kind: "git-tag", value: inventory.release_register.cli_tag },
        selector_is_integrity: false,
        hash_status: "UNRECORDED",
      };
      unit.registry = { status: "NOT_FETCHED", historical_register_state: "FROZEN_PUBLISHED", this_force_refetched: false };
      return unit;
    }
    return openUnit(pkg, distribution, unrecordedArtifact(pkg, distribution));
  });
  const actionPins = inventory.actions
    .filter((action) => !action.digest_pinned)
    .map((action) => pin(`${action.file} ${action.uses}`, "unpinned", action.uses, true, false));
  return {
    ...baseDossier({ product: "optics", package: "optics-public-and-private-source", distribution: "mixed" }),
    pins: [
      pin("pnpm", "exact-version", inventory.package_manager.raw, true, true),
      pin("pnpm-lock.yaml", "lockfile-digest", inventory.lockfile.sha256, true, true),
      pin("python-build-hatchling", "unpinned", "hatchling", true, false),
      pin("node-toolchain", "unpinned", "22", true, false),
      pin("python-wheel", "integrity-hash", inventory.sealed_pypi.wheel_sha256, true, true),
      pin("python-sdist", "integrity-hash", inventory.sealed_pypi.sdist_sha256, true, true),
      pin("cli-tarball", "unrecorded", "UNRECORDED", true, false),
      ...actionPins,
    ],
    reproducibility: assessment([
      "All tip third-party action uses in workflows and the local composite .github/actions/vantio-prove are commit SHA pins with tag comments.",
      "The Python build-system requirement is hatchling with no version comparator.",
      "No second build digest is recorded in this force.",
    ]),
    units,
    provenance: provenance("GITHUB_ATTESTATION_CAPABLE_UNVERIFIED"),
    sbom: {
      status: "ABSENT",
      completeness: "not-applicable",
      dependency_graph: "present",
      reason: "The generated workspace SBOM is not bound to the sealed Python bytes or an npm tarball.",
    },
    scans: scans("No vulnerability or license scanner result is attached to the sealed bytes. The workspace manifest license scan is a separate tree report."),
    retention: {
      class: "sealed-bytes",
      location: "hash pins in scripts/release/stage_sealed_pypi.py and git history of this repository",
      minimum_days: 730,
      customer_body_in_public_repo: false,
      demonstrated: false,
    },
    private_distribution: {
      applicable: true,
      public_distribution_of_customer_manual: false,
      customer_body_in_public_repo: false,
      body_class: "absent",
    },
  };
}

export function characterizePhantom(root) {
  const planning = readFileSync(join(root, PLANNING_DOC), "utf8");
  if (!planning.includes(PLANNING_TIP)) throw new Error("planning tip was not found in the Phantom provenance note");
  return {
    ...baseDossier({ product: "phantom-engine", package: "vantio-phantom-engine", distribution: "private" }),
    pins: [
      pin("planning-tip", "prior-record-unverified", PLANNING_TIP, true, false),
      pin("rust-channel", "prior-record-unverified", "nightly", true, false),
      pin("dockerfile-builder", "prior-record-unverified", "rust:1-bookworm", true, false),
      pin("dockerfile-runtime", "prior-record-unverified", "debian:bookworm-slim", true, false),
      pin("bpf-linker", "prior-record-unverified", "unversioned-binstall", true, false),
      pin("image-digest", "prior-record-unverified", "UNVERIFIED_THIS_FORCE", true, false),
    ],
    reproducibility: assessment([
      "This force did not re-fetch vantio-phantom-engine.",
      "The planning note records floating builder tags and an undated nightly channel.",
      "No image digest was observed by this force.",
    ]),
    units: [
      {
        package: "ghcr.io/vantioai/vantio-phantom-engine",
        version: "0.1.0",
        distribution: "private",
        artifacts: [
          {
            filename: "vantio-phantom-engine-0.1.0",
            role: "image",
            version: "0.1.0",
            byte_length: null,
            sha256: null,
            hash_status: "UNRECORDED",
            source_commit: "UNVERIFIED_THIS_FORCE",
            distribution: "private",
            custody: {
              selector: { kind: "unrecorded", value: "UNRECORDED" },
              selector_is_integrity: false,
              hash_status: "UNRECORDED",
            },
          },
        ],
        clean_env: { status: "NOT_RUN" },
        upgrade: { verified: false, from_version: null, to_version: "0.1.0", from_sha256: null, to_sha256: null, rollback_sha256: null },
        registry: { status: "NOT_FETCHED", historical_register_state: null, this_force_refetched: false },
        ordinary_client: { status: "NOT_RUN" },
        docs_gate: { status: "NOT_APPLICABLE", reason: "Phantom Engine product docs stay in the private repository." },
      },
    ],
    provenance: provenance("NONE"),
    sbom: {
      status: "ABSENT",
      completeness: "not-applicable",
      dependency_graph: "present",
      reason: "No Phantom Engine SBOM was fetched by this force.",
    },
    scans: scans("No Phantom Engine scanner result was fetched by this force."),
    retention: {
      class: "phantom-private",
      location: "private vantio-phantom-engine repository and its private registry",
      minimum_days: 730,
      customer_body_in_public_repo: false,
      demonstrated: false,
    },
    private_distribution: {
      applicable: true,
      public_distribution: false,
      channel: "private",
      body_class: "absent",
      customer_body_in_public_repo: false,
      prior_record: PLANNING_DOC,
      recorded_tip: PLANNING_TIP,
      this_force_refetched: false,
    },
  };
}

export function characterizeCustomer(root) {
  const paths = privateManualPaths(root);
  if (paths.length !== 1 || paths[0] !== FIXTURE) throw new Error(`unexpected manual paths: ${paths.join(", ")}`);
  const bytes = readFileSync(join(root, FIXTURE));
  const digest = sha256File(join(root, FIXTURE));
  return {
    ...baseDossier({ product: "private-customer", package: "pe-customer-bundle-fixture", distribution: "private" }),
    pins: [
      pin("fixture-version", "exact-version", FIXTURE_VERSION, false, true),
      pin("customer-bytes", "unrecorded", "UNRECORDED", true, false),
    ],
    reproducibility: assessment([
      "The file under docs/scripts/fixtures is a documentation test double.",
      "No customer package bytes are stored in this repository.",
    ]),
    units: [
      {
        package: "pe-customer-bundle-fixture",
        version: FIXTURE_VERSION,
        distribution: "private",
        artifacts: [
          recordedArtifact({
            filename: "PRIVATE-MANUAL.md",
            role: "test-double",
            version: FIXTURE_VERSION,
            byteLength: bytes.length,
            sha256: digest,
            sourceCommit: "UNRECORDED",
            distribution: "private",
          }),
        ],
        clean_env: { status: "NOT_RUN" },
        upgrade: { verified: false, from_version: null, to_version: FIXTURE_VERSION, from_sha256: null, to_sha256: null, rollback_sha256: null },
        registry: { status: "NOT_FETCHED", historical_register_state: null },
        ordinary_client: { status: "NOT_RUN" },
        docs_gate: { status: "NOT_APPLICABLE", reason: "The test double is not a public docs release." },
      },
    ],
    provenance: provenance("NONE"),
    sbom: {
      status: "NOT_APPLICABLE",
      completeness: "not-applicable",
      dependency_graph: "none",
      reason: "The test double has no dependency graph.",
    },
    scans: scans("The test double is not a sealed customer package."),
    retention: {
      class: "private-customer",
      location: "customer handoff channel outside this public repository",
      minimum_days: 730,
      customer_body_in_public_repo: false,
      demonstrated: false,
    },
    private_distribution: {
      applicable: true,
      public_distribution: false,
      channel: "private",
      body_class: "test-double",
      bundle_version: FIXTURE_VERSION,
      manual_version: FIXTURE_VERSION,
      customer_body_in_public_repo: false,
      test_double_path: FIXTURE,
    },
  };
}

export function generatedArtifacts(root) {
  const inventory = buildInventory(root);
  return {
    "pin-report.json": inventory,
    "open-core-sbom.cdx.json": buildSbom(root),
    "manifest-license-scan.json": scanManifestLicenses(root),
    "optics-public.json": characterizeOptics(root, inventory),
    "phantom-engine-private.json": characterizePhantom(root),
    "private-customer.json": characterizeCustomer(root),
  };
}

export function allGenerated(root) {
  const artifacts = generatedArtifacts(root);
  const evaluations = {};
  for (const name of ["optics-public.json", "phantom-engine-private.json", "private-customer.json"]) {
    evaluations[name] = evaluateDossier(artifacts[name], { root });
  }
  return { artifacts, evaluations };
}
