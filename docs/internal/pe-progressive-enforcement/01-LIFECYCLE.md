# Lifecycle

Audience: INTERNAL_RESTRICTED

`schema_status`: `unstable-pre-1.0`. Every object below is local to `@vantio/pe-progressive-enforcement`.

## 1. Stages

| Stage | How it is entered | What a decision returns |
| --- | --- | --- |
| `DISCOVER` | `discover` with a structural signal | `OBSERVATION` |
| `OBSERVE` | `observe` from `DISCOVER` | `OBSERVATION` |
| `PROPOSE` | `propose`, or `ingest` with `propose: true`, and at least one observation | `PROPOSAL` |
| `SIMULATE` | `simulate` replays a corpus | `SHADOW` |
| `CANARY` | `canary` on a named cohort of at most 20 subjects | `CANARY` inside the cohort when the predicate matches, otherwise `SHADOW` |
| `ENFORCE` | `promote` from `CANARY` | `PROMOTED_MATCH` only inside the current rollout set |
| `REVIEW` | `review` verdict `PASS` | Same match rule as `ENFORCE` |
| `REVOKE_OR_ROLLBACK` | `revokeOrRollback`, or `review` verdict `FAIL` | `ROLLED_BACK` |
| `RETIRE` | `retire` from `REVOKE_OR_ROLLBACK` | `RETIRED` |
| `VERIFY_REMOVAL` | `verifyRemoval` after the removal probe is clean | `REMOVED` |

Skipping a stage returns `WRONG_STAGE`. The emergency path may go from `ENFORCE` to `REVOKE_OR_ROLLBACK` without `REVIEW`. The full path enters `REVIEW` before rollback.

## 2. Evidence

| Kind | Recorded by |
| --- | --- |
| `DISCOVER`, `OBSERVATION` | Discovery and each observation |
| `PROPOSAL` | The proposal, including effect, predicate, and observation count |
| `SIMULATION`, `IMPACT` | Historical replay, shadow decisions, replay digest, per-rule impact |
| `CANARY` | Cohort id, subjects, canary decisions, canary impact |
| `PROMOTION` | Distinct actor and approver, replay digest, shadow count, both impacts, known-good snapshot id, rollout step `COHORT` |
| `ROLLOUT` | One-step widening, citing the previous promotion or rollout evidence |
| `REVIEW` | Pass verdict by an actor who is neither the promoter nor the approver |
| `ROLLBACK` | Known-good snapshot id and the restored stage (`CANARY`) |
| `FREEZE`, `THAW` | Emergency freeze. Thaw does not change any rule stage |
| `EXCEPTION`, `EXCEPTION_EXPIRY` | A future `not_after`. Expiry sets `promotions` to 0 |
| `RETIREMENT`, `REMOVAL` | Retirement, then a probe that the rule is not armed |

Prompt, completion, message, payload, and credential keys are not stored. A replay or canary corpus that carries those keys is `BAD_CORPUS` and does not move the stage.

## 3. Rollout

Steps: `NONE`, `COHORT`, `LIMITED`, `BROADER`.

`promote` arms `COHORT` only. `LIMITED` holds at most 50 subjects and must strictly contain the cohort. `BROADER` holds at most 200 and must strictly contain the limited set. There is no match-all step. Observation count does not select the next step.

## 4. Freeze, exception, rollback

`freeze` refuses `promote` and `advanceRollout`. `decide` returns `FROZEN` for an armed rule. `revokeOrRollback` still runs and restores the known-good snapshot taken at promotion, which is the pre-enforce `CANARY` posture. The live stage after rollback is `REVOKE_OR_ROLLBACK`, and the rule leaves the active set.

An exception is refused before `ENFORCE`. While it is active and unexpired, a matching subject in rollout returns `EXCEPTION`. When `not_after` is reached, the subject can match again only if the rule was already promoted. Expiry does not create that promotion.

## 5. Removal

`verifyRemoval` refuses with `STILL_ARMED` when the rule is in the active set, the rollout step is not `NONE`, or a decision would be `PROMOTED_MATCH` or `CANARY`. A clean probe moves the stage to `VERIFY_REMOVAL`.
