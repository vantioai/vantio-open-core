# Fresh independent A7 re-council

Audience: INTERNAL_RESTRICTED

Council: Cursor cloud agent `bc-5bb719b6-65bf-522c-a9b9-f3a9a96ef08b`, model Grok 4.7. This agent filled all 12 seats named in the re-council brief. It did not produce the A0–A6 pack and it did not produce the narrow revision. Producer of the revision: `bc-ed83d59a-1f55-569f-b02b-41135b77b95e`. First council, whose judgments were not reused: `bc-fd7a995a-0bba-5f0c-955b-f21702e5c6a2`.

Reviewed tip: `7db944d17c7f74706f08970b4908e92d0bf2d589` on draft PR https://github.com/vantioai/vantio-open-core/pull/55, branch `architecture/optics-foundation-a0-a7`. That tip matched `origin/architecture/optics-foundation-a0-a7` at review. Starting main: `d6b74d41808a43f251d6de46e1313625a025d16d`. Prior council tip, superseded for this review: `48bec775d421260e930fbf6e6b8b84acab0524f2`.

Reviewed at: 2026-09-26T16:38:00Z.

This file replaces the first council’s report text. The first council’s classification remains in git history at `48bec77` as `OPTICS_FOUNDATION_ARCHITECTURE_NEEDS_REVISION`. This re-council read the revised contracts at the tip above and reached its own verdict.

## Classification

`OPTICS_FOUNDATION_ARCHITECTURE_COUNCIL_PASSED`

The six blockers are specified, A1 and A5 agree on issue location, completeness is a property of declared scope, corrupt-store disclosure sits outside the failed file, legacy origin and `session_id` have one acceptance story, the proof profile has one byte form with a recomputed golden vector, and child-process identity scopes are explicit. Option C remains `FOUNDER_RATIFIED_ARCHITECTURE_ONLY`. Founder decisions 2–13 stay unresolved. No product code is authorized. Gate 8 stays closed. A8 is not started. The PR stays draft.

Producer classification `OPTICS_FOUNDATION_ARCHITECTURE_REVISION_READY_FOR_RECOUNCIL` remains the producer’s handoff. It is not this verdict. This verdict does not assign `UNIT_PROVED`, `INTEGRATION_PROVED`, `STRANGER_HOST_PROVED`, `PROVED_EXTERNAL`, or `CUSTOMER_VALIDATED`.

## Seat table

| Seat | Scope | Verdict |
| --- | --- | --- |
| 1 | Observability architecture | PASS |
| 2 | Data storage and recovery | PASS_WITH_NONBLOCKING_NOTES |
| 3 | Privacy and minimization | PASS_WITH_NONBLOCKING_NOTES |
| 4 | Application reliability and fail-open | PASS_WITH_NONBLOCKING_NOTES |
| 5 | Distributed tracing and child-process correlation | PASS_WITH_NONBLOCKING_NOTES |
| 6 | Query completeness and cardinality | PASS |
| 7 | Portable proof and canonicalization | PASS_WITH_NONBLOCKING_NOTES |
| 8 | Local security and corrupt-store recovery | PASS_WITH_NONBLOCKING_NOTES |
| 9 | Customer diagnostics | PASS |
| 10 | Evidence and independent verification | PASS_WITH_NONBLOCKING_NOTES |
| 11 | Cross-platform engineering | PASS_WITH_NONBLOCKING_NOTES |
| 12 | Scope control and product positioning | PASS |

## Blocker dispositions

### Blocker 1 — Issue location — PASS

Successful operations use `NONE`. HTTP 4xx and 5xx name an observed unsuccessful response as `PROVIDER_INTERACTION`. The human label is “Provider interaction.” Display text does not use “Provider fault.” A1 section 3 is the only selection rule, and A5 section 2 says it uses that rule.

Evidence:

