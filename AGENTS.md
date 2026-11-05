# Agent guide

This file is the working map for agents in `vantio-open-core`. Product and toolchain rules stay in [`.cursor/rules/vantio-engineering.mdc`](.cursor/rules/vantio-engineering.mdc). Do not delete or replace that file. Contributor commands also live in [CONTRIBUTING.md](CONTRIBUTING.md). CI commands live in [`.github/workflows/ci.yml`](.github/workflows/ci.yml). Read that workflow. Edit it only when the task is that workflow.

No `environment.json` is committed here. Use the install commands below. CI uses Node.js 22. The pnpm version is the `packageManager` field in `package.json`. The verification that added this file used Node.js v22.23.4, pnpm 11.13.0, and Python 3.12.3. CI also runs the Python SDK on 3.10 and 3.11. Those two interpreters were not used in that verification.

## Repo map

| Path | What it is |
| --- | --- |
| `packages/vantio-cli` | Optics CLI, `@vantio/cli` |
| `packages/vantio-agent-sdk` | Node SDK, `@vantio/agent-sdk` |
| `packages/vantio-agent-sdk-py` | Python SDK, `vantio-agent-sdk` |
| `packages/vantio-gate-mcp` | Compatibility package `@vantio/gate-mcp` |
| `packages/vantio-mcp-awareness` | MCP observation fixtures |
| `packages/vantio-install` | Installer sources. Agents do not publish it. |
| `extensions/vantio-optics` | Editor extension |
| `packages/` | Other packages are libraries with fixtures. Tests sit in the package or under `tests/`. |
| `scripts/lab` | Host-evidence checks and their offline tests |
| `scripts/aws`, `scripts/gcp` | Lab harness modules and offline tests |
| `scripts/release` | Release-gate checks and offline tests |
| `docs/` | Documentation. A new `.md` file is part of the legacy-name scan in `docs/governance/MANIFEST.json`. |
| `.cursor/rules/` | Always-on agent rules. Add a scoped file. Leave existing files in place. |

## Install

```bash
pnpm install --frozen-lockfile
```

CLI tests call `strace`. CI installs it before those tests:

```bash
sudo apt-get update && sudo apt-get install -y strace
```

Lab-harness and release-gate tests that import YAML, and the installer hash pin:

```bash
python3 -m pip install --disable-pip-version-check 'pyyaml==6.0.1'
python3 -m pip install --require-hashes --disable-pip-version-check -r packages/vantio-install/requirements/dev-hashes.txt
```

Python SDK observe tests use these clients. The SDK itself has no install dependencies:

```bash
python3 -m pip install --disable-pip-version-check requests httpx aiohttp urllib3
```

## Tests

Run these from the repository root after install.

```bash
pnpm --filter @vantio/cli run lint
pnpm --filter @vantio/cli run test
pnpm --filter @vantio/agent-sdk run typecheck
pnpm --filter @vantio/agent-sdk run typecheck:test
pnpm --filter @vantio/agent-sdk run test
pnpm --filter @vantio/agent-sdk run build
pnpm --filter @vantio/gate-mcp test
node --test packages/vantio-mcp-awareness/test/*.test.js
node packages/vantio-mcp-awareness/scripts/proof.mjs
python3 -m unittest discover -s tests -t . -v
```

The last command runs with the working directory `packages/vantio-agent-sdk-py`.

Installer fixtures, from `packages/vantio-install`:

```bash
python3 -m compileall -q vantio_install
python3 -m unittest discover -s tests -t . -v
```

More offline suites from the repository root:

```bash
python3 -m unittest deploy/docker/test_observe_example.py -v
node --test internal/gap-t2-openshell/test/*.test.cjs
python3 -m unittest discover -s tests/optics-agent-inventory -t tests/optics-agent-inventory -v
python3 packages/t5-egress-kernel/tests/test_kernel_model.py -v
python3 scripts/aws/test_t5_battery.py -v
python3 scripts/gcp/test_t5_battery.py -v
```

Documentation release check:

```bash
node docs/scripts/check-docs-release.mjs
node --test docs/scripts/check-docs-release.test.mjs tests/disclosure-governance-cleanup/direct.test.mjs tests/disclosure-governance-cleanup/adversarial.test.mjs
```

## Lab harness, offline

These tests use fixtures and fake runners. They do not need cloud credentials. Run them with no cloud credentials in the environment. Do not dispatch a workflow to exercise them.

```bash
python3 scripts/aws/test_webshell_grade.py -v
python3 scripts/aws/test_verify_w3_lab_teardown.py -v
python3 scripts/aws/test_preflight_w3_lab_teardown.py -v
python3 scripts/aws/test_w3_lab_teardown_workflow.py -v
python3 scripts/aws/test_w3_lab_auto.py -v
python3 scripts/aws/test_w3_lab_steps.py -v
python3 scripts/lab/test_host_evidence_hu.py -v
python3 scripts/lab/test_sparse_host_evidence.py -v
python3 scripts/lab/test_hostcheck_rows.py -v
python3 scripts/gcp/test_gcp_enterprise_uninstall.py -v
python3 scripts/aws/test_phase2_grade.py -v
python3 scripts/aws/test_descendant_banner.py -v
python3 scripts/aws/test_lab_oidc_trigger.py -v
python3 scripts/aws/test_w3_lab_eip.py -v
python3 scripts/gcp/test_lab_auto.py -v
python3 scripts/gcp/test_offline_deliver.py -v
python3 scripts/gcp/test_gcp_2d_restart.py -v
python3 scripts/gcp/test_gcp_phase_batteries.py -v
python3 scripts/gcp/test_redteam_packet.py -v
python3 scripts/gcp/test_redteam_brain.py -v
python3 tests/planning/test_r15_lifecycle.py -v
python3 scripts/ci/test_optics_observe_ci.py -v
python3 scripts/release/test_pe_canonical_seal.py -v
python3 scripts/release/test_promote_pypi.py -v
python3 scripts/release/test_pypi_publish_workflow.py -v
python3 scripts/release/test_optics_release_observe.py -v
node --test scripts/release/governance.test.mjs
node --test scripts/release/ws11/ws11.test.mjs
node --test scripts/release/seal-identity-recheck.test.mjs
node --test scripts/release/engine-archive-rebuild.test.mjs
node --test scripts/release/pe-canonical-seal.test.mjs
```

The T5 model test compiles the program with `clang` and does not load it. `python3 scripts/clean-host/t5/kernel_proof.py` writes a planning evidence file, so it is not part of the command list above. The `gcc` link of `scripts/clean-host/t5/t5_load.c` in the `test-t5-kernel` job needs `libbpf` and was not run in the verification that added this file. `internal/gap-t2-openshell/proof/prove-bypass.cjs` writes an evidence file under that package and was not run.

A zero exit can include skipped tests. Record the skip lines. An exit of 0 does not prove a skipped case.

## Definition of done

A task is done when all of the following hold:

1. The diff is one scope, and the pull request stays a draft. It is not merged, and the branch is not pushed to `main`.
2. Existing tests for that scope have been run. A new guard has offline tests with a negative case and a mutation case, and those tests do not use the network or cloud credentials.
3. The pull request body lists each command, its exit code, the git SHA, and a gap list of what only a real lab host can prove.
4. The body states only what those commands and logs prove.
5. The change does not print or store secret values, and it does not dispatch a cloud workflow, create a tag, publish, or deploy.

The Lab evidence section of `.cursor/rules/vantio-engineering.mdc` is the ceiling for host claims. An offline pass does not prove a new boot, live rows from that boot, or that a cloud instance was created or removed.
