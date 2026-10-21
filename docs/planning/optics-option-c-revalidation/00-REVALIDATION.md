# Option C revalidation

Audience: INTERNAL_RESTRICTED

Producer role: revalidation producer only. This agent does not sit the independent council, does not self-assign a council pass, and does not create a database.

Producer identity: Cursor cloud agent `bc-6c7884b7-0d3c-5c54-84f7-8a5e7bca41fe`, model Grok 4.7.

Producer URL: https://cursor.com/agents/bc-6c7884b7-0d3c-5c54-84f7-8a5e7bca41fe

Producer classification: `OPTICS_OPTION_C_REVALIDATED_READY_FOR_COUNCIL`

That classification means the merged Option C decision was re-read on current main and remains binding. It is a handoff to a separate council. It is not a council verdict, not a Gate 8 opening, and not a store implementation.

Revalidated base: `89f95099d0dce463307eb75d78e7fcf2ef99feb2` (`Merge pull request #83 from vantioai/cursor/pe-ws4-vocabulary-binding-f9f5`).

## 1. Boundary

This force re-reads the merged Option C plan and the architecture sentences that plan verified. It writes this packet and the tests under `tests/optics-option-c-revalidation/`.

This force leaves these surfaces untouched:

- Product code, package manifests, tests outside this packet, workflows, tags, and registries.
- `docs/planning/optics-production/` and `docs/architecture/optics-foundation/`.
- A database file, a Node binding, a schema, WAL activation, a migration, and record conversion.
- CLI `@vantio/cli` `0.3.24`, Python `vantio-agent-sdk` `3.1.0`, and Node SDK `@vantio/agent-sdk` `0.2.4`.
- Gate 8 in `docs/architecture/optics-foundation/09-IMPLEMENTATION-GATES.md`.
- Founder decisions 2–13.
- Live customer migration.

`schema_status` stays `unstable-pre-1.0`.

## 2. Decision citation

The Founder brief names the prior merge `OPTICS_STORE_OPTION_C_PLAN_MERGED_NO_IMPLEMENTATION`. On main that merge is pull request #69.

| Item | Value |
| --- | --- |
| Merge | `79b53e0e29df047aabb1863b62609ffd7b4dcff7` |
| Merge subject | Merge pull request #69 from `vantioai/cursor/optics-store-option-c-plan-c633` |
| Plan tip | `f6e90c148ec07b9e0d019dc89e852284d26a7cbf` |
| Plan subject | Record the Optics Option C verification and the O1–O20 dependency plan. |
| In-repo producer classification | `OPTICS_STORE_OPTION_C_VERIFIED_PLAN_READY_FOR_COUNCIL` |
| In-file council status | `PENDING_COUNCIL` in `docs/planning/optics-production/10-INDEPENDENT-COUNCIL-REPORT.md` |
| Control-plane status | `MERGED_PLAN_COUNCIL_PENDING` in `docs/programs/production-readiness/WORKSTREAM-REGISTRY.json` workstream `WS2` |
| Ancestor of this base | Yes. `79b53e0e29df047aabb1863b62609ffd7b4dcff7` is an ancestor of `89f95099d0dce463307eb75d78e7fcf2ef99feb2` |

The engine in this packet is the engine named in the ratified text.

`docs/architecture/optics-foundation/08-ARCHITECTURE-DECISION-PACK.md` section 12:

`STORE_OPTION_C: FOUNDER_RATIFIED_ARCHITECTURE_ONLY`. Embedded SQLite, WAL, application-owned schema, path `~/.vantio/optics/store.sqlite` under the evidence root. No file is created now. Ratification does not authorize a database, a Node binding, a migration, record conversion, or a package change. The store is not implemented, tested, proved, or customer-validated.

`docs/architecture/optics-foundation/03-OPERATIONAL-STORE-AND-PORTABLE-PROOF.md` section 4:

Option C is ratified architecture: embedded SQLite with WAL and an application-owned schema. Portable proof stays a separate JSON artifact. `STORE_OPTION_C: FOUNDER_RATIFIED_ARCHITECTURE_ONLY`.

The same file’s assumptions name Python’s expected mechanism as the standard-library `sqlite3` module and leave the Node binding unselected. Section 7 leaves the Node binding, at-rest encryption, `LEGACY_UNMARKED` promotion, busy-timeout, and page-size unresolved. `docs/architecture/optics-foundation/08-ARCHITECTURE-DECISION-PACK.md` section 35 item 1 records the same ratification. Item 9 records “Node SQLite binding. Not selected.” Items 2–13 stay unresolved.

`docs/architecture/optics-foundation/ARCHITECTURE-MANIFEST.json` field `store_option_c` is `FOUNDER_RATIFIED_ARCHITECTURE_ONLY`.

