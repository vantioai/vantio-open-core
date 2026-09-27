# O1–O20 package catalog

Audience: INTERNAL_RESTRICTED

Producer classification: `OPTICS_STORE_OPTION_C_VERIFIED_PLAN_READY_FOR_COUNCIL`

Machine-readable copy: `PACKAGES.json`.

O-numbers are identities. Dependency order is `04-DEPENDENCY-ORDER.md`. Each package’s satisfaction owner is an existing PKG or an already written architecture section. Assignment is not implementation. Evidence tiers stay `UNSET`.

Status values used here: `DESIGN_SKETCH_ONLY`, `CONSTRAINT_VERIFIED_NOT_AUTHORIZED`, `SOURCE_PRESENT_INERT`, `NOT_AUTHORIZED`, `NEEDS_FOUNDER_DECISION`, `DEFERRED`. None of those words means the package is implemented.

`PKG-01` is the external predecessor for the allowlist and the denylist. It is on this commit as `@vantio/optics-evidence-contract` `0.0.0-unstable-pre-1.0`. Live products do not import it. It is not an O package.

## O1 — Self-health and diagnostic event model

- Status: `DESIGN_SKETCH_ONLY`
- Satisfaction owner: `PKG-03`
- Scope: the sketch in `02-O1-SELF-HEALTH-BOUNDARIES.md`
- Non-scope: `vantio doctor`, numeric targets, a store file
- Predecessors: `PKG-01`
- Dependents: `O10`, `O12`, `O13`
- Founder decisions: 4, for the unset latency measurements

## O2 — Application store contract

- Status: `CONSTRAINT_VERIFIED_NOT_AUTHORIZED`
- Satisfaction owner: `PKG-05`
- Scope: an application-owned put, get, and query interface. A later in-memory adapter may implement it for tests. Caller SQL is rejected. Allowlist is enforced before insert. This is the isolation boundary in `01-STORE-OPTION-C-VERIFICATION.md` section 4.
- Non-scope: a Node binding, `store.sqlite`, WAL, migrations, DuckDB, a daemon
- Predecessors: `PKG-01`
- Dependents: `O6`, `O7`, `O10`, `O11`, `O12`, `O19`
- Founder decisions: decision 9 belongs to `O6`, not to this package

## O3 — Writer vocabulary consumption

- Status: `SOURCE_PRESENT_INERT`
- Satisfaction owner: `PKG-02`
- Scope: future Node and Python writers emit the shared vocabulary. On this commit, `@vantio/optics-record-vocabulary` is private and inert. Pull request #63 merged that source. The in-repo Unit A notes still say `OPTICS_PKG02_UNIT_A_READY_FOR_COUNCIL` is not a council verdict. The PKG-02 planning council passed the planning packet (`OPTICS_PKG02_PLAN_COUNCIL_PASSED`). That pass is not a live writer.
- Non-scope: patching CLI `0.3.24`, sealing Python `3.1.0`, SQLite
- Predecessors: `PKG-01`
- Dependents: `O5` before a cross-runtime correlation claim
- Founder decisions: 2, 7, 11, with the existing safe defaults

## O4 — Portable proof

- Status: `NOT_AUTHORIZED`
- Satisfaction owner: `PKG-04`
- Scope: `OPTICS_CANONICAL_JSON` version 1 for `proof.json` and `manifest.json`, the 428-byte golden vector, mode `0600`, symlink refusal, and partial-write behavior that does not rename a partial file into place
- Non-scope: attestation language, OTLP, rewriting proofs during compaction
- Predecessors: `PKG-01`
- Dependents: `O8`, `O18`
- Founder decisions: 12 stays unauthorized and is `O18`

## O5 — Correlation identity

- Status: `NOT_AUTHORIZED`
- Satisfaction owner: `PKG-09`
- Scope: `session_id`, `run_id`, `trace_id`, `span_id`, `producer_id`, `producer_sequence`, `event_id`, and the child-process rules in A4. Baggage is dropped. Timestamp proximity does not assign a parent.
- Non-scope: SQLite, synthetic `LOCAL_OBSERVATION` rows for unobserved children
- Predecessors: `PKG-01`. `O3` before a cross-runtime claim
- Dependents: `O10`
- Founder decisions: decision 4 keeps any dedup window unset

## O6 — Node binding selection

- Status: `NEEDS_FOUNDER_DECISION`
- Satisfaction owner: `PKG-06`
- Scope: a later Founder force compares candidates against the `O2` interface, packaging, offline install, and fail-open if the binding cannot load. The deliverable is a selection record.
- Non-scope: this plan names no library and adds no dependency
- Predecessors: `O2`, Founder decision 9
- Dependents: `O7`
- Founder decisions: 9

