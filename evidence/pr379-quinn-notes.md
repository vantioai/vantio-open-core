# PR 379 Quinn notes (offline)

Public repo note. No live dispatch, deploy, tag, publish, seal, or signing. No cloud calls.

Parent commit (branch `cursor/seal-input-fail-fast-15e7` at the start of this work): `0bb2451f4ef2636ccfc3398a764b97a7067a8b7f`.

The pull request head is the commit that adds this file on `cursor/quinn-notes-pr379-ad3e`. This file does not contain that commit id, because writing the id would change the commit.

## File hashes at the test run

sha256:

- `7498a631a0cd541e0dcb3456c3565bba50a17ea2f6bba2ebf7d5d40ff8a56115` `.github/workflows/gcp-lab-provision.yml`
- `48a619eae0b65cd223b348a8cc6d8fb845a7e4db899f308053d07659687dc77b` `scripts/lab/seal_dispatch.py`
- `878e16a2a62af49669aef6514687c2a875e7e26f2e74245f3b12c6cb5abc0768` `scripts/lab/test_seal_dispatch.py`
- `6ed5184ae1831e68286d9c57bd1534a785135401786b0d283f85f184bfb584fd` `docs/lab/seal-dispatch.md`

git blob (`git hash-object`):

- `4723eadbbfffb5f4722947aadbb8eff3e552b7a5` `.github/workflows/gcp-lab-provision.yml`
- `9536d79e34aaf9aab5eef49c7749fb28ea499b9f` `scripts/lab/seal_dispatch.py`
- `72b17793a6babcf548ad4f172927805b293ecb1d` `scripts/lab/test_seal_dispatch.py`
- `fd62e670ac2a62caaee727801f62796fdb8dd002` `docs/lab/seal-dispatch.md`

Tools: Python 3.12.3, Node v22.23.4, pnpm 11.13.0. Working directory: the repo root.

## What the tests lock

- `timed_out` jobs are fetched, including an empty step list. `startup_failure` and `neutral` are fetched when they have steps, or when the steps key is absent. Skipped jobs are not fetched.
- A failed `sealcheck` still schedules `teardown` (`if: always()`), which runs `teardown-if-present`. `fetch`, `gate`, and `deliver` stay skipped. `deliver` still requires `needs.fetch.result == 'success' && needs.gate.outputs.expected_oop_usd == '0'`. The previous `if` (`always() && needs.sealcheck.result == 'success'`) is asserted to skip teardown.
- `paste` still prints `seal=<64 hex> bundle_commit=<40 hex>` for an operator. With `GITHUB_ACTIONS=true` it prints lengths only and exits 1. The warning is `docs/lab/seal-dispatch.md`. The `sealcheck` step has no outputs and its script does not write `GITHUB_OUTPUT`, `GITHUB_STEP_SUMMARY`, or `GITHUB_ENV`.
- The `sealcheck` step env sets `LC_ALL` to `C`.

## Commands and exit codes

Each command was run from the repo root. `rc` is the process exit code. Chained commands use `&&`, so a later command ran only after the earlier one exited 0.

