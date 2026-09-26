# PKG-01 pinned-Unicode independent re-council

Audience: INTERNAL_RESTRICTED

## Classification

`OPTICS_PKG01_COUNCIL_PASSED`

Overall seat result: `PASS_WITH_NONBLOCKING_NOTES`

This council does not merge PR #58, does not mark it ready for review, and does not authorize seal, publication, live CLI or Python integration, SQLite, a database migration, UI, a daemon, an exporter, or alerting.

## Identity

| Item | Value |
| --- | --- |
| Re-council agent | `bc-1cc76959-8e57-5a6a-8ced-f51acd350637` |
| Re-council run | https://cursor.com/agents/bc-1cc76959-8e57-5a6a-8ced-f51acd350637 |
| This agent is not | `bc-10931acb-5cf2-55d6-9799-f2bed1299f79` or any earlier PKG-01 producer or council |
| Repository | `vantioai/vantio-open-core` |
| Draft PR | https://github.com/vantioai/vantio-open-core/pull/58 |
| Branch | `implementation/optics-pkg01-evidence-privacy` |
| Tip reviewed | `888121476bffd9451a0de2bc7e53bbbac1e373ab` |
| PR #58 HEAD at review | `888121476bffd9451a0de2bc7e53bbbac1e373ab` |
| PR #58 draft | yes |
| Prior pinned-Unicode start | `4a34ce40645ba5aa4495437d4fdfb4f7e91ac156` |
| Authorized base | `311f260a5f1bee1d3dc9b3734fd6910fb1116094` |
| Producer classification | `OPTICS_PKG01_REVISION_READY_FOR_COUNCIL` |

`gh pr view 58` reported `headRefOid` equal to the tip above, `isDraft: true`, and `state: OPEN`. Local `HEAD` at the start of review was that same commit, message `Pin PKG-01 privacy Unicode to committed UCD 16.0.0 tables.`

This council did not edit `packages/optics-evidence-contract/` or `tests/optics-evidence-contract/`.

## Scope

The diff from `311f260a5f1bee1d3dc9b3734fd6910fb1116094` to the reviewed tip is 42 files. Every path is under `packages/optics-evidence-contract/`, `tests/optics-evidence-contract/`, or `docs/internal/optics-pkg01/`.

The diff from `4a34ce40645ba5aa4495437d4fdfb4f7e91ac156` to the reviewed tip is 29 files in those same trees. It adds the pinned profile, the UCD sources, the offline generator, and the privacy/validate/walk changes that read the profile. It does not touch `packages/vantio-cli/`, `packages/vantio-agent-sdk/`, or `packages/vantio-agent-sdk-py/`.

CLI `packages/vantio-cli/package.json` version is `0.3.24`. Python `packages/vantio-agent-sdk-py/pyproject.toml` version is `3.1.0`. The private package version is `0.0.0-unstable-pre-1.0`. No SQLite module, migration, UI, daemon, OTLP, SIEM, or alerting path is in the diff.

## Pinned profile

| Field | Value |
| --- | --- |
| Profile id | `PKG01-UCD-16.0.0` |
| Profile version | `16.0.0` |
| Generator | `pkg01-unicode-gen-1` |
| Verification vectors | 15 |
| Letter ranges | 677 |
| Number ranges | 144 |
| Other ranges | 564 |
| Format-control ranges | 21 |
| Canonical mappings | 2081 |
| Compatibility mappings | 3832 |
| Nonzero combining classes | 934 |
| Full composition exclusions | 1120 |

Verified SHA-256, file bytes against `unicode-profile-metadata.json`:

| File | SHA-256 |
| --- | --- |
| `unicode-profile.json` | `edceba7880051fe2ca760d94f61ec8bf6b261ace47e23d1683bf1eab333ee6b6` |
| `unicode-nfkc-map.json` | `dbebb52f69eca51c733b2bab84491b40e7711baa37e2f3dc548c971d65dd7ba3` |
| `unicode-category-ranges.json` | `9930a19217d946b0de5d8d49318c058f4af53b8c3aad59fc4dbac03058553970` |
| `unicode-source/UnicodeData.txt` | `ff58e5823bd095166564a006e47d111130813dcf8bf234ef79fa51a870edb48f` |
| `unicode-source/CompositionExclusions.txt` | `89e83cf9cc8bef6c1f8bf77e42cf6f0341dfa42e66261f4dbe9b492e7a23c8ee` |

