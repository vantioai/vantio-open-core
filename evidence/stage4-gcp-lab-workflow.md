# Stage 4 GCP lab workflow

Audience: INTERNAL_RESTRICTED

Ported from vantio-phantom-engine draft pull request 89, branch
`cursor/gcp-stage4-lab-51c4`, head
`7fd76a673d4ad06b9c74e8257585d716ea7305ea`.
live_enforcement is NOT_PROVEN. This file does not record a GCP run.
No VM was created or removed. The workflow was not dispatched.

The git SHA for the commands below is the HEAD named in the pull request
body. Those commands were run on the commit that contains this file.

credit balance: UNREAD

`gcloud` is not installed here. A read of
`https://cloudbilling.googleapis.com/v1/projects/vantio-lab-oct08/billingInfo`
with no credential returned HTTP 401. No credential was created.

## What this change reuses

Workload identity is not added. The caller workflow does not authenticate.
The stage 4 guest jobs run inside `.github/workflows/gcp-lab-cost-gate.yml`,
which already has:

- `GCP_LAB_PROJECT` = `vantio-lab-oct08`
- `GCP_LAB_WIF_PROVIDER` = `projects/910881070503/locations/global/workloadIdentityPools/github-actions/providers/github`
- `GCP_LAB_SERVICE_ACCOUNT` = `vantio-lab-gha@vantio-lab-oct08.iam.gserviceaccount.com`
- `environment: gcp-lab`

The caller uses
`vantioai/vantio-open-core/.github/workflows/gcp-lab-cost-gate.yml@main # oidc-trust`.
That call runs the copy of the cost-gate file on `main`. The new stage 4
jobs are in this branch's copy of that file. They run only after this
change is on `main`. This run did not read the live IAM condition and did
not change IAM, the provider, the service account, or the environment.

The Phantom Engine tree is checked out read-only with the existing secret
name `W3_LAB_PRIVATE_BUNDLE_TOKEN`, the same name
`gcp-lab-enforcement-proof.yml` already uses. The value was not read and
was not printed. No new secret was created.

The harness used in this repo is `scripts/gcp/enforcement_proof.py`.
`scripts/gcp/guest_phases.sh` and `scripts/gcp/proof_grade.py` are not in
this tree. The drive does not check out another repo for the harness, and
it does not call `enforcement_proof.run`.

## DS hold

DS-01, DS-02, and DS-03 are not in this change. Their checks were not
invented and were not fetched. The input `ds_ref` is recorded and not
cloned. `python3 scripts/lab/stage4_plan.py ds-hold` prints:

```text
DS NOT WIRED — waiting on #85 run 26
```

That command exits 0. It does not print PASS. Exit 2 is the guard for a
bad project or a missing harness, not the DS step.

## Commands

| Command | Return code |
| --- | --- |
| `python3 -m py_compile scripts/lab/stage4_plan.py scripts/lab/stage4_drive.py scripts/lab/test_stage4_plan.py` | 0 |
| `bash -n scripts/lab/stage4_guest.sh` | 0 |
| `shellcheck scripts/lab/stage4_guest.sh` (0.9.0-1) | 0 |
| `python3 -m unittest discover -s scripts/lab -q` | 0 (132 tests, no skip lines) |
| `/tmp/actionlint` on `gcp-stage4-lab.yml` and `gcp-lab-cost-gate.yml` (1.7.12) | 0 |
| `yamllint` on `gcp-stage4-lab.yml`, line-length 120, truthy and comments disabled | 0 |
| `python3 scripts/gcp/test_enforcement_proof.py -v` | 0 (23 tests) |
| `python3 scripts/gcp/test_lab_auto.py -v` | 0 (22 tests) |
| `node --test scripts/release/ws11/ws11.test.mjs` | 0 (14 tests) |
| `python3 -m unittest test_offline_deliver.OfflineDeliverTest.test_workflow_keeps_wif_and_hides_the_bundle` from `scripts/gcp` | 0 |
| secret-scan `git grep` for private-key and token shapes on the new files | 0 (`secret-scan: no matches`) |
| DS hold command below | 0 |
| negative guard below | 2 |

DS hold, from the repo root. Stdout began with
`DS NOT WIRED — waiting on #85 run 26`. It did not contain `PASS`.

```bash
DS_REF=cursor/redteam-holds-8374 python3 scripts/lab/stage4_plan.py ds-hold
```

Negative guard, from the repo root. It must not call gcloud. Stderr
contained `project`, `soak_minutes`, and `harness_entrypoint_missing`.
Stdout ended with `live_enforcement=NOT_PROVEN`.

```bash
GCP_LAB_PROJECT=other-project \
GITHUB_EVENT_NAME=workflow_dispatch \
SOAK_MINUTES=241 \
RUN_GO=run-go-ok \
HOST_NAME=labhost \
HARNESS_CANDIDATES=/tmp/stage4-no-harness \
python3 scripts/lab/stage4_drive.py guard
```

The `scripts/lab` suite also runs the existing host-evidence tests. Those
tests printed H-U rows for a fixture. That output is not a stage 4 boot.

`gcp-lab-cost-gate.yml` already failed actionlint on
`export GCP_LAB_GATE_JSON="$(cat ...)"` (shellcheck SC2155) before this
change. The assignment is now split from `export` so actionlint exits 0
on the file this change edits. The value assigned is unchanged.

## Not run

- The workflow was not dispatched. `gh workflow run` was not used.
- No VM was booted. The image names and uname strings were not checked
  on a guest. The Compute Engine image API was not called.
- `scripts/gcp/fetch_offline_debs.sh` was not executed.
- The Phantom Engine default branch was not checked out in this run.
- Pull request 85 was not modified. Run 26 was not read.

## Gap list

- No new boot, no live rows from a boot, and no instance create or delete.
- The image pins `debian-13-trixie-v20261102` /
  `6.12.116+deb13-cloud-amd64` and `ubuntu-2604-resolute-amd64-v20261107` /
  `7.0.0-1016-gcp` were not booted.
- DS checks are not wired. The hold is not a pass.
- The founder go was not supplied. An empty `run_go` fails the guard
  before a VM.
- Quinn is still a blocker for a live run. This run did not contact Quinn.
- The harness `precheck` accepts only Phantom Engine git SHA
  `864289cb2c9c4135d74233c74c6655087de3f20d`. The fetch job passes the
  default-branch tip through and does not replace that check. A mismatch
  stops before a VM. This run did not resolve that tip.
- `fetch_offline_debs.sh` fetches an Ubuntu 24.04 snapshot. Debian 13 and
  Ubuntu 26.04 may reject those packages. This run did not execute it.
- The lab network path for a guest package download was not tested.
- credit balance: UNREAD
- No tag, release, seal, or signing key was created.
