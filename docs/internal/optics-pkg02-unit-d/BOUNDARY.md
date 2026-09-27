# PKG-02 Unit D boundary

PRIVATE | FUTURE LINE | NOT PUBLISHED | NOT SEALED | NO UNIT E | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

Unit D activates the Node Optics writer on `@vantio/cli` `0.4.0-pkg02-unit-d`. That version is the concrete future line for `PKG02-FUTURE-CLI-UNASSIGNED`. It is not `0.3.24`.

`schema_status` is `unstable-pre-1.0`. `schema_version` is `0`. The Unicode diagnostic is `PKG01-UCD-16.0.0`. The contract package stays private at `0.0.0-unstable-pre-1.0`. `@vantio/agent-sdk` stays `0.2.4`.

## Starting point

Founder Force starting commit: `dd3344dcc636136ed22df75e8df3866c993efd27`.

Prerequisites already on that commit: Unit A, Unit B, Unit F, and the T2a reader-compat gates. This unit does not re-implement them.

## What this unit contains

- `packages/vantio-cli-pkg02/` — the future CLI tree and writer.
- `tests/optics-pkg02-unit-d/` — proofs.
- `docs/internal/optics-pkg02-unit-d/` — these notes.
- Five cells in `docs/planning/optics-pkg02/RECORD-COMPATIBILITY-MATRIX.json` marked `UNIT_D_PROVED_NOT_SHIPPED`.

The package is not a pnpm workspace member. `packages/vantio-cli/` is not edited.

## What this unit does not do

- It does not reopen, edit, or republish `@vantio/cli` `0.3.24`.
- It does not change Python `3.1.0` or start Unit E.
- It does not publish to npm, seal, or open a release candidate.
- It does not add SQLite, a migration, a UI, a daemon, OTLP, SIEM, or alerting.
- It does not store prompts, machine hostnames, or cost.
- It does not mark a council pass, and it does not merge.

Producer classification before council: `OPTICS_PKG02_UNIT_D_READY_FOR_COUNCIL`.

That classification is not a council verdict and not a statement that the line is shipped.
