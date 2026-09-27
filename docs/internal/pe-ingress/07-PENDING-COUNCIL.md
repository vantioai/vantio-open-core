# Independent council

Audience: INTERNAL_RESTRICTED

Status: `PENDING_INDEPENDENT_COUNCIL`

Producer classification under review: `PE_INGRESS_PROGRAM_READY_FOR_COUNCIL`

This file is the producer stub. The producer does not sit the council and does not write a verdict.

## 1. What a separate council reviews

| Item | Value |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Paths | `packages/pe-ingress-authority/`, `tests/pe-ingress/`, `docs/internal/pe-ingress/` |
| Open-core base | `89f95099d0dce463307eb75d78e7fcf2ef99feb2` |
| Private product tip named by the producer | `631e435315cd780d83d3259e111893c1d0569bc3` |
| Producer | `bc-9ff0b560-ba53-5e6d-b8cc-0f62237258f5` |
| Classification the producer claims | `PE_INGRESS_PROGRAM_READY_FOR_COUNCIL` |

## 2. Seats

| Seat | Scope | Verdict |
| --- | --- | --- |
| 1 | Inventory matches the cited private blobs and does not promote Phantom-Box rows | `UNSAT` |
| 2 | Reachability and expected listen are not authority | `UNSAT` |
| 3 | A valid credential is not integrity, including a credential for another workload | `UNSAT` |
| 4 | Unknown, stale, and missing identity, integrity, policy, and health do not widen a grant | `UNSAT` |
| 5 | Live loader is unmutated and packet effect stays unapplied | `UNSAT` |
| 6 | Post-accept deny and child escape record containment without a live executor | `UNSAT` |
| 7 | Revoke, restart, and rollback drop grants and do not set `protected` | `UNSAT` |
| 8 | Unsupported paths and shared freshness `UNKNOWN` stay named | `UNSAT` |
| 9 | No customer deploy, stranger-host execution, CLI `0.3.24` edit, or Python `3.1.0` edit | `UNSAT` |

## 3. Checks the council can re-run without a live load

```sh
node --test tests/pe-ingress/*.test.cjs
```

- The diff from `89f95099d0dce463307eb75d78e7fcf2ef99feb2` stays under the three paths in section 1.
- `pnpm-workspace.yaml` does not list `pe-ingress-authority`.
- Result objects keep `live_loader_mutated` false and `freshness` `UNKNOWN`.
- `07-PENDING-COUNCIL.md` still says `PENDING_INDEPENDENT_COUNCIL` until this council replaces it.

## 4. Verdict block

| Field | Value |
| --- | --- |
| Council agent | `UNSAT` |
| Reviewed tip | `UNSAT` |
| Verdict | `PENDING_INDEPENDENT_COUNCIL` |
| Blocking findings | `UNSAT` |
