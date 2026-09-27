# Optics PKG-02 — independent council report

Audience: INTERNAL_RESTRICTED

Status: `RECORDED`

Producer classification reviewed: `OPTICS_PKG02_PLAN_READY_FOR_COUNCIL`

That producer classification is not this council's verdict.

Council classification: `OPTICS_PKG02_PLAN_COUNCIL_PASSED`

## Identity

| Item | Value |
| --- | --- |
| Council agent | `bc-9401ff14-8a46-5187-b497-2107ad16f590` |
| Council URL | https://cursor.com/agents/bc-9401ff14-8a46-5187-b497-2107ad16f590 |
| Model | Grok 4.7 |
| Reasoning | `xhigh` |
| Context | `500k` |
| Fast | false |
| Reviewed tip | `bfa699ed0ba56b9877fd91341094cd37782fe9e7` |
| Reviewed at (UTC) | `2026-09-27T01:54:47Z` |
| Reviewed at (America/New_York) | `2026-09-26T21:54:47-0400` |
| Verdict | `OPTICS_PKG02_PLAN_COUNCIL_PASSED` |
| Planning PR | https://github.com/vantioai/vantio-open-core/pull/60 |
| Branch | `planning/optics-pkg02-record-conformance` |
| Base | `dc212bca61fe80b65bb2cbab8e8f812c035ff2e0` |

This agent is the PKG-02 planning council. It is not the planning producer `bc-ebb705c2-daab-59d2-85c1-689c7af5499e`. It is not a PKG-01 council. In-repo council identities that this agent does not reuse include `bc-795c2ba1-73bc-5a15-beba-f1505acc58cf`, `bc-88b874ba-c80d-593c-be31-7332c8ba3f89`, `bc-1cc76959-8e57-5a6a-8ced-f51acd350637`, `bc-fd7a995a-0bba-5f0c-955b-f21702e5c6a2`, `bc-5bb719b6-65bf-522c-a9b9-f3a9a96ef08b`, `bc-cef881e2-7866-5523-9e29-1116de3490ab`, and the PR #59 author `bc-897d4dca-6304-5341-86f7-3aee4d6a3620`.

## Tip check

Local `HEAD` at the start of this review was `bfa699ed0ba56b9877fd91341094cd37782fe9e7`. GitHub reported the same SHA as the head of draft PR #60, with base `main` at `dc212bca61fe80b65bb2cbab8e8f812c035ff2e0`. The pull request was open, draft, and unmerged. The parent commit is the starting main named in `PKG02-MANIFEST.json`. The diff of that commit is the fourteen files under `docs/planning/optics-pkg02/` only.

Every `input_sha256` and every `files_sha256` in the producer manifest matched the files on that tip before this report was written.

## Seat table

| # | Seat | Verdict |
| --- | --- | --- |
| 1 | Observability semantics | `PASS_WITH_NONBLOCKING_NOTES` |
| 2 | Privacy engineering | `PASS` |
| 3 | Node instrumentation | `PASS_WITH_NONBLOCKING_NOTES` |
| 4 | Python instrumentation | `PASS_WITH_NONBLOCKING_NOTES` |
| 5 | Record compatibility | `PASS_WITH_NONBLOCKING_NOTES` |
| 6 | Release engineering | `PASS` |
| 7 | Rollback and downgrade | `PASS_WITH_NONBLOCKING_NOTES` |
| 8 | Cross-language conformance | `PASS_WITH_NONBLOCKING_NOTES` |
| 9 | Customer diagnostics | `PASS_WITH_NONBLOCKING_NOTES` |
| 10 | Evidence verification | `PASS` |
| 11 | Developer experience | `PASS_WITH_NONBLOCKING_NOTES` |
| 12 | Scope control and product positioning | `PASS` |

No seat is `NEEDS_REVISION`. No seat is `BLOCKED`.

## Challenges

### Diagnostic dimensions stay separate