- `02-EVIDENCE-AND-PRIVACY-CONTRACT.md` section 3. `NONE` is the value for a successful operation and for HTTP 2xx and HTTP 3xx. Rule 3 assigns HTTP 400–599 to `PROVIDER_INTERACTION`. The same section says that value means an unsuccessful HTTP response was observed and does not mean the provider is at fault. Catalog confidence does not change the location. `optics_status` `SUCCESS` means the record was stored. Disk pressure on the Optics write path is rule 1, `OPTICS`. An undetermined layer is `UNKNOWN`.
- Section 3.1 requires `NONE` for success and for HTTP 200 and HTTP 3xx, and `PROVIDER_INTERACTION` with human label “Provider interaction” for HTTP 401, 429, and 500. Display text for those cases does not contain “Provider fault.”
- Section 10’s illustration sets HTTP 200, `application_status` `SUCCESS`, and `issue_location` `NONE`. The following sentence assigns an observed HTTP 401 to `APPLICATION_ERROR`, `PROVIDER_INTERACTION`, and “Provider interaction.”
- `06-SELF-OBSERVABILITY-AND-RELIABILITY.md` section 2 repeats those rows and states that the table does not add a second mapping. A stored HTTP 500 can have `optics_status` `SUCCESS` and `issue_location` `PROVIDER_INTERACTION`. `OPTICS_ERROR` is reserved for an Optics-local failure.
- `08-ARCHITECTURE-DECISION-PACK.md` section 7 records the same enum, the same success value, and the same display rule.

### Blocker 2 — Completeness — PASS

Completeness describes the declared evidence scope. Pagination is a separate set of fields. `PARTIAL` is defined. Drops, corruption, sampling other than `UNSAMPLED`, and unavailable evidence cannot be `COMPLETE`.

Evidence:

- `05-CORRELATION-AND-QUERY-CONTRACT.md` section 5.2. Every answer carries `declaredScope`, `matchingRecords`, `returnedRecords`, `hasMore`, `completeness`, `completenessReasons`, `integrityState`, `samplingState`, `dropState`, and `freshness`. The text says pagination fields are not completeness.
- `COMPLETE` requires a fully evaluated scope, `integrityState` `OK`, known store health, `samplingState` `UNSAMPLED`, `dropState` `NO_DROPS`, no corrupt required evidence, lifecycle `COMPLETE` on every run in scope, no coverage gap, no parent conflict, no producer-sequence conflict, and an integer `matchingRecords`. A later page of that same evaluated scope may also be `COMPLETE`. An untruncated page is not automatically `COMPLETE`.
- `PARTIAL` is an evaluated scope that produced an answer and carries at least one listed reason. A page that returns every stored row is still `PARTIAL` when a reason applies. Known drops are `PARTIAL`. Salvage is `PARTIAL` or `UNAVAILABLE`, never `COMPLETE`.
- `UNAVAILABLE` includes `STOPPED_PRESERVED` before salvage and a salvage that cannot trust its rows.
- Reason tokens include `DROPS_IN_SCOPE`, `SAMPLING_NOT_UNSAMPLED`, `REQUIRED_EVIDENCE_CORRUPT`, `INTEGRITY_NOT_OK`, and `REQUIRED_EVIDENCE_UNAVAILABLE`.
- Section 5.3 states the same cases as architecture tests. They are specified and not executed.
- The section 8 illustration keeps `hasMore: true` and `completeness: PARTIAL` together because of `DROPS_IN_SCOPE`.
- `03-OPERATIONAL-STORE-AND-PORTABLE-PROOF.md` section 5 says a proof copies the source envelope’s completeness and reasons and does not upgrade them. Manifest completeness uses the same four values.
- `06-SELF-OBSERVABILITY-AND-RELIABILITY.md` section 5 says a future sampling policy sets completeness to `PARTIAL` with `SAMPLING_NOT_UNSAMPLED`. Section 7 says run lifecycle is not query completeness, and unknown freshness does not by itself set completeness.

### Blocker 3 — Corrupt store — PASS

Disclosure is an external recovery envelope that does not depend on opening the failed database. The corrupt file is not replaced with an empty store. Salvage is `PARTIAL` or `UNAVAILABLE`. Original bytes stay. The first corruption state is `STOPPED_PRESERVED`.

Evidence:

