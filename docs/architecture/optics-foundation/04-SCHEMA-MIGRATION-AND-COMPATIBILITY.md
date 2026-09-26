# A3 — Schema, migration, and compatibility

Classification: `OPTICS_FOUNDATION_A3_CONTRACT_READY`

Revision: `OPTICS_FOUNDATION_ARCHITECTURE_REVISION_READY_FOR_RECOUNCIL`. Gate 4 stays reopened until a fresh council passes. This line is not a council pass.

Audience: INTERNAL_RESTRICTED

Every schema named here is unstable and pre-1.0. `schema_status` is the constant `unstable-pre-1.0`. This Force does not declare a stable schema, a deprecation window, or a v1.

SQLite `user_version` and `BEGIN IMMEDIATE` in this document describe the ratified option C architecture. `STORE_OPTION_C: FOUNDER_RATIFIED_ARCHITECTURE_ONLY`. They do not authorize creating a database, choosing a Node binding, or running a migration.

## 1. Schema identity

Two integers exist so the operational store and the proof can move on different clocks:

- `operational_schema_version` on the store user-version (SQLite `user_version`) and on each row.
- `proof_schema_version` on the proof manifest.

Both start unassigned. An implementation Force sets them to a positive integer in the same change that writes the migrator. This architecture uses `0` only in examples to mean “not assigned.”

`vantio_run_log: "1"` remains the legacy file marker. It is not the store schema.

Current writers already emit `schema_version: 2` with different envelopes (inventory findings 1.2, 2.2, 15.1). That number is the legacy JSON marker. It is not reused as `operational_schema_version`, so a reader cannot confuse a legacy file with a migrated store.

## 2. Objects that carry schema identity

| Object | Marker | Reader rule |
| --- | --- | --- |
| Legacy JSON run file | `vantio_run_log == "1"` and legacy `schema_version` | Read-only. No write-back |
| Operational store | `user_version` plus row `schema_version` | Read and write only when the version is in the build’s writable set |
| Proof JSON | `proof_schema_version` and `schema_status` | Render or verify the hash. Do not import as `LOCAL_OBSERVATION` |
| CLI stdout JSON | `schema_status: unstable-pre-1.0` as today | Display contract. May change without notice |
| Product telemetry body | existing allowlist, no schema version today | Unchanged by this pack |

## 3. Migration and corrupt-store rule

A corrupt, truncated, or incompatible store must not be replaced with an empty store. The corrupt file is not opened as a healthy operational store.

Required behavior for a future implementation:

1. Detect before write: attempt to open, read `user_version` when the engine can, and run the integrity check the engine provides.
2. If the file is missing, a new store may be created only when the path does not already exist, including when the path is a symlink to somewhere else. “Missing” means `ENOENT` on the final path after refusing to follow a symlink that leaves the evidence root.
3. If the file exists and is corrupt: stop normal writes; preserve the original bytes; do not unlink the file; do not create `store.sqlite.new` and rename it over the corrupt file; do not write the disclosure into the corrupt file. Write the external recovery envelope in section 3.1. Issue location of the failure is `OPTICS`.
4. If the file’s version is newer than this build, do not write. Disclose the refusal through the same external envelope, with `recovery_state` `RECOVERY_REQUIRED` and `remediation_code` `NEWER_SCHEMA_REFUSED`. A read of rows is allowed only when the build knows the rows are still allowlist-safe. That read is not a salvage of a corrupt file.
5. If a migration is interrupted, the next open resumes from the last committed version or stops on the integrity failure. It does not start over by deleting the file. Migration failure uses the external envelope. `remediation_code` is `MIGRATION_FAILED`.
6. A privacy-weaker writer refuses to write and records that refusal in the external envelope. `remediation_code` is `WEAKER_WRITER_REFUSED`. It does not rewrite the file.
7. Pre-migration backup is a copy of the database file beside it, mode `0600`, before the first migration statement. Backup failure aborts migration. The backup is not a proof and is not called an attestation. The envelope records backup availability. The backup is not restored automatically.
8. Dry-run migration prints the version step and does not open a write transaction. This Force does not add the command.

Node and Python use the same migrator steps. A one-sided writer that “repairs” the file by recreating it is a violation of this rule.

### 3.1 External recovery envelope

The envelope does not depend on the failed store. It is a file under the evidence root at `optics/recovery/<safe-store-id>.recovery.json`, mode `0600`, owner-only. `<safe-store-id>` is an opaque id minted when a healthy store is created and kept in `optics/store.id` (that sidecar contains only the id). When the id cannot be read, the file name uses `store-id-unreadable`. The envelope does not contain a filesystem path, a username, or a hostname.

