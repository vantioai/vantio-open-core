# PKG-01 boundary

Audience: INTERNAL_RESTRICTED

Phase 1 inventory for Slice 1. This note is the implementation boundary. It does not change live writers, and it does not declare a stable schema.

`schema_status`: `unstable-pre-1.0`

Option: **B**. A private contract package. CLI `@vantio/cli@0.3.24` and Python `vantio-agent-sdk` 3.1.0 do not load it.

Starting commit: `311f260a5f1bee1d3dc9b3734fd6910fb1116094`

## What this package is

`packages/optics-evidence-contract/` holds a machine-readable allowlist, denylist, enums, and normalization rules, plus hand-written Node and Python validators. Tests live under `tests/optics-evidence-contract/`. Nothing in this package is on a customer install path.

The validators return a result object. They do not write `~/.vantio/runs`, do not create a database, and do not replace a caller-supplied application result.

## Live Node writer (frozen)

File: `packages/vantio-cli/bin/interceptor.cjs` (read, not modified).

Version in `packages/vantio-cli/package.json`: `0.3.24`. Engines: Node `>=18.3.0`.

On process exit the interceptor writes one JSON object. Envelope keys written in source:

`vantio_run_log` `"1"`, `schema_version` `2`, `plane` `"optics"`, `data_note`, `trace_id` (`RUN_TRACE_ID`, from `VANTIO_TRACE_ID` or `randomUUID()`), `pid`, `ppid`, `node_version`, `platform`, `arch`, `started_at`, `generated_at`, `duration_ms`, `cli_version`, `free_mode`, `calls`, `summary`, `residual`.

Call keys written in that mapper: `hostname`, `provider` (including `guessProvider`), `method`, `path`, `scheme`, `request_bytes`, `bytes` (expression `call.bytes || 0`), `status`, `ok`, `content_type`, `duration_ms`, `action`, `ts`, `redactions`, `error`, `error_class`.

Summary includes `est_spend_usd`. Residual is prose. The Node run file does not set `schema_status` and does not set `evidence_origin`.

PII categories already named in the interceptor policy default are `ssn`, `email`, `credit_card`, and `phone`. That redactor runs on request bodies inside the live process. It is not this package, and this package does not change it. Slice 1 does not treat hashing or masking as a way to keep a secret.

Display tokens live in `packages/vantio-cli/bin/optics-cx.cjs`: `OBSERVED`, `NOT_OBSERVED`, `UNSUPPORTED`, `UNAVAILABLE`, `APPLICATION_ERROR`, `OPTICS_ERROR`, `PARTIAL`, `SUCCESS`. `applicationStatusFromHttp` maps 200–399 to `SUCCESS`, 400–599 to `APPLICATION_ERROR`, and any other or missing status to `UNAVAILABLE`. The stored `ok` boolean is not the application outcome. `PARTIAL` there is a mixed-run display rollup. It is a different field from run `lifecycle` `PARTIAL` and from query completeness.

Reader gate in `packages/vantio-cli/bin/vantio.js`: `loadRunLog` / `tryLoadRunLog` accept a file when `vantio_run_log === "1"`. They do not check `schema_version`. Those functions are not exported. Compatibility tests re-check the marker on fixture copies and call `applicationStatusFromHttp` from `optics-cx.cjs`. They do not start the CLI against `~/.vantio/runs`.

`vantio demo` writes `hostname` `optics-demo.invalid`, `provider` `openai`, `POST /v1/chat/completions`, status 200, `bytes` 0, `action` `OBSERVED`. The file has no origin field. The trace id it mints is `0x` plus hex. In today’s file that string is the run boundary.

## Live Python writer (frozen)

File: `packages/vantio-agent-sdk-py/vantio/_http_observe.py` (read, not modified).

Version in `pyproject.toml`: `vantio-agent-sdk` `3.1.0`. Requires Python `>=3.10`. Python 3.0.15 is not the target.

`_write_run_log` writes only when `_calls` is non-empty and `_trace_id` is set. Envelope keys: `vantio_run_log` `"1"`, `schema_version` `2`, `schema_status`, `plane` `"optics"`, `workflow` `"sight_loop"`, `data_note`, `status_labels`, `trace_id`, `runtime` `"python"`, `mediation` (comma-joined), `started_at`, `generated_at`, `calls`, `summary`, `residual`. It does not write `pid`, `ppid`, `free_mode`, `duration_ms`, or `est_spend_usd`.

Call objects are the in-memory records from `_record`: `hostname`, `provider`, `action`, `mediation`, `ts`, plus extras such as `status`, `ok`, `duration_ms`, `error_class`, `failure_kind`, `error`, and human outcome lines (`opticsStatus`, `applicationStatus`, `opticsLabel`, and customer outcome fields). `provider` defaults to `"other"` when the caller did not set one.

`SCHEMA_STATUS` in `vantio/_outcome.py` is `unstable-pre-1.0`. `__version__` is `3.1.0`.

## Fields the contract will not persist

From the live objects, these are outside the A1 allowlist and are omitted from contract output:

- `plane`, `data_note`, `residual`, `workflow`, `status_labels`, `free_mode`
- `summary`, including `est_spend_usd` and other cost or usage keys (Founder decision 2 stays unresolved; the safe default is exclusion)
- `ok` as an application outcome
- human prose: `opticsLabel`, `applicationOutcomeLabel`, `providerResponse`, `failure_response`, `nextAction`
- `provider` when it is a substring guess (`guessProvider`). Contract `provider_id` is `unknown` with `provider_confidence` `NONE` unless the caller already supplied an allowlisted id and a confidence the rules accept. This package does not copy the host catalog and does not guess a vendor from a hostname
- `error` message text, stack, args, header maps, cookies, prompts, completions, bodies
- machine hostname, username, working directory, environment, command line
- `redactions` counts, enforcement `action` values other than `OBSERVED`

Legacy `trace_id` on a `vantio_run_log` file is mapped to `run_id`. It is not copied into contract `trace_id`. A4 identifies that current field as the wrapped-process boundary. Contract `trace_id` is set only from a trace-context input that passes the hex rules, with an explicit basis. `VANTIO_TRACE_ID` shape on a contract record is `ASSERTED_CONTEXT`. It is not observation proof and it does not mint `run_id`.

Legacy `bytes` value `0` maps to `response_bytes` null. The frozen writer still stores `0`. This package does not change that writer.

## Privacy-sensitive sources seen on the write path

The live writers can be handed, or can copy, material the contract must refuse:

- URL query, fragment, and userinfo on destinations the hooks already parse into `hostname` / `path` / `scheme` (the stored split is structural; a future caller can still put a raw URL or a secret into `path` or `error`)
- `error` and exception text (`_record_http_exception` can set `error` to `network_error` and always stores `error_class`)
- header and cookie maps if a caller nests them on a record
- policy and telemetry identifiers (`anonymousId` is a telemetry-file concern, not an observation field)
- PII categories named in the interceptor: email, SSN, credit card, phone
- demo host `optics-demo.invalid`

Field-name denial is not enough. Values inside allowlisted strings are scanned.

## Reader compatibility

Current readers keep parsing today’s files. Contract normalization returns a new object. It does not write that object back over the fixture or into `~/.vantio/runs`.

A missing origin stays a reader label `LEGACY_UNMARKED`. It is not stored as `LOCAL_OBSERVATION`. Destination `optics-demo.invalid` yields `SIMULATED_DEMO`. Claimed `LOCAL_OBSERVATION` without recognized producer (`node_interceptor`, `python_observe`, `demo_command`), a version string of at most 32 characters in `[A-Za-z0-9._+-]`, and an allowlisted origin is `LEGACY_UNMARKED`. The demo producer does not preserve `LOCAL_OBSERVATION`.

## Fail-open

`interceptor.cjs` already swallows run-log write failures. `_write_run_log` returns on exception. The private validator matches that posture for its own API: internal failures become a result object, the supplied application result is returned unchanged, and no secret from the thrown value is copied into the result.

This does not prove the live CLI or Python process is fail-open. Those paths are not wired to this package.

## Out of scope for this package

SQLite, WAL, migrations, database files, retention, pruning, trends, alerting, UI, daemon, OTLP, SIEM, stable schema, public API, package publish, tag, seal, cost and token fields, machine hostname, customer promotion of `LEGACY_UNMARKED`, a seventh annotation origin, freshness `CURRENT`, numeric performance targets, and any edit under:

- `packages/vantio-cli/`
- `packages/vantio-agent-sdk-py/`
- `packages/vantio-agent-sdk/`
- `docs/architecture/optics-foundation/`
- `docs/planning/optics-foundation-a8/`

Gate 8 in `docs/architecture/optics-foundation/09-IMPLEMENTATION-GATES.md` still says closed. This force opens Gate 8 only for the private PKG-01 source. That architecture file is not edited.

## Risks recorded before coding

| Risk | Bound |
| --- | --- |
| Cross-language drift | One corpus. Canonical JSON compared byte for byte. Patterns are loops and ASCII classes, not mixed regex dialects |
| Hostile getters and cycles | Bounded walk. Getter throws and cycles become `REJECT_RECORD` with no exception text in the result |
| Recursion and size | Depth, key, array, node, and string caps. Over-long strings are dropped without storing a prefix |
| Secret in a diagnostic | Reason codes and remediation codes are a closed token set. Values are never interpolated |
| Unicode bypass | NFC check for session ids. NFKC and a confusable map are detection-only. The folded form is not stored |
| Percent-encoding and base64 | One detection decode. Decoded text is not stored. Invalid UTF-8 fails closed for that field |
| JSON number drift | Integers only, inside the safe integer range |
| Application mutation | Input objects are not written. Frozen-input tests cover that |
| False privacy pass | Removal is the disposition. No hash and no mask of a canary is stored |
| Scope leak | Scope tests fail if the CLI or Python package references this package, if versions move, or if a SQLite dependency appears |