## O7 — Transactional persistence behind the contract

- Status: `NOT_AUTHORIZED`
- Satisfaction owner: `PKG-07`
- Scope: the Option C file, WAL, `user_version`, row schema version, `privacy_generation`, external recovery envelope, symlink confinement, and owner-only create. Implements `O2`. Does not expose SQL.
- Non-scope: legacy import (`O8`), retention commands (`O9`), binding shopping (`O6`), encryption, a Windows ACL, numeric page size and busy timeout
- Predecessors: `O2`, `O6`, `O12`
- Dependents: `O8`, `O9`, file-backed mode of `O10`, `O20`
- Founder decisions: 4, 5, 8, and 9. Decision 9 blocks the package. The safe defaults for 4, 5, and 8 do not select numbers, encryption, or an ACL.

## O8 — Legacy JSON compatibility and explicit copy

- Status: `NOT_AUTHORIZED`
- Satisfaction owner: `PKG-08`
- Scope: dual-read, then an explicit copy that keeps originals. `VANTIO_HOME` honored by future readers. Origin rules from A1. No copy on first open.
- Non-scope: promote to `LOCAL_OBSERVATION`, deletion of originals, patching the CLI `0.3.24` reader
- Predecessors: `O7`, `O4`, `PKG-01`
- Dependents: `O15` default trend scope, `O20`
- Founder decisions: 6. Safe default is no promote.

## O9 — Retention, pruning, deletion, and restore

- Status: `NOT_AUTHORIZED`
- Satisfaction owner: `PKG-11`
- Scope: unbounded retention by default, customer limits as configuration, two-step prune, selective delete by the same manifest, explicit restore onto a new store id. Existing proof bytes stay unchanged.
- Non-scope: `vantio prune` and `vantio config` in this plan, compliance claims, deletion to free space when a queue is full
- Predecessors: `O7`
- Dependents: none on the path to a first store file
- Founder decisions: 4, 5, 8

## O10 — Bounded query

- Status: `NOT_AUTHORIZED`
- Satisfaction owner: `PKG-10`
- Scope: the A4 request and response envelope, limit 1–500 with default 100, two sorts, an opaque cursor, exact-match predicates on the indexed allowlist, and completeness as a property of declared scope. Default origin filter is `LOCAL_OBSERVATION` only. A memory-adapter mode can exist before a file. File-backed mode waits for `O7`.
- Non-scope: arbitrary SQL, caller regular expressions, body filters, UI, emitting freshness `CURRENT`
- Predecessors: `O5`, `O2`, `O1`, `O12`. File-backed mode also waits for `O7`.
- Dependents: `O14`, `O15`, `O16`, `O17`
- Founder decisions: 10. Freshness stays `UNKNOWN`.

## O11 — Cardinality and overload caps

- Status: `NOT_AUTHORIZED`
- Satisfaction owner: `PKG-12`, using A5 section 5 and decision-pack section 26. This O id is an ordering constraint inside that package. It is not a second build.
- Scope: indexed-field allowlist, metric labels limited to low-cardinality enums and `provider_id`, explicit drops, default `UNSAMPLED`, queue-full behavior that does not delete history
- Non-scope: a sampling policy, a numeric queue size, silent loss
- Predecessors: `O2`
- Dependents: `O12`
- Founder decisions: 4. Targets stay `NOT_SET`.

## O12 — Fail-open, crash, and recovery behavior

- Status: `NOT_AUTHORIZED`
- Satisfaction owner: `PKG-12`
- Scope: the A5 fail-open invariant, explicit drops, lifecycle states `COMPLETE`, `PARTIAL`, `INTERRUPTED`, `ABANDONED`, and `RECOVERED`, clock quality, and the rule that a future store call on the request path has no unbounded lock
- Non-scope: numeric budgets, sampling policies, enforcement, alerting
- Predecessors: `PKG-01`, `O1`, `O2`, `O11`
- Dependents: `O7` before the store is a default write path, `O10`, `O17`
- Founder decisions: 4

## O13 — Coverage transparency

- Status: `NOT_AUTHORIZED`
- Satisfaction owner: `PKG-13`
- Scope: a future coverage status that reports hooked versus unhooked paths with existing status tokens and product-health. An unsupported client is not a stored HTTP success.
- Non-scope: `vantio doctor`. Deferred inside the same PKG and left deferred here: `OF-07`, `OF-08`, `OF-09`, `OF-10`, `OF-11`, `OF-17`, `OF-18`, `OF-50`, `OF-51`, `OF-52`.
- Predecessors: `O1`, `PKG-01`
- Dependents: none on the store path
- Founder decisions: none required to keep the deferred list deferred

