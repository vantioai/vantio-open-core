# Architecture

Audience: INTERNAL_RESTRICTED

The runtime is a dispatcher plus a projector. Each `integrate` call clones caller-supplied host and ingress objects when those objects are plain data, calls one existing evaluator, and builds a contribution.

A contribution carries:

- `capability` and `op`
- eight `planes`
- a `quote` of the child fields a reader needs
- the child result, so the underlying disposition stays visible
- locks: `active_protection` false, `host_attachment` false, `ebpf_loaded` false, `kernel_executed` false, `applied_to_host` false, `independent_verification_status` `NOT_INDEPENDENTLY_VERIFIED`

`sealChild` rejects a child or a plane that sets a boolean enforcement flag, a packet effect other than `NOT_APPLIED`, an enforcement label other than `EVALUATE_ONLY`, or an execution label outside `CONTRACT_ONLY`, `EVALUATE_ONLY`, `HOST_ATTACHMENT_FALSE`, and `NOT_PERFORMED`. A rejected child becomes `HONESTY_FAULT`. The runtime does not rewrite that child into a success.

Request keys such as `load_ebpf`, `attach_host`, and `host_attachment: true` return `ATTACHMENT_REFUSED` before a child evaluator runs.

`integrateAll` runs a list of those calls and stops after `ATTACHMENT_REFUSED` or `HONESTY_FAULT`. `snapshot` aggregates planes. Host and application enforcement aggregate to `NOT_APPLIED` or `GAP`. They do not aggregate to an applied state. A snapshot whose only host rows are `HOST_ATTACHMENT_FALSE` keeps that execution label. `CONTRACT_ONLY` appears on the aggregate only when a contribution actually carried that execution label.

Policy versions are in-memory records. Origins in this force are `recorded`, `ingress_decision`, `ingress_rollback`, and `host_contract_citation`. Each record sets `applied_to_host` false and `kernel_maps_changed` false.

Uninstall stores `RECORDED_NOT_PERFORMED`. `performed: true` is refused, and no path is deleted.

The progressive engine inside a runtime is private to that runtime. Its active rule ids are reported as `in_process_promoted_rule_ids` with `in_process_promoted_rules_are_host_enforcement` false.
