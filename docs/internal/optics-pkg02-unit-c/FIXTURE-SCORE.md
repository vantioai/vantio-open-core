# PKG-02 Unit C fixture score

PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

The score is the 34 fixtures in `packages/optics-record-vocabulary/fixtures/conformance-fixtures.json`.

For each fixture the adapter result must match:

- `expected_canonical`
- `expected_events`
- `record_emitted`
- `expected_unsupported_state`

The fixture object itself must be unchanged. No fixture projection stores `optics_status` `SUCCESS`.

Python `python-3-1-0` additionally requires `OPTIMISTIC_DEFAULT_FORBIDDEN`, `mediation_reading` `unknown`, and `started_at` `2026-07-01T00:00:00.100Z` while the input `ts` remains `2026-07-01T00:00:00.100000+00:00`.

The canonical JSON of the Python and CLI projections must be byte-identical to `canonicalJson` in the Unit A package.

Command:

```sh
python3 -m unittest discover -s tests/optics-python-adapter -v
```
