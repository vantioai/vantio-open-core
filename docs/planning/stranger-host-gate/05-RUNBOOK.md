# Runbook

Audience: INTERNAL_RESTRICTED

```
NOT AUTHORIZED
```

Phase 0 is the only phase this prep force runs. Phases 1 through 6 are the procedure a later Founder force follows after it replaces `scripts/refuse-stranger-host-execution.mjs`. Running them from this packet hits SH-STOP-01.

The later shell commands are the `run:` lines of the four jobs in `.github/workflows/ci.yml` on main `5064f32f1cdfcb840dfd100e2ce5c712d046550d`. `PACKET-MANIFEST.json` `later_commands` is that list, with one cited omission.

Cited and absent from `later_commands`:

- Job `lint-and-test-js`, step `Install strace`: `sudo apt-get update && sudo apt-get install -y strace`. The later host class requires `strace` already on `PATH` (SH-STOP-14). The later matrix installs no operating-system packages.

Present on that pin and included in `later_commands`:

- Job `candidate-artifacts`, step `Install dependencies`: a second `pnpm install --frozen-lockfile` (the same text as the install in `lint-and-test-js`).
- Job `candidate-artifacts`, step `Pack @vantio/cli candidate`, `working-directory: packages/vantio-cli`: `mkdir -p "$RUNNER_TEMP/candidates"`, then the `npm pack` line.
- Job `candidate-artifacts`, step `Build Python sdist and wheel candidate`, repository root: `mkdir -p "$RUNNER_TEMP/candidates-py"`, then `python3 -m pip install --disable-pip-version-check build`, then `python3 -m build --outdir "$RUNNER_TEMP/candidates-py" packages/vantio-agent-sdk-py`.

Job `candidate-artifacts` also has Actions step `actions/upload-artifact@v4` named `release-candidates`. That step is not a shell `run:` line and is absent from `later_commands`. The later matrix leaves the archives in the disposable `RUNNER_TEMP`.

## Phase 0 — Prep verifier

Run from the repository root:

```bash
node docs/planning/stranger-host-gate/scripts/verify-packet-prep.mjs
```

Pass: exit 0, stdout `STRANGER_HOST_PACKET_READY_AWAITING_EXECUTION_AUTH`.

Confirm the refuse entrypoints on their own:

```bash
node docs/planning/stranger-host-gate/scripts/refuse-stranger-host-execution.mjs
node docs/planning/stranger-host-gate/scripts/refuse-rollback.mjs
```

Pass: each exits 2. Stdout is `STRANGER_HOST_EXECUTION_BLOCKED_AWAITING_AUTH` or `STRANGER_HOST_ROLLBACK_BLOCKED_AWAITING_AUTH`.

## Phase 1 — Host attestation

Authorization required. This prep does not run this phase.

Record `host.txt` as specified in `02-EVIDENCE-REQUIREMENTS.md`. Stop under SH-STOP-02 when the machine is a customer host. Stop under SH-STOP-03 when the machine is this cloud agent, the author workstation, or a GitHub-hosted runner for this repository.

Confirm tools before install. Stop under SH-STOP-14 when any item is missing. The later matrix installs no operating-system packages. The apt-get line quoted above stays a citation.

- Linux, `strace` on `PATH`
- Node 22
- pnpm equal to the `packageManager` field in `package.json`
- Python 3.10, Python 3.11, and Python 3.12
- git

## Phase 2 — Clean tree and empty directories

Authorization required. This prep does not run this phase.

Clone or checkout the Founder-locked SHA. Stop under SH-STOP-05 or SH-STOP-06 when the SHA differs or the worktree is dirty.

Create two new empty directories and export them:

- `HOME` — disposable home
- `RUNNER_TEMP` — disposable pack output

Stop under SH-STOP-12 when either directory already contains files.

Export `VANTIO_TELEMETRY_DISABLED=1` and `DO_NOT_TRACK=1`. Leave the other names in `02-EVIDENCE-REQUIREMENTS.md` unset. Record presence in `env-posture.txt`. Stop under SH-STOP-04 or SH-STOP-08 when the posture is wrong.

CLI test helpers pass a child environment of `PATH` plus the variables that the test sets. Python telemetry tests clear `VANTIO_TELEMETRY`, `VANTIO_TELEMETRY_DISABLED`, and `DO_NOT_TRACK` in `setUp` and restore them afterward. Cases that opt in set `VANTIO_TELEMETRY=1` and point `VANTIO_INGEST_URL` at a local `MockServer`. The session exports still cover operator commands outside those harnesses, including the published smoke. Phase 4’s other modules call `shield()` with the session overrides still in the environment, so `send_run_telemetry_once` returns immediately. See SH-STOP-08.

## Phase 3 — JavaScript CI parity

Authorization required. This prep does not run this phase.

Working directory: repository root.

