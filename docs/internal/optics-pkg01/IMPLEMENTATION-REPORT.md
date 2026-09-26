# PKG-01 implementation report

Audience: INTERNAL_RESTRICTED

Producer only. This report does not pass council.

## Classification

`OPTICS_PKG01_REVISION_READY_FOR_COUNCIL`

The first council record stays in `INDEPENDENT-COUNCIL-REPORT.md` with classification `OPTICS_PKG01_NEEDS_REVISION`. This revision does not pass council. Status for the next agent is `PENDING_INDEPENDENT_RECOUNCIL`.

## What landed

Private package `packages/optics-evidence-contract/` (Option B):

- `contract/field-catalog.json` (120 fields)
- `contract/prohibited-fields.json`
- `contract/enums.json`
- `contract/normalization.json`
- `contract/contract-metadata.json`
- Hand-written `src/validate.cjs`, `src/canonical.cjs`, `src/walk.cjs`, `src/privacy.cjs`
- Hand-written `src/validate.py`, `src/canonical.py`, `src/walk.py`, `src/privacy.py`

Tests: `tests/optics-evidence-contract/corpus.json` (116 fixtures), `node.test.cjs`, `python_test.py`, `hostile_worker.cjs`, `hostile_worker.py`.

Internal notes: `docs/internal/optics-pkg01/`.

No live CLI or Python runtime file was modified. No workflow file was modified. No architecture or planning file was modified. No SQLite module, database file, migration, UI, daemon, OTLP, SIEM, or alerting path was added.

## Revision matrix

Started from council head `ed2a45ee9f09a9056050f8082f0302ce24d4ad42`.

| Blocker | Before | After |
| --- | --- | --- |
| B1 allowlisted detector values | Charset match stored the value. Privacy result null. | `REJECT_FIELD` / `DETECTOR_MATCH`. Value absent. Privacy category `DETECTOR_MATCH`. |
| B2 secret-shaped field name | `STRIP` / `UNKNOWN_FIELD_OMITTED`. Raw name copied into stripped fields. | `REJECT_FIELD` / `DETECTOR_MATCH`. Locator `UNKNOWN_FIELD_REDACTED_1`. Raw name absent from output. |
| B3 Unicode email path | Node stored the path. Python rejected it. | Both `REJECT_FIELD` / `REDACTION_DROP`. Path absent. NFC and NFD agree. |
| B4 `prompt` plus newline | Node dropped the record but echoed the raw name. Python stripped the field and echoed the raw name. | Both `REJECT_RECORD` / `PROHIBITED_FIELD_NAME`. Locator `PROHIBITED_FIELD_CATEGORY`. |
| B5 inherited trace labeled `OPTICS_GENERATED` | Caller basis stored. Traceparent meaning null. Inherited context kept `LOCAL_OBSERVATION`. | Basis replaced with `ASSERTED_CONTEXT`, or `IMPORTED_UNVERIFIED` on import quarantine. Meaning set. Conflict diagnostic set. `LOCAL_OBSERVATION` kept only with destination or HTTP evidence. |
| B6 missing status | Missing optics became `SUCCESS`. Missing action became `OBSERVED`. | Missing optics is `UNAVAILABLE` / `MISSING_REQUIRED_STATUS`. Missing action stays absent. HTTP 500 stays HTTP 500. Legacy `bytes` 0 stays null. Explicit `response_bytes` 0 stays 0. |
| B7 detached output | `application_result` was the caller reference. | Plain copy. Post-validation mutation does not cross the boundary. |
| B8 hostile accessor | Throwing getter ran and returned `HOSTILE_INPUT`. | `ACCESSOR_PROPERTY_FORBIDDEN` before the getter runs. Non-returning getter is isolated in a subprocess. No in-process timeout is claimed. |

## Corpus

116 shared fixtures, including harness metadata for accessor, proxy, class instance, and the isolated non-returning getter.

Disposition counts: `ACCEPT` 15, `NORMALIZE` 15, `STRIP` 22, `REJECT_FIELD` 39, `REPLACE_WITH_SAFE_CATEGORY` 9, `REJECT_RECORD` 16.

Reason counts: `REDACTION_DROP` 35, `OK` 16, `NORMALIZED` 7, `UNKNOWN_FIELD_OMITTED` 6, `PROHIBITED_FIELD_NAME` 6, `DETECTOR_MATCH` 5, `CONFLICTING_PROVENANCE` 5, `SESSION_ID_REJECTED` 4, `LEGACY_UNMARKED` 4, `CONTEXT_REJECTED` 4, `MISSING_REQUIRED_STATUS` 4, `ACCESSOR_PROPERTY_FORBIDDEN` 3, `PROMPT_COMPLETION_EXCLUDED` 2, and one each of `BAGGAGE_OMITTED`, `PATH_OVERSIZE`, `DESTINATION_CONFLICT`, `PROVENANCE_INSUFFICIENT`, `SIMULATED_DEMO`, `SCHEMA_STATUS_CORRECTED`, `ENFORCEMENT_ACTION_EXCLUDED`, `OPTICS_WRITE_FAILURE`, `ANNOTATION_ORIGIN_REFUSED`, `QUERY_STRIPPED`, `DUPLICATE_CANONICAL_FIELD`, `OPTIMISTIC_DEFAULT_FORBIDDEN`, `UNKNOWN_FIELD_REDACTED`, `MAX_SIZE_EXCEEDED`, `UNSUPPORTED_COMPLEX_VALUE`.

Legacy `bytes` 0 and explicit `response_bytes` 0 remain the existing fixtures `legacy-call-zero-bytes` and `explicit-zero-bytes`. The legacy fixture's completeness impact is now `MISSING_REQUIRED_STATUS` because that call has no `optics_status`. Its reason stays `LEGACY_UNMARKED`.

Canaries used in the corpus are absent from canonical output, including the secret-shaped field-name fixture.

## Commands and results

Linux `6.12.94+` x86_64. Node `v22.14.0`. Python `3.10.21`, `3.11.16`, and `3.12.3`. No npm install and no pip install of this package.

```bash
node --test tests/optics-evidence-contract/node.test.cjs
python3 tests/optics-evidence-contract/python_test.py
python3.10 -m unittest tests/optics-evidence-contract/python_test.py
python3.11 -m unittest tests/optics-evidence-contract/python_test.py
```

Node: 10 tests, 10 pass. Python 3.10, 3.11, and 3.12: 9 tests, OK. Canonical JSON matched across Node and each Python interpreter for all 116 fixtures. Canary scan of those canonical strings passed. Scope walk found no `optics-evidence-contract` import under the live CLI or Python SDK. Validator sources do not import network clients. No store file was created.

Windows: `NOT_TESTED`. macOS: `NOT_TESTED`. WSL: `NOT_TESTED`. Other Node versions: `NOT_TESTED`.

## Gates

This Force opens Gate 8 for PKG-01 source only. S1-G1 through S1-G8 are not claimed as passed; S1-G8 is the separate council. S1-G9 and S1-G10 are out of scope. Other implementation packages stay blocked. The architecture gate file was not edited and still describes Gate 8 as closed.

Founder decisions 2–13 remain unresolved.

## Hard stop

No merge. No seal. No publish. No live integration. No in-process universal timeout claim. Council status: `PENDING_INDEPENDENT_RECOUNCIL`.
