import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { findForbiddenClaims, loadRequirements } from "./claims.mjs";

const HEX64 = /^[0-9a-f]{64}$/;
const SHA40 = /^[0-9a-f]{40}$/;
const VERSION = /^[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9.-]+)?$/;
const BINDING_KINDS = new Set(["lockfile-digest", "exact-version", "integrity-hash", "git-sha", "image-digest"]);
const GAP_KINDS = new Set(["unpinned", "prior-record-unverified", "unrecorded"]);
const PIN_KINDS = new Set([...BINDING_KINDS, ...GAP_KINDS, "not-applicable"]);
const ROLE_NAMES = ["author", "builder", "custodian", "publisher", "approver", "verifier"];
const DISPOSITIONS = new Set(["CHARACTERIZED", "READY_TO_PUBLISH", "EMERGENCY", "REVOCATION", "RECOVERY"]);
const PRODUCTS = new Set(["optics", "phantom-engine", "private-customer"]);
const PROVENANCE = new Set([
  "NONE",
  "GITHUB_ATTESTATION_CAPABLE_UNVERIFIED",
  "PEP740_CAPABLE_UNCLAIMED",
  "BUNDLE_PRESENT_UNVERIFIED",
]);
const SBOM_FORMATS = new Set(["cyclonedx-1.5-json", "spdx-2.3-json"]);
const SBOM_COMPLETENESS = new Set([
  "direct-manifests",
  "pnpm-lockfile-packages-section-plus-workspace-manifests",
  "lockfile-hash-only",
  "not-applicable",
]);
const SCAN_STATUS = new Set(["NOT_RUN", "CLEAN", "FINDINGS", "NOT_APPLICABLE"]);
const RECOVERY = new Set(["NOT_REQUIRED", "DO_NOT_REPLACE_BYTES", "YANK_THEN_STOP", "REUPLOAD_DIFFERENT_BYTES"]);
const IMAGE_DIGEST = /^sha256:[0-9a-f]{64}$/;

function sat(detail) {
  return { status: "SATISFIED", detail };
}
function gap(detail) {
  return { status: "GAP", detail };
}
function rej(detail) {
  return { status: "REJECTED", detail };
}

function fold(id, parts) {
  const rejected = parts.filter((part) => part.status === "REJECTED");
  if (rejected.length) return { id, status: "REJECTED", detail: rejected.map((part) => part.detail).join("; ") };
  const gaps = parts.filter((part) => part.status === "GAP");
  if (gaps.length) return { id, status: "GAP", detail: gaps.map((part) => part.detail).join("; ") };
  return { id, status: "SATISFIED", detail: parts.map((part) => part.detail).join("; ") };
}

function isObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function sha256Buffer(buffer) {
  return createHash("sha256").update(buffer).digest("hex");
}

function versionMetadata(root) {
  return JSON.parse(readFileSync(join(root, "docs/governance/VERSION-METADATA.json"), "utf8"));
}

