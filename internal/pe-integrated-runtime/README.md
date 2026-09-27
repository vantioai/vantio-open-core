# Phantom Engine integrated runtime

INTERNAL_RESTRICTED. Source composition only.

`CONTRACT_ONLY` / `EVALUATE_ONLY` / `HOST_ATTACHMENT_FALSE`

This package calls the merged Wave 2 evaluators and keeps each result on an explicit plane: observation, decision, application enforcement, host enforcement, containment, revocation, evidence, and independent verification. It does not attach a host, load eBPF, or mark an unattached mechanism as active protection.

`productHealth` reads that runtime and emits a product health and failure-truth record. The record uses the twelve shared health states. `HEALTHY_ENFORCING` stays on the observation plane. `BLOCKED_HOST`, `ENFORCE`, and `PROMOTED_MATCH` stay on the decision plane while host attachment is false. `EVIDENCE_UNAVAILABLE` and `ENFORCEMENT_UNKNOWN` stay visible. The execution ceiling is `HOST_ATTACHMENT_FALSE`.

Producer classification for the integrated runtime: `W3_PE_INTEGRATED_RUNTIME_READY_FOR_COUNCIL`. Producer classification for the product health reading: `W3_PRODUCT_HEALTH_FAILURE_TRUTH_READY_FOR_COUNCIL`. Each classification is ready for a separate council. Council status for both remains `PENDING_INDEPENDENT_COUNCIL`.
