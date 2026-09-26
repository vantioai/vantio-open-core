# Implementation package map

Audience: INTERNAL_RESTRICTED

Producer classification: `OPTICS_FOUNDATION_IMPLEMENTATION_PLAN_READY_FOR_COUNCIL`

Machine-readable copy: `IMPLEMENTATION-PACKAGES.json`.

Package status is one of `PLANNED`, `BLOCKED_BY_DEPENDENCY`, `NEEDS_FOUNDER_DECISION`, `DEFERRED`. None of those words means the package is implemented. Evidence tiers stay `UNSET`.

No package is split further. The Founder taxonomy already isolates binding selection from schema work, proof from migration, and alerting from indicators. Collapsing those would couple releases that the architecture keeps apart.

Requirements listed under a package are assigned to it. Assignment is not satisfaction. Satisfaction waits for the evidence tier named on the requirement, which is `UNSET` now.

## PKG-01 — Evidence contract and write-path privacy boundary

- Status: `PLANNED`
- Customer problem: a record that crosses the persistence boundary can still carry a secret, a guessed provider, or an unlabeled evidence origin. Current Node and Python JSON writers disagree, and the privacy suite is `PARTIAL` in the inventory.
- Exact scope: one shared, testable contract for the current JSON persistence boundary. Allowlist, denylist, evidence origin, issue location, status tokens, destination sanitization, session id, trace context, structural redaction, privacy-invariant results, rejection and sanitization results, completeness impact on the validation result, Node and Python conformance fixtures, a privacy regression corpus, fail-open behavior of the contract API, and compatibility with current JSON readers. Detail: `07-FIRST-SLICE-SPECIFICATION.md`.
- Explicit non-scope: SQLite, schema, binding, WAL, migrations, legacy import execution, retention, pruning, trends, alerting, UI, daemon, OTLP, SIEM, stable schema, public API, new product telemetry, cost or token usage, at-rest encryption, machine hostname, promotion of `LEGACY_UNMARKED`, a seventh annotation origin, freshness `CURRENT`, numeric performance targets, and wiring the contract into `@vantio/cli@0.3.24` or into Python 3.1.0’s import path.
- Architectural requirements assigned: OF-13, OF-19, OF-22, OF-38, OF-39, OF-40, OF-49. OF-05 is assigned here as an exclusion (`NEEDS_FOUNDER_DECISION`), not as a field to add.
- Architecture documents consumed: `02-EVIDENCE-AND-PRIVACY-CONTRACT.md`, `07-THREAT-MODEL.md` (T12), `08-ARCHITECTURE-DECISION-PACK.md` sections 5–11, `01-CURRENT-STATE-INVENTORY.md` topics 1, 2, 16, 17, 25.
- Predecessors: none. This is the first slice.
- Downstream dependents: PKG-02, PKG-03, PKG-04, PKG-05, PKG-09, PKG-12, PKG-15.
- Files expected later, not in this planning commit: a private contract package `packages/optics-evidence-contract/` with a field catalog, Node and Python validators, and fixtures. The future force template names the exact set. Live files that must stay unchanged during Slice 1: `packages/vantio-cli/**`, `packages/vantio-agent-sdk-py/vantio/**`, `packages/vantio-agent-sdk/**`.
- Test fixtures: privacy corpus in `07-FIRST-SLICE-SPECIFICATION.md`; current Node and Python envelope shapes from inventory findings 1.2 and 2.2; issue-location cases from A1 section 3.1; session-id cases from A1 section 11.1.
- Platform matrix: contract tests are pure functions over bytes and strings. Required later on Windows, Linux, macOS, and WSL before any external claim. Offline. No daemon.
- Privacy / migration / compatibility risk: privacy-critical. Record-format-affecting only after a later writer cutover. Slice 1 itself is source-and-fixture until a Founder wires it. Current readers must keep parsing today’s files.
- Rollback design: remove the contract package. Legacy JSON files stay. No store file exists to roll back.
- Release boundary: internal contract package. It is not a CLI release and not a Python seal.
- Evidence required before an external claim: `UNIT_PROVED` on the corpus, then `INTEGRATION_PROVED` once writers are wired by a later package, then `STRANGER_HOST_PROVED` and `PROVED_EXTERNAL`. `CUSTOMER_VALIDATED` stays separate.
- Independent verifier required: yes, before any external privacy claim. Unset now.
- Stranger-host requirement: required before an external claim. Unset now.
- Customer-validation requirement: required before a customer claim. Unset now.
- Unresolved Founder decisions: 2, 6, 7, 11. Safe defaults are exclusion, no promote, `annotation_role`, hostname prohibited.
- Gates: implementation force still requires Gate 8, which this plan does not open. Slice 1 gates S1-G1 through S1-G10 are defined and unsatisfied. Merge of a future implementation requires an independent council on that tip. Release of CLI or Python is outside this package.
- Current status: `PLANNED`

## PKG-02 — Shared record vocabulary and Node/Python conformance

