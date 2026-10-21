# Independent council

Audience: PUBLIC_PLANNING_PLACEHOLDER

Status: `PENDING_INDEPENDENT_COUNCIL`

Producer classification under review: `PHANTOM_WAVE1_PACKAGING_HEALTH_PLAN_READY_FOR_COUNCIL`

This file is a public planning placeholder. The planning producer does not sit the council and does not write a verdict. Producer agent identifiers and private product tip SHAs are omitted from the public tip.

## 1. What a separate council reviews

| Item | Value |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Planning directory | `docs/planning/phantom-engine-production/` |
| Private product tip | `OMITTED_FROM_PUBLIC_TIP` |
| Classification the producer claims | `PHANTOM_WAVE1_PACKAGING_HEALTH_PLAN_READY_FOR_COUNCIL` |

## 2. Seats (pending)

Six seats remain `UNSAT` (private-repo access constraints, P1 provenance, P2 compatibility, P24 health/coverage, shared vocabulary / WS4 gap, public-repo confidentiality boundary) until an independent council records a verdict.

## 3. Checks the council can re-run without a live load

- The diff is only `docs/planning/phantom-engine-production/`.
- No file path contains `PRIVATE-MANUAL` or `CUSTOMER-MANUAL`.
- `vocabulary_status` remains `PENDING_WS4` (or successor token recorded in PLANNING-MANIFEST).
- Every coverage row has `this_force` `NOT_EXECUTED`.
- The producer classification is present and no council pass token is present.

## 4. Verdict block

| Field | Value |
| --- | --- |
| Council agent | unset |
| Reviewed tip | unset |
| Verdict | `PENDING_INDEPENDENT_COUNCIL` |
| Blocking findings | unset |
