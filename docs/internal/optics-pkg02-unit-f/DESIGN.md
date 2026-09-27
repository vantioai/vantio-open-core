# PKG-02 Unit F design

PRIVATE | INERT | NOT SHIPPED | READ_AND_EXPLAIN | NO_WRITE_BACK | NO_LIVE_WRITER | NO_MIGRATION | NO_STABLE_SCHEMA

Audience: INTERNAL_RESTRICTED

The reader is `@vantio/optics-record-reader`. `readRunFile` reads bytes, explains a copy, then reads the same path again and reports whether the bytes still match. `explainCopy` and `explainFixture` explain a value the caller already holds. They do not open a path string.

Interpretation goes through the merged Unit B adapter, which calls `validateEvidence` and `validateBytes` on copies. Those functions are the `legacyEnvelopeToContract` and `legacyCallToContract` reading. This package does not reimplement that mapper and does not activate it as a writer.

## Flow

1. Refuse a writer option before any read that could be confused with a write. `write`, `activate`, `emit`, `migrate`, `seal`, `publish`, and `sqlite` stay inactive.
2. For a file, read the bytes once. A missing path is `UNAVAILABLE`. An unreadable path or a directory is `OPTICS_ERROR`. Neither result is `NOT_OBSERVED`, and neither result creates a file.
3. Pass the bytes, text, or object to the adapter. The adapter copies before it maps.
4. Build a display from the detached reading. Each line names one dimension and one machine token. A gloss, when present, sits beside that token.
5. Read the file again. If the bytes differ, the explanation becomes `OPTICS_ERROR` and drops the record. The reader still does not write.

`explainCopy` of a path-like string returns `PATH_REFUSED` and does not open it. Opening is only `readRunFile`.

## Display rules

- `optics_status` and `optics_health` never render `SUCCESS`. A stored or legacy `SUCCESS` becomes `UNAVAILABLE` and sets `optimistic_default_forbidden`.
- `application_status` `SUCCESS` stays on the application dimension. It is not copied into `optics_status`.
- Missing optics input is class `absent`. Null optics input is class `null`. A token outside the enum is class `unknown`. Legacy or explicit `SUCCESS` is class `refused_success`. The raw unknown token is not stored.
- Explicit `OBSERVED` stays `OBSERVED`.
- `response_bytes` renders `absent`, `null`, or `0` as three different tokens.
- Reader labels stay the labels the contract already computed. `LEGACY_UNMARKED` and `IMPORTED` are not upgraded to `LOCAL_OBSERVATION`. Demo host `optics-demo.invalid` stays `SIMULATED_DEMO` on that observation. The envelope of a legacy demo file stays `LEGACY_UNMARKED`.

`live_writer_modified` stays false. `schema_version` on the reader result is `0`. Legacy `2` remains `compatibility.legacy_schema_version`.