- Status: `BLOCKED_BY_DEPENDENCY`
- Customer problem: Node and Python persist different envelopes for the same run, so a reader cannot treat them as one vocabulary.
- Exact scope: make future Node and Python writers emit the PKG-01 catalog, including `schema_status`, catalog `provider_id` with `provider_confidence`, `process_id` when the runtime provides it, zero-call envelopes on attached processes, derived diagnostics kept beside observations, and enforcement actions kept out of Optics rows. Conformance is the shared fixture corpus from PKG-01 plus writer-level tests.
- Explicit non-scope: SQLite, the frozen CLI 0.3.24 patch, Python 3.0.15, OTLP semantic-convention export, a stable v1 schema, and a schema generator.
- Architectural requirements assigned: OF-20, OF-47.
- Architecture documents consumed: `04-SCHEMA-MIGRATION-AND-COMPATIBILITY.md` section 5, `02-EVIDENCE-AND-PRIVACY-CONTRACT.md`, `03-CROSS-PACKAGE-COMPATIBILITY.md` in this planning set.
- Predecessors: PKG-01.
- Downstream dependents: PKG-09, writer cutover that lets PKG-07 and PKG-08 trust new rows.
- Files expected later: a future CLI version’s interceptor mapper, and a future Python version after 3.1.0. Exact paths belong to that later force. This plan does not name a version bump.
- Test fixtures: paired Node and Python envelopes for one scripted call; zero-call attach; `est_spend_usd` dropped; `workflow` omitted; human sentences on `derived_diagnostic`.
- Platform matrix: Windows, Linux, macOS, WSL, container, offline, for both runtimes, before an external conformance claim.
- Privacy / migration / compatibility risk: record-format-affecting and customer-output-affecting once wired. Privacy-critical because the writer is where secrets would be stored.
- Rollback design: ship the previous writer. New files written by the new writer must remain readable by the dual-read adapter. Unknown fields must not become a fabricated success. See `04-MIGRATION-AND-ROLLBACK-PLAN.md`.
- Release boundary: staged. Python can rev without the frozen CLI. The live Node path waits for a future CLI version. Conformance evidence for a claimed pair of versions ships together.
- Evidence required: `INTEGRATION_PROVED` on both writers, then `STRANGER_HOST_PROVED` before an external claim.
- Independent verifier required: yes, before an external claim.
- Stranger-host requirement: yes, before an external claim.
- Customer-validation requirement: yes, before a customer claim. Unset now.
- Unresolved Founder decisions: 2, 7, 11. Same safe defaults as PKG-01.
- Gates: blocked until PKG-01 S1-G2 at least. Writer wiring is a separate Founder force after Slice 1. CLI 0.3.24 stays frozen through that force unless the Founder explicitly reopens it.
- Current status: `BLOCKED_BY_DEPENDENCY`

## PKG-03 — Optics self-health and diagnostic event model

- Status: `BLOCKED_BY_DEPENDENCY`
- Customer problem: Optics failures can look like customer or provider failures, and a diagnostic write can recurse into the observation hook.
- Exact scope: the `product_health` record type and the A5 diagnostic name enum, recursion stop, separation from customer activity, and the rule that corrupt-store disclosure is the external recovery envelope rather than a row inside a failed file. The envelope file itself is PKG-07. This package defines the health record and the in-memory recursion stop.
- Explicit non-scope: `vantio doctor`, a support bundle, UI rendering, numeric latency fields as targets, alerting.
- Architectural requirements assigned: none as the closing owner. PKG-12 and PKG-13 consume this model. The health record is a prerequisite, not a separate roadmap id.
- Architecture documents consumed: `06-SELF-OBSERVABILITY-AND-RELIABILITY.md` sections 1 and 2, `02-EVIDENCE-AND-PRIVACY-CONTRACT.md` section 4.5.
- Predecessors: PKG-01, so health records use the same denylist.
- Downstream dependents: PKG-12, PKG-13, PKG-10 (envelope reads drop and integrity state).
- Files expected later: health-record builder beside the contract package. Not a new telemetry channel.
- Test fixtures: diagnostic write failure increments one counter and stops; health payload contains a canary and the canary is absent; health row is absent from a default observation list.
- Platform matrix: same as PKG-01. Process-exit behavior covered again when PKG-12 lands.
- Privacy / migration / compatibility risk: privacy-critical if a health detail copies a payload. Migration risk is low until the row is stored.
- Rollback design: stop writing health records. Observation files remain. A missing health row surfaces as unknown drop state later, which PKG-10 must treat as not `COMPLETE`.
- Release boundary: can ship inside the contract package before SQLite. It must ship before diagnostic commands and before the store is the default path.
- Evidence required: `UNIT_PROVED`, then `INTEGRATION_PROVED` with the writer.
- Independent verifier required: yes, before an external claim.
- Stranger-host requirement: yes, before an external claim.
- Customer-validation requirement: unset. Required only for a customer-facing diagnostic claim.
- Unresolved Founder decisions: 4 (no numeric target on `write_latency_ms` or `query_latency_ms`).
- Gates: after PKG-01 contract acceptance. Before PKG-13 and before PKG-07 default-path enablement.
- Current status: `BLOCKED_BY_DEPENDENCY`

## PKG-04 — Portable proof canonicalization and verifier

