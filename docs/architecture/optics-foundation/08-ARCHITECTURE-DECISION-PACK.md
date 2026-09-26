# Architecture decision pack

Audience: INTERNAL_RESTRICTED

Council verdict: `OPTICS_FOUNDATION_ARCHITECTURE_COUNCIL_PASSED`

This pack records producer decisions for A0–A6. It does not implement them. Unresolved items stay unresolved.

## 1. Program identity

Optics Foundation architecture, stages A0–A6, branch `architecture/optics-foundation-a0-a7`, base `d6b74d41808a43f251d6de46e1313625a025d16d`. Writable path is this directory. Detail: `00-PROGRAM-BOUNDARY.md`.

## 2. Product boundary

Optics observes structural metadata and does not enforce. Phantom Engine enforces. Co-located enforcement branches in the current interceptor are inventoried and are not extended. Decision: the foundation writer’s `action` value is `OBSERVED` only.

## 3. Audience and disclosure

Audience is `INTERNAL_RESTRICTED`. This pack is not public copy, not a release note, and not customer validation.

## 4. Inventory disposition

A0 is `OPTICS_FOUNDATION_A0_INVENTORY_COMPLETE`. Conflicts between Node and Python, and between docs and source, remain `CONFLICTING`. No product file was edited to remove them.

## 5. Evidence classes

Observed, derived diagnostic, annotation, simulated demo, imported, product-health, optional product telemetry, portable proof, fixture, and unsupported/unavailable are separate. Default queries return `LOCAL_OBSERVATION` only. Detail: `02-EVIDENCE-AND-PRIVACY-CONTRACT.md`.

## 6. Evidence-origin values

Writer values are `LOCAL_OBSERVATION`, `SIMULATED_DEMO`, `IMPORTED`, `TEST_FIXTURE`, `PRODUCT_HEALTH`, and `DERIVED_DIAGNOSTIC`. Missing origin on legacy files is the reader state `LEGACY_UNMARKED`. A reader preserves an allowlisted origin only with a recognized Optics producer, version, and sufficient provenance. Otherwise the disposition is `LEGACY_UNMARKED`, including a claimed `LOCAL_OBSERVATION` without that provenance. Imports store `IMPORTED` and preserve `original_evidence_origin` separately. Migration does not upgrade evidence maturity. Founder decision 6 stays unresolved. Annotations use `annotation_role` and do not receive a seventh origin.

## 7. Issue location

Machine enum: `NONE`, `OPTICS`, `CUSTOMER_APPLICATION`, `PROVIDER_INTERACTION`, `NETWORK`, `ENVIRONMENT`, `CONFIGURATION`, `COVERAGE`, `UNKNOWN`. `NONE` is the value for a successful operation and for HTTP 2xx/3xx. HTTP 4xx/5xx is `PROVIDER_INTERACTION` where the unsuccessful response was observed. The human label is “Provider interaction.” Display text does not use “Provider fault.” `optics_status` `SUCCESS` means the record was stored. Optics write failures, including disk pressure on the write path, are `OPTICS`. An undetermined layer is `UNKNOWN`. The single rule is A1 section 3. A5 uses that rule.

## 8. Allowlisted fields

Persisted keys are the catalog in A1 section 4. Unknown keys are dropped before write. `schema_status` is `unstable-pre-1.0` on every new object.

## 9. Prohibited data

Bodies, prompts, completions, header maps, query strings, secrets, exception messages, environment dumps, telemetry anonymous ids, and secret-shaped strings inside allowlisted text are prohibited. Reject overlong paths instead of truncating them into storage.

## 10. Privacy invariants

Six release-blocking invariants are specified in A1 section 6. None is marked passing. Current privacy behavior is `PARTIAL` in the inventory.

## 11. Product telemetry

Keep the existing opt-in channel, default off, disable precedence unchanged, separate file and destination. Do not store the ping in the evidence store. Do not add fields.

## 12. Operational store

