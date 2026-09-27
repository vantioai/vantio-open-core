# PKG-02 Unit A vocabulary

PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

Machine-readable file: `packages/optics-record-vocabulary/vocabulary/record-vocabulary.json`.

The file is generated from the merged planning vocabulary and the PKG-01 catalog, enums, contract metadata, and prohibited-name list. Generation copies declared field attributes. It does not copy detector code. `tools/build-vocabulary.cjs` rebuilds the object in memory. The test suite does not write that file.

## Row identity

| Set | Count | Treatment |
| --- | --- | --- |
| Planning entries | 187 | All retained |
| Canonical rows | 120 | One row per `record_type` + `canonical_name`. None were merged away |
| Unique canonical names | 88 | 22 names occur on more than one record type, which adds 32 rows |
| Compatibility rows | 67 | Kept as compatibility rows because they are not PKG-01 catalog fields |

`reason_code` is the only repeated name whose semantic dimension differs by record type: `import_disposition` on `import_quarantine`, `validation_structure` on `validation_result`. Every other repeated name keeps one dimension.

Each canonical row carries the force attributes: canonical name, semantic dimension, type, optionality, allowed enum values, absent-value behavior, invalid-value behavior, compatibility aliases, legacy interpretation, evidence-origin effect, issue-location effect, completeness effect, privacy class, metric eligibility, export eligibility, proof eligibility, reader fallback, writer requirement, and deprecation posture.

Unknown-enum posture is `NORMALIZE_UNAVAILABLE`, `NORMALIZE_DECLARED`, `REJECT_FIELD`, or `REJECT_RECORD`. It is never `COERCE_TO_SUCCESS`.

## Semantic dimensions

Required dimensions, each represented:

| Dimension | What it holds |
| --- | --- |
| `schema_identity_status` | `record_type`, `schema_status`, `schema_status_seen` |
| `record_identity` | Event, annotation, subject, and content identifiers |
| `execution_identity` | Session, run, trace, span, and producer identity |
| `process_identity` | Process ids, runtime, platform, arch |
| `timestamps_duration` | Timestamps, duration, clock quality |
| `destination_provider_identity` | Host, port, scheme, method, path, provider, mediation |
| `http_network_outcomes` | HTTP status, failure kind, error class, byte counts |
| `optics_health` | `optics_status` and validation health counters |
| `workload_outcome` | `application_status` and the application outcome label |
| `dependency_outcome` | `provider_response_phrase` |
| `issue_location` | `issue_location` and its label |
| `evidence_origin_basis` | Origin, trace basis, session basis, reader origin label |
| `coverage` | `coverage_note`, `call_count` |
| `completeness` | `completeness_impact`, `completeness_inputs` |
| `integrity` | `product_health` value family `integrity_state`: `OK`, `FAILED`, `UNKNOWN` |
| `sampling` | `sampling` |
| `drop_state` | `dropped_count` |
| `version_identity` | `schema_version`, `runtime_version`, `cli_or_sdk_version`, plus the Unicode profile compatibility names |

`lifecycle` is `attempt_lifecycle`, not completeness and not optics health. `action` is `observation_action`. Envelope `span_id` stays type `null` (`VALUE_IS_NULL`), which is different from an omitted span.

`integrity_state` is not a new catalog field. PKG-02 does not add one. The tokens are disjoint from `optics_status`.

## Privacy and versions

Canonical privacy classes stay `STRUCTURAL`, `IDENTITY`, `DIAGNOSTIC`, and `CUSTOMER_TEXT`. Metric, export, and proof eligibility match the PKG-01 catalog booleans.

Frozen versions recorded on the vocabulary: CLI `0.3.24`, Node SDK `0.2.4`, Python `3.1.0`, evidence contract `0.0.0-unstable-pre-1.0`.

`SUCCESS` remains a member of `optics_status` because the catalog enum contains it. Absence does not store it. See `NO-OPTIMISTIC-DEFAULTS.md`.