- `04-SCHEMA-MIGRATION-AND-COMPATIBILITY.md` section 3 step 3: stop normal writes, preserve original bytes, do not unlink, do not rename a replacement over the corrupt file, do not write the disclosure into the corrupt file, write the external envelope. Issue location is `OPTICS`.
- Section 3.1 places the envelope at `optics/recovery/<safe-store-id>.recovery.json`, mode `0600`. If the store id cannot be read, the name is `store-id-unreadable`. The next command surfaces the envelope before customer rows. A missing envelope is not health; the command classifies the preserved file again and writes the envelope. An in-memory counter is not this record.
- The first state is `STOPPED_PRESERVED`. `READ_ONLY_SALVAGE` is entered only after that classification. Salvage answers are never `COMPLETE`. Replacement is an explicit workflow onto a new store id and does not overwrite or delete the original bytes.
- Section 3.2’s test plan requires the original bytes, the external envelope, salvage other than `COMPLETE`, and no empty replacement. The tests are specified and not executed.
- `07-THREAT-MODEL.md` case T10 uses the same first state, the same envelope, the same salvage limit, and the same refusal for newer-schema and weaker-writer cases. Case T11 says the recursion counter is not the corrupt-store record. Case T15 says a bounded read-only adapter must not present a corrupt file as `COMPLETE`.
- `06-SELF-OBSERVABILITY-AND-RELIABILITY.md` section 1 says that when the store cannot be opened, `integrity_state` comes from the external envelope, and the in-memory recursion stop is not that disclosure. Section 2’s store-corrupt row is `OPTICS`, with query completeness `PARTIAL` or `UNAVAILABLE`, never `COMPLETE`.
- `08-ARCHITECTURE-DECISION-PACK.md` section 18 says T10 matches A3.

The legacy JSON phrase “bounded read-only adapter” in A3 section 6 is the dual-read adapter for `~/.vantio/runs/*.json`. It is not permission to open a torn database as the operational store.

### Blocker 4 — Legacy origin and `session_id` — PASS

A legacy file keeps an allowlisted origin only with recognized producer provenance. Otherwise the reader disposition is `LEGACY_UNMARKED`, including a claimed `LOCAL_OBSERVATION` without that provenance. Destination `optics-demo.invalid` is `SIMULATED_DEMO`. Promotion of `LEGACY_UNMARKED` to `LOCAL_OBSERVATION` stays Founder decision 6. `session_id` has an acceptance rule and a required basis.

Evidence:

- `02-EVIDENCE-AND-PRIVACY-CONTRACT.md` section 2. Recognized producers are `node_interceptor`, `python_observe`, and `demo_command`, with the marker, producer, version charset, and allowlisted origin all required. The demo producer does not preserve `LOCAL_OBSERVATION`. The demo destination is `SIMULATED_DEMO` on read. Import writes `IMPORTED` and stores `original_evidence_origin` separately. No reader promotes evidence maturity.
- `04-SCHEMA-MIGRATION-AND-COMPATIBILITY.md` section 6 repeats that origin rule and adds the legacy `session_id` rule: keep the value only when it passes A1 section 11; basis `LEGACY_UNMARKED` unless a recorded basis is present and provenance is sufficient.
- `03-OPERATIONAL-STORE-AND-PORTABLE-PROOF.md` migration step 3 uses the same origin rule and leaves explicit promotion as Founder decision 6. Section 7 lists that promotion as unresolved.
- `08-ARCHITECTURE-DECISION-PACK.md` section 20: demo host maps to `SIMULATED_DEMO`; every other legacy file without recognized provenance stays `LEGACY_UNMARKED`. Section 35 item 6 and section 38 leave promotion unresolved.
- A1 section 11. `session_id` is optional, at most `OPTICS_SESSION_ID_MAX_BYTES` (80 UTF-8 bytes), NFC, with the listed character and secret rejections, and is not truncated. `session_id_basis` is required on the same record when `session_id` is present and absent when it is absent. The basis enum is `OPTICS_GENERATED`, `APPLICATION_SUPPLIED`, `CUSTOMER_SUPPLIED`, `IMPORTED_UNVERIFIED`, and `LEGACY_UNMARKED`. Invalid value or basis: omit both fields, increment `session_id_rejected`, do not store the rejected bytes. The field is not a metric label and is not inferred from time. Equality query returns the basis. A proof that includes the field includes the basis.

### Blocker 5 — Canonical proof — PASS

`proof.json` and `manifest.json` have one eligible byte form: Optics Canonical JSON profile `OPTICS_CANONICAL_JSON` version `1`. Pretty-printed JSON is not eligible. Compact JSON that breaks the profile is not eligible. HTML and Markdown are renderings and stay outside the hash. This council recomputed the golden vector.

Evidence:

