# Sequential and aggregate authority — design

INTERNAL_CANDIDATE | EVALUATE_ONLY | NOT_HOST_ENFORCEMENT | NOT_SHIPPED | NO_KERNEL | NO_ENROLL | NO_CREDENTIAL_MATERIAL | NO_STABLE_SCHEMA

Audience: INTERNAL_RESTRICTED

`schema_status` is `unstable-pre-1.0`. Names in this file are candidate names. They are not a wire schema and not a database.

## Objects

An envelope names one principal, one tenant, one fleet, the workload ids and node ids it covers, the ordinary actions, destinations, credential ids, and explicit credential/destination pairs. Time is `not_before` inclusive and `not_after` exclusive. Every ceiling in `LIMIT_AXES` is present. `redelegation` is `forbidden`.

A root has `parent_envelope_id` null, an empty lineage, and may list reserved rights in `reserved_rights_held`. Reserved rights stay out of `actions`. A child has lineage `[root]` and an empty reserved-rights list.

A step names the action, the authority source, and the correlation ids: sequence, run, and process. Process id is echoed and is never part of a budget key. Resource units are a non-negative integer. Credential ids are opaque. The evaluator stores no secret.

The ledger holds consumption, single-use receipts, revocation marks, family composition history, and per-sequence step counts. `evaluate` copies it and advances the copy only on `ALLOW`.

## Decision order

1. Reject malformed input.
2. Authority source `consensus` or `process_count` denies.
3. A presented receipt denies. A receipt is evidence of a past decision.
4. Revocation marks and revoked catalog records deny. The catalog state of the subject wins over a caller-held `ACTIVE` copy, including when the ledger is empty. An `ACTIVE` copy after a revocation mark or a revoked catalog entry is stale. Parent generation drift denies whenever the catalog parent generation differs from the generation the child was issued against, including when that parent is `EXPIRED` or otherwise non-`ACTIVE`.
5. Child fields must be inside the parent. Lineage longer than one hop is redelegation and denies.
6. Reserved actions run only for a root that lists them. Any other use denies.
7. Time window, then tenant, fleet, workload, node, destination, and credential membership.
8. Composition rules, then ceilings. A step that crosses a cumulative ceiling denies and does not consume.

`proposeDelegation` builds a child from a root only. Cause `grant` is the only cause that can succeed. `process_spawn` and `consensus` deny. The child window, ceilings, and lists are subsets. `revoke` marks the named envelope and every catalog envelope whose lineage contains it, and bumps generation. `evaluate` of `revoke_grant` or `revoke_root` returns `revoke_transition` and does not write that mark.

## Budget keys

Cumulative ceilings share keys so a renamed run, sequence, process, or window cannot clear the principal and family totals:

| Axis | Key |
| --- | --- |
| action | Per-step maximum. It does not accumulate |
| sequence | principal + sequence id |
| run | principal + run id |
| workload | tenant + workload id |
| lineage | lineage root, shared by parent and child |
| credential | credential id |
| destination | destination id |
| tenant | tenant id |
| node | node id |
| fleet | fleet id |
| time_window | principal + window bounds |
| resource_budget | principal id |

The effective ceiling is the minimum along the lineage. Composition history is keyed by the lineage root, so a new sequence id does not erase it.

## Composition table

These pairs are unauthorized when the derived action is absent from the envelope. The history is the family history, including a parent step followed by a child step.

| Prior action | Later action | Derived authority |
| --- | --- | --- |
| `observe` | `label_enforced` | `enforce` |
| `propose` | `record_approval` | `activate` |
| `exercise` | `name_delegate` | `delegate` |

`raises_ceiling` denies. One step that names a second `composed_effect` denies. A credential and a destination that are each inside the envelope still require an explicit pair in `bound_uses`. Earlier separate steps do not create that pair.

## Result flags

Every result sets `host_attachment` false, `enforcement` `EVALUATE_ONLY`, and `doctrine_present` false. `consensus_ignored` is true when a consensus list was present and the authority source stayed `envelope`.