`CompositionExclusions.txt` identifies itself as Unicode 16.0.0. An independent parse of the committed `UnicodeData.txt` and `CompositionExclusions.txt` reproduced the committed canonical map, compatibility map, combining classes, full composition-exclusion set, and letter, number, other, and format ranges. Coarse ranges do not overlap. Every format-control range sits inside `other`. First/Last rows agree on category, combining class, and decomposition. The runtime loader checks those hashes and the 15 vectors before `profile_ready()` is true. It does not re-parse `UnicodeData.txt` on the validation path. The offline generator rewrote the committed JSON in place during the Node suite and left the worktree clean, so the generator still reproduces the pinned bytes.

## Normalization and category membership

Privacy NFC and NFKC are the contract functions in `unicode_profile.cjs` and `unicode_profile.py`. They decompose from the pinned maps, reorder by pinned combining class, and compose with Hangul syllable arithmetic plus the primary composite map. NFC is used for field-name comparison, session ids, and email spans. NFKC is used only as a detection view. The original string is what a clean field stores.

Letter and number membership is a binary search of `unicode-category-ranges.json`. `L*` is `LETTER`, `N*` is `NUMBER`, every other assigned general category is `OTHER`, and a scalar absent from those ranges is `UNKNOWN_TO_PROFILE`. Assigned `Cf` is `OTHER` and also a format control.

Source search of `packages/optics-evidence-contract/src/` found no `unicodedata` import, no `String.normalize`, no Unicode property escape, and no `str.isalpha` / `str.isalnum`. The generator does not call `unicodedata`. `ord`, `chr`, and UTF-16 code-unit walks are scalar transport. They are not property or normalization lookups.

On Python 3.12 (`unicodedata` 15.0.0) the council compared host category and host NFC/NFKC with the contract for host-assigned characters, including every decomposition and format control. Category mismatches on host-assigned characters: 0. Normalization mismatches on host-assigned characters: 0. Multi-character sequences the host fully assigns (combining-mark order, blocking, Hangul L+V+T, angstrom, fi ligature, NBSP, ZWSP) matched. 113 profile-assigned scalars are `Cn` in that host. For those, the contract result is the privacy decision. Node v22.14.0 reports ICU 76.1 and Unicode 16.0. Its `String.normalize("NFKC")` maps U+1CCF0 to U+0030. The validator does not call that API. Python 3.10, 3.11, and 3.12 leave U+1CCF0 unchanged under host NFKC, and they still omit the outlined PAN.

Spot checks:

| Scalar | Profile | Host Python 3.12 | Contract NFKC |
| --- | --- | --- | --- |
| U+0870 ARABIC LETTER ALEF WITH ATTACHED FATHA | `LETTER` | `Lo` on 3.11 and 3.12; `Cn` on 3.10 (UCD 13) | identity |
| U+1C89 CYRILLIC CAPITAL LETTER TJE | `LETTER` | `Cn` | identity |
| U+1CCF0 OUTLINED DIGIT ZERO | `NUMBER` | `Cn`; host NFKC identity | U+0030 |
| U+1CCF4 / U+1CCF9 | `NUMBER` | `Cn` | U+0034 / U+0039 |
| U+10D40 GARAY DIGIT ZERO | `NUMBER` | `Cn`; no compatibility decomposition in the UCD line | identity |
| U+0378 | `UNKNOWN_TO_PROFILE` | `Cn` | identity |
| U+200E, U+200B, U+00AD, U+061C, U+FEFF, U+E0001, U+E0020 | `OTHER` and format | `Cf` | identity |

## Unknown profile and damaged tables

