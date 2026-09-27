# PKG-02 Unit D implementation report

PRIVATE | FUTURE LINE | NOT PUBLISHED | NOT SEALED | NO UNIT E | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

Producer classification before council: `OPTICS_PKG02_UNIT_D_READY_FOR_COUNCIL`

This classification means the Unit D branch is ready for a separate council. It is not a council verdict, not a merge, and not a shipped product.

The producer did not sit the council.

## What landed

Private future CLI `@vantio/cli` `0.4.0-pkg02-unit-d` in `packages/vantio-cli-pkg02/`. The frozen package `packages/vantio-cli/` stays `0.3.24`. Node SDK stays `0.2.4`. Python stays `3.1.0`. The evidence contract stays `0.0.0-unstable-pre-1.0` and private.

`activates_unit_d` is true on this package and on five matrix cells. `activates_unit_e` is false. `shipped_product` is false.

## Proof order

1. The inert Unit B adapter is present. An ordinary `0.3.24` run file is byte-identical after the adapter module is loaded and `adaptNodeCopy` is not used on that file. A second `0.3.24` run that requires the adapter and does not call it keeps the frozen shape.
2. Unknown optics token `SUPER_SUCCESS` adapts to `UNAVAILABLE` with `optimistic_default_forbidden`. It does not become `SUCCESS`.
3. Only after those checks, the future writer stores canonical records on `0.4.0-pkg02-unit-d`.

## Checks

From the repository root:

```sh
node --test tests/optics-pkg02-unit-d/*.test.cjs
```

The suite covers Unit A fixtures, the five ordinary-client files, the written delta against `0.3.24`, rollback, and a validator fault whose child exit code stays `4`.

## Hard-stop attestations

- CLI `0.3.24` sources are unchanged.
- No npm publish, seal, or release candidate.
- No Unit E and no Python writer change.
- No SQLite, migration, UI, daemon, exporter, or alerting.
- No stable schema.
- No announcement.
- Draft pull request only. Not marked ready. Not merged.
- Council is a separate agent. This producer did not run it.
