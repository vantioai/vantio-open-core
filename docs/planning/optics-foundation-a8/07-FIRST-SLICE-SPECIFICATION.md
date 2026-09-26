# Slice 1 specification

Audience: INTERNAL_RESTRICTED

**SLICE 1 — EVIDENCE CONTRACT AND WRITE-PATH PRIVACY BOUNDARY**

Package: `PKG-01`. Status in this plan: `PLANNED`.

This specification does not authorize implementation. Gate 8 stays closed. A8 is not started. The future force text in `08-FIRST-SLICE-FUTURE-FORCE.md` is marked `NOT AUTHORIZED`.

## 1. Goal

Create one shared, testable persistence-boundary contract for current Node and Python JSON records before any SQLite work.

A record that crosses the contract is:

- allowlisted
- normalized
- classified by evidence origin
- stripped of prohibited fields
- checked for privacy invariants
- given bounded diagnostic metadata on the validation result
- emitted as a contract object only after validation
- rejected or sanitized on a defined path when invalid
- accompanied by an explicit completeness impact when a field or event is dropped

The live CLI and the live Python writer do not call this contract in Slice 1. See section 4.

## 2. Included scope

1. Canonical persisted-field allowlist, taken from A1 section 4 for `run_envelope` and `observation_event`, plus the `derived_diagnostic` and `product_health` field lists as contract objects. Annotation and import quarantine field lists are fixtures for rejection behavior. Slice 1 does not build annotation storage or an importer.
2. Canonical prohibited-field denylist from A1 section 5.
3. Evidence-origin validation. Writer values are `LOCAL_OBSERVATION`, `SIMULATED_DEMO`, `IMPORTED`, `TEST_FIXTURE`, `PRODUCT_HEALTH`, `DERIVED_DIAGNOSTIC`. Missing origin is not stored as `LOCAL_OBSERVATION`. The reader disposition `LEGACY_UNMARKED` is a result label for legacy fixtures, not a seventh writer value.
4. Issue-location validation using A1 section 3, including `NONE`.
5. Optics, workload, and dependency status validation using the current `optics-cx.cjs` tokens and `application_status` `SUCCESS`, `APPLICATION_ERROR`, `UNAVAILABLE`, `NOT_OBSERVED`.
6. HTTP and network outcome validation. HTTP 2xx and 3xx use issue location `NONE`. HTTP 400–599 use `PROVIDER_INTERACTION` and application status `APPLICATION_ERROR`. Typed DNS, connection, TLS, or transport timeout with no HTTP status uses `NETWORK`. The human label for `PROVIDER_INTERACTION` is “Provider interaction.”
7. Destination sanitization. Host, explicit port, scheme, and path. Query, fragment, and userinfo are removed before persistence.
8. Query-string exclusion.
9. Header and credential exclusion. No header map is a persisted field.
10. Exception-detail sanitization. `error_class` is a type-name token. Exception messages, args text, and stack traces are omitted.
11. Session-id validation from A1 section 11, including basis pairing and `OPTICS_SESSION_ID_MAX_BYTES` = 80.
12. Trace-context validation from A4. Overlong, non-hex, or conflicting context is dropped. Baggage is dropped.
13. Structural redaction before write. The contract output is the redacted object. Unknown keys are omitted.
14. Privacy-invariant signal without the leaked value. The result carries a token such as `REDACTION_DROP`. It does not carry the secret.
15. Explicit rejection and sanitization behavior in section 6.
16. Completeness and Optics-health impact on the validation result, in section 7.
17. Node and Python conformance fixtures that both validators must pass.
18. Privacy regression corpus in section 5.
19. Fail-open application behavior in section 8.
20. JSON-record compatibility with current readers in section 4.

`schema_status` on contract-shaped objects is `unstable-pre-1.0`. `schema_version` stays unassigned. Examples may use `0` to mean unassigned. That is not a stable schema.

## 3. Excluded scope

SQLite. Database schema. Database binding. WAL. Migrations. Legacy import execution. Retention. Pruning. Trends. Alerting. UI. Daemon. OTLP. SIEM export. A stable schema. A public API. New product telemetry. Cost or token usage. At-rest encryption. Machine hostname. Customer promotion of `LEGACY_UNMARKED`. An annotation-origin extension. Freshness token `CURRENT`. Numeric performance targets.

Also excluded: edits to `packages/vantio-cli/**`, `packages/vantio-agent-sdk-py/vantio/**`, `packages/vantio-agent-sdk/**`, workflows, package versions of existing packages, tags, and registries.

## 4. Compatibility

Slice 1 preserves:

- CLI 0.3.24 behavior. The package is frozen. `interceptor.cjs` and `vantio.js` stay as they are.
- Python 3.1.0 source behavior. `_http_observe.py` stays as it is. Python 3.0.15 is not the target.
- Existing run readers, proof renderers, and the status tokens in `optics-cx.cjs`.
- `schema_status: unstable-pre-1.0` where it already appears, and the legacy file marker `vantio_run_log` `"1"` with legacy `schema_version` 2.
- Prompts and completions absent from stored records.
- Telemetry opt-in, with `VANTIO_TELEMETRY_DISABLED=1` and `DO_NOT_TRACK=1` overriding `VANTIO_TELEMETRY=1`.
- Account-free local use.
- Application fail-open behavior. The contract API returns a result object. It does not change a caller-supplied application result.

