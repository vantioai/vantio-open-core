# Benchmark and performance qualification — program boundary

Audience: INTERNAL_RESTRICTED

Producer role: planning producer only. This agent writes the comparator and the qualification scaffold. It does not sit the independent council, does not self-assign a council pass, and does not authorize a benchmark run, a deploy, or a publish.

Producer identity: Cursor cloud agent `bc-e0913dd4-07fa-5610-a4fe-8178e8f2b6b6`, model Grok 4.7.

Producer URL: https://cursor.com/agents/bc-e0913dd4-07fa-5610-a4fe-8178e8f2b6b6

Producer classification: `BENCHMARK_FRAMEWORK_READY_FOR_COUNCIL`

That classification means this packet is ready for a separate council. The council file remains `PENDING_INDEPENDENT_COUNCIL`.

## 1. Locked input

| Item | Value |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Starting commit | `89f95099d0dce463307eb75d78e7fcf2ef99feb2` |
| Commit subject | Merge pull request #83 from `vantioai/cursor/pe-ws4-vocabulary-binding-f9f5` |
| Branch | `cursor/benchmark-framework-b6b6` |
| Writable path | `docs/planning/benchmark-framework/` |
| Comparison basis | Documents in this repository. Private Phantom Engine bodies are not copied. |
| CLI | `@vantio/cli` `0.3.24` in `packages/vantio-cli/package.json`. This force does not edit that package. |

## 2. What this force does

- Defines a seven-stage claim ladder. A later stage stays `NOT_REACHED` until every earlier stage is `SATISFIED`.
- Scores Optics, Phantom Engine, and Enterprise on nineteen dimensions from documented behavior.
- Records lineup checkmarks with `claim_effect` `DOES_NOT_SATISFY_ANY_STAGE`.
- Publishes a performance scaffold whose every metric is `NOT_MEASURED`.
- Adds a checker that fails when a stage is skipped or a metric carries a number without a measurement record.

`COMPARATOR-MATRIX.json` and `PERFORMANCE-SCAFFOLD.json` are normative. `03-SCORE.md` is generated from the same library.

## 3. Closed in this force

| Action | State |
| --- | --- |
| Customer deploy | Closed |
| Stranger-host execution | Closed |
| Announcement | Closed |
| Credential use | Closed |
| Money movement | Closed |
| Reopen of `@vantio/cli` 0.3.24 | Closed |
| Python 3.1.0 byte mutation | Closed |
| Copy of Phantom Engine confidential bodies onto this public tree | Closed |
| Merge of this branch | Closed |
| Live benchmark, load, or uninstall timing | Closed |

## 4. How a stage gets satisfied

Stage 1, `BEST_IN_CLASS_DESIGN_TARGET`, requires a written design: owner, behavior, non-goals, the evidence required to enter stage 2, and a measurement posture of `NOT_SET` or `NOT_MEASURED` unless a founder has set a target. For this population, an Optics design also requires `OPTICS_FOUNDATION_ARCHITECTURE_COUNCIL_PASSED` on the gate that contains it. A planning packet whose council is `PENDING_INDEPENDENT_COUNCIL` stays at stage `NONE`.

Stages 2 through 7 require the previous stage and a filled evidence slot. Every slot in this pack is `NOT_PRESENT`. The checker rejects a `SATISFIED` mark on those stages while the slot is empty.

A documented non-claim stays at `NONE`. Absence is not recorded as `EVIDENCE_BACKED_BEST_IN_CLASS`.

## 5. Checker

Command, from the repository root:

`node --test docs/planning/benchmark-framework/scripts/check-framework.test.mjs`

A passing checker is a structural result. It is not a performance measurement, not a clean-host proof, and not a council verdict.
