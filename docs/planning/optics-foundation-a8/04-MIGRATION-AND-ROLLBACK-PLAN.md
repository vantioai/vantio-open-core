# Migration and rollback plan

Audience: INTERNAL_RESTRICTED

Hard rule: a source rollback must leave recorded evidence readable. An older reader must not treat an unknown field, a missing origin, or a failed write as a successful provider call.

No migration runs in this planning force. No database is created. Legacy files are not converted.

## 1. Rollback classes

| Class | Meaning |
| --- | --- |
| Source | Remove or revert the code. Customer files stay |
| Package | Revert a published CLI or Python version. CLI 0.3.24 is the frozen floor for the current Node path |
| Data | Customer JSON or a future store file changes |
| Schema | `user_version`, row `schema_version`, or `privacy_generation` changes |
| Configuration | Retention limits, telemetry flags, or a future config file |

## 2. Package rollback

| Package | Source | Package publish | Data | Schema | Configuration | Evidence after rollback | Imported data | Proof | Windows / Linux / offline |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PKG-01 | Delete the private contract package | No customer publish in Slice 1 | None | None | None | Current JSON remains | Untouched. Import is not in Slice 1 | Untouched | Pure functions. Offline. OS-independent |
| PKG-02 | Restore the previous writer | Future CLI and future Python revert independently | New files may contain new keys | Still `unstable-pre-1.0` | None | Dual-read keeps old and new files readable. Unknown keys are ignored, not success | Not this package | Renderers that skip unknown keys still render | Writer path differs by OS only in process id and path separators. No network |
| PKG-03 | Stop emitting health records | Revert with the writer | Health rows may exist later | Health rows use the same schema identity | None | Missing health becomes unknown drop state, which is not query `COMPLETE` | Unaffected | Proofs omit health payloads | Offline |
| PKG-04 | Revert the verifier | Library revert | Proof files stay | Proof profile version 1 stays on the file | None | Old proofs verify under the profile or fail closed. Failure is not a pass | Proofs are not imported as `LOCAL_OBSERVATION` | Bytes stay. Compaction must not rewrite them | Byte check is OS-independent. File mode `0600` is owner-only intent. Windows ACL is decision 8 |
| PKG-05 | Delete the memory adapter | No customer data release | None | None | None | No customer evidence change | None | None | Offline |
| PKG-06 | Reverse the selection before PKG-07 ships | No dependency is added by the selection document | None until PKG-07 | None | None | N/A | N/A | N/A | Selection evidence must cover Windows, Linux, macOS, WSL before it is shippable |
| PKG-07 | Revert the writer to JSON-only | Future CLI and Python that understand the file refuse or stay read-only when `user_version` is newer | Store file stays. Legacy JSON stays. No empty replacement | No down-migration | None | Newer schema is refused. Older software still reads legacy JSON | Not copied yet | Proofs stay outside the store file | WAL and SHM sidecars stay beside the file. Offline. Owner-only create. Symlink escape refuses the write |
| PKG-08 | Remove the migrate command | Command revert | Originals stay. A failed copy rolls the transaction back | Copy writes the current store version inside a transaction | Explicit invocation only | Legacy files remain the readable floor. `LEGACY_UNMARKED` is not reread as `LOCAL_OBSERVATION` | Quarantine stays `IMPORTED` with `original_evidence_origin` preserved | A preservation claim requires PKG-04. Rollback does not regenerate proofs to hide a bad copy | `VANTIO_HOME` is the root for future readers. Offline. Corrupt files are left in place on every OS |
| PKG-09 | Revert propagation | Writer revert | New ids may be on new files | None beyond the record | Environment variables already defined (`VANTIO_TRACE_ID`, `VANTIO_PARENT_RUN_ID`) | Old files keep one `trace_id`, mapped to legacy `run_id`. Missing parent stays null | Inherited context is not observation proof | Proofs copy stored ids and bases | Child-process inheritance must be rechecked per OS at implementation time |
| PKG-10 | Disable the command | Command revert | Query does not mutate rows | None | Saved views, if added later, store the request object | Rows remain. An answer without completeness is not rendered as `COMPLETE` | Excluded from the default scope | Proof export copies completeness | Offline. Limit 500 is the structural cap while NFR numbers are `NOT_SET` |
| PKG-11 | Disable prune and restore commands | Command revert | A completed prune has removed listed rows. Rollback does not guess them back | None | Limits unset means unbounded | Proofs written before the prune stay | Deleted imported rows stay deleted | Proof bytes unchanged | Backup files are owner-only. Restore uses a new store id and leaves original bytes |
| PKG-12 | Revert to today’s exit write | Writer revert | Lifecycle labels may be on new rows | None | None | Missing flush stays unlabeled absence or `ABANDONED` / `INTERRUPTED` when those labels were written. It is not rewritten to `COMPLETE` | Unaffected | Partial export is not renamed into place | Kill and signal tests differ by OS. Offline. No invented timeout |
| PKG-13 | Remove the command | Future CLI revert | None if the command is read-only | None | None | Stored evidence unchanged | Unaffected | Unaffected | Follows the CLI OS matrix |
| PKG-14 | Stop the UI process | Separate release revert | UI has no mutation API, so no data rollback | None | Bind address if a charter sets one | Store unchanged | Unaffected | Unaffected | Loopback. Decision 13 is still open, so this row is a future constraint |
| PKG-15 | Disable trend commands | Command revert | Totals are computed, not a second evidence store | None | Scope filters | Excluded origins stay excluded. Missing origin is not added into the total as local observation | Excluded from the default trend | Rollups are not proofs | Offline |
| PKG-16 | Disable the emitter | Separate release revert | Alerts are not evidence rows | None | Mode is decision 3, still open | Evidence unchanged | Unaffected | Unaffected | Depends on the mode. No daemon in the safe default |
| PKG-17 | Disable the exporter | Separate release revert | No evidence rewrite | None | Decision 12, still open | A queued payload that fails the denylist is dropped, not sent after rollback | Exporters must not relabel `IMPORTED` as local | Proof files remain the local export | Offline default. A network exporter does not exist in this plan |