- Status: `BLOCKED_BY_DEPENDENCY`
- Customer problem: today’s proof is a rendering of the run file. A byte-stable local export is specified and not built. Customers need a copy they can hash without calling it an attestation.
- Exact scope: `OPTICS_CANONICAL_JSON` version 1 for `proof.json` and `manifest.json`, the golden vector in A2 section 5.2, allowlisted proof fields, completeness copied from the source envelope, default exclusion of annotations, mode `0600`, symlink refusal, and partial-write behavior that does not rename a partial file into place.
- Explicit non-scope: tamper-proof, WORM, notarized, certified, regulator-approved, or externally attested language. OTLP. HTML and Markdown as hashed bytes. Rewriting proofs during compaction.
- Architectural requirements assigned: OF-43.
- Architecture documents consumed: `03-OPERATIONAL-STORE-AND-PORTABLE-PROOF.md` sections 5 and 5.1–5.2, `08-ARCHITECTURE-DECISION-PACK.md` sections 14, 15, and 39.
- Predecessors: PKG-01 allowlist. Completeness tokens are defined with PKG-10; the proof copies them and does not invent a second scale. A minimal proof can carry the completeness value the caller supplies before the query engine exists.
- Downstream dependents: PKG-08 (evidence-preserving migration claims), PKG-17 (any later exporter must be at least as strict).
- Files expected later: Node and Python canonicalizers and verifiers in the contract package or a sibling private package. Both must emit the golden vector bytes.
- Test fixtures: exact 428-byte vector and SHA-256 `a12adfa5f7b59aa3c4c8c98a52d36a50dcf861c3f8aea9bee7ee2eac70fd263a`; one inserted space; key-order change; semantic regeneration only after recanonicalization; prohibited field absent from proof bytes.
- Platform matrix: byte-identical results on Windows, Linux, macOS, and WSL. Offline.
- Privacy / migration / compatibility risk: privacy-critical. Customer-output-affecting. Proof bytes are immutable once written. A later canonicalizer must verify old proof bytes rather than rewrite them.
- Rollback design: keep already written proof files. An older verifier that does not know the profile fails the verification and must not reserialize and call that a pass. Rollback of the operational store does not delete proof files.
- Release boundary: independently releasable as a library after PKG-01, before any migration claims evidence preservation.
- Evidence required: `UNIT_PROVED` on the vector, then `INTEGRATION_PROVED` for Node and Python emitting the same bytes.
- Independent verifier required: yes. The architecture council recomputed the vector as a document check. That recomputation is not `PROVED_EXTERNAL` for an implementation.
- Stranger-host requirement: yes, before an external claim.
- Customer-validation requirement: unset until a customer uses the export.
- Unresolved Founder decisions: 12 stays unauthorized and is not this package.
- Gates: after PKG-01. Before PKG-08 claims. Golden-vector tests are a release gate for this package.
- Current status: `BLOCKED_BY_DEPENDENCY`

## PKG-05 — Operational-store interface and in-memory/reference adapter

- Status: `BLOCKED_BY_DEPENDENCY`
- Customer problem: search, tail, and diff currently scan every JSON file. The long-term index is specified as SQLite, and the application API must exist before a binding or a schema is chosen.
- Exact scope: an application-owned interface for put, get, and the A4 query request once PKG-10 defines it. An in-memory reference adapter implements the interface for tests. No SQL string is accepted from a caller. The interface returns the A4 envelope shape once PKG-10 exists; until then the interface may return rows plus an explicit completeness object supplied by the caller’s policy hooks from PKG-12.
- Explicit non-scope: choosing a Node binding, creating `store.sqlite`, WAL, migrations, raw SQL customer API, DuckDB, a daemon.
- Architectural requirements assigned: the interface half of OF-01. OF-01 closes at PKG-07.
- Architecture documents consumed: `03-OPERATIONAL-STORE-AND-PORTABLE-PROOF.md` sections 1–4, `05-CORRELATION-AND-QUERY-CONTRACT.md` section 5.
- Predecessors: PKG-01.
- Downstream dependents: PKG-06, PKG-07, PKG-10, PKG-12.
- Files expected later: interface module and in-memory adapter under the private contract package. No `sqlite` dependency.
- Test fixtures: allowlist enforced before insert; prohibited key absent after put; reference adapter loses nothing that a caller committed in memory; caller-supplied SQL text is rejected.
- Platform matrix: in-memory tests on every CI OS. No filesystem store yet.
- Privacy / migration / compatibility risk: source-only while the adapter is in memory. The interface shape becomes a compatibility surface for PKG-07.
- Rollback design: delete the adapter module. No customer files change.
- Release boundary: test and library boundary. Not a customer data migration.
- Evidence required: `UNIT_PROVED` on the adapter. `INTEGRATION_PROVED` when Node and Python adapters accept the same fixture set.
- Independent verifier required: yes, before an external store claim. The claim itself waits for PKG-07.
- Stranger-host requirement: not meaningful for memory-only. Required once the interface is backed by a file.
- Customer-validation requirement: unset.
- Unresolved Founder decisions: 9 is the next package, not this one. This package must not select a binding.
- Gates: after PKG-01. Before PKG-06 evaluation starts. Before PKG-07.
- Current status: `BLOCKED_BY_DEPENDENCY`

## PKG-06 — SQLite binding evaluation and selection

- Status: `NEEDS_FOUNDER_DECISION`
- Customer problem: Node has no stdlib SQLite. A binding chosen poorly becomes a native packaging and fail-open problem. Python’s expected mechanism is stdlib `sqlite3`, and that expectation is not an implementation.
- Exact scope: a later Founder force compares candidate Node bindings against the PKG-05 interface, zero-install and native-build constraints, Windows/Linux/macOS/WSL, offline install, and fail-open if the binding cannot load. The deliverable of that force is a Founder selection. This planning packet does not list candidate libraries and does not add a dependency.
- Explicit non-scope: adding a dependency, creating a database, implementing the schema, benchmarking a number, selecting encryption.
- Architectural requirements assigned: none. Decision 9 is the gate in front of OF-01’s persistence half.
- Architecture documents consumed: `03-OPERATIONAL-STORE-AND-PORTABLE-PROOF.md` sections 4 and 7, decision 9 in `08-ARCHITECTURE-DECISION-PACK.md`.
- Predecessors: PKG-05.
- Downstream dependents: PKG-07.
- Files expected later: a decision record under a future Founder force. Dependency manifests change only after selection, in the PKG-07 force, not in this package’s evaluation notes if the Founder wants the evaluation to stay documentary.
- Test fixtures: load-failure fixture once a binding exists: application output unchanged, writes stopped, explicit error on the Optics path.
- Platform matrix: the selection force must show Windows, Linux, macOS, and WSL load results before a selection is treated as shippable. This plan does not run that matrix.
- Privacy / migration / compatibility risk: a binding is persistent-data-affecting only after PKG-07. The selection itself can lock packaging.
- Rollback design: selection rollback is a Founder reversal before PKG-07 ships. After PKG-07 ships, rollback follows PKG-07 and must not delete the database file.
- Release boundary: not independently customer-releasable. Ships together with PKG-07 once selected.
- Evidence required: the selection force’s own evidence. No tier is assigned here.
- Independent verifier required: yes, on the selection force’s tip, before PKG-07 merges.
- Stranger-host requirement: yes, before the binding is called shippable.
- Customer-validation requirement: unset.
- Unresolved Founder decisions: 9. Also 4 and 5 stay out of the selection.
- Gates: Founder decision 9. PKG-05 accepted. This planning PR does not open the evaluation.
- Current status: `NEEDS_FOUNDER_DECISION`

