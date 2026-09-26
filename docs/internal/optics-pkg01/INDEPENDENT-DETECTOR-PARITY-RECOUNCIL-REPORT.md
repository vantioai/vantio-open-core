# PKG-01 detector-parity re-council

Audience: INTERNAL_RESTRICTED

## Classification

`OPTICS_PKG01_NEEDS_REVISION`

This re-council does not assign `OPTICS_PKG01_COUNCIL_PASSED`. It does not authorize merge, seal, publication, live CLI or Python integration, SQLite, UI, a daemon, OTLP, SIEM, alerting, or a stable schema.

## Identity

| Item | Value |
| --- | --- |
| Re-council agent | `bc-897d4dca-6304-5341-86f7-3aee4d6a3620` |
| Re-council run | https://cursor.com/agents/bc-897d4dca-6304-5341-86f7-3aee4d6a3620 |
| This agent is not | `bc-952b98d0-92d9-5c6a-8224-b08917f03a3a` (revision producer), `bc-9d2eaaed-8a23-520b-8476-c64f679ba455`, `bc-795c2ba1-73bc-5a15-beba-f1505acc58cf`, `bc-a3731408-ea62-5894-8cd4-6f123ad7bc68`, `bc-88b874ba-c80d-593c-be31-7332c8ba3f89` |
| Repository | `vantioai/vantio-open-core` |
| Draft PR | https://github.com/vantioai/vantio-open-core/pull/58 |
| Branch | `implementation/optics-pkg01-evidence-privacy` |
| Tip reviewed | `4a34ce40645ba5aa4495437d4fdfb4f7e91ac156` |
| Prior head | `075b82508fa93b84ce7416512a8d422ed4ca4e49` |
| Authorized base | `311f260a5f1bee1d3dc9b3734fd6910fb1116094` |
| Producer classification | `OPTICS_PKG01_REVISION_READY_FOR_COUNCIL` |

PR 58 was open and draft at review time. `gh pr view 58` returned `headRefOid` `4a34ce40645ba5aa4495437d4fdfb4f7e91ac156`, `isDraft` true, `state` OPEN. Local `HEAD` was that same commit. Tip confirmed equal to PR HEAD: yes.

Earlier council files stay historical. This file does not replace `INDEPENDENT-COUNCIL-REPORT.md` or `INDEPENDENT-RECOUNCIL-REPORT.md`.

## Scope attestation

Diff of `311f260a5f1bee1d3dc9b3734fd6910fb1116094..4a34ce40645ba5aa4495437d4fdfb4f7e91ac156` is 32 files, all under:

- `packages/optics-evidence-contract/`
- `tests/optics-evidence-contract/`
- `docs/internal/optics-pkg01/`

The revision delta `075b82508fa93b84ce7416512a8d422ed4ca4e49..4a34ce40645ba5aa4495437d4fdfb4f7e91ac156` is 19 files inside those same trees, including new `contract/detector-classes.json`. No file under `packages/vantio-cli/` or `packages/vantio-agent-sdk-py/` changed. `@vantio/cli` remains `0.3.24`. `vantio-agent-sdk` remains `3.1.0`. No workflow, architecture, SQLite, migration, UI, daemon, exporter, or alerting file is in the diff.

Files read for this verdict: `detector-classes.json`, `enums.json`, `normalization.json`, `prohibited-fields.json`, `contract-metadata.json`, `privacy.cjs`, `privacy.py`, `validate.cjs`, `validate.py`, `walk.cjs`, `walk.py`, `corpus.json`, the package README, and the internal PKG-01 notes. Privacy sources do not contain `isalpha`, `isalnum`, `casefold`, `toLowerCase`, `toUpperCase`, `.lower(`, `.upper(`, or `toLocale`.

## Detector policy

`detector-classes.json` is the shared ASCII spec. Both languages build `ASCII_ALPHA`, `ASCII_DIGIT`, `ASCII_ALNUM`, `ASCII_HEX`, and `ASCII_BASE64` from that file. ASCII case fold is the code-point range 65–90 or 97–122 with delta 32 or −32. `MRN:` stays case-sensitive. Credential tails treat a non-ASCII code point as an insertion when the prefix itself is contiguous. PAN suppression uses `ASCII_ALPHA` only.

