# Store Option C verification

Audience: INTERNAL_RESTRICTED

Producer classification: `OPTICS_STORE_OPTION_C_VERIFIED_PLAN_READY_FOR_COUNCIL`

Verified on commit `587f3b94d47ea958f91d3a99125cd55931d995f1`. This file records checks. It does not create a database.

## 1. Ratified record

`STORE_OPTION_C: FOUNDER_RATIFIED_ARCHITECTURE_ONLY`.

The record is present in:

- `docs/architecture/optics-foundation/00-PROGRAM-BOUNDARY.md`
- `docs/architecture/optics-foundation/03-OPERATIONAL-STORE-AND-PORTABLE-PROOF.md` sections 4, the prerequisites under that section, and section 7
- `docs/architecture/optics-foundation/04-SCHEMA-MIGRATION-AND-COMPATIBILITY.md` section 1
- `docs/architecture/optics-foundation/08-ARCHITECTURE-DECISION-PACK.md` sections 12 and 35
- `docs/architecture/optics-foundation/09-IMPLEMENTATION-GATES.md` Gate 3
- `docs/architecture/optics-foundation/ARCHITECTURE-MANIFEST.json` field `store_option_c`
- `docs/architecture/optics-foundation/TRACEABILITY-MATRIX.json`

The fresh architecture council `bc-5bb719b6-65bf-522c-a9b9-f3a9a96ef08b` accepted Gate 3 as architecture on 2026-09-26 (`OPTICS_FOUNDATION_ARCHITECTURE_COUNCIL_PASSED`). That acceptance is an architecture result. Gate 8 stays closed.

Option C, as ratified, is embedded SQLite with WAL and an application-owned schema. Portable proof stays a separate JSON artifact under profile `OPTICS_CANONICAL_JSON` version `1`. Callers do not receive a raw SQL API.

Rejected for the long-term index, and left rejected by this plan:

| Id | Option |
| --- | --- |
| A | Per-run JSON files as the long-term operational store |
| B | Append-only JSONL plus a sidecar index as the operational store |
| D | An embedded analytical engine |
| E | An out-of-process store |

Option A remains the legacy reader input and the proof shape. Option B remains a named export possibility. Neither becomes the index.

## 2. Checks run on this commit

| Check | Result |
| --- | --- |
| `store_option_c` equals `FOUNDER_RATIFIED_ARCHITECTURE_ONLY` | Pass |
| Decision 1 in the decision pack is that same record | Pass |
| Decisions 2–13 remain unresolved | Pass |
| Gate 3 text says no database exists | Pass |
| Gate 8 text says closed and not started | Pass |
| `schema_status` remains `unstable-pre-1.0` | Pass |
| Repository contains no `store.sqlite` and no `*.sqlite` file | Pass |
| No `package.json` depends on `sqlite3`, `better-sqlite`, or `node:sqlite` | Pass |
| `@vantio/cli` version is `0.3.24` | Pass |
| CLI, Python SDK, and Node SDK do not import the evidence contract or the vocabulary package | Pass |
| Evidence-contract metadata lists `sqlite` under `excluded_from_slice` | Pass |
| Vocabulary isolation test bans a `sqlite` import | Pass |
| Golden proof vector is 428 UTF-8 bytes, SHA-256 `a12adfa5f7b59aa3c4c8c98a52d36a50dcf861c3f8aea9bee7ee2eac70fd263a` | Pass. Recomputed from the canonical line in A2 section 5.2. The vector is a proof-profile check. It is not a store |

No check assigns `UNIT_PROVED`, `INTEGRATION_PROVED`, `STRANGER_HOST_PROVED`, `PROVED_EXTERNAL`, or `CUSTOMER_VALIDATED` to the store. The store is not implemented, tested, proved, or customer-validated.

## 3. Exact constraints the ratification already states

These constraints bind a later implementation force. This packet does not execute them. Citing them is not permission to start.

### 3.1 Engine and file

- One local database file. Recommended path `~/.vantio/optics/store.sqlite`, plus `-wal` and `-shm` sidecars, under the evidence root.
- `VANTIO_HOME` is the override root for future writers and readers. The current CLI reader ignores `VANTIO_HOME`. A future implementation has to honor it. This plan does not patch the CLI.
- WAL mode is on in the architecture. Readers use the A4 application query API.
- One OS user owns the evidence directory. Isolation is filesystem permissions.
- Unix create mode for the store, the proof files, the backup, and the recovery envelope is `0600` / owner-only. Windows ACL details stay Founder decision 8.
- At-rest encryption is not selected. Founder decision 5.
- Busy-timeout and page-size are `NOT_SET`. Founder decision 4. No roadmap example number is adopted.
- Python’s expected mechanism is the standard-library `sqlite3` module. That expectation is not code on this commit.
- The Node binding is not selected. Founder decision 9. This plan names no candidate library.

### 3.2 Schema identity