- `03-OPERATIONAL-STORE-AND-PORTABLE-PROOF.md` section 5 and section 5.1. Fourteen byte rules cover encoding, object shape, whitespace, key order, duplicates, array order, NFC rejection without rewriting, escaping, integer range and spelling, literals, digests, and the timestamp field list. `manifest.json` records `canonicalization_scheme`, `canonicalization_scheme_version`, `proof_sha256`, and `proof_byte_length`. The verification sentence says to hash the stored `proof.json` bytes and not to reserialize before the byte check. The hash is not an attestation.
- Section 5.2 states 428 UTF-8 bytes and SHA-256 `a12adfa5f7b59aa3c4c8c98a52d36a50dcf861c3f8aea9bee7ee2eac70fd263a`.
- Recomputation at this review, over the exact canonical line in that section, with no trailing newline: length 428, SHA-256 `a12adfa5f7b59aa3c4c8c98a52d36a50dcf861c3f8aea9bee7ee2eac70fd263a`.
- One inserted space after the first colon: SHA-256 `2196636fef240005e8c489e097baa91618ea9ff2226be5c8bcb608f016dba2f9`, matching the stated failure digest.
- `schema_status` moved ahead of the other top-level keys, remaining keys left in canonical order: SHA-256 `3b2ce9d5736deded1a8af1a7e7bcf2d28a47c54a8a38cc59771d599718d9c21a`, matching the stated noncanonical digest.
- `08-ARCHITECTURE-DECISION-PACK.md` section 14 and section 39 (OF-43) name the same profile and exclude OTLP.

The vector is a profile example. It omits unassigned version fields. A full proof uses the same byte rules and the allowlisted keys. The stated checks are specified and were not an implementation test run.

### Blocker 6 — Child-process identity — PASS

`run_id`, `trace_id`, process ids, `producer_id`, and `producer_sequence` have separate scopes. Inherited trace context is asserted context. It is not observation proof and it does not mint `run_id`. Concurrent and child cases stay distinguishable.

Evidence:

- `05-CORRELATION-AND-QUERY-CONTRACT.md` section 1. `run_id` is one wrapped execution boundary. A child that is independently wrapped or attached receives a new `run_id`. `VANTIO_TRACE_ID` copies to `trace_id` with basis `ASSERTED_CONTEXT` when the syntax matches. That value does not mint `run_id` and does not make an unobserved child `LOCAL_OBSERVATION`. `parent_run_id` comes only from a valid `VANTIO_PARENT_RUN_ID`. Shared `trace_id`, shared `session_id`, and close timestamps do not set parenthood.
- `producer_id` is minted at process start, is not equal to `run_id`, and restarts on process restart. `producer_sequence` starts at 0 for that stream. `event_id` is `e.` plus the decimal byte length of `producer_id`, plus `producer_id`, plus the decimal sequence. `sequence` on an event equals `producer_sequence`.
- Async work and threads share `run_id` when they share the process install. `producer_sequence` stays monotonic for one `producer_id`. Several children with one `trace_id` stay distinguishable by `run_id`, `process_id`, `producer_id`, and `span_id`. A detached child gets no synthetic `LOCAL_OBSERVATION` row.
- Section 1.1 lists parent-plus-child, detached child, two children with one trace, restart, inherited trace without an observed child, conflicting parent, duplicate producer sequence, cross-process timestamp tie, malformed trace, and replay. Those tests are specified and not executed.
- Section 2 repeats that a child who does not inherit instrumentation is a coverage gap, not a child span and not `LOCAL_OBSERVATION`.
- `07-THREAT-MODEL.md` case T4 matches those scopes. `08-ARCHITECTURE-DECISION-PACK.md` sections 21–23 match them. A1 section 4 stores the same identity fields.

## Additional checks

### Option C

PASS. `STORE_OPTION_C: FOUNDER_RATIFIED_ARCHITECTURE_ONLY` is recorded in `00-PROGRAM-BOUNDARY.md`, `03-OPERATIONAL-STORE-AND-PORTABLE-PROOF.md` sections 4, 4 prerequisites, and 7, `04-SCHEMA-MIGRATION-AND-COMPATIBILITY.md` section 1’s introduction, `08-ARCHITECTURE-DECISION-PACK.md` sections 12 and 35, `ARCHITECTURE-MANIFEST.json`, and `TRACEABILITY-MATRIX.json`. The record ratifies embedded SQLite with WAL and an application-owned schema as architecture. It does not authorize a database, a Node binding, a schema implementation, a migration, record conversion, or a package change. The store is not implemented, tested, proved, or customer-validated. Rejected options A, B, D, and E stay rejected for the long-term index. This council did not reopen that selection.