`STORE_OPTION_C: FOUNDER_RATIFIED_ARCHITECTURE_ONLY`. Embedded SQLite, WAL, application-owned schema, path `~/.vantio/optics/store.sqlite` under the evidence root. No file is created now. Ratification does not authorize a database, a Node binding, a migration, record conversion, or a package change. The store is not implemented, tested, proved, or customer-validated.

## 13. Rejected store options

A (per-run JSON as the long-term index), B (JSONL plus sidecar as the index), D (embedded analytical engine), and E (daemon or network store) are rejected for the reasons in `03-OPERATIONAL-STORE-AND-PORTABLE-PROOF.md`. A and B remain relevant as legacy input and as export shapes.

## 14. Portable proof

The package is `proof.json` plus `manifest.json`. The only eligible byte form is Optics Canonical JSON profile `OPTICS_CANONICAL_JSON` version `1`, specified in A2. Pretty-printed JSON and non-profile compact JSON are not eligible. HTML and Markdown are renderings and are outside the hash. The manifest records the proof schema, the scheme and version, the SHA-256, the byte length, and the A4 completeness and reasons. The hash is not an attestation.

## 15. Prohibited proof language

Do not call the proof tamper-proof, WORM, notarized, certified, regulator-approved, or externally attested.

## 16. Retention

Default unbounded. No silent deletion. Future prune requires a dry-run manifest and a second explicit step. Commands are not created. Exported proofs are not rewritten by compaction.

## 17. Schema posture

No stable v1. Legacy JSON `schema_version` 2 is not reused as the operational `user_version`. `privacy_generation` starts at 1 when an implementation first writes the allowlist.

## 18. Corrupt-store rule

A corrupt store stops normal writes, preserves original bytes, and is not replaced with an empty store. Disclosure is an external recovery envelope that does not depend on the failed file. States are `STOPPED_PRESERVED`, `READ_ONLY_SALVAGE`, `RECOVERY_REQUIRED`, `RECOVERED_TO_NEW_STORE`, and `RECOVERY_FAILED`. Salvage is classified, bounded, and `PARTIAL` or `UNAVAILABLE`, never `COMPLETE`. Replacement is an explicit workflow onto a new store id. T10 matches A3. Newer-schema and weaker-writer refusals use the same envelope.

## 19. Node and Python compatibility

One allowlist. Catalog provider identity, not substring guess. Zero-call attached runs get an envelope. Human sentences are derived diagnostics. Enforcement actions are not Optics rows. `VANTIO_HOME` must be honored by future readers. The current CLI is not patched.

## 20. Legacy JSON

Dual-read adapter (option L2) plus an explicit copy that keeps originals (option L3). No copy on first open. Demo host maps to `SIMULATED_DEMO`. An allowlisted origin is preserved only with recognized producer provenance. Every other legacy file stays `LEGACY_UNMARKED`. Default trends exclude `LEGACY_UNMARKED`. Corrupt files are counted and skipped, not deleted. The copy does not upgrade evidence maturity.

## 21. Identity hierarchy

`session_id`, then `run_id`, then `trace_id`, then `span_id`. `run_id` is one wrapped execution boundary. A wrapped child gets a new `run_id`. `VANTIO_TRACE_ID` is asserted context, basis `ASSERTED_CONTEXT`, and is not observation proof. `parent_run_id` comes only from `VANTIO_PARENT_RUN_ID`. `producer_sequence` is scoped to `producer_id`. Global order is timestamp plus the tie-breakers in A4. `session_id` is optional bounded UTF-8 with a required `session_id_basis`, architecture max `OPTICS_SESSION_ID_MAX_BYTES` = 80, and is never a metric label. It is not inferred from time.

## 22. Correlation rules

Correlation is by writer-stamped ids. Timestamp proximity is not causality and is not parenthood. Malformed context is dropped and counted. An unobserved child is a coverage gap. Conflicting parenthood and conflicting producer sequences stay visible.

## 23. Deduplication

`event_id` is the encoding of (`producer_id`, `producer_sequence`) in A4. The same id with the same identity does not inflate counts. A conflicting reuse stays visible. No time-window heuristic while the window is `NOT_SET`.

## 24. Destination versus provider

