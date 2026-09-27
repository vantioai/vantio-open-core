# Future Force template — Python Optics writer integration

Audience: INTERNAL_RESTRICTED

Status: `NOT AUTHORIZED`

Status: `DRAFT FOR FOUNDER REVIEW`

Status: `DO NOT EXECUTE`

This template is not a Force. It does not start work. It does not alter `vantio-agent-sdk` `3.1.0`. It does not publish `3.1.0`. It does not publish `3.0.15`. It does not edit `packages/vantio-agent-sdk-py/vantio/` or `pyproject.toml` on that line.

## 1. Identity placeholders

| Item | Placeholder |
| --- | --- |
| Starting commit | `PKG02-FUTURE-START-SHA-UNASSIGNED` |
| Package | `vantio-agent-sdk` |
| Future version | `PKG02-FUTURE-PYTHON-UNASSIGNED` |
| Current source that stays put | `3.1.0` |
| Never the vehicle | `3.0.15` |
| Contract | `@vantio/optics-evidence-contract` `0.0.0-unstable-pre-1.0`, still private |
| Unicode profile | `PKG01-UCD-16.0.0` |

The starting commit is filled only when a Founder Force is actually issued. It is not this planning tip.

## 2. Allowed paths, once authorized

- A future Python package version `PKG02-FUTURE-PYTHON-UNASSIGNED`, not a patch on the 3.1.0 tree.
- Inert adapter first (Unit C), then the shared reader (Unit F), then writer activation (Unit E).
- Tests on the CPython versions the future force claims, using the pinned Unicode profile rather than host `unicodedata`.

Out of that future force:

- The 3.1.0 sources and the tests that lock `opticsStatus` `SUCCESS`
- `packages/vantio-cli/`
- PKG-01 tables and fixture hashes, unless a separate contract force says otherwise
- PyPI, TestPyPI, Twine, a release candidate, a seal
- SQLite, migrations, UI, daemon, OTLP, SIEM, alerting
- PR #59

## 3. Required order inside the future force

1. Land the inert adapter. `shield()` on 3.1.0 is not redirected at it.
2. Prove a 3.1.0 run file is byte-identical with the adapter present and unused.
3. Prove a missing `optics_status` becomes `UNAVAILABLE`, including the case today's tests expect to store `SUCCESS`.
4. Only then, and only on `PKG02-FUTURE-PYTHON-UNASSIGNED`, switch the new writer.
5. Stop before merge and before seal. An independent council reviews the activation. This template does not appoint that council.

## 4. Record delta the future force must show

Against a 3.1.0 file from the same workload, the new file must show:

- `runtime` `python` and `producer` `python_observe`
- No `workflow`, `status_labels`, `plane`, `data_note`, or `residual`
- `schema_version` `0`. The old `2` only as `compatibility.legacy_schema_version`
- Timestamps as UTC `Z` with three fractional digits
- Envelope `duration_ms` only when the interval was measured. Empty `shield()` is either an explicit `NOT_OBSERVED` envelope or no file, and the delta says which. It is not a file whose `optics_status` is `SUCCESS`
- Per-call `failure_kind` kept when 3.1.0 had one
- `provider` not copied into `provider_id`
- Comma-joined envelope `mediation` not copied as one token
- `response_bytes` omitted, matching today's missing size, not filled with `0`
- `optics_status` `OBSERVED` when the call was seen, including when the provider outcome is unavailable
- `application_status` from the HTTP code, never the token `PARTIAL`
- Unicode diagnostic `PKG01-UCD-16.0.0`
- Canonical JSON byte-identical to the Node adapter for a shared fixture whose semantics are the same

## 5. Rollback proof

Disable the new writer. The next `shield()` uses the previous shape. A canonical file already written stays on disk with its origin. A reader that no longer understands it reports `UNSUPPORTED` and shows `schema_status`. Customer exception text is still not stored. The wrapped function's return value does not change when validation fails.

## 6. Stop line

The future force stops before merge, before seal, and before publication. It does not mark a release ready. It does not announce. It does not upload to a package index.