A copy of the package with each of these faults, then a fresh import, returned `REJECT_RECORD` / `VALIDATOR_FAULT` / issue location `CONFIGURATION` / scan state `UNAVAILABLE` / `privacy_event` null / `record` null. The canonical JSON did not contain the input PAN `4111111111111111`.

- `unicode-category-ranges.json` deleted
- one byte of that file flipped, so the metadata hash no longer matches
- the metadata hash for that file replaced with 64 zeroes, file bytes left intact
- one byte of `UnicodeData.txt` flipped, so the source hash no longer matches

The suite's `setProfileUnavailableForTest(true)` path does the same for a present table. Input text is not copied into the result.

## Corpus

220 shared fixtures. Counts from the corpus expectations, and the suites asserted each fixture:

| Disposition | Count |
| --- | --- |
| `ACCEPT` | 35 |
| `NORMALIZE` | 15 |
| `STRIP` | 23 |
| `REJECT_FIELD` | 121 |
| `REPLACE_WITH_SAFE_CATEGORY` | 9 |
| `REJECT_RECORD` | 17 |

Reason counts: `REDACTION_DROP` 57, `OK` 36, `DETECTOR_MATCH` 36, `MAX_SIZE_EXCEEDED` 24, `NORMALIZED` 7, `UNKNOWN_FIELD_OMITTED` 6, `CONTEXT_REJECTED` 6, `PROHIBITED_FIELD_NAME` 6, `UNSUPPORTED_COMPLEX_VALUE` 6, `SESSION_ID_REJECTED` 5, `CONFLICTING_PROVENANCE` 5, `LEGACY_UNMARKED` 4, `MISSING_REQUIRED_STATUS` 4, `ACCESSOR_PROPERTY_FORBIDDEN` 3, `PROMPT_COMPLETION_EXCLUDED` 2, `UNKNOWN_FIELD_REDACTED` 2, and one each of `BAGGAGE_OMITTED`, `DESTINATION_CONFLICT`, `PROVENANCE_INSUFFICIENT`, `SIMULATED_DEMO`, `SCHEMA_STATUS_CORRECTED`, `ENFORCEMENT_ACTION_EXCLUDED`, `OPTICS_WRITE_FAILURE`, `ANNOTATION_ORIGIN_REFUSED`, `QUERY_STRIPPED`, `DUPLICATE_CANONICAL_FIELD`, `OPTIMISTIC_DEFAULT_FORBIDDEN`.

## Test matrix

| Runtime | Unicode data | Result |
| --- | --- | --- |
| Node v22.14.0, ICU 76.1, `process.versions.unicode` 16.0 | host Unicode 16.0 | `node --test tests/optics-evidence-contract/node.test.cjs`: 13 pass, 0 fail |
| Python 3.12.3 | `unicodedata` 15.0.0 | 12 tests OK, canonical JSON matched Node for all 220 fixtures |
| Python 3.11.16 | `unicodedata` 14.0.0 | 12 tests OK, canonical JSON matched Node for all 220 fixtures |
| Python 3.10.21 | `unicodedata` 13.0.0 | 12 tests OK, canonical JSON matched Node for all 220 fixtures |
| Windows | | `NOT_TESTED` |
| macOS | | `NOT_TESTED` |
| WSL | | `NOT_TESTED` |
| Node versions other than v22.14.0 | | `NOT_TESTED` |

Python 3.10 and 3.11 were not on the image. The council installed CPython 3.10.21 and 3.11.16 with `uv` and ran the suite there. The host OS for every run was Linux.

## Council probes outside the corpus

Canonical JSON for these inputs matched across Node v22.14.0 and Python 3.10, 3.11, and 3.12. "Omitted" means the original scalar and the ASCII fold of a detected secret were absent from the canonical result.

