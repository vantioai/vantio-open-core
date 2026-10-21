# Private Phantom Engine access and commit constraints

Audience: INTERNAL_RESTRICTED

Producer classification: `PHANTOM_WAVE1_PACKAGING_HEALTH_PLAN_READY_FOR_COUNCIL`

Read date: 2026-09-27. Product tip: `631e435315cd780d83d3259e111893c1d0569bc3`.

## 1. Access inventory

| Surface | Result |
| --- | --- |
| GitHub contents of `vantioai/vantio-phantom-engine` `main` | Readable. Tip above. |
| Local path `/home/zach_vantio/vantio-phantom-engine` | Absent in this environment |
| Local path `/mnt/c/Users/zach_vantio/vantio-phantom-engine` | Absent in this environment |
| Open-core git credential against the private commit, branch protection, and rulesets APIs | HTTP 404 |
| Branch protection and rulesets | `NOT_READ`. A 404 from the open-core credential is an access gap. It is not evidence that `main` is unprotected |
| Commit signature verification | `NOT_READ` (same 404) |
| `vantioai/vantio-enterprise` `master` | Readable. Tip `2df2d1f2d2e5a8e65c6d3021b20b94f179e485b7` |
| `vantioai/vantio-pe-customer-docs` | Repository exists and is empty (HTTP 409 on the default branch) |
| GitHub Releases on the Phantom repo | Empty list |
| Git tags on the Phantom repo | One tag: `pre-autonomy-rebuild-v1` → `1b04914bd1d34dae586f6a1b4bb77cccf9533269` |

The tag `pre-autonomy-rebuild-v1` is not the product tip and is not chart `appVersion` `0.1.0`.

## 2. Blobs this plan relies on

| Path | Git blob | Use in this plan |
| --- | --- | --- |
| `docs/product-spec.md` | `f12c0caf7413dc061d705c8fc78ce7d2bcdc525d` | Commercial model and `kind` versus managed-cloud qualification. Dated 2026-09-20. Internal confidential. Facts used here are the status labels, not a reprint |
| `architecture_state.md` | `84d53654894180cbf351d62231f90e564504162c` | Status matrix. Header date 2026-07-01. Internal |
| `docs/operations-guide.md` | `1b973342b3bf7f6aa6cdad70de49fa6e26db0077` | Cited as `CUSTOMER_SHIPPED`. Body not copied |
| `.github/workflows/ci.yml` | `3d01161c27e886d424c4bf56e84be533d7ad872c` | Publish trigger |
| `Dockerfile` | `9afb6b621ce58cddd76a5773e1d051b7086da5af` | Floating base images and unpinned `bpf-linker` |
| `Cargo.toml` | `50af722f4eb78891122b73f4afcda6e6398ee2e9` | Workspace members |
| `rust-toolchain.toml` | `1e64b272b103fcd98fc13a4e86e5aa0e12271076` | `nightly` without a date |
| `deploy/helm/Chart.yaml` | `76c0648d4759f43e22122bfe17f8ea2856cea6bc` | Chart `0.1.1`, `appVersion` `0.1.0` |
| `deploy/helm/values.yaml` | `06f5973904af1f8c2c114d7e1a201082646e95cb` | Image tag `0.1.0`, `pullPolicy: Always` |
| `deploy/helm/templates/daemonset.yaml` | `644407445abc468a8c9dc63d596f46f2e4a8d0d7` | Probe and capability set |
| `deploy/kubernetes/daemonset.yaml` | `a245c1558037aee84ca8b58cb76a81cc5d3253e1` | Same image pin and probe path |
| `python/pe_protection_state.py` | `a1b49fe6e431cdb574f0d285f7976236945519c7` | Protection-state names |
| `docs/internal/VERIFIER_CONTRACT.md` | `4c215cb2ebdff63a85c29094adb8dfbe2bb30dc7` | Verifier result names |
| `docs/internal/TEST_EVIDENCE_MANIFEST.md` | `5d4d3ddc5d15aa754b6d6df3433e0f77559ee181` | Evidence classes for the 2026-09-20 pass |
| `docs/internal/FILE_CHANGE_MANIFEST.md` | `8afe169b74c1112eb27b991936028385ab02c110` | Customer-artifact exclusions |
| `docs/internal/remediation-register.json` | `05ce11c5640702b2ba7f69d6c63ec622180e7c37` | Finding status and action bans |
| `docs/internal/ROLLBACK_PROCEDURE.md` | `0eb754e0b08548a4d7a0f92464e568451e871686` | Remediation rollback scope |
| `docs/P0_CUSTOMER_PROTECTION_STATE.md` | `04916238c295df03e549d02d5d3419e2ff5bd574` | Pointers to enterprise-tree docs |
| `docs/enterprise/P0_INVENTORY.md` | `36efb2dd0623bdac159409b913cf8e7fdb59a4fa` | Honesty constraints |
| `docs/enterprise/CLOUD_VALIDATION_CHECKLIST.md` | `71fd275e82f5a3db8622b27b42ccfe5e87b5216e` | Managed-cloud rows still open |
| `vantio-enterprise` `scripts/cloud_platform_readiness.py` | `2b7e06901dcf2da2a97131709a215e794452545f` | Platform status enum. Not executed here |

`Cargo.lock` is present on the tip (50500 bytes in the directory listing). This plan did not hash it.

