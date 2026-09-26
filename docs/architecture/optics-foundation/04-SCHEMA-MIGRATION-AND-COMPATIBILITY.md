# A3 — Schema, migration, and compatibility

Classification: `OPTICS_FOUNDATION_A3_CONTRACT_READY`

Audience: INTERNAL_RESTRICTED

Every schema named here is unstable and pre-1.0. `schema_status` is the constant `unstable-pre-1.0`. This Force does not declare a stable schema, a deprecation window, or a v1.

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

## 3. Migration hard rule

A corrupt, truncated, or incompatible store must not be replaced with an empty store.

Required behavior for a future implementation:

1. Detect before write: open, read `user_version`, run the integrity check the engine provides.
2. If the file is missing, a new store may be created only when the path does not already exist, including when the path is a symlink to somewhere else. “Missing” means `ENOENT` on the final path after refusing to follow a symlink that leaves the evidence root.
3. If the file exists and is corrupt, stop. Leave the bytes. Surface issue location `OPTICS` and lifecycle `INTERRUPTED` or a product-health integrity failure. Do not unlink the file. Do not create `store.sqlite.new` and rename it over the corrupt file.
4. If the file’s version is newer than this build, open read-only when the build knows the rows are still allowlist-safe, otherwise refuse. Never write.
5. If a migration is interrupted, the next open resumes from the last committed version or stops on the integrity failure. It does not start over by deleting the file.
6. Pre-migration backup is a copy of the database file beside it, mode `0600`, before the first migration statement. Backup failure aborts migration. The backup is not a proof and is not called an attestation.
7. Dry-run migration prints the version step and does not open a write transaction. This Force does not add the command.

Node and Python use the same migrator steps. A one-sided writer that “repairs” the file by recreating it is a violation of this rule.

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
- Origin: `optics-demo.invalid` becomes `SIMULATED_DEMO`. Otherwise `LEGACY_UNMARKED`.
- Corrupt JSON: report it, skip that file, do not delete it. One corrupt legacy file must not hide the others. This removes today’s split where some commands exit 1 and the MCP skips silently, by making “skip and count” the single rule. The count is product-health, not a customer call.
- `prove --from` on an arbitrary path is an import attempt. It quarantines as `IMPORTED` if a future import exists. Until then, rendering a `--from` file must label the output `LEGACY_UNMARKED` or `IMPORTED` and must not say it was observed on this machine unless the path is inside the evidence root and passes the legacy marker.

`VANTIO_HOME`, when set, is the evidence root for readers and writers. The current CLI reader uses only `homedir()`. Compatibility work includes that correction in a future Force. This document does not patch `vantio.js`.

## 7. Compatibility tests a future Force must have

Specified, not implemented:

- Legacy Node envelope and legacy Python envelope both map without persisting prohibited keys.
- A truncated JSON file and a truncated SQLite file are left in place.
- A store with `user_version` ahead of the build is not rewritten.
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
  if integrity fails: stop, keep bytes, product_health integrity_state=FAILED
  if user_version > build.max: read-only or refuse
  if user_version < build.writable: backup, then transactional migrate
  if migrate fails: rollback, keep backup, do not create a replacement file
```