export function evaluateDossier(dossier, context = {}) {
  const root = context.root;
  const catalog = loadRequirements(root || context.catalogRoot);
  const requirements = [];
  const shape = validateShape(dossier);
  if (shape) return rejectAll(dossier, shape, catalog);
  const claims = findForbiddenClaims(dossier, catalog.patterns);
  if (claims.length) return rejectAll(dossier, `forbidden claim at ${claims.map((hit) => hit.path).join(", ")}`, catalog);
  if (dossier.council_pass === true || dossier.release_success === true || dossier.program_classification) {
    return rejectAll(dossier, "a dossier cannot grant a council pass, a program classification, or release success", catalog);
  }

  const metadata = context.versionMetadata || (root ? versionMetadata(root) : null);
  requirements.push(evalPins(dossier));
  requirements.push(evalReproducibility(dossier));
  requirements.push(fold("R3", dossier.units.map((unit) => evalManifest(unit))));
  requirements.push(fold("R4", dossier.units.flatMap((unit) => unit.artifacts.map((artifact) => evalCustody(artifact)))));
  requirements.push(evalProvenance(dossier));
  requirements.push(evalSbom(dossier));
  requirements.push(evalScans(dossier));
  requirements.push(fold("R8", dossier.units.map((unit) => evalCleanEnv(unit))));
  requirements.push(fold("R9", dossier.units.map((unit) => evalUpgrade(unit))));
  requirements.push(fold("R10", dossier.units.map((unit) => evalRegistry(unit))));
  requirements.push(fold("R11", dossier.units.map((unit) => evalClient(unit, dossier))));
  requirements.push(evalRetention(dossier));
  requirements.push(evalPrivateDistribution(dossier));
  requirements.push(fold("R14", dossier.units.map((unit) => evalDocs(unit, metadata, root))));
  requirements.push(evalEmergency(dossier));
  requirements.push(evalPartial(dossier));
  requirements.push(evalRoles(dossier));
  requirements.push({ id: "R18", status: "SATISFIED", detail: "independent verifier executed; council_pass is false" });

  const known = new Set(requirements.map((item) => item.id));
  for (const id of catalog.ids) {
    if (!known.has(id)) {
      return finish(dossier, "REJECTED", false, [{ id: "R18", status: "REJECTED", detail: `missing evaluation for ${id}` }], catalog);
    }
  }

  const rejected = requirements.some((item) => item.status === "REJECTED");
  const gaps = requirements.some((item) => item.status === "GAP");
  const partial = dossier.partial.state === "PARTIAL";
  let disposition = "CHARACTERIZED";
  let releaseSuccess = false;
  if (rejected) disposition = "REJECTED";
  else if (dossier.disposition_requested === "READY_TO_PUBLISH" || dossier.disposition_requested === "EMERGENCY") {
    if (partial) disposition = "PARTIAL_PUBLICATION";
    else if (gaps) disposition = "EVIDENCE_MISSING";
    else {
      disposition = "RELEASE_AUTHORIZED";
      releaseSuccess = true;
    }
  } else if (dossier.disposition_requested === "REVOCATION") {
    disposition = gaps ? "EVIDENCE_MISSING" : "REVOCATION_RECORDED";
  } else if (dossier.disposition_requested === "RECOVERY") {
    disposition = gaps || partial ? "RECOVERY_REQUIRED" : "CHARACTERIZED";
  } else if (dossier.disposition_requested === "CHARACTERIZED") {
    disposition = "CHARACTERIZED";
  } else {
    disposition = "REJECTED";
  }
  if (releaseSuccess && requirements.some((item) => item.status !== "SATISFIED")) {
    releaseSuccess = false;
    disposition = "EVIDENCE_MISSING";
  }
  return finish(dossier, disposition, releaseSuccess, requirements, catalog);
}

function rejectAll(dossier, detail, catalog) {
  return finish(
    dossier,
    "REJECTED",
    false,
    catalog.ids.map((id) => ({ id, status: "REJECTED", detail })),
    catalog,
  );
}

function finish(dossier, disposition, releaseSuccess, requirements, catalog) {
  const ordered = catalog.ids.map((id) => requirements.find((item) => item.id === id)).filter(Boolean);
  return {
    schema: "vantio.ws11.verification-result/v1",
    subject: dossier && dossier.subject ? dossier.subject.package : null,
    disposition_requested: dossier ? dossier.disposition_requested : null,
    disposition,
    release_success: releaseSuccess,
    council_pass: false,
    formal_slsa_level: "NOT_CLAIMED",
    formal_certification: "NOT_CLAIMED",
    formal_reproducibility: "NOT_CLAIMED",
    hardware_backed_provenance: "NOT_CLAIMED",
    verifier: "ws11-independent-release-verifier",
    verifier_version: "1",
    requirements: ordered,
  };
}

export function exitCodeFor(result) {
  if (result.disposition === "REJECTED") return 1;
  if (result.disposition === "EVIDENCE_MISSING" || result.disposition === "PARTIAL_PUBLICATION" || result.disposition === "RECOVERY_REQUIRED") {
    return 2;
  }
  if (result.disposition === "CHARACTERIZED" || result.disposition === "RELEASE_AUTHORIZED" || result.disposition === "REVOCATION_RECORDED") {
    return 0;
  }
  return 1;
}

