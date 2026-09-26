# A6 — Implementation gates

Classification: `OPTICS_FOUNDATION_ARCHITECTURE_REVISION_READY_FOR_RECOUNCIL`

This classification is the producer revision state. It is not a council pass. The first council verdict remains `NEEDS_REVISION` in `10-INDEPENDENT-COUNCIL-REPORT.md`.

Audience: INTERNAL_RESTRICTED

No product implementation is authorized before Gate 8. Gate 8 is not open. A7 council is not this producer. A8 is not started.

Passing a gate in prose inside this pack is not `UNIT_PROVED`, `INTEGRATION_PROVED`, `STRANGER_HOST_PROVED`, `PROVED_EXTERNAL`, or `CUSTOMER_VALIDATED`. Producer readiness is not proof.

## Gate table

| Gate | Name | What must be true before the next gate | State |
| --- | --- | --- | --- |
| 1 | Inventory | A0 source inventory exists, with conflicts left intact | Written in `01-CURRENT-STATE-INVENTORY.md`. First council accepted the gate with one nonblocking inventory note. This revision does not edit that file |
| 2 | Evidence and privacy | A1 classes, origins, allowlist, issue location including `NONE`, session id, and release-blocking invariants are specified | Revised. Reopened until a fresh council passes. Not implemented |
| 3 | Store and proof | Option C ratified as architecture only, rejected options, and one canonical proof byte profile | Revised. `STORE_OPTION_C: FOUNDER_RATIFIED_ARCHITECTURE_ONLY`. No database exists. Reopened until a fresh council passes |
| 4 | Schema and migration | Unstable pre-1.0 identity, external recovery envelope, legacy origin rule | Revised. No migrator exists. Reopened until a fresh council passes |
| 5 | Correlation and query | Identity hierarchy, child process, query envelope, cardinality | Revised. No query engine exists. Reopened until a fresh council passes |
| 6 | Reliability | Product-health separation, fail-open, issue-location table aligned with A1, budgets at `NOT_SET` | Revised. Reopened until a fresh council passes |
| 7 | Threat model | Cases T1–T15, with T10 aligned to the external envelope, residual risk unset | Revised. Reopened until a fresh council passes |
| 8 | Implementation Force | A separate Founder implementation Force, after a fresh independent council passes | **Closed. Not started** |

## Rules

- Gates 1–7 in this pack are documents. They are not execution of the controls.
- Gate 8 is the only gate that could authorize product code, and only a separate Founder implementation Force can open it. This producer cannot open it.
- The first council reopened gates 2–7 and classified the pack `OPTICS_FOUNDATION_ARCHITECTURE_NEEDS_REVISION`. This revision leaves gates 2–7 reopened. The producer classification of the revision is `OPTICS_FOUNDATION_ARCHITECTURE_REVISION_READY_FOR_RECOUNCIL`. A fresh council has not passed.
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