Destination is normalized host, explicit port, scheme, and path. Provider is a catalog id plus confidence `CATALOG`, `REGIONAL_PATTERN`, `LOCAL_OLLAMA`, or `NONE`. Substring `guessProvider` is not the target.

## 25. Bounded query

Filters, limit 100 default and 500 maximum, UTC time bounds, opaque cursor, two sorts. No arbitrary SQL, no caller regular expressions, no body inspection. Saved views store the query. The response envelope carries `declaredScope`, `matchingRecords`, `returnedRecords`, `hasMore`, `completeness`, `completenessReasons`, `integrityState`, `samplingState`, and `dropState`. Completeness describes the declared scope. Pagination does not define it. `PARTIAL` is defined in A4. A future UI must not present `PARTIAL`, `UNKNOWN`, or `UNAVAILABLE` as complete.

## 26. Cardinality

Only the indexed allowlist is predicate-capable. Metric labels use `LOW` cardinality enums and `provider_id` only. Paths, run ids, session ids, and raw hosts are not metric labels.

## 27. Self-observability

Product-health names in A5 are the diagnostic set. They are excluded from customer activity. The default answer still carries drop, integrity, and sampling state on the query envelope. Recursion stops after one internal failure. That in-memory stop is not the corrupt-store disclosure.

## 28. Fail-open

Optics failures do not fail, hang, or alter application output, and do not fabricate success. Exceptions are privacy drop and evidence-root confinement. Both still leave the application response alone. Enforcement is not an Optics exception.

## 29. Record lifecycle

`COMPLETE`, `PARTIAL`, `INTERRUPTED`, `ABANDONED`, `RECOVERED`. Current files do not carry these values. They are not backfilled by guesswork.

## 30. Nonfunctional budgets

All twelve `NFR-*` targets are `NOT_SET`. No example number from the roadmap is adopted.

## 31. Overload

Default `UNSAMPLED`. Queue-full and size-limit behavior drop explicitly and do not delete history to make room. Sampling is not introduced.

## 32. Clock

UTC instants. Monotonic duration when available. No negative durations. Order ties by `producer_id`, then `producer_sequence`, then `event_id`. Freshness, completeness, and integrity are separate envelope fields. Freshness value `CURRENT` is not emitted until a window exists, and that window is `NOT_SET`, so the honest freshness value is `UNKNOWN`.

## 33. Threat model

Cases T1–T15 in `07-THREAT-MODEL.md`. Residual risk `UNSET`. Implementation `NOT_STARTED` except where the inventory already records a narrower current behavior.

## 34. Gates

Gates 1–7 are the documents in this directory. The first council reopened gates 2–7. The fresh independent council accepted gates 2–7 as architecture documents. Gate 8 is a separate Founder implementation Force and is not open. See `09-IMPLEMENTATION-GATES.md`.

## 35. Unresolved Founder decisions

1. Resolved for this architecture only: `STORE_OPTION_C: FOUNDER_RATIFIED_ARCHITECTURE_ONLY`. Not an implementation authorization.
2. Usage and cost metadata (OF-05). Not allowlisted.
3. Alerting mode among run-time, post-run, external scheduler, and explicit service (OF-45). Not selected. No daemon.
4. Numeric targets for every `NFR-*` budget (OF-32).
5. At-rest encryption. Not selected.
6. Whether a customer-run promote may stamp `LEGACY_UNMARKED` as `LOCAL_OBSERVATION`.
7. Whether annotations need a seventh origin value. This pack uses `annotation_role` instead.
8. Windows ACL specifics beyond owner-only intent.
9. Node SQLite binding. Not selected.
10. Freshness window that would allow the token `CURRENT`. Not set.
11. Optional persisted machine hostname. Not allowlisted. Docs that show `machine` disagree with writers.
12. OTLP or SIEM export. Not authorized.
13. Local UI charter (OF-06) and accessibility (OF-37). Prerequisites are recorded. The UI is not designed here as a build.

Council disposition of this list, 2026-09-26: the council ratified none of them. A later Founder architecture decision ratified item 1 only, as `STORE_OPTION_C: FOUNDER_RATIFIED_ARCHITECTURE_ONLY`. Items 2–13 stay unresolved. No item was added.

