# Drift waiting for Track 15

Audience: INTERNAL_RESTRICTED

These are disagreements among surfaces that are already public. Disposition is `UNREVIEWED` on each. This track does not pick a winner and does not edit either side.

| Id | What is public today |
| --- | --- |
| D-01 | `llms.txt` says Gate is not a SKU. The GitHub org description says Gate applies the rules you set. |
| D-02 | npm `@vantio/agent-sdk`, `@vantio/optics-mcp`, and `@vantio/gate-mcp` still describe an upgrade path to Gate or Pro. The agent SDK README links `vantioai/vantio-pro`, which returned HTTP 404. |
| D-03 | The open-core repository description still says CLI 0.3.2 and Python 3.0.2. Registries show 0.3.24 and 3.1.0. |
| D-04 | `docs/products/optics/` on this tip says PyPI is 3.0.14 and 3.1.0 is unpublished. The registry latest observed here is 3.1.0, and the wheel and sdist hashes match the GitHub custody release. |
| D-05 | PyPI 1.0.0, 2.0.0, and 3.0.0 remain installable. Their summaries describe a session SDK, a proxy interceptor, and governance telemetry. 3.1.0 describes metadata-only observe. None are yanked. |
| D-06 | The LinkedIn company page and the founder profile still describe Gate as a product and use stronger capability sentences than `llms.txt`. |
| D-07 | The org profile README links `vantioai/vantio-phantom-engine`. That URL is not in the public repository list and returned HTTP 404 to this token. |
| D-08 | `/pricing` says $799 per enrolled node per month and a 14-day trial. `/start/design-partner` says $600 per governed node per month, outreach paused, card checkout not live. |
| D-09 | Four live `/updates` URLs are missing from `sitemap.xml`. One slug is `vantio-runs-company-ops-on-optics-gate-phantom-engine`. |
| D-10 | `packages/vantio-gate-mcp/server.json` documents default API base `https://api.vantio.ai`. That hostname did not resolve. |
| D-11 | The website names `@vantioai`. X has `@VantioAI` with an empty follower count, joined September 2026. The GitHub org Twitter field is null. |
| D-12 | Open issues on `vantioai/.github` still title Gate as Policy Latch. |
| D-13 | `autonomous-ops-framework` is public. Its README title is Phantom Box and it says the skeleton is not yet announced. |
| D-14 | The PyPI Phantom Engine project URL is `/phantom`, which redirects to `/phantom-engine`. |

## What a reviewer should not treat as settled

The website’s own `llms.txt` is the most recent controlled claim ceiling observed on a Vantio-operated host. Older npm text, older PyPI releases, the GitHub org description, the public Optics manual, and LinkedIn posts were all still reachable on the same day. Reachable is not the same as current.

Frozen bytes stay frozen: `@vantio/cli` 0.3.24 and the `vantio-agent-sdk` 3.1.0 wheel and sdist recorded in the JSON. Track 15 can recommend a later cut. This track does not make one.