## 3. Commit constraints recorded on the product tip

The tip commit message states that the merge does not authorize GHCR publish, npm publish, PyPI publish, deploy, outbound calls, Roadmap-to-Shipped, or external proof claims. Pre-merge `main` named in that message is `816570aa7cac70a371ae8c0cb881d3eaed6ce26f`.

`docs/internal/remediation-register.json` summary on this tip:

- `production_actions_taken`: `none`
- `external_actions_taken`: `none`
- `runtime_ebpf_success_claimed`: `false`
- `pr7_remained_audit_only`: `true`
- `vantio_autonomous_enterprise_code_imported`: `false`

`docs/internal/TEST_EVIDENCE_MANIFEST.md` states that the 2026-09-20 remediation did not load, verify, or execute an eBPF program. Kernel, drop, and TLS claims in the architecture file stay `OBSERVED_FROM_REPOSITORY_EVIDENCE` from earlier sessions.

`docs/internal/ROLLBACK_PROCEDURE.md` limits its rollback to the documentation and Python changes of the remediation branch. It states that no production system was deployed by that pass.

`docs/internal/FILE_CHANGE_MANIFEST.md` excludes these paths from customer artifacts:

| Path | Classification recorded there |
| --- | --- |
| `docs/internal/*` | `INTERNAL_ONLY` |
| `docs/enterprise/FUTURE_AUTONOMY_NORTH_STAR.md` | `INTERNAL_ONLY` / `PROOF_PACK_RESTRICTED` |
| `python/pe_independent_verify.py` | `INTERNAL` |
| `scripts/demo_bypass_reconciliation.sh` | `INTERNAL` |

Finding F-09 records `docs/operations-guide.md` as `CUSTOMER_SHIPPED`.

## 4. Referenced paths that were not in the trees that were listed

`docs/P0_CUSTOMER_PROTECTION_STATE.md` points at an enterprise tree for `docs/ops/PE_FAILURE_MODE_MATRIX.md`, `PE_COMPATIBILITY_MATRIX.md`, `PE_BENCHMARK_METHODOLOGY.md`, and `PE_RECOVERY_ROLLBACK.md`.

`vantio-enterprise` `docs/ops/` at `2df2d1f2d2e5a8e65c6d3021b20b94f179e485b7` does not contain those four filenames. Helm `values.yaml` comments also point at `docs/ops/PHANTOM_ENGINE_CUSTOMER_PACK.md`, which is not in the Phantom `docs/` listing. Those files are an access-and-content gap. This plan does not invent their contents.

`docs/P0_CUSTOMER_PROTECTION_STATE.md` also names enterprise wrappers `scripts/pe_protection_state.py`, `scripts/pe_scoped_quarantine.py`, `scripts/pe_customer_pack_healthcheck.sh`, and `scripts/vantio_assure.py`. The Phantom repo `scripts/` listing contains `demo_bypass_reconciliation.sh` only. The wrappers were not read.

## 5. Cross-repo commercial constraint

Phantom `docs/product-spec.md` on this tip is the commercial source for the engine: Optics free, Phantom Engine at `$799` per enrolled node per month with Observe, Enforce, and Control in one purchase, Enterprise as talk-to-sales, Gate bundled rather than a separate invoice.

`vantio-enterprise` tip `2df2d1f2d2e5a8e65c6d3021b20b94f179e485b7` is older (2026-08-23). Its commit message still describes a four-product ladder. Remediation finding F-03 records cross-repo customer-facing cleanup as open and outside the Phantom repo. This plan does not edit that repository and does not reprint the retired ladder.

## 6. Intra-repo conflicts that later forces must keep visible

| ID | Conflict |
| --- | --- |
| `CONFLICT-CI-PUBLISH-TRIGGER` | `.github/workflows/ci.yml` pushes an image when the event is `workflow_dispatch` or the ref is `refs/tags/v*.*.*`. The `CUSTOMER_SHIPPED` operations guide says the same workflow publishes on every merge to `main`. The workflow file is the mechanism. No `v*.*.*` tag exists, so a push to `main` does not take the image job |
| `CONFLICT-ARCHITECTURE-HEADER` | `architecture_state.md` header still says `--enroll-watch` remains unverified. The status matrix later in the same file records a local `kind` watch against that file’s API server. `docs/product-spec.md` qualifies `kind` as local testing and leaves GKE/EKS/AKS as `TARGET_DESIGN` |
| `CONFLICT-REMAINING-WORK` | `docs/product-spec.md` says remaining work is cloud-account-gated. The same architecture file’s roadmap still lists an engineering residual: Kubernetes `--enroll-watch` does not auto-attach `cgroup_skb/egress` to pod cgroups |
| `CONFLICT-HEARTBEAT-PATH` | Raw DaemonSet and Helm template set `VANTIO_HEARTBEAT_PATH` to `/run/vantio/heartbeat` and probe that path. The operations guide’s troubleshooting table names a different heartbeat filename. This plan does not choose a winner by editing the private repo. P24 treats the manifests as the deploy artifact and the guide sentence as unresolved drift |
| `CONFLICT-SPANNER-ENV` | Helm omits `GOOGLE_SPANNER_*` when `spannerDatabase` is empty. The raw manifest always sets `GOOGLE_APPLICATION_CREDENTIALS` and optionally injects `GOOGLE_SPANNER_DATABASE` from `vantio-secrets` |
