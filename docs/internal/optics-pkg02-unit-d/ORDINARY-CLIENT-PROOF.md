# PKG-02 Unit D ordinary-client proof

PRIVATE | FUTURE LINE | NOT PUBLISHED | NOT SEALED | NO UNIT E | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

The proofs run `vantio-pkg02 run node <script>` with `VANTIO_EXTRA_LLM_HOSTS=127.0.0.1`. They read the file under the runs directory. They do not read the frozen stderr line as the record.

| Proof | File result |
| --- | --- |
| One in-scope `POST` with `Content-Length: 2` | `observation_event`, optics `OBSERVED`, `http_status` `200`, `application_status` `SUCCESS`, `response_bytes` `2`, `issue_location` `NONE`, `action` `OBSERVED`. The request body canary is absent. |
| Empty `process.exit(0)` | Envelope optics `NOT_OBSERVED`, `call_count` `0`, `events` `[]`. |
| `200` with chunked transfer and no `Content-Length` | Optics `OBSERVED`. `response_bytes` is absent. |
| HTTP `500` with a length | Optics `OBSERVED`, `application_status` `APPLICATION_ERROR`, `issue_location` `PROVIDER_INTERACTION`. |
| Connection refused after the local server closes | Optics `OBSERVED`, `failure_kind` `network`, `issue_location` `NETWORK`, `application_status` `UNAVAILABLE`. `response_bytes` and `http_status` are absent. |

Every file has `record_type` `run_envelope`, `schema_version` `0`, `compatibility.legacy_schema_version` `2`, producer `node_interceptor`, `cli_or_sdk_version` `0.4.0-pkg02-unit-d`, `evidence_origin` `LOCAL_OBSERVATION`, and diagnostic `unicode_profile_id` `PKG01-UCD-16.0.0`.

`run_id` is the value the frozen writer would have stored as `trace_id`. The canonical file does not also store `trace_id`.

Prohibited keys absent from these files: `plane`, `data_note`, `residual`, `free_mode`, `est_spend_usd`.