## PKG-07 — SQLite schema and transactional persistence

- Status: `BLOCKED_BY_DEPENDENCY`
- Customer problem: per-run JSON is the legacy file and the current index. It does not give transactional integrity, crash behavior, or a single evidence root that both runtimes honor.
- Exact scope: application-owned schema in the selected binding, WAL, `user_version`, row `schema_version`, `privacy_generation` starting at 1 for the first allowlist write, path under the evidence root, `BEGIN IMMEDIATE` or the binding’s equivalent, external recovery envelope, symlink confinement, owner-only create, no raw SQL API, no empty replacement of a corrupt file.
- Explicit non-scope: legacy import (PKG-08), retention commands (PKG-11), binding shopping (PKG-06), encryption (decision 5), Windows ACL invention (decision 8), numeric page size and busy timeout (decision 4), a stable public schema.
- Architectural requirements assigned: OF-01 (closes here), OF-34, OF-35. OF-16 is assigned here as `DEFERRED` because no deprecation schedule opens while `schema_status` is `unstable-pre-1.0`.
- Architecture documents consumed: `03-OPERATIONAL-STORE-AND-PORTABLE-PROOF.md`, `04-SCHEMA-MIGRATION-AND-COMPATIBILITY.md` sections 1–4, `07-THREAT-MODEL.md` T6, T10, T15.
- Predecessors: PKG-01, PKG-05, PKG-06, PKG-12. Fail-open is in place before this store is the default write path. PKG-04 is not a prerequisite for creating the file. PKG-04 is a prerequisite for PKG-08’s preservation claims.
- Downstream dependents: PKG-08, PKG-11, PKG-15. File-backed query in PKG-10 also waits for this package. The memory-adapter query does not.
- Files expected later: schema and open/write/recover modules in the private package, called by a future CLI and a future Python version. Not called by CLI 0.3.24.
- Test fixtures: A3 section 3.2 corrupt-store plan; newer `user_version` refused; weaker privacy generation refused; Node and Python alternate committed writes; missing file created only on real `ENOENT` after symlink refusal.
- Platform matrix: Windows, Linux, macOS, WSL, container, offline. Windows ACL claim waits on decision 8.
- Privacy / migration / compatibility risk: persistent-data-affecting, privacy-critical, migration-critical. First writer assigns versions that later writers must honor.
- Rollback design: software rollback does not down-migrate the file. Legacy JSON remains because this package does not delete it. A newer `user_version` opens read-only or refuses. Unknown fields are not reread as success. Corrupt bytes stay. Detail in `04-MIGRATION-AND-ROLLBACK-PLAN.md`.
- Release boundary: ships together with the selected binding and with PKG-12’s default-path behavior. Not a silent swap on first open of an old CLI.
- Evidence required: `INTEGRATION_PROVED` on Node and Python against the same file, then `STRANGER_HOST_PROVED` before an external claim.
- Independent verifier required: yes.
- Stranger-host requirement: yes, before an external claim.
- Customer-validation requirement: unset. Required before a customer store claim.
- Unresolved Founder decisions: 4, 5, 8, 9. Decision 9 blocks the package. 4, 5, and 8 have safe defaults that allow a later implementation force to proceed only after decision 9, without inventing numbers, encryption, or ACLs.
- Gates: Gate 8 for that future force. PKG-06 selection recorded. PKG-12 fail-open tests green. Independent council on the implementation tip. No seal in the same force as the first schema write unless a later Founder says so.
- Current status: `BLOCKED_BY_DEPENDENCY`

## PKG-08 — Legacy JSON compatibility and migration tooling

- Status: `BLOCKED_BY_DEPENDENCY`
- Customer problem: customers already have `~/.vantio/runs/*.json`. Ignoring those files hides evidence. Copying them on first open would surprise them and could upgrade evidence maturity.
- Exact scope: dual-read adapter (L2) as the minimum, plus an explicit copy (L3) that keeps originals. `VANTIO_HOME` honored by future readers. Corrupt JSON counted and skipped, not deleted. Origin rules from A1. Demo host maps to `SIMULATED_DEMO`. Recognized provenance preserves an allowlisted origin. Everything else is `LEGACY_UNMARKED`.
- Explicit non-scope: copy on first open, promote to `LOCAL_OBSERVATION`, deletion of originals, using legacy `schema_version` 2 as SQLite `user_version`, patching CLI 0.3.24’s `homedir()` reader inside Slice 1.
- Architectural requirements assigned: OF-48.
- Architecture documents consumed: `04-SCHEMA-MIGRATION-AND-COMPATIBILITY.md` sections 5–7, `03-OPERATIONAL-STORE-AND-PORTABLE-PROOF.md` migration path, `02-EVIDENCE-AND-PRIVACY-CONTRACT.md` section 2.
- Predecessors: PKG-07, PKG-04, PKG-01. SQLite exists before migration writes into it. Portable proof exists before a claim that migration preserved evidence.
- Downstream dependents: PKG-15 default trend scope, supportability of old files.
- Files expected later: read-only adapter and an explicit migrate command in a future CLI. Command is not created here.
- Test fixtures: A3 section 7 list, including a claimed `LOCAL_OBSERVATION` without provenance reading as `LEGACY_UNMARKED`, and a demo file excluded from a trend query.
- Platform matrix: path and permission behavior on Windows, Linux, macOS, WSL. Offline.
- Privacy / migration / compatibility risk: migration-critical and privacy-critical. A bad mapper can persist a secret that the old file only held in a dropped key, or can launder origin.
- Rollback design: originals remain. A failed copy rolls the store transaction back and leaves the previous database file. Software rollback still reads legacy JSON. Migrated rows with a newer schema are not rewritten down. Unknown fields are not treated as success.
- Release boundary: separate from first store creation. Explicit customer invocation. Not the default on open.
- Evidence required: `INTEGRATION_PROVED` on Node and Python fixtures, including corrupt files left in place.
- Independent verifier required: yes, before a preservation claim.
- Stranger-host requirement: yes, before an external claim.
- Customer-validation requirement: unset. A preservation claim aimed at customers needs it.
- Unresolved Founder decisions: 6. Safe default is no promote.
- Gates: after PKG-07 and PKG-04. Independent council. Dry-run before any write copy.
- Current status: `BLOCKED_BY_DEPENDENCY`

