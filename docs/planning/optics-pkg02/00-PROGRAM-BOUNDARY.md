# Optics PKG-02 — program boundary

Audience: INTERNAL_RESTRICTED

Producer role: planning producer only. This agent does not sit the independent council, does not self-assign a council pass, and does not authorize a writer change.

Producer identity: Cursor cloud agent `bc-ebb705c2-daab-59d2-85c1-689c7af5499e`, model Grok 4.7.

Producer URL: https://cursor.com/agents/bc-ebb705c2-daab-59d2-85c1-689c7af5499e

Producer classification: `OPTICS_PKG02_PLAN_READY_FOR_COUNCIL`

That classification means the planning packet is ready for a separate council. It is not a council verdict, not an implementation authorization, and not evidence that any package is proved.

## 1. Locked input

| Item | Value verified at planning time |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Starting commit | `dc212bca61fe80b65bb2cbab8e8f812c035ff2e0` |
| Commit subject | Merge pull request #58 from `vantioai/implementation/optics-pkg01-evidence-privacy` |
| `origin/main` | Same commit. Fetched before this branch was written. |
| Planning branch | `planning/optics-pkg02-record-conformance` |
| Writable path | `docs/planning/optics-pkg02/` only |
| PKG-01 label | `OPTICS_PKG01_MERGED_NO_LIVE_INTEGRATION` |
| Package | `@vantio/optics-evidence-contract` `0.0.0-unstable-pre-1.0` |
| Schema | `schema_status` `unstable-pre-1.0`, `schema_version` `0`, `stable_schema` false |
| Unicode profile | `PKG01-UCD-16.0.0` |
| Corpus | 220 fixtures in `tests/optics-evidence-contract/corpus.json` |
| CLI | `@vantio/cli` `0.3.24` |
| Python | `vantio-agent-sdk` `3.1.0` in `packages/vantio-agent-sdk-py/pyproject.toml` |
| Python 3.0.15 | Changelog only. Not the ship target. |
| Node SDK | `@vantio/agent-sdk` `0.2.4` |
| Store | `STORE_OPTION_C: FOUNDER_RATIFIED_ARCHITECTURE_ONLY` |

Sentences inside merged PKG-01 notes that say draft PR #58 stays draft were written before that merge. This planning force leaves those sentences in place.

## 2. Product principle

Optics is observational. It stores bounded connection metadata rather than prompt or completion content. It must not imply enforcement, and it must not imply coverage beyond supported paths. Optics observes. Phantom Engine enforces. Missing or unavailable evidence stays visible. It is not promoted to success.

## 3. What this force does

- Inventories CLI, Node SDK, and Python record shapes from source, then compares them with the PKG-01 catalog.
- Defines one shared vocabulary for a future Node writer and a future Python writer.
- Locks absent-value dispositions, the status dimensions, the compatibility matrix, the release units, and the rollback rules.
- Writes future Force templates and marks both `NOT AUTHORIZED`, `DRAFT FOR FOUNDER REVIEW`, and `DO NOT EXECUTE`.
- Leaves `10-INDEPENDENT-COUNCIL-REPORT.md` as `PENDING_COUNCIL`.

## 4. What this force keeps closed

- Live CLI, Python SDK, and Node SDK source, tests, and package metadata.
- PKG-01 behavior, Unicode data, expected hashes, and fixtures.
- Package version bumps, release candidates, seals, npm, and PyPI.
- Imports of `@vantio/optics-evidence-contract` into live code.
- Rewrites of existing customer or JSON records.
- SQLite, a binding choice, migrations, UI, a daemon, OTLP, SIEM export, and alerting.
- A stable schema declaration.
- PKG-03.
- Public documentation, website source, and any announcement.
- PR #59. This force does not edit, close, merge, or comment on it.

No PKG-02 implementation gate is satisfied by this packet. Gate 8 is open only for this planning packet. The architecture gate file is not modified.

## 5. PR #59 disposition

Classification: `SUPERSEDED_HISTORICAL_COUNCIL`

Evidence read for this classification:

- PR #59 is an open draft: https://github.com/vantioai/vantio-open-core/pull/59
- Title: `Record PKG-01 detector-parity re-council: NEEDS_REVISION`
- Head: `cursor/optics-pkg01-detector-parity-recouncil-3620` at `320e927e608c15bba5e0181906e1289ebef7735a`
- Base: `implementation/optics-pkg01-evidence-privacy` at `4a34ce40645ba5aa4495437d4fdfb4f7e91ac156`
- GitHub reports `mergeable_state` `dirty`
- The pull request adds `docs/internal/optics-pkg01/INDEPENDENT-DETECTOR-PARITY-RECOUNCIL-REPORT.md` and edits `PENDING-COUNCIL.md`
- That report classified tip `4a34ce40645ba5aa4495437d4fdfb4f7e91ac156` as `OPTICS_PKG01_NEEDS_REVISION` on a 185-fixture corpus and on host Unicode disagreement
- `4a34ce40645ba5aa4495437d4fdfb4f7e91ac156` is an ancestor of `dc212bca61fe80b65bb2cbab8e8f812c035ff2e0`
- Later commits on that line pin Unicode (`8881214`) and record `OPTICS_PKG01_COUNCIL_PASSED` (`86e6d04`)
- Main at the starting commit has profile `PKG01-UCD-16.0.0`, 220 fixtures, and `docs/internal/optics-pkg01/PENDING-COUNCIL.md` pointing at the pinned-Unicode pass
- The detector-parity report file is not on this starting commit

Merging PR #59 would put the pre-pin `NEEDS_REVISION` pointer back into `PENDING-COUNCIL.md`. This force does not do that. Closing the pull request is a Founder action. This classification is not a close instruction.

PKG-02 does not depend on PR #59 as a live record. The vocabulary in this packet is taken from the merged tree.

## 6. Unresolved Founder decisions

Items 2–13 in `docs/architecture/optics-foundation/08-ARCHITECTURE-DECISION-PACK.md` section 35 stay unresolved. This packet does not approve usage, cost, token counts, machine hostname, a seventh annotation origin, or the freshness token `CURRENT`.

Additional planning gaps that are not new Founder decision numbers:

- The contract call bound is 64. Live run logs are not capped at 64. PKG-02 does not raise the bound.
- Whether `@vantio/agent-sdk` should ever write a local run log is not selected. The live Node writer is the CLI interceptor.

## 7. Placeholders

These names do not exist as releases:

| Placeholder | Means |
| --- | --- |
| `PKG02-FUTURE-CLI-UNASSIGNED` | First future `@vantio/cli` version eligible to consume PKG-01. Not `0.3.24`. |
| `PKG02-FUTURE-NODE-SDK-UNASSIGNED` | Not `@vantio/agent-sdk` `0.2.4`. Not selected as the local writer. |
| `PKG02-FUTURE-PYTHON-UNASSIGNED` | First future `vantio-agent-sdk` version eligible to consume PKG-01. Not `3.1.0`. Not `3.0.15`. |
| `PKG02-FUTURE-START-SHA-UNASSIGNED` | Starting commit of a future integration Force. Not this planning tip. |

## 8. Council handoff

`10-INDEPENDENT-COUNCIL-REPORT.md` is `PENDING_COUNCIL`. A separate agent fills it. This producer stops at `OPTICS_PKG02_PLAN_READY_FOR_COUNCIL`.
