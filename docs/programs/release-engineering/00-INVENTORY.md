# WS11 inventory

Audience: INTERNAL_RESTRICTED

Base commit: `89f95099d0dce463307eb75d78e7fcf2ef99feb2`

Producer classification: `WS11_RELEASE_ENGINEERING_REVISION_READY_FOR_COUNCIL`

Council `bc-6ad40712-8957-5742-b9a4-b42fecf3b115` returned `WS11_RELEASE_ENGINEERING_NEEDS_REVISION` on tip `2e20cb018590dff720e2c209ad2b41ee2b9a0035`. This revision closes the Phantom R13 distribution hole. The classification is not a council verdict.

This inventory is the tree this force read. The machine-readable copy is `generated/pin-report.json`. A later edit that changes a pin, a hash, or a workflow trigger fails `scripts/release/ws11/ws11.test.mjs` until the generated files are emitted again.

## Surfaces

| Surface | Where this force looked | Distribution in the dossier |
| --- | --- | --- |
| Optics public packages and private source packages | `docs/governance/VERSION-METADATA.json`, package manifests, `scripts/release/`, `.github/workflows/` | `mixed` |
| Phantom Engine | `release/phantom-provenance-tip.txt` | `private` |
| Private customer package | `docs/governance/PE-CUSTOMER-BUNDLE.json` and the test double at `docs/scripts/fixtures/pe-customer-bundle/PRIVATE-MANUAL.md` | `private` |

The prior program snapshot that recorded WS11 as `NOT_RETRIEVED` is not in this public tree.

## Optics versions in this tree

| Package | Version | Registry bytes fetched by this force |
| --- | --- | --- |
| `@vantio/cli` | `0.3.24` | No. `docs/programs/release-engineering/SEALED-RELEASE-PINS.json` records tag `v0.3.24` at `1fd21a64468ebc6f05fdbf624dae06a2fc8e75c4`. The tag selector is not an integrity pin. |
| `@vantio/agent-sdk` | `0.2.4` | No |
| `vantio-agent-sdk` | `3.1.1` | No. Sealed hashes below are copied from `scripts/release/stage_sealed_pypi.py`. |
| `@vantio/optics-mcp` | `0.1.2` | No |
| `@vantio/gate-mcp` | `0.1.0` | No |
| `vantio-optics` | `0.1.0` | No |
| `@vantio/optics-evidence-contract` | `0.0.0-unstable-pre-1.0` | Unpublished private source |

Python wheel `vantio_agent_sdk-3.1.1-py3-none-any.whl` is pinned at 33997 bytes, SHA-256 `6a0e4aff4c3d520df0016ae2d56c97fd2c5a7a09e184edd63c59044f558685b8`. The sdist `vantio_agent_sdk-3.1.1.tar.gz` is pinned at 57039 bytes, SHA-256 `8a03682afd2058788bd044fbd3784d3b837067bf5ff189d6be5b09434ec96799`. The sealed release pins record the current row state as `SEALED_BYTES_RECORDED_NOT_PUBLISHED`. Its earlier observation remains `PUBLISHED_REGISTRY_BYTES_VERIFIED_CLIENT_PROVED`. The custody tag `custody-py-3.1.1` is not created by this record. The Optics dossier keeps registry status `NOT_FETCHED` and `this_force_refetched: false`. The historical label stays a citation. This refresh did not fetch registry bytes.

## Pins this tree actually has

- Root `packageManager` names pnpm `11.13.0` and carries a `sha512` integrity string.
- `pnpm-lock.yaml` is present. Its SHA-256 is in the pin report. Lockfile importers record resolved versions for the workspace dependency ranges.
- `scripts/release/stage_sealed_pypi.py` pins the Python 3.1.1 filenames, byte lengths, and SHA-256 values. Dispatch inputs cannot replace them.
- Workflow files under `.github/workflows/` and the local composite `.github/actions/vantio-prove/action.yml` pin third-party actions to commit SHAs with tag comments. The pin report records those as `owner/name@sha # tag` with `digest_pinned: true`.
- `packages/vantio-agent-sdk-py/pyproject.toml` requires `hatchling` with no version comparator.
- CI and the provenance workflow install with `pnpm install --frozen-lockfile`. That binds the install to the lockfile. The Python build backend stays unpinned.

`npm-publish.yml`, `pypi-publish.yml`, and `mcp-registry-publish.yml` trigger on `workflow_dispatch`. `ci.yml` triggers on push and builds candidate artifacts. The candidate job packs and builds. It performs no registry write.

## Provenance characterization

`.github/workflows/enterprise-slsa-provenance.yml` requests `actions/attest-build-provenance@e8998f949152b193b063cb0ec769d69d929409be # v2` for a tarball of `packages/vantio-agent-sdk/dist` and `packages/vantio-cli/bin`. The workflow comment withholds an in-repo verification. This force did not copy an attestation bundle into the tree.

`release/architecture-state-level-phrase.txt` is what the pin report reads for `historical_log_contains_level_assertion`. `apps/web` and `packages/edge-proxy` are absent. The workflow file on this commit attests a smaller bundle. WS11 claim tokens stay `NOT_CLAIMED`.

`pypi-publish.yml` leaves the publish action's attestation input unset and says a real publication can generate PEP 740 attestations. This force records that as capability. It records no PEP 740 bundle.

## Phantom Engine

The recorded planning tip is `631e435315cd780d83d3259e111893c1d0569bc3` in `release/phantom-provenance-tip.txt`. This force did not re-fetch `vantio-phantom-engine` and did not query a registry. The dossier kind for those inputs is `prior-record-unverified`.

## Private customer package

The only path containing `PRIVATE-MANUAL` or `CUSTOMER-MANUAL` is the documentation test double. Its header is `manual_version: 0.0.0-test`. The dossier hashes that file so custody has a subject. `body_class` is `test-double`. A customer manual body is not in this repository.

## Scans and SBOM

`generated/open-core-sbom.cdx.json` is a CycloneDX 1.5 document of workspace manifests plus the `packages:` section of `pnpm-lock.yaml`. `vantio:bound-to-sealed-artifact` is `false`. `generated/manifest-license-scan.json` reports missing `license` fields on the root manifest and the private Optics packages. `@vantio/cli` declares MIT. Neither report is a sealed-byte scan. The dossiers keep vulnerability and license status `NOT_RUN` for sealed bytes.

## Current verifier result

`generated/evaluations.json` records each dossier as `CHARACTERIZED` with `release_success` false. Gaps include unpinned toolchains, unrecorded tarball and image hashes, absent sealed-byte SBOM and scans, clean-environment installs not run, rollback hashes not recorded, registry bytes not fetched, ordinary-client proofs not run, retention not demonstrated, and partial publication not assessed.
