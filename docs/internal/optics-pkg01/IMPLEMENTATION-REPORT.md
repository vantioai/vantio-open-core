# PKG-01 implementation report

Audience: INTERNAL_RESTRICTED

Producer only. This report does not pass council.

## Classification

`OPTICS_PKG01_REVISION_READY_FOR_COUNCIL`

Producer classification for the pinned-Unicode revision. This is not a council pass. Status for the next agent is `PENDING_INDEPENDENT_RECOUNCIL` (pinned-Unicode). The revision starts from tip `4a34ce40645ba5aa4495437d4fdfb4f7e91ac156`. Earlier council records stay historical: `INDEPENDENT-COUNCIL-REPORT.md` and `INDEPENDENT-RECOUNCIL-REPORT.md`, both `OPTICS_PKG01_NEEDS_REVISION`.

## What landed

Private package `packages/optics-evidence-contract/` (Option B):

- `contract/field-catalog.json` (120 fields)
- `contract/prohibited-fields.json`
- `contract/enums.json`
- `contract/normalization.json`
- `contract/contract-metadata.json`
- `contract/detector-classes.json`
- Hand-written `src/validate.cjs`, `src/canonical.cjs`, `src/walk.cjs`, `src/privacy.cjs`, `src/unicode_profile.cjs`
- Hand-written `src/validate.py`, `src/canonical.py`, `src/walk.py`, `src/privacy.py`, `src/unicode_profile.py`
- Pinned Unicode profile `PKG01-UCD-16.0.0` under `contract/unicode-profile.json`, `contract/unicode-nfkc-map.json`, `contract/unicode-category-ranges.json`, and `contract/unicode-profile-metadata.json`
- Offline generator `tools/generate_unicode_profile.py` and committed UCD sources under `contract/unicode-source/`

Tests: `tests/optics-evidence-contract/corpus.json` (220 fixtures), `node.test.cjs`, `python_test.py`, `hostile_worker.cjs`, `hostile_worker.py`.

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

## Detector-parity revision

Started from PR head `075b82508fa93b84ce7416512a8d422ed4ca4e49`. Closed B1–B8 behavior stays in the corpus.

| Probe | Before (re-council) | After |
| --- | --- | --- |
| PAN `/pay/4111111111111111α` and the before-digit form | Node redacted. Python stored the path. | Both `REJECT_FIELD` / `REDACTION_DROP`. Path absent. Privacy category `DESTINATION_COMPONENT_REDACTED`. |
| Mixed-script `sk-`, Bearer, JWT, Basic, `ghp_`, `AKIA`, `AIza` | One language stored the value. | Both reject. Detector fields use `DETECTOR_MATCH`. A secret path uses `REDACTION_DROP` plus `DESTINATION_COMPONENT_REDACTED`. |
| `/` plus 300 U+03B1 | Node stored it. Python treated the letters as a privacy drop. | Both `REJECT_FIELD` / `MAX_SIZE_EXCEEDED`. Privacy event null. 601 UTF-8 bytes. |
| Function value | Node `HOSTILE_INPUT`. Python `ACCESSOR_PROPERTY_FORBIDDEN`. | Both `REJECT_FIELD` / `UNSUPPORTED_COMPLEX_VALUE`. |
| Secret path with no host | Path absent and privacy event null. | Path absent. Privacy category `DESTINATION_COMPONENT_REDACTED`. |
| ASCII case fold of `AKIA`, `ghp_`, `Bearer`, `Basic`, `eyJ` | Case-swapped markers were stored. | Same disposition as the canonical-case sample. `MRN:` stays case-sensitive. |

Character classes and the reported-reason order are in `contract/detector-classes.json`. String bounds are UTF-8 bytes. `MAX_SIZE_EXCEEDED` outranks `DETECTOR_MATCH`; the value is still omitted. An ASCII letter still suppresses PAN detection.

## Pinned-Unicode revision

Started from tip `4a34ce40645ba5aa4495437d4fdfb4f7e91ac156`. Privacy normalization and letter/number membership read the committed profile `PKG01-UCD-16.0.0` (Unicode 16.0.0). Node ICU and CPython `unicodedata` are not the privacy decision. NFC is comparison-only. NFKC is detection-only and is not stored. A code point absent from the profile is `UNKNOWN_TO_PROFILE` and fails closed inside an email-shaped span. Pinned format controls are removed only in the detector view; a hit omits the original. A governed prefix may contain one non-ASCII insertion and still match. A walk above 8192 bytes with no detector hit in the scanned prefix is `MAX_SIZE_EXCEEDED`, privacy null, scan state `SIZE_ONLY`. A candidate that crosses that cut is `SCAN_INCOMPLETE` and scan state `BOUNDARY`, without `DETECTOR_MATCH`. `Buffer`, `Uint8Array`, `bytes`, `bytearray`, and `memoryview` are `REJECT_FIELD` / `UNSUPPORTED_COMPLEX_VALUE`.

This is not universal confusable detection, not live runtime protection, and not a shipment. Windows, macOS, and WSL are `NOT_TESTED`.

## Corpus

220 shared fixtures, including harness metadata for accessor, proxy, class instance, function, function-valued field, the isolated non-returning getter, and binary containers. The earlier 185-fixture counts below are the detector-parity baseline, not the pinned-Unicode total.