| Command | rc |
| --- | --- |
| `node --test docs/scripts/check-docs-release.test.mjs tests/disclosure-governance-cleanup/direct.test.mjs tests/disclosure-governance-cleanup/adversarial.test.mjs` | 0 (23 pass; this was before this evidence file existed) |
| `python3 scripts/ci/test_optics_observe_ci.py -v` | 0 (5 tests) |
| `python3 scripts/lab/test_seal_dispatch.py -v` | 0 (23 tests) |
| `node --test scripts/release/governance.test.mjs && node --test scripts/release/ws11/ws11.test.mjs && node --test scripts/release/seal-identity-recheck.test.mjs && node --test scripts/release/engine-archive-rebuild.test.mjs && node --test scripts/release/pe-canonical-seal.test.mjs` | 0 (15+14+1+3+1 pass) |
| `python3 scripts/release/test_pe_canonical_seal.py -v && python3 scripts/release/test_promote_pypi.py -v && python3 scripts/release/test_pypi_publish_workflow.py -v && python3 scripts/release/test_optics_release_observe.py -v` | 0 (5+8+19+6; one skip inside the publish workflow file) |
| `python3 scripts/aws/test_webshell_grade.py -v && python3 scripts/aws/test_verify_w3_lab_teardown.py -v && python3 scripts/aws/test_preflight_w3_lab_teardown.py -v && python3 scripts/aws/test_w3_lab_teardown_workflow.py -v && python3 scripts/aws/test_w3_lab_auto.py -v && python3 scripts/aws/test_w3_lab_steps.py -v && python3 scripts/aws/test_phase2_grade.py -v && python3 scripts/aws/test_descendant_banner.py -v && python3 scripts/aws/test_lab_oidc_trigger.py -v && python3 scripts/aws/test_w3_lab_eip.py -v` | 0 |
| `python3 scripts/lab/test_host_evidence_hu.py -v && python3 scripts/lab/test_sparse_host_evidence.py -v && python3 scripts/lab/test_hostcheck_rows.py -v` | 0 (18+1+60) |
| `python3 scripts/gcp/test_gcp_enterprise_uninstall.py -v && python3 scripts/gcp/test_lab_auto.py -v && python3 scripts/gcp/test_offline_deliver.py -v && python3 scripts/gcp/test_gcp_2d_restart.py -v && python3 scripts/gcp/test_gcp_phase_batteries.py -v && python3 scripts/gcp/test_redteam_packet.py -v && python3 scripts/gcp/test_redteam_brain.py -v` | 0 (33+22+109+40+89+11+7; one skip in offline deliver) |
| `python3 tests/planning/test_r15_lifecycle.py -v` | 0 (2) |
| `python3 -m unittest discover -s packages/vantio-agent-sdk-py/tests -t packages/vantio-agent-sdk-py -v` | 0 (126 tests, 3 skipped; Python 3.12 only) |
| `python3 -m compileall -q packages/vantio-install/vantio_install && python3 -m unittest discover -s packages/vantio-install/tests -t packages/vantio-install -v && python3 -m unittest deploy/docker/test_observe_example.py -v` | 0 (281+3) |
| `node --test internal/gap-t2-openshell/test/*.test.cjs && node internal/gap-t2-openshell/proof/prove-bypass.cjs` | 0 (36 pass). The proof rewrote `generated_at` in `internal/gap-t2-openshell/evidence/bypass-drill.json`. That rewrite was reverted and is not part of this change. |
| `python3 -m unittest discover -s tests/optics-agent-inventory -t tests/optics-agent-inventory -v` | 0 (19) |
| `python3 packages/t5-egress-kernel/tests/test_kernel_model.py -v && python3 scripts/clean-host/t5/kernel_proof.py && python3 scripts/aws/test_t5_battery.py -v && python3 scripts/gcp/test_t5_battery.py -v` | 0 (18+18+6+6). `kernel_proof` printed `result=pass compile=pass` and wrote `docs/planning/gap-t5-egress/evidence/kernel-compile.json`. That generated file was deleted and is not part of this change. |
| `pnpm --filter @vantio/cli run lint && pnpm --filter @vantio/agent-sdk run typecheck && pnpm --filter @vantio/agent-sdk run typecheck:test && pnpm --filter @vantio/cli run test && pnpm --filter @vantio/gate-mcp test && node --test packages/vantio-mcp-awareness/test/*.test.js && node packages/vantio-mcp-awareness/scripts/proof.mjs && pnpm --filter @vantio/agent-sdk run test && pnpm --filter @vantio/agent-sdk run build` | 0 (CLI 175, gate-mcp 50, mcp-awareness 36, agent-sdk 42) |

The first Node CLI test run exited 1 before `strace` was installed (`demo performs no network syscalls` and `status default performs no network syscalls` reported `ENOENT`). `strace` was installed from the OS package set and the command above was run again. That second run is the rc 0 row. No product file was changed to get there.

`python3 scripts/lab/test_seal_dispatch.py -v` was run again after the final `seal_dispatch.py` comment edit. rc=0 (23 tests). The docs command in the first row was run again with this file present. rc=0 (23 pass).

## Gap list (not run, or left for a person)

- A live `workflow_dispatch` with a 51-character seal, stopping at `sealcheck` while teardown still runs. Lab only. Not run.
- A live `workflow_dispatch` with a good 64-character lowercase seal, reaching check-dispatch. Lab only. Not run.
- Operator use of `paste` and `check-pasted` on a lab host. Offline only. `paste` with `GITHUB_ACTIONS=true` is unit-tested and does not print the seal.
- `schedule()` in `scripts/lab/test_seal_dispatch.py` evaluates the workflow `if` strings locally. It is not a GitHub-hosted run, so `if: always()` was not observed on a runner.
- `teardown-if-present` deletes the VM named for this run id. It does not delete a VM from an earlier run id. `gcp-lab-sweeper.yml` is the cross-run backstop. `sweeper_enabled` ships false, so that sweeper records `would_delete` and does not delete. Turning that on is a human decision.
- `sealcheck` has no Require main step. It holds no cloud credentials. Fetch and teardown still require main before they authenticate. Quinn f5 asked for no code change.
- `w3-lab-auto-arm.yml` still treats an empty seal as the pinned digest. Unchanged. Out of scope (Quinn f6).
- Fetch and deliver still pass `inputs.seal` through `EXPECTED_SEAL` and `W3_EXPECTED_SEAL`. Fetch still publishes job output `seal_sha256`. Those lines were not changed. Actions step debug on a later step can still print that step's environment. `sealcheck` does not write the seal. Leave `ACTIONS_STEP_DEBUG` off for this workflow. The step does not mask the input.
- Python SDK tests ran on 3.12 only. Python 3.10 and 3.11 are not installed in this workspace.
- The Optics observe lab steps in CI (registry install of the CLI and `vantio run`) were not run.
