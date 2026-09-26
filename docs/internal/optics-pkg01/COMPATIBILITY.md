# PKG-01 compatibility

Audience: INTERNAL_RESTRICTED

Compatibility fixtures are copies. The contract output is not written back over them, and the live writers are not modified.

A Node-shaped envelope (`vantio_run_log` `"1"`, `schema_version` 2, `calls`) maps the legacy `trace_id` string onto contract `run_id`. It does not become the contract `trace_id`. Missing origin yields reader label `LEGACY_UNMARKED` and disposition `REPLACE_WITH_SAFE_CATEGORY`. `schema_version` on the contract record is `0`. The legacy integer is kept only on `compatibility.legacy_schema_version`. `plane`, `data_note`, `free_mode`, `summary`, and `residual` are omitted. `est_spend_usd` is not in the output.

A call's `bytes` value `0` becomes `response_bytes` null. An explicit contract `response_bytes` of `0` is kept. `provider` is not inferred from the legacy string; `provider_id` is `unknown` and `provider_confidence` is `NONE` unless the caller supplied an allowlisted token. Content-type parameters are dropped.

A Python-shaped envelope is recognized when `runtime` is `python` or `workflow` is `sight_loop`. `workflow` and `status_labels` are omitted. `schema_status` `unstable-pre-1.0` is preserved. Mediation must be one of the closed tokens or it becomes `unknown`.

`applicationStatusFromHttp` in this package matches `packages/vantio-cli/bin/optics-cx.cjs` for integer statuses: 200–399 `SUCCESS`, 400–599 `APPLICATION_ERROR`, otherwise `UNAVAILABLE`. The compatibility test calls that frozen helper directly. It does not import `vantio.js` and it does not start a CLI against `~/.vantio/runs`.

Python `SCHEMA_STATUS` in `vantio/_outcome.py` remains `unstable-pre-1.0`. The test reads that source. It does not call `shield` or `install`.