## 36. First council verdict (historical)

Independent council: Cursor cloud agent `bc-fd7a995a-0bba-5f0c-955b-f21702e5c6a2`, model Grok 4.7, reviewing producer tip `8aef23cd6886139d3b8f7de52cfb28c0972628cd`. This agent did not produce A0–A6.

This section records the first council only. The current verdict is section 41.

First council verdict: `NEEDS_REVISION`

First council force classification: `OPTICS_FOUNDATION_ARCHITECTURE_NEEDS_REVISION`

The first council’s seat table is in git history at commit `48bec77`. `10-INDEPENDENT-COUNCIL-REPORT.md` now holds the fresh re-council report.

Historical gate effect of that first council: gates 2, 3, 4, 5, 6, and 7 were reopened. Gate 1 stayed accepted. Gate 8 stayed closed. A8 was not started.

The producer classification that the council reviewed was `OPTICS_FOUNDATION_A6_READY_FOR_COUNCIL`. This revision’s producer classification is in section 40. It is not a council pass.

This pack does not authorize implementation, a release, a tag, a seal, a publish, a store file, a migration, a UI, a daemon, OTLP, alerting, or A8. The revision producer did not rewrite the first council record. The fresh re-council replaced `10-INDEPENDENT-COUNCIL-REPORT.md`.

## 37. Nonblocking notes left unresolved

These notes are not the six blockers. This revision does not close them.

- Inventory finding 1.3 still understates missing response size. The Node exit mapper stores `call.bytes || 0`. The target catalog already forbids inventing that zero. `01-CURRENT-STATE-INVENTORY.md` was not edited.
- The A2 scorecard still gives option C a pass on application policies that file stores can also enforce. The scorecard was not rescored. Ratification does not convert those cells into an engine proof.
- Annotation’s seventh origin stays open (Founder decision 7). The allowlist cell no longer cites `DERIVED_DIAGNOSTIC` as the annotation origin. That repair does not add an origin.
- Whether a customer promote may stamp `LEGACY_UNMARKED` as `LOCAL_OBSERVATION` stays Founder decision 6. Default trends exclude `LEGACY_UNMARKED`, and that exclusion is part of `declaredScope`.
- Windows ACL, the Node binding, encryption, every `NFR-*` number, the freshness window for `CURRENT`, alerting, OTLP, and the UI charter stay unresolved.
- OF-36 records UI security prerequisites. OF-06 stays `TARGET_DESIGN`.
- Co-located block, redact, and cap branches are outside Optics fail-open. The observation-path invariant stands.
- A future SQLite call on process exit can delay exit. The `NOT_SET` shutdown budget still blocks an invented timeout.

## 38. Founder decisions after this revision

Item 1 in section 35 is ratified as architecture only. Items 2–13 remain unresolved. The first council resolved none of them. See `10-INDEPENDENT-COUNCIL-REPORT.md` for the council’s copy of the list.

## 39. Reconciliation of OF-27, OF-33, OF-34, and OF-43

No row is `IMPLEMENTED`, `SHIPPED`, `PROVED_EXTERNAL`, or `CUSTOMER_VALIDATED`. Required proof tiers below are what a future Gate 8 Force would still need. This revision assigns none of those tiers. `evidence_tier` stays `UNSET`.

### OF-27 — Data-quality dimensions

- Original blocking reason: freshness, completeness, and integrity were named separately and were not fields of one read answer, so a page could look complete while capture was partial.
- Revised decision: the A4 response envelope carries `freshness`, `completeness`, `completenessReasons`, and `integrityState` together, plus `samplingState` and `dropState`. Completeness describes declared scope. `CURRENT` remains unemitted while its window is unset, so freshness is `UNKNOWN`.
- Affected documents: A1, A2, A4, A5, this pack, the threat model, and `TRACEABILITY-MATRIX.json`.
- Required tests: the A4 completeness architecture test plan.
- Required proof tier before an external claim: `INTEGRATION_PROVED` on the envelope. Not assigned now.
- Remaining Founder decision: item 10, the freshness window for `CURRENT`.
- Revised status: `ARCHITECTURE_DEFINED`.

