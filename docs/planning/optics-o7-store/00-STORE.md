# O7 operational store

Audience: INTERNAL_RESTRICTED

Producer role: implementation producer only. This agent does not sit the independent council, does not self-assign a council pass, and does not deploy a store to a customer host.

Producer identity: Cursor cloud agent `bc-4b9b153e-e636-58b6-a894-7de8dd2cd819`, model Grok 4.7.

Producer URL: https://cursor.com/agents/bc-4b9b153e-e636-58b6-a894-7de8dd2cd819

Producer classification: `OPTICS_O7_STORE_BLOCKED_NODE_BINDING_UNSELECTED_READY_FOR_COUNCIL`

That classification means the Python file store is implemented and the Node file store is not. Founder decision 9 is unresolved, so this force did not select a Node binding. The packet is a handoff to a separate council. It is not a council verdict, not a Gate 8 opening, not an evidence tier, and not a claim that Optics persistence is product-complete.

Starting commit: `6d409eb73b8875b1c525348a92e9db42a74291b9` (`Merge pull request #86 from vantioai/cursor/optics-option-c-revalidate-41fe`).

## 1. Boundary

This force adds the private package `@vantio/optics-operational-store` `0.0.0-unstable-pre-1.0` and the tests under `tests/optics-o7-store/`.

The engine is the engine named in the ratified text. `docs/architecture/optics-foundation/08-ARCHITECTURE-DECISION-PACK.md` section 12 and `docs/architecture/optics-foundation/03-OPERATIONAL-STORE-AND-PORTABLE-PROOF.md` section 4: embedded SQLite, WAL, application-owned schema. Python’s named mechanism is the standard-library `sqlite3` module. This force uses that module. It does not add a package dependency.

This force leaves these surfaces untouched:

- `docs/architecture/optics-foundation/`
- `docs/planning/optics-production/` including `PACKAGES.json`
- Gate 8 in `docs/architecture/optics-foundation/09-IMPLEMENTATION-GATES.md`
- Founder decisions 2–13
- `@vantio/cli` `0.3.24`, Python `vantio-agent-sdk` `3.1.0`, and Node SDK `@vantio/agent-sdk` `0.2.4`
- Live writers, Units D and E activation flags, and the PKG-02 reader
- Legacy `~/.vantio/runs/*.json` copy (`O8`)
- Retention commands (`O9`)
- A customer migration, a publish, a tag, and a host deploy

`schema_status` stays `unstable-pre-1.0`. Evidence tier stays `UNSET`.

`PACKAGES.json` still says `O7` is `NOT_AUTHORIZED`. This force did not edit that file. The merged plan’s hashes are checked by `tests/optics-option-c-revalidation/`. The implementation status in this packet is separate from that catalog cell.

## 2. What the Python store does

`packages/optics-operational-store/src/optics_operational_store/store.py` is the file engine.

- One local file at `{evidence_root}/optics/store.sqlite`, plus `-wal` and `-shm` when SQLite creates them. `VANTIO_HOME` is the evidence root when the caller does not pass one. The CLI reader is not patched.
- Create runs only when the caller passes `create=True` and the final path is missing. Importing the package creates nothing. PKG-02 flags `activate`, `emit`, `migrate`, `publish`, `seal`, `sqlite`, and `write` do not create a file. There is no shared activation switch with Units D or E.
- WAL is on. `operational_schema_version` is `1` on SQLite `user_version` and on each row. That integer is the first migrator written here. It is not legacy JSON `schema_version` 2. The evidence record’s own `schema_version` stays `0`.
- `privacy_generation` starts at `1`.
- Callers use put, get, and the A4 query request. A caller-supplied SQL string is rejected. A caller regular expression is rejected. Allowlist enforcement calls the private PKG-01 validator before insert. Prohibited fields are not written.
- Unix create mode is `0600` for the store, the id sidecar, the backup, and the recovery envelope. Directories this force creates are `0700`. Windows ACL detail stays Founder decision 8. No ACL is invented.
- A symlink on `optics`, the store path, the id sidecar, the backup, the recovery directory, or a WAL sidecar is refused. The store does not follow it.
- A corrupt or unreadable file stays in place. Disclosure is `optics/recovery/<safe-store-id>.recovery.json`. The first corruption state is `STOPPED_PRESERVED`. Salvage after that classification returns `UNAVAILABLE` for a torn file and is never `COMPLETE`. This force does not add a replacement command and does not write `store.sqlite.new`.
- A newer `user_version` is refused with `NEWER_SCHEMA_REFUSED`. A privacy-weaker writer is refused with `WEAKER_WRITER_REFUSED`. Software rollback does not down-migrate the file.
- An empty database below version 1 is migrated forward after a `0600` backup. A file that already has foreign tables is not replaced. An injected migration fault leaves the original bytes, keeps the backup, and records `MIGRATION_FAILED`.
- If the store cannot be opened or a write cannot finish, the call returns and the application result is detached. Normal writes stop. The function does not raise for those cases.
- Busy-timeout and page-size stay `NOT_SET`. Connections use no wait. That is not a selected NFR number. At-rest encryption is not selected.
- Default retention is unbounded. This force does not prune.
- Query freshness is `UNKNOWN`. A request for freshness `CURRENT` is rejected. Decision 10 stays unresolved.
- The store is not a default write path. `O12` is still `NOT_AUTHORIZED`, and the dependency order says fail-open is required before the store is a default write path.

