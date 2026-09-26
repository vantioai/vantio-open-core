# PKG-01 independent re-council report

Audience: INTERNAL_RESTRICTED

## Classification

`OPTICS_PKG01_NEEDS_REVISION`

This re-council does not assign `OPTICS_PKG01_COUNCIL_PASSED`. It does not authorize merge, seal, publication, live CLI or Python integration, SQLite, UI, a daemon, OTLP, SIEM, or alerting.

The first council record stays in `INDEPENDENT-COUNCIL-REPORT.md`. This file does not replace it.

## Identity

| Item | Value |
| --- | --- |
| Re-council agent | `bc-88b874ba-c80d-593c-be31-7332c8ba3f89` |
| Re-council run | https://cursor.com/agents/bc-88b874ba-c80d-593c-be31-7332c8ba3f89 |
| Original producer (judgments not reused) | `bc-9d2eaaed-8a23-520b-8476-c64f679ba455` |
| First council (judgments not reused) | `bc-795c2ba1-73bc-5a15-beba-f1505acc58cf` |
| Revision producer (judgments not reused) | `bc-a3731408-ea62-5894-8cd4-6f123ad7bc68` |
| Repository | `vantioai/vantio-open-core` |
| Draft PR | https://github.com/vantioai/vantio-open-core/pull/58 |
| Branch | `implementation/optics-pkg01-evidence-privacy` |
| Tip reviewed | `6da63f8aafceb7eed3950975d224848fec6c3ba5` |
| Prior council head | `ed2a45ee9f09a9056050f8082f0302ce24d4ad42` |
| Authorized base | `311f260a5f1bee1d3dc9b3734fd6910fb1116094` |
| Producer classification | `OPTICS_PKG01_REVISION_READY_FOR_COUNCIL` |

The re-council reviewed that tip, re-ran the isolated tests, and ran an independent probe outside the corpus. It did not edit `packages/optics-evidence-contract/` or `tests/optics-evidence-contract/`.

## Seats

Overall is the worst material seat. `NEEDS_REVISION` is the worst result below. No seat is `BLOCKED`.

| # | Seat | Result |
| --- | --- | --- |
| 1 | Privacy engineering | `NEEDS_REVISION` |
| 2 | Observability semantics | `PASS_WITH_NONBLOCKING_NOTES` |
| 3 | Node security | `PASS_WITH_NONBLOCKING_NOTES` |
| 4 | Python security | `NEEDS_REVISION` |
| 5 | Cross-language conformance | `NEEDS_REVISION` |
| 6 | Application fail-open | `PASS` |
| 7 | Compatibility | `PASS` |
| 8 | Cross-platform | `PASS_WITH_NONBLOCKING_NOTES` |
| 9 | Release and scope control | `PASS` |
| 10 | Customer diagnostics | `PASS_WITH_NONBLOCKING_NOTES` |
| 11 | Evidence verification | `PASS_WITH_NONBLOCKING_NOTES` |
| 12 | Product positioning | `PASS` |

## Blocking finding

**Python and Node use different character classes, so the same plain string gets two dispositions, and Python persists a PAN that Node redacts.**

`privacy.cjs` classifies bearer, basic, OpenAI tails, JWT segments, MRN tails, card boundaries, and base64 runs with ASCII ranges. `privacy.py` uses `str.isalnum()` or `str.isalpha()` in `_has_bearer`, `_has_basic`, `_has_openai`, `_has_jwt`, `_has_mrn`, `_has_card`, and `_b64_char`. Python 3.10.21, 3.11.16, and 3.12.3 agreed with each other. They disagreed with Node. The 116-fixture corpus has no such input, so a green corpus run does not cover this.