function validateShape(dossier) {
  if (!isObject(dossier)) return "dossier is not an object";
  if (dossier.schema !== "vantio.ws11.release-dossier/v1") return "schema is not vantio.ws11.release-dossier/v1";
  if (!DISPOSITIONS.has(dossier.disposition_requested)) return "disposition_requested is not allowed";
  if (!isObject(dossier.subject)) return "subject is missing";
  if (!PRODUCTS.has(dossier.subject.product)) return "subject.product is not allowed";
  if (typeof dossier.subject.package !== "string" || dossier.subject.package.length === 0) return "subject.package is missing";
  if (!["public", "private", "mixed"].includes(dossier.subject.distribution)) return "subject.distribution is not allowed";
  if (!Array.isArray(dossier.units) || dossier.units.length === 0) return "units are missing";
  if (!Array.isArray(dossier.pins)) return "pins are missing";
  for (const key of ["reproducibility", "provenance", "sbom", "scans", "retention", "private_distribution", "emergency", "partial", "roles"]) {
    if (!isObject(dossier[key])) return `${key} is missing`;
  }
  if (typeof dossier.roles.roles_are_slots !== "boolean") return "roles.roles_are_slots is missing";
  for (const name of ROLE_NAMES) {
    if (typeof dossier.roles[name] !== "string" || dossier.roles[name].length === 0) return `role ${name} is missing`;
  }
  return null;
}

function evalPins(dossier) {
  if (dossier.pins.length === 0) return { id: "R1", ...rej("pin list is empty") };
  const parts = dossier.pins.map((pin) => {
    if (!isObject(pin) || typeof pin.name !== "string" || typeof pin.value !== "string" || pin.value.length === 0) {
      return rej("pin is missing name or value");
    }
    if (!PIN_KINDS.has(pin.kind)) return rej(`pin ${pin.name} kind is not allowed`);
    if (typeof pin.required_for_publish !== "boolean" || typeof pin.accepted_as_pin !== "boolean") {
      return rej(`pin ${pin.name} is missing required_for_publish or accepted_as_pin`);
    }
    if (pin.accepted_as_pin && !BINDING_KINDS.has(pin.kind)) return rej(`pin ${pin.name} is accepted without a binding kind`);
    if ((pin.kind === "integrity-hash" || pin.kind === "lockfile-digest") && !HEX64.test(pin.value)) {
      return rej(`pin ${pin.name} is not a sha256`);
    }
    if (pin.kind === "git-sha" && !SHA40.test(pin.value)) return rej(`pin ${pin.name} is not a git sha`);
    if (pin.kind === "image-digest" && !IMAGE_DIGEST.test(pin.value)) return rej(`pin ${pin.name} is not an image digest`);
    if (pin.required_for_publish && !BINDING_KINDS.has(pin.kind)) return gap(`pin ${pin.name} is ${pin.kind}`);
    return sat(`pin ${pin.name} recorded`);
  });
  return fold("R1", parts);
}

function evalReproducibility(dossier) {
  const record = dossier.reproducibility;
  if (record.formal_claim !== false) return { id: "R2", ...rej("formal byte-identity claim is set") };
  const builds = Array.isArray(record.builds) ? record.builds : null;
  if (!builds) return { id: "R2", ...rej("builds list is missing") };
  if (record.status === "NOT_ASSESSED") return { id: "R2", ...gap("byte-identity assessment is not recorded") };
  if (record.status === "ASSESSED_NOT_REPRODUCIBLE") {
    if (!Array.isArray(record.reasons) || record.reasons.length === 0) return { id: "R2", ...rej("assessment reasons are missing") };
    if (record.reasons.some((reason) => typeof reason !== "string" || reason.length === 0)) return { id: "R2", ...rej("assessment reason is empty") };
    return { id: "R2", ...sat("assessment recorded; formal byte-identity claim token is NOT_CLAIMED") };
  }
  if (record.status === "BYTE_MATCH_OBSERVED") {
    if (builds.length < 2) return { id: "R2", ...rej("byte match needs two builds") };
    const ids = builds.map((build) => build && build.id);
    if (new Set(ids).size !== builds.length) return { id: "R2", ...rej("build ids are not distinct") };
    const digests = builds.map((build) => build && build.sha256);
    if (digests.some((digest) => !HEX64.test(digest || ""))) return { id: "R2", ...rej("build digest is missing") };
    if (new Set(digests).size !== 1) return { id: "R2", ...rej("build digests differ") };
    return { id: "R2", ...sat("two submitted digests match; formal byte-identity claim token is NOT_CLAIMED") };
  }
  return { id: "R2", ...rej("reproducibility status is not allowed") };
}

