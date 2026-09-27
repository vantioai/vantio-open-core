# Method

Audience: INTERNAL_RESTRICTED

Track 15 did not repeat the Track 14 crawl. `source_inventory.refetched_public_http` is false. The observation window remains 2026-09-27T14:33:28Z through 2026-09-27T14:42:53Z.

A claim is a sentence a public surface asks a reader to believe. Routes, package descriptions, release text, profile text, and the fourteen drift items are the inputs. Gaps G-01 through G-10 stay in `gaps_not_promoted`. An unconfirmed listing is not turned into a claim that the listing exists or that it does not.

## Evidence status

| Status | When it is used |
| --- | --- |
| `SUPPORTED` | The register and the files on this checkout agree, and the agreement is enough for that sentence. A product definition can be supported without a new traffic run. The scope field says which kind of support it is. |
| `UNSUPPORTED` | The sentence states a fact this evidence set does not support, or a current version number the registries contradict. No performance number was added to fill a gap. |
| `UNKNOWN` | The sentence may be true and this evidence set does not show it. Present-tense enforcement, patents, corporate filings, form backends, and marketplace listings land here when proof is missing. |
| `CONFLICTING` | Two public surfaces, or a public surface and a file in this checkout, disagree. |

`SUPPORTED` is not a runtime pass. Optics observation is not Phantom Engine enforcement. Internal measurements stay not-customer-proof, because the product-evidence page says that and this program's `clean_host_internal_proof` and `proved_external` flags are false.

HTTP 404 on a named GitHub repository is not proof the repository is missing. The ledger uses `UNKNOWN` for that question.

## What was compared in-repo

Version fields in `packages/vantio-cli/package.json`, `packages/vantio-agent-sdk/package.json`, and `packages/vantio-agent-sdk-py/pyproject.toml`. The Optics manual sentence that 3.1.0 is unpublished. `docs/PRODUCT_LINEUP.md` and `docs/governance/canonical/product-boundary.md`. `packages/vantio-gate-mcp/server.json`. The Wave 3 status flags `customer_deployed`, `stranger_host_executed`, `kernel_executed`, `clean_host_internal_proof`, and `proved_external`.

Those flags bound this program. They are not a measurement of a repository this token cannot see.
