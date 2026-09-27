# Status tokens

JSON records use schema_status `unstable-pre-1.0`. That shape may change without notice.

## Optics display vocabulary

These tokens are the `VOCABULARY` list in `packages/vantio-cli/bin/optics-cx.cjs`.

- `OBSERVED`
- `NOT_OBSERVED`
- `UNSUPPORTED`
- `UNAVAILABLE`
- `APPLICATION_ERROR`
- `OPTICS_ERROR`
- `PARTIAL`
- `SUCCESS`

A recorded call uses Optics status `SUCCESS`. Application status comes from the HTTP status: `SUCCESS` for 200–399, `APPLICATION_ERROR` for 400–599, otherwise `UNAVAILABLE`. `PARTIAL` is a mixed-run rollup. The stored `ok` boolean is not the application outcome.

## SDK action tokens

`VantioActionTaken` in `@vantio/agent-sdk` includes enforcement tokens used when a Phantom Engine / Enterprise policy is applied. Free Optics display copy does not use the block or redact tokens as the Observe outcome.

- `OBSERVED`
- `ALLOWED`
- `REDACTED`
- `BLOCKED_HOST`
- `BLOCKED_SIZE`
- `BLOCKED_SPEND`
- `ENFORCEMENT_GAP`
- `DRY_RUN_BLOCKED_HOST`
- `DRY_RUN_BLOCKED_SIZE`
- `DRY_RUN_BLOCKED_SPEND`