### 4.1 Options for where the contract lives

| Option | Slice 1 effect |
| --- | --- |
| A | A future CLI version loads the contract on the live Node writer |
| B | A private contract package exists and is not loaded by CLI 0.3.24 or by the Python 3.1.0 import path |
| C | Node and Python customer behavior change in staged releases |

**Recommendation: option B for Slice 1.**

The Node writer lives in the frozen CLI. Changing it is option A and needs a later CLI version. Python 3.1.0 is merged source without a seal. Changing its writer inside Slice 1 would change that source’s behavior before the corpus is a release gate. Option C is the cutover shape for PKG-02 after Slice 1, not the Slice 1 shape.

Tests may call current reader functions without modifying their files. They assert that fixtures of today’s Node and Python envelopes still parse and that their existing status tokens still mean what the inventory records.

### 4.2 Current envelopes the contract must tolerate as legacy fixtures

Node exit object, inventory finding 1.2: `vantio_run_log`, `schema_version` 2, `plane`, `data_note`, `trace_id`, `pid`, `ppid`, `node_version`, `platform`, `arch`, `started_at`, `generated_at`, `duration_ms`, `cli_version`, `free_mode`, `calls`, `summary`, `residual`. Call keys include `hostname`, `provider`, `method`, `path`, `scheme`, `request_bytes`, `bytes`, `status`, `ok`, `content_type`, `duration_ms`, `action`, `ts`, `redactions`, `error`, `error_class`. Summary may contain `est_spend_usd`.

Python object, inventory finding 2.2: adds `schema_status`, `workflow` `"sight_loop"`, `runtime`, `mediation`, `status_labels`. It omits pid, ppid, and zero-call files. Call objects may contain human outcome lines.

Contract behavior on those fixtures:

- They remain readable by current readers.
- A contract normalization result may map known structural fields into the target names.
- `workflow`, `est_spend_usd`, `plane`, `data_note`, `residual`, human prose, and other keys outside the allowlist are omitted from the contract output.
- Omitted cost fields do not resolve decision 2. They implement the safe default.
- Missing origin on the fixture yields result disposition `LEGACY_UNMARKED`.
- Destination `optics-demo.invalid` yields `SIMULATED_DEMO`.
- The contract output is not written back over the fixture file.

`bytes` stored as `0` when the length was unknown is an inventory defect. The target field `response_bytes` is null when unknown. Slice 1’s normalizer uses null for a missing length. It does not change the frozen writer that stores `0`.

## 5. Privacy corpus

Each fixture is deterministic. The expected disposition is one of: reject the field or the event, strip the prohibited part and keep structural fields that remain valid, normalize a structural value, or retain an allowlisted value that contains no prohibited content.

Hashing a secret and storing the digest is not a disposition in this corpus. Removal is the disposition. Import `content_sha256` and proof `proof_sha256` belong to later packages and are not used to keep a canary.

| Fixture | Expected disposition |
| --- | --- |
| Authorization bearer token in a header map | Header map is not a field. If the token is copied into an allowlisted string, omit that field or drop the event. Retain no token bytes |
| Basic auth | Same as bearer |
| Cookie or `Set-Cookie` | Same as bearer |
| API key in a query string | Strip the query. Retain host, explicit port, scheme, and path when those parts are otherwise clean. If stripping fails, omit destination fields |
| URL userinfo | Strip userinfo. Retain host and path when they are clean. Do not retain the userinfo |
| OpenAI-like key (`sk-` shape) inside a persisted string | Omit the field or drop the event. Do not store a mask or a hash |
| Cloud credential string inside a persisted string | Omit the field or drop the event |
| Session token inside a persisted string | Omit the field or drop the event. A valid `session_id` that fails the secret check is omitted together with `session_id_basis` |
| Private-key marker (`BEGIN` private key banner) inside a persisted string | Omit the field or drop the event |
| Database URL with credentials | Do not store the URL. Strip fails closed: omit destination fields |
| Email canary inside `path`, `destination_host`, `error_class`, annotation text, or another persisted string | Omit that field or reject the annotation text |
| Financial identifier canary (payment-card pattern) in those strings | Omit that field |
| Health-data canary in those strings | Omit that field |
| Unicode lookalike of an `sk-` style token | Omit the field. Do not normalize the lookalike into a stored token |
| Percent-encoded canary | Omit the field. Do not decode it into storage |
| Base64-wrapped canary | Omit the field. Do not decode it into storage |
| Nested arrays or objects on unknown keys | Omit the unknown keys. Do not keep a nested copy “for later” |
| Exception message and exception args containing a canary | Omit the message and args. `error_class` may retain the type-name token when that token itself matches `[A-Za-z0-9_]` and contains no canary |
| Trace baggage | Drop baggage. It is not stored. A valid trace id beside it may remain, with its basis |
| Customer annotation text containing a canary | Reject the annotation text. Do not write it onto the observation. Slice 1 does not open an annotation store |
| Imported-record-shaped object containing a canary | Prohibited fields are absent from the contract output. Origin is not rewritten to `LOCAL_OBSERVATION`. Slice 1 does not run an importer |
| Malformed UTF-8 in `session_id` or another text field | Reject the field. Session id and basis are both omitted |
| Oversized path (over 512 characters) or oversized session id (over 80 UTF-8 bytes) | Reject the whole value. Do not truncate |
| Filesystem path containing a username | Omit the field. Working directory and home paths are not allowlisted |
| Prompt or completion canary, including a message array | Drop the field or the event. Prompts and completions are never stored |

