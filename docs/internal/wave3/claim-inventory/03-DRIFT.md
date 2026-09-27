# Drift D-01 through D-14

Audience: INTERNAL_RESTRICTED

Each drift from the Track 14 register is linked from at least one claim. The claim rows are the disposition record. This table is the index.

| Drift | What is public | Claims | Recommendation that does not execute |
| --- | --- | --- | --- |
| D-01 | `llms.txt` says Gate is not a current SKU. The GitHub org description says Gate applies the rules you set. | `CL-W3-T15-001`, `CL-W3-T15-002`, `CL-W3-T15-040`, `CL-W3-T15-053` | Keep the ceiling sentence. The org description is an external-account change. |
| D-02 | npm text still offers an upgrade path to Gate or Pro, including a link that returned HTTP 404. | `CL-W3-T15-001`, `CL-W3-T15-003`, `CL-W3-T15-031`, `CL-W3-T15-032`, `CL-W3-T15-033` | Hold. Correcting `@vantio/agent-sdk@0.2.4` would reopen it. No npm publish. |
| D-03 | The open-core description still says CLI 0.3.2 and Python 3.0.2. | `CL-W3-T15-004`, `CL-W3-T15-029` | The description is external metadata. The frozen CLI version stays 0.3.24. |
| D-04 | The Optics manual says PyPI is 3.0.14 and 3.1.0 is unpublished. The registry latest T14 read was 3.1.0, with matching hashes. | `CL-W3-T15-005`, `CL-W3-T15-030` | Rewrite is recommended for the manual and was not done. 3.1.0 bytes stay frozen. |
| D-05 | PyPI 1.0.0, 2.0.0, and 3.0.0 remain installable with older summaries. None are yanked. | `CL-W3-T15-006`, `CL-W3-T15-030`, `CL-W3-T15-035` | Hold. A yank is named only as a later action that is not authorized. |
| D-06 | LinkedIn still describes Gate as a product and uses stronger capability sentences than `llms.txt`. | `CL-W3-T15-001`, `CL-W3-T15-007`, `CL-W3-T15-058`, `CL-W3-T15-059`, `CL-W3-T15-060` | External account only. Latency, kernel, and compliance-proof wording stay unsupported. |
| D-07 | The org profile links `vantioai/vantio-phantom-engine`, which returned HTTP 404 and is not in the public list. | `CL-W3-T15-008`, `CL-W3-T15-034`, `CL-W3-T15-062` | Unknown whether the repository is private. This repo does not ship Phantom Engine. |
| D-08 | `/pricing` says $799 and a 14-day trial. `/start/design-partner` says $600, outreach paused, card checkout not live. | `CL-W3-T15-009`, `CL-W3-T15-028`, `CL-W3-T15-061`, `CL-W3-T15-062`, `CL-W3-T15-067` | Keep the paused and no-checkout sentences. Canonical price wording waits for Track 16. |
| D-09 | Four live `/updates` URLs are missing from the sitemap. One slug still says gate. | `CL-W3-T15-010`, `CL-W3-T15-039`, `CL-W3-T15-040` | The omission is an external-account fix. The Show HN age is not a biographical fact. |
| D-10 | `packages/vantio-gate-mcp/server.json` documents `https://api.vantio.ai`. That host did not resolve. | `CL-W3-T15-011` | Rewrite is recommended and was not done. DNS was not created. |
| D-11 | The website names `@vantioai`. X is `@VantioAI` with an empty follower count. The GitHub org Twitter field is null. | `CL-W3-T15-012` | External accounts only. Nothing was posted. |
| D-12 | Open issues on `vantioai/.github` still title Gate as Policy Latch. | `CL-W3-T15-001`, `CL-W3-T15-013` | External repository. Issues were not closed. |
| D-13 | `autonomous-ops-framework` is public. The README title is Phantom Box and says the skeleton is not yet announced. | `CL-W3-T15-014` | External repository. It was not unpublished and not announced. |
| D-14 | The PyPI Phantom Engine URL is `/phantom`, which redirects to `/phantom-engine`. | `CL-W3-T15-015` | Hold. Changing the URL would republish metadata on frozen 3.1.0 bytes. |

## What not to treat as settled

Reachable text is not current text. The ceiling on `llms.txt` is the controlled website statement from the Track 14 day. Older registry text was still installable the same day. This track does not pick a publish to make them match.
