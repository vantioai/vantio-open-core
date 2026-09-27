# O7 runtime integration

Audience: INTERNAL_RESTRICTED

Classification: `O7_RUNTIME_INTEGRATION_READY_FOR_COUNCIL`

Starting commit: `ebc060f2af98362bc7e317f4a01e635138a657b1`

Binding: `node:sqlite@24.15.0`, from `docs/internal/optics-o7/00-BINDING-DECISION.md`.

This record is an implementation handoff. It is not a council pass, not an evidence tier, and not a host proof.

## What the runtime does

`packages/optics-operational-store` loads `node:sqlite` only when `process.versions.node` is Node.js 24 at or above 24.15.0, or Node.js 26. On every other version, including Node.js 22 that can already resolve the builtin, `openStore` returns `NODE_BINDING_CANNOT_LOAD`, the application continues, and no store file is created.

On a supported runtime the constructor receives a filesystem path. Read-only opens pass `readOnly: true` and do not create a missing path. Every open passes `timeout: 0` and `enableForeignKeyConstraints: false`, then reads back `PRAGMA busy_timeout` and `PRAGMA foreign_keys`. `allowExtension` stays false. WAL is confirmed with `prepare('PRAGMA journal_mode=WAL').get()`. `BEGIN IMMEDIATE`, `COMMIT`, and `ROLLBACK` go through `exec`. Application values use bound parameters. Tables match the Python writer and are not `STRICT`. Backup is a filesystem copy.

`better-sqlite3` is not installed and is not loaded when the selected module cannot load.

The private store `engines` field is `>=24.15.0`. `@vantio/cli` `0.3.24` stays `>=18.3.0`. `@vantio/agent-sdk` `0.2.4` and `vantio-agent-sdk` `3.1.0` are unchanged.

## What stays closed

Evidence tier `UNSET`. Gate 8 closed. `external_proof` is `NOT_CLAIMED`. The store is not a default write path. `schema_status` stays `unstable-pre-1.0`. The package stays private at `0.0.0-unstable-pre-1.0`. No publish and no customer migration.

This force executed the store tests on the official Node.js `v24.15.0` and `v26.10.0` linux-x64 binaries inside this workspace. That execution is not a stranger host, not a clean-host certification, and not external proof. Node.js 22.14.0 in this workspace fail-opens with `NODE_BINDING_CANNOT_LOAD` and creates no file.

`docs/architecture/optics-foundation/08-ARCHITECTURE-DECISION-PACK.md` still says the binding is not selected. `docs/planning/optics-o7-store/STORE-MANIFEST.json` still says `founder_decision_9` is `UNRESOLVED`. Those sentences describe those older files. This runtime implements the binding packet.