`02-SHARED-RECORD-VOCABULARY.md` section 6 assigns optics machinery, workload, HTTP status, transport class, exception type, issue location, lifecycle, coverage, derived phrases, product health, store integrity, and completeness to different fields. `enums.json` `application_status` has no `PARTIAL`. The plan forbids storing `application_status` `PARTIAL` and forbids using optics `SUCCESS` as the future writer's default for "a call was recorded."

The frozen `optics_status` enum still lists `SUCCESS`, `APPLICATION_ERROR`, and `PARTIAL`. This packet does not delete those tokens. Separation is a writer rule and a reader rule on top of the frozen catalog. That is the right boundary for a plan that must not change PKG-01.

`vantio status` reuses the same token names for install, registry, telemetry, directory bytes, and importability (`vantio.js` around the status report). `03-NODE-PYTHON-DELTA.md` says `sdkRows` `UNSUPPORTED` is a different dimension and must not be copied into an observation. `07-CONFORMANCE-TEST-PLAN.md` section 3 refuses those facts as `optics_status` fixtures.

### Old readers and unknown status

`opticsStatusForRecordedCall` in `packages/vantio-cli/bin/optics-cx.cjs` returns `SUCCESS` and takes no arguments. `displayCall` assigns that value to every call object. It does not read a stored `optics_status` or `opticsStatus`. `humanStatus("SUCCESS")` is `Successful`. An unknown token passed to `humanStatus` is returned as that token; the success trap is `displayCall`, which never consults the stored token.

`04-COMPATIBILITY-MATRIX.md` therefore marks future CLI output, future Python output, and PKG-01 contract output as `UNSUPPORTED` when the reader is CLI 0.3.24. The same cells in `RECORD-COMPATIBILITY-MATRIX.json` give that reason in prose. `07-CONFORMANCE-TEST-PLAN.md` section 8 says the old-reader fixture classifies that pairing as `UNSUPPORTED` and does not edit `optics-cx.cjs`.

Contract behavior for a token that is not in the enum is the other direction: `validate.cjs` stores `normalization.missing_optics_status` (`UNAVAILABLE`) and adds `OPTIMISTIC_DEFAULT_FORBIDDEN` when the value is a non-member string. Missing optics status takes the same stored value with `MISSING_REQUIRED_STATUS`.

### Aliases do not fabricate success from absence

Canonical aliases in `RECORD-VOCABULARY.json` rename keys (`opticsStatus`, `hostname`, `status`, `bytes`, `ts`, `pid`, `trace_id`, `generated_at`, and the other listed names). `legacyCallToContract` copies `opticsStatus` onto `optics_status` when the live call has that key. `validate.cjs` then accepts `SUCCESS` only when that value is the one presented. Absence and unknown strings become `UNAVAILABLE`.

Python `_record` sets `opticsStatus` to `SUCCESS` on every appended call, including an unavailable provider outcome (`_http_observe.py`). A detached adapter reading a 3.1.0 file will therefore keep that token. CLI run files omit the field, so the same adapter stores `UNAVAILABLE`. The alias is transporting a token the live writer already stored. It is not inventing `SUCCESS` from a missing or unknown value.

Those Python files also omit `producer`. The contract's missing-origin rule labels them `LEGACY_UNMARKED`. `customer_promote_legacy_unmarked` in `contract-metadata.json` is false. Founder decision 6 stays unresolved. The matrix cells for import and `LEGACY_UNMARKED` are `READ_ONLY` with `may_upgrade_origin` false on every cell.

Legacy `bytes` `0` becomes `response_bytes` null (`validate.cjs`). Explicit `response_bytes` `0` stays `0`. `ok` is not in the legacy call map as a status source. `applicationStatusFromHttp` ignores `ok`.

### Node and Python equivalence under the plan

Future writers that store the same semantic value are compared as canonical JSON after timestamp normalization and alias renaming (`07-CONFORMANCE-TEST-PLAN.md`). The plan does not claim today's files are already those bytes.

