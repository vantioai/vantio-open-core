# Gates

Audience: INTERNAL_RESTRICTED

These gates are what the package enforces. They are not a claim that a host enforces them.

| Code | When |
| --- | --- |
| `AUTO_REJECTED` | Actor is `auto`, `system`, `observation`, `ingest`, `anonymous`, `policy`, or `automatic`. Also when `promote`, `simulate`, `canary`, `advanceRollout`, or `propose` is called with `auto`, `automatic`, `auto_promote`, or `enforce` set true. `advanceRollout` also refuses `from_observations: true` |
| `SAME_ACTOR` | Promoter and approver are the same person. Reviewer is the promoter or the approver |
| `WRONG_STAGE` | The operation is not legal for the current stage |
| `MISSING_OBSERVATION` | `propose` runs with an empty observation list |
| `WIDE_PREDICATE` | The predicate does not constrain the declared effect |
| `COHORT_UNBOUNDED` | Cohort id is missing, a subject is `*`, the list is empty, or it exceeds 20 |
| `ROLLOUT_NOT_FIRST_STEP` | The first promotion asks for anything other than `COHORT` |
| `ROLLOUT_SKIP` | Rollout advance is not the immediate next step |
| `ROLLOUT_NOT_SUPERSET` | The next subject list does not strictly contain the previous list, or it exceeds the step cap |
| `FROZEN` | Promotion or rollout advance runs while the engine freeze is set |
| `MISSING_EVIDENCE` | Simulation, canary, promotion, known-good snapshot, or the prior rollout evidence id is absent |
| `EXCEPTION_BEFORE_PROMOTION` | An exception is granted before `ENFORCE` or `REVIEW` |
| `EXCEPTION_NOT_FUTURE` | `not_after` is not an integer strictly after the engine clock |
| `STILL_ARMED` | Removal verification still sees an armed rule |
| `BAD_CORPUS` | Replay input is empty, too large, or contains a dropped or control key |

`observe` and `ingest` do not use `AUTO_REJECTED` for an `enforce` flag on the observation. They record the structural event, list the flag on `control_attempt`, and leave the stage unchanged except for the explicit `DISCOVER` to `OBSERVE` move and an explicit `propose: true`.

Setting `rule.stage` to `ENFORCE` without a promotion record, a known-good snapshot, and membership in the active set makes `decide` return `REFUSED`.
