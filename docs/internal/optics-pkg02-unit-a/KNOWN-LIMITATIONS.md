# PKG-02 Unit A known limitations

PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

- This unit does not read or write live run logs. Fixture inputs are declarations.
- The runner is not a record converter. It rejects a bare call object. It does not implement `legacyEnvelopeToContract`.
- Canonical rows repeat the planning prose on each row, including fallback text that is identical across rows. That keeps each row self-contained. The file is large because of that repetition.
- `integrity` has no catalog field of its own. It is the `product_health` name `integrity_state` and the tokens `OK`, `FAILED`, `UNKNOWN`. This unit does not add a field.
- There is no catalog field for a reader version. Version identity is `schema_version`, `runtime_version`, `cli_or_sdk_version`, and the Unicode profile compatibility names.
- Legacy `schema_version` `2` is not emitted as `compatibility.legacy_schema_version` by these fixtures. The CLI and Python diagnostics say that a future read may retain it only there.
- `generated_at` is not stored as `ended_at` in the CLI fixture. The alias still exists for a later reader matrix.
- The witnessed-trace and explicit-`OBSERVED` fixtures use `PKG02-FUTURE-CLI-UNASSIGNED`. That string is not a version that exists. Those fixtures do not authorize Units B–F.
- Node SDK `timestamp_ns` is carried as a decimal string because the integer is outside the safe JSON integer range used by the neutral encoder.
- The Python check compares canonical JSON bytes for fixture comparison documents and a few vectors. It is not a second validator and it does not import `vantio-agent-sdk`.
- `tools/build-vocabulary.cjs` and `tools/emit-fixtures.cjs` can write their JSON artifacts when invoked as programs. The test suite calls the in-memory builders and does not write them.
- The call bound of 64, the frozen writers, and the unresolved Founder decisions 2–13 are unchanged.
- `proof_manifest` stays out of this slice.
- No fixture claims matrix class `FULL`.