Email membership and the detection fold do not use that pinned table. Email uses the host Unicode general categories `L` and `N` (`\p{L}` / `\p{N}` on Node, `unicodedata.category` on Python). The second detection pass is host `NFKC` plus the small confusable map. Those two operations follow the Unicode version linked into the runtime.

Measured databases on this host:

| Runtime | Unicode data | L/N code points | NFKC mappings that change a character |
| --- | --- | --- | --- |
| Node v22.14.0, ICU 76.1 | 16.0 | 142939 | 4964 |
| CPython 3.10.21 | 13 | 133022 | 4807 |
| CPython 3.11.16 | 14 | 133547 | 4866 |
| CPython 3.12.3 | 15.0 | 137935 | 4928 |

Node's L/N set is a superset of each CPython set on this host. 157 NFKC mappings disagree across the four runtimes. Ten of those are U+1CCF0–U+1CCF9, which Node NFKC-maps to ASCII `0`–`9`. CPython 3.10, 3.11, and 3.12 leave those code points unchanged.

## Precedence

The reported reason is the highest index in `enums.json` `reason_priority`. `MAX_SIZE_EXCEEDED` (later in that list) outranks `DETECTOR_MATCH` and `REDACTION_DROP`. The value is still omitted when a detector also matched. Session overflow under the session byte cap keeps `SESSION_ID_REJECTED`.

`detector-classes.json` also has a coarser `precedence` list that names prohibited field names and detector hits before excessive size. That list is not the selector. The selector matches the `reported_reason` sentence in the same file. On ASCII size-only inputs under the field caps, both languages follow the enum order.

## Corpus

185 fixtures. Per-fixture canonical strings from Node v22.14.0 and from CPython 3.10.21, 3.11.16, and 3.12.3 compared equal: 0 differences.

Disposition counts, from those canonical results: `ACCEPT` 33, `NORMALIZE` 15, `STRIP` 23, `REJECT_FIELD` 88, `REPLACE_WITH_SAFE_CATEGORY` 9, `REJECT_RECORD` 17.

Reason counts: `REDACTION_DROP` 45, `OK` 34, `DETECTOR_MATCH` 25, `MAX_SIZE_EXCEEDED` 17, `NORMALIZED` 7, `UNKNOWN_FIELD_OMITTED` 6, `CONTEXT_REJECTED` 6, `PROHIBITED_FIELD_NAME` 6, `SESSION_ID_REJECTED` 5, `CONFLICTING_PROVENANCE` 5, `LEGACY_UNMARKED` 4, `MISSING_REQUIRED_STATUS` 4, `ACCESSOR_PROPERTY_FORBIDDEN` 3, `UNSUPPORTED_COMPLEX_VALUE` 3, `PROMPT_COMPLETION_EXCLUDED` 2, `UNKNOWN_FIELD_REDACTED` 2, and one each of `BAGGAGE_OMITTED`, `DESTINATION_CONFLICT`, `PROVENANCE_INSUFFICIENT`, `SIMULATED_DEMO`, `SCHEMA_STATUS_CORRECTED`, `ENFORCEMENT_ACTION_EXCLUDED`, `OPTICS_WRITE_FAILURE`, `ANNOTATION_ORIGIN_REFUSED`, `QUERY_STRIPPED`, `DUPLICATE_CANONICAL_FIELD`, `OPTIMISTIC_DEFAULT_FORBIDDEN`.

Privacy-event counts on the same results: null 106, `DESTINATION_COMPONENT_REDACTED` 33, `DETECTOR_MATCH` 26, `REDACTION_DROP` 20.

The producer disposition and reason counts match this recount. The corpus does not include U+1CCF0–U+1CCF9 or a letter that exists in only one of these Unicode versions.

## Test matrix

| Runtime | Command result | Unicode |
| --- | --- | --- |
| Node v22.14.0 | `node --test tests/optics-evidence-contract/node.test.cjs`: 10 pass, 0 fail | 16.0 |
| CPython 3.10.21 | `python3.10 -m unittest tests/optics-evidence-contract/python_test.py`: 9 tests, OK | 13 |
| CPython 3.11.16 | `python3.11 -m unittest ...`: 9 tests, OK | 14 |
| CPython 3.12.3 | `python3 tests/optics-evidence-contract/python_test.py`: 9 tests, OK | 15.0 |
| Windows | `NOT_TESTED` | |
| macOS | `NOT_TESTED` | |
| WSL | `NOT_TESTED` | |
| Other Node versions | `NOT_TESTED` | |

