# Independent council

Audience: INTERNAL_RESTRICTED

Status: `PENDING_INDEPENDENT_COUNCIL`

Producer classification under review: `OPTICS_OPTION_C_REVALIDATED_READY_FOR_COUNCIL`

Producer: Cursor cloud agent `bc-6c7884b7-0d3c-5c54-84f7-8a5e7bca41fe`, model Grok 4.7.

Producer URL: https://cursor.com/agents/bc-6c7884b7-0d3c-5c54-84f7-8a5e7bca41fe

This file is the producer stub. The revalidation producer does not sit the council and does not write a verdict.

## 1. What a separate council reviews

| Item | Value |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Packet | `docs/planning/optics-option-c-revalidation/` |
| Tests | `tests/optics-option-c-revalidation/` |
| Base the producer re-read | `89f95099d0dce463307eb75d78e7fcf2ef99feb2` |
| Merged plan | `79b53e0e29df047aabb1863b62609ffd7b4dcff7` pull request #69 |
| Plan tip | `f6e90c148ec07b9e0d019dc89e852284d26a7cbf` |
| Classification the producer claims | `OPTICS_OPTION_C_REVALIDATED_READY_FOR_COUNCIL` |
| Amendment | `NOT_REQUIRED` |
| Production-plan council file | Remains `PENDING_COUNCIL` |
| `O7` | Remains `NOT_AUTHORIZED` |

## 2. Seats

| Seat | Scope | Verdict |
| --- | --- | --- |
| 1 | Cited decision bytes and the engine sentence | `UNSAT` |
| 2 | Hash recheck of the merged plan and its architecture inputs | `UNSAT` |
| 3 | Absence of a store file, a dependency, and a selected Node binding | `UNSAT` |
| 4 | Non-amending deltas after pull request #69 | `UNSAT` |
| 5 | O7 entry criteria and the unmet steps | `UNSAT` |
| 6 | Frozen CLI, closed Gate 8, and pending councils | `UNSAT` |

## 3. Checks the council can re-run

From the repository root:

```sh
node --test tests/optics-option-c-revalidation/*.test.cjs
```

Also:

- The diff is `docs/planning/optics-option-c-revalidation/` and `tests/optics-option-c-revalidation/`.
- `docs/planning/optics-production/` and `docs/architecture/optics-foundation/` are unchanged against `89f95099d0dce463307eb75d78e7fcf2ef99feb2`.
- `docs/planning/optics-production/10-INDEPENDENT-COUNCIL-REPORT.md` still says `PENDING_COUNCIL`.
- `docs/architecture/optics-foundation/09-IMPLEMENTATION-GATES.md` still says Gate 8 is closed.
- `@vantio/cli` is `0.3.24`.
- No tracked file name ends in `.sqlite`.
- The engine sentence the producer quotes is the sentence in decision-pack section 12 and A2 section 4.

## 4. Notes for the council

The producer treats three labels as one merge: the Founder brief’s `OPTICS_STORE_OPTION_C_PLAN_MERGED_NO_IMPLEMENTATION`, the in-file `OPTICS_STORE_OPTION_C_VERIFIED_PLAN_READY_FOR_COUNCIL`, and the control-plane `MERGED_PLAN_COUNCIL_PENDING`. The producer does not rewrite the merged plan to collapse those labels.

The producer cites embedded SQLite because decision-pack section 12 and A2 section 4 name it. A council that finds a different engine in those sections should classify `OPTICS_OPTION_C_AMENDMENT_REQUIRED_READY_FOR_COUNCIL`.

A council pass of this packet leaves `O7` closed until `04-DEPENDENCY-ORDER.md` section 3 steps 2 through 5 are met in earlier forces.