## 3. Unknown fields and success

Readers and rollback builds follow these rules:

- An unknown key is skipped or, on the contract write path, omitted before persistence.
- Skipping an unknown key does not set `application_status` to `SUCCESS` and does not set `issue_location` to `NONE`.
- `optics_status` `SUCCESS` is used when an observation row was stored. A reader that does not see a row does not invent that token for the provider outcome.
- HTTP status, when present, remains the application outcome. Issue location does not replace it.
- `LEGACY_UNMARKED` is a reader disposition for a missing or unproven origin. Rollback software keeps that disposition.
- Display token `PARTIAL`, lifecycle `PARTIAL`, and query completeness `PARTIAL` are not interchangeable. Rollback must not collapse them into `SUCCESS`.

## 4. Imported data

Import is PKG-08 and later, not Slice 1.

- Import writes `evidence_origin` `IMPORTED`.
- `original_evidence_origin` is the allowlisted origin found in the bytes, or `LEGACY_UNMARKED`.
- Import does not write `LOCAL_OBSERVATION`.
- Rollback of the importer leaves quarantine rows in place. It does not promote them.
- A proof of an imported scope keeps origin `IMPORTED` and the source completeness.

## 5. Proof compatibility

- Eligible bytes are `OPTICS_CANONICAL_JSON` version 1.
- Verification hashes the stored `proof.json` bytes. It does not reserialize before the byte check.
- Semantic regeneration passes only after the profile is applied again.
- HTML and Markdown stay outside the hash.
- The manifest limitation phrase stays “Local export. Not an external attestation.”
- Store rollback, prune, and compaction do not rewrite an existing proof.
- A privacy-weaker writer refuses to re-export fields it does not know how to strip.

## 6. What Slice 1 rolls back

Slice 1, under option B, has source rollback only. There is no package publish, no data rewrite, no schema, and no configuration change. Current CLI and Python behavior remain the behavior after rollback because they were never switched.

## 7. Release-unit classes

| Class | Packages |
| --- | --- |
| Source-only until a later cutover | PKG-01, PKG-05, PKG-06’s decision record |
| Record-format-affecting once wired | PKG-02, PKG-03, PKG-09 |
| Persistent-data-affecting | PKG-07, PKG-08, PKG-11, PKG-12 when recovery files or lifecycle rows are stored |
| Customer-output-affecting | PKG-02, PKG-04, PKG-10, PKG-13, PKG-14, PKG-15, PKG-16, PKG-17 |
| Privacy-critical | PKG-01, PKG-02, PKG-03, PKG-04, PKG-07, PKG-08, PKG-11, PKG-12, PKG-17 |
| Migration-critical | PKG-07, PKG-08, with PKG-04 required for a preservation claim |
| Independently releasable | Slice 1 private package; future Python writer; future CLI writer; proof library; coverage command; UI; alerting; network export |
| Required to ship together | Selected Node binding with PKG-07; PKG-12 with the release that makes SQLite the default writer; Node and Python fixture results for any claim that the two languages match; PKG-04 with any PKG-08 build that claims preservation |

CLI 0.3.24 is not in any of these release units.