Host: Linux `6.12.94+` x86_64. No npm install and no pip install of this package. CPython 3.10.21 and 3.11.16 were installed for this re-council with `uv` because the image had only 3.12.3.

## Council probes outside the corpus

66 JSON records, run on Node and on CPython 3.10, 3.11, and 3.12. 62 agreed. Four diverged. Additional `!` byte-boundary records were compared on Node and CPython 3.12.3. Complex values were compared on Node and CPython 3.12.3. The annotation walk-cap case was also run on CPython 3.10.21.

### Divergent

| Probe | Node v22.14.0 | CPython 3.10.21 | CPython 3.11.16 | CPython 3.12.3 |
| --- | --- | --- | --- | --- |
| Path `/pay/` plus U+1CCF4/U+1CCF1 shaped as a 16-digit PAN | `REJECT_FIELD` / `REDACTION_DROP` / `DESTINATION_COMPONENT_REDACTED`. Path absent. | `ACCEPT` / `OK`. Privacy null. Path stored. | Same as 3.10. | Same as 3.10. |
| Path `/pay/4111` plus twelve U+1CCF1 | Same rejection. Path absent. | `ACCEPT` / `OK`. Path stored. | Same as 3.10. | Same as 3.10. |
| Path `/a` + U+0870 + `@b.co` (Arabic letter alef with attached fatha) | `REJECT_FIELD` / `REDACTION_DROP` / `DESTINATION_COMPONENT_REDACTED`. Path absent. | `ACCEPT` / `OK`. Path stored. | Same rejection as Node. | Same rejection as Node. |
| Path `/a` + U+1C89 + `@b.co` | Rejected, path absent. U+1C89 is a letter in Unicode 16. | `ACCEPT` / `OK`. Path stored. Category `Cn` on 3.10. | `ACCEPT` / `OK`. Path stored. | `ACCEPT` / `OK`. Path stored. Category `Cn` on 3.12. |

Node `containsProhibited` is true for the compatibility-digit paths because NFKC yields ASCII digits and the PAN scan hits. All three CPython builds return false and emit the path. The contiguous ASCII string `4111111111111111` is absent from every canonical result. The Python results still contain the preimage path.

### Agreed, locked behavior

All four runtimes agreed on these outcomes:

- PAN adjacent to U+03B1, U+00E9, NFD `e` + U+0301, emoji U+1F600, U+0627, U+4E00, U+AC00, U+05D0, or U+0905: `REJECT_FIELD` / `REDACTION_DROP` / `DESTINATION_COMPONENT_REDACTED`. Path absent. Contiguous test PAN absent.
- PAN with an adjacent ASCII letter, before or after: `ACCEPT` / `OK`. Path stored, including the contiguous test PAN. This matches the documented ASCII-letter gap.
- Contiguous prefixes with an interior non-ASCII tail and with ASCII case changes (`sK-proj-`, `SK-ANT-`, `bEaReR`, `bAsIc`, `EYJ`, `GhP_`, `akIA`, `aiZA`, `asia`, `GitHub_PAT_`, `MRN:`): `REJECT_FIELD` / `DETECTOR_MATCH` on an allowlisted label. Value absent.
- `Mrn:ABCDEF` stored. `Bearer` with U+03B1 in place of the required space stored.
- Prefix broken by U+03B1 or U+200B (`s` + insertion + `k-` + tail) stored on every runtime.
- U+200B inside a 16-digit run stores the path. NBSP (U+00A0) and ideographic space (U+3000) between groups are rejected, because NFKC maps those spaces to ASCII space on every runtime tested.
- `/` + 300 U+03B1: 601 UTF-8 bytes, `REJECT_FIELD` / `MAX_SIZE_EXCEEDED`, privacy null.
- Plain Greek path stored. The same path plus `%20` is `REDACTION_DROP` because a non-ASCII byte beside `%` fails the percent-decode closed.
- Sensitive query, userinfo, `://` plus a canary, and a broken host plus a canary: privacy `DESTINATION_COMPONENT_REDACTED`. Canary substrings absent.
- Missing `optics_status` stores `UNAVAILABLE`. Missing `action` omits action. Unknown optics token `SUPER_SUCCESS` stores `UNAVAILABLE` with `OPTIMISTIC_DEFAULT_FORBIDDEN`.
- Catalog name `api_key` / `API-KEY` with a secret value: `STRIP` / `REDACTION_DROP`. Raw name and canary absent. Allowlisted `detail_code` holding an `sk-` value: `REJECT_FIELD` / `DETECTOR_MATCH`. Value absent.
- Direct `trace_id_basis` `OPTICS_GENERATED` without the witness becomes `ASSERTED_CONTEXT` with `TRACE_BASIS_REPLACED`. Inherited trace without a destination becomes reader label `LEGACY_UNMARKED`. With witness `PKG01_OPTICS_GENERATED_WITNESS`, basis stays `OPTICS_GENERATED` and the witness string is absent from canonical output.