## PKG-09 — Correlation identity and child-process propagation

- Status: `BLOCKED_BY_DEPENDENCY`
- Customer problem: today’s `trace_id` is a process-run id. Child processes, retries, and inherited context can be counted as one run or as a fake observation.
- Exact scope: `session_id`, `run_id`, `trace_id`, `span_id`, `producer_id`, `producer_sequence`, `event_id` encoding `e.` + length + producer + sequence, `VANTIO_TRACE_ID` as `ASSERTED_CONTEXT`, `parent_run_id` only from valid `VANTIO_PARENT_RUN_ID`, conflict visibility, baggage dropped, malformed context dropped.
- Explicit non-scope: timestamp-proximity parenthood, a time-window dedup heuristic while the window is `NOT_SET`, synthetic `LOCAL_OBSERVATION` rows for unobserved children, SQLite.
- Architectural requirements assigned: OF-03, OF-21, OF-25.
- Architecture documents consumed: `05-CORRELATION-AND-QUERY-CONTRACT.md` sections 1–3, `07-THREAT-MODEL.md` T4 and T13, A1 section 11.
- Predecessors: PKG-01 (session and trace validation). PKG-02 before a cross-runtime conformance claim.
- Downstream dependents: PKG-10.
- Files expected later: propagation in a future CLI wrapper and a future Python process wrap. Slice 1 validates the fields. This package writes them on the live path only in a later force.
- Test fixtures: A4 section 1.1 child-process table.
- Platform matrix: process and environment inheritance on Windows, Linux, macOS, WSL. Offline.
- Privacy / migration / compatibility risk: record-format-affecting. High-cardinality ids must stay off metric labels. Bad baggage must not be stored.
- Rollback design: old files keep their single `trace_id`. Readers map that string to `run_id` for legacy files and must not invent a parent. New ids that an older reader ignores must not be displayed as a successful provider call.
- Release boundary: can follow PKG-02 in a writer release. Session-aware queries wait for PKG-10.
- Evidence required: `INTEGRATION_PROVED` on parent/child fixtures.
- Independent verifier required: yes, before an external correlation claim.
- Stranger-host requirement: yes, before an external claim.
- Customer-validation requirement: unset.
- Unresolved Founder decisions: none that change the safe default. Decision 4 keeps the dedup window unset.
- Gates: after PKG-01. Before PKG-10 session filters. Writer cutover is not Slice 1.
- Current status: `BLOCKED_BY_DEPENDENCY`

## PKG-10 — Bounded query contract and query engine

- Status: `BLOCKED_BY_DEPENDENCY`
- Customer problem: search is an unbounded substring scan. Diff is a two-run host rollup. Completeness, drops, and integrity are not one answer.
- Exact scope: the A4 request and response envelope, limit 1–500 default 100, two sorts, opaque cursor, exact-match predicates on the indexed allowlist, cardinality rules, completeness as a property of declared scope, default origin `LOCAL_OBSERVATION` only. Engine against the PKG-05 memory adapter first. File-backed engine after PKG-07.
- Explicit non-scope: arbitrary SQL, caller regular expressions, body filters, UI, trend commands, emitting freshness `CURRENT`.
- Architectural requirements assigned: OF-27, OF-29, OF-33, OF-42.
- Architecture documents consumed: `05-CORRELATION-AND-QUERY-CONTRACT.md` sections 5–6, `06-SELF-OBSERVABILITY-AND-RELIABILITY.md` on drops and freshness, `08-ARCHITECTURE-DECISION-PACK.md` sections 25–26 and 39.
- Predecessors: PKG-09, PKG-05, PKG-03, PKG-12 (drop behavior). PKG-07 before the engine is pointed at a customer store file.
- Downstream dependents: PKG-14, PKG-15, PKG-04 proof scope when the proof is generated from a query, PKG-08 trend exclusion tests.
- Files expected later: query module in the private package and, later, a future CLI command. No command is added to CLI 0.3.24.
- Test fixtures: A4 section 5.3 completeness plan; `hasMore` false with drops is `PARTIAL`; salvage is never `COMPLETE`; `declaredScope` lists excluded origins.
- Platform matrix: same OS set. Offline. Query-cost number stays `NOT_SET`; structural caps are the gate.
- Privacy / migration / compatibility risk: customer-output-affecting. A query that returns a prohibited field fails the privacy gate. Pagination must not be labeled complete.
- Rollback design: disable the command. Stored rows stay. An older caller that does not understand `completeness` must not render a blank envelope as success. The envelope field is required on every answer the new engine returns.
- Release boundary: memory-adapter engine can be an internal release. Customer command waits until file-backed results and fail-open are in place.
- Evidence required: `INTEGRATION_PROVED` on the envelope.
- Independent verifier required: yes.
- Stranger-host requirement: yes, before an external claim.
- Customer-validation requirement: unset.
- Unresolved Founder decisions: 10. Safe default: freshness `UNKNOWN`, `CURRENT` unemitted. Decision 4 leaves query latency `NOT_SET`.
- Gates: after correlation and after the store interface. Before any UI. Before trends.
- Current status: `BLOCKED_BY_DEPENDENCY`

