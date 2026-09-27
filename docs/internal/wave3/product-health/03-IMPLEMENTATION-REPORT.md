# Implementation report

Audience: INTERNAL_RESTRICTED

Producer classification: `W3_PRODUCT_HEALTH_FAILURE_TRUTH_READY_FOR_COUNCIL`

## Added

- `internal/pe-integrated-runtime/src/product-health.cjs` — reading over the merged runtime and the shared health contract.
- `productHealth` on the runtime, and `product_health` on each snapshot.
- Shared health quotes now include `failure_classification`, `failure_classification_basis`, and `evidence_source`.
- `tests/pe-integrated-runtime/product-health.test.cjs`.
- This directory, and the same registers and status under `docs/programs/production-readiness/wave3/product-health/`.

## Honesty fields

`RUNTIME-REGISTER.json` and `INTEGRATION-REGISTER.json` for the merged runtime, and the product-health pair, record:

- `healthy_enforcing_reported_as_host_enforcement` false
- `blocked_host_reported_as_host_enforcement` false
- `enforce_stage_reported_as_host_enforcement` false
- `promoted_match_reported_as_host_enforcement` false
- `missing_evidence_collapsed_to_success` false
- `unknown_evidence_collapsed_to_success` false
- `unavailable_evidence_collapsed_to_success` false
- `optimistic_success` false
- `eligible_plane` `NONE`
- `named_eligible_plane` false
- `infra_requirement` `W3-INFRA-REQ-1`
- `execution_ceiling` `HOST_ATTACHMENT_FALSE`
- `product_health_failure_truth` `W3_PRODUCT_HEALTH_FAILURE_TRUTH_READY_FOR_COUNCIL`

The merged runtime's own producer classification stays `W3_PE_INTEGRATED_RUNTIME_READY_FOR_COUNCIL`.

## Left unchanged

- `@vantio/cli` `0.3.24`, `@vantio/agent-sdk` `0.2.4`, and Python `vantio-agent-sdk` `3.1.0`
- `pnpm-workspace.yaml`
- The twelve shared health states and `packages/shared-health-runtime/contract.json`
- `BLOCKED-INFRA.json`
- CLI, SDK, and Python package sources

## Verification

`node --test tests/pe-integrated-runtime/*.test.cjs`

The product-health tests drive the real evaluators. They check the four collapse tokens, an empty runtime, process-up with HTTP 200, disagreed health states, and refused success and attachment requests.