| Probe | Result on every claimed runtime |
| --- | --- |
| Path `/pay/` plus U+1CCF0–U+1CCF9 for `4111111111111111` | `REJECT_FIELD` / `REDACTION_DROP`. Path omitted. `privacy_event` `DESTINATION_COMPONENT_REDACTED` |
| Same outlined run, 12 digits | `ACCEPT` / `OK`. Stored. Below the 13-digit floor |
| Greek alpha before the 16 outlined digits | Omitted. A non-ASCII neighbor does not suppress |
| ASCII `a` before the 16 outlined digits | Stored. Suppression runs on the NFKC view |
| U+FF21 (fullwidth A) before the 16 outlined digits | Stored. NFKC of U+FF21 is ASCII `A`, so the existing letter-boundary rule suppresses |
| Four U+200E inside an ASCII PAN | Omitted |
| ZWSP, U+200E, U+00AD, U+061C, and U+E0020 together inside an ASCII PAN | Omitted |
| U+E0020 alone inside an ASCII PAN | Omitted |
| `/a` + U+0870 + `@b.co` | Omitted, including on Python 3.10 where host category is `Cn` |
| `/a` + U+1C89 + `@b.co` | Omitted |
| `/a` + U+1CCF0 + `@b.co` | Omitted. Profile `NUMBER` counts as email alnum |
| `/a` + U+10D40 + `@b.co` | Omitted. Garay digit is `NUMBER` and has no compatibility decomposition |
| `/a` + U+10FFFF + `@b.co` | Omitted. Absent from the profile, so `UNKNOWN_TO_PROFILE` |
| `/hello` plus U+0870, U+1C89, U+0378, or one ZWSP and no secret | Stored. No privacy event |
| `AKIA` with one U+1C89 or one U+1CCF0 inserted, plus an alnum tail | `REJECT_FIELD` / `DETECTOR_MATCH`. Value omitted |
| `AKIA` with two non-format insertions (U+1C89 and U+0870) | `ACCEPT` / `OK`. Label stored. This is outside the one-insertion bound |
| Six U+200E inside `AKIA`, five ZWSP inside `ghp_`, U+00AD inside `Bearer` | Omitted |
| `product_health.detail_code` `AK` + U+200E + `IAIOSFODNN7EXAMPLE` | `REJECT_FIELD` / `DETECTOR_MATCH`. Value omitted |
| Field name `sk-` + ZWSP + `CANARYEXTRA0001` | `REJECT_FIELD` / `DETECTOR_MATCH`. Locator `UNKNOWN_FIELD_REDACTED_1`. Raw name absent |
| Exact field name `api_key` | `STRIP` / `REDACTION_DROP`. Locator is the exact name. Value absent. Closed safe-grammar rule for an exact catalog name |
| Missing `optics_status` and `action` | `NORMALIZE` / `MISSING_REQUIRED_STATUS`. Action absent. `privacy_event` null |
| Inherited `vantio_trace_id` without producer and version | `REPLACE_WITH_SAFE_CATEGORY` / `PROVENANCE_INSUFFICIENT`. Basis `ASSERTED_CONTEXT` |
| 8193 `!` | `REJECT_FIELD` / `MAX_SIZE_EXCEEDED`. `privacy_event` null. Scan `SIZE_ONLY`. Invariant `UNKNOWN` |
| 600 `!` in `path` | `REJECT_FIELD` / `MAX_SIZE_EXCEEDED`. `privacy_event` null. Scan `FULL` |
| ASCII PAN crossing byte 8192 | `MAX_SIZE_EXCEEDED`. Scan `BOUNDARY`. Completeness `SCAN_INCOMPLETE`. `privacy_event` null. Value absent |
| Outlined PAN with 10 digits inside the 8192-byte window and 6 past it | `MAX_SIZE_EXCEEDED`. Scan `SIZE_ONLY`. Completeness `NONE`. `privacy_event` null. Value absent |
| Outlined PAN fully inside the scanned prefix of an oversized string | `MAX_SIZE_EXCEEDED`. Scan `MATCHED_IN_PREFIX`. `privacy_event` `DESTINATION_COMPONENT_REDACTED`. Value absent |
| Python `bytes`, `bytearray`, `memoryview` and Node `Buffer`, `Uint8Array`, and a `Uint8Array` subarray, as the root and as `path` | `REJECT_FIELD` / `UNSUPPORTED_COMPLEX_VALUE`. `privacy_event` null. No decoded PAN |

