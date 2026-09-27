# Runbook

Audience: INTERNAL_RESTRICTED

```
NOT AUTHORIZED
```

Phase 0 is the only phase this prep force runs. Phases 1 through 6 are the procedure a later Founder force follows after it replaces `scripts/refuse-stranger-host-execution.mjs`. Running them from this packet hits SH-STOP-01.

The command list matches `.github/workflows/ci.yml` on main `5064f32f1cdfcb840dfd100e2ce5c712d046550d`.

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

Confirm tools before install. Stop under SH-STOP-14 when any item is missing. Do not install operating-system packages from this runbook.

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

CLI test helpers pass a child environment of `PATH` plus the variables that the test sets. Python telemetry tests clear `VANTIO_TELEMETRY`, `VANTIO_TELEMETRY_DISABLED`, and `DO_NOT_TRACK` in `setUp` and restore them afterward. The session exports still cover operator commands outside those harnesses, including the published smoke.

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

## Phase 5 — Release governance and local candidates

Authorization required. This prep does not run this phase.

Working directory: repository root.

```bash
python3 -m pip install --disable-pip-version-check 'pyyaml==6.0.1'
node --test scripts/release/governance.test.mjs
python3 scripts/release/test_promote_pypi.py -v
python3 scripts/release/test_pypi_publish_workflow.py -v
python3 -m pip install --disable-pip-version-check build
python3 -m build --outdir "$RUNNER_TEMP/candidates-py" packages/vantio-agent-sdk-py
```

Working directory: `packages/vantio-cli`. Create `$RUNNER_TEMP/candidates` as an empty directory first.

```bash
npm pack --ignore-scripts --pack-destination "$RUNNER_TEMP/candidates"
```

The governance tests are the CI tests, which use local stand-ins and do not upload. Stop under SH-STOP-04 when a token is present. `npm pack` and `python3 -m build` write local archives. An upload flag, or a call to a production upload module under `scripts/release/`, is SH-STOP-09.

## Phase 6 — Evidence and stop

Authorization required. This prep does not run this phase.

Write the bundle from `02-EVIDENCE-REQUIREMENTS.md`. `tier.txt` contains `UNSET`. Return `STRANGER_HOST_EVIDENCE_RECORDED_TIER_UNSET` when every CI parity command that the Founder included has an exit code of 0. Return the matching blocked classification from `04-FOUNDER-AUTHORIZATION-TEMPLATE.md` when a stop fires. Then follow `06-ROLLBACK.md` for the disposable paths.

## Published install smoke

`published_install_smoke` in the prep template is `NO`.

Default: NO

Authorization required even after a later force sets the field to `YES`. This prep does not run this phase. The commands stay in the runbook so the later force has a fixed list.

Use a new disposable virtualenv, separate from Phase 4. Set the telemetry overrides before the Python process starts. Do not call `shield()`. Do not call `vantio status --check-registry`. Re-check the registry pins and stop on drift before installing.

```bash
npm install -g @vantio/cli@0.3.24
vantio --version
vantio status
pip install 'vantio-agent-sdk==3.0.14'
python -c 'import vantio; print(vantio.__version__)'
```

Expected prints when the pins still match the 2026-09-27 manual: CLI `0.3.24`, Python `3.0.14`. A different print stops the smoke. Record the subject as `published`, separate from the git SHA.
