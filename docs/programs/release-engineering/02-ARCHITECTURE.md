# WS11 architecture

Audience: INTERNAL_RESTRICTED

These are the council notes for the release-engineering packet. They describe the verifier this force added. They are not a council verdict.

## Components

| Piece | Path | Role |
| --- | --- | --- |
| Requirement catalog and claim denylist | `REQUIREMENTS.json` | R1–R18 names and the strings a dossier may not carry |
| Retention classes | `RETENTION-POLICY.json` | Minimum days and locations. `operated_in_this_force` is false |
| Role rules | `ROLE-SEPARATION.json` | Six roles and the collisions the verifier rejects |
| Pin report, SBOM, license scan, evaluations | `generated/` | Regenerated from the tree. Tests compare bytes |
| Dossiers | `dossiers/` | One current characterization per surface |
| Inventory and SBOM builder | `scripts/release/ws11/inventory.mjs` | Reads workflows, the lockfile, the sealed Python pins, and manifests |
| Dossier generator | `scripts/release/ws11/characterize.mjs` | Builds the three current dossiers from those reads |
| Evaluator | `scripts/release/ws11/evaluate.mjs` | R1–R18. Fail closed |
| Command | `scripts/release/ws11/verify.mjs` | Independent verifier. R18 |

CI runs the evaluator from the existing `release-governance` job in `.github/workflows/ci.yml`. That job already refuses registry writes. This force adds the WS11 test file to the same job.

## Disposition

The evaluator returns one disposition:

| Disposition | `release_success` | Exit |
| --- | --- | --- |
| `CHARACTERIZED` | false | 0 |
| `RELEASE_AUTHORIZED` | true | 0 |
| `REVOCATION_RECORDED` | false | 0 |
| `EVIDENCE_MISSING` | false | 2 |
| `PARTIAL_PUBLICATION` | false | 2 |
| `RECOVERY_REQUIRED` | false | 2 |
| `REJECTED` | false | 1 |

`RELEASE_AUTHORIZED` requires `READY_TO_PUBLISH` or `EMERGENCY`, every requirement `SATISFIED`, and partial state `CLEAR`. A complete dossier that only asks to be characterized stays `release_success` false. A dossier cannot set `release_success`, `council_pass`, or `program_classification`. The result always sets `council_pass` false and the four claim tokens to `NOT_CLAIMED`.

`REVOCATION_RECORDED` is an observation that a yank, deprecate, or unpublish was seen. It is not a release.

## Requirement binding

R1 accepts a pin only for kinds `lockfile-digest`, `exact-version`, `integrity-hash`, `git-sha`, and `image-digest`. Kinds `unpinned`, `prior-record-unverified`, and `unrecorded` are gaps when `required_for_publish` is true. Setting `accepted_as_pin` on a gap kind is a rejection.

R2 records an assessment. `ASSESSED_NOT_REPRODUCIBLE` with reasons satisfies the assessment. `BYTE_MATCH_OBSERVED` requires two builds, distinct ids, and one digest. The formal byte-identity token stays `NOT_CLAIMED` in both cases.

R3 and R4 require filename, version, distribution, and either an explicit `UNRECORDED` hash or a SHA-256 and byte length. Optional `content_base64` is hashed and compared. A git tag may be a selector. `selector_is_integrity` true on a tag is a rejection. Recorded custody uses a `sha256` selector whose value equals the artifact.

R5 allows `NONE`, `GITHUB_ATTESTATION_CAPABLE_UNVERIFIED`, `PEP740_CAPABLE_UNCLAIMED`, and `BUNDLE_PRESENT_UNVERIFIED`. The level field and the conformance field stay null. `hardware_backed` and `reproducible_build_claimed` stay false. `verified: true` requires a bundle SHA-256 and a verification record, and it still leaves the formal level token `NOT_CLAIMED`.

R6 allows an absent SBOM as a gap. `NOT_APPLICABLE` requires `dependency_graph: none` and a reason. A present SBOM names CycloneDX 1.5 or SPDX 2.3, a SHA-256, and a completeness value from the allowlist. The value `complete` is rejected. `bound_to_artifact` false is a gap.

R7 requires a vulnerability half and a license half. `NOT_RUN` is a gap. `CLEAN` with findings, or without a tool version, is a rejection. Unaccepted findings are a gap.

R8 `PASSED` requires exit code 0, an image digest, `environment_characterized: true`, and an artifact hash that matches the manifest. `PASSED` without a digest is a rejection. `NOT_RUN` is a gap.

R9 `verified: true` requires distinct from/to hashes and a rollback hash equal to the previous artifact. Anything short of that is a gap or a rejection.

R10 `BYTE_MATCH` requires the observed SHA-256 and byte length to match an artifact. The observer cannot be `publisher-workflow`. `NOT_FETCHED` is a gap. A historical register label on the same object does not change that.

R11 `PROVED` requires a client identity different from the publisher and a hash that matches custody.

R12 names a retention class, a location, and a positive minimum. Private classes keep `customer_body_in_public_repo` false. `demonstrated: false` is a gap. The policy file says the retention archive was not operated in this force.

R13 rejects customer manual text, `body_class: customer-manual`, and a public distribution flag on Phantom Engine or the private customer package. Optics must keep the customer-manual flags closed. The test double may be characterized. It cannot authorize a customer release. Phantom Engine in this packet was not re-fetched.

R14 compares each unit's manifest version and docs version with the unit version. When the package is in `VERSION-METADATA.json`, the evaluator also reads the manifest and the `also` snippets. `MISMATCH` is a rejection. The existing `packageVersionProblems` check remains the tree-wide docs gate. This force calls it from the WS11 tests.

R15 leaves ordinary dossiers with `invoked: false`. An emergency or revocation sets `invoked: true`, a reason, and an authorization reference. `skip_hash: true` is a rejection. The approver differs from the publisher and the builder. A revocation observation names yank, deprecate, or unpublish, a SHA-256, and an observed time. `NOT_PERFORMED` is a gap.

R16 recovery `REUPLOAD_DIFFERENT_BYTES` is a rejection. `PARTIAL` with a safe recovery yields `PARTIAL_PUBLICATION` and `release_success` false. `NOT_ASSESSED_THIS_FORCE` is a gap. The current dossiers use that gap. They do not treat the historical Python publication label as a fresh partial-publication assessment.

R17 requires six distinct role ids. The verifier differs from the publisher. The approver differs from the publisher. A publish, emergency, or revocation request sets `roles_are_slots` false and `approver_recorded` true. Current dossiers name slots only.

R18 is this evaluator. It is not the GitHub environment that approves npm or PyPI, and it is not the council.

## What the current dossiers are for

They are the honest characterization of this commit. They are the fixtures the direct tests evaluate. A future release supplies a new dossier. The generator command `node scripts/release/ws11/verify.mjs --emit` rewrites the committed characterization from the tree. `--emit` does not publish.
