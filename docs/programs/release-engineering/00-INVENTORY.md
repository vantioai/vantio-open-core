# WS11 inventory

Audience: INTERNAL_RESTRICTED

Base commit: `89f95099d0dce463307eb75d78e7fcf2ef99feb2`

Producer classification: `WS11_RELEASE_ENGINEERING_READY_FOR_COUNCIL`

This inventory is the tree this force read. The machine-readable copy is `generated/pin-report.json`. A later edit that changes a pin, a hash, or a workflow trigger fails `scripts/release/ws11/ws11.test.mjs` until the generated files are emitted again.

## Surfaces

| Surface | Where this force looked | Distribution in the dossier |
| --- | --- | --- |
| Optics public packages and private source packages | `docs/governance/VERSION-METADATA.json`, package manifests, `scripts/release/`, `.github/workflows/` | `mixed` |
| Phantom Engine | `docs/planning/phantom-engine-production/02-P1-PACKAGE-ARTIFACT-PROVENANCE.md` | `private` |
| Private customer package | `docs/governance/PE-CUSTOMER-BUNDLE.json` and the test double at `docs/scripts/fixtures/pe-customer-bundle/PRIVATE-MANUAL.md` | `private` |

The control-plane snapshot in `docs/programs/production-readiness/WORKSTREAM-REGISTRY.json` still records WS11 as `NOT_RETRIEVED`. That snapshot is a prior refresh. This program sits beside it.

## Optics versions in this tree

| Package | Version | Registry bytes fetched by this force |
| --- | --- | --- |
| `@vantio/cli` | `0.3.24` | No. The release register records tag `v0.3.24` at `1fd21a64468ebc6f05fdbf624dae06a2fc8e75c4`. The tag selector is not an integrity pin. |
| `@vantio/agent-sdk` | `0.2.4` | No |
| `vantio-agent-sdk` | `3.1.0` | No. Sealed hashes below are copied from `scripts/release/stage_sealed_pypi.py`, which matches `RELEASE-REGISTER.json`. |
| `@vantio/optics-mcp` | `0.1.2` | No |
| `@vantio/gate-mcp` | `0.1.0` | No |
| `vantio-optics` | `0.1.0` | No |
| `@vantio/optics-evidence-contract` | `0.0.0-unstable-pre-1.0` | Unpublished private source |

Python wheel `vantio_agent_sdk-3.1.0-py3-none-any.whl` is pinned at 39235 bytes, SHA-256 `dcf84cb3c4f144ece21032001657bfd9c91067faeffbefd0fb2ae19d6109dbeb`. The sdist `vantio_agent_sdk-3.1.0.tar.gz` is pinned at 59669 bytes, SHA-256 `9f991291d5e44a23e17a9b0d7db24f6e7048d4c76cf0a9c37e35ccbcfe999c4f`. The release register calls the earlier observation `PUBLISHED_REGISTRY_BYTES_VERIFIED_CLIENT_PROVED`. The Optics dossier keeps registry status `NOT_FETCHED` and `this_force_refetched: false`. The historical label stays a citation.

## Pins this tree actually has

- Root `packageManager` names pnpm `11.13.0` and carries a `sha512` integrity string.
- `pnpm-lock.yaml` is present. Its SHA-256 is in the pin report. Lockfile importers record resolved versions for the workspace dependency ranges.
- `scripts/release/stage_sealed_pypi.py` pins the Python 3.1.0 filenames, byte lengths, and SHA-256 values. Dispatch inputs cannot replace them.
- GitHub Action references under `.github/` use floating refs such as `@v4` and `@release/v1`. The pin report records `digest_pinned: false` for each.
- `packages/vantio-agent-sdk-py/pyproject.toml` requires `hatchling` with no version comparator.
- CI and the provenance workflow install with `pnpm install --frozen-lockfile`. That binds the install to the lockfile. It leaves the Action refs and the Python build backend unpinned.

`npm-publish.yml`, `pypi-publish.yml`, and `mcp-registry-publish.yml` trigger on `workflow_dispatch`. `ci.yml` triggers on push and builds candidate artifacts. The candidate job packs and builds. It performs no registry write.

## Provenance characterization

`.github/workflows/enterprise-slsa-provenance.yml` can request `actions/attest-build-provenance@v2` for a tarball of `packages/vantio-agent-sdk/dist` and `packages/vantio-cli/bin`. The workflow comment withholds an in-repo verification. This force did not copy an attestation bundle into the tree.

`architecture_state.md` Phase VIII is a historical log. The pin report sets `historical_log_contains_level_assertion` from that log. The same log names `apps/web` and `packages/edge-proxy`. Both paths are absent. The workflow file on this commit attests a smaller bundle. WS11 claim tokens stay `NOT_CLAIMED`.

`pypi-publish.yml` leaves the publish action's attestation input unset and says a real publication can generate PEP 740 attestations. This force records that as capability. It records no PEP 740 bundle.

## Phantom Engine

The planning note at tip `631e435315cd780d83d3259e111893c1d0569bc3` records a chart pin, floating image tags, an undated Rust nightly channel, floating Docker tags, and an unversioned `bpf-linker` install. This force did not re-fetch `vantio-phantom-engine` and did not query a registry. The dossier kind for those inputs is `prior-record-unverified`.

## Private customer package

The only path containing `PRIVATE-MANUAL` or `CUSTOMER-MANUAL` is the documentation test double. Its header is `manual_version: 0.0.0-test`. The dossier hashes that file so custody has a subject. `body_class` is `test-double`. A customer manual body is not in this repository.

## Scans and SBOM

`generated/open-core-sbom.cdx.json` is a CycloneDX 1.5 document of workspace manifests plus the `packages:` section of `pnpm-lock.yaml`. `vantio:bound-to-sealed-artifact` is `false`. `generated/manifest-license-scan.json` reports missing `license` fields on the root manifest and the private Optics packages. `@vantio/cli` declares MIT. Neither report is a sealed-byte scan. The dossiers keep vulnerability and license status `NOT_RUN` for sealed bytes.

## Current verifier result

`generated/evaluations.json` records each dossier as `CHARACTERIZED` with `release_success` false. Gaps include unpinned toolchains, unrecorded tarball and image hashes, absent sealed-byte SBOM and scans, clean-environment installs not run, rollback hashes not recorded, registry bytes not fetched, ordinary-client proofs not run, retention not demonstrated, and partial publication not assessed.
