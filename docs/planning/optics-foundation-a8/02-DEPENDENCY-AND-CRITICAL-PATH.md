# Dependency graph and critical path

Audience: INTERNAL_RESTRICTED

No dates. No durations. Order is a predecessor constraint, not a schedule.

Edges mean “the successor waits for the predecessor.” The canonical edge list is `dependency_graph.edges` in `IMPLEMENTATION-PACKAGES.json`. The graph hash in `PLANNING-MANIFEST.json` is the SHA-256 of that edge list encoded as canonical JSON.

## 1. Edges

| Predecessor | Successor | Why it waits |
| --- | --- | --- |
| PKG-01 | PKG-02 | Shared vocabulary implements the evidence contract |
| PKG-01 | PKG-03 | Health records use the same denylist |
| PKG-01 | PKG-04 | Proof fields are the allowlist |
| PKG-01 | PKG-05 | The store interface inserts allowlisted records |
| PKG-01 | PKG-09 | Correlation stamps fields the contract accepts |
| PKG-01 | PKG-12 | Fail-open includes the privacy exception |
| PKG-01 | PKG-15 | Trends need origin rules before they include a row |
| PKG-02 | PKG-09 | Cross-runtime correlation claims need one vocabulary |
| PKG-03 | PKG-12 | Recovery disclosure and drop counts need the health model |
| PKG-03 | PKG-13 | Diagnostic commands read self-health |
| PKG-04 | PKG-08 | Evidence-preserving migration claims need portable proof |
| PKG-05 | PKG-06 | Binding evaluation targets a fixed interface |
| PKG-05 | PKG-07 | Persistence implements the interface |
| PKG-05 | PKG-10 | The query engine calls the interface |
| PKG-05 | PKG-12 | Overload and crash behavior bind to interface failures |
| PKG-06 | PKG-07 | Binding selection before SQLite persistence |
| PKG-12 | PKG-07 | Fail-open before the store is the default write path |
| PKG-07 | PKG-08 | SQLite exists before legacy rows are copied into it |
| PKG-07 | PKG-11 | Retention acts on persistent rows |
| PKG-09 | PKG-10 | Correlation before session-aware querying |
| PKG-10 | PKG-14 | Query before UI |
| PKG-10 | PKG-15 | Completeness before trends, baselines, and indicators |
| PKG-15 | PKG-16 | Indicators before alerts that would read them |
| PKG-04 | PKG-17 | Export privacy and proof rules before any network export |
| PKG-01 | PKG-17 | Denylist before any network export |

Decision gates that are not packages sit in front of successors:

| Gate | Successor |
| --- | --- |
| Founder decision 9 | PKG-06 selection, then PKG-07 |
| Founder decision 13 | PKG-14 |
| Founder decision 3 | PKG-16 |
| Founder decision 12 | PKG-17 |
| Founder decision 10 | any emitter of freshness `CURRENT` |
| Founder decision 6 | any promote of `LEGACY_UNMARKED` |
| Founder decision 2 | any usage or cost field |

## 2. Foundational path

The path that must land before SQLite is the default writer:

1. PKG-01 evidence contract and write-path privacy.
2. PKG-03 self-health model and PKG-05 store interface, both after PKG-01. PKG-12 fail-open after PKG-01, PKG-03, and PKG-05.
3. Founder decision 9, then PKG-06.
4. PKG-07 schema and transactional persistence, only after PKG-06 and after PKG-12.

The path that must land before a migration claims evidence was preserved:

1. PKG-01, then PKG-04 portable proof.
2. PKG-07 store file.
3. PKG-08 explicit copy, with originals kept.

The path that must land before a trend or a UI:

1. PKG-01 origin rules.
2. PKG-09 correlation.
3. PKG-10 query envelope, including completeness.
4. PKG-15 trends after PKG-10.
5. PKG-14 UI after PKG-10 and after decision 13.

## 3. Optional paths

These can wait without blocking PKG-07:

- PKG-11 retention and prune commands. Default retention is unbounded, so the store can exist with no prune command.
- PKG-13 coverage command. Self-health can be recorded before a command prints it.
- PKG-04 as a customer-facing export. It is optional for creating the store and mandatory before PKG-08’s preservation claim.
- Memory-adapter PKG-10. Useful before the file exists. Session-aware file query is not optional once PKG-10 is the customer read API.

## 4. Deferred paths

- OF-07, OF-08, OF-09, OF-10, OF-11, OF-17, OF-18, OF-50, OF-51, OF-52 inside PKG-13.
- OF-16 deprecation schedule inside PKG-07, while schema status stays `unstable-pre-1.0`.
- OF-23 topology surface inside PKG-15.
- OF-44 incident workflow inside PKG-16.
- PKG-14, PKG-16, and PKG-17 until their Founder decisions.