| Input | Node v22.14.0 | Python 3.10 / 3.11 / 3.12 |
| --- | --- | --- |
| `path` `/pay/4111111111111111α` with host `api.example.com` | `REJECT_FIELD` / `REDACTION_DROP`. Path absent. `privacy_event` `REDACTION_DROP` | `NORMALIZE` / `NORMALIZED`. Path stored. `privacy_event` null |
| `path` `/pay/α4111111111111111` | Same rejection. Path absent | Path stored. `privacy_event` null |
| `path` `/sk-ABCDEFGαHIJK` | `NORMALIZE`. Path stored. `privacy_event` null | `REJECT_FIELD` / `REDACTION_DROP`. Path absent |
| `source_label` `Bearer abcdefgαHIJK` | Value stored. `privacy_event` null | `REJECT_FIELD` / `DETECTOR_MATCH`. Value absent |
| `source_label` `eyJhbGciOiJIUzI1NiJ9.abcα` | Value stored. `privacy_event` null | `REJECT_FIELD` / `DETECTOR_MATCH`. Value absent |
| `duplicate_of` `Basic abcdefgαHIJK` | Value stored | `REJECT_FIELD` / `REDACTION_DROP`. Value absent |
| `path` `/` plus 300 U+03B1 letters | Path stored. `privacy_event` null | `REJECT_FIELD` / `REDACTION_DROP`. Path absent. Privacy set |

`α` is U+03B1. Scanner checks on the same interpreters also disagreed for `MRN:ABCDEα` (Node false, Python true) and for ASCII controls that both already flag (`Bearer abcdefgh`, `Basic abcdefgh`, a bare 16-digit PAN, `4111-1111-1111-1111`).

The PAN row is the privacy failure. Python's card rule treats a following or preceding non-ASCII letter as a letter boundary, so a 16-digit PAN in an allowlisted `path` is kept. Node's ASCII letter check redacts that path. The token and base64 rows are the other side of the same split: Node keeps strings Python's scanner calls prohibited, and a long Unicode letter run becomes a Python privacy drop because `_b64_char` treats those letters as base64.

Required outcome for the next revision:

- One canonical result on Node and on Python 3.10, 3.11, and 3.12 for each input above.
- A 13–19 digit PAN stays absent from both outputs when the adjacent character is a non-ASCII letter. Matching Python to Node's current ASCII card check does that. Copying `str.isalpha()` onto Node would persist the PAN on both sides.
- Bearer, basic, OpenAI, JWT, MRN, and base64 use one shared character class, so a non-ASCII letter cannot make only one language persist the string.
- Add these inputs to the shared corpus. The current 116 fixtures do not fail on this defect.

`BOUNDARY.md` already says the scanners are loops and ASCII classes. `privacy.py` does not follow that for the functions named above.

## Former blockers

Independent inputs, both languages, tip `6da63f8aafceb7eed3950975d224848fec6c3ba5`. Canonical JSON matched on these rows. The summary fields that look like `undefined` versus `null` are absent values, not different stored strings.

