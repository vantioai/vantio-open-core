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
- Status: TARGET_DESIGN / INTERNAL_PROOF / PROVED_EXTERNAL / CUSTOMER_VALIDATED

