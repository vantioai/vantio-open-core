# Independent council — Wave 3 Track 8 performance qualification

Audience: INTERNAL_RESTRICTED

Council status: `PENDING_INDEPENDENT_COUNCIL`

Producer classification under review: `W3_PERFORMANCE_QUALIFICATION_READY_FOR_COUNCIL`

This producer does not mark a row `SAT` or `UNSAT`. A pass or a rejection belongs to a later reader who is not this agent.

## 1. Questions

| # | Question | Status |
| --- | --- | --- |
| 1 | Is the producer classification `W3_PERFORMANCE_QUALIFICATION_READY_FOR_COUNCIL`, with council status `PENDING_INDEPENDENT_COUNCIL` and a null verdict? | `PENDING` |
| 2 | Do the register metric ids match `PERFORMANCE-SCAFFOLD.json` in that order, while the scaffold itself stays `NOT_MEASURED`? | `PENDING` |
| 3 | Does every `MEASURED` row have an instrument, a workload, UTC and ET start times, a sample count, and a result value recomputed from the stored samples? | `PENDING` |
| 4 | Does every other scaffold metric stay `NOT_MEASURED`, with a null result and a reason, and with no numeric placeholder? | `PENDING` |
| 5 | Does the packet keep host attachment false, the selected plane `NONE`, and `W3-INFRA-REQ-1` unprovisioned? | `PENDING` |
| 6 | Does the packet keep production SLOs, claim-stage satisfaction, `PROVED_EXTERNAL`, and customer proof closed? | `PENDING` |
| 7 | Are `@vantio/cli` `0.3.24`, `@vantio/agent-sdk` `0.2.4`, and `vantio-agent-sdk` `3.1.0` unmodified? | `PENDING` |
| 8 | Do the program and internal `PERFORMANCE-REGISTER.json` copies match byte for byte? | `PENDING` |

## 2. What a verdict means

A pass accepts or rejects this qualification record. It does not attach a host. It does not provision `W3-INFRA-REQ-1`. It does not publish a number as a customer SLO. It does not move a Wave 2 claim stage.