function evalManifest(unit) {
  if (!isObject(unit) || typeof unit.package !== "string" || !VERSION.test(unit.version || "")) return rej("unit version is missing");
  if (!["public", "private"].includes(unit.distribution)) return rej(`${unit.package} distribution is not allowed`);
  if (!Array.isArray(unit.artifacts) || unit.artifacts.length === 0) return rej(`${unit.package} artifacts are missing`);
  const parts = unit.artifacts.map((artifact) => evalArtifact(unit, artifact));
  return fold("R3", parts).status === "REJECTED"
    ? rej(parts.filter((part) => part.status === "REJECTED").map((part) => part.detail).join("; "))
    : parts.some((part) => part.status === "GAP")
      ? gap(parts.filter((part) => part.status === "GAP").map((part) => part.detail).join("; "))
      : sat(`${unit.package} manifest recorded`);
}

function evalArtifact(unit, artifact) {
  if (!isObject(artifact) || typeof artifact.filename !== "string" || typeof artifact.role !== "string") return rej("artifact filename is missing");
  if (artifact.version !== unit.version) return rej(`${artifact.filename} version differs from the unit`);
  if (!["public", "private"].includes(artifact.distribution)) return rej(`${artifact.filename} distribution is not allowed`);
  if (artifact.hash_status === "UNRECORDED") {
    if (artifact.sha256 !== null || artifact.byte_length !== null) return rej(`${artifact.filename} records a hash while marked unrecorded`);
    return gap(`${artifact.filename} hash unrecorded`);
  }
  if (artifact.hash_status !== "RECORDED") return rej(`${artifact.filename} hash_status is not allowed`);
  if (!HEX64.test(artifact.sha256 || "") || !Number.isInteger(artifact.byte_length) || artifact.byte_length < 0) {
    return rej(`${artifact.filename} hash or length is missing`);
  }
  if (artifact.source_commit !== "UNRECORDED" && artifact.source_commit !== "UNVERIFIED_THIS_FORCE" && !SHA40.test(artifact.source_commit || "")) {
    return rej(`${artifact.filename} source commit is missing`);
  }
  if (typeof artifact.content_base64 === "string") {
    const buffer = Buffer.from(artifact.content_base64, "base64");
    if (buffer.length !== artifact.byte_length || sha256Buffer(buffer) !== artifact.sha256) {
      return rej(`${artifact.filename} bytes differ from the manifest`);
    }
  }
  return sat(`${artifact.filename} manifest recorded`);
}

function evalCustody(artifact) {
  const custody = artifact.custody;
  if (!isObject(custody) || !isObject(custody.selector) || typeof custody.selector.kind !== "string") return rej(`${artifact.filename} custody is missing`);
  if (custody.selector.kind === "git-tag" && custody.selector_is_integrity === true) {
    return rej(`${artifact.filename} treats a tag as an integrity pin`);
  }
  if (artifact.hash_status === "UNRECORDED") return gap(`${artifact.filename} custody hash unrecorded`);
  if (custody.selector.kind !== "sha256" || custody.selector_is_integrity !== true) {
    return rej(`${artifact.filename} recorded bytes are not bound to a sha256 selector`);
  }
  if (custody.selector.value !== artifact.sha256) return rej(`${artifact.filename} custody hash differs from the manifest`);
  return sat(`${artifact.filename} custody hash matches`);
}

function evalProvenance(dossier) {
  const record = dossier.provenance;
  if (!PROVENANCE.has(record.characterization)) return { id: "R5", ...rej("provenance characterization is not allowed") };
  if (record.slsa_level !== null || record.certification !== null) return { id: "R5", ...rej("formal provenance fields are set") };
  if (record.hardware_backed !== false || record.reproducible_build_claimed !== false) {
    return { id: "R5", ...rej("provenance claim flags are set") };
  }
  if (record.verified !== false && record.verified !== true) return { id: "R5", ...rej("provenance verified flag is missing") };
  if (record.verified === true) {
    if (!HEX64.test(record.bundle_sha256 || "") || typeof record.verification_record !== "string" || record.verification_record.length === 0) {
      return { id: "R5", ...rej("verified provenance is missing a bundle digest") };
    }
  }
  return { id: "R5", ...sat("provenance characterization recorded; formal level token is NOT_CLAIMED") };
}