### OF-33 — Graceful degradation

- Original blocking reason: the application continues, and the default read did not have to show drops, so loss could look complete.
- Revised decision: the application still continues. `dropState` and `completeness` are on every default answer, including when product-health rows are absent from the timeline. Known drops in scope are `PARTIAL`.
- Affected documents: A4, A5, this pack, and `TRACEABILITY-MATRIX.json`.
- Required tests: the drop row of the A4 completeness test plan, plus the existing explicit-drop fixtures in A5.
- Required proof tier before an external claim: `INTEGRATION_PROVED`. Not assigned now.
- Remaining Founder decision: none for this requirement. Numeric overload budgets stay Founder decision 4 and are not this requirement’s status.
- Revised status: `ARCHITECTURE_DEFINED`.

### OF-34 — Crash consistency

- Original blocking reason: A3 stopped on a corrupt file, T10 also allowed bounded read-only, and disclosure was a health row inside the store that failed.
- Revised decision: corruption enters `STOPPED_PRESERVED`, preserves bytes, and writes an external recovery envelope. `READ_ONLY_SALVAGE` is a later classified mode. Salvage is `PARTIAL` or `UNAVAILABLE`, never `COMPLETE`. T10 matches A3. Replacement is explicit and uses a new store id.
- Affected documents: A2, A3, A5, the threat model, this pack, and `TRACEABILITY-MATRIX.json`.
- Required tests: the A3 corrupt-store architecture test plan.
- Required proof tier before an external claim: `INTEGRATION_PROVED`. Not assigned now.
- Remaining Founder decision: none for the recovery rule. At-rest encryption and the Node binding stay unresolved and are not selected by this rule.
- Revised status: `ARCHITECTURE_DEFINED`.

### OF-43 — Export formats

- Original blocking reason: pretty-printed and compact JSON were both allowed, and no canonical byte profile was defined for the SHA-256.
- Revised decision: profile B, `OPTICS_CANONICAL_JSON` version `1`, is the only eligible byte form for `proof.json` and `manifest.json`. The golden vector in A2 names the bytes, the length, and the SHA-256. HTML and Markdown stay renderings. OTLP stays unauthorized.
- Affected documents: A1, A2, A4, this pack, and `TRACEABILITY-MATRIX.json`.
- Required tests: the A2 golden-vector checks: exact bytes pass, whitespace-altered bytes fail, key-order-altered bytes fail, semantic regeneration passes only after recanonicalization.
- Required proof tier before an external claim: `UNIT_PROVED` for the vector, then `INTEGRATION_PROVED` for a Node and Python writer of the same bytes. Not assigned now.
- Remaining Founder decision: item 12, OTLP or SIEM export, stays unauthorized.
- Revised status: `ARCHITECTURE_DEFINED`.

## 40. Producer classification of this revision

`OPTICS_FOUNDATION_ARCHITECTURE_REVISION_READY_FOR_RECOUNCIL`

This classification means the six blockers are specified in the documents named above and the four requirements are no longer `ARCHITECTURE_BLOCKED`. It was the producer’s handoff. The fresh council result is section 41. Gate 8 stays closed. A8 is not started. Draft PR #55 stays draft.

## 41. Fresh independent re-council

Independent council: Cursor cloud agent `bc-5bb719b6-65bf-522c-a9b9-f3a9a96ef08b`, model Grok 4.7, reviewing revised tip `7db944d17c7f74706f08970b4908e92d0bf2d589`. This agent did not produce A0–A6 and did not produce the revision. It did not reuse the first council’s judgments.

Council verdict: `PASS`

Force classification: `OPTICS_FOUNDATION_ARCHITECTURE_COUNCIL_PASSED`

Full seat table, blocker dispositions, and scope attestations: `10-INDEPENDENT-COUNCIL-REPORT.md`.

Gates 2–7 are accepted as architecture documents. Gate 1 stays accepted as the inventory document. Gate 8 stays closed. A8 is not started. Draft PR #55 stays draft. No evidence tier is assigned.
