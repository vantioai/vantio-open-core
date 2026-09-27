# PKG-02 Unit A known limitations

PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

- This unit does not read or write live run logs. Fixture inputs are declarations.
- The runner is not a record converter. It rejects a bare call object. It does not implement `legacyEnvelopeToContract`.
- Canonical rows repeat the planning prose on each row, including fallback text that is identical across rows. That keeps each row self-contained. The file is large because of that repetition.
- `integrity` has no catalog field of its own. It is the `product_health` name `integrity_state` and the tokens `OK`, `FAILED`, `UNKNOWN`. This unit does not add a field.
- There is no catalog field for a reader version. Version identity is `schema_version`, `runtime_version`, `cli_or_sdk_version`, and the Unicode profile compatibility names.
- Frozen CLI and Python envelopes still carry live `schema_version` `2` on the declared input. Canonical `schema_version` is `0`. The diagnostics name `compatibility.legacy_schema_version` as the only retention slot. These fixtures do not emit a compatibility object.
- `generated_at` is not stored as `ended_at` in the CLI fixture. The alias still exists for a later reader matrix.
- The witnessed-trace and explicit-`OBSERVED` fixtures use `PKG02-FUTURE-CLI-UNASSIGNED`. That string is not a version that exists. Those fixtures do not authorize Units B–F.
- Node SDK `timestamp_ns` is carried as a decimal string because the integer is outside the safe JSON integer range. Node and the Python encoder both reject integers outside `-9007199254740991` through `9007199254740991`.
- The Python check compares canonical JSON bytes for fixture comparison documents and the safe-integer bounds. It is not a second validator and it does not import `vantio-agent-sdk`.
- `tools/build-vocabulary.cjs` and `tools/emit-fixtures.cjs` write only inside `vocabulary/` and `fixtures/`. A direct path outside those directories, including a symlink that leaves them, is refused before any write. The suite proves that refusal without leaving a probe file behind.
- The call bound of 64, the frozen writers, and the unresolved Founder decisions 2–13 are unchanged.
- `proof_manifest` stays out of this slice.
- No fixture claims matrix class `FULL`.