### Byte bounds (`!`, so the run is outside the base64 alphabet)

Node and CPython 3.12.3:

| Input | UTF-8 bytes | Disposition | Reason | Privacy |
| --- | --- | --- | --- | --- |
| `/` + 510 `!` | 511 | `ACCEPT` | `OK` | null |
| `/` + 511 `!` | 512 | `ACCEPT` | `OK` | null |
| `/` + 512 `!` | 513 | `REJECT_FIELD` | `MAX_SIZE_EXCEEDED` | null |
| `!` × 8192 as a path | 8192 | `REJECT_FIELD` | `MAX_SIZE_EXCEEDED` | null |
| `!` × 8193 as a path | 8193 | `REJECT_FIELD` | `MAX_SIZE_EXCEEDED` | `DESTINATION_COMPONENT_REDACTED` |
| annotation `!` × 280 | 280 | `ACCEPT` | `OK` | null |
| annotation `!` × 281 | 281 | `REJECT_FIELD` | `MAX_SIZE_EXCEEDED` | null |
| annotation `!` × 8193 | 8193 | `REJECT_FIELD` | `REDACTION_DROP` | `REDACTION_DROP` |

CPython 3.10.21 matches the 8193-byte annotation row. A source label of 121 `a` is `MAX_SIZE_EXCEEDED` with privacy null. A source label of 8193 `a` is `INVALID_FORMAT` with privacy null, because the walk has already replaced the string with a bound marker. A long run of `a` under the field cap and over the base64 run cap is treated as prohibited on every runtime. That matches the existing long-base64 limitation. The `!` rows are the size-only measurement.

### Complex values

Node and CPython 3.12.3, getter call count 0, canary absent:

| Input | Node | Python |
| --- | --- | --- |
| Function, lambda, builtin, function-valued field | `REJECT_FIELD` / `UNSUPPORTED_COMPLEX_VALUE` | same |
| Plain class instance | `REJECT_RECORD` / `UNSUPPORTED_COMPLEX_VALUE` | same |
| Accessor or setter | `REJECT_RECORD` / `ACCESSOR_PROPERTY_FORBIDDEN` | same |
| Async function | `REJECT_FIELD` / `UNSUPPORTED_COMPLEX_VALUE` | |
| Bound method, callable instance | | `REJECT_FIELD` / `UNSUPPORTED_COMPLEX_VALUE` |
| Callable instance that also has a property | function-with-getter: `REJECT_FIELD` / `UNSUPPORTED_COMPLEX_VALUE` | same reason, getter not called |
| Nested `bytes` / `bytearray` | | `REJECT_RECORD` / `HOSTILE_INPUT` |
| Top-level `bytes` | | `REJECT_RECORD` / `RECORD_TYPE_REJECTED` |
| `Buffer`, `Uint8Array`, `Map` | `REJECT_RECORD` / `ACCESSOR_PROPERTY_FORBIDDEN` | |
| `Date` | `REJECT_RECORD` / `UNSUPPORTED_COMPLEX_VALUE` | |
| bigint, symbol, NaN | `REJECT_RECORD` / `HOSTILE_INPUT` | |

Corpus harnesses for accessor, proxy, class, function, function field, and the isolated non-returning getter stayed green inside the 185-fixture run.

## Required answers