## PKG-11 — Retention, pruning, deletion, backup, and restoration

- Status: `BLOCKED_BY_DEPENDENCY`
- Customer problem: nothing deletes evidence today, and a future limit must not silently delete or compact exported proofs.
- Exact scope: default unbounded retention; customer limits as configuration; prune as dry-run manifest then a second explicit step; selective delete by the same manifest; backup copy before migration already specified in PKG-07; restore is an explicit workflow onto a new store id; proofs already written stay byte-identical.
- Explicit non-scope: `vantio prune` and `vantio config` in this plan, compliance or certified-deletion claims, deletion to free space when the queue is full, at-rest encryption.
- Architectural requirements assigned: OF-02, OF-15, OF-41.
- Architecture documents consumed: `03-OPERATIONAL-STORE-AND-PORTABLE-PROOF.md` section 6, `04-SCHEMA-MIGRATION-AND-COMPATIBILITY.md` backup rule, `08-ARCHITECTURE-DECISION-PACK.md` sections 16 and 30.
- Predecessors: PKG-07.
- Downstream dependents: none on the critical path to a first store. Support and customer data-ops claims depend on this package.
- Files expected later: future commands and a config file. Schema of the config file is not fully specified in the architecture, so the implementation force must keep the config surface limited to the named limit fields or stop for a Founder note.
- Test fixtures: unset limit deletes nothing; dry-run writes a manifest and deletes nothing; second step deletes only matching manifest rows; proof bytes unchanged; queue-full does not delete history.
- Platform matrix: filesystem permissions on Windows, Linux, macOS, WSL. Offline.
- Privacy / migration / compatibility risk: persistent-data-affecting and privacy-critical. A manifest must not list payloads. Restoration must not mark salvage `COMPLETE`.
- Rollback design: software rollback does not restore deleted rows by guessing. Backups taken before a prune are customer files, restored only by the explicit workflow. A failed restore leaves `RECOVERY_FAILED` and the original bytes.
- Release boundary: separate from store creation. Default install behavior is unbounded retention with no prune command required.
- Evidence required: `INTEGRATION_PROVED` on dry-run and on the explicit second step.
- Independent verifier required: yes, before a deletion claim.
- Stranger-host requirement: yes, before an external claim.
- Customer-validation requirement: unset. Deletion claims aimed at customers need it.
- Unresolved Founder decisions: 4, 5, 8.
- Gates: after PKG-07. Two-step prune is a release gate. No compliance wording in release notes.
- Current status: `BLOCKED_BY_DEPENDENCY`

## PKG-12 — Fail-open, overload, crash, and recovery behavior

- Status: `BLOCKED_BY_DEPENDENCY`
- Customer problem: observation must not fail, hang, or rewrite the application call, and it must not invent a successful observation when the write did not happen.
- Exact scope: the A5 fail-open invariant, privacy and evidence-root exceptions, explicit drops, default `UNSAMPLED`, queue-full behavior that does not delete history, lifecycle states, clock quality, crash labels, and the rule that a future store call on the request path has no unbounded lock. Slice 1 covers the contract-API subset. This package covers the runtime and store subset.
- Explicit non-scope: numeric budgets, sampling policies, enforcement block/redact/cap, a timeout number, alerting.
- Architectural requirements assigned: OF-14, OF-26, OF-31, OF-32 (`NEEDS_FOUNDER_DECISION` for the numbers).
- Architecture documents consumed: `06-SELF-OBSERVABILITY-AND-RELIABILITY.md`, `07-THREAT-MODEL.md` T1, T5, T11, T13, A5 sections 3–6.
- Predecessors: PKG-01, PKG-03, PKG-05.
- Downstream dependents: PKG-07 default path, PKG-10 drop disclosure, PKG-16 if alerting is ever selected.
- Files expected later: runtime guards in a future CLI and future Python writer. Slice 1’s future force tests the contract API only.
- Test fixtures: observation exception leaves a scripted application result unchanged; prohibited value drops the field or event; symlink escape refuses the write; queue-full records one drop count; `SIGKILL` is `ABANDONED` or absence, not a backfilled success; duplicate hooks do not inflate the deduped count.
- Platform matrix: signals and process kill differ by OS. Windows, Linux, macOS, WSL, container, offline. Crash tests are part of the package gate.
- Privacy / migration / compatibility risk: privacy-critical on the drop path. Persistent-data-affecting once lifecycle and recovery files are written.
- Rollback design: returning to the current exit-write behavior must still read old JSON. It must not relabel a missing flush as `COMPLETE`. Recovery envelopes written by a newer build stay on disk and an older build must not delete them to look healthy.
- Release boundary: required in the same release that turns SQLite on as the default writer. The Slice 1 subset ships earlier inside the contract library.
- Evidence required: `INTEGRATION_PROVED` including adversity tests. `STRANGER_HOST_PROVED` before an external reliability claim.
- Independent verifier required: yes.
- Stranger-host requirement: yes, before an external claim.
- Customer-validation requirement: unset.
- Unresolved Founder decisions: 4. Safe default: targets stay `NOT_SET`; structural behavior from A5 still applies; no invented timeout.
- Gates: before PKG-07 is the default path. S1-G7 covers only the contract-API subset.
- Current status: `BLOCKED_BY_DEPENDENCY`

## PKG-13 — Coverage transparency and future diagnostic command surface

