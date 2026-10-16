# Gap program T6–T14 risk register

Audience: INTERNAL

Phase: 1 design only.

Written: 2026-10-16T15:48:08Z

Track label: Roadmap

This register rolls up the track risks. It is not a closed risk list. "Accepted" means the design names the residual and does not pretend it is solved.

| ID | Track | Risk | State |
| --- | --- | --- | --- |
| R1 | T6 | A historical SAML menu or a local "run identity" label is treated as Entra, Okta, or SPIFFE | Open |
| R2 | T6 | Enforce falls back to an identity-blind allow if a later eBPF load fails | Open. Design says deny |
| R3 | T7 | An in-process swap puts the secret in the compromised workload | Open. Design rejects that swap |
| R4 | T7 | The broker becomes a required proxy for all egress | Open. Design forbids it |
| R5 | T7 | Root on the host can read the broker | Accepted residual |
| R6 | T8 | The 2026-10-10 scoped lab is read as product OTLP authorization | Open. `product_otlp_export_authorized` stays false |
| R7 | T8 | Local NDJSON is described as WORM | Open. Validator result is `MUTABLE_LOCAL_LEDGER` |
| R8 | T9 | A Roadmap cell or a nearby unit test is cited as Verified | Open. Verified count is 0 |
| R9 | T10 | Timeout is implemented as proceed | Open. Design says deny |
| R10 | T10 | `APPROVED` is shown as host activation | Open. E3 separates the states |
| R11 | T11 | Unenrolled start is displayed as covered | Open. Coverage stays enrolled cgroups |
| R12 | T11 | Descendant lab scripts are graded without a run this force is allowed to do | Accepted. Not graded here |
| R13 | T12 | OTEL field preview and policy preview are merged | Open. Different modules |
| R14 | T13 | The gap list is shortened to a FedRAMP or FIPS claim | Open. Every row is GAP |
| R15 | T14 | 2 December 2027 is quoted as the only application date, or as a classification | Open. Annex III qualifier required. 2 August 2028 stays named |
| R16 | All | A dollar amount or a currency code in `docs/gap-program`, or a later README price, tag, or production signing root | Open. The checker rejects a dollar sign and the currency codes inside `docs/gap-program`. It does not watch the README, tags, or the pin. The pin stays `e0b19d55` |
| R17 | All | T0–T5 artifacts are assumed merged | Accepted. They are sibling charters, not in this commit |

## Threat model

The register itself can be copied without the track documents. Each row is a pointer. The response lives in the track file.

## Failure modes

A risk register that does not name every track from T6 through T14 fails the checker. Reason: an omitted track id is how a gap gets dropped. The checker looks for those ids. It does not judge whether the row is wise.

## Edge cases

A track moves to Lab-only later. The register row stays until that force updates it. This file does not auto-close.

## Memory footprint

Document only.

## eBPF verifier limits

No program.

## Dependencies on T0–T5

R17. Sibling charters T0 through T5 are not merged. Designs that need them say so in the track files.

## Rollback

Revert this file with the track documents. No runtime flag.

## Approval gates

Draft PR only. No founder-approved label. No external send.

## Council

Verdict: PENDING_INDEPENDENT_REVIEW
