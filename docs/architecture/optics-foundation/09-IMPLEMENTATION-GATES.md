# A6 — Implementation gates

Classification: `OPTICS_FOUNDATION_A6_READY_FOR_COUNCIL`

Audience: INTERNAL_RESTRICTED

No product implementation is authorized before Gate 8. Gate 8 is not open. A7 council is not this producer. A8 is not started.

Passing a gate in prose inside this pack is not `UNIT_PROVED`, `INTEGRATION_PROVED`, `STRANGER_HOST_PROVED`, `PROVED_EXTERNAL`, or `CUSTOMER_VALIDATED`. Producer readiness is not proof.

## Gate table

| Gate | Name | What must be true before the next gate | State |
| --- | --- | --- | --- |
| 1 | Inventory | A0 source inventory exists, with conflicts left intact | Written in `01-CURRENT-STATE-INVENTORY.md`. Council has not accepted it |
| 2 | Evidence and privacy | A1 classes, origins, allowlist, prohibited data, and release-blocking invariants are specified | Written in `02-EVIDENCE-AND-PRIVACY-CONTRACT.md`. Not implemented |
| 3 | Store and proof | One store recommendation, rejected options, and a portable-proof boundary that avoids attestation language | Written in `03-OPERATIONAL-STORE-AND-PORTABLE-PROOF.md`. Founder ratification of option C is still open. No database exists |
| 4 | Schema and migration | Unstable pre-1.0 identity, no silent empty store, Node/Python target, legacy JSON adapter | Written in `04-SCHEMA-MIGRATION-AND-COMPATIBILITY.md`. No migrator exists |
| 5 | Correlation and query | Identity hierarchy, deduplication, destination versus provider, bounded query, cardinality | Written in `05-CORRELATION-AND-QUERY-CONTRACT.md`. No query engine exists |
| 6 | Reliability | Product-health separation, fail-open, lifecycle, budgets at `NOT_SET` | Written in `06-SELF-OBSERVABILITY-AND-RELIABILITY.md` |
| 7 | Threat model | Cases T1–T15 with required fields and unset residual risk | Written in `07-THREAT-MODEL.md`. Council has not accepted residual risk |
| 8 | Implementation Force | A separate Founder implementation Force, after an independent council report that is not `PENDING_SEPARATE_COUNCIL` | **Not open. Not started** |

## Rules

- Gates 1–7 in this pack are documents. They are not execution of the controls.
- Gate 8 is the only gate that could authorize product code, and only a separate Founder implementation Force can open it. This producer cannot open it.
- A council request for revision reopens the affected gate and sets the producer classification to `OPTICS_FOUNDATION_ARCHITECTURE_NEEDS_REVISION`. That has not happened inside this file.
- CLI 0.3.24 stays frozen through every gate. Python 3.1.0 is not sealed by any gate in this pack.
- No gate authorizes SQLite creation, a migration, a tag, a publish, a UI, a daemon, OTLP, or alerting.
- Numeric budgets stay `NOT_SET` through Gate 8 unless a Founder sets them in a later Force. This pack does not set them.

## Evidence a future Gate 8 Force would still need

Specified here so they are not confused with current results:

| Check | Tier required before an external claim | Tier now |
| --- | --- | --- |
| Allowlist unit fixtures | `UNIT_PROVED` is not enough for a claim | Unset |
| Node and Python writing one store | `INTEGRATION_PROVED` | Unset |
| Same checks on a host that is not the producer’s | `STRANGER_HOST_PROVED` | Unset |
| Independent verifier | `PROVED_EXTERNAL` | Unset |
| Customer workload and window | `CUSTOMER_VALIDATED` | Unset |

Internal tests that already exist for the current CLI and Python SDK are inventory findings. They are not retiered by this gate document.

## Stop

A8 is not started. No implementation task is filed.
