# PKG-02 Unit C adapter

PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

Public functions:

| Function | Behavior |
| --- | --- |
| `adapt_copy(source)` | Adapts a dict copy. A path, string, or bytes value is not opened. |
| `adapt_fixture(fixture)` | Adapts one Unit A fixture, including absent, unreadable, and malformed parse states. |
| `canonical_json(value)` | Contract canonical JSON for the projection. |

The returned reading always sets `writes_live_run_directory` false, `live_writer_modified` false, `events_invented` false, and `stable_schema` false. `posture` is the seven inert tokens. `claimed_cpython` is `3.12`.

`record_emitted` follows the fixture: a canonical object is emitted, and a null canonical is not. `events` is set for a multi-call run. A one-call run is a single canonical object.

Mapper defaults that Unit A does not declare (`sampling` `UNSAMPLED` when the input omitted sampling, `provider_id` `unknown` guessed from a provider string, `identity_conflict`, null spans, `ended_at` taken from `generated_at`) stay off the scored object. The mapper still ran on the copy. The projection is the Unit A reading.
