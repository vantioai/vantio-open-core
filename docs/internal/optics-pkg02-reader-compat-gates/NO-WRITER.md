# PKG-02 reader compatibility entry gates — no writer

PRIVATE | INERT | NOT SHIPPED | READ_AND_EXPLAIN | NO_WRITE_BACK | NO_LIVE_WRITER | NO_MIGRATION | NO_STABLE_SCHEMA

Audience: INTERNAL_RESTRICTED

Unit D and Unit E stay `NOT_AUTHORIZED`.

This package exports `evaluateEntryGates` and constants. It does not export a writer, a migrator, or a promote operation.

`readRunFile` options `write`, `activate`, `migrate`, and `path` produce `WRITER_INACTIVE` from the existing reader. The gate checks that result and then checks the file bytes.

`promote` is not a writer flag on the Unit F reader. The gate still sends it. The claimed-local file must keep its bytes, and the reading must stay `LEGACY_UNMARKED`.

No file under `packages/vantio-cli/`, `packages/vantio-agent-sdk/`, or `packages/vantio-agent-sdk-py/` is part of this change. `opticsStatusForRecordedCall` still returns `SUCCESS`.

The future producer version string `PKG02-FUTURE-CLI-UNASSIGNED` is the planning placeholder. It does not create a CLI package and it does not bump `0.3.24`.