1. Non-ASCII adjacency does not hide a 13–19 ASCII-digit PAN. Greek, é in NFC and NFD, emoji, and the other scripts probed above are rejected on every runtime, and the contiguous PAN is absent. U+200B inside the digit run stores the path on every runtime. U+1CCF0–U+1CCF9 are rejected on Node and stored on CPython 3.10, 3.11, and 3.12.
2. A non-ASCII insertion in the tail of a contiguous governed prefix does not hide the value. The same insertion inside the prefix (`s` + U+03B1 or U+200B + `k-`) stores the value on every runtime. Bearer without an ASCII space is stored on every runtime.
3. ASCII case variation does not bypass a governed prefix. `MRN:` stays case-sensitive. All four runtimes agreed.
4. Node and the three CPython builds compute the same UTF-8 byte lengths for the measured strings, including a lone surrogate as 3 bytes, an emoji as 4, NFD é as 3, and `/` + 300 U+03B1 as 601. Field caps at 511/512/513 and annotation 279/280/281 agree. Host Unicode category and NFKC tables do not agree.
5. Size-only rejection under the published field caps stays privacy-null (`!` path 513, annotation 281, 300 Greek alphas). Above the 8192-byte walk cap, a size-only path still reports `MAX_SIZE_EXCEEDED` and also sets privacy `DESTINATION_COMPONENT_REDACTED`. A size-only annotation of 8193 `!` reports `REDACTION_DROP`.
6. A sensitive omitted destination did not leave privacy null. Query, userinfo, and both malformed canary URLs set `DESTINATION_COMPONENT_REDACTED` on every runtime.
7. Function, lambda, builtin, function-valued field, class instance, and accessor inputs receive the same reason codes on Node and Python. Binary containers do not: Node `Buffer` / `Uint8Array` / `Map` are `ACCESSOR_PROPERTY_FORBIDDEN`; Python nested `bytes` are `HOSTILE_INPUT`; Python top-level `bytes` are `RECORD_TYPE_REJECTED`. No canary from those inputs was emitted.
8. Locked canaries stayed out of canonical output. The compatibility-digit path is present in the Python canonical result and absent from the Node result. The documented ASCII-letter PAN is present on every runtime.
9. Inherited context without the witness cannot keep `OPTICS_GENERATED` or `LOCAL_OBSERVATION`. The witness path keeps `OPTICS_GENERATED` and does not echo the witness.
10. Missing `optics_status` becomes `UNAVAILABLE`. Missing `action` stays omitted. An unknown optics token becomes `UNAVAILABLE` with `OPTIMISTIC_DEFAULT_FORBIDDEN`.
11. No live product import changed.
12. No out-of-scope capability entered the PR.
13. Platform support is described as `NOT_TESTED` for Windows, macOS, WSL, and other Node versions. Detection uniformity is overclaimed. The privacy note says Node and Python share one detector spec and that a Unicode email-like path is rejected. It does not say L/N membership or NFKC follow the host Unicode version. Those versions disagree on this host.

## Canary proof

Corpus scan on all 185 canonical strings passed in the Node test and in each Python unittest, including the shared banned tokens. Independent probes found no `sk-CANARY`, `CANARYQUERY`, `CANARYUSER`, `CANARYMALFORM`, `CANARYHOST`, `CANARYNAME`, `CANARYDETAIL`, or `PKG01_OPTICS_GENERATED_WITNESS` in canonical output on any runtime. Function names and getter strings were absent, and accessor call counts stayed 0.

## Parity proof

Corpus canonical strings: 185 ids, 0 mismatches across Node v22.14.0 and CPython 3.10.21, 3.11.16, and 3.12.3.

Independent parity does not hold for the four rows in the divergent table. Those rows are outside the corpus. The wrapper dump files differ in encoding; the per-fixture canonical strings do not.

## Byte-length parity proof

Shared lengths on Node `Buffer.byteLength` and Python `privacy.utf8_bytes`: ASCII `a` 1, U+03B1 2, U+00E9 2, NFD é 3, U+1F600 4, lone surrogate 3, U+10000 4, U+1CCF1 4, `/` + 300 U+03B1 = 601, `/` + 512 `!` = 513.

## Destination-redaction proof

Token query, userinfo, malformed canary URL, and broken-host canary URL: privacy event `DESTINATION_COMPONENT_REDACTED` on Node and all three CPython builds. Canary substrings absent. Host remains when the URL still has a safe host. A path-only PAN next to U+03B1, with the host omitted, keeps that same privacy category and omits the path.

## Complex-value parity proof

See the complex-value table. Named function and accessor cases match. Binary containers do not share one reason code. No secret from those values was emitted.

## Cross-platform evidence

