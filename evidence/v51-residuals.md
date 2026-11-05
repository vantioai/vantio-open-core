# V51 workflow residuals (offline)

Public repo note. No live dispatch, deploy, tag, publish, seal, or signing. No cloud calls. No secrets.

Parent commit on `cursor/quinn-notes-pr379-ad3e`: `1b4aa0a6f0bf54dc9614f2ff62f862621a960cab`.

This branch is `cursor/v51-workflow-residuals-8c2a`. The pull request head is the commit that adds this file. This file does not contain that commit id, because writing the id would change the commit.

## What changed

- `sealcheck` in `.github/workflows/gcp-lab-provision.yml` runs `Require main on vantio-open-core` before it reads the seal. The step is the same four checks `fetch` and `teardown` run before they authenticate. The job still has no cloud credentials. A failed guard fails the job. `fetch`, `gate`, and `deliver` stay skipped. `teardown` still runs because its `if` is `always()`.
- `.github/workflows/w3-lab-auto-arm.yml` rejects an empty, short, or non-64-lowercase-hex seal in `Check the seal input` before checkout and before any arm step. Failure prints `seal_len=<n> result=fail` and does not write the value. `Read the canonical seal` does not substitute `lane_seal.sha256` for an empty input. An empty public pin still uses `public_pin.archive_sha256`.
- `fetch` and `deliver` register `::add-mask::` in `Mask the seal input`, the first step in that job whose environment contains `inputs.seal`. The limit is `docs/lab/seal-dispatch.md`: the runner writes that step's environment before the script, a mask does not cross jobs, and `seal_sha256` stays a job output. `sealcheck` does not call `::add-mask::`, because the check step holds `SEAL` and has no later step.
- `scripts/gcp/lab_capabilities.json` still has `sweeper_enabled` false. This change does not arm the scheduled sweeper. Arming that flag is a human call. A person has to set it. This run did not.

## File hashes at the test run

sha256:

- `d3bde0f5904731a61f7ed78ddd200be7250abe0292ca4ef941c9b40a404812fa` `.github/workflows/gcp-lab-provision.yml`
- `84cb92096aeb33956d50922641baa90f7cee60d050f36e5fb2414b9d083b56e9` `.github/workflows/w3-lab-auto-arm.yml`
- `9d45b811c4078d7775d4ee7df6c6f6b2d7267f4cfc74fb8d17af301579218d4f` `scripts/lab/test_seal_dispatch.py`
- `8c4e39bc1dd869d4e35f33a7cb9fb6cee0f6f3425ed74b68c865112a331baebb` `scripts/ci/test_optics_observe_ci.py`
- `378fc37c15afa9f7af9f689e1662ce8e103b5089c229b02b6022237a56608f64` `docs/lab/seal-dispatch.md`
- `af3ab7074185e1222ed7efe2d4c930a220aae912babd365888b8393ee2711b26` `scripts/gcp/lab_capabilities.json` (unchanged; `sweeper_enabled` is false)

git blob (`git hash-object`):

- `fd3cad645dfdbbd5d1bb3125c2aa93084d3c20bb` `.github/workflows/gcp-lab-provision.yml`
- `dd0a7422f9680ecad4bb5dba5e3904ed0c2cbf9f` `.github/workflows/w3-lab-auto-arm.yml`
- `d18c92a4a776a0e33f4c20220ba4a5995320a2d8` `scripts/lab/test_seal_dispatch.py`
- `1eee33bf566a8584c0839c909351efa605cc3af5` `scripts/ci/test_optics_observe_ci.py`
- `a183e573223c4b3326bbbc24e6a55fc349ee1519` `docs/lab/seal-dispatch.md`
- `5d90c96dfdee368f7c42e3cb5bbb9dd85b54a189` `scripts/gcp/lab_capabilities.json`

Tools: Python 3.12.3, Node v22.23.4, pnpm 11.13.0, strace 6.8, jq 1.7 (the arm canonical step uses jq). Working directory: the repo root.

## Commands and exit codes

