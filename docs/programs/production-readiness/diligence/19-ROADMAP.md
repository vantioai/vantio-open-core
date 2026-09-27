# Roadmap

Audience: INTERNAL_RESTRICTED

Document status: SKELETON

Future slot: `INVESTOR_UNDER_NDA`

Fill status: `NOT_FILLED`

Investor send: `NOT_CLEARED`

External publication: PROHIBITED

## Purpose

Point at the internal requirements roadmap without turning it into a commitment. Dates stay unset.

## Sources

| Source | How to use it |
| --- | --- |
| `docs/internal/optics-best-in-class-roadmap.md` | Requirements input. The file states that it does not authorize implementation, a release, a tag, a seal, or a publish. It assigns no dates. |
| `docs/architecture/optics-foundation/09-IMPLEMENTATION-GATES.md` | Gates 1–7 are documents. Gate 8 is closed. |
| `docs/governance/ROADMAP-NOT-CURRENT.json` | Items that canonical docs must not present as current. |
| `docs/planning/optics-foundation-a8/` | Planning for a later implementation force. A8 is not authorization to ship. |

## Slots

| Horizon | Content | Date |
| --- | --- | --- |
| Shipping now | Public Optics manual for the versions in [11-BUILD-STATUS.md](11-BUILD-STATUS.md) | Already published as recorded there. Re-read before sending. |
| Architecture ratified, not built | Store option C and gates 2–7 | `NOT_SET` |
| Implementation force | Gate 8 | Closed. Date `NOT_SET` |
| Named future product commands | Listed as absent or earmarked in the governance file above | `NOT_SET`. Do not present them as shipped. |
| Phantom Engine roadmap | `NOT_VERIFIED_IN_THIS_REPO` | `NOT_SET` |

## Fill rules

- No calendar commitment in this file.
- A roadmap sentence that names a command also says the command is absent from the shipping CLI, unless the public manual documents that command.
- Evidence tier for roadmap items stays unset. The internal roadmap says current evidence tier, stranger-host, and customer validation are unset for its items.
- Retired product names in `docs/governance/STALE-NAMES.json` stay unused.
