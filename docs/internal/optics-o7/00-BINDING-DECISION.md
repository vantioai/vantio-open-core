# O7 Node binding decision packet

Audience: INTERNAL_RESTRICTED

Council: `bc-00af4334-6f4f-59be-9ebf-c084d3c9baa6`, model Grok 4.7.

Council URL: https://cursor.com/agents/bc-00af4334-6f4f-59be-9ebf-c084d3c9baa6

Starting commit: `0620f10ee52d3abcea18c1c988df02f687f51b36`

Observed: 2026-09-27

Verdict: `O7_NODE_BINDING_COUNCIL_PASSED`

Machine-readable copy: `BINDING-DECISION.json`

## 1. Selection

| Field | Value |
| --- | --- |
| Binding | `node:sqlite` |
| Version | `24.15.0` |
| Token | `node:sqlite@24.15.0` |
| What the version is | The minimum Node.js version. The module is the one compiled into that Node.js binary. |
| npm dependency | None |
| npm integrity | None. There is no package tarball. |
| Runtime pin | `node>=24.15.0` on the 24.x line, plus Node.js 26.x |
| Fallback token | `better-sqlite3@13.0.3` |
| Fallback installed | No |
| Load fallback when `node:sqlite` is missing | No. Fail open. |

`24.15.0` is the revision named in the Node.js 24.19.0 documentation history table: "v24.15.0 | SQLite is now a release candidate." Source: `https://nodejs.org/docs/latest-v24.x/api/sqlite.html`, fetched 2026-09-27. The current-line documentation, Node.js v26.8.1, says Stability 1.2, release candidate, and dates that designation to v25.7.0. Source: `https://nodejs.org/api/sqlite.html`, fetched 2026-09-27.

Node.js 22.23.3 documentation still says the module is experimental after v22.13.0 removed the `--experimental-sqlite` flag. Source: `https://nodejs.org/docs/latest-v22.x/api/sqlite.html`, fetched 2026-09-27. Node.js 22 is unsupported for this selection.

## 2. Engine

The engine stays the ratified one. `docs/architecture/optics-foundation/08-ARCHITECTURE-DECISION-PACK.md` section 12 and `docs/architecture/optics-foundation/03-OPERATIONAL-STORE-AND-PORTABLE-PROOF.md` section 4: embedded SQLite, WAL, application-owned schema, path `~/.vantio/optics/store.sqlite` under the evidence root.

Python's mechanism stays the standard-library `sqlite3` module. This packet does not replace it.

The Python writer that a Node binding has to meet is `packages/optics-operational-store/src/optics_operational_store/store.py`:

- `timeout=0` and `isolation_level=None` in `_connect`
- `PRAGMA journal_mode=WAL`, and the call fails open with `WAL_UNAVAILABLE` when the result is not `wal`
- `PRAGMA integrity_check`
- `PRAGMA user_version`
- `BEGIN IMMEDIATE`, `COMMIT`, and `ROLLBACK`
- Bound parameters, including the `ON CONFLICT` upsert into `store_meta`
- Tables `store_meta`, `records`, and `drops` with ordinary columns and indexes
- No `STRICT` tables and no `FOREIGN KEY` clauses
- Read-only open through a `file:` URI with `mode=ro`, which must not create a missing file
- Backup is a filesystem copy, not the SQLite online backup API

Busy-timeout and page size stay `NOT_SET`. A binding whose default is to wait on a lock has to be opened with an explicit zero wait before it matches this store.

## 3. What this packet leaves alone

- `@vantio/cli` `0.3.24`, `@vantio/agent-sdk` `0.2.4`, and `vantio-agent-sdk` `3.1.0`
- `docs/governance/VERSION-METADATA.json`
- Gate 8 in `docs/architecture/optics-foundation/09-IMPLEMENTATION-GATES.md`
- The sentence "9. Node SQLite binding. Not selected." in the architecture decision pack
- `docs/planning/optics-o7-store/STORE-MANIFEST.json`, which still says `founder_decision_9` is `UNRESOLVED`
- `docs/planning/optics-production/PACKAGES.json`, which still says `O6` needs a Founder decision
- Node `openStore`, which still returns `NODE_BINDING_UNSELECTED` and creates no file
- Every `package.json` dependency list. None gains `sqlite3`, `better-sqlite3`, or `node:sqlite`

