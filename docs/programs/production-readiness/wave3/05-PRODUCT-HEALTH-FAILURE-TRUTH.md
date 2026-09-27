# Wave 3 Track 6 — product health and failure truth

Audience: INTERNAL_RESTRICTED

Producer classification: `W3_PRODUCT_HEALTH_FAILURE_TRUTH_READY_FOR_COUNCIL`

That classification means this reading is ready for a separate council. Council status is `PENDING_INDEPENDENT_COUNCIL`. `council_verdict` is null.

## Locked input

| Item | Value |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Starting commit | `0cd36cf1d01c4db83a0a6999db0a322441f61c98` |
| Branch | `cursor/wave3-product-health-failure-truth-2a5b` |
| Producer | `bc-e3b48f10-95e0-51a9-be59-03f664ad2a5b` |
| Module | `internal/pe-integrated-runtime` |
| Eligible plane | `NONE` |
| Infrastructure requirement | `W3-INFRA-REQ-1` |
| Execution ceiling | `HOST_ATTACHMENT_FALSE` |

The reading composes the merged Phantom Engine runtime with the Wave 2 shared health states. It adds no health state. `HEALTHY_ENFORCING` stays on `OBSERVATION`. `BLOCKED_HOST`, `ENFORCE`, and `PROMOTED_MATCH` stay on `DECISION` while host attachment is false. Missing, unavailable, and unknown evidence stay visible.

## Registers

The same documents live here and under `docs/internal/wave3/product-health/`:

- `product-health/RUNTIME-REGISTER.json`
- `product-health/INTEGRATION-REGISTER.json`
- `product-health/STATUS.json`

The merged runtime registers at `docs/programs/production-readiness/wave3/RUNTIME-REGISTER.json` and `INTEGRATION-REGISTER.json` carry the same honesty fields. Their producer classification remains `W3_PE_INTEGRATED_RUNTIME_READY_FOR_COUNCIL`.

Mechanism notes are in `docs/internal/wave3/product-health/`.
