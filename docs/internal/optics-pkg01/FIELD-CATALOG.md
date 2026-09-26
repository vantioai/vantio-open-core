# PKG-01 field catalog

Audience: INTERNAL_RESTRICTED

The catalog is `packages/optics-evidence-contract/contract/field-catalog.json`. It is not a JSON Schema, and it is not a stable public schema. `schema_status` is `unstable-pre-1.0`. `schema_version` `0` means unassigned.

120 field rows. Record classes: `run_envelope`, `observation_event`, `derived_diagnostic`, `annotation`, `product_health`, `import_quarantine`, `validation_result`. `proof_manifest` is listed as not written by this slice.

Each row carries the canonical name, type, required flag, producer, origin, purpose, sensitivity, cardinality, index / export / proof / metric eligibility, normalization, max size, invalid disposition, compatibility note, and fixture coverage. Unknown keys are denied. Usage, token counts, cost, machine hostname, and an annotation evidence-origin are not allowlisted fields.

Enums, ranks, and remediation codes are in `contract/enums.json`. Bounds and normalization rules are in `contract/normalization.json`. Prohibited names and detectors are in `contract/prohibited-fields.json`. Package identity and the unresolved Founder decisions are in `contract/contract-metadata.json`.

Writer origins are `LOCAL_OBSERVATION`, `SIMULATED_DEMO`, `IMPORTED`, `TEST_FIXTURE`, `PRODUCT_HEALTH`, and `DERIVED_DIAGNOSTIC`. `LEGACY_UNMARKED` is a reader label. It is not stored as a writer origin and it is not promoted to `LOCAL_OBSERVATION`.
