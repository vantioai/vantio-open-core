# A2 — Operational store and portable proof

Classification: `OPTICS_FOUNDATION_A2_DECISION_READY`

Audience: INTERNAL_RESTRICTED

The attached Founder Force says to evaluate options A–E and does not name the five options. This document closes that set. If a later Founder note meant a different five, that correction is a Founder decision and would reopen A2. Until then, the set below is the set that was evaluated.

No SQLite file is created by this Force. No migration is executed.

## 1. Two artifacts

**Operational store.** Mutable local infrastructure for search, tail, diff, retention accounting, integrity, and diagnostics. It is not a proof.

**Portable proof.** A separate bounded artifact the customer can copy. It is a snapshot of allowlisted fields plus a manifest. Retention and compaction of the operational store must not change a proof that was already written.

Words that must not be used for the proof, because they are not established: tamper-proof, WORM, notarized, certified, regulator-approved, externally attested.

## 2. Options

| Id | Option | Summary |
| --- | --- | --- |
| A | Per-run JSON files | Today’s `~/.vantio/runs/<trace>.json` remains the operational store and the proof |
| B | Append-only JSONL segments plus a sidecar index | Files only. No embedded engine |
| C | Embedded SQLite, WAL, application-owned schema | One local database file. JSON proof is a separate export. No raw SQL API |
| D | Embedded analytical engine (DuckDB or equivalent) | Columnar local database as the operational store |
| E | Out-of-process store | Local daemon or networked database |

## 3. Comparison criteria

Each option is scored against the roadmap and the A1 contract. “Pass” means the option can meet the criterion without contradicting a hard stop. It is not a claim that the criterion is implemented.

| Criterion | A | B | C | D | E |
| --- | --- | --- | --- | --- | --- |
| Search, tail, and diff without scanning every historical file | Fail | Partial | Pass | Pass | Pass |
| Transactional migration and integrity check | Fail | Fail | Pass | Partial | Partial |
| Crash consistency short of a silent empty replacement | Fail | Partial | Pass | Pass | Partial |
| Corrupt file is refused, not replaced | Policy only | Policy only | Pass, if the file is not deleted | Pass, if the file is not deleted | Partial |
| No daemon | Pass | Pass | Pass | Pass | Fail |
| Node and Python writers in-process | Pass today | Pass | Pass. Python has stdlib `sqlite3`. Node needs a binding chosen later | Pass only with a native library on both | Pass only if both talk to the daemon |
| JSON remains the portable proof, separate from the mutable index | Fail | Pass | Pass | Pass | Pass |
| Allowlist enforced before insert | Possible | Possible | Pass | Pass | Possible |
| Bounded query without exposing an engine language | Pass only by not having an engine | Pass | Pass if the application API is the only interface | Weak. The engine invites ad hoc SQL | Weak |
| Retention default unbounded, no silent delete | Pass, because nothing deletes | Pass if implemented | Pass if implemented | Pass if implemented | Pass if implemented |
| Unix mode on one evidence object | Partial today | Partial | Pass | Pass | Socket permissions instead |
| Fail-open for the application if the store cannot open | Pass today, by swallowing errors | Pass | Pass | Pass | Fail when the daemon is down, unless a second fail-open path exists |
| Fits a frozen CLI and an unsealed Python SDK as a later change, not this Force | No code now | No code now | No code now | No code now | No code now |
| Does not expand Optics into enforcement | Pass | Pass | Pass | Pass | Pass |

## 4. Recommendation

**Option C. Embedded SQLite as the operational store. Portable proof stays a separate JSON artifact.**

Reasons tied to the criteria:

- The inventory shows search, tail, diff, and discover parse every JSON file, and the roadmap treats that as the scaling gap (OF-01).
- Section 9 of the roadmap requires transactional migrations, integrity checks, and no silent empty-database recreation. SQLite transactions and a single file that is left in place when corrupt meet that more directly than JSONL plus a hand-rolled index.
- A daemon (option E) conflicts with the roadmap rule not to add a daemon silently, and it conflicts with fail-open if the daemon must be up for the application to proceed.
- DuckDB (option D) can query, and it is a poor fit for a small transactional row log shared by Node and Python without a second native stack. It also makes “no arbitrary SQL” harder to keep.
- JSONL (option B) avoids a native dependency and still lacks a transactional migration story. It remains a valid export format, not the operational store.
- Per-run JSON (option A) stays the legacy reader input and the proof shape. It does not remain the long-term index.

### Rejected options

- **A rejected as the long-term operational store.** It remains the legacy on-disk format and the proof encoding. Keeping it as the index conflicts with the roadmap’s own “incompatible parallel work” note under operational storage.
- **B rejected as the operational store.** Useful as a future export (JSONL is already named in OF-23-25). Not sufficient for transactional migration.
- **D rejected.** Extra engine, dual native packaging, and a wider SQL surface than this product needs.
- **E rejected.** Daemon and network stores are out of scope for the default local, fail-open, in-process observer.

### Assumptions

