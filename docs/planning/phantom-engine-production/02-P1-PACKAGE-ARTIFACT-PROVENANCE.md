# P1 — package and artifact provenance

Audience: INTERNAL_RESTRICTED

Producer classification: `PHANTOM_WAVE1_PACKAGING_HEALTH_PLAN_READY_FOR_COUNCIL`

Status of this design: `PLAN_ONLY`. No image is built, pulled, or pushed here.

## 1. Artifact set on the product tip

The shipped runtime artifact is one binary. `vantio-loader/build.rs` compiles the eBPF crate, patches ELF OSABI (`e_ident[7]`), and `include_bytes!` embeds the object. The image does not ship a separate `.o`. Provenance that hashes only the compiler’s pre-patch object misses the bytes the loader actually contains.

| Artifact | Identity on tip `631e435315cd780d83d3259e111893c1d0569bc3` |
| --- | --- |
| Git tip | `631e435315cd780d83d3259e111893c1d0569bc3` |
| Chart | `deploy/helm/Chart.yaml` version `0.1.1`, `appVersion` `0.1.0` |
| Helm image | `ghcr.io/vantioai/vantio-phantom-engine` tag `0.1.0`, `pullPolicy: Always` |
| Raw DaemonSet image | `ghcr.io/vantioai/vantio-phantom-engine:0.1.0`, `imagePullPolicy: Always` |
| CI tags, when the image job runs | `ghcr.io/vantioai/vantio-phantom-engine:latest` and `ghcr.io/vantioai/vantio-phantom-engine:${{ github.sha }}` |
| CI image-job condition | `workflow_dispatch` or tag ref `refs/tags/v*.*.*` |
| Git tag that exists | `pre-autonomy-rebuild-v1` → `1b04914bd1d34dae586f6a1b4bb77cccf9533269` |
| GitHub Release | none listed |
| `v*.*.*` tag | none listed |

The chart pin `0.1.0` is not a tag the workflow file writes. The workflow writes `:latest` and a full git SHA. Whether `ghcr.io/vantioai/vantio-phantom-engine:0.1.0` exists in the registry is `UNVERIFIED`. This force did not query GHCR.

The tip merge message withholds authorization to publish to GHCR. The workflow file can still publish on a `v*.*.*` tag or a manual dispatch. Those are different facts. A future publish needs a commit whose message grants it. This plan does not grant it.

## 2. Build inputs that are not pinned

| Input | Recorded value | Provenance gap |
| --- | --- | --- |
| Rust channel | `rust-toolchain.toml` `channel = "nightly"` plus `rust-src` and `clippy` | No date, no commit |
| Dockerfile builder | `rust:1-bookworm` | Floating tag |
| Dockerfile runtime | `debian:bookworm-slim` plus `ca-certificates` and `curl` | Floating tag |
| `bpf-linker` | `cargo binstall --no-confirm bpf-linker` in CI and in the Dockerfile | No version |
| `cargo-binstall` installer | `https://raw.githubusercontent.com/cargo-bins/cargo-binstall/main/install-from-binstall-release.sh` | `main` branch of the installer |
| Crate graph | `Cargo.lock` present | Lockfile exists; toolchain and linker above sit outside it |
| eBPF object | Embedded after the OSABI patch | Digest of the post-patch bytes is not a published field |

`Cargo.toml` default members are `vantio-common`, `vantio-loader`, and `test_load`. The eBPF crate `vantio-phantom-engine` is excluded from a host `cargo check`. A provenance record has to name both the host binary and the embedded `bpfel` object.

The workflow does not set a `provenance` or `sbom` key on `docker/build-push-action`. This plan does not infer what the action’s default emitted on a past run. No past run was inspected.

Open-core has `.github/workflows/enterprise-slsa-provenance.yml` for open-core release artifacts. That workflow is not a Phantom image attestation. This plan does not attach it to GHCR.

## 3. Provenance contract for a later authorized force

A later force may implement this only after a council pass and a commit that authorizes publish. This document does not authorize that force.

Required fields on any future Phantom artifact record:

| Field | Rule |
| --- | --- |
| `git_sha` | Full tip that produced the bits |
| `image_digest` | Registry digest. A tag is a lookup hint |
| `chart_version` | Helm chart version that renders the digest |
| `app_version` | Equal to the tag the workflow actually pushed, or omitted when the record uses a digest only |
| `embedded_ebpf_sha256` | Hash of the post-OSABI-patch object inside the binary |
| `rust_toolchain` | Dated nightly, not the floating channel name alone |
| `bpf_linker_version` | The binstall crate version that ran |
| `base_image_digests` | Builder and runtime bases by digest |
| `publish_authorization` | Commit SHA whose message grants GHCR publish. Absent means the artifact is a local build record only |
| `distribution` | `PRIVATE`. Customer manual bytes stay out of this public repository |

Prohibited as a production pin:

- Tag `latest`
- `imagePullPolicy: Always` on a tag that is not paired with a digest
- Treating chart `0.1.0` as the same object as CI’s `${{ github.sha }}` tag without a digest comparison

`pullPolicy: Always` on tag `0.1.0` can move bytes under a constant tag. P1 treats that tag as mutable until a digest pin exists.

## 4. Customer bundle

Open-core governance already marks a Phantom customer bundle `public_distribution: false`. This P1 record is an internal planning contract. It is not a customer bundle, and it does not add a manual path.

`python/pe_customer_pack.py` exists on the private tip (30149 bytes). This plan did not execute it and does not copy it.

## 5. Rollback of a future artifact

`docs/internal/ROLLBACK_PROCEDURE.md` rolls back the 2026-09-20 documentation remediation. It is not an image rollback. A future image rollback is: stop using the digest, return the chart to the previous digest, and leave `latest` unpublished. That procedure is not implemented here.