Those older files describe the tree Track 2 has not changed yet. This packet is the selection. Track 2 implements this packet. It does not treat the older "not selected" sentence as a reason to choose a different library, and it does not treat this packet as a reason to pretend the current process already opens a database.

Evidence tier stays `UNSET`. Gate 8 stays closed. `external_proof` is `NOT_CLAIMED`.

## 4. Repository constraints that bound the choice

| Constraint | Where it is written | Effect on the choice |
| --- | --- | --- |
| Store and CLI engines | `packages/optics-operational-store/package.json` and `packages/vantio-cli/package.json`: `node>=18.3.0` | The frozen CLI is not edited. A binding that needs a newer Node applies to a future store load, not to CLI `0.3.24`. |
| Node SDK engines | `packages/vantio-agent-sdk/package.json`: `node>=18.0.0` | Same. The SDK is not edited. |
| Import ban | `tests/optics-option-c-revalidation/adversarial.test.cjs` rejects a Node binding import and a package dependency on `sqlite3`, `better-sqlite3`, `better-sqlite`, or `node:sqlite` | This packet adds no import and no dependency. Track 2 is the change that lifts the ban for the selected module only. |
| Running facade | `packages/optics-operational-store/src/open.cjs` | Stays `NODE_BINDING_UNSELECTED`. |
| Node release calendar | `https://github.com/nodejs/release`, fetched 2026-09-27 | Node.js 18 EOL 2025-04-30. Node.js 20 EOL 2026-04-30. Node.js 22 Maintenance LTS through 2027-04-30. Node.js 24 Active LTS through 2028-04-30. Node.js 25 EOL 2026-06-01. Node.js 26 Current, EOL 2029-04-30. |

Node.js 18 and 20 are end of life on the observation date. Keeping them in `engines` is the frozen manifest. It is not a reason to pick a binding that only exists as a source build on those lines.

## 5. Candidates

| Candidate | Class | Disposition |
| --- | --- | --- |
| `node:sqlite` | Node.js built-in, synchronous `DatabaseSync` | Selected, floor `24.15.0` |
| `better-sqlite3@13.0.3` | Native addon, synchronous, MIT | Fallback. Not installed. |
| `sqlite3@6.0.1` | Native addon, asynchronous, BSD-3-Clause | Disqualified |
| `sql.js` | SQLite compiled to WebAssembly, MIT | Disqualified |
| `libSQL` and Turso | Fork, and a separate Rust engine | Disqualified |
| `bun:sqlite` | Bun built-in | Disqualified |

Wrappers that sit on top of one of these are not a second candidate. DuckDB stays rejected by the ratified option C record. SQLCipher stays out because at-rest encryption is Founder decision 5 and is not selected.

## 6. Evidence

### 6.1 `node:sqlite` documentation

Fetched 2026-09-27:

- Node.js v26.8.1 `https://nodejs.org/api/sqlite.html`. Stability 1.2, release candidate. History: experimental and unflagged at v22.13.0 and v23.4.0; release candidate at v25.7.0. `DatabaseSync` is synchronous. `timeout` default is 0 and arrived at v24.0.0 and v22.16.0. `readOnly: true` fails when the file is missing. `enableForeignKeyConstraints` default is true. `allowExtension` default is false. `exec` runs SQL and returns no rows. `prepare` returns `StatementSync` with `run`, `get`, and `all`. `defensive` defaults to true from v24.14.0 and v25.5.0.
- Node.js v24.19.0 `https://nodejs.org/docs/latest-v24.x/api/sqlite.html`. History row v24.15.0: "SQLite is now a release candidate."
- Node.js v22.23.3 `https://nodejs.org/docs/latest-v22.x/api/sqlite.html`. History row v22.13.0: no longer behind the flag, still experimental. `timeout` added at v22.16.0. Further constructor options added at v22.18.0.
- `https://github.com/nodejs/node/blob/main/configure.py` exposes `--without-sqlite` with the help text "build without SQLite (disables SQLite and Web Storage API)". A build that passes that flag has no module.
- The v26.8.1 page also distinguishes builds linked with `--shared-sqlite`. Those builds are a different SQLite than the one Node vendors. They are unsupported by this selection.
- `https://github.com/nodejs/node/issues/54135`. The bundled SQLite version is readable with `sqlite_version()` and `process.versions.sqlite`. A maintainer comment on that issue says a security fix could move the bundled version backward. This packet does not pin a SQLite version number for `node:sqlite`.