- Status: `BLOCKED_BY_DEPENDENCY`
- Customer problem: unsupported clients and coverage gaps are easy to read as a quiet success. Several CLI convenience items were inventoried and were not given a contract.
- Exact scope for this foundation: a future coverage status that reports hooked versus unhooked paths using existing status tokens and product-health, without calling a gap a successful provider call. `vantio doctor` stays uncreated.
- Explicit non-scope and deferred requirements: OF-07 `NO_COLOR`, OF-08 shell completion, OF-09 status legend, OF-10 pager, OF-11 quiet mode, OF-17 generated help, OF-18 example repository, OF-50 public doc rewrite, OF-51 support-operations program, OF-52 customer-acceptance protocol. Those requirements stay `DEFERRED`. The architecture marks several of them out of this foundation’s implementation scope or unspecified as commands.
- Architectural requirements assigned: OF-12 as `BLOCKED_BY_DEPENDENCY`. Deferred ids listed above.
- Architecture documents consumed: `01-CURRENT-STATE-INVENTORY.md` topics 12 and 25, `00-PROGRAM-BOUNDARY.md`, A1 status-token note.
- Predecessors: PKG-03 before any diagnostic command. PKG-01 so coverage tokens stay distinct from origins.
- Downstream dependents: none on the store critical path.
- Files expected later: a future CLI command in a version after 0.3.24. Not in Slice 1.
- Test fixtures: unsupported client yields `COVERAGE` or `UNKNOWN` and `NOT_OBSERVED`, and does not yield a stored HTTP success.
- Platform matrix: follows the CLI’s OS matrix when the command exists.
- Privacy / migration / compatibility risk: customer-output-affecting. Low persistence risk if the command is read-only.
- Rollback design: remove the command. Stored evidence stays. The command must not be the only reader that understands the store.
- Release boundary: independently releasable after self-health exists. Deferred chrome items are each their own future decision.
- Evidence required: `INTEGRATION_PROVED` for OF-12 if it is built.
- Independent verifier required: yes, before an external coverage claim.
- Stranger-host requirement: yes, before an external claim.
- Customer-validation requirement: OF-52 stays `DEFERRED` and unset.
- Unresolved Founder decisions: none required to keep the deferred list deferred.
- Gates: self-health before the command. CLI 0.3.24 unchanged.
- Current status: `BLOCKED_BY_DEPENDENCY`

## PKG-14 — Local read-only UI foundation

- Status: `NEEDS_FOUNDER_DECISION`
- Customer problem: a local read-only view is a roadmap target. The charter and accessibility work are not opened. Building from security notes alone would skip that decision.
- Exact scope, after a charter: loopback bind, no third-party assets, no mutation API, no daemon, read the PKG-10 envelope, use A1 human labels, and present `PARTIAL`, `UNKNOWN`, and `UNAVAILABLE` as incomplete.
- Explicit non-scope until decision 13: any UI file, asset pipeline, account login, or hosted dashboard.
- Architectural requirements assigned: OF-06, OF-36, OF-37. All three stay blocked on decision 13. OF-36’s security prerequisites are architecture. They are not a charter.
- Architecture documents consumed: `08-ARCHITECTURE-DECISION-PACK.md` sections 33–35, `07-THREAT-MODEL.md` T7 and T8, `09-IMPLEMENTATION-GATES.md` on OF-06.
- Predecessors: Founder decision 13, PKG-10, and the OF-36 prerequisites. Query and security come before UI.
- Downstream dependents: PKG-15 exemplars that need a drill-down surface.
- Files expected later: none in this plan. A charter force names them.
- Test fixtures, after a charter: injection case T7, non-loopback refusal T8, partial envelope not styled as success.
- Platform matrix: browser on Windows, Linux, macOS. Not started.
- Privacy / migration / compatibility risk: customer-output-affecting and privacy-critical if the UI renders a prohibited field.
- Rollback design: stop the process. The UI writes nothing, so rollback has no data half. A UI that gained a write API would violate OF-36 and is out of scope.
- Release boundary: own release after the charter. Not bundled silently into the CLI 0.3.24 freeze.
- Evidence required: `INTEGRATION_PROVED` plus the accessibility evidence the charter requires. Unset now.
- Independent verifier required: yes.
- Stranger-host requirement: yes, before an external claim.
- Customer-validation requirement: unset. OF-37 and OF-06 need it before a customer UX claim.
- Unresolved Founder decisions: 13, and 4 for `NFR-UI-QUERY-RENDER-LATENCY`.
- Gates: decision 13, then PKG-10, then a UI force. This plan does not open the charter.
- Current status: `NEEDS_FOUNDER_DECISION`

## PKG-15 — Trends, baselines, indicators, and exemplars

- Status: `BLOCKED_BY_DEPENDENCY`
- Customer problem: cross-run comparison is a two-file diff. Baselines and indicators are easy to confuse with SLOs and with demo or legacy rows.
- Exact scope: indicators from structural fields only; default trend scope excludes `LEGACY_UNMARKED`, demo, fixture, imported, product-health, and derived origins; a trend carries source completeness; no SLO until a customer sets a target and a window; exemplars wait on a UI drill-down; no ownership inference for topology.
- Explicit non-scope: OF-23 topology surface (`DEFERRED`, unspecified), customer-configured objectives, alerting, numeric SLO targets.
- Architectural requirements assigned: OF-04, OF-24, OF-28, OF-30, OF-46. OF-23 assigned `DEFERRED`.
- Architecture documents consumed: `05-CORRELATION-AND-QUERY-CONTRACT.md` trend notes, `06-SELF-OBSERVABILITY-AND-RELIABILITY.md` section 8, `08-ARCHITECTURE-DECISION-PACK.md` sections 28–29.
- Predecessors: PKG-10 and PKG-01 origin rules. Exemplars also wait on PKG-14.
- Downstream dependents: PKG-16 if alerts ever key off indicators.
- Files expected later: a future command after the query engine. Not in Slice 1.
- Test fixtures: demo and `LEGACY_UNMARKED` excluded; partial source stays partial on the rollup; indicator label set rejects `session_id` and raw host.
- Platform matrix: same as PKG-10.
- Privacy / migration / compatibility risk: customer-output-affecting. Wrong origin filter inflates customer activity.
- Rollback design: disable the command. Underlying rows stay. An older build must not add excluded origins back into a stored total by reinterpreting missing origin as `LOCAL_OBSERVATION`.
- Release boundary: after query. Separate from alerting. SLO configuration is not in this release.
- Evidence required: `INTEGRATION_PROVED` on scope and completeness propagation.
- Independent verifier required: yes.
- Stranger-host requirement: yes, before an external claim.
- Customer-validation requirement: unset. A trend claim aimed at customers needs it.
- Unresolved Founder decisions: 6 and 10. Safe defaults: no promote, `CURRENT` unemitted, excluded origins listed in `declaredScope`.
- Gates: evidence origin and completeness before trends. Indicators before any customer objective. UI charter before exemplar drill-down.
- Current status: `BLOCKED_BY_DEPENDENCY`

