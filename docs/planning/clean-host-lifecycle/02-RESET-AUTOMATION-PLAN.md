# Reset automation plan

Audience: INTERNAL_RESTRICTED

Command: `scripts/lifecycle.sh reset`

Reset prepares a new cycle. It does not capture, and it does not assign an evidence tier.

## 1. Preconditions

Reset runs the same guard as preflight. The parent environment must already satisfy `04-STOP-CONDITIONS.md`. In particular:

- `LAB_ROOT` is absolute, is not `/`, is not the operator home, is not inside the operator `~/.vantio`, and is not inside the git repository.
- The parent of `LAB_ROOT` exists and is writable.
- Phantom-Box and control-plane variables are unset.
- `VANTIO_HOME` is unset.
- `VANTIO_TELEMETRY` is unset.
- No stranger-host argument or variable is present.

The operator invokes reset from their normal shell. The script redirects `HOME` only inside later capture. The operator does not export `HOME` to the lab home before calling the script. `CLEAN_HOST_OPERATOR_HOME` is the `HOME` value at process start, so the script can still see the real data directory after capture changes `HOME`.

## 2. Steps

1. Parse arguments. The only accepted flag is `--abandon`. Any other argument stops the process.
2. Run the guard. A failed guard exits before any delete.
3. Create `$LAB_ROOT` with mode `0700` if it is missing.
4. If `state.env` exists and status is `CAPTURED`, stop unless `--abandon` is set. With `--abandon`, write `cycles/<id>/abandoned.txt` with reason `ABANDONED_BEFORE_RETAIN` and then continue. That file contains the reason and the classification. It does not contain run bytes.
5. Delete `$LAB_ROOT/home` only.
6. Create `$LAB_ROOT/home`, `$LAB_ROOT/cycles`, and `$LAB_ROOT/retention` with mode `0700`.
7. Allocate a cycle id `YYYYMMDDTHHMMSSZ-` plus 8 hex characters from `node:crypto` random bytes.
8. Write `$LAB_ROOT/home/.clean-host-cycle` and a copy at `cycles/<id>/cycle.txt`. Both record classification, `evidence_tier=UNSET`, `stranger_host=NOT_RUN`, `phantom_box=EXCLUDED`, the cycle id, the UTC time, and `git rev-parse HEAD`.
9. Write `state.env` with status `RESET_READY`.

`umask 077` is set at process start. State and marker files are then chmod `0600`.

## 3. What reset deletes

| Path | Result |
| --- | --- |
| `$LAB_ROOT/home` | Removed and recreated |
| Run files from the previous cycle that lived only in that home | Removed with the home |
| `$LAB_ROOT/retention/` | Kept |
| `$LAB_ROOT/cycles/` | Kept |
| Operator `~/.vantio` | Not a reset target. The path is refused if it is `LAB_ROOT`. |

A `CAPTURED` cycle that has not been retained still holds its only copy under `home/`. Reset without `--abandon` refuses to delete it. Reset with `--abandon` deletes that unretained copy on purpose. The abandon note stays under `cycles/`.

## 4. Idempotence

Reset may run again from `ABSENT`, `RESET_READY`, `RETAINED`, or `STOPPED`. Each invocation allocates a new cycle id and replaces the disposable home. Previous retention bundles stay until `expire --cycle <id>`.

Two resets in a row without capture leave the first cycle as a marker under `cycles/` and a new `RESET_READY` cycle in `state.env`. The first cycle has no retention bundle.

Reset is not idempotent in the sense of preserving the cycle id. The stable result is a fresh home and an unchanged retention directory.

## 5. Failure behavior

| Failure | Result |
| --- | --- |
| Guard fails | Exit with the stop code in `04-STOP-CONDITIONS.md`. `home/` is unchanged. |
| Status is `CAPTURED` and `--abandon` is absent | Exit 26. The run file stays in the disposable home. |
| `node` or `git` is missing | Exit 25 before the delete. |
| Disk error during recreate | The script stops on the failed command. The operator inspects `$LAB_ROOT` before retrying. A partial home is not a `CAPTURED` cycle unless `state.env` says so. |

Reset does not contact the network, does not open port `5001`, and does not read the operator data directory except for the path checks in the guard.

## 6. Environment after reset

Reset does not print a shell snippet that exports secrets. The next command is `lifecycle.sh capture`, which performs isolation itself:

- `HOME=$LAB_ROOT/home`
- `VANTIO_HOME`, `VANTIO_API_KEY`, `VANTIO_IDENTITY`, `VANTIO_INGEST_URL`, `VANTIO_API_BASE`, `VANTIO_SOAK_LOCAL`, `VANTIO_CLOUD_INGEST`, `VANTIO_AUDIT_MODE`, `VANTIO_TELEMETRY`, `VANTIO_EXTRA_LLM_HOSTS`, `VANTIO_TRACE_ID`, and `VANTIO_MOCK_LLM_PORT` unset
- `VANTIO_TELEMETRY_DISABLED=1` and `DO_NOT_TRACK=1` exported for the capture process
- `VANTIO_EXTRA_LLM_HOSTS=127.0.0.1`, `VANTIO_TRACE_ID=<cycle-id>`, and `VANTIO_MOCK_LLM_PORT=<ephemeral>` applied only to the fixture process

## 7. Relationship to product retention

The product has no prune command and no retention policy. Files under the real `~/.vantio/runs` stay until a person deletes them. This reset plan applies only to `$LAB_ROOT`. It is not a product feature and it does not delete customer runs.
