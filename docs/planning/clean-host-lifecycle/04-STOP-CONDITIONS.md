# Stop conditions

Audience: INTERNAL_RESTRICTED

A stop ends the current command. It does not promote the cycle. It does not change `evidence_tier` from `UNSET`. It does not delete a retention bundle that `retain` already wrote, except `expire`, which is an explicit delete of one named cycle.

The product interceptor fails open for the agent. These conditions are lab conditions. They fail closed before capture, or they mark the cycle `STOPPED` when they fire during capture.

## 1. Conditions

| ID | Detection | Exit | Effect |
| --- | --- | --- | --- |
| S1 | Argument or command `stranger-host`, `--stranger`, or `--stranger-host` | 20 | No lab mutation from the dispatcher. Capture and reset refuse the same tokens. |
| S2 | `CLEAN_HOST_STRANGER_HOST_REQUEST=1`, `STRANGER_HOST=1`, or `VANTIO_STRANGER_HOST=1` | 20 | No capture. |
| S3 | `state.env` field `stranger_host` is anything other than `NOT_RUN` | 20 | The state file is not trusted. |
| S4 | `VANTIO_SOAK_LOCAL=1` | 21 | Phantom-Box soak is excluded. |
| S5 | `VANTIO_INGEST_URL` contains `:5001` | 21 | Phantom-Box local control plane is excluded. The lab match is broader than the interceptor's suffix regex. |
| S6 | `VANTIO_INGEST_URL` is set to any other value | 21 | The free path leaves this variable unset. |
| S7 | `VANTIO_API_KEY` or `VANTIO_IDENTITY` is non-empty | 21 | The control-plane client stays off. |
| S8 | `VANTIO_API_BASE` is set, or `VANTIO_CLOUD_INGEST` is `1` or `true`, or `VANTIO_AUDIT_MODE=1` | 21 | Control-plane and audit paths stay off. |
| S9 | `state.env` field `phantom_box` is anything other than `EXCLUDED` | 21 | The state file is not trusted. |
| S10 | `VANTIO_HOME` is set | 22 | Avoid a split between the writer and the CLI reader. |
| S11 | `VANTIO_TELEMETRY=1` | 23 | The usage ping stays off. Capture also exports `VANTIO_TELEMETRY_DISABLED=1` and `DO_NOT_TRACK=1`. |
| S12 | `LAB_ROOT` is empty, relative, contains `..`, is `/`, is the operator home, is inside the operator `~/.vantio`, is inside the repository, or has a parent that is missing or not writable | 24 | No writes. |
| S13 | `node` is missing or older than 18, `git` or `realpath` is missing, or the interceptor, CLI, or fixture file is missing | 25 | No capture. |
| S14 | Command arguments are unknown, status is not the one the command requires, or reset sees `CAPTURED` without `--abandon` | 26 | No promotion. An in-progress capture failure also uses 26 and sets `STOPPED` when the cycle already exists. |
| S15 | The run file is missing, is a symlink, is outside the disposable `runs/` directory, is not the single `<cycle-id>.json` file, or fails `inspect-run.mjs` | 27 | Status becomes `STOPPED` on the capture path. `retain` refuses. The file is not copied to `retention/`. |
| S16 | `state.env` `evidence_tier` is anything other than `UNSET`, or the run object contains `evidence_tier` | 27 | The lab does not accept a self-assigned tier. |
| S17 | The operator's real `~/.vantio` snapshot changes during capture | 28 | Status becomes `STOPPED` with reason `OPERATOR_HOME_TOUCHED`. |
| S18 | `expire` is called with `--all`, without one well-formed cycle id, or for a cycle that is not a retained bundle | 29 | No wide delete. |
| S19 | Parent `VANTIO_EXTRA_LLM_HOSTS`, `VANTIO_TRACE_ID`, or `VANTIO_MOCK_LLM_PORT` is set | 30 | Capture assigns those itself. An inherited host list would widen the fixture. |

## 2. Shape check details

`inspect-run.mjs` is S15. It accepts a file only when every item below holds:

- Regular file, not a symlink.
- JSON object with `vantio_run_log` `1`, `schema_version` `2`, `plane` `optics`, `free_mode` true.
- No `evidence_tier` property and no `workflow` property.
- Exactly one call: action `OBSERVED`, hostname `127.0.0.1`, method `POST`, path `/v1/chat/completions`, `ok` true, status 200, `error` null, positive `request_bytes`, positive `bytes`.
- Summary `blocked` 0, `redacted` 0, `total_calls` 1, `est_spend_usd` null, hosts exactly `["127.0.0.1"]`.
- The model string literal from `scripts/fixtures/minimal-agent.js` does not occur in the raw file.

A file that records `BLOCKED`, `REDACTED`, `free_mode` false, or any other hostname is a stop. Those values mean the process was not on the free observe path this lab defines.

## 3. What a stop does not do

- It does not set `STRANGER_HOST_PROVED`, `PROVED_EXTERNAL`, `INTEGRATION_PROVED`, `UNIT_PROVED`, or `CUSTOMER_VALIDATED`.
- It does not edit the traceability matrix.
- It does not open port `5001` or send a telemetry ping as part of the stop path.
- It does not delete `retention/` except through `expire --cycle`.
- It does not turn a stopped cycle into a citation for an external claim.

## 4. Operator stop

`lifecycle.sh stop --reason OPERATOR_STOP` records S14's state transition with an operator-supplied token. The reason is stored in `cycles/<id>/stop.txt` with the classification fields. Retention already written stays on disk until a separate expire.
