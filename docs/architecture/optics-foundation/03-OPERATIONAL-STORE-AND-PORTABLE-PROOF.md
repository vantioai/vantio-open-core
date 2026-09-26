# A2 — Operational store and portable proof

Classification: `OPTICS_FOUNDATION_A2_DECISION_READY`

Revision: `OPTICS_FOUNDATION_ARCHITECTURE_REVISION_READY_FOR_RECOUNCIL`. Fresh council `bc-5bb719b6-65bf-522c-a9b9-f3a9a96ef08b` accepted Gate 3 as architecture on 2026-09-26 (`OPTICS_FOUNDATION_ARCHITECTURE_COUNCIL_PASSED`). Gate 8 stays closed. This line is not implementation. `STORE_OPTION_C: FOUNDER_RATIFIED_ARCHITECTURE_ONLY`.

Audience: INTERNAL_RESTRICTED

The attached Founder Force says to evaluate options A–E and does not name the five options. This document closes that set. If a later Founder note meant a different five, that correction is a Founder decision and would reopen A2. Until then, the set below is the set that was evaluated.

No SQLite file is created by this Force. No migration is executed.

`STORE_OPTION_C: FOUNDER_RATIFIED_ARCHITECTURE_ONLY`. Option C is the ratified operational-store architecture. Ratification does not authorize creating a database, choosing a Node SQLite binding, implementing a schema, running a migration, converting records, or changing a package. The store is not implemented, tested, proved, or customer-validated.

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

Cells that pass because of an application policy, including “do not delete a corrupt file” and “allowlist before insert,” are application rules. Ratification of option C does not turn those cells into an engine proof. The scorecard is unchanged by ratification.

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

**Option C is ratified architecture: embedded SQLite with WAL and an application-owned schema. Portable proof stays a separate JSON artifact. `STORE_OPTION_C: FOUNDER_RATIFIED_ARCHITECTURE_ONLY`.**

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
- If the file cannot be opened, or integrity fails, the application continues. Normal writes stop. The database bytes stay in place. Disclosure is the external recovery envelope in A3, not a row inside the failed file, and not an empty replacement.
- Python `sqlite3` in the standard library is the expected Python mechanism. The Node binding is an implementation choice and is not selected here.
- Encryption at rest is not selected. Feasibility stays open.

### Migration path from today’s files

1. Leave `~/.vantio/runs/*.json` untouched.
2. A future explicit migrate operation, which this Force does not create, copies allowlisted fields into the store inside a transaction, after a file backup of the database if one already exists.
3. Origin on copy follows A1. A recognized producer and version with sufficient provenance keep an allowlisted origin. Anything else is stored as `LEGACY_UNMARKED`. Demo host `optics-demo.invalid` is `SIMULATED_DEMO`. The copy does not promote evidence maturity. An explicit customer promote of `LEGACY_UNMARKED` to `LOCAL_OBSERVATION` remains Founder decision 6 and is not the default.
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
- Founder ratification of option C is recorded as `STORE_OPTION_C: FOUNDER_RATIFIED_ARCHITECTURE_ONLY`. That record is not an implementation order.

### Required evidence tier before any implementation is called done

Not assigned now. The closing tier for an implementation Force should be at least `INTEGRATION_PROVED` on Node and Python against the same file, plus `STRANGER_HOST_PROVED` before any external claim. `CUSTOMER_VALIDATED` is a further tier and is not implied. This producer document assigns none of those tiers.

## 5. Portable proof decision

Selection: **B. Optics Canonical JSON profile `OPTICS_CANONICAL_JSON` version `1`.**

The portable proof package is two files: `proof.json` and `manifest.json`. Both files are serialized only with this profile. Pretty-printed JSON is not eligible. A compact document that breaks the profile is not eligible. HTML and Markdown are renderings. They are outside the hash.

`proof.json` does not contain its own hash. `manifest.json` records the SHA-256 and byte length of the exact `proof.json` bytes. The hash detects accidental change. It does not prove who wrote the file, and it is not an attestation.