Each command was run from the repo root. `rc` is the process exit code. Chained commands use `&&`, so a later command ran only after the earlier one exited 0.

`strace` 6.8 was installed from the OS package set before the Node command. The Node command was not run before that install.

`pnpm install --frozen-lockfile` was run with `COREPACK_ENABLE_DOWNLOAD_PROMPT=0` before the Node command. rc=0. An earlier install stopped at the corepack download prompt and was cancelled. It did not change product files.

| Command | rc |
| --- | --- |
| `node --test docs/scripts/check-docs-release.test.mjs tests/disclosure-governance-cleanup/direct.test.mjs tests/disclosure-governance-cleanup/adversarial.test.mjs` | 0 (23 pass; this was before this evidence file existed) |
| `python3 scripts/lab/test_seal_dispatch.py -v` | 0 (31 tests) |
| `python3 scripts/ci/test_optics_observe_ci.py -v` | 0 (5 tests) |
| `node --test scripts/release/governance.test.mjs && node --test scripts/release/ws11/ws11.test.mjs && node --test scripts/release/seal-identity-recheck.test.mjs && node --test scripts/release/engine-archive-rebuild.test.mjs && node --test scripts/release/pe-canonical-seal.test.mjs` | 0 (15+14+1+3+1 pass) |
| `python3 scripts/release/test_pe_canonical_seal.py -v && python3 scripts/release/test_promote_pypi.py -v && python3 scripts/release/test_pypi_publish_workflow.py -v && python3 scripts/release/test_optics_release_observe.py -v` | 0 (5+8+19+6; one skip inside the publish workflow file) |
| `python3 scripts/aws/test_webshell_grade.py -v && python3 scripts/aws/test_verify_w3_lab_teardown.py -v && python3 scripts/aws/test_preflight_w3_lab_teardown.py -v && python3 scripts/aws/test_w3_lab_teardown_workflow.py -v && python3 scripts/aws/test_w3_lab_auto.py -v && python3 scripts/aws/test_w3_lab_steps.py -v && python3 scripts/aws/test_phase2_grade.py -v && python3 scripts/aws/test_descendant_banner.py -v && python3 scripts/aws/test_lab_oidc_trigger.py -v && python3 scripts/aws/test_w3_lab_eip.py -v` | 0 (8+51+11+5+33+114+125+8+11+5; one skip in phase2 for a local netns) |
| `python3 scripts/lab/test_host_evidence_hu.py -v && python3 scripts/lab/test_sparse_host_evidence.py -v && python3 scripts/lab/test_hostcheck_rows.py -v` | 0 (18+1+60) |
| `python3 scripts/gcp/test_gcp_enterprise_uninstall.py -v && python3 scripts/gcp/test_lab_auto.py -v && python3 scripts/gcp/test_offline_deliver.py -v && python3 scripts/gcp/test_gcp_2d_restart.py -v && python3 scripts/gcp/test_gcp_phase_batteries.py -v && python3 scripts/gcp/test_redteam_packet.py -v && python3 scripts/gcp/test_redteam_brain.py -v` | 0 (33+22+109+40+89+11+7; one skip in offline deliver) |
| `python3 tests/planning/test_r15_lifecycle.py -v` | 0 (2) |
| `python3 -m unittest discover -s packages/vantio-agent-sdk-py/tests -t packages/vantio-agent-sdk-py -v` | 0 (126 tests, 14 skipped; Python 3.12 only; the skips are optional HTTP clients that are not installed here) |
| `python3 -m compileall -q packages/vantio-install/vantio_install && python3 -m unittest discover -s packages/vantio-install/tests -t packages/vantio-install -v && python3 -m unittest deploy/docker/test_observe_example.py -v` | 0 (281+3) |
| `node --test internal/gap-t2-openshell/test/*.test.cjs && node internal/gap-t2-openshell/proof/prove-bypass.cjs` | 0 (36 pass). The proof rewrote `generated_at` in `internal/gap-t2-openshell/evidence/bypass-drill.json`. That rewrite was reverted and is not part of this change. |
| `python3 -m unittest discover -s tests/optics-agent-inventory -t tests/optics-agent-inventory -v` | 0 (19) |
| `python3 packages/t5-egress-kernel/tests/test_kernel_model.py -v && python3 scripts/clean-host/t5/kernel_proof.py && python3 scripts/aws/test_t5_battery.py -v && python3 scripts/gcp/test_t5_battery.py -v` | 0 (18+18+6+6). `kernel_proof` printed `result=pass compile=pass` and wrote `docs/planning/gap-t5-egress/evidence/kernel-compile.json`. That generated file was deleted and is not part of this change. |
| `pnpm --filter @vantio/cli run lint && pnpm --filter @vantio/agent-sdk run typecheck && pnpm --filter @vantio/agent-sdk run typecheck:test && pnpm --filter @vantio/cli run test && pnpm --filter @vantio/gate-mcp test && node --test packages/vantio-mcp-awareness/test/*.test.js && node packages/vantio-mcp-awareness/scripts/proof.mjs && pnpm --filter @vantio/agent-sdk run test && pnpm --filter @vantio/agent-sdk run build` | 0 (CLI 175, gate-mcp 50, mcp-awareness 36, agent-sdk 42; the awareness proof reported `assertions=26 failed=0`) |