| ID | Result |
| --- | --- |
| B1 allowlisted detector values | Closed for the canonical samples. `schema_status_seen` `sk-CANARYSEEN00001` and the sample JWT, `detail_code` `AKIAIOSFODNN7EXAMPLE` and `AIzaCANARY0001`, `reason_code` `ghp_CANARYTOKEN0001`, and `provider_id` `sk-canary0001` at `CATALOG`, `LOCAL_OLLAMA`, `REGIONAL_PATTERN`, and `NONE` are `REJECT_FIELD` / `DETECTOR_MATCH`. The value is absent. `privacy_event` is `DETECTOR_MATCH`. On the provider rows the confidence enum remains and `provider_id` does not. |
| B2 secret-shaped field name | Closed. Key `sk-CANARYKEYNAME0001` and key `AKIAIOSFODNN7EXAMPLE` are `REJECT_FIELD` / `DETECTOR_MATCH` with stripped locator `UNKNOWN_FIELD_REDACTED_1`. The raw name is absent. |
| B3 Unicode email path | Closed. `/user@exämple.com` in NFC and in NFD is `REJECT_FIELD` / `REDACTION_DROP` on both languages. Path absent. `privacy_event` `REDACTION_DROP`. ASCII `canary.person@example.com` is rejected by both. |
| B4 `prompt` plus a control or fold | Closed. `prompt` plus newline, CR, tab, U+200B, U+2028, or U+FEFF, and the folded name `Prompt`, are `REJECT_RECORD` / `PROHIBITED_FIELD_NAME` with locator `PROHIBITED_FIELD_CATEGORY`. Exact `prompt` is `REJECT_RECORD` / `PROMPT_COMPLETION_EXCLUDED` and the locator is the catalog name `prompt`. The raw disguised name is absent. `privacy_event` is `REDACTION_DROP`. |
| B5 inherited trace | Closed for a caller basis without the witness. `vantio_trace_id` or `traceparent` plus caller basis `OPTICS_GENERATED` is stored as `ASSERTED_CONTEXT`, or `IMPORTED_UNVERIFIED` for `traceparent` on `import_quarantine`. `trace_basis_meaning` is set. `provenance_conflict` is `TRACE_BASIS_REPLACED`. |
| B6 missing status and action | Closed. Missing `optics_status` is stored as `UNAVAILABLE` with reason `MISSING_REQUIRED_STATUS`, including beside HTTP 500, which stays `application_status` `APPLICATION_ERROR`. Missing `action` stays absent. Missing both leaves `optics_status` `UNAVAILABLE`, action absent, and `application_status` absent. |
| B7 detached output | Closed on the exercised objects. Validation copies first. Mutating `destination_host` on the input after the call leaves the result on `api.example.com`. Mutating the result leaves the input on the caller's later value. The fail-open test keeps a nested `application_result` copy that is not the caller's object. |
| B8 hostile accessor | Closed on the exercised shapes. Own getter, nested getter, array element getter, and prototype getter: Node call count stays 0 and the reason is `ACCESSOR_PROPERTY_FORBIDDEN`. Python dict-subclass property and the harness proxy: call count stays 0. A plain class is `UNSUPPORTED_COMPLEX_VALUE`. The non-returning getter runs only in `hostile_worker.cjs` / `hostile_worker.py`; the parent reports `CALLS 0` and `ACCESSOR_PROPERTY_FORBIDDEN`, and the hang mode is killed by the parent's timeout. |

Inherited trace plus a sufficient producer and version, with no destination and no HTTP status, does not store `evidence_origin`. Reader label is `LEGACY_UNMARKED`. With a destination or an HTTP status, `LOCAL_OBSERVATION` can remain. That remaining origin is the destination or HTTP evidence.

The private witness `PKG01_OPTICS_GENERATED_WITNESS`, together with a recognized producer and a version, stores basis `OPTICS_GENERATED` for a direct `trace_id` and for `vantio_trace_id`. Without a destination or HTTP status, that witness still does not store `LOCAL_OBSERVATION`. The witness is the static contract value. It is not persisted. This matches `normalization.json` and `PRIVACY-DISPOSITIONS.md`.

## Nonblocking notes

- Case-swapped cloud markers are stored by both languages with `privacy_event` null. `akiaiosfodnn7example` was stored in `detail_code`, `provider_id`, `error_class`, `cli_or_sdk_version`, `path`, `source_label`, `duplicate_of`, `text`, and `session_id`. `aizacanary0001` was stored in `provider_id`. `GHP_CANARYTOKEN0001` was stored in quarantine `reason_code`. `XOXB-CANARY0001` was stored in `schema_status_seen`. The canonical-case samples `AKIA…`, `AIza…`, `ghp_…`, and `sk-…` are rejected. `sk-` is case-folded. `AKIA`, `AIza`, `ghp_`, `xoxb-`, and `ya29.` are literal. Both scanners agree, so this is coverage, not a language split.
- A digit run bounded by an ASCII letter is stored by both languages. `path` `/pay/4111111111111111a` stays in the record. `KNOWN-LIMITATIONS.md` already says a letter boundary suppresses card detection.
- A secret `path` with no destination host is omitted and `privacy_event` stays null. The probed value `/sk-CANARYPATH00001` was absent from the canonical result. Collection returns before the path scan when no host is chosen.
- A safe grammar name such as `customer_note` is echoed in `fields.stripped`. Unsafe names use `UNKNOWN_FIELD_REDACTED_n` or `PROHIBITED_FIELD_CATEGORY`.
- A function value is rejected by both languages and is not present in the record. Node's reason is `HOSTILE_INPUT`. Python's reason is `ACCESSOR_PROPERTY_FORBIDDEN`.
- There is no in-process timeout. The hang proof is the killable subprocess. The suite's hang mode returned `ETIMEDOUT` under the parent's 500 ms limit and did not fail the test.
- Python string length is code points. Some Node checks use UTF-16 code units. The corpus is BMP. That limit is already in `KNOWN-LIMITATIONS.md`.
- One detection decode is the documented scanner depth.
- Gate 8 in `docs/architecture/optics-foundation/09-IMPLEMENTATION-GATES.md` is outside this diff and still describes Gate 8 as closed. The package notes say this force opens Gate 8 only for the private package.
- Windows, macOS, WSL, and Node versions other than v22.14.0 were not run.

