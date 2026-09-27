# PKG-02 Unit D record delta

PRIVATE | FUTURE LINE | NOT PUBLISHED | NOT SEALED | NO UNIT E | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

The same local `POST` workload was run with `@vantio/cli` `0.3.24` and with `0.4.0-pkg02-unit-d`. The written files differ as follows.

| Fact | `0.3.24` file | `0.4.0-pkg02-unit-d` file |
| --- | --- | --- |
| Top-level marker | `vantio_run_log` `"1"` | `record_type` `run_envelope` plus `events[]` of `observation_event` |
| `schema_version` | `2` | `0`, with `2` only at `compatibility.legacy_schema_version` |
| Run identity | `trace_id` | `run_id` holding that same kind of `0x` value. `trace_id` is absent |
| Optics token | No stored optics token. Display fills `SUCCESS` | `OBSERVED` on the call that was seen |
| Response size | `bytes` from the frozen exit map | `response_bytes` when `Content-Length` was present |
| Origin | Absent on the file | `LOCAL_OBSERVATION` with `producer` `node_interceptor` and `cli_or_sdk_version` `0.4.0-pkg02-unit-d` |
| Action | Frozen action string | `OBSERVED` on the observation. Enforcement tokens are not stored |
| Issue location | Absent | `issue_location` on the observation |
| Unicode | Absent | `diagnostics.unicode_profile_id` `PKG01-UCD-16.0.0` |
| Prohibited keys | `plane`, `data_note`, `residual`, `free_mode`, and `summary.est_spend_usd` are on the frozen file | Those keys are absent |

A Unit A reading of the frozen CLI fixture `cli-0-3-24` stays `UNAVAILABLE`, because that file has no optics token. The future writer of a seen call stores `OBSERVED`. Those are different acts: reading an old file, and writing a new one.
