# Optics best-in-class roadmap

Internal planning capture only. This document does not authorize implementation, a release, a tag, a seal, or a publish. It makes no public claim. It assigns no dates and no timelines.

Out of scope for this capture: `packages/vantio-cli` (frozen at 0.3.24, LIVE_AND_CLIENT_PROVED) and the in-progress Python 3.1.0 diagnostic model work (PR #53).

**Planning sequence (no dates):** Foundational → Operational maturity → Product experience → Later strategic decisions. This order is planning language only. It does not promise delivery.

**Planning note (no dates):** After this addendum, stop expanding feature categories and turn the roadmap into a traceable architecture. Best-in-class sequence: Evidence and privacy → Storage integrity and migration → Correlation and query → Diagnostics and self-observability → Performance and overload proof → Local UI → Trends, alerts, interoperability → Independent customer validation. This order is planning language only. It does not promise delivery.

## Section 1 — Data architecture

**FOUNDATIONAL.** Highest priority. Sequence this section before other roadmap items.

1. Local storage backend migration from per-run JSON files to an embedded local store (e.g., SQLite), keeping JSON as the export/proof format only. Rationale: current design does not scale to real customer call volume; search/tail/diff currently require file scanning.
2. Retention and pruning policy:
   - `vantio config set retention.max-age <duration>`
   - `vantio config set retention.max-size <size>`
   - `vantio prune --dry-run` / `vantio prune`
   - Must default to unbounded retention unless the customer configures a limit (never silently delete evidence).

## Section 2 — Correlation and analysis

**FUTURE.**

3. Session/workflow grouping: allow multiple related calls to be correlated under one parent session/run identifier distinct from a single call's trace ID. Design the schema change required; do not implement.
4. Cross-run trend/comparison command (e.g., `vantio trends --since=<window>`) showing error-rate and duration drift over time using only already-stored structural metadata (never inspecting content).
5. Usage/cost metadata: investigate whether token/usage fields are exposed by supported providers in structural response metadata (not body content inspection). Requires an explicit separate product decision before any implementation — design memo on feasibility and privacy boundary only.

## Section 3 — Local visual surface

**FUTURE, STRATEGIC.**

6. A fully local, localhost-only, read-only web UI (`vantio ui`) rendering the same on-disk evidence: timeline, session grouping, filters. No account, no cloud, no external network. Highest-leverage "feels mature" item; own dedicated future release — not folded into CLI or Python patch releases.

## Section 4 — CLI ergonomics

**FUTURE, LOW RISK, SMALL SCOPE EACH.**

7. Confirm and document `NO_COLOR` / `--no-color` support across all commands.
8. Shell completion: `vantio completion bash|zsh|fish`.
9. `vantio legend` explaining every status glyph/color/label.
10. Pager-awareness for long tail/search (`$PAGER`, `--no-pager`).
11. `--quiet` mode distinct from `--json` (exit code only).

## Section 5 — Coverage transparency

**FUTURE.**

12. `vantio status --coverage`: list every currently supported HTTP client/provider on this runtime, and explicitly state what is not covered.

## Section 6 — Security hard gates

Schedule with real priority. Not implemented in this capture.

13. Metadata redaction test suite: fixtures with tokens in headers/query strings; assert persisted record NEVER contains them. Same severity class as prompt/completion non-storage; release-blocking when implemented.
14. Fail-open reliability gate: prove if Optics write/observation path throws or is killed mid-run, wrapped app output/behavior is byte-identical to running without Optics. Document target max per-call overhead (e.g. "<5ms p99") to validate once implemented.

## Section 7 — Compatibility and documentation

**FUTURE.**

15. Versioned config file (e.g. `vantio.config.json`) as alternative to flags/env for redaction, retention, telemetry defaults.
16. Documented flag/schema deprecation policy once JSON schema exits unstable-pre-1.0.
17. Generated single reference (e.g. `vantio help --all`) so `--help` and public docs cannot drift.
18. Runnable multi-agent example repository for prospective customers.

Sections 8–22 are roadmap and design only. None of these items is claimed to exist.

## Section 8 — Cardinality and resource governance

- Indexed-field allowlist
- Cardinality budgets
- Maximum local write rate and queue size
- Database-size limits
- Explicit overflow and dropped-record evidence
- Query-cost limits
- No silent evidence loss

## Section 9 — Database integrity and migrations

- Versioned transactional schema migrations
- Pre-migration backup
- Migration dry run
- Integrity checks
- Interrupted-migration recovery
- Newer-schema refusal or bounded read-only fallback
- No silent empty-database recreation
- Rollback compatibility tests

## Section 10 — Proof and operational-store separation

- SQLite is the searchable operational index
- JSON proof remains portable, hashable, scoped, and independently verifiable
- No claim of tamper-proofing or notarization without external proof
- Retention and compaction must not alter previously exported proof artifacts

## Section 11 — Trace, session, and process correlation

Design fields for:

- run_id
- trace_id
- span_id
- parent_span_id
- session_id
- process_id
- parent_process_id

Require concurrency, async, thread, child-process, retry, and context-conflict tests before implementation is considered complete.

## Section 12 — Sampling and overload

- Define unsampled default behavior
- Define queue-full and burst behavior
- If sampling is ever introduced, record policy and coverage explicitly
- Preserve error, slow-call, and proof-critical evidence under a future policy
- Never display sampled evidence as complete

## Section 13 — Clock and event ordering

- UTC canonical timestamps
- Monotonic duration measurement
- Customer-selected display timezone later
- Clock-rollback and DST tests
- No negative durations
- Stable tied-timestamp ordering
- No causal claims based only on timestamp proximity

## Section 14 — Optics self-observability

Diagnostic metrics:

- hooks installed
- events received
- events persisted
- events rejected/dropped
- write/query latency
- database size
- last successful write
- integrity state
- formatter failures
- migration state
- redaction failures
- schema version

Hard rule: Optics internal diagnostics must not recursively appear as customer AI activity.

## Section 15 — Bounded query contract

- One query model shared by CLI, local UI, and structured output
- Filters for provider, destination, status, fault domain, coverage, time, duration, process, session, trace, freshness, and HTTP status
- No arbitrary SQL exposure
- Saved views store queries, not duplicate evidence

## Section 16 — Alerting architecture decision

- Do not silently add a daemon
- Evaluate run-time, post-run, external-scheduler, and explicit-service options
- Define trigger evidence, window, freshness, deduplication, recovery, severity, and safe remediation
- Privacy invariant and evidence-write failures are highest-severity candidates

## Section 17 — Local indicators, not invented SLOs

Potential indicators:

- observed-call success
- latency percentiles
- provider-error rate
- evidence-write success
- evidence freshness
- partial/unknown/unavailable rate

Do not label any objective as an SLO until the customer configures one.

## Section 18 — Local UI truth contract

Require explicit UI states for:

- first run
- healthy
- honest idle
- not attached
- partial coverage
- stale evidence
- sampled evidence
- migration required
- database corruption
- privacy failure
- unsupported client
- mixed outcomes
- no results
- historical-only data

Every material view must show status, scope, time range, freshness, evidence source, version, limitation, and completeness.

Require keyboard navigation, contrast, reduced motion, color-independent status, responsive layouts, copyable local deep links, UTC-preserving timezone display, localhost-only binding, and read-only first release.

## Section 19 — Portability and provenance

Design future export/import/backup/restore behavior:

- imported evidence cannot masquerade as locally observed
- duplicate handling
- schema compatibility
- source-machine provenance
- no secrets
- no silent overwrite
- config inclusion separately controlled

## Section 20 — Evidence origin

Add design values:

- LOCAL_OBSERVATION
- SIMULATED_DEMO
- IMPORTED
- TEST_FIXTURE

Demo and fixture evidence must be excluded from operational trends by default.

## Section 21 — Release and upgrade posture

- No background auto-update
- Explicit version and integrity inspection
- Release-channel visibility
- Schema compatibility
- rollback compatibility
- security-update visibility
- registry check only when explicitly requested

## Section 22 — Customer annotations

- Customer may name or annotate runs
- Annotation is stored separately
- Annotation never mutates original observation evidence
- UI must visibly distinguish observed evidence from customer-entered context

## Section 23 — Complete observability requirement matrix

Roadmap and design only. None of these requirements is claimed to exist. None is marked implemented. Status for every item in this section is TARGET_DESIGN.

1. Signal contract: traces, metrics, logs/events, context/baggage, external profiles, and what Optics intentionally does not collect.
2. Semantic-convention conformance: upstream version, implemented fields, intentional omissions, Optics-specific extension namespace, schema identity, compatibility handling, and tests.
3. Context-propagation security: sensitive baggage prohibition, allowlists, size limits, imported-context provenance, malformed context, replay, collision, and trust classification.
4. Resource identity: service/application, environment, deployment version, runtime, process, host and container identity with privacy-safe provenance and conflict handling.
5. Observed dependency topology: current/historical edges, first/last seen, partial coverage, simulated-data exclusion, and no ownership inference from names alone.
6. Baselines: transparent deterministic baselines for call volume, destinations, latency, errors, retries, unknown outcomes, and coverage changes.
7. Deduplication and idempotency: stable event identity, duplicate markers, repeat-safe import, multi-hook detection, and no duplicate inflation of metrics.
8. Instrumentation conflicts: coexistence with OpenTelemetry/APM/provider SDK instrumentation, duplicate hooks, wrapper order, and multiple Optics copies.
9. Data-quality dimensions: coverage, freshness, completeness, integrity, correlation, and privacy checks; no misleading aggregate percentage.
10. Golden signals: call rate, error rate, duration, in-progress work, retries, queue depth, dropped records, write latency, unknown outcomes, and coverage gaps.
11. Cardinality-safe metric model: no trace/run/session IDs or arbitrary URLs in metric labels; high-cardinality identifiers remain in events/traces.
12. Exemplars: trend/chart drill-down to representative local runs and traces.
13. Sampling correction: exact versus estimated counts, sampling probability, mixed-policy periods, proof disclosure, and policy-change markers.
14. Performance budgets: startup, initialization, per-call overhead, memory, write latency, queue, query, UI, export, and shutdown flush, measured by percentiles.
15. Graceful degradation: application continues under queue saturation or storage failure; incomplete evidence is disclosed; no recursive drop-notice storms.
16. Crash consistency: normal exit, signals, power loss, sleep/resume, interpreter shutdown, interrupted streams, and queued writes; COMPLETE/PARTIAL/INTERRUPTED/ABANDONED/RECOVERED states.
17. Local security: filesystem permissions, Windows ACLs, Unix modes, multi-user workstation boundaries, symlink defense, imported-evidence quarantine, and optional at-rest-encryption feasibility.
18. Local UI security: loopback-only binding, no third-party assets/analytics, CSP, origin restrictions, CSRF defense, output escaping, no query-string secrets, no mutation endpoints in v1, explicit shutdown, and no persistent daemon.
19. Accessibility: screen readers, keyboard flow, focus, non-color status, contrast, reduced motion, text scaling, narrow viewports, ASCII fallback, and terminal width.
20. Destination normalization: case, ports, IPv4/IPv6, redirects, proxies, regional hosts, and query-string exclusion by default.
21. Provider identity confidence: provenance of provider/model identity and no unsupported inference.
22. Privacy corpus: allowlisting before persistence, encoded/nested secrets, URLs, credentials, PII, financial/health indicators, Unicode bypass testing, and release-blocking invariant failures.
23. Local data operations: selective deletion, backup implications, import provenance, retention proof, and no unsupported compliance claims.
24. Automation contract: read-only local API/CLI schema, pagination, sorting, time bounds, error objects, cancellation, query limits, schema negotiation, and localhost-only default.
25. Export formats: JSON/JSONL, simple tabular export, future OTLP/SIEM feasibility, integrity manifest, filters/time range, schema version, completeness, sampling, and redaction metadata.
26. Incident workflow: detect, scope, investigate, explain, export, remediate, and verify recovery.
27. Alert lifecycle: active, acknowledged, silenced, resolved, deduplication, maintenance windows, evidence retention, recovery notices, and honest idle handling.
28. SLI/SLO separation: Optics-product-health SLIs separate from observed-workload provider SLIs; no SLO claim until customer target and window are configured.
29. Cross-platform matrix: Windows/WSL, Linux, macOS if supported, containers, CI, proxies, TLS interception, IPv6, offline, locale, and restrictive filesystem cases.
30. Upgrade and rollback: old/new record compatibility, interrupted migration, safe rollback, mixed CLI/Python versions, future schema refusal, and export/import testing.
31. Product telemetry separation: customer evidence versus optional Vantio telemetry, explicit destinations, fields, triggers, frequency, last result, and disable precedence.
32. Documentation operability: executable quickstarts, fixture-generated output, versioned docs, flag parity, known issues, migration notes, and remediation anchors.
33. Support/security operations: vulnerability disclosure, supported-version policy, safe issue templates, support bundle, severity model, release advisories, integrity checks, and rollback guidance.
34. Independent customer acceptance: persona matrix and adversity scenarios covering errors, coverage gaps, concurrency, migration, privacy, rollback, uninstall, and portability.

## Requirement traceability template

Applies to every roadmap item in Sections 1–23. No item in this document is marked implemented. Every item remains TARGET_DESIGN.

- Requirement ID
- Customer problem
- Scope
- Evidence required
- Test required
- Privacy classification
- Failure behavior
- UI state
- CLI state
- Structured state
- Documentation
- Release gate
- Current evidence tier
- Required closing tier
- Independent verifier
- Stranger-host
- Customer-validation
- Status: TARGET_DESIGN / INTERNAL_PROOF / PROVED_EXTERNAL / CUSTOMER_VALIDATED

Counted from numbered items in this document: Sections 1–7 contain 18 numbered requirements, and Section 23 contains 34 numbered requirements. Each of those 52 numbered requirements has status TARGET_DESIGN. Sections 8–22 are unnumbered design bullets and remain TARGET_DESIGN; this document does not give them a separate numeric total.

Current evidence tier, required closing tier, independent verifier, stranger-host, and customer-validation are unset for every item. No item is assigned UNIT_PROVED, INTEGRATION_PROVED, STRANGER_HOST_PROVED, PROVED_EXTERNAL, or CUSTOMER_VALIDATED. Requirement status and evidence tier are different fields. INTERNAL_PROOF is a requirement-status value, not an evidence tier, and it must not be displayed as CUSTOMER_VALIDATED.

## Governance — separation of layers

These governance sections are design controls. They do not delete Sections 1–23. They do not mark any item implemented or complete. They do not reopen CLI 0.3.24. They do not add Python 3.1.0 implementation scope.

- Requirement: Sections 1–23. Status of every requirement remains TARGET_DESIGN.
- Architecture: the dependency graph, budget categories, and threat-model linkage below. Numeric budget targets are NOT_SET.
- Implementation: not authorized by this document.
- Proof: the acceptance evidence hierarchy below. No evidence tier is assigned.
- Release: release-gate fields are unset. This document does not authorize a release.
- Customer validation: a defined evidence tier that no item has reached.

## Governance — requirement dependency graph

Dependency relationships only. No dates. No delivery promise. Every workstream remains TARGET_DESIGN.

Local UI (Section 3 and Section 18) depends on all of the following before it can be treated as a coherent workstream: operational storage, schema migration, bounded query contract, evidence-origin model, privacy policy, local UI security model, and freshness/completeness semantics.

### Operational storage

Section 1, item 1.

- Prerequisites: none inside this roadmap. This workstream is foundational.
- Downstream dependents: retention and pruning, schema migration, proof separation, bounded query, correlation, local UI, trends, export, and self-observability.
- Incompatible parallel work: keeping per-run JSON file scanning as the long-term search, tail, and diff store. JSON remains the export and proof format only.
- Migration dependency: the store change is the migration this graph sequences before UI and query.
- Privacy dependency: retention defaults stay unbounded unless the customer sets a limit.
- Schema dependency: versioned schema before readers depend on the store.
- UI dependency: Local UI reads this store and does not replace it.
- Validation dependency: integrity checks and crash-consistency states.

### Retention and pruning

Section 1, item 2.

- Prerequisites: operational storage; unbounded retention unless the customer configures a limit.
- Downstream dependents: database-size budget, local data operations, proof separation.
- Incompatible parallel work: silent deletion of evidence; compaction that changes a previously exported proof artifact.
- Migration dependency: prune behavior has to follow the active schema.
- Privacy dependency: never silently delete evidence.
- Schema dependency: retention limits are configuration, not a rewrite of exported proof.
- UI dependency: a prune result has to be visible as an explicit evidence state.
- Validation dependency: `vantio prune --dry-run` before a destructive prune.

### Schema migration and database integrity

Section 9 and Section 23, item 30.

- Prerequisites: operational storage.
- Downstream dependents: bounded query, local UI, upgrade and rollback, export and import.
- Incompatible parallel work: silent empty-database recreation; a UI built on an unversioned store; rollback onto a privacy-weaker schema.
- Migration dependency: versioned transactional migrations, pre-migration backup, dry run, interrupted-migration recovery, and newer-schema refusal or bounded read-only fallback.
- Privacy dependency: rollback compatibility includes the privacy invariants, not only row shape.
- Schema dependency: mixed CLI and Python readers refuse or stay read-only when the schema is newer.
- UI dependency: explicit “migration required” and “database corruption” states.
- Validation dependency: rollback compatibility tests and interrupted-migration tests.

### Proof and operational-store separation

Section 10.

- Prerequisites: operational storage.
- Downstream dependents: export, retention, portability.
- Incompatible parallel work: treating the operational index as notarized or tamper-proof without external proof; retention or compaction that alters previously exported proof.
- Migration dependency: proof artifacts stay stable across store migrations.
- Privacy dependency: proof export carries redaction metadata and does not add secrets.
- Schema dependency: proof schema identity is independent of the operational index.
- UI dependency: the UI shows evidence source and does not present the index as the proof artifact.
- Validation dependency: exported proof remains hashable and independently verifiable after retention.

### Privacy policy

Section 6, items 13 and 14, and Section 23, items 22 and 31.

- Prerequisites: none. The redaction invariant is release-blocking when the work is implemented. This document does not implement it.
- Downstream dependents: storage, query, local UI, export, import, product-telemetry separation, and annotations.
- Incompatible parallel work: persisting tokens from headers or query strings; inspecting body content for usage or cost; mixing optional Vantio telemetry with customer evidence.
- Migration dependency: rollback and a newer schema cannot weaken an existing privacy invariant.
- Privacy dependency: allowlisting before persistence.
- Schema dependency: persisted records exclude non-allowlisted secrets.
- UI dependency: Local UI depends on this policy; privacy failure is an explicit UI state.
- Validation dependency: metadata redaction fixtures and the privacy corpus, including encoded and nested secrets. Usage and cost metadata still requires a separate product decision before any implementation.

### Evidence-origin model

Section 20.

- Prerequisites: a schema field for origin.
- Downstream dependents: trends, UI truth contract, import, baselines, and customer-validation evidence.
- Incompatible parallel work: counting SIMULATED_DEMO or TEST_FIXTURE in operational trends by default; letting IMPORTED masquerade as LOCAL_OBSERVATION.
- Migration dependency: origin survives schema migration and import.
- Privacy dependency: import carries no secrets.
- Schema dependency: design values are LOCAL_OBSERVATION, SIMULATED_DEMO, IMPORTED, and TEST_FIXTURE.
- UI dependency: Local UI depends on this model and shows evidence source.
- Validation dependency: trend queries exclude demo and fixture evidence. This document sets no exception.

### Correlation schema

Section 2, item 3, and Section 11.

- Prerequisites: operational storage schema.
- Downstream dependents: session grouping in the local UI, trends, and exemplars.
- Incompatible parallel work: using one call’s trace ID as the parent session or run identifier.
- Migration dependency: adding session and process fields is a schema change and stays design-only here.
- Privacy dependency: correlation IDs are not metric labels.
- Schema dependency: run_id, trace_id, span_id, parent_span_id, session_id, process_id, and parent_process_id.
- UI dependency: session grouping waits on this schema.
- Validation dependency: concurrency, async, thread, child-process, retry, and context-conflict tests are required before implementation is considered complete. Those tests are not recorded here.

### Bounded query contract

Section 15 and Section 23, item 24.

- Prerequisites: operational storage, evidence-origin model, and freshness/completeness semantics.
- Downstream dependents: CLI, local UI, structured output, saved views, and the automation contract.
- Incompatible parallel work: arbitrary SQL exposure; saved views that duplicate evidence.
- Migration dependency: queries target the versioned store.
- Privacy dependency: filters do not require content inspection.
- Schema dependency: one query model for CLI, local UI, and structured output.
- UI dependency: Local UI depends on this contract.
- Validation dependency: pagination, sorting, time bounds, cancellation, and query limits.

### Freshness and completeness semantics

Sections 12, 13, 17, and 18, and Section 23, items 9 and 13.

- Prerequisites: clock and ordering rules, sampling-policy recording, and evidence origin.
- Downstream dependents: UI states, trends, alerts, and baselines.
- Incompatible parallel work: displaying sampled evidence as complete; causal claims from timestamp proximity alone; labeling an objective as an SLO before the customer configures a target and window.
- Migration dependency: ordering rules apply to records read after a migration.
- Privacy dependency: completeness checks do not read body content.
- Schema dependency: sampling policy, coverage, and clock fields are explicit.
- UI dependency: Local UI depends on these semantics. Stale, sampled, partial, unknown, and unavailable stay explicit states.
- Validation dependency: clock-rollback, DST, negative-duration, and tied-timestamp tests.

### Local UI security model

Section 23, item 18.

- Prerequisites: privacy policy.
- Downstream dependents: Local UI.
- Incompatible parallel work: non-loopback binding, third-party assets or analytics, mutation endpoints in the first release, a persistent daemon, or secrets in query strings.
- Migration dependency: the UI refuses or discloses a store that requires migration.
- Privacy dependency: output escaping and no query-string secrets.
- Schema dependency: the UI reads the bounded query contract and does not invent a second schema.
- UI dependency: Local UI depends on this model.
- Validation dependency: binding, origin, CSRF, escaping, and shutdown checks. Those checks are not recorded here.

### Local UI

Section 3, Section 18, and Section 23, item 19.

- Prerequisites: operational storage, schema migration, bounded query contract, evidence-origin model, privacy policy, local UI security model, and freshness/completeness semantics.
- Downstream dependents: exemplar drill-down, incident-workflow views, and display of customer annotations.
- Incompatible parallel work: folding this UI into a CLI patch release or a Python patch release; shipping the UI before the prerequisites above; a read-write first release.
- Migration dependency: schema migration, listed above.
- Privacy dependency: privacy policy, listed above.
- Schema dependency: bounded query contract and evidence origin, listed above.
- UI dependency: truth-contract states, accessibility, localhost-only binding, and read-only first release.
- Validation dependency: every material view shows status, scope, time range, freshness, evidence source, version, limitation, and completeness. A healthy screen is not proof.

### Cardinality, queue, and overload

Sections 8 and 12, and Section 23, items 11 and 15.

- Prerequisites: operational storage.
- Downstream dependents: the metric model, self-observability, graceful degradation, and the budget ledger.
- Incompatible parallel work: metric labels that contain trace, run, or session IDs, or arbitrary URLs; silent evidence loss.
- Migration dependency: cardinality limits apply to the versioned store.
- Privacy dependency: high-cardinality identifiers stay in events and traces, not in metric labels.
- Schema dependency: indexed-field allowlist and overflow records.
- UI dependency: sampled or partial evidence stays labeled.
- Validation dependency: queue-full, burst, and dropped-record evidence.

### Self-observability

Section 14.

- Prerequisites: operational storage and privacy policy.
- Downstream dependents: diagnostics for write latency, database size, integrity, migration, redaction, and schema version.
- Incompatible parallel work: Optics internal diagnostics appearing as customer AI activity.
- Migration dependency: migration state is a diagnostic, not a customer trace.
- Privacy dependency: redaction failures are diagnostics.
- Schema dependency: schema version is reported separately from customer spans.
- UI dependency: diagnostics must not be rendered as customer activity.
- Validation dependency: a recursion check that internal diagnostics are excluded from customer activity.

### Alerting architecture

Section 16 and Section 23, item 27.

- Prerequisites: bounded query, freshness and completeness, evidence origin, and privacy policy.
- Downstream dependents: incident workflow.
- Incompatible parallel work: silently adding a daemon.
- Migration dependency: alerts read the versioned store and honor freshness.
- Privacy dependency: privacy-invariant failure is a highest-severity candidate.
- Schema dependency: alert state is not a second copy of evidence.
- UI dependency: any future surface uses the local UI truth contract. No surface is selected here.
- Validation dependency: the architecture decision among run-time, post-run, external-scheduler, and explicit-service options. The decision is not made in this document.

### Trends and baselines

Section 2, item 4, Section 17, and Section 23, items 6 and 12.

- Prerequisites: operational storage, structural metadata only, evidence origin, and sampling disclosure.
- Downstream dependents: exemplars.
- Incompatible parallel work: inspecting body content; including demo or fixture evidence in operational trends by default.
- Migration dependency: baselines read records that survived migration without treating import as local observation.
- Privacy dependency: structural metadata only.
- Schema dependency: origin, sampling, and coverage fields.
- UI dependency: charts drill down to representative local runs and traces.
- Validation dependency: exact versus estimated counts stay distinct.

### Usage and cost metadata

Section 2, item 5.

- Prerequisites: an explicit separate product decision, and structural response metadata only.
- Downstream dependents: none until that decision exists.
- Incompatible parallel work: implementing this item from this roadmap; inspecting body content.
- Migration dependency: none until a decision exists.
- Privacy dependency: the privacy boundary is part of the design memo, which is not written here.
- Schema dependency: unset until a decision exists.
- UI dependency: none until a decision exists.
- Validation dependency: feasibility and privacy memo only.

### Portability, export, and import

Sections 10 and 19, and Section 23, item 25.

- Prerequisites: proof separation, evidence origin, privacy policy, and schema version.
- Downstream dependents: portability scenarios in independent customer acceptance.
- Incompatible parallel work: imported evidence masquerading as locally observed; silent overwrite; secrets in an export.
- Migration dependency: schema compatibility on import.
- Privacy dependency: no secrets; config inclusion is separately controlled.
- Schema dependency: integrity manifest, schema version, completeness, sampling, and redaction metadata.
- UI dependency: imported evidence shows its origin.
- Validation dependency: duplicate handling and quarantine of imported evidence.

### Customer annotations

Section 22.

- Prerequisites: evidence origin, operational storage, and the local UI truth contract.
- Downstream dependents: a visible distinction between observed evidence and customer-entered context.
- Incompatible parallel work: an annotation that mutates the original observation.
- Migration dependency: annotations live in separate storage and survive store migration without rewriting proof.
- Privacy dependency: annotation text is customer-entered context, not an observation.
- Schema dependency: annotation records are separate from observation records.
- UI dependency: the distinction is visible.
- Validation dependency: a test that annotation edits leave the original observation unchanged.

### CLI ergonomics and coverage transparency

Sections 4 and 5.

- Prerequisites: none that authorize new product behavior in this document.
- Downstream dependents: the generated help reference in Section 7, item 17.
- Incompatible parallel work: defining `--quiet` as a synonym of `--json`; treating CLI ergonomics as a substitute for the Local UI workstream.
- Migration dependency: none.
- Privacy dependency: coverage output states what is not covered and does not dump secrets.
- Schema dependency: none beyond the existing evidence the commands would read.
- UI dependency: terminal behavior only. This is not the local web UI.
- Validation dependency: NO_COLOR, completion, legend, pager, quiet mode, and coverage listing remain design items.

### Release, upgrade, and customer validation

Sections 7 and 21, and Section 23, items 32, 33, and 34.

- Prerequisites: migration, privacy, schema compatibility, and the evidence hierarchy.
- Downstream dependents: none inside the product. Acceptance closes only at the tier the hierarchy requires.
- Incompatible parallel work: background auto-update; treating this document as customer validation or as a release.
- Migration dependency: old and new record compatibility, interrupted migration, and safe rollback.
- Privacy dependency: security-update visibility does not weaken redaction.
- Schema dependency: future schema refusal and export/import testing.
- UI dependency: none that bypasses the Local UI prerequisites.
- Validation dependency: persona and adversity scenarios. They are requirements, not recorded results.

## Governance — nonfunctional budget ledger

Reusable fields for every budget: Budget ID, Category, User impact, Current target, Target status (NOT_SET | TARGET_DESIGN | TESTED_INTERNAL | PROVED_EXTERNAL | CUSTOMER_VALIDATED), Measurement method, Workload profile, Percentile/aggregation, Privacy impact, Failure behavior, Release gate, Evidence reference.

Requirement status and budget-target status are different fields. Every requirement remains TARGET_DESIGN. Every numeric current target below is NOT_SET. Every budget target status below is NOT_SET. An example figure named elsewhere in this document is not adopted as a current target.

No measurement method, workload profile, percentile, release gate, or evidence reference is set. Privacy impact and failure behavior below point at existing design rules and do not add a numeric limit.

### NFR-STARTUP

- Budget ID: NFR-STARTUP
- Category: startup
- User impact: time added before the wrapped application is usable
- Current target: NOT_SET
- Target status: NOT_SET
- Measurement method: NOT_SET
- Workload profile: NOT_SET
- Percentile/aggregation: NOT_SET
- Privacy impact: startup must not persist secrets while initializing
- Failure behavior: application startup continues if Optics observation cannot start; the gap is disclosed
- Release gate: NOT_SET
- Evidence reference: none

### NFR-INTERCEPTOR-INIT

- Budget ID: NFR-INTERCEPTOR-INIT
- Category: interceptor init
- User impact: time to install observation hooks
- Current target: NOT_SET
- Target status: NOT_SET
- Measurement method: NOT_SET
- Workload profile: NOT_SET
- Percentile/aggregation: NOT_SET
- Privacy impact: hook installation must not record customer content
- Failure behavior: a failed hook install is disclosed and does not change application output
- Release gate: NOT_SET
- Evidence reference: none

### NFR-PER-CALL-OVERHEAD

- Budget ID: NFR-PER-CALL-OVERHEAD
- Category: per-call overhead
- User impact: time added on each observed call
- Current target: NOT_SET
- Target status: NOT_SET
- Measurement method: NOT_SET
- Workload profile: NOT_SET
- Percentile/aggregation: NOT_SET
- Privacy impact: overhead measurement must not read body content
- Failure behavior: if the observation path throws or is killed, wrapped application output stays byte-identical to a run without Optics
- Release gate: NOT_SET
- Evidence reference: none

### NFR-MEMORY

- Budget ID: NFR-MEMORY
- Category: memory
- User impact: resident memory added by observation and the local store
- Current target: NOT_SET
- Target status: NOT_SET
- Measurement method: NOT_SET
- Workload profile: NOT_SET
- Percentile/aggregation: NOT_SET
- Privacy impact: memory holding secrets is not flushed into evidence
- Failure behavior: memory pressure follows the queue and degradation rules; evidence loss is explicit
- Release gate: NOT_SET
- Evidence reference: none

### NFR-WRITE-LATENCY

- Budget ID: NFR-WRITE-LATENCY
- Category: write latency
- User impact: delay to persist one observation
- Current target: NOT_SET
- Target status: NOT_SET
- Measurement method: NOT_SET
- Workload profile: NOT_SET
- Percentile/aggregation: NOT_SET
- Privacy impact: the write path allowlists before persistence
- Failure behavior: a failed write is disclosed; the application continues
- Release gate: NOT_SET
- Evidence reference: none

### NFR-QUEUE-CAPACITY

- Budget ID: NFR-QUEUE-CAPACITY
- Category: queue capacity
- User impact: how many observations can wait during a burst
- Current target: NOT_SET
- Target status: NOT_SET
- Measurement method: NOT_SET
- Workload profile: NOT_SET
- Percentile/aggregation: NOT_SET
- Privacy impact: queued records obey the same allowlist as persisted records
- Failure behavior: queue-full and burst behavior must be defined; drops are explicit
- Release gate: NOT_SET
- Evidence reference: none

### NFR-DATABASE-SIZE

- Budget ID: NFR-DATABASE-SIZE
- Category: database size
- User impact: disk used by the operational store
- Current target: NOT_SET
- Target status: NOT_SET
- Measurement method: NOT_SET
- Workload profile: NOT_SET
- Percentile/aggregation: NOT_SET
- Privacy impact: size limits must not silently delete evidence; retention stays unbounded unless the customer sets a limit
- Failure behavior: reaching a future configured limit produces explicit evidence, not a silent wipe
- Release gate: NOT_SET
- Evidence reference: none

### NFR-QUERY-LATENCY

- Budget ID: NFR-QUERY-LATENCY
- Category: query latency
- User impact: time to answer a bounded query
- Current target: NOT_SET
- Target status: NOT_SET
- Measurement method: NOT_SET
- Workload profile: NOT_SET
- Percentile/aggregation: NOT_SET
- Privacy impact: queries use structural fields and do not inspect body content
- Failure behavior: query-cost limits stop a runaway query; the failure is explicit
- Release gate: NOT_SET
- Evidence reference: none

### NFR-UI-QUERY-RENDER-LATENCY

- Budget ID: NFR-UI-QUERY-RENDER-LATENCY
- Category: UI query/render latency
- User impact: time for the local UI to show a bounded result
- Current target: NOT_SET
- Target status: NOT_SET
- Measurement method: NOT_SET
- Workload profile: NOT_SET
- Percentile/aggregation: NOT_SET
- Privacy impact: render uses the privacy policy and the evidence-origin model
- Failure behavior: a slow or failed query stays an explicit UI state and is not shown as a healthy current view
- Release gate: NOT_SET
- Evidence reference: none

### NFR-EXPORT-TIME

- Budget ID: NFR-EXPORT-TIME
- Category: export time
- User impact: time to write a proof or tabular export
- Current target: NOT_SET
- Target status: NOT_SET
- Measurement method: NOT_SET
- Workload profile: NOT_SET
- Percentile/aggregation: NOT_SET
- Privacy impact: export includes redaction metadata and omits secrets
- Failure behavior: a partial export is labeled incomplete and does not overwrite an existing proof silently
- Release gate: NOT_SET
- Evidence reference: none

### NFR-SHUTDOWN-FLUSH

- Budget ID: NFR-SHUTDOWN-FLUSH
- Category: shutdown flush
- User impact: whether queued writes reach disk before exit
- Current target: NOT_SET
- Target status: NOT_SET
- Measurement method: NOT_SET
- Workload profile: NOT_SET
- Percentile/aggregation: NOT_SET
- Privacy impact: flush persists only allowlisted fields
- Failure behavior: crash-consistency states COMPLETE, PARTIAL, INTERRUPTED, ABANDONED, and RECOVERED stay explicit
- Release gate: NOT_SET
- Evidence reference: none

### NFR-DROPPED-RECORD

- Budget ID: NFR-DROPPED-RECORD
- Category: dropped-record behavior
- User impact: whether a lost observation is visible
- Current target: NOT_SET
- Target status: NOT_SET
- Measurement method: NOT_SET
- Workload profile: NOT_SET
- Percentile/aggregation: NOT_SET
- Privacy impact: a drop notice must not contain the dropped secret or body
- Failure behavior: overflow and dropped records are explicit; no silent evidence loss; no recursive drop-notice storm
- Release gate: NOT_SET
- Evidence reference: none

## Governance — threat-model linkage

Design linkage only. Each case names the required control objective. None of these controls is claimed to exist. No case is closed. Status of every case is TARGET_DESIGN. Residual risk is unset.

### Compromised observed app

- Threat actor: code running inside the observed application, including a dependency
- Asset: local evidence store and proof export
- Trust boundary: observed application process versus Optics persistence
- Abuse path: the application submits customer content, credentials, or forged records for persistence
- Prevention: allowlisting before persistence; observation evidence is structural metadata; annotations and imports cannot rewrite a local observation
- Detection: redaction-failure and rejected-event diagnostics, kept out of customer AI activity
- Failure behavior: the application continues; rejected or incomplete evidence is disclosed
- Recovery: refuse the bad record; do not recreate an empty database silently
- Residual risk: unset
- Required test: fixtures with disallowed content assert the persisted record excludes it
- Status: TARGET_DESIGN

### Malicious local user

- Threat actor: another user on the same workstation
- Asset: evidence files, database, exports, and configuration
- Trust boundary: user account versus other local accounts
- Abuse path: a local user reads or replaces another user’s evidence or config
- Prevention: filesystem permissions, Windows ACLs, Unix modes, and multi-user workstation boundaries
- Detection: integrity checks and permission failures surfaced as integrity state
- Failure behavior: access outside the owner boundary fails closed for the store and does not widen the file mode
- Recovery: restore from a pre-migration backup or an export the owner still trusts; do not silently create a replacement database
- Residual risk: unset
- Required test: two-user permission fixtures on the documented filesystem cases
- Status: TARGET_DESIGN

### Poisoned imported evidence

- Threat actor: the author of an imported bundle
- Asset: operational trends, UI views, and proof exports
- Trust boundary: imported bytes versus LOCAL_OBSERVATION
- Abuse path: imported records are presented as locally observed customer activity
- Prevention: IMPORTED origin, quarantine, duplicate handling, and no silent overwrite
- Detection: evidence source and origin shown on every material view
- Failure behavior: import that fails provenance or schema checks is refused or quarantined
- Recovery: leave prior local observations unchanged
- Residual risk: unset
- Required test: import fixtures that must not count as local observation or as operational trends
- Status: TARGET_DESIGN

### Malformed trace context

- Threat actor: a caller or upstream process supplying trace context
- Asset: correlation fields and any propagated baggage
- Trust boundary: incoming context versus trusted local correlation
- Abuse path: malformed, replayed, colliding, or sensitive baggage is stored or propagated
- Prevention: sensitive-baggage prohibition, allowlists, size limits, and trust classification
- Detection: context-conflict and rejected-context diagnostics
- Failure behavior: malformed context is not treated as a trusted parent span
- Recovery: record the conflict without adopting the bad context
- Residual risk: unset
- Required test: malformed, replay, collision, and oversize-context fixtures
- Status: TARGET_DESIGN

### Oversized telemetry

- Threat actor: a noisy or hostile observed workload
- Asset: queue, store, and application latency
- Trust boundary: observation path versus application progress
- Abuse path: volume exhausts queue, disk, or query budget
- Prevention: cardinality budgets, queue bounds, database-size policy, and query-cost limits, with numeric targets still NOT_SET
- Detection: dropped-record, queue, and database-size diagnostics
- Failure behavior: explicit overflow; application continues; no silent evidence loss; no drop-notice storm
- Recovery: customer retention policy only when the customer has configured a limit
- Residual risk: unset
- Required test: burst and queue-full fixtures that assert explicit drop evidence
- Status: TARGET_DESIGN

### Path traversal and symlink

- Threat actor: a local user or a crafted import path
- Asset: files outside the intended evidence directory
- Trust boundary: configured evidence path versus the rest of the filesystem
- Abuse path: a path or symlink redirects reads or writes outside the evidence directory
- Prevention: symlink defense and path confinement to the configured evidence location
- Detection: refused path attempts in integrity state
- Failure behavior: the operation stops and does not follow the link out of the evidence root
- Recovery: no partial write outside the evidence root
- Residual risk: unset
- Required test: symlink and parent-directory fixtures that must fail closed
- Status: TARGET_DESIGN

### Local UI injection

- Threat actor: evidence or annotation text rendered by the local UI
- Asset: the local browser session
- Trust boundary: stored text versus the UI document
- Abuse path: stored text is interpreted as active UI content
- Prevention: output escaping, CSP, and no third-party assets
- Detection: the first UI release has no mutation endpoint that could persist an injected action
- Failure behavior: untrusted text renders as text
- Recovery: restart the local UI process; the store is unchanged because the first release is read-only
- Residual risk: unset
- Required test: render fixtures for evidence and annotation text
- Status: TARGET_DESIGN

### Unauthorized local UI access

- Threat actor: a different local user or a non-loopback client
- Asset: the read-only evidence view
- Trust boundary: loopback interface versus other interfaces and users
- Abuse path: a client off-machine, or another local user, opens the UI
- Prevention: loopback-only binding, origin restrictions, and explicit shutdown
- Detection: bind and origin failures are visible; no analytics channel exists to hide them
- Failure behavior: non-loopback and cross-origin requests are refused
- Recovery: shut the UI down; it is not a persistent daemon
- Residual risk: unset
- Required test: bind-address and origin fixtures
- Status: TARGET_DESIGN

### Query denial of service

- Threat actor: a local query client
- Asset: UI and CLI responsiveness and store availability
- Trust boundary: bounded query contract versus arbitrary query power
- Abuse path: an expensive query or unrestricted scan stalls the local store
- Prevention: no arbitrary SQL; query-cost limits; pagination and time bounds
- Detection: query latency and rejected-query diagnostics
- Failure behavior: the query is cancelled or refused; the application under observation keeps running
- Recovery: another bounded query still works; saved views store queries, not copied evidence
- Residual risk: unset
- Required test: over-broad query fixtures that must hit the cost limit
- Status: TARGET_DESIGN

### Database corruption

- Threat actor: crash, disk fault, or a partial write
- Asset: operational store integrity
- Trust boundary: durable store versus in-flight queue
- Abuse path: a torn write or interrupted migration is opened as a healthy database
- Prevention: transactional migrations, integrity checks, and crash-consistency states
- Detection: integrity state and the “database corruption” UI state
- Failure behavior: refuse silent empty-database recreation; newer or corrupt schemas stay refused or bounded read-only
- Recovery: pre-migration backup and interrupted-migration recovery
- Residual risk: unset
- Required test: interrupted migration and torn-write fixtures
- Status: TARGET_DESIGN

### Instrumentation recursion

- Threat actor: Optics observing its own diagnostic writes
- Asset: customer activity views and metric totals
- Trust boundary: customer AI calls versus Optics-internal diagnostics
- Abuse path: hooks, writes, or formatter failures are stored as customer calls and inflate metrics
- Prevention: internal diagnostics are excluded from customer activity and from metric labels
- Detection: a recursion counter that must stay out of the customer event stream
- Failure behavior: diagnostic failure does not create another customer event
- Recovery: drop the recursive diagnostic, record one explicit internal failure, and stop
- Residual risk: unset
- Required test: a self-observation fixture that asserts zero customer events from internal diagnostics
- Status: TARGET_DESIGN

### Metadata secret placement

- Threat actor: an application or provider that puts tokens in headers, query strings, or nested fields
- Asset: persisted records, exports, and UI
- Trust boundary: allowlisted structural metadata versus secrets and content
- Abuse path: a secret in a header, query string, URL, or encoded field is stored
- Prevention: allowlisting before persistence; query strings excluded from destination normalization by default
- Detection: redaction-failure diagnostic; release-blocking invariant when this control is implemented
- Failure behavior: the persisted record does not contain the secret; the application still returns its own output
- Recovery: the bad field is omitted, not masked in place with a reversible copy
- Residual risk: unset
- Required test: the metadata redaction suite and the privacy corpus, including Unicode and nested encodings
- Status: TARGET_DESIGN

### Duplicate instrumentation

- Threat actor: stacked Optics copies or co-installed OpenTelemetry, APM, or provider SDK hooks
- Asset: event identity and metric totals
- Trust boundary: one observation pipeline versus other hooks in the same process
- Abuse path: one call is stored more than once and inflates counts
- Prevention: stable event identity, duplicate markers, and no duplicate inflation of metrics
- Detection: multi-hook detection
- Failure behavior: duplicates are marked and excluded from inflated totals
- Recovery: repeat-safe import does not create a second logical event
- Residual risk: unset
- Required test: wrapper-order and multiple-copy fixtures
- Status: TARGET_DESIGN

### Tampered annotation

- Threat actor: the local customer, or another local user editing annotation storage
- Asset: original observation evidence
- Trust boundary: annotation store versus observation store
- Abuse path: an annotation edit changes the original observation or is shown as an observation
- Prevention: annotations are stored separately and never mutate observation evidence
- Detection: the UI distinguishes customer-entered context from observed evidence
- Failure behavior: a corrupt annotation is dropped from view and the observation remains
- Recovery: restore or delete the annotation without rewriting proof
- Residual risk: unset
- Required test: an annotation edit that must leave the observation bytes unchanged
- Status: TARGET_DESIGN

### Rollback to a privacy-weaker schema

- Threat actor: an operator rolling back software or schema
- Asset: privacy invariants already enforced on stored records
- Trust boundary: newer privacy schema versus an older reader
- Abuse path: rollback reinterprets stored records under weaker redaction or re-emits stripped secrets
- Prevention: rollback compatibility tests include privacy invariants; a privacy-weaker schema is refused
- Detection: schema version and migration state
- Failure behavior: refuse the weaker schema rather than rewrite records
- Recovery: stay on the privacy-preserving schema or use a bounded read-only fallback that does not export newly weakened fields
- Residual risk: unset
- Required test: rollback fixtures that attempt to read current records with a weaker schema and must fail closed
- Status: TARGET_DESIGN

## Governance — acceptance evidence hierarchy

Evidence tiers, from narrowest to broadest. Assigning a tier is a proof record. This document assigns none.

- UNIT_PROVED: one component met one requirement under its stated fixture. This does not establish integration, a stranger host, external proof, or customer validation.
- INTEGRATION_PROVED: linked components met the requirement together on one controlled host. This does not establish a stranger host, external proof, or customer validation.
- STRANGER_HOST_PROVED: the same check passed on a host that is not the producer’s development environment. This does not establish customer validation.
- PROVED_EXTERNAL: an independent verifier outside the producing change recorded the required evidence. This does not establish customer validation.
- CUSTOMER_VALIDATED: the customer confirmed the requirement on that customer’s own workload and window.

Rules:

- Producer success is not proof.
- Exit code zero is not proof.
- A healthy UI is not proof.
- Imported evidence is not local observation.
- Simulated demo evidence is not customer evidence.
- INTERNAL_PROOF cannot be displayed as CUSTOMER_VALIDATED.
- Stale evidence cannot retain a current pass.
- Unsupported and unavailable stay explicit.

Traceability for every roadmap item uses the template above, including current evidence tier, required closing tier, independent verifier, stranger-host, customer-validation, and status. Those evidence fields are unset. Status remains TARGET_DESIGN. No item is complete.