## Required questions

1. **Can detector-positive content cross through any allowlisted string?** Yes. Python stores `/pay/4111111111111111α` and `/pay/α4111111111111111`. Node stores `/sk-ABCDEFGαHIJK`, `Bearer abcdefgαHIJK`, `eyJhbGciOiJIUzI1NiJ9.abcα`, and `Basic abcdefgαHIJK` in allowlisted strings. The canonical B1 samples do not cross. A walk of the 110 plain corpus results found no stored string for which Node `containsProhibited` returned true.

2. **Can a secret-shaped field name appear in diagnostics?** No for the names probed. `sk-CANARYKEYNAME0001` and `AKIAIOSFODNN7EXAMPLE` become `UNKNOWN_FIELD_REDACTED_1`. Disguised `prompt` names become `PROHIBITED_FIELD_CATEGORY`. A safe grammar name can still be echoed.

3. **Can Node and Python disagree for Unicode or normalized field names?** Yes for the Unicode values in the blocking finding. The normalized names that were probed agree: `prompt` plus newline, CR, tab, space, case fold, ZWSP, line separator, and BOM.

4. **Can inherited trace context claim `OPTICS_GENERATED`?** Only together with the private witness, a recognized producer, and a version. A caller basis `OPTICS_GENERATED` on `vantio_trace_id` or `traceparent` without that witness is stored as `ASSERTED_CONTEXT`, or `IMPORTED_UNVERIFIED` for import `traceparent`.

5. **Can inherited trace context establish `LOCAL_OBSERVATION` by itself?** No. With producer `node_interceptor`, version `0.3.24`, and no destination or HTTP status, `evidence_origin` is absent. A destination or HTTP status can keep `LOCAL_OBSERVATION`.

6. **Can a missing status become `SUCCESS`?** No. Missing `optics_status` is `UNAVAILABLE`. HTTP 500 stays `APPLICATION_ERROR`. Missing `application_status` with no HTTP status is omitted. The corpus case `missing-application-status-no-http` passed with that shape.

7. **Can a missing action become `OBSERVED`?** No. The action key stays absent. Reason `MISSING_REQUIRED_STATUS` is recorded.

8. **Can input mutation change validator output?** No on the objects exercised. The input compared equal to its pre-call snapshot. A later write to `destination_host` left the result on `api.example.com`.

9. **Can output mutation change input?** No on the objects exercised. Writing the result host left the caller object on its own value. The nested `application_result` in the fail-open test is a separate tree.

10. **Can arbitrary executable objects reach output?** No. A function value is rejected and omitted. Prototype getters, proxies, and class instances are rejected. The record is null.

11. **Can accessor-bearing input execute during ordinary traversal?** No on the shapes exercised. Node own, nested, array, and prototype getters stayed at call count 0. Python property and dict-subclass hooks stayed at call count 0. The harness asserts the same for the accessor and proxy fixtures.

12. **Can a non-returning hostility test hang the test suite?** No. `hostile_worker` validate mode printed `CALLS 0` and `ACCESSOR_PROPERTY_FORBIDDEN` inside the 2 second parent limit. Hang mode was killed by the parent timeout. The validator does not claim an in-process timeout.

13. **Can privacy-triggered dispositions leave privacy result null?** No for the privacy reason codes checked. The 110 plain corpus results with reason `REDACTION_DROP`, `DETECTOR_MATCH`, `PROHIBITED_FIELD_NAME`, or `PROMPT_COMPLETION_EXCLUDED` all had a non-null `privacy_event`. A control-character unknown name is `STRIP` / `UNKNOWN_FIELD_REDACTED` with `privacy_event` null, which is the written non-privacy redaction. A secret path with no host is omitted without a privacy disposition.

