# PKG-02 reader compatibility entry gates — boundary

PRIVATE | INERT | NOT SHIPPED | READ_AND_EXPLAIN | NO_WRITE_BACK | NO_LIVE_WRITER | NO_MIGRATION | NO_STABLE_SCHEMA

Audience: INTERNAL_RESTRICTED

This force proves reader compatibility entry gates before Unit D and Unit E. The producer classification, when the suite passes, is `OPTICS_PKG02_READER_COMPAT_GATES_READY_FOR_COUNCIL`.

That classification is a handoff to a separate council. It is not a council verdict, not a merge, and not permission to activate a writer.

## Starting point

Locked commit: `89f95099d0dce463307eb75d78e7fcf2ef99feb2`.

Units A, B, C, and F are already merged and stay inert. This force does not reopen their packages.

## What this force contains

- `packages/optics-reader-compat-gates/` — private inert evaluator.
- `tests/optics-pkg02-reader-compat-gates/` — direct, adversarial, and isolation tests.
- `docs/internal/optics-pkg02-reader-compat-gates/` — these notes.

The package is not a pnpm workspace member. `@vantio/cli` `0.3.24`, `vantio-agent-sdk` `3.1.0`, and `@vantio/agent-sdk` `0.2.4` do not import it.

`schema_status` is `unstable-pre-1.0`. `schema_version` is `0`. The package version is `0.0.0-unstable-pre-1.0`.

## What stays closed

- CLI `0.3.24`, Node SDK `0.2.4`, and Python `3.1.0` bytes, versions, and tests.
- Unit D and Unit E. `PKG02-FUTURE-CLI-UNASSIGNED` and `PKG02-FUTURE-PYTHON-UNASSIGNED` are placeholders, not releases.
- Write-back, migration, SQLite, a UI, a daemon, an exporter, and alerting.
- A stable schema, a release candidate, a seal, a publish, and an announcement.
- Edits to `RECORD-COMPATIBILITY-MATRIX.json`. Every cell stays `NOT_SHIPPED`.
- A merge. The pull request stays draft.

`units_d_e` on every gate report is `NOT_AUTHORIZED`. `activates_unit_d` and `activates_unit_e` stay false. `council_verdict` stays null.
