# PKG-02 Unit B compatibility fixtures

PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

The adapter scores the 34 Unit A fixtures in `packages/optics-record-vocabulary/fixtures/conformance-fixtures.json`. It does not add a second fixture corpus and it does not edit those declarations.

Each expected canonical key must appear with the same value on the detached envelope or on a detached event. `optics_health` is not counted as `optics_status`. `cli-empty-call-file` stores `optics_status` `NOT_OBSERVED` on the envelope. `inherited-trace` stores `optics_status` `UNAVAILABLE` on the envelope. Alias keys and `fields_not_promoted` tokens are absent from those records. `record_emitted` matches the fixture. Reader origin matches `evidence_origin` when the fixture names one.

Python-shaped fixtures are scored here so the Node adapter and a later Python adapter can be compared on the same declarations. Scoring them does not import `vantio-agent-sdk` and does not change `3.1.0`.

`generated_at` on the CLI fixture remains on the detached envelope as `ended_at`, labeled as write time. The Unit A expected object does not list that key. The score checks the keys the fixture does list.

A frozen CLI reader of a future record is not updated. The adversarial test calls `displayCall` and records that it still says `SUCCESS` while the adapter says `UNAVAILABLE`.