14. **Can diagnostics leak canaries?** The corpus ban list and each case `forbidden` list passed on Node and on Python 3.10, 3.11, and 3.12. Secret-shaped field names are replaced with locators. Case-swapped marker strings can still be stored in allowlisted record fields; see the nonblocking note. Those stored values are record fields, and the canonical-case canaries from B1 and B2 were absent.

15. **Did live CLI or Python imports change?** No. The diff against `311f260a5f1bee1d3dc9b3734fd6910fb1116094` is 30 added files under `packages/optics-evidence-contract/`, `tests/optics-evidence-contract/`, and `docs/internal/optics-pkg01/`. `git diff` of `packages/vantio-cli/package.json` and `packages/vantio-agent-sdk-py/pyproject.toml` is empty. CLI version is `0.3.24`. Python package version is `3.1.0`. A search for `optics-evidence-contract` under `packages/vantio-cli`, `packages/vantio-agent-sdk-py`, and `packages/vantio-agent-sdk` found no matches. The scope test passed.

16. **Did SQLite, UI, daemon, exporter, alerting, or release work enter the PR?** No. The 30-file diff has no sqlite, migration, UI, daemon, OTLP, SIEM, alerting, workflow, architecture, or planning path. The private `package.json` has no `dependencies`. `store.sqlite` is absent. Founder decisions 2–13 stay unresolved in `contract-metadata.json`.

17. **Does documentation overclaim runtime protection or stable schema?** No. The package README, `contract-metadata.json`, and `docs/internal/optics-pkg01/` say `unstable-pre-1.0`, `schema_version` 0, private, and not loaded by the live CLI or Python runtime. `stable_schema` is false. Fail-open notes say they cover this validator only. The field catalog says it is not a JSON Schema and not a stable public schema.

## Test matrix

Host: Linux `6.12.94+` x86_64. Offline. No npm install and no pip install of this package. Tip `6da63f8aafceb7eed3950975d224848fec6c3ba5`.

| Command | Interpreter | Result |
| --- | --- | --- |
| `node --test tests/optics-evidence-contract/node.test.cjs` | Node v22.14.0 | 10 tests, 10 pass, 0 fail |
| `python3 -m unittest tests/optics-evidence-contract/python_test.py` | Python 3.12.3 | 9 tests, OK |
| `python3.11 -m unittest tests/optics-evidence-contract/python_test.py` | Python 3.11.16 | 9 tests, OK |
| `python3.10 -m unittest tests/optics-evidence-contract/python_test.py` | Python 3.10.21 | 9 tests, OK |

Each Python run compares canonical JSON with Node. The Node run compares canonical JSON with Python 3.12. All 116 fixtures matched inside those runs, including canary absence. Python 3.10, 3.11, and 3.12 then produced identical probe JSON for the out-of-corpus set, and that JSON disagreed with Node on the blocking rows.

`NOT_TESTED`: Windows, macOS, WSL, Node versions other than v22.14.0.

Corpus count checked from `corpus.json`: 116 cases. Disposition counts: `ACCEPT` 15, `NORMALIZE` 15, `STRIP` 22, `REJECT_FIELD` 39, `REPLACE_WITH_SAFE_CATEGORY` 9, `REJECT_RECORD` 16. `field-catalog.json` has 120 field rows.

## Confirmations

- PR 58 was draft at review time: `isDraft` true, `state` OPEN, `headRefOid` `6da63f8aafceb7eed3950975d224848fec6c3ba5`, `baseRefOid` `311f260a5f1bee1d3dc9b3734fd6910fb1116094`. This re-council does not merge it and does not mark it ready.
- No live CLI or Python integration was added or authorized.
- No SQLite, UI, daemon, OTLP, SIEM, or alerting work is in the diff.
- Founder decisions 2–13 remain unresolved.
- The architecture gate file still describes Gate 8 as closed. This review does not advance any other package.
- No in-process universal timeout is claimed.

## Next Founder choice

Revise PKG-01 again. The revision stays inside the private contract, its tests, and these internal notes. The blocking character-class split has to close before a later council can pass the package.

Merging PKG-01 source, and any live runtime integration, stay unauthorized.
