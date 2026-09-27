# Lifecycle script inventory

Audience: INTERNAL_RESTRICTED

All scripts live under `docs/planning/clean-host-lifecycle/scripts/`. They are bash or Node, with imports at the top of each Node module. They do not modify product source.

Dispatcher: `lifecycle.sh <command>`.

| Command | Script | Mutates lab root | Purpose |
| --- | --- | --- | --- |
| `preflight` | `preflight.sh` | No | Run the guard and print the classification banner. |
| `reset` | `reset.sh` | Yes | Open a new cycle and replace the disposable home. |
| `capture` | `capture.sh` | Yes | Run one loopback fixture under the disposable `HOME`. |
| `retain` | `retain.sh` | Yes | Copy the accepted run file and write `manifest.json`. |
| `stop` | `stop.sh` | Yes | Record a stop reason. Leave existing retention in place. |
| `expire` | `expire.sh` | Yes | Delete one retained cycle and write a tombstone. |
| `status` | `status.sh` | No | Print classification and the current state. |
| — | `lib.sh` | No | Shared guards. Sourced, not dispatched. |
| — | `inspect-run.mjs` | No | Shape check for one run file. |
| — | `emit-cycle-manifest.mjs` | Writes the manifest path it is given | Build the cycle manifest. |
| — | `check-guards.sh` | Temporary directory under `/tmp` only | Exercise the guards and one temporary cycle, then delete that directory. |

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | The command finished. This is not an evidence tier. |
| 20 | Stranger-host was requested, or state says stranger-host ran. |
| 21 | Phantom-Box or another control-plane variable is set, or state says Phantom-Box was included. |
| 22 | `VANTIO_HOME` is set. |
| 23 | `VANTIO_TELEMETRY=1`. |
| 24 | `LAB_ROOT` is missing or unsafe. |
| 25 | A required tool or repository file is missing, or Node is older than 18. |
| 26 | The lifecycle state or the arguments do not allow the command. |
| 27 | The run file failed the shape check, or the manifest was refused. |
| 28 | The operator's real `~/.vantio` changed during capture. |
| 29 | `expire` was asked to do something other than delete one named cycle. |
| 30 | The parent environment already set the fixture hostname, trace id, or mock port. |

Every non-zero exit prints `classification=CLEAN_HOST_INTERNAL_PROOF`, `evidence_tier=UNSET`, `stranger_host=NOT_RUN`, and `phantom_box=EXCLUDED`.

## Command contracts

### preflight

Reads the parent environment and `LAB_ROOT`. Prints the banner, the lab root, the repository root, `preflight=PASS`, and `preflight_assigns_evidence_tier=false`.

### reset

Arguments: optional `--abandon`.

Writes `state.env`, `home/.clean-host-cycle`, and `cycles/<id>/cycle.txt`. Prints `status=RESET_READY` and `reset_assigns_evidence_tier=false`.

### capture

Arguments: none.

Requires `RESET_READY`. Starts a loopback server on `127.0.0.1`, runs `node --require <interceptor> scripts/fixtures/minimal-agent.js`, checks that the operator data directory is unchanged, and requires exactly one run file whose name is `<cycle-id>.json`. The shape check is `inspect-run.mjs`. Success prints `status=CAPTURED` and `capture_assigns_evidence_tier=false`.

On fixture failure, missing server, shape failure, or an operator-home change, capture writes `STOPPED` and a reason file under `cycles/<id>/` before exiting. Agent stdout and stderr are stored in that cycle directory with mode `0600`.

### retain

Arguments: none.

Requires `CAPTURED`. Copies the run file to `retention/<id>/runs/`, mode `0600`, runs the shape check on the copy, and writes `retention/<id>/manifest.json`. Does not copy `config.json` or `telemetry-id`. Success prints `status=RETAINED` and `retain_assigns_evidence_tier=false`.

The manifest records whether `git status --porcelain` was empty at retain time. A dirty worktree is recorded as `worktree_dirty: true`. It does not stop the copy. A dirty tree is not a sealed tip.

### stop

Arguments: `--reason <TOKEN>` where the token is uppercase letters, digits, and underscores, at most 80 characters.

Writes `cycles/<id>/stop.txt` and sets status `STOPPED`. Does not delete `retention/`.

### expire

Arguments: `--cycle <id>`.

Refuses `--all`. Deletes `retention/<id>/` and writes `retention/<id>.expired` with the cycle id, the time, and the classification. The tombstone has no run bytes. If that id is the current cycle and the status is `RETAINED` or `STOPPED`, state becomes `STOPPED` with reason `EXPIRED`.

### status

Prints the banner and either `status=ABSENT` or the current status, cycle id, and run file name.

## check-guards.sh

This script is the scaffold exerciser. It:

1. Clears control-plane variables in its own process.
2. Expects the refusal exit codes for stranger-host, Phantom-Box, telemetry, split home, inherited host list, and unsafe `LAB_ROOT`.
3. Resets, captures, and retains one cycle under a temporary `LAB_ROOT` in `/tmp`.
4. Checks the manifest fields, expires that cycle, resets again, and checks that the operator `~/.vantio` snapshot is unchanged.
5. Deletes the temporary root on exit, including after a failed assertion.

The temporary cycle is not committed. Exit 0 from this script is `check_guards=PASS` together with `evidence_tier=UNSET`. It is a scaffold self-check.

## What the inventory does not include

- A stranger-host runner, an SSH command, a cloud VM provisioner, or a container build.
- A Phantom-Box soak, a `vantio-pro` process, or a publish step.
- A Python cycle.
- A call to `vantio prove`.