function evalSbom(dossier) {
  const record = dossier.sbom;
  if (record.completeness === "complete") return { id: "R6", ...rej("sbom completeness overclaims the generated document") };
  if (!SBOM_COMPLETENESS.has(record.completeness) && record.status !== "ABSENT") {
    return { id: "R6", ...rej("sbom completeness is not allowed") };
  }
  if (record.status === "ABSENT") return { id: "R6", ...gap("sbom absent for sealed bytes") };
  if (record.status === "NOT_APPLICABLE") {
    if (record.dependency_graph !== "none" || typeof record.reason !== "string" || record.reason.length === 0) {
      return { id: "R6", ...rej("sbom not-applicable reason is missing") };
    }
    return { id: "R6", ...sat("dependency graph is absent and the sbom gap is named") };
  }
  if (record.status !== "PRESENT") return { id: "R6", ...rej("sbom status is not allowed") };
  if (!SBOM_FORMATS.has(record.format) || !HEX64.test(record.sha256 || "") || !SBOM_COMPLETENESS.has(record.completeness)) {
    return { id: "R6", ...rej("sbom format or digest is missing") };
  }
  if (record.bound_to_artifact !== true) return { id: "R6", ...gap("sbom is not bound to the sealed artifact") };
  return { id: "R6", ...sat("sbom digest recorded") };
}

function evalScanHalf(label, record) {
  if (!isObject(record) || !SCAN_STATUS.has(record.status)) return rej(`${label} status is not allowed`);
  if (record.status === "NOT_RUN" || record.status === "NOT_APPLICABLE") {
    if (typeof record.reason !== "string" || record.reason.length === 0) return rej(`${label} reason is missing`);
    return gap(`${label} result absent for sealed bytes`);
  }
  if (typeof record.tool_name !== "string" || typeof record.tool_version !== "string" || record.tool_version.length === 0) {
    return rej(`${label} tool identity is missing`);
  }
  if (typeof record.scope !== "string" || record.scope.length === 0 || record.scope === "assumed") return rej(`${label} scope is missing`);
  if (!Array.isArray(record.findings)) return rej(`${label} findings are missing`);
  if (record.status === "CLEAN" && record.findings.length > 0) return rej(`${label} clean result includes findings`);
  if (record.status === "FINDINGS") {
    if (record.findings.length === 0) return rej(`${label} findings result is empty`);
    if (record.findings.some((finding) => !isObject(finding) || typeof finding.id !== "string" || finding.accepted !== true)) {
      return gap(`${label} findings are not accepted`);
    }
  }
  return sat(`${label} scan recorded`);
}

function evalScans(dossier) {
  const vuln = evalScanHalf("vulnerability", dossier.scans.vulnerability);
  const license = evalScanHalf("license", dossier.scans.license);
  return fold("R7", [vuln, license]);
}

function evalCleanEnv(unit) {
  const record = unit.clean_env;
  if (!isObject(record)) return rej(`${unit.package} clean environment record is missing`);
  if (record.status === "NOT_RUN") return gap(`${unit.package} clean environment not run`);
  if (record.status === "FAILED") return rej(`${unit.package} clean environment failed`);
  if (record.status === "PASSED_UNCHARACTERIZED") return gap(`${unit.package} install exit was recorded without an environment digest`);
  if (record.status !== "PASSED") return rej(`${unit.package} clean environment status is not allowed`);
  if (record.exit_code !== 0) return rej(`${unit.package} clean environment exit is not zero`);
  if (!IMAGE_DIGEST.test(record.environment_digest || "") || record.environment_characterized !== true) {
    return rej(`${unit.package} clean environment digest is missing`);
  }
  const hashes = unit.artifacts.map((artifact) => artifact.sha256);
  if (!hashes.includes(record.artifact_sha256)) return rej(`${unit.package} clean environment hash differs from the manifest`);
  return sat(`${unit.package} clean environment hash matches`);
}