### SQLite, binding, migration, UI, daemon, OTLP, alerting

PASS. `git diff --name-only d6b74d41808a43f251d6de46e1313625a025d16d..7db944d17c7f74706f08970b4908e92d0bf2d589` lists only paths under `docs/architecture/optics-foundation/`. No SQLite file is in the tree from this branch. The Node binding remains Founder decision 9. Alerting remains Founder decision 3. OTLP remains Founder decision 12. The local UI remains Founder decision 13. Those surfaces are named as future dependents or explicit non-goals.

### Founder decisions 2–13

PASS. They remain unresolved in `08-ARCHITECTURE-DECISION-PACK.md` sections 35 and 38 and in `ARCHITECTURE-MANIFEST.json` (`unresolved_founder_decisions`, 12 entries). Decision 1 is the architecture-only option C ratification. This council resolved none of items 2–13.

### OF-27, OF-33, OF-34, OF-43

PASS. Each row in `TRACEABILITY-MATRIX.json` is `ARCHITECTURE_DEFINED`, `evidence_tier` `UNSET`, `customer_validation` `UNSET`. That status matches the contracts:

| ID | Status in the matrix | Why that status holds |
| --- | --- | --- |
| OF-27 | `ARCHITECTURE_DEFINED` | A4 section 5.2 puts `freshness`, `completeness`, `completenessReasons`, and `integrityState` on one envelope, with `samplingState` and `dropState`. A5 section 7 keeps freshness independent and withholds `CURRENT` while its window is `NOT_SET`. Founder decision 10 stays open. |
| OF-33 | `ARCHITECTURE_DEFINED` | The application continues. `dropState` and `completeness` are on every default answer. Known drops in scope are `PARTIAL`. Product-health rows stay off the customer timeline. |
| OF-34 | `ARCHITECTURE_DEFINED` | A3 section 3.1 and T10 agree: external envelope, `STOPPED_PRESERVED` first, salvage never `COMPLETE`, original bytes kept, replacement explicit. |
| OF-43 | `ARCHITECTURE_DEFINED` | Profile `OPTICS_CANONICAL_JSON` version `1` is the only eligible byte form. The golden digest above was recomputed. HTML and Markdown stay renderings. OTLP stays unauthorized. |

None of the four is `IMPLEMENTED`, `SHIPPED`, `PROVED_EXTERNAL`, or `CUSTOMER_VALIDATED`. This council did not change their status values.

### Requirement counts

Not changed by this council. Recount of `TRACEABILITY-MATRIX.json` `requirements`: 52 rows. `ARCHITECTURE_DEFINED` 29, `TARGET_DESIGN` 20, `NEEDS_FOUNDER_DECISION` 3, `ARCHITECTURE_BLOCKED` 0. Sum 52. Every `evidence_tier` is `UNSET`. Every `customer_validation` is `UNSET`. No row uses a forbidden status. The matrix `status_counts` object matches that recount.

### Public and customer-validation claims

PASS. Audience on the pack is `INTERNAL_RESTRICTED`. Evidence tiers are unset. The proof limitation phrase is “Local export. Not an external attestation.” Option C’s ratification text says the store is not customer-validated.

### Manifest hashes at the reviewed tip

PASS for the tip under review. Before this council edited status annotations, all 12 `files_sha256` entries in `ARCHITECTURE-MANIFEST.json` matched the file bytes at `7db944d17c7f74706f08970b4908e92d0bf2d589`. This council commit updates the entries for files it edits. The manifest still does not store its own commit SHA.

## Gates

