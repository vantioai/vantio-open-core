# Independent council

Audience: INTERNAL_RESTRICTED

Status: `PENDING_INDEPENDENT_COUNCIL`

Producer classification under review: `PHANTOM_WAVE1_PACKAGING_HEALTH_PLAN_READY_FOR_COUNCIL`

This file is the producer stub. The planning producer does not sit the council and does not write a verdict.

## 1. What a separate council reviews

| Item | Value |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Planning directory | `docs/planning/phantom-engine-production/` |
| Open-core base named by the producer | `5064f32f1cdfcb840dfd100e2ce5c712d046550d` |
| Private product tip named by the producer | `631e435315cd780d83d3259e111893c1d0569bc3` |
| Producer | `bc-67390466-de62-5277-ba0b-3f01b390aa8c` |
| Classification the producer claims | `PHANTOM_WAVE1_PACKAGING_HEALTH_PLAN_READY_FOR_COUNCIL` |

## 2. Seats

| Seat | Scope | Verdict |
| --- | --- | --- |
| 1 | Private-repo access and commit constraints | `UNSAT` |
| 2 | P1 package and artifact provenance | `UNSAT` |
| 3 | P2 prerequisite and compatibility | `UNSAT` |
| 4 | P24 health and coverage | `UNSAT` |
| 5 | Shared vocabulary and Workstream 4 gap | `UNSAT` |
| 6 | Public-repo confidentiality boundary | `UNSAT` |

## 3. Checks the council can re-run without a live load

- The diff is only `docs/planning/phantom-engine-production/`.
- No file path contains `PRIVATE-MANUAL` or `CUSTOMER-MANUAL`.
- `docs/operations-guide.md` body from blob `1b973342b3bf7f6aa6cdad70de49fa6e26db0077` is not pasted.
- `vocabulary_status` is `PENDING_WS4`.
- Every coverage row has `this_force` `NOT_EXECUTED`.
- The producer classification is present and no council pass token is present.

## 4. Verdict block

| Field | Value |
| --- | --- |
| Council agent | `UNSAT` |
| Reviewed tip | `UNSAT` |
| Verdict | `PENDING_INDEPENDENT_COUNCIL` |
| Blocking findings | `UNSAT` |