The next command surfaces this envelope before any customer rows. If the envelope is missing, the command classifies the preserved file again and writes the envelope. A missing envelope does not mean the store is healthy. An in-memory counter is not this record.

Recovery states:

| State | Meaning |
| --- | --- |
| `STOPPED_PRESERVED` | Corruption classified. Normal writes stopped. Original bytes preserved. Envelope written. |
| `READ_ONLY_SALVAGE` | After classification, a bounded read-only salvage is in progress. It does not write into the corrupt file. |
| `RECOVERY_REQUIRED` | An explicit recovery workflow is required before normal writes resume. Also used for newer-schema and weaker-writer refusal. |
| `RECOVERED_TO_NEW_STORE` | An explicit workflow created a replacement store with a new id. Original bytes still exist. |
| `RECOVERY_FAILED` | An explicit workflow failed. Original bytes still exist. |

On corruption the first state is `STOPPED_PRESERVED`. Bounded read-only salvage happens only after that classification, and only by entering `READ_ONLY_SALVAGE`. Salvage answers are `PARTIAL` or `UNAVAILABLE`. They are never `COMPLETE`. Salvage is not “open the torn file as the operational database.”

Replacement and restore are an explicit workflow. This Force does not add the command. The workflow preserves the original bytes, does not overwrite them, and does not delete them. Success sets `RECOVERED_TO_NEW_STORE` and records `replacement_store_id`. Failure sets `RECOVERY_FAILED`. Provenance is the envelope itself: preserved-byte hash, backup availability, and the replacement id when one exists.

Envelope allowlist, and nothing else:

- `record_type`: `recovery_envelope`
- `schema_status`: `unstable-pre-1.0`
- `safe_store_id`
- `schema_version` if readable, otherwise null
- `product_version`
- `failure_timestamp` canonical UTC
- `integrity_result`: `FAILED`, `UNREADABLE`, or `OK` when the file is readable but writes are refused
- `recovery_state` one of the five states
- `last_known_successful_integrity_check` timestamp or null
- `remediation_code` token
- `backup_availability`: `AVAILABLE`, `ABSENT`, or `UNKNOWN`
- `preserved_bytes_sha256` lowercase hex of the raw preserved file when the hash can be computed without parsing the file as a database, otherwise null
- `replacement_store_id` or null

The envelope must not include prompts, completions, raw bodies, credentials, arbitrary exception contents, or arbitrary customer payloads.

A future support bundle may attach this envelope and the A4 query envelope. It may not attach the prohibited fields above. No support bundle is created here. A future UI may display `recovery_state` and must not present salvage as complete. No UI is created here.

Query `integrityState` comes from this envelope whenever the store file cannot be opened as healthy. A product-health row inside a store that failed to open is not the source of that field.

### 3.2 Architecture test plan — corrupt store

Specified, not executed. No evidence tier is assigned.

- A torn file stops normal writes, keeps its original bytes, and gains an external envelope in `STOPPED_PRESERVED`. No empty file replaces it.
- The envelope contains only the allowlist. A fixture that would place a prompt, body, credential, or exception string in the envelope is omitted.
- The next command prints the recovery state without treating the torn file as a healthy store.
- Salvage after classification returns `PARTIAL` or `UNAVAILABLE`, never `COMPLETE`.
- An explicit recovery writes a new store id and leaves the corrupt bytes in place.
- A failed explicit recovery leaves `RECOVERY_FAILED` and the original bytes.

## 4. Privacy and rollback

- Each migration is additive or narrowing. A migration that needs a prohibited field is invalid.
- Rollback of the software to an older build does not down-migrate the file.
- A build whose allowlist is weaker than the stored privacy generation refuses to write and refuses to re-export fields the older build would not know how to strip. Privacy generation is an integer `privacy_generation` on the store, starting at 1 for the first implementation of the A1 allowlist. This pack sets the meaning, not the code.
- Mixed CLI and Python versions: the newer writer may migrate forward inside a transaction. The older writer must refuse or stay read-only. Today neither writer checks `schema_version`. That is the gap OF-23-30 records.

## 5. Node and Python compatibility

Target envelope is the A1 catalog, not the union of today’s extra keys.

