# Technical appendix

Audience: INTERNAL_RESTRICTED

Document status: SKELETON

Future slot: `INVESTOR_UNDER_NDA`

Fill status: `POINTERS_ONLY`

Investor send: `NOT_CLEARED`

External publication: PROHIBITED

## Purpose

Index primary technical documents a later appendix might cite. The appendix body is the pointer list. Do not paste those documents into this file.

## Pointers

| Topic | Path | Handling of the source |
| --- | --- | --- |
| Public product manual | `docs/products/optics/README.md` | Public. Quote only after a fresh read. |
| Supported paths | `docs/products/optics/SUPPORTED-PATHS.md` | Public. |
| Record shape | `docs/products/optics/RECORD-REFERENCE.md` | Public. |
| Privacy | `docs/products/optics/PRIVACY-AND-SECURITY.md` | Public. |
| Current architecture bounds | [04-ARCHITECTURE.md](04-ARCHITECTURE.md) | This room. |
| Target store | `docs/architecture/optics-foundation/03-OPERATIONAL-STORE-AND-PORTABLE-PROOF.md` | Internal architecture. Not shipping. |
| Threat cases | `docs/architecture/optics-foundation/07-THREAT-MODEL.md` | Internal. Do not copy abuse paths into an investor appendix. |
| Evidence and privacy contract | `docs/architecture/optics-foundation/02-EVIDENCE-AND-PRIVACY-CONTRACT.md` | Internal architecture. |
| Documentation versions | `docs/governance/VERSION-METADATA.json` | Internal governance record of tree versions. |
| Public lineup | `docs/PRODUCT_LINEUP.md` | Public. |

## Kept out of the appendix

| Material | Reason |
| --- | --- |
| Kernel program lists and bypass write-ups | Hard exclude |
| Interceptor reproduction steps beyond the public manual | Company procedure and exploit-adjacent detail stay in source, not in this packet |
| `packages/optics-evidence-contract` detector internals | Private package. Not an investor appendix body. |
| Test workers under `tests/optics-evidence-contract/` | Repository tests. Not an appendix narrative. |
| Credentials and sample customer payloads | Hard exclude |

## Sections still empty

| Section | Value |
| --- | --- |
| Selected quotations | `NOT_FILLED` |
| Diagrams | `NOT_FILLED` |
| Phantom Engine appendix | `NOT_VERIFIED_IN_THIS_REPO` |