## 3. What stays blocked

| Item | State after this force |
| --- | --- |
| Founder decision 9 | Unresolved. This force names no Node library. |
| `O6` Node binding selection | Unmet. Node `openStore` returns `NODE_BINDING_UNSELECTED`, creates no file, and imports no SQLite module. |
| `O2` store contract as its own accepted package | Unmet. Put, get, and query live on this store so the file can be tested. There is no separate in-memory contract package and no change to the `O2` catalog cell. |
| `O1` health model as code | Unmet. The recovery envelope is the A3 disclosure. A drop row stores a timestamp and a count, not a payload. That is not PKG-03. |
| `O11` structural caps | Unmet. The query refuses a limit outside 1–500, refuses caller regular expressions, and sets no numeric queue. |
| `O12` fail-open package | Unmet. Open and write failures on this store are fail-open. The store is not wired to an application request path. |
| `O8` legacy copy | Not done. A `runs/*.json` file beside the store is left byte-for-byte. |
| `O10` as a product query package | Not claimed. The store answers the A4 request for rows it holds. |
| Node and Python alternate writes on one file | Not demonstrated. Node cannot open the file. |
| Evidence tier | `UNSET`. No `UNIT_PROVED`, `INTEGRATION_PROVED`, `STRANGER_HOST_PROVED`, `PROVED_EXTERNAL`, or `CUSTOMER_VALIDATED`. |
| Gate 8 | Closed. The architecture file was not edited. |

The blocked classification is `NODE_BINDING_UNSELECTED` because a dual-runtime store file cannot exist until decision 9 and `O6` name a Node binding. The other rows are sequenced follow-ons. They are not closed by the Python file tests.

## 4. Revalidation gate

`tests/optics-option-c-revalidation/adversarial.test.cjs` used to reject every `import sqlite3` in the working tree. That check described the tree before this force. A2 already names the Python standard-library module, and this force is the authorized file implementation.

The test now still rejects a tracked `*.sqlite` file, a package dependency on `sqlite3`, `better-sqlite3`, `better-sqlite`, or `node:sqlite`, and any Node binding import in every source file. A standard-library `import sqlite3` or `from sqlite3` is allowed only under `packages/optics-operational-store/` and `tests/optics-o7-store/`.

`docs/planning/optics-option-c-revalidation/REVALIDATION-MANIFEST.json` records the new hash of that test file. The revalidation producer classification stays `OPTICS_OPTION_C_REVALIDATED_READY_FOR_COUNCIL`. This force does not rewrite `00-REVALIDATION.md` and does not sit that council.

## 5. Result

`OPTICS_O7_STORE_BLOCKED_NODE_BINDING_UNSELECTED_READY_FOR_COUNCIL`

Machine-readable copy: `STORE-MANIFEST.json`. Council stub: `10-INDEPENDENT-COUNCIL.md`, status `PENDING_INDEPENDENT_COUNCIL`.