## Seats

| # | Seat | Result | Rationale |
| --- | --- | --- | --- |
| 1 | Privacy engineering | `PASS_WITH_NONBLOCKING_NOTES` | Outlined PANs, U+0870, and U+1C89 are omitted on every claimed runtime. Format controls do not hide a PAN or a one-insertion prefix. The one-insertion bound and ASCII-letter suppression after NFKC are unchanged limits. |
| 2 | Unicode/data-table integrity | `PASS` | Independent derivation matches the committed tables. Host-assigned NFC/NFKC matches the contract. Damaged hashes fail closed. |
| 3 | Observability semantics | `PASS_WITH_NONBLOCKING_NOTES` | Size-only input stays privacy-null. An ASCII candidate cut by the cap is `BOUNDARY` / `SCAN_INCOMPLETE`. An outlined-digit tail cut by the cap is `SIZE_ONLY` and still omits the value. |
| 4 | Node security | `PASS` | No ICU normalization or category API on the privacy path. Binary containers are rejected without a decode. |
| 5 | Python security | `PASS` | No `unicodedata` category or normalization on the privacy path. The same containers and table faults fail closed. |
| 6 | Cross-language conformance | `PASS` | Corpus canonical JSON matches across Node and Python 3.10, 3.11, and 3.12. Council probes matched the same way. |
| 7 | Application fail-open | `PASS` | Missing, corrupt, and hash-mismatched profile data returns `VALIDATOR_FAULT` and does not copy the input PAN. |
| 8 | Compatibility | `PASS` | Live CLI 0.3.24 and Python 3.1.0 are untouched. The frozen display helper test passed. |
| 9 | Cross-platform | `PASS_WITH_NONBLOCKING_NOTES` | Linux only. Windows, macOS, WSL, and other Node versions are `NOT_TESTED`. Three Python Unicode versions on this host did not change a disposition. |
| 10 | Release and scope control | `PASS` | Diff stays in the private package, its tests, and internal docs. PR #58 stays draft. |
| 11 | Customer diagnostics | `PASS_WITH_NONBLOCKING_NOTES` | Secrets probed here are absent from diagnostics. The outlined-digit cut is reported as size-only rather than an incomplete scan. |
| 12 | Evidence verification | `PASS` | Hashes, re-derivation, corpus, failure copies, and both-language probes were run in this council. |
| 13 | Product positioning | `PASS` | Docs keep the package private, unshipped, and not a live runtime control. They do not claim host-Unicode independence beyond the pinned 16.0.0 tables. |

No seat is `NEEDS_REVISION` or `BLOCKED`.

## Answers

