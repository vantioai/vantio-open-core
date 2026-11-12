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
`scripts/gcp/guest_phases.sh` and `scripts/gcp/proof_grade.py` are not
required and are not in this tree. The drive calls `phases_for("full")`
and `phase_accepted`. It does not call `run_proof`, because that function
creates its own VM. There is no 31-phase count. `PE_GIT_SHA` passed into
`precheck` is that module's constant
`864289cb2c9c4135d74233c74c6655087de3f20d`. The fetch job checks out that
commit and `scripts/gcp/build_pe_loader.sh` builds the loader on the
runner. The guest script has no `apt-get` and no `rustup`. A non-empty
`HARNESS_REF` is rejected. The allowlist is the empty ref, which means
this repo's checkout.

`lab_auto.WORKFLOWS` was not changed. It still names seven workflow files.
`gcp-stage4-lab.yml` is not one of them. The auth action stays inside
`gcp-lab-cost-gate.yml`, which is already in that tuple. The one line that
was not added, and is a decision for Zach only if he rejects this fit, is
a new entry `"gcp-stage4-lab.yml",` in `scripts/gcp/lab_auto.py`
`WORKFLOWS`. This change does not add it.

The `gcp-lab` environment's required-reviewer list was not changed. V136
read that list as empty. Adding required reviewers on the create job, and
leaving teardown able to delete without a second wait, is a settings
decision for Zach. This run did not change environment settings.

The typed `run_go` string is a length check. It is not a go. An empty
event name fails the guard. The caller `on:` block is still only
`workflow_dispatch`. The jobs inside the cost-gate file also accept
`workflow_call`, because that is the event name of a reusable call.

Before create, the drive runs `gcloud compute images describe` for the
pinned image name and does not create if that command fails or returns a
different name. This run did not call that API. The boot disk is 10 GB
`pd-standard`, with `--boot-disk-labels` set to the same two labels.
Verify also lists the disk names `s4-<run id>-deb`, `s4-<run id>-ubu`,
and `s4-<run id>-off`. The guest GRUB drop-in puts `lsm=` last on
`GRUB_CMDLINE_LINUX_DEFAULT`, and the second preflight compares
`/proc/cmdline`. Neither image was booted, so the observed `uname -r`
is still unknown.

The caller concurrency group is `gcp-stage4-lab`, so a second dispatch
waits. It does not reuse the cost-gate group name, because the caller
holds its group while the reusable workflow runs. No price figure is
recorded here. credit balance: UNREAD

The shell step that refuses a caller-supplied key file stays before the
auth step. After auth, `STAGE4_AFTER_AUTH=1` and the drive does not treat
`GOOGLE_APPLICATION_CREDENTIALS` or
`CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE` as a static key. Those are the
two paths that auth action exports. `GCP_SA_KEY` still fails.

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
| `python3 -m unittest discover -s scripts/lab -q` | 0 (139 tests, no skip lines) |
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
- The pinned Phantom Engine commit was not checked out in this run.
  The workflow's fetch job is the step that would check it out.
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
  `864289cb2c9c4135d74233c74c6655087de3f20d`. The drive passes that
  constant. A different supplied value fails before create. This run did
  not check out that commit and did not build the loader.
- The image describe step was not executed. A wrong or missing image name
  fails closed in the unit test. That does not prove the image exists.
- The GRUB `lsm=` order was checked by sourcing the drop-in in bash. It
  was not checked on a booted guest. The catalog `uname -r` strings were
  not observed on a guest.
- `fetch_offline_debs.sh` fetches an Ubuntu 24.04 snapshot. Debian 13 and
  Ubuntu 26.04 may reject those packages. This run did not execute it.
- The lab network path for a guest package download was not tested.
- credit balance: UNREAD
- No tag, release, seal, or signing key was created.
