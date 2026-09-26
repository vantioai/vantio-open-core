# PKG-01 implementation report

Audience: INTERNAL_RESTRICTED

Producer only. This report does not pass council.

## Classification

`OPTICS_PKG01_READY_FOR_COUNCIL`

## What landed

Private package `packages/optics-evidence-contract/` (Option B):

- `contract/field-catalog.json` (120 fields)
- `contract/prohibited-fields.json`
- `contract/enums.json`
- `contract/normalization.json`
- `contract/contract-metadata.json`
- Hand-written `src/validate.cjs`, `src/canonical.cjs`, `src/walk.cjs`, `src/privacy.cjs`
- Hand-written `src/validate.py`, `src/canonical.py`, `src/walk.py`, `src/privacy.py`

Tests: `tests/optics-evidence-contract/corpus.json` (75 fixtures), `node.test.cjs`, `python_test.py`.

Internal notes: `docs/internal/optics-pkg01/`.

No live CLI or Python runtime file was modified. No workflow file was modified. No architecture or planning file was modified. No SQLite module, database file, migration, UI, daemon, OTLP, SIEM, or alerting path was added.

## Corpus

75 shared JSON fixtures.

Disposition counts: `ACCEPT` 11, `NORMALIZE` 9, `STRIP` 16, `REJECT_FIELD` 27, `REPLACE_WITH_SAFE_CATEGORY` 8, `REJECT_RECORD` 4.

Reason counts include `REDACTION_DROP` 29, `OK` 12, `NORMALIZED` 7, `UNKNOWN_FIELD_OMITTED` 5, `SESSION_ID_REJECTED` 4, `LEGACY_UNMARKED` 4, `CONTEXT_REJECTED` 2, `PROMPT_COMPLETION_EXCLUDED` 2, and one each of `BAGGAGE_OMITTED`, `PATH_OVERSIZE`, `DESTINATION_CONFLICT`, `PROVENANCE_INSUFFICIENT`, `SIMULATED_DEMO`, `SCHEMA_STATUS_CORRECTED`, `ENFORCEMENT_ACTION_EXCLUDED`, `OPTICS_WRITE_FAILURE`, `ANNOTATION_ORIGIN_REFUSED`, `QUERY_STRIPPED`.

Programmatic cases, in both runners and not in the JSON file: hostile enumerable getter, cycle, depth bound, top-level array, lone surrogate session, malformed UTF-8 bytes, injected fault, and a 2,000,000 character string. Canaries used in the corpus are absent from canonical output.

## Commands and results

Linux `6.12.94+` x86_64. Node `v22.14.0`. Python `3.12.3`. Offline. No npm install and no pip install.

```bash
node --test tests/optics-evidence-contract/node.test.cjs
python3 tests/optics-evidence-contract/python_test.py
```

Node: 7 tests, 7 pass. Python: 6 tests, OK. The cross-language test compared canonical JSON for all 75 fixtures and the strings matched.

Python 3.10: `NOT_TESTED` (not installed). Python 3.11: `NOT_TESTED` (not installed). Windows: `NOT_TESTED`. macOS: `NOT_TESTED`. WSL: `NOT_TESTED`. Other Node versions: `NOT_TESTED`.

## Gates

This Force opens Gate 8 for PKG-01 source only. S1-G1 through S1-G8 are not claimed as passed; S1-G8 is the separate council. S1-G9 and S1-G10 are out of scope. Other implementation packages stay blocked. The architecture gate file was not edited and still describes Gate 8 as closed.

Founder decisions 2–13 remain unresolved.

## Hard stop

No merge. No seal. No publish. No live integration. Council status: `PENDING_INDEPENDENT_COUNCIL`.
