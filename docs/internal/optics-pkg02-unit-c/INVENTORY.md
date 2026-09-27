# PKG-02 Unit C inventory

PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

Starting commit: `587f3b94d47ea958f91d3a99125cd55931d995f1` (`Merge pull request #63`, Unit A vocabulary on main).

## Frozen surfaces this unit leaves in place

| Surface | Location | Version |
| --- | --- | --- |
| CLI writer | `packages/vantio-cli/bin/interceptor.cjs` | `@vantio/cli` `0.3.24` |
| Python writer | `packages/vantio-agent-sdk-py/vantio/` | `vantio-agent-sdk` `3.1.0` |
| Node SDK | `packages/vantio-agent-sdk/` | `@vantio/agent-sdk` `0.2.4` |
| Evidence mapper | `packages/optics-evidence-contract/src/validate.py` | `0.0.0-unstable-pre-1.0` |
| Vocabulary | `packages/optics-record-vocabulary/` | `0.0.0-unstable-pre-1.0` |

The Python writer entrypoint is `shield` in `packages/vantio-agent-sdk-py/vantio/sdk.py`. Call rows are built in `_record` (`vantio/_http_observe.py`), which assigns `opticsStatus` `SUCCESS` before `_append`. The run file is written under the home runs directory. Envelope `mediation` is `",".join(mediations)` in that same module. Empty `shield()` writes no file.

## What Unit C adds

- `packages/optics-python-adapter/` — private package `vantio-optics-python-adapter` `0.0.0-unstable-pre-1.0`.
- `tests/optics-python-adapter/` — fixture score and isolation.
- `docs/internal/optics-pkg02-unit-c/` — these notes.

The package is not a pnpm workspace member. It is not `vantio-agent-sdk`. Claimed CPython for this force is 3.12, which is the interpreter that ran the suite.

## Shared corpus

Unit A fixtures: `packages/optics-record-vocabulary/fixtures/conformance-fixtures.json` (34 fixtures). This unit reads that file. It does not rewrite it.
