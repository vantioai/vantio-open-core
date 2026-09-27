# Known limitations

Audience: INTERNAL_RESTRICTED

- Host attachment is `NOT_PERFORMED`. `PROMOTED_MATCH` is an in-process record. It is not a packet drop, a byte rewrite, or a live interceptor result.
- This force did not load eBPF, run a kernel verifier, enroll a cluster, or write a ledger. It does not promote repository evidence about WSL2 or local kind into a new execution claim.
- Private Phantom Engine blobs were not copied into this tree.
- CLI `0.3.24`, Node SDK `0.2.4`, and Python SDK `3.1.0` are unchanged. This package is not on their import path.
- Enterprise E1–E3 approval classes remain the planned model in `docs/planning/enterprise-governance/`. This package's distinct-actor rule is not that model and is not a customer quorum.
- The engine clock is injected by the caller. There is no distributed clock and no host heartbeat.
- Freeze is process-local. It is not the customer one-shot freeze that enterprise planning marks unsatisfied.
- Rollout stops at a bounded `BROADER` list of 200 subjects. A later force would have to define anything past that, and this package has no such step.
- The engine object is mutable in-process. Forging `promotion`, `known_good`, the active set, and the rollout step together is outside the API. A stage-only edit does not arm a match.
- `schema_status` is `unstable-pre-1.0`. Decision classes are not Layer A status tokens and are not in the Workstream 4 catalog.
- Council status is `PENDING_INDEPENDENT_COUNCIL`.