Documented differences that remain visible:

- CLI persists an empty `calls` array. Python `_write_run_log` returns when `_calls` is empty.
- CLI exit map stores `call.bytes || 0` at `interceptor.cjs` line 3736. Python HTTP records omit response size.
- CLI timestamps are `toISOString()` (`Z`, milliseconds). Python `isoformat()` is `+00:00` with microseconds. The contract stores `Z` with three fractional digits and rejects a non-zero offset.
- Python stores `failure_kind` and envelope `schema_status`. The CLI run file omits both.
- Envelope `mediation` on Python is a comma join. A non-member string becomes `unknown` in `validate.cjs`. It is not split into extra events.

Option D activates each future writer only after the shared fixtures exist. Units D and E do not share a commit.

### Release sequence and rollback

`05-INTEGRATION-SEQUENCING.md` selects option D and the inert half of option C. The manifest `recommended_sequence` is Unit A, then B parallel with C, then F, then D, then E. `06-RELEASE-AND-ROLLBACK-BOUNDARY.md` gives each unit its own source boundary. No unit includes `@vantio/cli` `0.3.24`. D is `PKG02-FUTURE-CLI-UNASSIGNED` and depends on A, B, and F. E is `PKG02-FUTURE-PYTHON-UNASSIGNED` and depends on A, C, and F. D and E are separate releases.

Rollback of an activated writer stops the new writer for later runs, leaves canonical files on disk, and requires the rolled-back reader to show `UNSUPPORTED` with `schema_status`. It does not map a canonical status back to `SUCCESS`, does not upgrade origin, and does not run a migration. `rewrites_source` is false on all 104 matrix cells. `achievement` is `NOT_SHIPPED` on all 104.

### CLI 0.3.24 stays frozen

`packages/vantio-cli/package.json` version is `0.3.24`. The interceptor reads that version into `cli_version`. This commit does not modify `packages/vantio-cli/`. Units A–F exclude that tree. The future Node template says it does not edit `packages/vantio-cli/bin/` or that package's `package.json` on the frozen line.

### Python 3.1.0 stays unchanged

`pyproject.toml` and `vantio/__init__.py` are `3.1.0`. `3.0.15` appears in `CHANGELOG.md` and `README.md` and is marked never the vehicle. This commit does not modify `packages/vantio-agent-sdk-py/`. Tests that lock `opticsStatus == "SUCCESS"` stay evidence of current behavior (`07-CONFORMANCE-TEST-PLAN.md`).

### PKG-01 stays private

`contract-metadata.json` has `private` true, `schema_version` 0, `schema_status` `unstable-pre-1.0`, `loaded_by_live_cli_0_3_24` false, and `loaded_by_python_3_1_0` false. No `package.json` or `pyproject.toml` outside `packages/optics-evidence-contract/` depends on that package. This commit does not change contract source, Unicode tables, hashes, or the 220-fixture corpus (`tests/optics-evidence-contract/corpus.json` key `cases`).

### Future versions are placeholders

`PKG02-FUTURE-CLI-UNASSIGNED`, `PKG02-FUTURE-NODE-SDK-UNASSIGNED`, `PKG02-FUTURE-PYTHON-UNASSIGNED`, and `PKG02-FUTURE-START-SHA-UNASSIGNED` are the only future identifiers. They are not present as versions in the live package manifests. The Node SDK placeholder is not in the activation order. `@vantio/agent-sdk` `0.2.4` writes no `~/.vantio/runs` file. `reportAnomaly` posts `traceId`, `auditMode`, and `eventPayload` only when ingest is enabled. `VantioActionTaken` does not include `SEVERED`; the example in the same file uses that word anyway. `timestamp_ns` is a number. The matrix row for a future Node SDK local log is `NOT_YET_DECIDED` except where a hard rule already fixes reader behavior.

### Migration and SQLite stay out

