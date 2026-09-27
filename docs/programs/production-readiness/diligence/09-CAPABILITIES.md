# Capabilities

Audience: INTERNAL_RESTRICTED

Document status: SKELETON

Future slot: `INVESTOR_UNDER_NDA`

Fill status: `NOT_FILLED`

Investor send: `NOT_CLEARED`

External publication: PROHIBITED

## Purpose

Separate a public lineup statement from an evidence tier. Checkmarks in `docs/PRODUCT_LINEUP.md` are lineup statements. This room does not convert them into proof.

## Lineup statements to re-read

Source: `docs/PRODUCT_LINEUP.md` capability matrix. Evidence tier for every cell: `UNSET`.

| Capability | Optics lineup | Phantom Engine lineup | Enterprise lineup |
| --- | --- | --- | --- |
| Observe wrapped calls | Stated | Stated | Stated |
| Block by hostname on a wrapped path | Absent | Stated | Stated |
| PII redaction on a wrapped path | Absent | Stated | Stated |
| Spend / size caps on a wrapped path | Absent | Stated | Stated |
| Host enforcement on enrolled Linux | Absent | Stated | Stated |
| Fork inheritance on enrolled hosts | Absent | Stated | Stated |
| CIDR / Kubernetes network policy on enrolled hosts | Absent | Stated | Stated |
| Durable ledger / dual-control | Absent | Partial, as the lineup word | Stated |

Phantom Engine and Enterprise rows are lineup text. Their implementation status in the Phantom Engine repository is `NOT_VERIFIED_IN_THIS_REPO`.

## Optics capabilities this repository can speak to

Re-read `docs/products/optics/SUPPORTED-PATHS.md` and `docs/governance/SUPPORTED-PATHS.json` before naming a client. The public manual's supported-path list is the list. This skeleton does not duplicate it, so the two cannot drift.

`@vantio/optics-mcp` is a read-only local log reader at the version in `docs/governance/VERSION-METADATA.json`.

`@vantio/gate-mcp` is legacy/compat dry-run evaluation. It is not a capability of free Optics and not a standalone SKU.

## Sections still empty

| Section | Value |
| --- | --- |
| Per-capability test pointer | `NOT_FILLED` |
| Per-capability proof tier | `UNSET` |
| Unsupported-path inventory for the packet | `NOT_FILLED`. Use the public supported-path document. |

## Fill rules

- A capability sentence names the product that owns it.
- Enforcement, redaction, and spend caps stay on the Phantom Engine row.
- Host-level controls stay as lineup statements until the Phantom Engine source of truth is re-read. Do not add bypass or enforcement procedure text here.