function evalUpgrade(unit) {
  const record = unit.upgrade;
  if (!isObject(record) || record.verified !== true && record.verified !== false) return rej(`${unit.package} upgrade record is missing`);
  if (record.verified !== true) return gap(`${unit.package} rollback hash unrecorded or unverified`);
  if (!HEX64.test(record.from_sha256 || "") || !HEX64.test(record.to_sha256 || "") || !HEX64.test(record.rollback_sha256 || "")) {
    return rej(`${unit.package} upgrade hashes are missing`);
  }
  if (record.from_sha256 === record.to_sha256) return rej(`${unit.package} upgrade hashes are identical`);
  if (record.rollback_sha256 !== record.from_sha256) return rej(`${unit.package} rollback hash is not the previous artifact`);
  if (record.from_version === record.to_version) return rej(`${unit.package} upgrade versions are identical`);
  return sat(`${unit.package} rollback hash matches the previous artifact`);
}

function evalRegistry(unit) {
  const record = unit.registry;
  if (!isObject(record)) return rej(`${unit.package} registry record is missing`);
  if (record.status === "NOT_FETCHED" || record.status === "ABSENT") return gap(`${unit.package} registry bytes not fetched by this force`);
  if (record.status === "BYTE_MISMATCH") return rej(`${unit.package} registry bytes differ from custody`);
  if (record.status !== "BYTE_MATCH") return rej(`${unit.package} registry status is not allowed`);
  const artifact = unit.artifacts.find((item) => item.sha256 === record.observed_sha256 && item.byte_length === record.observed_bytes);
  if (!artifact) return rej(`${unit.package} registry observation differs from the manifest`);
  if (record.client === "publisher-workflow") return rej(`${unit.package} registry observation was made by the publisher workflow`);
  return sat(`${unit.package} registry bytes match`);
}

function evalClient(unit, dossier) {
  const record = unit.ordinary_client;
  if (!isObject(record)) return rej(`${unit.package} ordinary client record is missing`);
  if (record.status === "NOT_RUN") return gap(`${unit.package} ordinary client proof absent`);
  if (record.status === "FAILED") return rej(`${unit.package} ordinary client proof failed`);
  if (record.status !== "PROVED") return rej(`${unit.package} ordinary client status is not allowed`);
  if (record.client_identity === dossier.roles.publisher || record.client_identity === "publisher-workflow") {
    return rej(`${unit.package} ordinary client is the publisher`);
  }
  if (typeof record.client_identity !== "string" || record.client_identity.length === 0) return rej(`${unit.package} ordinary client identity is missing`);
  const artifact = unit.artifacts.find((item) => item.sha256 === record.sha256);
  if (!artifact) return rej(`${unit.package} ordinary client hash differs from custody`);
  return sat(`${unit.package} ordinary client hash matches custody`);
}

function evalRetention(dossier) {
  const record = dossier.retention;
  const classes = new Set(["public-source", "sealed-bytes", "phantom-private", "private-customer"]);
  if (!classes.has(record.class)) return { id: "R12", ...rej("retention class is not allowed") };
  if (typeof record.location !== "string" || record.location.length === 0) return { id: "R12", ...rej("retention location is missing") };
  if (!Number.isInteger(record.minimum_days) || record.minimum_days <= 0) return { id: "R12", ...rej("retention minimum is missing") };
  if (record.customer_body_in_public_repo === true) return { id: "R12", ...rej("customer body is marked present in the public repository") };
  if ((record.class === "phantom-private" || record.class === "private-customer") && record.customer_body_in_public_repo !== false) {
    return { id: "R12", ...rej("private retention record leaves the public-repository flag unset") };
  }
  if (record.demonstrated === true) {
    if (typeof record.witness !== "string" || record.witness.length === 0) return { id: "R12", ...rej("retention witness is missing") };
    return { id: "R12", ...sat("retention witness recorded") };
  }
  if (record.demonstrated !== false) return { id: "R12", ...rej("retention demonstrated flag is missing") };
  return { id: "R12", ...gap("retention policy named; retention not demonstrated") };
}

function phantomDistributionAgrees(dossier, record) {
  if (record.public_distribution !== false) return false;
  if (!isObject(dossier.subject) || dossier.subject.distribution !== "private") return false;
  if (!Array.isArray(dossier.units) || dossier.units.length === 0) return false;
  for (const unit of dossier.units) {
    if (!isObject(unit) || unit.distribution !== "private") return false;
    if (!Array.isArray(unit.artifacts) || unit.artifacts.length === 0) return false;
    for (const artifact of unit.artifacts) {
      if (!isObject(artifact) || artifact.distribution !== "private") return false;
    }
  }
  return true;
}