Exercised here: one Linux x86_64 host, Node v22.14.0, CPython 3.10.21, 3.11.16, and 3.12.3. Windows, macOS, WSL, and other Node builds remain `NOT_TESTED`. The Unicode-version split is already visible across CPython minor versions on this single OS.

## Seats

Overall is `NEEDS_REVISION` because four seats are `NEEDS_REVISION`. No seat is `BLOCKED`.

| # | Seat | Result | Rationale |
| --- | --- | --- | --- |
| 1 | Privacy engineering | `NEEDS_REVISION` | CPython stores a path that Node's NFKC treats as a 16-digit PAN, and CPython 3.10 stores an email-like path the other claimed runtimes reject. |
| 2 | Observability semantics | `PASS_WITH_NONBLOCKING_NOTES` | Enum reason order, missing status, and provenance replacement agree. The 8192-byte walk cap can report a size-only annotation as `REDACTION_DROP`. |
| 3 | Node security | `PASS_WITH_NONBLOCKING_NOTES` | Node fail-closes the compatibility-digit PAN and the divergent emails. U+200B inside a PAN, and a broken prefix, still store on Node. |
| 4 | Python security | `NEEDS_REVISION` | Python 3.10, 3.11, and 3.12 accept and emit the U+1CCF0–U+1CCF9 path with privacy null. |
| 5 | Cross-language conformance | `NEEDS_REVISION` | Four probed inputs produce different dispositions across the claimed matrix. ASCII class tables match. Host Unicode tables do not. |
| 6 | Application fail-open | `PASS` | Corpus fail-open, detached application result, and isolated non-returning getter tests passed. Injected fault text is not copied. |
| 7 | Compatibility | `PASS` | Frozen CLI `applicationStatusFromHttp` check passed. Live writer files are unchanged. |
| 8 | Cross-platform | `PASS_WITH_NONBLOCKING_NOTES` | Linux matrix above is real. Windows, macOS, WSL, and other Node versions are `NOT_TESTED`. |
| 9 | Release and scope control | `PASS` | Diff stays inside the three allowed trees. Package remains private, `schema_version` 0, `unstable-pre-1.0`. PR stayed draft. |
| 10 | Customer diagnostics | `NEEDS_REVISION` | On the divergent Python accepts, `privacy_event` is null and the reason is `OK`, so the stored preimage is not flagged. |
| 11 | Evidence verification | `PASS_WITH_NONBLOCKING_NOTES` | The 185-fixture canonical match is real and was re-run. It does not cover the characters that diverge. |
| 12 | Product positioning | `NEEDS_REVISION` | Internal notes describe one shared Unicode email outcome and one shared detector spec. They do not disclose host Unicode version skew. Platform `NOT_TESTED` labels are accurate. |

## Remaining limitations

These agreed on every runtime and are recorded as residuals, not as the revision driver:

- An ASCII letter beside a PAN still stores the PAN.
- U+200B inside a digit run stores both halves.
- A non-ASCII code point inside `sk-` or `Bearer`'s required space stores the tail.
- A non-ASCII path that also contains `%` is privacy-rejected even when the decoded text is ordinary.
- Strings above 8192 bytes can be labeled with a privacy reason because the walk marker is treated as prohibited, or because the field handler no longer sees a string.
- Node `Buffer` and Python `bytes` do not share one reason code.
- There is no in-process timeout for a getter that never returns.

## Gate 8

PKG-01 remains a private contract package. `docs/architecture/optics-foundation/09-IMPLEMENTATION-GATES.md` is not in this diff. Live CLI 0.3.24 and Python SDK 3.1.0 do not import the package. No run file or database is created by these tests.

## Next recommendation

Revise again. Do not treat this tip as merge-source-only.

Pin every Unicode operation that decides a privacy hit, including NFKC and the `L`/`N` email classes, to data both languages share. Add fixtures for U+1CCF0–U+1CCF9 and for U+0870 and U+1C89, and require one disposition. The closed direction is to omit the value on every claimed runtime. Leave the walk-cap size-only rows as `MAX_SIZE_EXCEEDED` with a null privacy event unless a detector matched the original bytes. State the host-Unicode dependency until that pin exists.

## Confirmations

No merge. PR 58 was left draft. No live CLI or Python integration. CLI `0.3.24` unchanged. Python `3.1.0` unchanged. No version change. No SQLite, database, or migration. No UI, daemon, exporter, or alerting. No stable schema. No RC, seal, or publication. No registry, credential, or announcement change.