- `schema_status` is `unstable-pre-1.0`. This plan does not declare a stable schema or a deprecation window.
- `operational_schema_version` lives on SQLite `user_version` and on each row. `proof_schema_version` lives on the proof manifest. Both start unassigned. An implementation force sets them to a positive integer in the same change that writes a migrator. This architecture uses `0` only to mean unassigned.
- Legacy `schema_version: 2` on today’s JSON files is not reused as `user_version`.
- `privacy_generation` starts at 1 on a future first allowlist write. This plan does not perform that write.
- `BEGIN IMMEDIATE`, or the binding’s equivalent, is architecture language for a future migrator. It is not a command this plan runs.

### 3.3 Open, corruption, and migration

- A missing file may be created only on `ENOENT` of the final path, after refusing a symlink that leaves the evidence root.
- A corrupt, truncated, or incompatible file is not replaced with an empty file, not unlinked, and not overwritten by a `store.sqlite.new` rename.
- Normal writes stop. Original bytes stay. Issue location is `OPTICS`. The application call continues.
- Disclosure is the external recovery envelope at `optics/recovery/<safe-store-id>.recovery.json`, mode `0600`. The first corruption state is `STOPPED_PRESERVED`. Salvage is `PARTIAL` or `UNAVAILABLE`, and it is never query `COMPLETE`.
- A newer `user_version` is not written. The build refuses or stays read-only. Remediation code `NEWER_SCHEMA_REFUSED`.
- A privacy-weaker writer refuses to write. Remediation code `WEAKER_WRITER_REFUSED`. Software rollback does not down-migrate the file.
- An interrupted migration resumes from the last commit or stops. It does not delete the file.
- Pre-migration backup is a `0600` copy beside the file. Backup failure aborts migration. The backup is not restored automatically and is not a proof.
- Legacy `~/.vantio/runs/*.json` stays in place. Copy into the store is a future explicit operation. Migration is not deletion. Copy does not promote evidence maturity. Demo host `optics-demo.invalid` reads as `SIMULATED_DEMO`. Anything without recognized provenance is `LEGACY_UNMARKED`. Customer promote stays Founder decision 6.

### 3.4 Proof, retention, and privacy

- The operational store is mutable local infrastructure for search, tail, diff, retention accounting, integrity, and diagnostics. It is not a proof.
- Proof export reads allowlisted fields through the query API. Default proof excludes annotations. Compaction and retention do not rewrite an existing proof file.
- Words that do not apply to the proof: tamper-proof, WORM, notarized, certified, regulator-approved, externally attested.
- Default retention is unbounded. Optics does not delete evidence because a limit was left unset. A future prune is a dry-run manifest, then a second explicit invocation. This plan adds neither `vantio config` nor `vantio prune`.
- Allowlist enforcement happens before insert. Prohibited fields, including prompts, completions, raw bodies, and credentials, stay off the store and off the recovery envelope.

### 3.5 Fail-open and product boundary

- If the store cannot open, the application continues, normal writes stop, and the bytes stay.
- A future store call on the application request path must not take an unbounded lock. The timeout number is `NOT_SET`. Today’s writers flush at exit. Both facts stand. This plan adds no call on that path.
- The store write is not an observed customer destination.
- Optics observation does not block, redact, or cap the application call. Those branches are Phantom Engine behavior and stay outside the store contract.

## 4. Isolation rule

Any future database sits behind the `O2` application store contract (`PKG-05`).

- Callers use put, get, and the A4 query request. A caller-supplied SQL string is rejected.
- `O6` is the only place a Node binding may be selected, and only after a Founder decision. `O2` does not select one.
- `O7` is the only place a schema and a file may be created, and only after `O2`, `O6`, and `O12`, in a later force. This packet does not open `O7`.
- An in-memory reference adapter, when a later force writes it, is the test double for the contract. It is not a database file.
- Portable proof (`O4`) stays a pair of JSON files. It is not a table inside the store.

The scorecard in A2 gives some Option C cells a pass because of an application policy, including “do not delete a corrupt file” and “allowlist before insert.” Those cells are application rules. Ratification does not turn them into an engine proof.

## 5. What remains unresolved

Decision 1 is closed as architecture only. These stay open, with the safe behavior already recorded in the decision pack:

| # | Topic | Safe behavior while open |
| --- | --- | --- |
| 2 | Usage and cost metadata | Off the allowlist |
| 3 | Alerting delivery mode | No alerter and no daemon |
| 4 | Numeric `NFR-*` targets | `NOT_SET` |
| 5 | At-rest encryption | Not selected |
| 6 | Promote `LEGACY_UNMARKED` to `LOCAL_OBSERVATION` | No promote |
| 7 | Seventh annotation origin | `annotation_role` `CUSTOMER_ANNOTATION` |
| 8 | Windows ACL beyond owner-only intent | Owner-only intent. No invented ACL |
| 9 | Node SQLite binding | Unselected. No dependency |
| 10 | Freshness window for `CURRENT` | `CURRENT` is not emitted. Freshness stays `UNKNOWN` |
| 11 | Persisted machine hostname | Prohibited |
| 12 | OTLP or SIEM export | Unauthorized |
| 13 | Local UI charter | UI stays closed |

## 6. Authorization result

`STORE_OPTION_C_VERIFIED_ARCHITECTURE_ONLY`

The verification authorizes this planning packet. It does not authorize a database, a binding, a schema, a migration, record conversion, a package change, or a production implementation.
