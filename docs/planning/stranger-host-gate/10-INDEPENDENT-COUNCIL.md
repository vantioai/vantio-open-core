# Independent council

Audience: INTERNAL_RESTRICTED

Status: `PENDING_INDEPENDENT_COUNCIL`

Producer classification under review: `STRANGER_HOST_READINESS_UPDATED_READY_FOR_COUNCIL`

This file is the producer stub. The readiness producer does not sit the council and does not write a verdict.

## 1. What a separate council reviews

| Item | Value |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Packet | `docs/planning/stranger-host-gate/` |
| Currency main named by the producer | `89f95099d0dce463307eb75d78e7fcf2ef99feb2` |
| Prep pin | `5064f32f1cdfcb840dfd100e2ce5c712d046550d` |
| Producer | `bc-ad6e7ae1-4de4-5416-bc9d-a6971c7717f4` |
| Prep classification | `STRANGER_HOST_PACKET_READY_AWAITING_EXECUTION_AUTH` |
| Execution | `NOT_AUTHORIZED` |

## 2. Seats

| Seat | Scope | Verdict |
| --- | --- | --- |
| 1 | Currency: `ci.yml` unchanged, added tests outside `later_commands` | `UNSAT` |
| 2 | Placeholder families ingress, egress, host-authority, sequential-authority, health, progressive-enforcement stay `NOT_EXECUTED` | `UNSAT` |
| 3 | Named host and operator checklist unfilled; in-place completion forbidden | `UNSAT` |
| 4 | Refuse scripts exit 2; readiness `--execute` exits 2 | `UNSAT` |
| 5 | Evidence tiers remain empty | `UNSAT` |
| 6 | Customer host forbidden, credentials none, no private engine bodies copied | `UNSAT` |

## 3. Checks the council can re-run

From the repository root:

```bash
node docs/planning/stranger-host-gate/scripts/verify-packet-prep.mjs
node docs/planning/stranger-host-gate/scripts/verify-readiness-update.mjs
node --test docs/planning/stranger-host-gate/scripts/readiness.test.mjs
```

Prep stdout is `STRANGER_HOST_PACKET_READY_AWAITING_EXECUTION_AUTH`. Readiness stdout is `STRANGER_HOST_READINESS_UPDATED_READY_FOR_COUNCIL`. The test file is the direct and adversarial suite. These commands are packet reads. They are outside `.github/workflows/ci.yml`.

## 4. Verdict line

Council verdict: unset. Seat marks above are `UNSAT` because this producer leaves them for the council.
