# Independent council slot

Audience: INTERNAL_RESTRICTED

Status: `PENDING_INDEPENDENT_COUNCIL`

Verdict: null

Self-certified council pass: false

Producer classification under review: `SHARED_HEALTH_RUNTIME_READY_FOR_COUNCIL`

This file is the producer's slot. It is not a council verdict. A later agent fills the result. This force does not set `COUNCIL_PASSED`.

## What the council is asked to review

- The twelve states and the evidence fields in `packages/shared-health-runtime/contract.json`.
- Refusal of healthy tokens from process up, HTTP 200, loader liveness, Optics display, and verifier `PASS`.
- `audit.green` remaining false, including when the state token is `HEALTHY_ENFORCING` or `HEALTHY_OBSERVING`.
- No live Phantom Engine enforcement change.
- The bound catalog commit `c1de02538f66df94d58aef58bf0ec8459ae797ad` left byte-stable.
- Direct tests in `tests/shared-health-runtime/produce.test.cjs` and `tests/shared-health-runtime/consume.test.cjs`.
- Adversarial tests in `tests/shared-health-runtime/adversarial.test.cjs`.

## Checklist

| Item | Producer result |
| --- | --- |
| Classification claimed | `SHARED_HEALTH_RUNTIME_READY_FOR_COUNCIL` |
| Council verdict | `PENDING_INDEPENDENT_COUNCIL` |
| Live enforcement changed | false |
| Optimistic green emitted | false |
| Merge authorized by this file | false |
