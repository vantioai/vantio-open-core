# Target architecture

Audience: INTERNAL_RESTRICTED

Document status: SKELETON

Future slot: `INVESTOR_UNDER_NDA`

Fill status: `NOT_FILLED`

Investor send: `NOT_CLEARED`

External publication: PROHIBITED

## Purpose

Keep the shipping architecture and the ratified target in separate sentences. The target is not a ship claim.

## Shipping

See [04-ARCHITECTURE.md](04-ARCHITECTURE.md). Today's Optics store is one JSON file per trace id. The CLI version in this tree is 0.3.24 and is frozen in the public manual.

## Ratified target inside this repository

| Item | State | Source |
| --- | --- | --- |
| Store option C | `FOUNDER_RATIFIED_ARCHITECTURE_ONLY` | `docs/architecture/optics-foundation/00-PROGRAM-BOUNDARY.md` |
| Database | Not created | Same file |
| Gates 2–7 | Accepted as architecture documents by the fresh council named in that pack | `docs/architecture/optics-foundation/09-IMPLEMENTATION-GATES.md` |
| Gate 8 | Closed. Not started | Same file |
| Schema | `unstable-pre-1.0` | Public manual and the architecture pack |
| Numeric performance budgets | `NOT_SET` | Architecture pack |
| Local UI, retention prune, trends, alerting, OTLP export | Planning or explicitly absent. Canonical docs must not present them as current. | `docs/governance/ROADMAP-NOT-CURRENT.json` |

A later investor page that mentions the target labels it as architecture. It does not say the store has shipped.

## Phantom Engine target

Component list, host scope, and cluster status: `NOT_VERIFIED_IN_THIS_REPO`.

This file does not copy kernel design, loader design, or bypass analysis from the Phantom Engine repository.

## Sections still empty

| Section | Value |
| --- | --- |
| Target diagram | `NOT_FILLED` |
| Migration story from JSON files to a future store | `NOT_FILLED`. No migrator exists. |
| Decision log of founder items still open | `NOT_FILLED`. Architecture decision pack items 2–13 were unresolved in `docs/architecture/optics-foundation/00-PROGRAM-BOUNDARY.md`. Re-read before repeating that count. |

## Fill rules

- "Ratified" means the architecture choice was recorded. It does not mean implemented, tested, or customer-validated.
- Leave prohibited mechanisms in [00-ROOM-BOUNDARY.md](00-ROOM-BOUNDARY.md) unstated.