| Today | Target rule |
| --- | --- |
| Node omits `schema_status` on the file; Python sets it | Both set `schema_status` |
| Python sets `workflow: sight_loop`; Node omits `workflow` | `workflow` is not an observation field. Sight Loop remains a product name in docs, not a stored record key |
| Node `guessProvider` substring; Python catalog | `provider_id` only from catalog, regional pattern, or local Ollama. Otherwise `unknown` with `provider_confidence: NONE` |
| Node stores `pid` and `ppid`; Python does not | Both store `process_id` and `parent_process_id` when the runtime provides them, else null |
| Node writes zero-call files; Python does not | An attached process writes a `run_envelope` even when `call_count` is 0, lifecycle `COMPLETE`, application status `NOT_OBSERVED` |
| Python persists human outcome sentences on the call | Those sentences are `derived_diagnostic` records or a view |
| Node `est_spend_usd` | Not in the allowlist. Dropped. Usage and cost stay `NEEDS_FOUNDER_DECISION` |
| Enforcement `action` values | Not Optics observation rows |

Readers of legacy files accept both envelopes without crashing and without treating them as the new schema.

## 6. Legacy `~/.vantio/runs/*.json`

Three options were considered.

| Option | Behavior | Decision |
| --- | --- | --- |
| L1 | Ignore legacy files once the store exists | Rejected. It hides evidence the customer already has |
| L2 | Dual-read forever, no copy into the store | Accepted as the minimum. Legacy files stay readable by a bounded read-only adapter |
| L3 | Explicit copy into the store, originals kept | Accepted as an additional future operation. Not the default on first open |

Adapter rules:

- Require `vantio_run_log == "1"` and a JSON object.
- Map known keys through the allowlist. Drop unknown keys, including any body-shaped key.
- Do not write the mapped row back over the JSON file.
- Origin follows A1. Preserve an allowlisted origin only with recognized producer, version, and sufficient provenance. Otherwise `LEGACY_UNMARKED`, including a file that claims `LOCAL_OBSERVATION` without that provenance. Destination `optics-demo.invalid` is `SIMULATED_DEMO`. The adapter does not promote evidence maturity.
- A legacy `session_id` is kept only when it passes A1 section 11. Its basis is `LEGACY_UNMARKED` unless a recorded basis is present and provenance is sufficient. Invalid session values are omitted.
- Corrupt JSON: report it, skip that file, do not delete it. One corrupt legacy file must not hide the others. This removes today’s split where some commands exit 1 and the MCP skips silently, by making “skip and count” the single rule. The count is product-health, not a customer call.
- `prove --from` on an arbitrary path is an import attempt. It quarantines as `IMPORTED` if a future import exists. Until then, rendering a `--from` file must label the output `LEGACY_UNMARKED` or `IMPORTED` and must not say it was observed on this machine unless the path is inside the evidence root and passes the legacy marker.

`VANTIO_HOME`, when set, is the evidence root for readers and writers. The current CLI reader uses only `homedir()`. Compatibility work includes that correction in a future Force. This document does not patch `vantio.js`.

## 7. Compatibility tests a future Force must have

Specified, not implemented:

- Legacy Node envelope and legacy Python envelope both map without persisting prohibited keys.
- A truncated JSON file and a truncated SQLite file are left in place, and the SQLite case writes the external recovery envelope.
- A legacy file that claims `LOCAL_OBSERVATION` without recognized provenance is read as `LEGACY_UNMARKED`.
- A legacy file with recognized provenance keeps its allowlisted origin and is not upgraded further.
- An import stores `IMPORTED` plus `original_evidence_origin` and does not become `LOCAL_OBSERVATION`.
- A store with `user_version` ahead of the build is not rewritten. The refusal is on the external envelope.
- A privacy generation ahead of the build is not exported by the older build.
- Node and Python alternate writes under one file lock (`BEGIN IMMEDIATE` or equivalent) without dropping a committed row.
- Demo file does not enter a trend query.

No evidence tier is assigned to those tests.

## 8. Deprecation

OF-16 asks for a deprecation policy once JSON schema leaves unstable pre-1.0. It has not left. There is nothing to deprecate. The policy text is: no field in this pack is stable, and no removal schedule is published.

## 9. Non-executable illustration

`NON_EXECUTABLE_ARCHITECTURE_EXAMPLE`

```text
open(store):
  if path is a symlink leaving the evidence root: refuse
  if ENOENT: create new store at privacy_generation 1
  if integrity fails: STOPPED_PRESERVED, keep bytes, write external recovery envelope, do not write inside the corrupt file
  if user_version > build.max: RECOVERY_REQUIRED, remediation NEWER_SCHEMA_REFUSED, no rewrite
  if user_version < build.writable: backup, then transactional migrate
  if migrate fails: rollback, keep backup, envelope MIGRATION_FAILED, do not create a replacement file
  salvage only after classification: READ_ONLY_SALVAGE, completeness PARTIAL or UNAVAILABLE
```
