# Build status

Audience: INTERNAL_RESTRICTED

Document status: SKELETON

Future slot: `INVESTOR_UNDER_NDA`

Fill status: `VERSIONS_INDEXED`

Investor send: `NOT_CLEARED`

External publication: PROHIBITED

## Purpose

Record versions that are already in this tree, and mark everything outside this tree as unverified. Re-read the version files before an investor send. This page is an index taken at base commit `5064f32f1cdfcb840dfd100e2ce5c712d046550d`.

## Versions in this tree

Source of the version strings: `docs/governance/VERSION-METADATA.json`. That file records versions already in the tree. It does not bump them.

| Package | Version in tree | Note for a later fill |
| --- | --- | --- |
| `@vantio/cli` | 0.3.24 | Public manual records the npm package at 0.3.24 and the CLI as frozen. |
| `vantio-agent-sdk` (Python) | 3.1.0 | Source version. `docs/products/optics/VERSION-METADATA.json` records PyPI latest 3.0.14 at `registry_checked_utc` `2026-09-27T05:24:00Z`. Unpublished source is not the installable package. |
| `@vantio/agent-sdk` | 0.2.4 | Public manual: this package does not write `~/.vantio/runs`. |
| `@vantio/optics-mcp` | 0.1.2 | Read-only local log reader. |
| `@vantio/gate-mcp` | 0.1.0 | Legacy/compat. Not a standalone public SKU. |
| `vantio-optics` VS Code extension | 0.1.0 | Version recorded in governance metadata. Behavior for an investor page is `NOT_FILLED`. |
| `@vantio/optics-evidence-contract` | `0.0.0-unstable-pre-1.0` | Private. Not a shipment. |
| `@vantio/optics-record-vocabulary` | `0.0.0-unstable-pre-1.0` | Private package. Not imported by the live CLI or SDKs at this base commit. |

## Build claims this index allows

| Claim | Status |
| --- | --- |
| Optics observe CLI and Python SDK source exist in this repository | Indexed above |
| Python 3.1.0 is the published PyPI package | False on the registry check cited above. Re-check before sending. |
| Evidence contract or record vocabulary is loaded by the shipping CLI | Not on this base commit |
| Phantom Engine build status | `NOT_VERIFIED_IN_THIS_REPO` |
| Enterprise control plane | Lives outside this repository. `architecture_state.md` points at `vantio-pro` as archival for an older web app move. Do not describe that pointer as current revenue infrastructure without a fresh read. |
| Cluster enforcement, live ledger writes | `NOT_VERIFIED_IN_THIS_REPO` |

## Sections still empty

| Section | Value |
| --- | --- |
| Commit-to-registry reconciliation performed for this packet | `NOT_FILLED` |
| Known defect list beyond the public limitations | `NOT_FILLED` |
| Phantom Engine status matrix | Prohibited until read in that repository, and kernel detail stays out even then |
