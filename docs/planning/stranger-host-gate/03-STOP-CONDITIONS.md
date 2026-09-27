# Stop conditions

Audience: INTERNAL_RESTRICTED

A stop ends the activity. The operator records the stop id and leaves the host unchanged except for the rollback in `06-ROLLBACK.md` when a disposable directory was already created. Prep itself creates no host directory. During prep, the refuse scripts are the stop.

## SH-STOP-01 Execution entrypoint

`scripts/refuse-stranger-host-execution.mjs` exits 2 and prints `STRANGER_HOST_EXECUTION_BLOCKED_AWAITING_AUTH`. Invoking it is the stop for any attempt to start the host run from this packet. The verifier exits 2 with `STRANGER_HOST_EXECUTION_BLOCKED_PREP_ONLY` when `--execute` is passed or when `STRANGER_HOST_EXECUTE` or `STRANGER_HOST_HOST` is set.

## SH-STOP-02 Customer host

A host that runs a customer workload, holds customer data, or is operated for a customer is forbidden. This force has no customer-validation step. `CUSTOMER_VALIDATED` stays unset.

## SH-STOP-03 Producer environment

This cloud agent, the author workstation, and GitHub-hosted runners for `vantioai/vantio-open-core` are producer environments. Re-running CI there can support a producer result. It is the wrong host for a stranger-host claim. The later host is one the Founder names outside those environments.

## SH-STOP-04 Credentials

Creating or using an API key, npm token, PyPI token, SSH key, cloud credential, or `VANTIO_API_KEY` stops the run. The packet ships with `credentials` set to `NONE`. The later environment keeps `NPM_TOKEN`, `PYPI_TOKEN`, `TWINE_USERNAME`, `TWINE_PASSWORD`, `NODE_AUTH_TOKEN`, and `VANTIO_API_KEY` unset. The posture file records presence, not values.

## SH-STOP-05 SHA drift

The checkout must equal the SHA a later Founder force locks. Any other SHA stops the run before install.

## SH-STOP-06 Dirty tree

Tracked edits, staged edits, or untracked files on the stranger-host checkout stop the run. The tree matches the locked commit.

## SH-STOP-07 Command scope

The authorized command list, once a later force exists, is the CI parity list in `05-RUNBOOK.md`. Adding a package, a workflow, or a live provider call stops the run. While `published_install_smoke` remains `NO`, the published install commands are out of scope even though the runbook prints them.

## SH-STOP-08 Telemetry

The later session sets `VANTIO_TELEMETRY_DISABLED=1` and `DO_NOT_TRACK=1`. `VANTIO_TELEMETRY` stays unset. Published Python 3.0.14 `shield()` sends unless those overrides are set (`docs/products/optics/TELEMETRY.md`). The default matrix does not call `shield()`. A process that would send a ping stops the run.

## SH-STOP-09 Registry write

Forbidden: `npm publish`, `pnpm publish`, twine upload, git tags, GitHub releases, and the publish workflows named in `00-PACKET-BOUNDARY.md`. `npm pack` and `python3 -m build` write local archives into the disposable `RUNNER_TEMP` only.

The release-governance tests in CI call local stand-ins and do not upload. A token in the environment is SH-STOP-04. Invoking a production upload module under `scripts/release/` is SH-STOP-09.

## SH-STOP-10 Product edits

The later checkout is read-only. Package manifests, source files, and version numbers stay at the locked SHA. CLI 0.3.24 and Python source 3.1.0 are the versions in `docs/governance/VERSION-METADATA.json`.

## SH-STOP-11 Tiers and gates

The later bundle’s `tier.txt` contains `UNSET`. The run leaves Gate 8 closed and leaves `docs/architecture/optics-foundation/` unchanged. Writing `STRANGER_HOST_PROVED`, `PROVED_EXTERNAL`, or `CUSTOMER_VALIDATED` into the bundle stops the run.

## SH-STOP-12 Existing home data

The later run exports `HOME` to a new empty disposable directory before any command. If that directory exists and is not empty, stop. The account’s previous home, including any pre-existing `~/.vantio`, stays on its original path because `HOME` points at the disposable directory.

## SH-STOP-13 Phantom Engine

Enrollment, kernel modules, eBPF, and privileged host enforcement are outside `.github/workflows/ci.yml` and outside this repository’s prep packet. A step that needs root for those mechanisms stops the run.

## SH-STOP-14 Host tools

The default later host class is Linux with `strace` already on `PATH`, Node 22, pnpm from `package.json` `packageManager`, and Python 3.10, 3.11, and 3.12. A missing tool stops the run. The matrix does not install operating-system packages. A non-Linux host is a different matrix; this packet does not define one, and the `strace` tests in `packages/vantio-cli/test/optics-cx.test.js` are part of the CLI test script.

## SH-STOP-15 Lockfile

The install command is `pnpm install --frozen-lockfile`. Failure stops the run. `--no-frozen-lockfile` is forbidden.

## SH-STOP-16 Evidence contents

Logs may contain test output. Customer prompts, completions, private keys, and registry tokens in the bundle stop the run. The rollback then deletes the disposable directories. Provider hostnames and synthetic canaries printed by the CI suite are fixtures. CLI interceptor tests use a local mock. `TARGET_URL` stays unset so a leftover value cannot retarget them.

## SH-STOP-17 Published smoke still off

`published_install_smoke` is `NO` in the template. Running `npm install -g @vantio/cli@0.3.24` or `pip install 'vantio-agent-sdk==3.0.14'` under this packet stops at SH-STOP-01 and SH-STOP-07.

## SH-STOP-18 Provider calls

The run does not call a model endpoint. `TARGET_URL`, `VANTIO_INGEST_URL`, and `VANTIO_EXTRA_LLM_HOSTS` stay unset. `vantio status --check-registry` is opt-in network to npm and is outside the matrix. Plain `vantio status` is listed only under the default-off published smoke.

## SH-STOP-19 Interpreter mixing

Source-tree Python tests import the repository at 3.1.0. A later published 3.0.14 smoke, if a future authorization enables it, uses a separate disposable virtualenv. One interpreter holding both stops the run. The evidence names `git` and `published` as separate subjects.

## SH-STOP-20 Rollback scope

Cleanup deletes only the disposable `HOME`, the disposable `RUNNER_TEMP`, and the disposable git worktree recorded in that run’s bundle. Any other path stops the rollback. During prep, `scripts/refuse-rollback.mjs` exits 2 and deletes nothing.