`future_store_import` is `NOT_YET_DECIDED` for every writer. `00-PROGRAM-BOUNDARY.md` excludes SQLite, a binding, and migrations. `06-RELEASE-AND-ROLLBACK-BOUNDARY.md` says no rollback path chooses a SQLite binding or rewrites history. Founder decision 9 remains unresolved. `STORE_OPTION_C` stays architecture-only.

### Founder decisions 2–13 stay unresolved

`08-ARCHITECTURE-DECISION-PACK.md` section 35 still lists items 2 through 13 as unresolved. The input hash of that file matched the manifest. This packet does not allowlist usage, cost, or token counts, does not add a seventh annotation origin, does not emit `CURRENT`, and does not allowlist machine hostname. `prohibited-fields.json` still names `machine` and `est_spend_usd`. `02-SHARED-RECORD-VOCABULARY.md` repeats the refusal. The manifest array `unresolved_founder_decisions` is `[2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]`.

Two planning gaps stay open and are not new decision numbers: contract `calls_max` 64 versus uncapped live logs, and whether the Node SDK should ever write a local run log.

### Public claims stay unchanged

The planning commit touches only `docs/planning/optics-pkg02/`. It does not edit README files, the website, changelogs, or customer-facing command text. `scope_complete` stays false. `05-INTEGRATION-SEQUENCING.md` section 5 keeps the product claim on the frozen writers until a later authorized, shipped, and proved writer exists. A matrix cell `FULL` has `achievement` `NOT_SHIPPED`.

### Option D and units A–F

Options A, B, and C are recorded and rejected for activation order. Option D is the selection. B may merge without C. C may merge without B. F can ship before D and E and cannot ship inside the 0.3.24 package. D and E are not combined. The Node SDK is not a unit in this order.

### Frozen CLI reading a future contract record

See the old-reader challenge. The supported statement is `UNSUPPORTED`, because `displayCall` would still show `SUCCESS`.

### PR #59

Classification `SUPERSEDED_HISTORICAL_COUNCIL` matches a fresh read of PR #59:

- Open draft, title `Record PKG-01 detector-parity re-council: NEEDS_REVISION`.
- Head `cursor/optics-pkg01-detector-parity-recouncil-3620` at `320e927e608c15bba5e0181906e1289ebef7735a`.
- Base `implementation/optics-pkg01-evidence-privacy` at `4a34ce40645ba5aa4495437d4fdfb4f7e91ac156`.
- `mergeable_state` `dirty`.
- `4a34ce40645ba5aa4495437d4fdfb4f7e91ac156` is an ancestor of `dc212bca61fe80b65bb2cbab8e8f812c035ff2e0`.
- `8881214` (Unicode pin) and `86e6d04` (`OPTICS_PKG01_COUNCIL_PASSED`) are ancestors of that same main.
- `docs/internal/optics-pkg01/PENDING-COUNCIL.md` on this tree points at the pinned-Unicode pass.
- `docs/internal/optics-pkg01/INDEPENDENT-DETECTOR-PARITY-RECOUNCIL-REPORT.md` is absent on this tree.

This council did not edit, comment on, close, or merge PR #59. Closing it remains a Founder action.

### Templates 08 and 09

`08-FUTURE-NODE-INTEGRATION-FORCE.md` and `09-FUTURE-PYTHON-INTEGRATION-FORCE.md` each carry `NOT AUTHORIZED`, `DRAFT FOR FOUNDER REVIEW`, and `DO NOT EXECUTE`. Both say they are not a Force. This council did not execute them and did not appoint an activation council.

## Nonblocking notes

These notes do not change option D, the version placeholders, or the hard rules.