- One OS user owns the evidence directory. Multi-user isolation is filesystem permissions, not row-level grants.
- The database file lives under the evidence root, recommended path `~/.vantio/optics/store.sqlite` plus `-wal` and `-shm` sidecars. `VANTIO_HOME` is the override root for both writers and readers. The current CLI reader ignores `VANTIO_HOME`; a future implementation must stop doing that. This pack does not patch the CLI.
- WAL mode is on. Readers use the application query API from A4, not a SQL prompt.
- If the file cannot be opened, or integrity fails, the application continues, product-health records the failure in a side diagnostic that is not a customer AI call, and the database file is not deleted or replaced.
- Python `sqlite3` in the standard library is the expected Python mechanism. The Node binding is an implementation choice and is not selected here.
- Encryption at rest is not selected. Feasibility stays open.

### Migration path from today’s files

1. Leave `~/.vantio/runs/*.json` untouched.
2. A future explicit migrate operation, which this Force does not create, copies allowlisted fields into the store inside a transaction, after a file backup of the database if one already exists.
3. Demo host `optics-demo.invalid` is stored as `SIMULATED_DEMO`. Every other legacy file is stored as `LEGACY_UNMARKED` reader state, not stamped `LOCAL_OBSERVATION`, unless the customer runs an explicit promote step. That promote step is `NEEDS_FOUNDER_DECISION` and is not designed as a default.
4. Originals stay on disk until the customer deletes them. Migration is not deletion.
5. A failed migration rolls the transaction back and leaves the previous database file. It does not create a new empty file over the failed one.

### Rollback

- Application rollback to a build that only understands per-run JSON continues to read the legacy files, which were not deleted.
- A build that understands the store and sees a newer `schema_version` than it can write opens read-only or refuses. It does not rewrite the file to an older schema.
- Rollback onto a privacy-weaker allowlist is a refuse, per A3.

### Proof and privacy boundaries

- Proof export reads allowlisted fields through the query API.
- The proof does not include telemetry ids, prohibited fields, or annotation text unless a separate export flag, default off, is added later. Default proof excludes annotations.
- Compaction and retention do not rewrite an existing proof file.

### Prerequisites

- A1 allowlist.
- A3 schema version and the corrupt-store rule.
- Founder ratification of option C. This recommendation is ready for that ratification. It is not an implementation order.

### Required evidence tier before any implementation is called done

Not assigned now. The closing tier for an implementation Force should be at least `INTEGRATION_PROVED` on Node and Python against the same file, plus `STRANGER_HOST_PROVED` before any external claim. `CUSTOMER_VALIDATED` is a further tier and is not implied. This producer document assigns none of those tiers.

## 5. Portable proof decision

Canonical proof is one JSON document, pretty-printed or compact, with a sibling or embedded manifest. HTML and Markdown remain renderings. The hash is over the canonical JSON bytes, not over the HTML.

Manifest allowlist:

- `record_type`: `proof_manifest`
- `schema_status`: `unstable-pre-1.0`
- `schema_version`
- `generated_at` UTC
- `time_range`
- `run_ids` included
- `origin_counts`
- `completeness`: `COMPLETE` or `PARTIAL` or `UNKNOWN`
- `sampling`: `UNSAMPLED`
- `redaction_posture`: `ALLOWLIST_ONLY`
- `event_count`
- `canonical_sha256`
- `producer_name` and `producer_version`
- `limitation`: fixed phrase that the file is a local export, not an external attestation

The hash is SHA-256 of the canonical proof body with the hash field empty, then stored in the manifest. It detects accidental change. It does not prove who wrote the file.

`vantio prove` today writes a rendering into the current directory without `0600`. A future proof writer creates the file mode `0600` and refuses to follow a symlink outside the destination the customer named. That behavior is not implemented here.

Export failure: if the write is partial, the destination is not renamed into place. An existing proof path is not overwritten unless the customer passed an explicit overwrite flag. That flag does not exist today and is not added by this Force.

## 6. Retention and deletion

Decision:

- Default retention is unbounded.
- Optics never deletes evidence because a limit was left unset.
- A future customer limit (`max-age`, `max-size`) is configuration, not a schema rewrite.
- A future prune is two steps: a dry-run that writes a deletion manifest (what would be removed, counts, bytes, origin breakdown), then a second explicit invocation that deletes only rows listed in that manifest and only if the manifest hash still matches.
- Dry-run output is product-health plus a manifest file. It is not a customer AI call.
- Deletion does not edit previously exported proofs.
- This Force does not add `vantio config` or `vantio prune`.

Selective deletion of one run, when it exists later, uses the same manifest rule.

No compliance, retention-law, or “certified deletion” claim is made.

## 7. Unresolved questions

- Founder ratification of option C versus A–E as closed here.
- Node SQLite binding. Not chosen.
- At-rest encryption. Not chosen.
- Explicit promote of `LEGACY_UNMARKED` to `LOCAL_OBSERVATION`. Not chosen.
- Exact busy-timeout and page-size. Numeric targets `NOT_SET`.

## 8. Non-executable illustration

`NON_EXECUTABLE_ARCHITECTURE_EXAMPLE`

```text
evidence root/
  optics/store.sqlite          operational store (future)
  optics/proofs/<id>.json      portable proof (future)
  runs/<legacy>.json           legacy files, retained until the customer deletes them
  telemetry-id                 product telemetry, not evidence
```