The docs command in the first row was run again with this file present. rc=0 (23 pass).

## Pass criteria covered here

- Require main: `RequireMainGuard` in `scripts/lab/test_seal_dispatch.py` runs the shell guard and the same job-`if` model as the teardown sweep. A non-main ref fails the guard in `sealcheck`, `fetch`, `deliver`, and `teardown`. A failed `sealcheck` still schedules teardown.
- Arm seal: `ArmSealReject` runs the check script on empty, 51-character, non-hex, and valid inputs. The Actions-log model keeps lengths only. The canonical step rejects the same bad inputs and does not print the lane digest.
- Mask: `SealLogMask` checks that `fetch` and `deliver` mask before later steps, that a later line is redacted, and that a line emitted before the command is not. The same limit is written in `docs/lab/seal-dispatch.md`.
- Sweeper: `SweeperStaysDisarmed` reads `sweeper_enabled` and expects false. `scripts/gcp/test_lab_auto.py` also expects false. The flag was not edited.

## Gap list (not run, or left for a person)

- A live `workflow_dispatch` of `gcp-lab-provision.yml` from a ref other than `refs/heads/main`. The Require main step should fail `sealcheck` before the seal script. Lab only. Not run.
- A live `workflow_dispatch` on `main` with a 51-character seal. Require main passes, the length check fails, and teardown still runs. Lab only. Not run.
- A live `workflow_dispatch` on `main` with a 64-character lowercase seal, reaching check-dispatch. Lab only. Not run.
- A live `workflow_dispatch` of `w3-lab-auto-arm.yml` with an empty seal, a short seal, a non-hex seal, and a valid seal. The bad values should fail before checkout and before AssumeRole. Not run. No cloud spend.
- `ACTIONS_STEP_DEBUG=true` on a runner. The offline model is not the GitHub runner. It does not show whether `Set up job` prints workflow inputs before the first user step. `docs/lab/seal-dispatch.md` says that diagnostic cannot be masked from inside a step, and this run did not observe it.
- Fetch job output `seal_sha256`, the arm step output `seal`, and the workflow input remain on the run. `::add-mask::` redacts later log text on that runner. It does not remove those outputs. Not observed on a runner.
- `teardown-if-present` deletes the VM named for this run id. It does not delete a VM from an earlier run id. `gcp-lab-sweeper.yml` is the cross-run backstop. `sweeper_enabled` stays false, so that sweeper records `would_delete` and does not delete. Turning that flag on is a human call. This change does not arm it.
- Python SDK tests ran on 3.12 only. Python 3.10 and 3.11 are not installed in this workspace. Fourteen SDK tests skipped because optional HTTP clients are not installed.
- The Optics observe lab steps in CI (registry install of the CLI and `vantio run`) were not run.