Deferred work is absent from the foundational path.

## 5. Parallel-safe work

After PKG-01 is accepted, these may proceed in parallel with each other:

- PKG-02 writer conformance design
- PKG-03 health record model
- PKG-04 canonicalizer and verifier
- PKG-05 in-memory interface
- PKG-09 identity rules that do not yet write SQLite

PKG-10’s memory-adapter engine may proceed in parallel with PKG-04 and with PKG-06’s documentary evaluation once PKG-05 and PKG-09 are accepted. Pointing that engine at a store file waits for PKG-07. That wait is a mode of PKG-10. It is not an edge on the whole package, so the memory adapter is not blocked by SQLite.

PKG-11 may proceed in parallel with PKG-15 after PKG-07 and PKG-10 exist. Neither is the other’s predecessor.

## 6. Work that must not run in parallel

| Pair | Order |
| --- | --- |
| PKG-01 and any SQLite package | PKG-01 first. No overlap that creates a database |
| PKG-06 and PKG-07 | Binding selected first |
| PKG-12 and PKG-07 default-path enablement | Fail-open first |
| PKG-04 and PKG-08 preservation claims | Proof first |
| PKG-07 and PKG-08 | Store first |
| PKG-09 and session-aware PKG-10 | Correlation first |
| PKG-10 and PKG-14 | Query first |
| PKG-03 and PKG-13 commands | Self-health first |
| PKG-15 and customer-configured objectives | Indicators first. Objectives stay out until a customer target exists |
| Decision 3 and PKG-16 | Decision first |
| Decision 12 and PKG-17 | Decision first. Export privacy from PKG-01 and PKG-04 is already in front |
| Decision 13 and PKG-14 | Charter first |

A “parallel” implementation that adds `better-sqlite3` or any other binding while PKG-01 is open violates this graph.

## 7. Schema-freeze dependencies

There is no schema freeze in this plan.

- `schema_status` remains `unstable-pre-1.0`.
- Legacy JSON `schema_version` 2 stays the legacy marker. It is not SQLite `user_version`.
- `operational_schema_version` and `proof_schema_version` stay unassigned until the implementation force that writes a migrator. This plan does not assign them.
- `privacy_generation` is defined as starting at 1 on the first allowlist write. Slice 1 does not perform that write.
- OF-16’s deprecation schedule stays deferred until a future Founder declares a stable schema. This plan does not declare one.
- PKG-02 conformance fixtures may version the fixture set. That fixture version is not a customer schema version.

## 8. Rollback dependencies

- PKG-08 rollback assumes legacy JSON was never deleted. PKG-07 must not delete those files.
- PKG-04 rollback assumes proof bytes are verified as stored. PKG-11 must not rewrite them.
- PKG-07 rollback assumes no down-migration. PKG-12’s recovery envelope stays on disk if the software rolls back.
- PKG-01 rollback is package removal only while writers are unwired. After PKG-02 wires writers, rollback uses the PKG-02 and PKG-08 rules.
- A source rollback must keep recorded evidence readable. Unknown fields must not be reinterpreted as a successful provider call. The rule is specified in `04-MIGRATION-AND-ROLLBACK-PLAN.md`.

## 9. Cross-platform dependencies

- PKG-01 contract tests are pure and precede OS-specific store tests.
- PKG-06’s selection is invalid as a ship decision until Windows, Linux, macOS, and WSL load results exist. This plan does not produce those results.
- PKG-07’s Windows ACL claim waits on decision 8. Owner-only intent can be implemented on Unix without that decision. A Windows release that claims an ACL cannot.
- PKG-09 child-process propagation waits on OS environment and process semantics. It does not wait on SQLite.
- PKG-12 crash tests wait on OS signal behavior and must exist before PKG-07 is the default path on that OS.
- Offline use is a constraint on every package. None of the edges require a network service.

## 10. Critical path summary

Shortest ordered chain to a default local store, with Founder decisions written as gates:

`PKG-01 → (PKG-03 and PKG-05) → PKG-12 → decision 9 → PKG-06 → PKG-07`

Shortest ordered chain to an evidence-preserving legacy copy:

`PKG-01 → PKG-04` and `PKG-07`, then `PKG-08`

Shortest ordered chain to a bounded customer query:

`PKG-01 → PKG-09 → PKG-10`, with PKG-05 before the engine and PKG-07 before the engine reads a store file

Everything else is off those chains or blocked by an unresolved Founder decision.