### 6.2 `better-sqlite3@13.0.3`

Fetched 2026-09-27 from the npm registry and from tag `v13.0.3`:

- Registry `https://registry.npmjs.org/better-sqlite3/13.0.3`. Version `13.0.3`. License MIT. Integrity `sha512-RbOBxmLBG8uvFUc15X9+9SFemKcQ0WBuISBVkpuiaUB2qblC8UWlHEjdWVoZ8AdhSwmoEgsiXKfopX0CQxaACQ==`. Published 2026-08-05.
- `package.json` at that tag. `engines.node` is `>=22`. Runtime dependency is `node-addon-api`. `files` includes `prebuilds/**`. `exports` names `linux-x64`, `linux-arm64`, `linuxmusl-x64`, `linuxmusl-arm64`, `darwin-x64`, `darwin-arm64`, `win32-x64`, and `win32-arm64`. The fetched manifest has no `install` script. This council did not unpack the published tarball, so the presence of those prebuilds inside the tarball is the manifest's claim.
- `lib/database.js` at that tag. Default `timeout` is 5000. The constructor rejects a negative timeout. Zero is allowed by the comparison `timeout < 0`. `readonly` is a separate option. The spelling `readOnly` throws.
- `deps/sqlite3/sqlite3.h` at that tag. `#define SQLITE_VERSION "3.53.4"`.

This council did not `npm install` the package.

### 6.3 Disqualified projects

- `sqlite3` on npm, version `6.0.1`, license BSD-3-Clause. The project README is titled as deprecated and says the repository is unmaintained. The GitHub repository `TryGhost/node-sqlite3` is archived. The API is asynchronous. Sources fetched via the npm page and the repository README on 2026-09-27.
- `sql.js` README at `https://github.com/sql-js/sql.js/blob/master/README.md`. The library stores the database in a memory file and states that it does not persist changes. Persistence is an export of a typed array and a later import of those bytes. The same README points Node users at a native binding when they need to work on database files directly.
- `libSQL` README at `https://github.com/tursodatabase/libsql/blob/main/README.md`. libSQL is a fork of SQLite with its own extensions, including a virtual write-ahead log interface and embedded replicas. The same README says the Turso database is a separate Rust engine and is not that fork. Either one is a different engine from the ratified SQLite file.

### 6.4 Workstation probe

This probe is not a supported-floor run, not a crash test, and not a stranger-host or external proof. The machine was Linux, Node.js `v22.14.0`, Python `3.12.3` linked to SQLite `3.45.1`. Node reported `process.versions.sqlite` `3.47.2`. Loading `node:sqlite` printed `ExperimentalWarning: SQLite is an experimental feature and might change at any time`. The files lived under a temporary directory and were deleted before this packet was written. No `*.sqlite` file was added to the repository.

Observed on that Node `v22.14.0` build:

