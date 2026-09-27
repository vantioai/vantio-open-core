# Threat model

Audience: INTERNAL_RESTRICTED

Document status: SKELETON

Future slot: `INVESTOR_UNDER_NDA`

Fill status: `NOT_FILLED`

Investor send: `NOT_CLEARED`

External publication: PROHIBITED

## Purpose

Reserve a threat-model chapter for a later redacted packet. This skeleton records status. It does not reproduce abuse paths.

## Source

`docs/architecture/optics-foundation/07-THREAT-MODEL.md`

That file is `INTERNAL_RESTRICTED`. It specifies cases T1–T15. Model status there is `ARCHITECTURE_DEFINED`. Implementation of the controls is `NOT_STARTED`. Residual risk is `UNSET`. Evidence tier is unset. Optics observes. A threat solved only by blocking customer traffic is a Phantom Engine concern in that file's own scope statement.

This room does not copy case write-ups from that file. A later investor page may name the case id, the asset class, and the implementation status after a human deletes procedure text.

## Status table

| Item | Value |
| --- | --- |
| Case range | T1–T15, specified in the architecture file |
| Copied into this room | No |
| Implementation | `NOT_STARTED` in the architecture file |
| Residual risk | `UNSET` |
| Evidence tier | Unset |
| Kernel and host-enforcement cases | Out of this file. No bypass detail. No probe list. No drop-path description. |

## Investor sections

| Section | Value |
| --- | --- |
| Assets an investor page may name | Local run files, local proof export, product-telemetry id. Detail `NOT_FILLED`. |
| Attacker procedures | Prohibited in this room |
| Exploit material | Prohibited |
| Compensating control claimed as shipped | None in this skeleton |
| Phantom Engine threat model | `NOT_VERIFIED_IN_THIS_REPO` |

## Fill rules

- High-level actor, asset, and impact only.
- Omit steps, commands, parameters, and reproduction detail.
- Do not claim a control is closed while the architecture file says `NOT_STARTED`.