`docs/planning/optics-production/01-STORE-OPTION-C-VERIFICATION.md` section 6 records `STORE_OPTION_C_VERIFIED_ARCHITECTURE_ONLY`. That verification authorizes the planning packet. It leaves the database, the binding, the schema, the migration, record conversion, and the package change unauthorized.

Rejected options stay rejected for the long-term index: A per-run JSON, B JSONL plus a sidecar index, D an embedded analytical engine, E an out-of-process store. A remains the legacy reader input and the proof shape. B remains a named export possibility.

## 3. Checks on this base

| Check | Result |
| --- | --- |
| Every `input_sha256` in `docs/planning/optics-production/PRODUCTION-MANIFEST.json` matches the current file | Pass. 14 files |
| Every `files_sha256` in that manifest matches the current planning file | Pass. 7 files |
| `dependency_graph_sha256` matches `dependency_graph.edges` in `PACKAGES.json` | Pass. `c9702d2dbb4f75f0f9c668efc144a080935e0d950ceb107d12d3455b8f9e66ce` |
| `git diff 587f3b94d47ea958f91d3a99125cd55931d995f1..89f95099d0dce463307eb75d78e7fcf2ef99feb2 -- docs/architecture/optics-foundation` | Empty |
| `git diff 79b53e0e29df047aabb1863b62609ffd7b4dcff7..89f95099d0dce463307eb75d78e7fcf2ef99feb2 -- docs/planning/optics-production` | Empty |
| `store_option_c` | `FOUNDER_RATIFIED_ARCHITECTURE_ONLY` |
| Decisions 2–13 | Unresolved |
| Gate 3 | Architecture acceptance. The gate text says no database exists |
| Gate 8 | `Closed. Not started` |
| `schema_status` | `unstable-pre-1.0` |
| Working tree `*.sqlite` | None |
| `package.json` and `pyproject.toml` dependency on `sqlite3`, `better-sqlite3`, `better-sqlite`, or `node:sqlite` | None |
| `@vantio/cli` | `0.3.24` |
| Golden proof vector | 428 UTF-8 bytes, SHA-256 `a12adfa5f7b59aa3c4c8c98a52d36a50dcf861c3f8aea9bee7ee2eac70fd263a`, recomputed from the canonical line in A2 section 5.2. The vector is a proof-profile check |
| Evidence tiers on O1–O20 | `UNSET` |
| `O7` status in `PACKAGES.json` | `NOT_AUTHORIZED` |

No check assigns `UNIT_PROVED`, `INTEGRATION_PROVED`, `STRANGER_HOST_PROVED`, `PROVED_EXTERNAL`, or `CUSTOMER_VALIDATED` to the store.

## 4. Confirmation

The merged decision remains binding. Amendment is `NOT_REQUIRED`.

The classification would have been `OPTICS_OPTION_C_AMENDMENT_REQUIRED_READY_FOR_COUNCIL` if any of these had been true on this base: the cited decision bytes had changed, a tracked SQLite file or a SQLite dependency had appeared, a Node binding had been selected, Gate 8’s architecture text had opened for a store, options A, B, D, or E had been restored as the long-term index, or `@vantio/cli` had left `0.3.24`. None of those is true.

## 5. Deltas that leave the decision in place

Commits after `79b53e0e29df047aabb1863b62609ffd7b4dcff7` advanced main to `89f95099d0dce463307eb75d78e7fcf2ef99feb2`. The Option C planning files and the architecture inputs hashed by that plan are byte-identical to the plan’s record.

| Later fact | Why the decision stays |
| --- | --- |
| PKG-02 Unit B merge `4e50dd9` (`56ec23c`), Unit C merge `2ada719` (`74313b5`), Unit F merge `4b1b85a` (`2c31764`) | Inert adapter and reader source. `packages/optics-record-reader/src/boundary.cjs` lists `sqlite` among inactive writer flags. The Unit F adversarial test passes `{ migrate: true, sqlite: true }` and requires the missing file to stay absent. The catalog sentence in the merged plan that names Unit A is the snapshot at plan time. |
| WS4 catalog merge `5227470` (`c1de025`) | `docs/planning/shared-health-vocabulary/00-BOUNDARY.md` keeps Optics store writes and O7 closed. |
| Phantom health binding merge `89f9509` (`dcddd37`) | Binds the health packet to that catalog. It adds no store file. |
| Production-plan council file | Still `PENDING_COUNCIL`. This revalidation leaves that file in place and does not record a pass. |
| PKG-01 private-package notes | Those notes limit a Gate 8 sentence to the private contract. The architecture gate file hashed by the plan still says Gate 8 is closed. |

## 6. O7 entry criteria

