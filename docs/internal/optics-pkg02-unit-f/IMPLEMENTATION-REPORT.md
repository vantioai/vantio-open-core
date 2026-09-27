# PKG-02 Unit F implementation report

PRIVATE | INERT | NOT SHIPPED | READ_AND_EXPLAIN | NO_WRITE_BACK | NO_LIVE_WRITER | NO_MIGRATION | NO_STABLE_SCHEMA

Audience: INTERNAL_RESTRICTED

Producer classification before council: `OPTICS_PKG02_UNIT_F_READY_FOR_COUNCIL`

This classification means the Unit F branch is ready for a separate council agent. It is not a council verdict, not a merge, and not a statement that a writer exists.

The producer did not sit the council. Units D and E stay `NOT_AUTHORIZED`.

## What landed

Private package `@vantio/optics-record-reader` at `0.0.0-unstable-pre-1.0`. That version matches the unstable posture. It is not a bump of CLI `0.3.24`, Node SDK `0.2.4`, Python `3.1.0`, `@vantio/optics-evidence-contract`, `@vantio/optics-record-vocabulary`, or `@vantio/optics-node-adapter`.

The package is not in `pnpm-workspace.yaml`. It explains copies through the Unit B adapter. Live CLI and SDK sources do not import it.

## Checks

From the repository root:

```sh
node --test tests/optics-pkg02-unit-f/*.test.cjs
```

The producer run of that command reported 24 tests and 0 failures. The suite explains all 34 Unit A fixtures, refuses unknown and legacy optics `SUCCESS` in the display, keeps absent, null, and unknown classes apart, keeps status dimensions apart, preserves origin, omits prohibited canaries, and reads four ordinary-client inputs without changing their bytes.

## Hard-stop attestations

- No CLI, Python SDK, or Node SDK source change, and no version bump.
- No PKG-01 behavior change.
- No live writer and no live emission.
- No write-back. Input bytes stay byte-identical after a read.
- No SQLite, migration, UI, daemon, exporter, or alerting.
- No stable schema.
- No release candidate, seal, publish, tag, or announcement.
- No Units D or E.
- Draft pull request only. Not marked ready. Not merged.
- Council is a separate agent. This producer did not run it.
