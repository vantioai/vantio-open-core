# Documentation release gate — integration plan

Status: proposal for council review. This change does not modify publish or release workflows.

Base commit: `d7299a35be0d9a70ec306ca672aa1359e09f1515`

Branch: `docs/documentation-release-governance-v1`

## Revision after DOCS_GOVERNANCE_NEEDS_REVISION

The gate is rebased onto `d7299a35be0d9a70ec306ca672aa1359e09f1515`, the Optics public manual from PR #64. `MANIFEST.json` `base_commit` and the hardcoded SHA in `checkManifestShape` are that same commit.

Supported-path needles are whole clauses from `packages/vantio-cli/bin/interceptor.cjs` and `packages/vantio-agent-sdk-py/vantio/_http_observe.py`. A needle that is only a prefix of a longer path clause fails `supported-paths-match-catalogs`. The catalog includes Client/Pool/Agent `request()` and `dispatch()`, `http/https.request|get` and `ClientRequest`, `http2` `session.request`, `undici.WebSocket`, `undici.upgrade / CONNECT tunnel writes`, and distinct `curl`, `wget`, `httpie`, and `aria2c` rows for Node and Python. Python also includes `requests`, `OpenerDirector.open`, and `http.client`. The known-limitations sentence about `http.client` and pycurl success-path HTTP status is repeated in the supported-paths doc.

The legacy scan includes `.txt`. PR #64 pages that name `Sight Loop` / `sight_loop` as leftover storage are `intentional_leftovers` in `LEGACY-STALE-NAMES.json`, not new debt. The product name in that rule is Vantio Optics. `docs/products/optics/llms.txt` and `docs/products/optics/llms-full.txt` are the same leftovers outside `docs/governance/`. The manual text is unchanged.

## Manifest design

`docs/governance/MANIFEST.json` is the documentation release manifest (`vantio.docs-release/v1`). Its shape is `docs/governance/schema/documentation-release.schema.json`. The manifest points at the governed files; it does not copy product behavior.

| File | Role |
|---|---|
| `VERSION-METADATA.json` | Package versions already in this tree. Checks compare manifests to this file. No version bump. |
| `PRODUCT-BOUNDARY.json` | Phrases the root `README.md` must keep, and phrases it must not gain. |
| `PUBLIC-EXPORTS.json` | Current TypeScript exports and Python `__all__`, plus removed names. |
| `ENV-VARS.json` | Public and internal environment variables read by runtime code. |
| `STATUS-TOKENS.json` | Optics display vocabulary and SDK action tokens. |
| `SUPPORTED-PATHS.json` | Wrapped and unsupported paths, each tied to a source needle and a canonical phrase. |
| `LLM-HOSTS.json` | Exact host list shared by Node `LLM_HOSTS`, Python `_LLM_HOSTS`, and Python `_CATALOG`. |
| `STALE-NAMES.json` | Retired names rejected in canonical docs. |
| `LEGACY-STALE-NAMES.json` | Frozen inventory of those names outside the canonical set. |
| `ROADMAP-NOT-CURRENT.json` | Planning items that cannot be described as current. |
| `KNOWN-LIMITATIONS.json` | Phrases `canonical/known-limitations.md` must contain. |
| `PACKAGING-EXCLUSION.json` | Public package roots and path fragments that must not ship. |
| `PE-CUSTOMER-BUNDLE.json` | Non-public bundle contract. The only manual in this repo is a test fixture. |
| `llms.txt` | Repo-relative paths of current canonical docs, and nothing else. |
| `llms-full.txt` | Byte-for-byte concatenation of those docs. Regenerate with `node docs/scripts/render-llms-full.mjs`. |
| `canonical/ai-guide.md` | AI guide whose `ai_guide_versions` map matches `VERSION-METADATA.json`. |

Canonical docs are the root README, the three shipping READMEs that do not carry retired names (`@vantio/cli`, `@vantio/agent-sdk`, `vantio-agent-sdk`), and the files under `docs/governance/canonical/`. Historical docs stay in the tree. They are not current until they pass these checks and are added to `llms.txt`.

## Check inventory

Run: `node --test docs/scripts/check-docs-release.test.mjs`

Report: `node docs/scripts/check-docs-release.mjs`