function evalPrivateDistribution(dossier) {
  const record = dossier.private_distribution;
  if (typeof record.manual_text === "string" && record.manual_text.length > 0) {
    return { id: "R13", ...rej("customer manual text is present in the dossier") };
  }
  if (record.body_class === "customer-manual") return { id: "R13", ...rej("customer manual body is not carried in this public repository") };
  if (record.customer_body_in_public_repo === true) return { id: "R13", ...rej("customer body is marked present in the public repository") };
  const product = dossier.subject.product;
  if (product === "optics") {
    if (record.customer_body_in_public_repo !== false || record.body_class !== "absent") {
      return { id: "R13", ...rej("optics dossier leaves the customer-body gate incomplete") };
    }
    if (record.public_distribution_of_customer_manual !== false) {
      return { id: "R13", ...rej("optics customer manual distribution flag is unset") };
    }
    return { id: "R13", ...sat("optics customer manual stays out of this public tree") };
  }
  if (record.applicable !== true || record.public_distribution !== false) {
    return { id: "R13", ...rej("private package distribution is public") };
  }
  if (!["private", "ghcr-private", "customer-handoff"].includes(record.channel)) {
    return { id: "R13", ...rej("private channel is not allowed") };
  }
  if (product === "private-customer") {
    if (record.body_class !== "test-double") return { id: "R13", ...rej("private customer body class is not the test double") };
    if (record.bundle_version !== record.manual_version) return { id: "R13", ...rej("manual version differs from the bundle version") };
    if (dossier.disposition_requested === "READY_TO_PUBLISH" || dossier.disposition_requested === "EMERGENCY") {
      return { id: "R13", ...rej("the test double cannot authorize a customer release") };
    }
    return { id: "R13", ...sat("test double stays private and version-matched") };
  }
  if (record.body_class !== "absent") return { id: "R13", ...rej("phantom dossier body class is not absent") };
  if (!phantomDistributionAgrees(dossier, record)) {
    return { id: "R13", ...rej("phantom subject, units, and artifacts do not agree on private distribution") };
  }
  return { id: "R13", ...sat("phantom distribution stays private") };
}

function declaredVersion(root, entry) {
  const text = readFileSync(join(root, entry.manifest), "utf8");
  if (entry.manifest.endsWith(".json")) return JSON.parse(text).version;
  const match = text.match(/^version\s*=\s*"([^"]+)"/m);
  return match ? match[1] : undefined;
}

function evalDocs(unit, metadata, root) {
  const record = unit.docs_gate;
  if (!isObject(record)) return rej(`${unit.package} docs gate is missing`);
  if (record.status === "NOT_APPLICABLE") {
    if (typeof record.reason !== "string" || record.reason.length === 0) return rej(`${unit.package} docs gate reason is missing`);
    return sat(`${unit.package} docs gate is not applicable`);
  }
  if (record.status === "MISMATCH") return rej(`${unit.package} docs version mismatches the package`);
  if (record.status !== "MATCH") return rej(`${unit.package} docs gate status is not allowed`);
  if (record.manifest_version !== unit.version || record.docs_version !== unit.version) {
    return rej(`${unit.package} docs versions differ from the unit`);
  }
  if (metadata) {
    const entry = metadata.packages.find((item) => item.name === unit.package);
    if (entry && entry.version !== unit.version) return rej(`${unit.package} tree version is ${entry.version}`);
    if (entry && root) {
      if (declaredVersion(root, entry) !== unit.version) return rej(`${unit.package} manifest version differs from the unit`);
      for (const extra of entry.also || []) {
        const text = readFileSync(join(root, extra.file), "utf8");
        if (!text.includes(extra.contains)) return rej(`${unit.package} is missing ${extra.contains}`);
      }
    }
  }
  return sat(`${unit.package} docs versions match`);
}