1. The frozen `optics_status` enum still contains `SUCCESS`, `APPLICATION_ERROR`, and `PARTIAL`. Future writers follow the dimension table in `02-SHARED-RECORD-VOCABULARY.md`. This plan correctly leaves the enum in PKG-01.
2. Unit E still allows an empty `shield()` to be either an explicit `NOT_OBSERVED` envelope or no file, and the release must say which. `07-CONFORMANCE-TEST-PLAN.md` classifies a path the reader cannot open as `UNAVAILABLE` or `OPTICS_ERROR`, and `02-SHARED-RECORD-VOCABULARY.md` reserves `NOT_OBSERVED` for a wrap that ran and stored no supported call. The future Python delta has to keep those outcomes distinct.
3. Unit C says a comma-joined Python `mediation` becomes `unknown` or is split in the copy without inventing events. `validate.cjs` already stores `unknown` for a non-member string. One `mediation` field cannot hold a split. The operative adapter result is `unknown`.
4. A Python 3.1.0 call's stored `opticsStatus` `SUCCESS` survives the alias into canonical `optics_status` because `SUCCESS` is an enum member. Adapter fixtures should show that token beside `LEGACY_UNMARKED` when producer and version are absent. Absence and unknown tokens still become `UNAVAILABLE`.
5. All 120 canonical rows share the reader fallback sentence "Preserve absence." The operative rule is each row's `absent_value_behavior`. That field-specific text matches the contract for missing `optics_status` (`UNAVAILABLE`), missing `action` (omit), and absent `sampling` (fill `UNSAMPLED`).
6. `unknown_status_becomes_success` is false on every matrix cell, including `future_cli` read by `cli_0_3_24`. Read the boolean as "this cell does not authorize the misread." The reason string and the `UNSUPPORTED` class are what record that `displayCall` would still show `SUCCESS`.
7. Unit A is a shared prerequisite. Removing it after B or C has merged is a code rollback of those dependents. Customer files still do not change. D and E remain independently rollback-safe against each other.
8. `applyDispatchGate` `baseCall` does store `bytes: 0`, `status: null`, `ok: true`, and `duration_ms: 0` before the response (`interceptor.cjs`). Other paths in the same file also store `bytes: 0` before completion. The persisted optimistic zero is the exit map at line 3736. The future-writer rule is to omit `response_bytes` until the count is finished, which covers those sites.

## Blockers

None.

## Verdict

All twelve seats are `PASS` or `PASS_WITH_NONBLOCKING_NOTES`.

Overall verdict: `OPTICS_PKG02_PLAN_COUNCIL_PASSED`

## Gate 8

`docs/architecture/optics-foundation/ARCHITECTURE-MANIFEST.json` still lists gate 8 under `council_closed_gates`. This council did not edit that file. This planning return closes the PKG-02 planning review. Implementation stays unauthorized. `attestations.implementation_gate_satisfied` remains false.

## Attestations

| Claim | Result |
| --- | --- |
| Reviewed tip is the producer tip | Yes. `bfa699ed0ba56b9877fd91341094cd37782fe9e7` |
| Council is distinct from the producer and from prior PKG-01 councils | Yes |
| Only `docs/planning/optics-pkg02/` is written by this council | Yes. Report and manifest council fields |
| Producer planning prose in files 00–09 and both record JSON files | Unchanged |
| PKG-01 private and not imported by live CLI, Python 3.1.0, or Node SDK 0.2.4 | Yes |
| CLI `0.3.24`, Python `3.1.0`, Node SDK `0.2.4` | Unchanged |
| No version bump, RC, seal, or publish | Yes |
| No SQLite, migration, UI, daemon, OTLP, SIEM, or alerting | Yes |
| No stable schema | Yes. `stable_schema` false, `schema_version` 0 |
| No live record conversion | Yes |
| No announcement and no public-claim edit | Yes |
| PR #60 left draft | Yes |
| PR #59 untouched | Yes |
| Templates 08 and 09 | Not executed |
| Implementation | Still unauthorized |

## Next recommendation

A later Founder Force may merge this planning branch only, after reading this council record. That Force is not launched here. It must not mark PR #60 ready for a product release, must not merge PR #59, and must not start Units A–F or the templates in `08` and `09`.