| Gate | Status after this council |
| --- | --- |
| 1 | Accepted as an inventory document. `01-CURRENT-STATE-INVENTORY.md` exists, the revision commit did not edit it, and the decision pack still marks Node/Python and docs/source conflicts as `CONFLICTING`. This council did not re-execute the inventory’s source-line citations. |
| 2 | Accepted as architecture. Issue location, origins, `session_id`, and the privacy invariants are specified. Not implemented. |
| 3 | Accepted as architecture. Option C is ratified as architecture only. One canonical proof profile is specified. No database exists. |
| 4 | Accepted as architecture. Unstable pre-1.0 identity, the external recovery envelope, and the legacy origin rule are specified. No migrator exists. |
| 5 | Accepted as architecture. Identity hierarchy, child process, query envelope, and cardinality are specified. No query engine exists. |
| 6 | Accepted as architecture. Product-health separation, fail-open, the A1 issue-location table, and `NOT_SET` budgets are specified. |
| 7 | Accepted as architecture. T1–T15 are specified, T10 matches the external envelope, and residual risk stays `UNSET`. |
| 8 | Closed. Not started. A8 is not started. |

Passing a document gate is not `UNIT_PROVED`, `INTEGRATION_PROVED`, `STRANGER_HOST_PROVED`, `PROVED_EXTERNAL`, or `CUSTOMER_VALIDATED`.

## Nonblocking notes

These notes do not reopen a blocker and do not resolve a Founder decision.

1. The A2 scorecard still gives option C a pass on some rows that are application policy, including “do not delete a corrupt file” and “allowlist before insert.” A2 section 3 says those cells are application rules and that ratification does not turn them into an engine proof. The scorecard was not rescored.
2. `producer_id` and `run_id` generation specify charset and maximum length. They do not specify entropy. A repeated `(producer_id, producer_sequence)` with a different identity stays visible as `PRODUCER_SEQUENCE`. The wrapper is not required to export `VANTIO_PARENT_RUN_ID`; when that variable is absent, `parent_run_id` is null, and `parent_process_id` remains the operating-system value when the runtime provides it.
3. The canonical timestamp field list does not name `time_start` or `time_end`. Those keys appear in the golden vector and in query scope. A given string still has one profile encoding. A scope-bound spelling outside the listed timestamp pattern is not rejected by rule 13.
4. NFC rejection does not name a Unicode version. The golden vector is ASCII. The profile rejects a non-NFC string and does not rewrite it.
5. `preserved_bytes_sha256` is defined for the raw preserved database file. WAL and SHM sidecars are named as store neighbors in A2 and are covered by T10’s “no automatic overwrite or delete,” and they are not separate fields on the envelope.
6. If the recovery directory itself cannot be written, A3 says a missing envelope is not health. The operator-visible text for that second failure is the same refusal, not a new empty store.
7. `dropState` `UNKNOWN` with otherwise healthy fields cannot be `COMPLETE`, because `COMPLETE` requires `NO_DROPS`. There is no separate reason token for unknown drops when store health is known. The completeness value for that case is `UNKNOWN` under the “cannot tell” rule.
8. A1 section 10’s shape illustration uses `event_id` `evt_example`. A4’s encoding is `e.` plus length, producer id, and sequence. The illustration is labeled non-executable.
9. A legacy file with destination `optics-demo.invalid` is `SIMULATED_DEMO` in A1, A2, A3, and decision-pack section 20. The earlier missing-origin sentence names `LEGACY_UNMARKED` as the default reader state. The demo-destination sentence is the specific assignment. Neither assignment is `LOCAL_OBSERVATION`. Promotion stays unresolved.
10. Windows ACL detail stays Founder decision 8. The Node SQLite binding stays Founder decision 9. This council ran no Windows, Linux, or offline product test.
11. Every `NFR-*` target stays `NOT_SET`. A future store call on process exit still has no numeric shutdown budget, so an implementation Force cannot invent a timeout from this pack.
12. `01-CURRENT-STATE-INVENTORY.md` was not edited by the revision and was not line-audited again here.

## Scope attestations

| Stop | Result |
| --- | --- |
| Reviewed tip | `7db944d17c7f74706f08970b4908e92d0bf2d589` |
| Council work | This report, plus status lines in the program boundary, A1–A6 headers, the decision pack, the gate table, the manifest, and the traceability note |
| No product code | CLI and Python sources are unchanged on this branch relative to starting main |
| No SQLite implementation | No database, migration, Node binding, or record conversion |
| No UI, daemon, OTLP, or alerting | Not started |
| Founder decisions 2–13 | Left unresolved |
| No public or customer-validation claim | None added |
| Gate 8 and A8 | Closed and not started |
| PR | Left draft. Not merged |

## Stop

A8 is not started. No implementation task is filed. Draft PR #55 stays draft.
