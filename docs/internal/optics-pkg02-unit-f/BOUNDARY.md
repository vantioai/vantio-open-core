# PKG-02 Unit F boundary

PRIVATE | INERT | NOT SHIPPED | READ_AND_EXPLAIN | NO_WRITE_BACK | NO_LIVE_WRITER | NO_MIGRATION | NO_STABLE_SCHEMA

Audience: INTERNAL_RESTRICTED

Unit F is the inert reader compatibility release. It reads a record and explains it. It does not write the record back, and it does not ship inside `@vantio/cli` 0.3.24.

`schema_status` is `unstable-pre-1.0`. `schema_version` is `0`. The package version is `0.0.0-unstable-pre-1.0`. JSON Schema is not the source of truth.

## Starting point

Locked main: `4e50dd9775d23899e1c68e5fa0e7a59c17066ea3`.

That commit is the merge of Unit B. Units A, B, and C are already on that main. This unit does not reopen them.

## What this unit contains

- `packages/optics-record-reader/` — the private inert reader.
- `tests/optics-pkg02-unit-f/` — direct, adversarial, ordinary-client, and isolation tests.
- `docs/internal/optics-pkg02-unit-f/` — these notes.

The package is not a pnpm workspace member. Nothing in the live CLI, Python SDK, Node SDK, or publish workflows imports it.

## What this unit does not do

- It does not change CLI `0.3.24`, Python `3.1.0`, or Node SDK `0.2.4`.
- It does not change PKG-01 contract behavior, Unicode tables, or the Unit A fixture file.
- It does not write `~/.vantio/runs`, rewrite a record, or sit on the `vantio run` exit path.
- It does not add SQLite, a migration, a UI, a daemon, an exporter, or alerting.
- It does not start Units D or E. Writer activation stays `NOT_AUTHORIZED`.
- It does not mark a pull request ready, and it does not merge.

Producer classification before council: `OPTICS_PKG02_UNIT_F_READY_FOR_COUNCIL`.

That classification is not a council verdict.
