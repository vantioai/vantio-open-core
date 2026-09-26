# Architecture decision pack

Audience: INTERNAL_RESTRICTED

Council verdict: `PENDING_SEPARATE_COUNCIL`

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

Writer values are `LOCAL_OBSERVATION`, `SIMULATED_DEMO`, `IMPORTED`, `TEST_FIXTURE`, `PRODUCT_HEALTH`, and `DERIVED_DIAGNOSTIC`. Missing origin on legacy files is the reader state `LEGACY_UNMARKED`, not a silent promotion.

## 7. Issue location

Machine enum: `OPTICS`, `CUSTOMER_APPLICATION`, `PROVIDER_INTERACTION`, `NETWORK`, `ENVIRONMENT`, `CONFIGURATION`, `COVERAGE`, `UNKNOWN`. Human wording is “issue location” or “failing interaction layer.”

## 8. Allowlisted fields

Persisted keys are the catalog in A1 section 4. Unknown keys are dropped before write. `schema_status` is `unstable-pre-1.0` on every new object.

## 9. Prohibited data

Bodies, prompts, completions, header maps, query strings, secrets, exception messages, environment dumps, telemetry anonymous ids, and secret-shaped strings inside allowlisted text are prohibited. Reject overlong paths instead of truncating them into storage.

## 10. Privacy invariants

Six release-blocking invariants are specified in A1 section 6. None is marked passing. Current privacy behavior is `PARTIAL` in the inventory.

## 11. Product telemetry

Keep the existing opt-in channel, default off, disable precedence unchanged, separate file and destination. Do not store the ping in the evidence store. Do not add fields.

## 12. Operational store

Recommendation: option C, embedded SQLite, WAL, application-owned schema, path `~/.vantio/optics/store.sqlite` under the evidence root. No file is created now. Founder ratification remains open.

## 13. Rejected store options

A (per-run JSON as the long-term index), B (JSONL plus sidecar as the index), D (embedded analytical engine), and E (daemon or network store) are rejected for the reasons in `03-OPERATIONAL-STORE-AND-PORTABLE-PROOF.md`. A and B remain relevant as legacy input and as export shapes.

## 14. Portable proof

Canonical proof is JSON plus a manifest and a SHA-256 of the canonical body. HTML and Markdown are renderings. The hash is not an attestation.

## 15. Prohibited proof language

Do not call the proof tamper-proof, WORM, notarized, certified, regulator-approved, or externally attested.

## 16. Retention

Default unbounded. No silent deletion. Future prune requires a dry-run manifest and a second explicit step. Commands are not created. Exported proofs are not rewritten by compaction.

## 17. Schema posture

No stable v1. Legacy JSON `schema_version` 2 is not reused as the operational `user_version`. `privacy_generation` starts at 1 when an implementation first writes the allowlist.

## 18. Corrupt-store rule

A corrupt or incompatible store is not replaced with an empty store. Bytes stay. Migration failure rolls back. Newer versions are read-only or refused.

## 19. Node and Python compatibility

One allowlist. Catalog provider identity, not substring guess. Zero-call attached runs get an envelope. Human sentences are derived diagnostics. Enforcement actions are not Optics rows. `VANTIO_HOME` must be honored by future readers. The current CLI is not patched.

## 20. Legacy JSON

Dual-read adapter (option L2) plus an explicit copy that keeps originals (option L3). No copy on first open. Demo host maps to `SIMULATED_DEMO`. Other files stay `LEGACY_UNMARKED`. Corrupt files are counted and skipped, not deleted.

## 21. Identity hierarchy

`run_id` is the attached execution. Today’s `trace_id` maps to `run_id` for legacy files. New `trace_id`, `span_id`, and `parent_span_id` are optional and validated. `session_id` is not inferred from time.

## 22. Correlation rules

Correlation is by writer-stamped ids. Timestamp proximity is not causality. Malformed context is dropped and counted. Child processes correlate only when they inherit instrumentation.

## 23. Deduplication

`event_id` is (`producer`, `run_id`, `sequence`). Same id does not inflate counts. No time-window heuristic while the window is `NOT_SET`.

## 24. Destination versus provider

Destination is normalized host, explicit port, scheme, and path. Provider is a catalog id plus confidence `CATALOG`, `REGIONAL_PATTERN`, `LOCAL_OLLAMA`, or `NONE`. Substring `guessProvider` is not the target.

## 25. Bounded query

Filters, limit 100 default and 500 maximum, UTC time bounds, opaque cursor, two sorts. No arbitrary SQL, no caller regular expressions, no body inspection. Saved views store the query.

## 26. Cardinality

Only the indexed allowlist is predicate-capable. Metric labels use `LOW` cardinality enums and `provider_id` only. Paths, run ids, and raw hosts are not metric labels.

## 27. Self-observability

Product-health names in A5 are the diagnostic set. They are excluded from customer activity. Recursion stops after one internal failure.

## 28. Fail-open

Optics failures do not fail, hang, or alter application output, and do not fabricate success. Exceptions are privacy drop and evidence-root confinement. Both still leave the application response alone. Enforcement is not an Optics exception.

## 29. Record lifecycle

`COMPLETE`, `PARTIAL`, `INTERRUPTED`, `ABANDONED`, `RECOVERED`. Current files do not carry these values. They are not backfilled by guesswork.

## 30. Nonfunctional budgets

All twelve `NFR-*` targets are `NOT_SET`. No example number from the roadmap is adopted.

## 31. Overload

Default `UNSAMPLED`. Queue-full and size-limit behavior drop explicitly and do not delete history to make room. Sampling is not introduced.

## 32. Clock

UTC instants. Monotonic duration when available. No negative durations. Order ties by `sequence` then `event_id`. Freshness value `CURRENT` is not emitted until a window exists, and that window is `NOT_SET`, so the honest value is `UNKNOWN`.

## 33. Threat model

Cases T1–T15 in `07-THREAT-MODEL.md`. Residual risk `UNSET`. Implementation `NOT_STARTED` except where the inventory already records a narrower current behavior.

## 34. Gates

Gates 1–7 are the documents in this directory. Gate 8 is a separate Founder implementation Force and is not open. See `09-IMPLEMENTATION-GATES.md`.

## 35. Unresolved Founder decisions

1. Ratify or replace operational-store option C.
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

## 36. Council and non-authorization

Council verdict: `PENDING_SEPARATE_COUNCIL`. Seat identities: `PENDING`. This pack does not authorize implementation, a release, a tag, a seal, a publish, a store file, a migration, a UI, a daemon, OTLP, alerting, or A8.

Producer terminal classification, which is not a Force verdict: `OPTICS_FOUNDATION_A6_READY_FOR_COUNCIL`.
