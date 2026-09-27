# Evidence requirements

Audience: INTERNAL_RESTRICTED

Evidence tiers named in `docs/architecture/optics-foundation/09-IMPLEMENTATION-GATES.md` and `docs/planning/optics-foundation-a8/05-TEST-AND-EVIDENCE-STRATEGY.md` are `UNIT_PROVED`, `INTEGRATION_PROVED`, `STRANGER_HOST_PROVED`, `PROVED_EXTERNAL`, and `CUSTOMER_VALIDATED`.

This packet assigns none of them. `PACKET-MANIFEST.json` records `evidence_tiers_assigned` as an empty array. A later execution of the runbook still writes the tier as `UNSET`. Assigning `STRANGER_HOST_PROVED` is a separate act on a recorded bundle, by a reviewer who can show the host was not the producer’s. `PROVED_EXTERNAL` is an independent verifier on the exact source tip. `CUSTOMER_VALIDATED` is a customer workload and window. A customer host is forbidden for this force.

## Three evidence classes

| Class | What it can show | Produced by this prep |
| --- | --- | --- |
| Prep integrity | The packet files match the manifest, the authorization template is unfilled, and both refuse scripts exit 2 | Yes. The verifier stdout is the record |
| Stranger-host command evidence | The CI parity commands from `.github/workflows/ci.yml` ran on a Founder-named host outside the producer environment, with transcripts | No |
| Independent review and customer validation | Another reviewer, then a customer workload | No |

A green producer run, including GitHub-hosted runners for this repository and this cloud agent, is producer evidence. It is the wrong class for `STRANGER_HOST_PROVED`.

## Prep record

Command:

```bash
node docs/planning/stranger-host-gate/scripts/verify-packet-prep.mjs
```

Pass condition: exit 0 and stdout exactly `STRANGER_HOST_PACKET_READY_AWAITING_EXECUTION_AUTH`.

The verifier also requires the prepared main SHA `5064f32f1cdfcb840dfd100e2ce5c712d046550d` to be an ancestor of `HEAD`, and every dirty or untracked path to stay under `docs/planning/stranger-host-gate/`.

## Later bundle

A later authorized run writes the bundle only under the disposable directory it records. This prep creates none of these files.

```
<disposable HOME>/stranger-host-evidence/<run-id>/
  host.txt
  git-sha.txt
  versions.txt
  env-posture.txt
  commands.tsv
  results/<step-name>.exit
  results/<step-name>.log
  secret-scan.txt
  tier.txt
```

| File | Required contents |
| --- | --- |
| `host.txt` | Owner, OS from `uname -srm`, and a statement of why this machine is outside the producer environment (this agent, the author workstation, and GitHub-hosted runners for this repository). Customer host: forbidden. |
| `git-sha.txt` | `git rev-parse HEAD`, equal to the Founder-locked SHA. `git status --porcelain` empty before the run. |
| `versions.txt` | `node --version` (CI uses Node 22), `pnpm --version` matching `package.json` `packageManager`, each Python `3.10` / `3.11` / `3.12`, and `strace` available on `PATH`. |
| `env-posture.txt` | Presence or absence only, never values, for `VANTIO_TELEMETRY_DISABLED`, `DO_NOT_TRACK`, `VANTIO_TELEMETRY`, `VANTIO_API_KEY`, `VANTIO_INGEST_URL`, `VANTIO_EXTRA_LLM_HOSTS`, `TARGET_URL`, `NPM_TOKEN`, `PYPI_TOKEN`, `TWINE_USERNAME`, `TWINE_PASSWORD`, and `NODE_AUTH_TOKEN`. Required posture: the two disable variables present and set to `1`; every other name absent. |
| `commands.tsv` | Step name, working directory, argv, exit code. One row per command in the runbook matrix that actually ran. |
| `results/*.log` | Combined stdout and stderr for that step. |
| `secret-scan.txt` | A scan of the bundle for private-key headers and token prefixes. A hit stops the run and the bundle is deleted under the rollback rules. |
| `tier.txt` | The single word `UNSET`. |

## What a later green run is allowed to support

| Observation | Allowed statement | Still unset |
| --- | --- | --- |
| Source-tree CI parity exits 0 on the named Linux host | These commands passed on that host at that SHA | `STRANGER_HOST_PROVED` until a separate review accepts the bundle. `PROVED_EXTERNAL`. `CUSTOMER_VALIDATED` |
| Python unittest exits 0 from `packages/vantio-agent-sdk-py` | Repository Python 3.1.0 passed on that interpreter. The suite calls `shield()`; `send_run_telemetry_once` follows SH-STOP-08 | Behavior of published 3.0.14. A live telemetry send |
| `npm pack` and `python3 -m build` exit 0 | Local candidate archives were produced in the disposable directory | A publish, a tag, or a release |
| CLI tests exit 0 | The in-repo tests, including local `127.0.0.1` mocks and the `strace` checks, passed | A live provider call. Coverage of paths listed as unobserved in `docs/products/optics/SUPPORTED-PATHS.md` |

## What the bundle must keep out

Customer prompts, completions, private keys, registry tokens, and `VANTIO_API_KEY`. Provider hostnames and synthetic canaries in CI logs are fixtures from the suite. Optics run files written by tests belong under the disposable `HOME` and are deleted with that directory. They are not customer evidence.

## Published pins

`docs/products/optics/INSTALLATION.md` and `docs/products/optics/UPGRADE-ROLLBACK-UNINSTALL.md` record `@vantio/cli@0.3.24` and `vantio-agent-sdk==3.0.14` as the published packages observed on 2026-09-27. This prep did not repeat that query. If a later force turns `published_install_smoke` on, that force records a fresh registry observation and stops when the resolved version differs from the pin written in its authorization. The smoke uses a separate virtualenv from the 3.1.0 source tests. Its evidence file names the package under test as `published`, separate from `git-sha.txt`.
