# Independent council

Audience: INTERNAL_RESTRICTED

Status: `PENDING_INDEPENDENT_COUNCIL`

Producer classification under review: `CLEAN_HOST_BLOCKED_INFRA_READY_FOR_COUNCIL`

That producer classification is the handoff. It is not a council verdict. This file does not record a pass. The execution producer does not sit this council and does not fill the verdicts below.

## Identity to be completed by the council

| Item | Value |
| --- | --- |
| Council agent | `PENDING` |
| Council URL | `PENDING` |
| Model | `PENDING` |
| Reviewed tip | `PENDING` |
| Reviewed at (UTC) | `PENDING` |
| Verdict | `UNSET` |
| Force classification | `PENDING` |

Producer: `bc-36ae62af-00aa-561d-ba4e-e99dd8ea62cc`

Producer URL: https://cursor.com/agents/bc-36ae62af-00aa-561d-ba4e-e99dd8ea62cc

## Questions for the council

The council reads the packet at the reviewed tip and answers each item. The producer leaves every verdict `PENDING`.

| # | Question | Verdict |
| --- | --- | --- |
| 1 | Is the producer classification `CLEAN_HOST_BLOCKED_INFRA_READY_FOR_COUNCIL`, with environment class `CLEAN_HOST_INTERNAL_PROOF` and evidence tier `UNSET`? | `PENDING` |
| 2 | Does every required sequence row stay `BLOCKED_INFRA`, with the missing prerequisite named on that row? | `PENDING` |
| 3 | Does the `check-guards.sh` record stay a process result, with `evidence_tier=UNSET`, `stranger_host=NOT_RUN`, and `phantom_box=EXCLUDED`? | `PENDING` |
| 4 | Does the packet keep Phantom-Box excluded, with no use of port `5001` or `VANTIO_SOAK_LOCAL` as a baseline? | `PENDING` |
| 5 | Does the packet avoid assigning `PROVED_EXTERNAL`, `STRANGER_HOST_PROVED`, `UNIT_PROVED`, `INTEGRATION_PROVED`, and `CUSTOMER_VALIDATED`? | `PENDING` |
| 6 | Does the packet avoid product-code edits, CLI `0.3.24` changes, a kernel load, a reboot, and a traceability-matrix edit? | `PENDING` |

## Effect of a later pass

A pass accepts or rejects this blocked-infra record. It does not install Phantom Engine, does not create a clean host, and does not assign an evidence tier. A later force that runs the sequence needs the prerequisites in `04-MISSING-PREREQUISITES.md` and a separate charter.
