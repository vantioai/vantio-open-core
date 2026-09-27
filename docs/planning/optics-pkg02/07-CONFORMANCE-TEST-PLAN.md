# Optics PKG-02 — conformance test plan

Audience: INTERNAL_RESTRICTED

This is a plan for tests a future force would add. This force adds none. Existing PKG-01 fixtures stay as they are. CLI and Python tests that lock today's `SUCCESS` default stay as they are until a future versioned writer exists. Those tests are evidence of current behavior, not failures to fix inside 0.3.24 or 3.1.0.

Where two languages store the same semantic value, the future comparison is byte-for-byte on the contract's canonical JSON. Timestamp normalization and alias renaming happen before that comparison. The live file is not the canonical bytes.

## 1. Vocabulary and enums

- Every catalog name accepted on the record class that owns it.
- A closed enum outside its set follows the catalog invalid disposition.
- `action` other than `OBSERVED` is `ENFORCEMENT_ACTION_EXCLUDED` and the observation is not emitted.
- `sampling` other than `UNSAMPLED` is stored as `UNSAMPLED` and is not treated as success.
- `schema_status` other than `unstable-pre-1.0` is corrected. The reason is visible.
- `schema_version` on the contract record is `0`. Legacy `2` appears only as `compatibility.legacy_schema_version`.

## 2. Absence, null, and unknown

One fixture each, Node and Python adapters, same canonical bytes:

| Input | Stored result |
| --- | --- |
| `optics_status` missing | `UNAVAILABLE` |
| `optics_status` `SUPER_SUCCESS` | `UNAVAILABLE` and `OPTIMISTIC_DEFAULT_FORBIDDEN` |
| `action` missing | key omitted |
| `http_status` missing | key omitted, not `200`, not `0` |
| `bytes` `0` | `response_bytes` null |
| `response_bytes` `0` | `response_bytes` `0` |
| `bytes` missing | `response_bytes` omitted |
| origin missing | reader label `LEGACY_UNMARKED` |
| origin `LOCAL_OBSERVATION` without producer | reader label `LEGACY_UNMARKED` |
| inherited trace without witness | basis `ASSERTED_CONTEXT`, not `OPTICS_GENERATED` |
| corrupt JSON | no record, not an empty success |
| reader cannot open the path | `UNAVAILABLE` or `OPTICS_ERROR`, not `NOT_OBSERVED` |
| `failure_kind` missing | omitted, and `application_status` is not implied `SUCCESS` |

`null` span on the envelope stays null. Absent span is not the same fixture as null span when the catalog distinguishes them.

## 3. Status dimensions

A single HTTP 500 fixture stores `http_status` 500, `application_status` `APPLICATION_ERROR`, `optics_status` `OBSERVED` when the future writer saw the call, and `issue_location` `PROVIDER_INTERACTION`. It does not store `optics_status` `SUCCESS`. It does not store `ok`.

A mixed run stores two application tokens and `lifecycle` `PARTIAL` or a derived label `Partial`. It does not store `application_status` `PARTIAL`.

`vantio status` style facts (install version, registry, telemetry posture, importable packages) are not fixtures for `optics_status`. If a future product-health record is written, it uses `product_health` and `evidence_origin` `PRODUCT_HEALTH`.

## 4. Issue location and origin

Fixtures for `NETWORK` (transport kind, no HTTP status), `CUSTOMER_APPLICATION` (`wrapped` or `error_class` and no HTTP status), `COVERAGE`, `CONFIGURATION`, `ENVIRONMENT`, `OPTICS` (validator fault), and `UNKNOWN`. `Provider fault` is rejected as a customer label.

Demo host `optics-demo.invalid` stores `SIMULATED_DEMO` on that observation. A second fixture with the same host and `producer` `demo_command` claiming `LOCAL_OBSERVATION` stays unmarked rather than local.

Import fixture stores `IMPORTED` and the original origin unchanged.

## 5. Trace, session, time, and bytes

- Witness present with producer and version: basis `OPTICS_GENERATED`, witness absent from output.
- CLI `0x` trace string: `run_id`, not `trace_id`.
- Python `uuid4` string: `run_id`, not `trace_id`.
- Session over 80 UTF-8 bytes: `SESSION_ID_REJECTED`, value omitted, not truncated.
- CLI `Z` timestamp and Python `+00:00` timestamp of the same instant: identical canonical `started_at`.
- Non-zero offset: rejected, not converted.
- `generated_at` mapped to `ended_at` is labeled as write time in the fixture note.
- Dispatch-style `duration_ms` `0` with `status` null is not a completed measurement in the future-writer fixture. The adapter of a legacy file may surface it as a normalized zero only with the legacy marker, and the test name says it was pre-completion input.
- Missing content-length: `response_bytes` omitted in the future-writer fixture. Legacy CLI `bytes` `0` becomes null in the adapter fixture.

## 6. HTTP, network, async, and streaming

- 200, 302, 404, 500, and a non-integer status.
- DNS, connection, TLS, timeout, and `wrapped`, with and without a final HTTP status. The HTTP status wins when both are present.
- One asyncio client and one callback client. The record appears after completion.
- A stream that ends: byte count present. A stream that does not: `response_bytes` omitted and lifecycle `PARTIAL` or `INTERRUPTED`.
- Redirect: one event for the observed request. No invented hop. 3xx is `application_status` `SUCCESS` and `optics_status` `OBSERVED`, not optics `SUCCESS`.

## 7. Unicode, privacy, and aliases

- Profile id in the diagnostic is `PKG01-UCD-16.0.0` on every runtime under test.
- A fixture the pinned profile rejects is rejected on Node and on each claimed CPython. Host `unicodedata` is not the oracle.
- Prohibited names `prompt`, `plane`, `est_spend_usd`, `anonymousId`, and `machine` are absent from canonical output.
- Alias fixture: `opticsStatus`, `applicationStatus`, `hostname`, `status`, `bytes`, `ts`, `pid`, `trace_id` on an envelope. Canonical names are the stored names. Aliases are not a second copy.
- No caller object is retained. A mutating getter fixture still shows zero calls, matching the existing contract hostile-object rule.

## 8. Readers, mix, rollback, and fail-open

- Old-reader fixture: a canonical file fed to the frozen display rules is classified `UNSUPPORTED` by the test oracle. The test does not change `optics-cx.cjs`. It documents that `displayCall` would still say `SUCCESS`, which is why the matrix forbids that pairing.
- Mixed-version fixture: a 0.3.24 file and a canonical file in one directory. Neither file's bytes change.
- Rollback fixture: after a simulated writer rollback, the canonical file is still present, origin is unchanged, and the reader result is `UNSUPPORTED` with `schema_status` visible.
- Fail-open fixture: the application return value is unchanged when the validator rejects the record.
- No secret persistence: canary tokens from the PKG-01 corpus stay absent.

## 9. Where the tests live

Future tests belong to Units A–C and F. They do not replace `tests/optics-evidence-contract/` and they do not edit `packages/vantio-cli/test/` or `packages/vantio-agent-sdk-py/tests/` on the frozen lines. A later activation force may add tests inside the future package trees named in `08` and `09`. This plan does not create those trees.
