# Comparator rules

Audience: INTERNAL_RESTRICTED

The comparator scores documented behavior. Marketing lines in `docs/PRODUCT_LINEUP.md` are copied into `lineup_ignored` and then left out of stage status.

## Products

| Id | Product | Where this pack may read |
| --- | --- | --- |
| `optics` | Vantio Optics | This repository, including the architecture pack whose fresh council classification is `OPTICS_FOUNDATION_ARCHITECTURE_COUNCIL_PASSED` |
| `phantom_engine` | Vantio Phantom Engine | Open-core lineup and planning summaries. Private manual and product-spec bodies stay in the private repository. |
| `enterprise` | Vantio Enterprise | Open-core lineup and `docs/planning/enterprise-governance/`. That packet's council is `PENDING_INDEPENDENT_COUNCIL`. |

`docs/planning/enterprise-governance/00-PROGRAM-BOUNDARY.md` records Enterprise status in the cited product-spec table as internal dogfood. This pack does not reclassify that status as shipped.

## Statement classes

| Class | Meaning for stage 1 |
| --- | --- |
| `ARCHITECTURE_DESIGN_TARGET` | The accepted Optics architecture states owner, behavior, non-goals, and advance evidence. Eligible for stage 1. |
| `DOCUMENTED_CURRENT_BEHAVIOR` | A manual describes what the current package does. Eligible for stage 1 only when the design checklist is also met. In this population the install and uninstall pages stay at `NONE`. |
| `DOCUMENTED_NON_CLAIM` | The product boundary states the dimension belongs elsewhere. Stage status stays `NONE`. |
| `NOT_DOCUMENTED` | The source set does not state the dimension for that product. Stage status stays `NONE`. |
| `LINEUP_ONLY` | The lineup states the cell. Stage status stays `NONE`. |
| `PLAN_PENDING_COUNCIL` | A planning packet describes the dimension and its own council is still pending. Stage status stays `NONE`. |

## Population rule for stage 1

An Optics cell is `BEST_IN_CLASS_DESIGN_TARGET` only when the design sits in a gate the fresh architecture council accepted and the checklist in `01-CLAIM-STAGE-LADDER.md` is met. Phantom Engine and Enterprise cells stay at `NONE` because the open-core plans that describe them are still `PENDING_INDEPENDENT_COUNCIL`, and because lineup text is ignored.

Repository evidence of a privileged WSL2 host or a local `kind` cluster, as labeled in `docs/planning/phantom-engine-production/COVERAGE-MATRIX.json`, stays `OBSERVED_FROM_REPOSITORY_EVIDENCE` with `this_force` `NOT_EXECUTED`. This force did not re-execute those rows. They do not become `CLEAN_HOST_PROVED_CANDIDATE` or `PRODUCTION_GRADE_INTERNAL_CANDIDATE`.

## Excluded practices

`excluded_practices` in the matrix names inputs that must not be relabeled as a dimension:

- Privacy-canary fixtures are not the canary dimension. Canary here is a subset rollout of a policy or release.
- `producer_sequence` is an event order, not a sequential limit.
- `docs/specs/WRAP_UNDICI_WS_FRAMES_2026-08-15.md` is a historical spec. The current boundary says Optics does not block, redact, or apply spend caps.
- The roadmap's example per-call overhead figure is `NOT_ADOPTED`.

The generated score is `03-SCORE.md`.