Pinned-Unicode totals: `ACCEPT` 35, `NORMALIZE` 15, `STRIP` 23, `REJECT_FIELD` 121, `REPLACE_WITH_SAFE_CATEGORY` 9, `REJECT_RECORD` 17.

Pinned-Unicode reasons: `REDACTION_DROP` 57, `OK` 36, `DETECTOR_MATCH` 36, `MAX_SIZE_EXCEEDED` 24, `NORMALIZED` 7, `UNKNOWN_FIELD_OMITTED` 6, `CONTEXT_REJECTED` 6, `PROHIBITED_FIELD_NAME` 6, `UNSUPPORTED_COMPLEX_VALUE` 6, `SESSION_ID_REJECTED` 5, `CONFLICTING_PROVENANCE` 5, `LEGACY_UNMARKED` 4, `MISSING_REQUIRED_STATUS` 4, `ACCESSOR_PROPERTY_FORBIDDEN` 3, `PROMPT_COMPLETION_EXCLUDED` 2, `UNKNOWN_FIELD_REDACTED` 2, and one each of `BAGGAGE_OMITTED`, `DESTINATION_CONFLICT`, `PROVENANCE_INSUFFICIENT`, `SIMULATED_DEMO`, `SCHEMA_STATUS_CORRECTED`, `ENFORCEMENT_ACTION_EXCLUDED`, `OPTICS_WRITE_FAILURE`, `ANNOTATION_ORIGIN_REFUSED`, `QUERY_STRIPPED`, `DUPLICATE_CANONICAL_FIELD`, `OPTIMISTIC_DEFAULT_FORBIDDEN`.

Detector-parity baseline (185 fixtures, historical): `ACCEPT` 33, `NORMALIZE` 15, `STRIP` 23, `REJECT_FIELD` 88, `REPLACE_WITH_SAFE_CATEGORY` 9, `REJECT_RECORD` 17.

Detector-parity baseline reasons: `REDACTION_DROP` 45, `OK` 34, `DETECTOR_MATCH` 25, `MAX_SIZE_EXCEEDED` 17, `NORMALIZED` 7, `UNKNOWN_FIELD_OMITTED` 6, `CONTEXT_REJECTED` 6, `PROHIBITED_FIELD_NAME` 6, `SESSION_ID_REJECTED` 5, `CONFLICTING_PROVENANCE` 5, `LEGACY_UNMARKED` 4, `MISSING_REQUIRED_STATUS` 4, `ACCESSOR_PROPERTY_FORBIDDEN` 3, `UNSUPPORTED_COMPLEX_VALUE` 3, `PROMPT_COMPLETION_EXCLUDED` 2, `UNKNOWN_FIELD_REDACTED` 2, and one each of `BAGGAGE_OMITTED`, `DESTINATION_CONFLICT`, `PROVENANCE_INSUFFICIENT`, `SIMULATED_DEMO`, `SCHEMA_STATUS_CORRECTED`, `ENFORCEMENT_ACTION_EXCLUDED`, `OPTICS_WRITE_FAILURE`, `ANNOTATION_ORIGIN_REFUSED`, `QUERY_STRIPPED`, `DUPLICATE_CANONICAL_FIELD`, `OPTIMISTIC_DEFAULT_FORBIDDEN`.

Legacy `bytes` 0 and explicit `response_bytes` 0 remain the existing fixtures `legacy-call-zero-bytes` and `explicit-zero-bytes`. The legacy fixture's completeness impact is now `MISSING_REQUIRED_STATUS` because that call has no `optics_status`. Its reason stays `LEGACY_UNMARKED`.

Canaries used in the corpus are absent from canonical output, including the secret-shaped field-name fixture.

## Commands and results

Linux host. Node `v22.14.0`. Python `3.10.21`, `3.11.16`, and `3.12.3`. No npm install and no pip install of this package.

```bash
node --test tests/optics-evidence-contract/node.test.cjs
python3 -m unittest tests/optics-evidence-contract/python_test.py
python3.10 -m unittest tests/optics-evidence-contract/python_test.py
python3.11 -m unittest tests/optics-evidence-contract/python_test.py
```

Node: 13 tests, 13 pass. Python 3.10.21, 3.11.16, and 3.12.3: 12 tests, OK on each interpreter. Canonical JSON matched across Node and each Python interpreter for all 220 fixtures. Declared UTF-8 byte lengths matched both encoders. Profile file hashes matched `unicode-profile-metadata.json`. The offline generator reproduced those files. Verification vectors matched in both languages. A missing profile returned `VALIDATOR_FAULT` with scan state `UNAVAILABLE` and did not copy the input PAN. Canary scan of the canonical strings passed. Scope walk found no `optics-evidence-contract` import under the live CLI or Python SDK. Validator sources do not import network clients. Privacy and profile sources do not call host Unicode category or normalization APIs. No store file was created.

Windows: `NOT_TESTED`. macOS: `NOT_TESTED`. WSL: `NOT_TESTED`. Other Node versions: `NOT_TESTED`.

## Gates

This Force opens Gate 8 for PKG-01 source only. S1-G1 through S1-G8 are not claimed as passed; S1-G8 is the separate council. S1-G9 and S1-G10 are out of scope. Other implementation packages stay blocked. The architecture gate file was not edited and still describes Gate 8 as closed.

Founder decisions 2–13 remain unresolved.

## Hard stop

No merge. No seal. No publish. No live integration. No in-process universal timeout claim. Council status: `PENDING_INDEPENDENT_RECOUNCIL`.