| Check id | Requirement |
|---|---|
| `manifest-schema` | Manifest matches the schema and the pinned base commit. |
| `package-version-matches-metadata` | Each package manifest (and Python `__version__`) matches `VERSION-METADATA.json`. |
| `readme-matches-product-boundary` | Root README keeps the product-boundary phrases and rejects retired wording. |
| `public-exports-documented` | Source exports match the manifest and appear in `canonical/public-exports.md`. |
| `removed-exports-not-current` | Removed names appear only under a historical heading in canonical docs. |
| `examples-execute` | Feasible examples run; infeasible examples name a reason and an existing path. |
| `env-vars-documented` | Runtime `VANTIO_*` and `DO_NOT_TRACK` reads match the catalog. Public names are in `canonical/environment.md`. |
| `status-tokens-documented` | Display and action tokens match source and `canonical/status-tokens.md`. |
| `supported-paths-match-catalogs` | Path needles match whole source clauses, the canonical path doc, and the three host catalogs. A prefix of a longer path clause fails. |
| `known-limitations-exist` | The known-limitations doc contains each required phrase. |
| `changelog-entry-exists` | Each governed version has a changelog heading. New headings for packages that had no changelog live under `docs/governance/changelogs/` so they are not added to an npm pack. |
| `ai-guide-version-matches` | AI guide versions equal the package versions. |
| `llms-txt-canonical-only` | `llms.txt` lists the canonical set and no other path. |
| `llms-full-regenerable` | Committed `llms-full.txt` matches regeneration. |
| `public-artifacts-exclude-pe-customer-docs` | `npm pack --dry-run` file lists and Python wheel/sdist candidates exclude customer-manual paths. |
| `public-packages-exclude-internal-docs` | Those same lists exclude `docs/internal/`, `LEAVE_ENGINEERING_GAP.md`, and the other denial fragments. |
| `private-packages-stay-private` | `@vantio/optics-evidence-contract` stays `"private": true`. |
| `pe-customer-bundle-includes-matching-manual` | The bundle design is non-public and the test fixture manual version matches the bundle version. |
| `stale-product-names-rejected` | Canonical docs contain none of the retired-name patterns. |
| `roadmap-features-not-current` | Canonical docs do not present unimplemented roadmap items as current. A line may say there is no OTLP exporter. |
| `legacy-stale-name-inventory-frozen` | Non-canonical matches stay exactly the committed debt inventory, including `.txt`. Optics intentional leftovers stay on their own list. New matches fail. Canonical paths cannot be listed as debt or as leftovers. |

Packaging tests build temporary npm and Python trees that include `CUSTOMER-MANUAL` and `docs/internal/` and assert those paths are hits. They do not upload anywhere.

## Phantom Engine customer bundle

No Phantom Engine customer manual is stored in this repository. `docs/scripts/fixtures/pe-customer-bundle/PRIVATE-MANUAL.md` is a test double with `manual_version: 0.0.0-test`.

A customer bundle is valid only when:

- `public_distribution` is false
- members include `manifest` and `private-manual`
- the manual's `manual_version` header equals the bundle version

Public packs are rejected if a path contains `CUSTOMER-MANUAL`, `PRIVATE-MANUAL`, `phantom-engine/customer/`, or `pe-customer/`. The fixture is not inside a public package directory.

## Legacy retired names

Canonical docs were chosen so they do not contain the retired-name patterns in `STALE-NAMES.json`. Other files still contain those patterns, including some text that ships inside package metadata. That debt is frozen in `LEGACY-STALE-NAMES.json` `hits`. Adding a new match fails the check. Removing a match requires a reviewed inventory edit. Promoting a legacy file into `llms.txt` fails until the names are gone.

`.txt` is part of the scan. `docs/governance/` stays excluded, so the governance `llms.txt` is not this scan. `docs/products/optics/llms.txt` and `docs/products/optics/llms-full.txt` are outside that directory. They repeat PR #64's manual.

`intentional_leftovers` records that manual. The seven markdown pages and the two text exports name `Sight Loop` / `sight_loop` as leftover storage. The rule states that the product name is Vantio Optics. Those sentences are not new debt. A count change on those paths fails until the rule is updated. A retired name in any other file, including another `.txt`, is still new debt.

This change does not rewrite product source, package descriptions, historical docs, or the Optics public manual.

## Proposed CI job (not added)

Do not attach this job to `npm-publish.yml`, `pypi-publish.yml`, `mcp-registry-publish.yml`, or `enterprise-slsa-provenance.yml`. Those workflows stay as they are. Do not call `npm publish`, `twine`, the PyPI publish action, or the promote scripts from this job.

When council accepts the gate, add a new workflow file `.github/workflows/docs-release-governance.yml` and nothing else:

```yaml
name: Docs release governance

on:
  pull_request: {}
  workflow_dispatch: {}

jobs:
  docs-release-governance:
    name: Documentation release checks
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Node.js 22
        uses: actions/setup-node@v4
        with:
          node-version: "22"

      - name: Check documentation release manifests
        run: node --test docs/scripts/check-docs-release.test.mjs
```

The job has no secrets, no registry auth, and no publish step. `npm pack --dry-run` runs only inside the check, against local package directories and temp fixtures.

Until that workflow exists, run the same command locally before a documentation release.

## Out of scope for this change

- Publishing to npm, PyPI, or the MCP registry
- Version bumps
- Product behavior changes
- Editing credentialed publish workflows
- Merging this branch
- A self-council decision

DOCS_GOVERNANCE_READY_FOR_COUNCIL