## O14 — Freshness and completeness emission

- Status: `NOT_AUTHORIZED`
- Satisfaction owner: `PKG-10` for `OF-27`. This O id is the emission rule inside that package. It is not a second query engine.
- Scope: `freshness`, `completeness`, `completenessReasons`, `integrityState`, `samplingState`, and `dropState` travel together on the default answer. `CURRENT` stays unemitted. Known drops in scope are `PARTIAL`.
- Non-scope: a freshness window, a percentage completeness score, an SLO
- Predecessors: `O10`
- Dependents: readers of the envelope, including `O15` and `O16`, through `O10`
- Founder decisions: 10

## O15 — Trends, baselines, and indicators

- Status: `NOT_AUTHORIZED`
- Satisfaction owner: `PKG-15`
- Scope: indicators from structural fields. Default trend scope excludes `LEGACY_UNMARKED`, demo, fixture, imported, product-health, and derived origins. A trend carries source completeness. No SLO until a customer sets a target and a window.
- Non-scope: `OF-23` topology, which stays `DEFERRED`. Alerting. Numeric SLO targets.
- Predecessors: `O10`, `PKG-01`
- Dependents: `O17`
- Founder decisions: 6 and 10

## O16 — Local read-only UI

- Status: `NEEDS_FOUNDER_DECISION`
- Satisfaction owner: `PKG-14`
- Scope after a charter: loopback bind, no third-party assets, no mutation API, no daemon, read the `O10` envelope, and present `PARTIAL`, `UNKNOWN`, and `UNAVAILABLE` as incomplete
- Non-scope until decision 13: any UI file
- Predecessors: Founder decision 13, `O10`
- Dependents: `O19` visible distinction
- Founder decisions: 13, and 4 for UI render latency, which stays `NOT_SET`

## O17 — Alerting

- Status: `NEEDS_FOUNDER_DECISION`
- Satisfaction owner: `PKG-16`
- Scope after decision 3: the selected delivery mode only. Privacy-invariant failure and evidence-write failure are the severity candidates the architecture already names. That sentence is a priority note.
- Non-scope: any alerter or daemon in this plan. `OF-44` stays `DEFERRED`.
- Predecessors: decision 3, `O15`, `O10`, `O12`
- Dependents: none
- Founder decisions: 3. Safe default is no alerter and no daemon.

## O18 — Network export

- Status: `NEEDS_FOUNDER_DECISION`
- Satisfaction owner: `PKG-17`
- Scope after decision 12: only an exporter a Founder names, fed by allowlisted fields, with completeness copied rather than upgraded
- Non-scope: OTLP, SIEM, and webhooks. Proof JSON stays `O4`.
- Predecessors: decision 12, `PKG-01`, `O4`
- Dependents: none
- Founder decisions: 12. Safe default is no exporter.

## O19 — Customer annotations

- Status: `NOT_AUTHORIZED`
- Satisfaction owner: architecture decision-pack section 6 and roadmap section 22. No separate PKG. No new writer in this plan.
- Scope: annotation text is customer-entered context, stored separately, and it does not mutate the observation. Role is `annotation_role` `CUSTOMER_ANNOTATION`.
- Non-scope: a seventh evidence origin, a UI, putting annotation text in the default proof
- Predecessors: `PKG-01`, `O2`. A visible on-screen distinction also waits for `O16`.
- Dependents: none
- Founder decisions: 7. Safe default keeps `annotation_role`.

## O20 — Release, upgrade, and customer-validation posture

- Status: `DEFERRED`
- Satisfaction owner: roadmap sections 7 and 21, and the deferred requirements `OF-50`, `OF-51`, and `OF-52` already parked on `PKG-13`. This O id does not authorize a release.
- Scope: no background auto-update, explicit version inspection, schema refusal for a newer store, and customer validation as a tier that no package has reached
- Non-scope: a tag, a publish, a seal, and treating this packet as customer validation
- Predecessors: `O7`, `O8`, `PKG-01`
- Dependents: none
- Founder decisions: none that this packet resolves

## Status counts

| Status | Packages |
| --- | --- |
| `DESIGN_SKETCH_ONLY` | O1 |
| `CONSTRAINT_VERIFIED_NOT_AUTHORIZED` | O2 |
| `SOURCE_PRESENT_INERT` | O3 |
| `NOT_AUTHORIZED` | O4, O5, O7, O8, O9, O10, O11, O12, O13, O14, O15, O19 (12) |
| `NEEDS_FOUNDER_DECISION` | O6, O16, O17, O18 |
| `DEFERRED` | O20 |

Count: 20.