- `PRAGMA journal_mode=WAL` through `prepare().get()` returned `wal`. Before `close`, the directory contained `store.sqlite-wal` and `store.sqlite-shm`.
- `exec("BEGIN IMMEDIATE")` returned `undefined`. An insert followed by `ROLLBACK` left `COUNT(*)` at 0. A later `COMMIT` kept the row. `PRAGMA user_version = 1` through `prepare().run()` survived. `PRAGMA integrity_check` returned `ok`.
- `readOnly: true` on a missing path threw `ERR_SQLITE_ERROR` (`unable to open database file`) and left the path absent. A later read-only open of the real file rejected an insert with `attempt to write a readonly database`.
- `enableForeignKeyConstraints: true` made `PRAGMA foreign_keys` return 1. `false` made it return 0. The Python schema has no foreign keys. The Python connection does not enable them. Track 2 sets this option to `false`.
- `timeout: 2500` left `PRAGMA busy_timeout` at 0. An unknown constructor option was also accepted and ignored. On this build, a constructor that does not throw is not evidence that the option took effect. The v22 documentation places the `timeout` option at v22.16.0, which is above v22.14.0.
- `isTransaction` is absent on this build. The v22.23.3 documentation lists it. Track 2 does not need the property. `BEGIN IMMEDIATE` and `ROLLBACK` are the contract.
- After Node closed the file, Python `sqlite3` opened the same path, read journal mode `wal`, `user_version` 1, and the committed row. A Python `ROLLBACK` dropped an uncommitted insert. A Python `COMMIT` of a second row was then read back by Node.

That is evidence that this build's SQLite 3.47.2 and this Python's SQLite 3.45.1 can share one ordinary WAL file for sequential writers, for a schema with no `STRICT` tables. It is not evidence about Node.js 24.15.0, about simultaneous writers, or about a killed process.

## 7. Criterion notes

The brief asks for these properties. Popularity was not a score. Download counts appear in the npm registry and were not used.

| Criterion | `node:sqlite@24.15.0` | `better-sqlite3@13.0.3` |
| --- | --- | --- |
| Node runtime | Gap. Floor is 24.15.0. Node 22 loads an experimental module and is unsupported. CLI `0.3.24` engines stay `>=18.3.0` because the CLI is not modified. | Meets its own manifest: `node>=22`, which includes Maintenance LTS 22. Misses the frozen `>=18.3.0` field the same way, on lines that are already end of life. Not installed here. |
| Native dependency | None beyond the Node binary. | Native addon. |
| Prebuilt binaries | The official Node binary is the build. | Manifest names eight platform entry points and a `prebuilds` directory. Tarball not unpacked here. |
| Linux architectures | Official Node Linux binaries on the supported lines. This council exercised one Linux x64 workstation on an unsupported Node. | Manifest names `linux-x64`, `linux-arm64`, `linuxmusl-x64`, `linuxmusl-arm64`. |
| Transactions | `exec` of `BEGIN IMMEDIATE`, `COMMIT`, and `ROLLBACK` worked on the probed build. | Documented `transaction()` helper and `exec`. Not executed here. |
| WAL | Host `-wal` and `-shm` files appeared on the probed build. Python reread the file. | Documented `pragma('journal_mode = WAL')`. Not executed here. |
| Prepared statements | `StatementSync` `run`, `get`, and `all` worked on the probed build. | Documented `prepare`. Not executed here. |
| Crash consistency | SQLite WAL recovery is the mechanism. This council did not kill a writer. | Same mechanism. Not crash-tested. |
| Installation reliability | `require('node:sqlite')` either resolves or throws. A throw fail-opens. | A missing platform binary fails the addon load. The package has to be optional or the future CLI install fails closed. |
| Release packaging | No dependency entry. Track 2 changes the private store `engines` field. | An npm dependency, optional if it is ever adopted. |
| Supply chain | The Node.js release the operator already runs. | The npm package, `node-addon-api`, and a native binary. |
| Maintenance | The Node.js project. The module is Stability 1.2 on the current docs, not Stability 2. | Release `13.0.3` on 2026-08-05. MIT. The project is one maintainer line, Joshua Wise, and it has kept shipping. |
| Memory | Synchronous calls block the Node event loop for the duration of the SQLite call. The same is true of the Python store. The query limit of 500 is an application rule. | Same synchronous shape, plus a worker helper this store does not need. |
| Concurrency | One `DatabaseSync` is a single connection. WAL is what lets another process read. Simultaneous Node and Python writers were not tested. `timeout` default 0 means a lock does not wait. | WAL is available. Default timeout 5000 waits. Track 2 would have to pass 0. |
| Rollback | SQL `ROLLBACK` worked on the probe. Software rollback stops loading the module and leaves the file and its sidecars. | SQL rollback is SQLite's. Software rollback removes a dependency and leaves the file. |
| License | No third license beyond the Node.js binary already required to run the CLI. SQLite itself is public domain. | MIT. Compatible with the MIT CLI. |
| Ordinary-client installation | A client on an official Node binary at the floor installs no extra module. A client on Node 22 fail-opens. CLI `0.3.24` does not load the store, so today's CLI install is unchanged. | Extra native install for a future package. |
| Testability | Gap. This environment cannot run Node.js 24.15.0. The probe covered Node.js 22.14.0 only. | Could be installed on this Node 22.14.0. This council did not install it, because the packet must not add the dependency. |
| Long-term support | Node.js 24 through 2028-04-30 and Node.js 26 through 2029-04-30, on the release schedule fetched above, for as long as those lines keep the module. The API is a release candidate. | Semver on the library. Bundled SQLite is 3.53.4 at this version. A new Node major has already moved `engines` to `>=22`. |

