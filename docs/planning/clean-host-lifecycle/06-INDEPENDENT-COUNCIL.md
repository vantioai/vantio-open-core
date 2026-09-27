# Independent council

Audience: INTERNAL_RESTRICTED

Status: `PENDING_INDEPENDENT_COUNCIL`

Producer classification under review: `CLEAN_HOST_LAB_DESIGN_READY_FOR_COUNCIL`

That producer classification is the handoff. It is not a council verdict. This file does not record a pass. The planning producer does not sit this council and does not fill the verdicts below.

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

Producer: `bc-696d1176-5194-564e-a77c-9001563d5885`

Producer URL: https://cursor.com/agents/bc-696d1176-5194-564e-a77c-9001563d5885

## Questions for the council

The council reads the packet at the reviewed tip and answers each item. The producer leaves every verdict `PENDING`.

| # | Question | Verdict |
| --- | --- | --- |
| 1 | Is the environment class `CLEAN_HOST_INTERNAL_PROOF`, with evidence tier `UNSET`? | `PENDING` |
| 2 | Does the design exclude Phantom-Box (`VANTIO_SOAK_LOCAL`, ingest port `5001`, API key) without treating loopback `127.0.0.1` as Phantom-Box? | `PENDING` |
| 3 | Do the scripts refuse stranger-host, and is stranger-host left `NOT_RUN`? | `PENDING` |
| 4 | Does isolation redirect `HOME` and leave `VANTIO_HOME` unset, matching the CLI reader behavior? | `PENDING` |
| 5 | Does reset preserve `retention/` and refuse to destroy a `CAPTURED` cycle unless `--abandon` is set? | `PENDING` |
| 6 | Does retention copy only the accepted run file, exclude `config.json` and `telemetry-id`, and keep `product_seal` false? | `PENDING` |
| 7 | Do stop conditions fail closed without assigning an evidence tier? | `PENDING` |
| 8 | Does the packet avoid product-code edits, traceability-matrix edits, and external claims? | `PENDING` |

## Effect of a later pass

A pass on this design accepts the documents and the script contracts. It does not assign `UNIT_PROVED`, `INTEGRATION_PROVED`, `STRANGER_HOST_PROVED`, `PROVED_EXTERNAL`, or `CUSTOMER_VALIDATED`. It does not authorize a stranger-host run. It does not open Phantom-Box.