function evalEmergency(dossier) {
  const record = dossier.emergency;
  const requested = dossier.disposition_requested;
  if (requested !== "EMERGENCY" && requested !== "REVOCATION") {
    if (record.invoked !== false) return { id: "R15", ...rej("emergency record is invoked on an ordinary dossier") };
    return { id: "R15", ...sat("emergency path not invoked") };
  }
  if (record.invoked !== true) return { id: "R15", ...rej("emergency disposition is missing invoked") };
  if (record.skip_hash === true) return { id: "R15", ...rej("emergency path skips hash custody") };
  if (typeof record.reason !== "string" || record.reason.length === 0) return { id: "R15", ...rej("emergency reason is missing") };
  if (typeof record.authorization_ref !== "string" || record.authorization_ref.length === 0) {
    return { id: "R15", ...rej("emergency authorization reference is missing") };
  }
  if (dossier.roles.approver === dossier.roles.publisher || dossier.roles.approver === dossier.roles.builder) {
    return { id: "R15", ...rej("emergency approver collides with publisher or builder") };
  }
  if (requested === "REVOCATION") {
    const revocation = record.revocation;
    if (!isObject(revocation)) return { id: "R15", ...rej("revocation record is missing") };
    if (revocation.status === "NOT_PERFORMED") return { id: "R15", ...gap("revocation was not observed") };
    if (revocation.status !== "OBSERVED") return { id: "R15", ...rej("revocation status is not allowed") };
    if (!["yank", "deprecate", "unpublish"].includes(revocation.method)) return { id: "R15", ...rej("revocation method is not allowed") };
    if (!HEX64.test(revocation.sha256 || "") || typeof revocation.observed_at !== "string") {
      return { id: "R15", ...rej("revocation observation is missing") };
    }
    return { id: "R15", ...sat("revocation observation recorded") };
  }
  return { id: "R15", ...sat("emergency authorization recorded without skipping hashes") };
}

function evalPartial(dossier) {
  const record = dossier.partial;
  if (!RECOVERY.has(record.recovery)) return { id: "R16", ...rej("recovery action is not allowed") };
  if (record.recovery === "REUPLOAD_DIFFERENT_BYTES") return { id: "R16", ...rej("recovery replaces bytes for an existing version") };
  if (record.state === "NOT_ASSESSED_THIS_FORCE") return { id: "R16", ...gap("partial publication not assessed") };
  if (record.state === "PARTIAL") {
    if (!(record.published_artifacts > 0) || !(record.expected_artifacts > record.published_artifacts)) {
      return { id: "R16", ...rej("partial counts are inconsistent") };
    }
    if (record.recovery === "NOT_REQUIRED") return { id: "R16", ...rej("partial publication has no recovery") };
    return { id: "R16", ...gap("publication is partial; replacement bytes stay forbidden") };
  }
  if (record.state !== "CLEAR") return { id: "R16", ...rej("partial state is not allowed") };
  if (!Number.isInteger(record.expected_artifacts) || !Number.isInteger(record.published_artifacts)) {
    return { id: "R16", ...rej("publication counts are missing") };
  }
  if (record.published_artifacts !== 0 && record.published_artifacts !== record.expected_artifacts) {
    return { id: "R16", ...rej("publication counts are neither complete nor unpublished") };
  }
  return { id: "R16", ...sat("publication counts are complete or the version is unpublished") };
}

function evalRoles(dossier) {
  const roles = dossier.roles;
  const ids = ROLE_NAMES.map((name) => roles[name]);
  if (new Set(ids).size !== ids.length) return { id: "R17", ...rej("release roles are not distinct") };
  if (roles.verifier === roles.publisher) return { id: "R17", ...rej("verifier is the publisher") };
  if (roles.approver === roles.publisher) return { id: "R17", ...rej("approver is the publisher") };
  if ((dossier.disposition_requested === "READY_TO_PUBLISH" || dossier.disposition_requested === "EMERGENCY" || dossier.disposition_requested === "REVOCATION") && roles.roles_are_slots) {
    return { id: "R17", ...rej("publish request still uses role slots") };
  }
  if (!roles.roles_are_slots && roles.approver_recorded !== true && dossier.disposition_requested !== "CHARACTERIZED" && dossier.disposition_requested !== "RECOVERY") {
    return { id: "R17", ...rej("approver record is missing") };
  }
  return { id: "R17", ...sat(roles.roles_are_slots ? "role slots are distinct" : "acting roles are distinct") };
}
