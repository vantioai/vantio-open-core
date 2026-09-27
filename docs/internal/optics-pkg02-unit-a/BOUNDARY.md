# PKG-02 Unit A boundary

PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

Unit A is the shared record vocabulary and its conformance fixtures. It is a private package. It is not a release, not a stable schema, and not loaded by `@vantio/cli` 0.3.24, `vantio-agent-sdk` 3.1.0, or `@vantio/agent-sdk` 0.2.4.

`schema_status` is `unstable-pre-1.0`. `schema_version` is `0`. JSON Schema is not the source of truth.

## Starting point

Locked main: `14249ba84ff1f3d5aa8ad7a7366172f29235c76e`.

Branch: `implementation/optics-pkg02-unit-a-vocabulary`.

## What this unit contains

- `packages/optics-record-vocabulary/` — vocabulary, loaders, structural checks, fixture declarations.
- `tests/optics-record-vocabulary/` — the isolated suite, including the Python canonical-JSON check.
- `docs/internal/optics-pkg02-unit-a/` — these notes.

The package is not a pnpm workspace member. Nothing in the live CLI, Python SDK, or Node SDK imports it.

## What this unit does not do

- It does not change PKG-01, and it does not import the PKG-01 validator or privacy detector.
- It does not write `~/.vantio/runs`, rewrite a record, or open a live run directory.
- It does not add SQLite, a migration, a UI, a daemon, an exporter, or alerting.
- It does not bump `@vantio/cli`, `@vantio/agent-sdk`, `vantio-agent-sdk`, or `@vantio/optics-evidence-contract`.
- It does not start Units B, C, D, E, or F.
- It does not mark a pull request ready, and it does not merge.

The fixture runner checks declared interpretations. It does not convert an arbitrary live record, and a bare call object is rejected.

## Unicode

The diagnostic profile identity is `PKG01-UCD-16.0.0` version `16.0.0`. This unit does not add a payload field for it and does not generate a second profile.
