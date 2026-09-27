# PKG-02 Unit A compatibility fixtures

PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

File: `packages/optics-record-vocabulary/fixtures/conformance-fixtures.json`.

34 fixtures. Each one sets `writes_live_run_directory` false, `achievement` `NOT_SHIPPED`, and `stable_schema` false. The runner returns a canonical comparison document. It does not write a file.

No fixture uses compatibility class `FULL`. `FULL` would mean two conformant future records. Nothing here is shipped.

## Force scenarios

| Fixture | What it declares |
| --- | --- |
| `cli-0-3-24` | Frozen CLI envelope and one HTTP 200 call. Legacy `trace_id` becomes `run_id`. `ok` is not stored. Provider string is not an allowlisted `provider_id`. |
| `python-3-1-0` | Frozen Python call whose live `opticsStatus` is `SUCCESS`. Canonical optics health is `UNAVAILABLE`. Joined `mediation` is not one token. `+00:00` is declared as `Z` with three fractional digits. |
| `node-sdk-0-2-4` | Ingest payload. `record_emitted` false. `UNSUPPORTED`. `timestamp_ns` stays a decimal string. |
| `empty-shield` | Python empty shield. No file. `UNAVAILABLE`, not `NOT_OBSERVED`. |
| `no-file` | Reader path absent. `UNAVAILABLE`, not `NOT_OBSERVED`. |
| `missing-status` | Missing optics status, action, HTTP status, and bytes. |
| `unknown-status` | `SUPER_SUCCESS` becomes `UNAVAILABLE` with `OPTIMISTIC_DEFAULT_FORBIDDEN`. |
| `missing-action` | Action key omitted. |
| `bytes-missing` | `response_bytes` omitted. |
| `legacy-bytes-zero` | Legacy `bytes` 0 becomes `response_bytes` null. |
| `explicit-response-bytes-zero` | Canonical `response_bytes` 0 stays 0. Declared future input, frozen reader `UNSUPPORTED`. |
| `inherited-trace` | Basis `ASSERTED_CONTEXT`, not `OPTICS_GENERATED`. |
| `imported-evidence` | `IMPORTED` and original origin kept. Class `READ_ONLY`. |
| `simulated-evidence` | Host `optics-demo.invalid` is `SIMULATED_DEMO` on that observation. |
| `partial-run` | `lifecycle` `PARTIAL`. Per-call application tokens are not `PARTIAL`. |
| `interrupted-run` | `lifecycle` `INTERRUPTED`. Pre-completion `duration_ms` 0 is not stored. |
| `corrupt-record` | Malformed JSON. No record. `OPTICS_ERROR`. Not an empty object. |
| `unknown-enum` | Method `FLY` is omitted and named in the diagnostic. |
| `future-field` | `freshness` `CURRENT`, `widget_hint`, and `cost` are not promoted. |
| `compatibility-alias` | Alias keys are absent from the canonical object. Class `REQUIRES_ALIAS`. |
| `provider-http-error` | HTTP 500, `APPLICATION_ERROR`, `PROVIDER_INTERACTION`. |
| `dns-failure`, `connection-failure`, `tls-failure` | Transport kind kept. String `network_error` is not the enum. Issue location `NETWORK`. |
| `customer-application-exception` | `wrapped` plus `ValueError`. Issue location `CUSTOMER_APPLICATION`. |
| `successful-http-response` | HTTP 200 workload `SUCCESS`, optics `UNAVAILABLE`. |

## Additional declarations

These lock the same rules. They are not later units.

| Fixture | Why it is here |
| --- | --- |
| `cli-empty-call-file` | A CLI file with `calls: []` is `NOT_OBSERVED`. A missing file is not. |
| `unreadable-record` | Unreadable bytes are `OPTICS_ERROR`, not `NOT_OBSERVED`. |
| `timeout-failure` | `failure_kind` `timeout` is the same network rule as DNS, connection, and TLS. |
| `sampling-not-success` | A non-`UNSAMPLED` token normalizes to `UNSAMPLED` and is not optics success. |
| `claimed-local-without-provenance` | Claimed `LOCAL_OBSERVATION` without producer and version stays `LEGACY_UNMARKED`. |
| `redirect-3xx` | HTTP 302 is workload `SUCCESS`. No hop is invented. |
| `witnessed-trace` | Basis `OPTICS_GENERATED` only with the witness present on input and absent on output. Placeholder version `PKG02-FUTURE-CLI-UNASSIGNED`. Not a writer authorization. |
| `explicit-observed-not-default` | Explicit `OBSERVED` is preserved. Missing status does not become `OBSERVED`. |

Producer versions on these fixtures are only `0.3.24`, `3.1.0`, `0.2.4`, null, or the unassigned placeholder. The placeholder is not a release.
