# PKG-02 reader compatibility entry gates — catalog

PRIVATE | INERT | NOT SHIPPED | READ_AND_EXPLAIN | NO_WRITE_BACK | NO_LIVE_WRITER | NO_MIGRATION | NO_STABLE_SCHEMA

Audience: INTERNAL_RESTRICTED

Each gate id is fixed. `achievement` is `NOT_SHIPPED`. A pass still leaves Unit D and Unit E `NOT_AUTHORIZED`.

| Id | What the proof has to show |
| --- | --- |
| `mixed_version_directories` | CLI `0.3.24`, Python `3.1.0`, and a future canonical file in one directory. Bytes differ. Bytes match before and after the read. Legacy readings stay `LEGACY_UNMARKED`. |
| `legacy_records` | Legacy `schema_version` `2` stays on the file and on `compatibility.legacy_schema_version` for the CLI file. Python stored optics `SUCCESS` is refused. Neither reading accepts `LOCAL_OBSERVATION`. |
| `future_records` | Source `schema_version` `0`, `schema_status` `unstable-pre-1.0`, optics `OBSERVED`, origin `LOCAL_OBSERVATION`. The inert reader keeps those tokens. Application `SUCCESS` stays on the application field. The frozen display pairing is `UNSUPPORTED`. |
| `unknown_statuses` | Source token outside the optics enum. Reader class `unknown`. Health and record optics `UNAVAILABLE`. `optimistic_default_forbidden` is true. The raw token is absent from the explanation. |
| `absent_fields` | Source optics key absent. Reader class `absent`, not `unknown`. HTTP status, response bytes, and application status stay absent. Optics health is `UNAVAILABLE`. |
| `origin_preservation` | Import stays `IMPORTED` with original `LEGACY_UNMARKED`. Claimed local without provenance is read as `LEGACY_UNMARKED` while the file still says `LOCAL_OBSERVATION`. Demo observation stays `SIMULATED_DEMO`. Provenanced local origin stays `LOCAL_OBSERVATION`. |
| `reader_fallback` | Newer schema file keeps `schema_version` `99` and `schema_status` `stable-v9`. The detached record uses schema version `0`. Corrupt input is `OPTICS_ERROR` and is not `NOT_OBSERVED`. The absent path is `UNAVAILABLE` and is not created. |
| `no_unknown_to_success` | Every role's explanation has optics success false. Unknown health is not `SUCCESS`. Explicit `OBSERVED` is not replaced by `SUCCESS`. |
| `frozen_cli_honestly_unsupported` | Frozen display `opticsStatus` is `SUCCESS`. Disposition is `UNSUPPORTED`. Node SDK `0.2.4` payload emits no local record and does not mention `LOCAL_OBSERVATION`. |
| `rollback_without_record_rewriting` | Future origin and newer schema marker are still on disk after a refused writer option. Directory membership is unchanged. |
| `reader_refuses_unsafe_promotion` | Promote option does not set the reader origin to `LOCAL_OBSERVATION` and does not change bytes. Prohibited names are not echoed. Writer option reason is `WRITER_INACTIVE`. |

The direct test builds the CLI and Python files with the frozen `vantio run` and `shield()` writers in temporary homes, then copies those bytes into the gate directory. The original run files are hashed again after the evaluation.