### 5.1 Profile `OPTICS_CANONICAL_JSON` version `1`

Scheme identity, recorded on the manifest: `canonicalization_scheme` = `OPTICS_CANONICAL_JSON`, `canonicalization_scheme_version` = `1`.

Byte rules:

1. Encoding is UTF-8. A leading BOM (EF BB BF) is a canonicalization failure.
2. The top-level value is one JSON object.
3. No insignificant whitespace. No space or newline between tokens.
4. The canonical byte sequence has no trailing newline and no trailing carriage return. The last byte is the closing `}` of the top-level object.
5. Object keys are compared as sequences of UTF-16 code units of the unescaped key, lexicographic, shorter prefix first. Keys are then emitted in that order.
6. Duplicate keys are a canonicalization failure.
7. Array order is the semantic order. Arrays are not sorted.
8. Strings must already be Unicode Normalization Form C. The canonicalizer rejects a string that is not NFC. It does not rewrite the string.
9. String escaping, applied to keys and to values: `"` becomes `\"`; `\` becomes `\\`; each code point U+0000 through U+001F becomes `\u00xx` with four lowercase hex digits; every other code point is emitted as its UTF-8 bytes. `/` is not escaped. Non-ASCII characters are not written as `\u` escapes.
10. Numbers are integers in the closed range `-9007199254740991` through `9007199254740991`. Serialization is base-10 with no leading zero, no plus sign, no decimal point, and no exponent. Zero is `0`. Negative zero, non-integers, `NaN`, and `Infinity` are canonicalization failures. The profile does not coerce them.
11. Literals are `true`, `false`, and `null`.
12. Binary values are forbidden. A digest field is a lowercase hex string matching `^[0-9a-f]{64}$` when it is a SHA-256 field. Customer payloads are not base64-encoded into the proof.
13. Timestamp fields, when present and not null, match `^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z$` and are a real UTC calendar value with seconds `00` through `59`. The fields are `started_at`, `ended_at`, `generated_at`, `observed_at`, `created_at`, `export_time`, `failure_timestamp`, and `last_known_successful_integrity_check`. The canonicalizer does not convert offsets. `+00:00` is a failure.
14. Any other JSON type is a canonicalization failure.

`proof.json` allowlist: `schema_status`, `proof_schema_version`, `declared_scope`, `filters`, `completeness`, `completeness_reasons`, `evidence_origins`, `sampling_posture`, `event_count`, `events`. Each event contains only A1 observation fields selected for the export. Completeness uses the A4 values. A proof whose source envelope was not `COMPLETE` records that same completeness and the same reasons. It does not upgrade them.

`manifest.json` allowlist:

- `record_type`: `proof_manifest`
- `schema_status`: `unstable-pre-1.0`
- `proof_schema_version`
- `canonicalization_scheme`: `OPTICS_CANONICAL_JSON`
- `canonicalization_scheme_version`: `1`
- `proof_sha256`: lowercase hex SHA-256 of the exact `proof.json` bytes
- `proof_byte_length`: integer byte length of those bytes
- `export_time`: canonical UTC timestamp
- `producer_version`: producer name and version
- `declared_scope`
- `filters`
- `completeness`
- `completeness_reasons`
- `evidence_origins`
- `sampling_posture`
- `redaction_policy_identity`: `ALLOWLIST_ONLY`
- `source_schema_versions`: operational schema version and proof schema version, or null when unassigned
- `verification_instructions`: the fixed sentence “Hash the proof.json bytes as stored. Compare to proof_sha256. Do not reserialize before the byte check. Semantic regeneration passes only after OPTICS_CANONICAL_JSON version 1.”
- `verifier_version`
- `limitation`: the fixed phrase “Local export. Not an external attestation.”

Manifest completeness uses `COMPLETE`, `PARTIAL`, `UNKNOWN`, or `UNAVAILABLE`, with reasons. The hash is not an attestation.

`vantio prove` today writes a rendering into the current directory without `0600`. A future proof writer creates both files mode `0600` and refuses to follow a symlink outside the destination the customer named. That behavior is not implemented here.

Export failure: if the write is partial, the destination is not renamed into place. An existing proof path is not overwritten unless the customer passed an explicit overwrite flag. That flag does not exist today and is not added by this Force.

### 5.2 Golden vector

Profile vector, not an executed test, and not a full proof document. A full `proof.json` uses these same byte rules and only the allowlisted keys. `proof_schema_version` is present on a full proof when an implementation Force assigns it. This vector omits unassigned version fields so the byte check has one exact input. Input object, before serialization:

`NON_EXECUTABLE_ARCHITECTURE_EXAMPLE`

```json
{
  "schema_status": "unstable-pre-1.0",
  "completeness": "COMPLETE",
  "completeness_reasons": [],
  "sampling_posture": "UNSAMPLED",
  "declared_scope": {
    "origin": "LOCAL_OBSERVATION",
    "time_start": "2026-09-26T00:00:00.000Z",
    "time_end": "2026-09-26T16:00:00.000Z"
  },
  "evidence_origins": ["LOCAL_OBSERVATION"],
  "event_count": 1,
  "events": [
    {
      "application_status": "SUCCESS",
      "http_status": 200,
      "issue_location": "NONE",
      "started_at": "2026-09-26T16:00:00.000Z"
    }
  ]
}
```

Exact canonical UTF-8 bytes, 428 bytes, no BOM, no trailing newline:

```text
{"completeness":"COMPLETE","completeness_reasons":[],"declared_scope":{"origin":"LOCAL_OBSERVATION","time_end":"2026-09-26T16:00:00.000Z","time_start":"2026-09-26T00:00:00.000Z"},"event_count":1,"events":[{"application_status":"SUCCESS","http_status":200,"issue_location":"NONE","started_at":"2026-09-26T16:00:00.000Z"}],"evidence_origins":["LOCAL_OBSERVATION"],"sampling_posture":"UNSAMPLED","schema_status":"unstable-pre-1.0"}
```

Expected SHA-256: `a12adfa5f7b59aa3c4c8c98a52d36a50dcf861c3f8aea9bee7ee2eac70fd263a`.

Required checks, specified and not run:

| Check | Result |
| --- | --- |
| Exact canonical bytes | Verification pass. Byte length 428. SHA-256 above |
| Same bytes with one inserted space after the first colon | Verification fail. SHA-256 `2196636fef240005e8c489e097baa91618ea9ff2226be5c8bcb608f016dba2f9` |
| Same members with `schema_status` moved ahead of the other top-level keys | Noncanonical. Byte verification fail. SHA-256 `3b2ce9d5736deded1a8af1a7e7bcf2d28a47c54a8a38cc59771d599718d9c21a` |
| Semantic regeneration | Pass only after the altered documents are serialized again with `OPTICS_CANONICAL_JSON` version `1` |

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

- Node SQLite binding. Not chosen. Ratification of option C does not choose it.
- At-rest encryption. Not chosen.
- Explicit promote of `LEGACY_UNMARKED` to `LOCAL_OBSERVATION`. Not chosen.
- Exact busy-timeout and page-size. Numeric targets `NOT_SET`.

Option C ratification is not an unresolved question. It is `STORE_OPTION_C: FOUNDER_RATIFIED_ARCHITECTURE_ONLY`.

## 8. Non-executable illustration

`NON_EXECUTABLE_ARCHITECTURE_EXAMPLE`

```text
evidence root/
  optics/store.sqlite                 operational store (future, not created here)
  optics/recovery/<id>.recovery.json  external recovery envelope (future)
  optics/proofs/<id>/proof.json       canonical proof bytes (future)
  optics/proofs/<id>/manifest.json    manifest of those bytes (future)
  runs/<legacy>.json                  legacy files, retained until the customer deletes them
  telemetry-id                        product telemetry, not evidence
```
