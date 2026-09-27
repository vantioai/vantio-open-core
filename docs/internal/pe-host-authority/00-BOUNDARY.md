# Track 7 — host authority boundary

Audience: INTERNAL_RESTRICTED

Producer role: internal proof. This agent does not sit the independent council, does not self-assign a council pass, and does not authorize a load, a publish, or a deploy.

Producer identity: Cursor cloud agent `bc-6c5477b2-f25a-5ed5-bef1-6927d216024b`.

Producer classification: `PE_HOST_AUTHORITY_READY_FOR_COUNCIL`

That classification means this proof is ready for a separate council. It is not a council verdict, not a kernel attestation, and not a statement that this host is under universal Linux control.

## 1. Locked input

| Item | Value |
| --- | --- |
| Writable repository | `vantioai/vantio-open-core` |
| Open-core base | `89f95099d0dce463307eb75d78e7fcf2ef99feb2` |
| Base subject | Merge pull request #83 from `vantioai/cursor/pe-ws4-vocabulary-binding-f9f5` |
| Branch | `cursor/pe-host-authority-024b` |
| Private product tip read | `vantioai/vantio-phantom-engine` `631e435315cd780d83d3259e111893c1d0569bc3` |
| eBPF program file read | `vantio-phantom-engine/src/main.rs` blob `5b20674536e55faecd5cde75f72a9f0140bb6b2b` |
| Shared contract read | `vantio-common/src/lib.rs` blob `f764460fc8ee28c9571be547f317d04cabc9153c` |
| Architecture file read | `architecture_state.md` blob `84d53654894180cbf351d62231f90e564504162c` |
| Reference-monitor file read | `docs/enterprise/REFERENCE_MONITOR.md` blob `57b0d613267a9ea57b2f94897b5c839727bc5e1f` |
| Loader source | `vantio-loader/src/main.rs` blob `773f3ab4c201079db331bd862dc5b31ed8a6ba77` — `NOT_READ` |

## 2. What this force does

- Adds a private package, `@vantio/pe-host-authority` at `0.0.0-internal-proof`, outside `pnpm-workspace.yaml`.
- Encodes the decision rules of the cited mechanisms for thirteen surfaces: files, processes, descendants, privileges, credentials, namespaces, containers, devices, persistence, resource use, monitor disablement, policy tampering, and evidence tampering.
- Runs those rules as a contract. Every contract row carries `execution: CONTRACT_ONLY` and `kernel_executed: false`.
- Runs three local checks on this process: effective capabilities and `/sys/fs/bpf` writability, a child process that receives no trace id and no allowlist, and a temporary hash-chained ledger.
- Leaves `INDEPENDENT-COUNCIL.md` as `PENDING_INDEPENDENT_COUNCIL`.

The package is the proof. It is not the Phantom Engine loader and it is not an eBPF program.

## 3. What this force keeps closed

- Live eBPF load, `bpftool`, kernel verifier runs, and any build or edit of `vantio-loader`.
- Kernel or loader exploration. This process is not isolated clean-host infrastructure. `clean_host_infrastructure` stays false.
- Stranger-host execution, customer hosts, and customer deploy.
- CLI `@vantio/cli@0.3.24`, Node SDK `@vantio/agent-sdk@0.2.4`, and Python `vantio-agent-sdk@3.1.0` source, version, and bytes.
- npm, PyPI, GHCR, tags, and announcements.
- Customer-manual bodies. The operations guide blob `1b973342b3bf7f6aa6cdad70de49fa6e26db0077` stays uncopied.
- A copy of the private Rust sources into this repository.
- Merge of this pull request. Council is a separate agent.

## 4. How to read a row

| Field | Meaning |
| --- | --- |
| `DENIED_BY_CITED_MECHANISM` | The cited rule, for `open` and `openat`, returns `-EACCES` when the path matches. The program was not attached here. |
| `BEST_EFFORT_NOT_PROVED` | The cited file marks that attach as best-effort. `decision_if_attached` is the rule. Attach was not proved. |
| `CITED_DROP` / `CITED_ALLOW` | The cited classifier's pass or drop. A pass is the rule for that packet. It is not a clearance of the host. |
| `NOT_COVERED` | The named mechanism does not decide this attempt. |
| `NAMED_RESIDUAL` | A privileged path remains. It is recorded and it is not a pass. |
| `NOT_REIMPLEMENTED` | The cited program has the rule. This contract does not reimplement it. |
| `CHAIN_INTACT` / `DETECTED` | Local ledger result. `prevention: FAIL_CLOSED_GAP` stays on every evidence row. |

Absence rows are bounded to `vantio-phantom-engine/src/main.rs` at the blob above. This force did not search every other path in the private repository.

## 5. Re-run

From the repository root:

```sh
node --test tests/pe-host-authority/*.test.cjs
```

The producer run of that command is recorded in `02-LOCAL-PROOF.md`.
