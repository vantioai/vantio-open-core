# Local proof

Audience: INTERNAL_RESTRICTED

Producer classification: `PE_HOST_AUTHORITY_READY_FOR_COUNCIL`

## What ran

Command, from the repository root:

```sh
node --test tests/pe-host-authority/*.test.cjs
```

The tests under `tests/pe-host-authority/` execute the contract cases in `cases.cjs`, one live child, one local capability read, and four temporary-ledger checks. The manifest records the contract-case count.

Contract cases assert the disposition, the mechanism id, `kernel_executed: false`, `execution: CONTRACT_ONLY`, and `authority_widened: false`. The host fixture is cloned per case and compared before and after. A credential token used in the present-token case does not appear in the decision JSON.

Local rows on the producer process:

| Check | Result class |
| --- | --- |
| `CapEff` and `CapPrm` read from `/proc/self/status` | `THIS_PROCESS` |
| Write access to `/sys/fs/bpf` | `THIS_PROCESS`. The producer euid was not 0, both capability masks were zero, and the mount was not writable. `pins_created_by_this_force` is false. |
| `spawn` of `process.execPath -e` with `PATH` only | `THIS_PROCESS`. Child `ppid` is this process. `VANTIO_TRACE_ID` and `VANTIO_ALLOW` are null. |
| Hash chain under `os.tmpdir()` | `TEMP_FILE`. Directory removed after the check. |

`privileged_helper_invoked` is false. `kernel_loaded_this_force` is false. `loader_mutated_this_force` is false. `clean_host_infrastructure` is false. `stranger_host` is `NOT_RUN`.

## What the rows refuse

- A `CITED_DROP` or `DENIED_BY_CITED_MECHANISM` row is the cited rule. It is not a packet captured on this host and it is not an attached kprobe.
- `BEST_EFFORT_NOT_PROVED` keeps `decision_if_attached` and does not upgrade it to a deny.
- `NOT_REIMPLEMENTED` covers VLAN/QinQ parse, IPv6 LPM, PID-offset measurement, loader attach gating, Kubernetes `cgroup_skb` auto-attach, minimal-cap sufficiency, and live Spanner insert.
- Evidence prevention stays `FAIL_CLOSED_GAP` when detection succeeds.
- The classification token is `PE_HOST_AUTHORITY_READY_FOR_COUNCIL`. The council verdict field is `PENDING_INDEPENDENT_COUNCIL`.

## Frozen surfaces left in place

| Surface | Version | Touched |
| --- | --- | --- |
| `@vantio/cli` | `0.3.24` | No |
| `@vantio/agent-sdk` | `0.2.4` | No |
| `vantio-agent-sdk` (Python) | `3.1.0` | No |
| `pnpm-workspace.yaml` | unchanged membership | The proof package is not a member |
