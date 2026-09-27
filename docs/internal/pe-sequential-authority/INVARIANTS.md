# Invariants

INTERNAL_CANDIDATE | EVALUATE_ONLY | NOT_HOST_ENFORCEMENT | NOT_SHIPPED | NO_KERNEL | NO_ENROLL | NO_CREDENTIAL_MATERIAL | NO_STABLE_SCHEMA

Audience: INTERNAL_RESTRICTED

These nine names are the closed invariant list. A passing unit test here is a property of this candidate. It does not move a reference-monitor row to Present.

| Invariant | Candidate rule |
| --- | --- |
| `SPLIT_CANNOT_BYPASS_AGGREGATE` | A cumulative ceiling denies the step that would cross it. Separate runs, sequences, processes, and later windows keep the principal `resource_budget`. Parent and child share the lineage counter |
| `CONSENSUS_IS_NOT_AUTHORIZATION` | Authority source `consensus` denies. A consensus list on an ungranted action denies. Agent count does not change units. A delegation cause of `consensus` denies |
| `PROCESS_COUNT_IS_NOT_PRINCIPAL` | Process id is not a budget key and cannot rename the principal. Cause `process_spawn` does not create a grant |
| `CHILD_CANNOT_EXCEED_INHERITANCE` | Actions, destinations, credentials, nodes, workloads, domains, pairs, ceilings, step cap, and window of a child stay inside the parent. A child cannot revoke an ancestor |
| `DELEGATION_CANNOT_CREATE_RESERVED_RIGHTS` | Freeze, revoke root, recover, export, hash, rollback, uninstall, leave, witness removal, and root-set change are reserved. Security and recovery domains are reserved on a delegate. A child exercise of a reserved action denies |
| `REVOCATION_REACHES_DESCENDANTS` | Revoking an envelope marks every descendant in the catalog. A descendant record already marked revoked still denies |
| `STALE_DESCENDANT_DOES_NOT_SURVIVE_PARENT_REVOCATION` | An `ACTIVE` copy denies when the ledger or the catalog shows the envelope or an ancestor revoked. Parent generation drift denies |
| `NO_REPLAY_ACROSS_ACTIONS` | A receipt bound to one action denies for a different action, a different tuple, a second use of the same tuple, and an unknown id |
| `SEQUENCE_DOES_NOT_COMPOSE_UNAUTHORIZED_AUTHORITY` | The composition table, an unbound credential/destination pair, a ceiling raise, and a second effect on one step deny. Splitting those steps across sequence ids does not clear family history |

Additional fail-closed rules, outside the nine:

| Rule | Meaning |
| --- | --- |
| `INPUT_REJECTED` | Missing fields, unknown keys, bad ids, and a redelegation value other than `forbidden` |
| `LIMIT` | Membership, per-step action ceiling, time bounds, and sequence step count |
| `REDELEGATION_FORBIDDEN` | A delegate cannot issue a further grant. Lineage longer than one hop denies |

Reserved rights on a root that lists them stay with that root. Delegation does not copy them.