## 8. Disqualifiers

`sqlite3@6.0.1`. The maintainers have deprecated and archived it. The API is asynchronous, so a `BEGIN IMMEDIATE` transaction depends on a serialized queue the application would have to build. The store facade and the Python writer are synchronous. Maintenance status removes it before popularity is considered. The BSD-3-Clause license would have been compatible.

`sql.js`. The database lives in a WebAssembly memory image. The README's persistence path is export and import of the whole byte array. A crash after a write and before that export loses the write. The host files `store.sqlite-wal` and `store.sqlite-shm` are the ratified WAL pair. This library does not produce them.

`libSQL` and Turso. libSQL is a fork with extra WAL and replica machinery. Turso's README describes a separate Rust engine. Option C ratified SQLite. Selecting either one reopens the engine. File-format promises on the libSQL README do not make the fork the ratified engine.

`bun:sqlite`. The store package, the CLI, and the Node SDK declare Node. A Bun-only module is outside that runtime.

`better-sqlite3@13.0.3` is not disqualified. It loses the primary seat for three recorded reasons:

1. It is a native addon and a third SQLite build. Python already links one SQLite. `node:sqlite` uses the SQLite inside the Node binary. Adding 3.53.4 makes a third.
2. The default busy timeout is 5000 ms. The store's contract is no wait. Every open would have to remember `timeout: 0`. `node:sqlite` documents the default as 0.
3. A required dependency fails installation on machines outside the eight exported platform tuples. The ordinary-client failure mode for this product is a native install failure. Fail-open only works if the dependency is optional, which is a later packaging choice, not the primary seat.

It remains the fallback because its API is semver-stable on Node.js `>=22`, including the Maintenance LTS line this selection leaves unsupported.

## 9. Why the floor is 24.15.0

Three dates stack, and the floor is the latest of them:

- v22.13.0 unflags the module and leaves it experimental.
- v22.16.0 and v24.0.0 add the `timeout` option. The probed v22.14.0 build ignores `timeout`.
- v24.15.0 is the 24.x revision that marks the module a release candidate. v22.23.3 documentation has not received that mark. The probed v22.14.0 build prints the experimental warning.

Node.js 22 remains Maintenance LTS until 2027-04-30. Leaving it unsupported is a support gap. Covering it with the experimental module would bind the store to an API Node's own warning says might change at any time. Covering it with `better-sqlite3` would take the native addon as the primary. This council accepts the Node.js 22 gap and writes the addon down as the fallback.

Node.js 25 reached end of life on 2026-06-01. It is unsupported even where a 25.x build marked the module as a release candidate.

## 10. Track 2 limits

Track 2 may load `node:sqlite` only when `process.versions.node` is on Node.js 24 at or above `24.15.0`, or on Node.js 26. Below that, including a Node.js 22 that can already `require` the module, the call fail-opens and creates no file.

Constructor options Track 2 sets, then checks, because the probed build ignores unknown options:

- filesystem path, not a `file:` URI
- `readOnly: true` for the read-only open, and a missing path must stay missing
- `timeout: 0`, then `PRAGMA busy_timeout` must read back 0
- `enableForeignKeyConstraints: false`, then `PRAGMA foreign_keys` must read back 0
- `allowExtension` left false

