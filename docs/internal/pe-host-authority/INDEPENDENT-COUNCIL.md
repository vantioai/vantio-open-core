# Independent council

Audience: INTERNAL_RESTRICTED

Status: `PENDING_INDEPENDENT_COUNCIL`

Producer classification under review: `PE_HOST_AUTHORITY_READY_FOR_COUNCIL`

This file is the producer stub. The proof producer does not sit the council and does not write a verdict.

## 1. What a separate council reviews

| Item | Value |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Proof package | `packages/pe-host-authority/` |
| Tests | `tests/pe-host-authority/` |
| Notes | `docs/internal/pe-host-authority/` |
| Open-core base | `89f95099d0dce463307eb75d78e7fcf2ef99feb2` |
| Private product tip named by the producer | `631e435315cd780d83d3259e111893c1d0569bc3` |
| eBPF blob the producer read | `5b20674536e55faecd5cde75f72a9f0140bb6b2b` |
| Loader blob | `773f3ab4c201079db331bd862dc5b31ed8a6ba77`, marked `NOT_READ` |
| Producer | `bc-6c5477b2-f25a-5ed5-bef1-6927d216024b` |
| Classification the producer claims | `PE_HOST_AUTHORITY_READY_FOR_COUNCIL` |

## 2. Seats

| Seat | Scope | Verdict |
| --- | --- | --- |
| 1 | Thirteen surfaces, each with a named mechanism | `UNSAT` |
| 2 | Contract rows stay `CONTRACT_ONLY` and `kernel_executed: false` | `UNSAT` |
| 3 | Best-effort attaches, uid 0, cgroup id 0, and detached `cgroup_skb` stay residuals or gaps | `UNSAT` |
| 4 | Absence claims stay bounded to the cited program file | `UNSAT` |
| 5 | Local ledger prevention stays `FAIL_CLOSED_GAP` | `UNSAT` |
| 6 | No loader edit, no eBPF load, no CLI/SDK/Python byte change, no customer manual | `UNSAT` |

## 3. Checks the council can re-run

```sh
node --test tests/pe-host-authority/*.test.cjs
```

- The proof package is absent from `pnpm-workspace.yaml`.
- `@vantio/cli` stays `0.3.24`, `@vantio/agent-sdk` stays `0.2.4`, and Python `vantio-agent-sdk` stays `3.1.0`.
- No path under the proof tree contains `PRIVATE-MANUAL` or `CUSTOMER-MANUAL`.
- `docs/operations-guide.md` from blob `1b973342b3bf7f6aa6cdad70de49fa6e26db0077` is not pasted.
- `HOST-AUTHORITY-MANIFEST.json` hashes match the listed files.
- The producer classification is present and no council-pass token is present.

## 4. Verdict block

| Field | Value |
| --- | --- |
| Council agent | `UNSAT` |
| Reviewed tip | `UNSAT` |
| Verdict | `PENDING_INDEPENDENT_COUNCIL` |
| Blocking findings | `UNSAT` |
