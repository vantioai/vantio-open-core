# PKG-02 Unit D rollback

PRIVATE | FUTURE LINE | NOT PUBLISHED | NOT SEALED | NO UNIT E | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

`VANTIO_PKG02_WRITER=0` disables the new writer for the next run. That run writes `vantio_run_log` `"1"`, `schema_version` `2`, and `cli_version` `0.3.24`.

The canonical file from the earlier run stays on disk when the next run uses a new trace id. Its bytes do not change. `evidence_origin` stays `LOCAL_OBSERVATION`. The file is not deleted and not converted back into a `SUCCESS` record.

`readRolledBack` on that file reports `classification` `UNSUPPORTED`, `optics_status` `UNSUPPORTED`, `schema_status` `unstable-pre-1.0`, and `schema_version` `0`. The schema marker is the pair of `schema_status` and `schema_version`. The reader does not rewrite the file.

`displayCall` from CLI `0.3.24` still returns optics `SUCCESS` for a call row. The rollback result does not use that return value. CLI `0.3.24` remains `UNSUPPORTED` as a reader of the canonical file.

A validator fault does not change the child exit code. `VANTIO_PKG02_INJECT_FAULT=1` with `process.exit(4)` exits `4` and writes `optics_status` `OPTICS_ERROR`. The in-process application result is returned unchanged and is not copied into the file.

Reusing one `VANTIO_TRACE_ID` still overwrites that trace's file, because the frozen path is the trace id. Rollback does not delete other files. The proof uses a new trace id so the canonical file remains.