SQL Track 2 may use:

- `prepare('PRAGMA journal_mode=WAL').get()` and a fail-open when the mode is not `wal`. `exec` returns no row, so it cannot confirm the mode.
- `exec` for `BEGIN IMMEDIATE`, `COMMIT`, and `ROLLBACK`
- `prepare` with bound parameters for every value the application supplies
- `PRAGMA user_version` and `PRAGMA integrity_check`
- the same non-`STRICT` tables the Python writer already creates

SQL and APIs Track 2 leaves unused:

- `STRICT`
- `loadExtension` and `allowExtension: true`
- `createSession`, `applyChangeset`, `createTagStore`, `setAuthorizer`
- user-defined functions and aggregates
- `sqlite.backup` as a replacement for the filesystem copy the Python store already does
- `ATTACH` of a second database

`defensive` defaults to true on Node.js versions at and above v24.14.0. The selected floor is above that. Defensive mode does not change the file format. Track 2 does not treat it as the integrity check. `PRAGMA integrity_check` remains the check.

A future `engines` field on the private store package becomes `>=24.15.0` in the Track 2 change. CLI `0.3.24` does not gain that field.

## 11. Fallback and rollback

Operational fallback when the module is missing, the Node version is below the floor, or open throws: the call returns, the application continues, and no store file is created. The current reason code is `NODE_BINDING_UNSELECTED`. Track 2 may use a distinct reason for "selected binding cannot load." It does not download or compile another library inside that failure.

Named fallback for a later council: `better-sqlite3@13.0.3`, integrity `sha512-RbOBxmLBG8uvFUc15X9+9SFemKcQ0WBuISBVkpuiaUB2qblC8UWlHEjdWVoZ8AdhSwmoEgsiXKfopX0CQxaACQ==`. If that later council adopts it, the package is an `optionalDependency`, every open passes `timeout: 0`, and a missing addon fail-opens. It is not a required dependency of `@vantio/cli`. This council does not adopt it.

Software rollback: stop loading `node:sqlite`. Leave `store.sqlite`, `store.sqlite-wal`, and `store.sqlite-shm` on disk. Do not down-migrate `user_version`. Do not delete the sidecars. Legacy JSON files stay where they are.

SQL rollback: a failed `BEGIN IMMEDIATE` body ends in `ROLLBACK`. The corrupt-file rule in the architecture pack still applies. A failed write does not replace the file with an empty database.

## 12. Platforms

Authorized target: official Node.js release binaries for Node.js 24 at or above 24.15.0, and for Node.js 26, built with the default SQLite configuration.

Unsupported:

- Node.js below 24.15.0, including 18, 20, 22, and 25
- binaries configured with `--without-sqlite`
- binaries configured with `--shared-sqlite`
- Bun and Deno
- a WASM memory image or an export-byte-array store

Exercised here: one Linux workstation, Node.js v22.14.0, which is on the unsupported list. Windows, macOS, arm64, musl, Node.js 24.15.0, and Node.js 26 were not run. Windows ACL detail stays Founder decision 8. This packet does not invent an ACL.

## 13. Release impact

This change is documents plus a test that locks the documents. No package manifest changes. No changelog heading changes. No tag. No publish.

CLI `0.3.24` continues to declare `node>=18.3.0` and continues to ignore the store. A later CLI that loads the store cannot keep that engines field. That CLI is a later release. This packet does not open it.

The private store package stays `0.0.0-unstable-pre-1.0` and `private: true`. `schema_status` stays `unstable-pre-1.0`. The store stays off the default write path. `O12` stays unmet. `O6` in `PACKAGES.json` stays the historical cell. The implementation status of the binding is this packet, not that cell.

## 14. Reading rule

This record selects the Node binding. The architecture decision pack still says the binding is not selected. The running store still returns `NODE_BINDING_UNSELECTED`. Those sentences remain true of those files and of the current process. Track 2 implements `node:sqlite@24.15.0` from this record and does not pick a different library because an older sentence still says "not selected."