```bash
pnpm install --frozen-lockfile
pnpm --filter @vantio/cli run lint
pnpm --filter @vantio/agent-sdk run typecheck
pnpm --filter @vantio/agent-sdk run typecheck:test
pnpm --filter @vantio/cli run test
pnpm --filter @vantio/agent-sdk run test
pnpm --filter @vantio/agent-sdk run build
```

`pnpm install --frozen-lockfile` reads the lockfile’s registry. Failure is SH-STOP-15. `--no-frozen-lockfile` is forbidden.

`pnpm --filter @vantio/cli run test` includes local mocks on `127.0.0.1` and the `strace` checks in `packages/vantio-cli/test/optics-cx.test.js`. Keep `TARGET_URL` unset (SH-STOP-18).

## Phase 4 — Python CI parity

Authorization required. This prep does not run this phase.

Repeat this pair once per Python 3.10, 3.11, and 3.12, using that interpreter. Working directory for unittest: `packages/vantio-agent-sdk-py`. The pip line may run from the repository root with that interpreter.

```bash
python -m pip install --disable-pip-version-check requests httpx aiohttp urllib3
python -m unittest discover -s tests -t . -v
```

These tests import the repository tree. That tree’s Python version is 3.1.0. Stop under SH-STOP-19 when the same interpreter also has published 3.0.14 installed for the smoke below.

`python -m unittest discover -s tests -t . -v` calls `shield()` from `tests/test_sdk.py`, `tests/test_http_observe.py`, `tests/test_optics_status.py`, `tests/test_socket_timing.py`, and `tests/test_outcome_clarity.py`. `shield()` calls `send_run_telemetry_once`. With the Phase 2 session (`VANTIO_TELEMETRY` unset, `VANTIO_TELEMETRY_DISABLED=1`, `DO_NOT_TRACK=1`), that function returns immediately. `tests/test_telemetry.py` clears those three names in `setUp`. Cases that opt in set `VANTIO_TELEMETRY=1` and set `VANTIO_INGEST_URL` to a local `MockServer` on `127.0.0.1`. A ping aimed at the public ingest stops the run under SH-STOP-08.

## Phase 5 — Release governance and local candidates

Authorization required. This prep does not run this phase.

Working directory: repository root.

```bash
python3 -m pip install --disable-pip-version-check 'pyyaml==6.0.1'
node --test scripts/release/governance.test.mjs
python3 scripts/release/test_promote_pypi.py -v
python3 scripts/release/test_pypi_publish_workflow.py -v
```

The governance tests are the CI tests, which use local stand-ins and do not upload. Stop under SH-STOP-04 when a token is present.

Job `candidate-artifacts` installs dependencies again. Working directory: repository root.

```bash
pnpm install --frozen-lockfile
```

That is the second `pnpm install --frozen-lockfile` on the prepared SHA. The first is Phase 3.

Working directory: `packages/vantio-cli`. These two lines are the `Pack @vantio/cli candidate` step.

```bash
mkdir -p "$RUNNER_TEMP/candidates"
npm pack --ignore-scripts --pack-destination "$RUNNER_TEMP/candidates"
```

Working directory: repository root. These lines are the `Build Python sdist and wheel candidate` step.

```bash
mkdir -p "$RUNNER_TEMP/candidates-py"
python3 -m pip install --disable-pip-version-check build
python3 -m build --outdir "$RUNNER_TEMP/candidates-py" packages/vantio-agent-sdk-py
```

`npm pack` and `python3 -m build` write local archives under the disposable `RUNNER_TEMP`. The CI job’s `actions/upload-artifact@v4` step stays out of this list. An upload flag, or a call to a production upload module under `scripts/release/`, is SH-STOP-09.

## Phase 6 — Evidence and stop

Authorization required. This prep does not run this phase.

Write the bundle from `02-EVIDENCE-REQUIREMENTS.md`. `tier.txt` contains `UNSET`. Return `STRANGER_HOST_EVIDENCE_RECORDED_TIER_UNSET` when every CI parity command that the Founder included has an exit code of 0. Return the matching blocked classification from `04-FOUNDER-AUTHORIZATION-TEMPLATE.md` when a stop fires. Then follow `06-ROLLBACK.md` for the disposable paths.

## Published install smoke

`published_install_smoke` in the prep template is `NO`.

Default: NO

Authorization required even after a later force sets the field to `YES`. This prep does not run this phase. The commands stay in the runbook so the later force has a fixed list.

Use a new disposable virtualenv, separate from Phase 4. Set the telemetry overrides before the Python process starts. The commands below print the CLI version, plain `vantio status`, and the Python version. Phase 4’s unittest suite is the suite that calls `shield()` (SH-STOP-08). `vantio status --check-registry` stays outside the matrix. Re-check the registry pins and stop on drift before installing.

```bash
npm install -g @vantio/cli@0.3.24
vantio --version
vantio status
pip install 'vantio-agent-sdk==3.0.14'
python -c 'import vantio; print(vantio.__version__)'
```

Expected prints when the pins still match the 2026-09-27 manual: CLI `0.3.24`, Python `3.0.14`. A different print stops the smoke. Record the subject as `published`, separate from the git SHA.