## PKG-16 — Future alerting architecture implementation

- Status: `NEEDS_FOUNDER_DECISION`
- Customer problem: the roadmap names an alert lifecycle and does not select a delivery mode. A daemon would contradict fail-open and the rejected store option E.
- Exact scope after decision 3: the selected mode only, fed by PKG-15 indicators and PKG-10 completeness, with privacy-invariant failure and evidence-write failure as the severity candidates the architecture already names. That sentence is a priority note in A5, not an implementation.
- Explicit non-scope: any alerter, daemon, pager, or webhook in this plan. OF-44 incident workflow is `DEFERRED` because no workflow is specified.
- Architectural requirements assigned: OF-45 (`NEEDS_FOUNDER_DECISION`), OF-44 (`DEFERRED`).
- Architecture documents consumed: `06-SELF-OBSERVABILITY-AND-RELIABILITY.md` section 9, `08-ARCHITECTURE-DECISION-PACK.md` decision 3.
- Predecessors: decision 3, PKG-15, PKG-10, PKG-12.
- Downstream dependents: none.
- Files expected later: none until a Founder selects a mode.
- Test fixtures: specified by that later force. Must include a case where Optics failure does not page the application into a failed exit.
- Platform matrix: depends on the mode. Unset.
- Privacy / migration / compatibility risk: privacy-critical if an alert body copies a record. Customer-output-affecting.
- Rollback design: disable the emitter. Already stored evidence stays. Alerts are not an evidence origin.
- Release boundary: own release after the decision. Not bundled with the store.
- Evidence required: `INTEGRATION_PROVED` for the selected mode, then stranger-host before an external claim.
- Independent verifier required: yes.
- Stranger-host requirement: yes, before an external claim.
- Customer-validation requirement: unset.
- Unresolved Founder decisions: 3. Safe default: no alerter and no daemon.
- Gates: alerting decision before any alert implementation.
- Current status: `NEEDS_FOUNDER_DECISION`

## PKG-17 — Future interoperability and export implementation

- Status: `NEEDS_FOUNDER_DECISION`
- Customer problem: some customers will ask for OTLP or SIEM export. The architecture leaves that unauthorized. The specified export is the portable proof.
- Exact scope after decision 12: only the exporter the Founder names, fed by allowlisted fields, with the same denylist as PKG-01 and with completeness copied rather than upgraded. Until that decision, the package has no implementation scope.
- Explicit non-scope: OTLP, SIEM, webhooks, and any network export in this plan. Proof JSON stays PKG-04.
- Architectural requirements assigned: none of the 52 close here. OF-43 closes in PKG-04. Decision 12 is the reason this package exists as a blocked successor.
- Architecture documents consumed: `03-OPERATIONAL-STORE-AND-PORTABLE-PROOF.md` section 5, `08-ARCHITECTURE-DECISION-PACK.md` decision 12, A1 prohibited-data list.
- Predecessors: decision 12, PKG-01, PKG-04.
- Downstream dependents: none.
- Files expected later: none until authorized.
- Test fixtures: a later force must show a prohibited canary absent from the exported bytes.
- Platform matrix: unset until a protocol is chosen.
- Privacy / migration / compatibility risk: privacy-critical. Export is customer-output-affecting and can leave the machine.
- Rollback design: disable the exporter. Proof files already written stay. A rollback must not send a queued payload that the new policy would drop.
- Release boundary: own release after the decision. Export privacy lands before the exporter.
- Evidence required: `INTEGRATION_PROVED` and `STRANGER_HOST_PROVED` before an external interoperability claim.
- Independent verifier required: yes.
- Stranger-host requirement: yes.
- Customer-validation requirement: unset.
- Unresolved Founder decisions: 12. Safe default: no exporter.
- Gates: export privacy and the Founder decision before any OTLP or SIEM work.
- Current status: `NEEDS_FOUNDER_DECISION`

## Package status counts

| Status | Packages |
| --- | --- |
| `PLANNED` | PKG-01 (1) |
| `BLOCKED_BY_DEPENDENCY` | PKG-02, PKG-03, PKG-04, PKG-05, PKG-07, PKG-08, PKG-09, PKG-10, PKG-11, PKG-12, PKG-13, PKG-15 (12) |
| `NEEDS_FOUNDER_DECISION` | PKG-06, PKG-14, PKG-16, PKG-17 (4) |
| `DEFERRED` | no package is wholly deferred (0) |

Deferred requirements live inside PKG-07 (OF-16), PKG-13, and PKG-15 (OF-23) and PKG-16 (OF-44). Counts by requirement are in `IMPLEMENTATION-PACKAGES.json`.
