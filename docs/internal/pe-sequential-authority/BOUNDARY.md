# Sequential and aggregate authority — boundary

INTERNAL_CANDIDATE | EVALUATE_ONLY | NOT_HOST_ENFORCEMENT | NOT_SHIPPED | NO_KERNEL | NO_ENROLL | NO_CREDENTIAL_MATERIAL | NO_STABLE_SCHEMA

Audience: INTERNAL_RESTRICTED

Producer classification: `PE_SEQUENTIAL_AGGREGATE_AUTHORITY_READY_FOR_COUNCIL`

That classification means this branch is ready for a separate council. It is a producer handoff. Council status is `PENDING_INDEPENDENT_COUNCIL`.

## Starting point

Repository: `vantioai/vantio-open-core`

Locked commit: `89f95099d0dce463307eb75d78e7fcf2ef99feb2`

Subject: Merge pull request #83 from `vantioai/cursor/pe-ws4-vocabulary-binding-f9f5`

Producer: Cursor cloud agent `bc-9eb86d6c-ac94-528a-8d98-23f58f64ad38`, model Grok 4.7, reasoning `xhigh`, context `500k`, fast `false`.

Producer URL: https://cursor.com/agents/bc-9eb86d6c-ac94-528a-8d98-23f58f64ad38

## What this candidate contains

- `packages/pe-sequential-authority/` — private package `@vantio/pe-sequential-authority` at `0.0.0-unstable-pre-1.0`
- `tests/pe-sequential-authority/` — invariant, axis, input, and isolation tests
- `docs/internal/pe-sequential-authority/` — these notes

The package is not a pnpm workspace member. CLI `0.3.24`, the Node SDK, the Python SDK `3.1.0`, publish workflows, and the Gate compatibility package do not import it.

## What this candidate evaluates

A pure function over a caller-supplied envelope, catalog, and ledger. It decides one step at a time. Aggregate counters cover action, sequence, run, workload, parent/child lineage, credential, destination, tenant, node, fleet, time window, and resource budget.

The nine invariants are listed in `INVARIANTS.md` and exported as `INVARIANTS`.

## What stays closed

- Customer deploy, stranger-host execution, and announcements
- Credential material, prompts, and raw bodies
- CLI `0.3.24` and Python `3.1.0` bytes
- Kernel programs, enroll, freeze executors, and quarantine executors
- A second host enforcement engine in this repository
- Copying Phantom Engine customer-manual bodies onto public main
- A stable schema, a package publish, a tag, or a merge
- Founder decisions EG-D1 through EG-D10. Redelegation stays `forbidden`
- Marking reference-monitor doctrine Present. The doctrine file remains `SCOPED`

`revoke` records a catalog transition. `evaluate` authorizes a revoke step. Host attachment stays false on every result.

## Doctrine citation

Read-only. This tree does not vendor the file.

| Repo | Commit | Path | Blob |
| --- | --- | --- | --- |
| `vantioai/vantio-phantom-engine` | `631e435315cd780d83d3259e111893c1d0569bc3` | `docs/enterprise/REFERENCE_MONITOR.md` | `57b0d613267a9ea57b2f94897b5c839727bc5e1f` |

Enterprise grant rules already on this repository: `docs/planning/enterprise-governance/`. This candidate does not edit that packet and does not satisfy EG-SP-1 through EG-SP-5.