Clean structural values are retained after normalization: lowercase DNS host, IP literal without brackets, explicit port only, scheme enum, path without query or fragment, HTTP status integer, byte lengths that were actually observed, and allowlisted enums.

Normalization that is not a secret disposition: lowercase DNS host, strip query and fragment and userinfo, drop content-type parameters, leave default ports null unless the URL showed an explicit port.

A fixture passes only when the prohibited bytes are absent from the contract output and absent from any diagnostic string on the result.

## 6. Rejection and sanitization

| Condition | Result |
| --- | --- |
| Unknown key | Omitted |
| Prohibited value inside an allowlisted string | Field omitted, or the whole event dropped when the field cannot be separated. Result token `REDACTION_DROP`. Secret absent from the result |
| Query strip succeeds | Destination kept without the query |
| Query strip or userinfo strip fails | Destination fields omitted. Result token `REDACTION_DROP` |
| Path longer than 512 characters | Path omitted. Not truncated |
| Session id invalid, overlong, not NFC, or missing basis | Both `session_id` and `session_id_basis` omitted. Result token `SESSION_ID_REJECTED` |
| Trace context malformed, oversized, or not in the accepted hex forms | Trace fields null. Context bytes absent. Result token `CONTEXT_REJECTED` |
| Two accepted contexts disagree | Neither is stored as parent. Issue location `CONFIGURATION` on the diagnostic result. Local `run_id` kept when it was already valid |
| Baggage present | Baggage omitted |
| Missing evidence origin on a legacy fixture | Disposition `LEGACY_UNMARKED` |
| Claimed `LOCAL_OBSERVATION` without recognized producer, version, and provenance | Disposition `LEGACY_UNMARKED` |
| Demo destination `optics-demo.invalid` | `SIMULATED_DEMO` |
| `response_bytes` unknown | Null. Not zero |

Recognized producers for a provenance check are `node_interceptor`, `python_observe`, and `demo_command`, with the rules in A1 section 2. The demo producer does not preserve `LOCAL_OBSERVATION`.

## 7. Completeness and health impact

The validation result carries:

- `completeness_impact`: `NONE` or one or more of `REDACTION_DROP`, `SESSION_ID_REJECTED`, `CONTEXT_REJECTED`, `EVENT_DROPPED`
- `health_signals`: counts only, names drawn from the A5 set that apply at the boundary (`events_rejected`, `redaction_failures`, `session_id_rejected`, `rejected_context`)
- no payload, no canary, no hostname of the customer machine

Slice 1 does not write a `product_health` row to disk. The signals are on the result object so PKG-03 and PKG-10 can map them later. A dropped event is an impact of `EVENT_DROPPED`. A later default query that includes that gap is `PARTIAL` with `DROPS_IN_SCOPE`. Slice 1 does not implement that query. It does record the impact that makes the later envelope honest.

`optics_status` on a contract object is `SUCCESS` only when the contract produced an observation object. A dropped event does not get `optics_status` `SUCCESS`.

## 8. Fail-open

The contract function catches its own failures. The caller receives a result. A test supplies an application return value and asserts it is unchanged when:

- validation omits a secret
- validation drops an event
- the validator throws internally
- the input is malformed UTF-8
- the input is enormous

The contract does not hang the caller and does not replace the application result with an Optics error. Enforcement block, redact, and cap paths stay outside this invariant. Slice 1 does not extend them.

## 9. Future release gates

These gates are unsatisfied. This planning document satisfies none of them.

| Gate | Name |
| --- | --- |
| S1-G1 | Source inventory and compatibility plan accepted |
| S1-G2 | Shared contract accepted |
| S1-G3 | Node implementation tests pass |
| S1-G4 | Python implementation tests pass |
| S1-G5 | Cross-package conformance passes |
| S1-G6 | Privacy corpus passes with zero prohibited persistence |
| S1-G7 | Fail-open adversity tests pass |
| S1-G8 | Independent council passes the exact source tip |
| S1-G9 | Sealed artifacts independently verified |
| S1-G10 | Ordinary-client proof passes |

S1-G9 and S1-G10 apply when a later force ships the contract on a customer install path. Option B by itself does not seal and does not publish.

## 10. Stop

Slice 1 implementation is not opened by this file.