`docs/planning/optics-production/04-DEPENDENCY-ORDER.md` section 3 is the path before any database file. `PACKAGES.json` gives `O7` predecessors `O2`, `O6`, and `O12`. Founder decision 9 blocks `O6`, then `O7`.

| Step | Criterion | State on this base |
| --- | --- | --- |
| 1 | `PKG-01` allowlist present as a private contract, unwired from live writers | Present and unwired. `@vantio/optics-evidence-contract` `0.0.0-unstable-pre-1.0` |
| 2 | `O2` store contract accepted, including an in-memory adapter and a rejected SQL string | Unmet. Status `CONSTRAINT_VERIFIED_NOT_AUTHORIZED`. No contract module is in this tree |
| 3 | `O1` health model accepted as code | Unmet. Status `DESIGN_SKETCH_ONLY` |
| 4 | `O11` structural caps, then `O12` fail-open | Unmet. Both `NOT_AUTHORIZED` |
| 5 | Founder decision 9, then an `O6` selection record | Unmet. Decision 9 unresolved. `O6` is `NEEDS_FOUNDER_DECISION`. This packet names no library |
| 6 | A later force opens `O7` | Unmet. `O7` is `NOT_AUTHORIZED`. This force is step 6’s predecessor check, and it stops before the file |

A pass of this revalidation leaves steps 2 through 6 unmet. Creating `store.sqlite` before those steps would break the merged plan.

These constraints bind the force that eventually opens `O7`. They are already written in `01-STORE-OPTION-C-VERIFICATION.md` section 3. This packet repeats the entry list:

- One local file at the recommended path `~/.vantio/optics/store.sqlite`, plus `-wal` and `-shm`, under the evidence root. `VANTIO_HOME` is the override for a future reader. The current CLI reader is unchanged.
- WAL mode. Callers use put, get, and the A4 query request. A caller-supplied SQL string is rejected.
- The Node binding arrives only through decision 9 and `O6`. The Python mechanism named in A2 is the standard-library `sqlite3` module, and that module is unused on this base.
- `schema_status` stays `unstable-pre-1.0`. `operational_schema_version` stays unassigned until the change that writes a migrator. Legacy JSON `schema_version` 2 is a different number.
- `privacy_generation` starts at 1 on a future first allowlist write.
- Create only on `ENOENT` of the final path, after refusing a symlink that leaves the evidence root. Mode `0600` for the store, the proof files, the backup, and the recovery envelope.
- A corrupt, truncated, or incompatible file stays in place. Disclosure is the external recovery envelope. Salvage is `PARTIAL` or `UNAVAILABLE`.
- A newer `user_version` is refused. A privacy-weaker writer is refused. Software rollback does not down-migrate the file.
- Legacy `~/.vantio/runs/*.json` stays in place. Copy into the store is `O8`, after `O7` and `O4`.
- Default retention stays unbounded. Allowlist enforcement happens before insert.
- If the store cannot open, the application continues and normal writes stop.
- Busy-timeout, page-size, at-rest encryption, and Windows ACL detail stay at the safe behavior in decision-pack items 4, 5, and 8.
- Evidence tiers stay `UNSET`.

## 7. Path notes for a later O7 force

A later O7 force starts from this packet only after a separate council reviews this classification. That council pass still leaves section 6 steps 2 through 5 unmet. The O7 force’s own entry is the first commit that can create a database, and only after those steps are accepted in earlier forces.

Order that force follows:

1. Keep `O2` in its own force. That force writes the application interface and an in-memory adapter. It rejects a caller-supplied SQL string. It creates no file.
2. Accept the `O1` health model as code before `O12` claims recovery disclosure.
3. Accept `O11`, then `O12`, before the store is a default write path.
4. Record Founder decision 9, then write the `O6` selection record. The selection record names the Node binding. This packet does not.
5. Open `O7` as `PKG-07`: the file, WAL, `user_version`, the row schema version, `privacy_generation`, the external recovery envelope, symlink confinement, and owner-only create. `O7` implements `O2`. It exposes no SQL.
6. Leave legacy copy, retention commands, proof export, and CLI `0.3.24` in their own later forces. `O8` waits on `O7` and `O4`.

Surfaces that stay closed inside that O7 force as well, unless a later Founder force names them: Gate 8’s architecture file, decisions 2–8 and 10–13, customer migration, a publish, and an evidence tier above `UNSET`.

## 8. Result

`OPTICS_OPTION_C_REVALIDATED_READY_FOR_COUNCIL`

Machine-readable copy: `REVALIDATION-MANIFEST.json`. Council stub: `10-INDEPENDENT-COUNCIL.md`, status `PENDING_INDEPENDENT_COUNCIL`.
