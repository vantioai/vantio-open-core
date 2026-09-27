# WS11 requirements

Audience: INTERNAL_RESTRICTED

The catalog is `REQUIREMENTS.json`. The evaluator in `scripts/release/ws11/evaluate.mjs` is the behavior. This page is the short map a council can read beside the architecture notes.

| Id | Name | Current Optics dossier | Current Phantom dossier | Current customer test double |
| --- | --- | --- | --- | --- |
| R1 | Pinning | Gap. Lockfile and sealed Python hashes bind. Actions, Node 22, hatchling, and the CLI tarball do not. | Gap. Planning-note inputs are `prior-record-unverified`. | Gap. Customer bytes are `unrecorded`. |
| R2 | Byte-identity assessment | Satisfied as an assessment. Formal token `NOT_CLAIMED`. | Satisfied as an assessment. This force did not re-fetch the image. | Satisfied as an assessment of a test double. |
| R3 | Artifact manifest | Gap. Python wheel and sdist are recorded. Other units are `UNRECORDED`. | Gap. Image hash `UNRECORDED`. | Satisfied for the test-double file hash. |
| R4 | Exact-hash custody | Gap where the hash is unrecorded. CLI tag `v0.3.24` has `selector_is_integrity` false. | Gap. | Satisfied. The selector is the test-double SHA-256. |
| R5 | Signing and provenance characterization | Satisfied as `GITHUB_ATTESTATION_CAPABLE_UNVERIFIED`. Formal level token `NOT_CLAIMED`. | Satisfied as `NONE`. | Satisfied as `NONE`. |
| R6 | SBOM where appropriate | Gap. A workspace CycloneDX file exists and is not bound to sealed bytes. | Gap. No SBOM was fetched. | Satisfied as not applicable. The test double has no dependency graph. |
| R7 | Vulnerability and license scan | Gap. Sealed bytes were not scanned. The manifest license scan is a separate tree report with findings. | Gap. | Gap. |
| R8 | Clean-environment install | Gap. Not run. | Gap. Not run. | Gap. Not run. |
| R9 | Upgrade and rollback verification | Gap. Python names 3.0.14 to 3.1.0 and leaves the previous hash null. | Gap. | Gap. |
| R10 | Registry-byte verification | Gap. `NOT_FETCHED`, including Python, whose historical register label is only a citation. | Gap. | Gap. |
| R11 | Ordinary-client proof | Gap. Not run. | Gap. | Gap. |
| R12 | Evidence retention | Gap. Class and location are named. `demonstrated` is false. | Gap. Class `phantom-private`. | Gap. Class `private-customer`. |
| R13 | Private Phantom Engine and customer distribution | Satisfied. Customer-manual flags are closed. | Satisfied. `public_distribution` false agrees with private subject, unit, and artifact distribution. Channel `private`. Body absent. | Satisfied for characterization. The test double cannot authorize a release. |
| R14 | Version-matched docs gates | Satisfied against `VERSION-METADATA.json` and the manifests. | Satisfied as not applicable. | Satisfied as not applicable. |
| R15 | Emergency release and revocation | Satisfied. Path not invoked. | Satisfied. Path not invoked. | Satisfied. Path not invoked. |
| R16 | Partial-publication recovery | Gap. Not assessed. Recovery value remains `DO_NOT_REPLACE_BYTES`. | Gap. | Gap. |
| R17 | Role separation | Satisfied as distinct slots. | Satisfied as distinct slots. | Satisfied as distinct slots. |
| R18 | Independent release verifier | Satisfied. `council_pass` false. | Satisfied. `council_pass` false. | Satisfied. `council_pass` false. |

A publish request moves every Gap row to Satisfied with evidence, or the verifier returns `EVIDENCE_MISSING` or `PARTIAL_PUBLICATION` and `release_success` false. Rejected rows stop the dossier.

The denylist of dossier phrases is `REQUIREMENTS.json` `forbidden_claim_patterns`. The tests feed known overclaim phrases into that denylist and expect rejection.