1. Host Unicode version does not alter a disposition. Python 3.10 (UCD 13), 3.11 (UCD 14), 3.12 (UCD 15), and Node Unicode 16 produced the same canonical JSON for the outlined PAN, the U+0870 email, and the U+1C89 email.
2. Host NFKC does not alter a disposition. Python host NFKC leaves U+1CCF0 in place. The contract maps it to U+0030 and omits the PAN. The privacy path does not call host NFKC.
3. Host letter/number membership does not alter a disposition. U+0870 is `Cn` on Python 3.10 and `Lo` on 3.11 and 3.12. U+1C89 is `Cn` on all three. The profile calls both `LETTER`, and every runtime omits the email.
4. U+1CCF0–U+1CCF9 are not stored for the PAN-shaped path or the mixed ASCII/outlined path. They are stored when the NFKC view has an adjacent ASCII letter, including when that letter is the NFKC of U+FF21. That is the existing suppression rule, and both languages agree.
5. U+0870 and U+1C89 do not produce divergent email outcomes. All four claimed runtimes omit `/a` + that letter + `@b.co`.
6. Format controls do not hide a PAN or a governed prefix. U+200E, repeated ZWSP, soft hyphen, Arabic letter mark, and non-BMP tag characters were removed in the detector view, and the original value was omitted.
7. One non-ASCII insertion does not hide `AKIA`. A second non-format insertion is outside the pinned budget of one and can leave the label stored.
8. A size-only input does not produce a privacy event. 8193 `!` is `MAX_SIZE_EXCEEDED`, `privacy_event` null, scan `SIZE_ONLY`, invariant `UNKNOWN`.
9. The listed binary containers do not receive divergent reason codes. Root and field forms are `REJECT_FIELD` / `UNSUPPORTED_COMPLEX_VALUE` on Node and Python.
10. Missing or corrupt table data does not fail open. Each damaged copy rejected the record and left the PAN out of the result.
11. Corpus canaries and the council's secret strings did not appear in canonical output when the case was a detection, a table fault, or a binary reject. An exact catalog name such as `api_key` is still echoed as a strip locator. Its value is not.
12. The closed blockers did not regress. The shared corpus, including the B1–B8 fixtures, passed on Node and on Python 3.10, 3.11, and 3.12.
13. Live product imports did not change. The diff against main contains none of the CLI or SDK trees, and the scope test found no `optics-evidence-contract` import there.
14. Out-of-scope capability did not enter the PR. No SQLite, migration, UI, daemon, exporter, alerting, stable schema, or release version bump of CLI 0.3.24 or Python 3.1.0.
15. The docs do not overclaim Unicode coverage or runtime protection. They name profile `PKG01-UCD-16.0.0`, say host ICU and `unicodedata` are not the privacy decision, and mark Windows, macOS, WSL, and other Node versions `NOT_TESTED`.

## Former blockers

B1 through B8 remain covered by the shared corpus. That corpus passed on every claimed runtime in this council. Additional probes for a detector-positive allowlisted `detail_code`, a secret-shaped field name with a format control, a missing status and action, and an inherited trace matched the closed outcomes and matched across languages.

## Non-blocking notes

- The boundary heuristic looks for an ASCII digit tail, an `AKIA` or OpenAI prefix, or an email in the raw scanned prefix. It does not run pinned NFKC first. A partial outlined-digit PAN that crosses the 8192-byte cut is therefore `SIZE_ONLY` with completeness `NONE`, not `BOUNDARY` / `SCAN_INCOMPLETE`. The field is still omitted, `privacy_event` is null, and `privacy_invariant` is `UNKNOWN`. A full outlined PAN inside the scanned prefix is `MATCHED_IN_PREFIX`.
- PAN suppression is decided after NFKC. U+FF21 plus outlined digits is stored because the detection view is ASCII `A` plus ASCII digits. A Greek letter beside the same digits is omitted.
- Governed prefixes allow one non-ASCII insertion. Two insertions can store the label. Format controls are stripped before that budget and do not consume it.
- Exact safe-grammar prohibited names are echoed as strip locators. Detector-shaped names are not.
- Runtime integrity is the metadata hash plus the 15 vectors plus the source-file hashes. A commit that changed a derived table and the metadata hash together would load. The generator suite and this council's re-derivation both match the current commit.
- A long base64-alphabet string can still be treated as a secret. That limit is already written in `KNOWN-LIMITATIONS.md`. The size-only probe used `!` so it would not trip that rule.

## Gate 8

Gate 8 stays open only for this private package. `docs/architecture/optics-foundation/09-IMPLEMENTATION-GATES.md` is not in the diff. S1-G9 and S1-G10 are out of scope. Founder decisions 2–13 stay unresolved. The package is not loaded by the live CLI or the live Python SDK.

## Recommendation

No further revision is required for the pinned-Unicode privacy locks. Source-only merge of draft PR #58 is a separate founder authorization. This council does not merge, does not mark the PR ready, and does not seal or publish.

## Confirmation

No merge. No live CLI or Python integration. CLI 0.3.24 unchanged. Python 3.1.0 unchanged. No version change of those packages. No SQLite, database, or migration. No UI, daemon, exporter, or alerting. No stable schema. No RC, seal, or publication. No registry, credential, or announcement change.
