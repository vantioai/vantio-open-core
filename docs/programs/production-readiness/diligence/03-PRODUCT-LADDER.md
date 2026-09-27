# Product ladder

Audience: INTERNAL_RESTRICTED

Document status: SKELETON

Future slot: `INVESTOR_UNDER_NDA`

Fill status: `NOT_FILLED`

Investor send: `NOT_CLEARED`

External publication: PROHIBITED

## Purpose

Index the public commercial ladder already written in this repository. A later investor retelling has to match that ladder on the day it is sent. This file is the checklist, not the leave-behind.

## Public lineup to re-read

| Source | Recorded statement |
| --- | --- |
| `docs/PRODUCT_LINEUP.md` | Optics (Free), Phantom Engine (`$799/node/mo`), Enterprise (talk to sales) |
| `README.md` | Same price line for Phantom Engine. Free Optics needs no account and no API key. |
| `docs/internal/claim-scrub-report-2026-09-20.md` | Gate is not a current standalone public SKU. Historical note only. Re-read the lineup before sending. |

The `$799/node/mo` figure is the public lineup figure in this repository. It is not a new price decision. Re-read `vantio-phantom-engine/docs/product-spec.md` before an investor packet treats it as current. That file is not in this repository. Status of that re-read: `NOT_VERIFIED_IN_THIS_REPO`.

## Ladder slots

| Product | Job in the public lineup | This repo | Investor clearance |
| --- | --- | --- | --- |
| Vantio Optics | Observe | This repository | `NOT_CLEARED` |
| Vantio Phantom Engine | Enforce + Control on enrolled Linux hosts | Separate repository | `NOT_CLEARED` |
| Vantio Enterprise | Governance on that protection | Talk to sales in the public lineup | `NOT_CLEARED` |
| Gate | Internal name for the Enforce function set. `@vantio/gate-mcp` is legacy/compat dry-run. | Package exists here | `NOT_CLEARED` |

## Honest gaps already in the lineup

Re-read `docs/PRODUCT_LINEUP.md` section "Honest gaps" before filling. The lineup records: Optics has no block; traffic that never hits the interceptor is never recorded; Phantom Engine has a privileged disable of the loader, pod-network caveats, and applies on enrolled hosts; Enterprise shares that host scope; certifications are not held.

This skeleton does not add gaps and does not remove those.

## Fill rules

- Do not reintroduce a four-product purchasable ladder.
- Do not add ARR bands, discount schedules, or contract terms. None are in the public lineup.
- Do not paste a Phantom Engine customer price schedule from outside this repository into this file.
