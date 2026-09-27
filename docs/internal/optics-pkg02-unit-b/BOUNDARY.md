# PKG-02 Unit B boundary

PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

Unit B is the inert Node adapter. It calls the existing private mapper on copies. It is not a release, not a stable schema, and not loaded by `@vantio/cli` 0.3.24, `vantio-agent-sdk` 3.1.0, or `@vantio/agent-sdk` 0.2.4.

`schema_status` is `unstable-pre-1.0`. `schema_version` is `0`. The package version is `0.0.0-unstable-pre-1.0`. The future writer placeholder is `PKG02-FUTURE-CLI-UNASSIGNED`. That string is not a version that exists.

## Starting point

Locked main: `587f3b94d47ea958f91d3a99125cd55931d995f1`.

That commit is the merge of Unit A. This unit does not reopen the Unit A vocabulary.

## What this unit contains

- `packages/optics-node-adapter/` — the inert adapter.
- `tests/optics-node-adapter/` — direct and adversarial tests.
- `docs/internal/optics-pkg02-unit-b/` — these notes.
- `tests/optics-record-vocabulary/isolation.test.cjs` — the Unit A path proof now points at the Unit A branch tip `299651c429b588e1e982a26ba717a1b4f1ffeac4`, so later commits are not reported as Unit A scope violations.

The package is not a pnpm workspace member. Nothing in the live CLI, Python SDK, or Node SDK imports it.

## What this unit does not do

- It does not change CLI `0.3.24`, Python `3.1.0`, or Node SDK `0.2.4`.
- It does not change PKG-01 contract behavior, Unicode tables, or the 220-fixture corpus.
- It does not write `~/.vantio/runs`, rewrite a record, or sit on the `vantio run` exit path.
- It does not add SQLite, a migration, a UI, a daemon, an exporter, or alerting.
- It does not start Units D, E, or F, and it does not activate a writer.
- It does not mark a pull request ready, and it does not merge.

Producer classification before council: `OPTICS_PKG02_UNIT_B_READY_FOR_COUNCIL`.
