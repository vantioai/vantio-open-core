# Claim ledger

Audience: INTERNAL_RESTRICTED

Document status: SKELETON

Future slot: `INTERNAL_RESTRICTED`

Fill status: `INDEX_ONLY`

Investor send: `NOT_CLEARED`

External publication: PROHIBITED

## Purpose

List claims a later packet might want, each tied to a file in this repository, with evidence tier left unset. An index row is not clearance to speak the claim.

Evidence tier for every row: `UNSET`.

Investor clearance for every row: `NOT_CLEARED`.

## Rows

| ID | Claim, as supported by the source | Source | Evidence |
| --- | --- | --- | --- |
| CL-01 | Optics is free, local-first observability for AI agent egress. | `README.md` | `UNSET` |
| CL-02 | The Node path injects an interceptor with `NODE_OPTIONS --require`. | `README.md` | `UNSET` |
| CL-03 | The free record is destination, process, size, and timing. Prompts and completions are absent. | `README.md` | `UNSET` |
| CL-04 | A call that never hits the interceptor is not recorded. | `docs/governance/canonical/known-limitations.md` | `UNSET` |
| CL-05 | Browser paths stay outside this wrap. | `README.md` | `UNSET` |
| CL-06 | Without `vantio-agent-sdk`, prefixing `vantio run python` does not intercept. | `docs/governance/canonical/known-limitations.md` | `UNSET` |
| CL-07 | JSON records use `schema_status` `unstable-pre-1.0`. | `docs/governance/canonical/known-limitations.md` | `UNSET` |
| CL-08 | There is no OTLP exporter. | `docs/governance/canonical/known-limitations.md` | `UNSET` |
| CL-09 | Free Optics needs no account and no API key. | `README.md` | `UNSET` |
| CL-10 | Public lineup price for Phantom Engine is `$799/node/mo`. | `README.md`, `docs/PRODUCT_LINEUP.md` | `UNSET`. Product-spec re-read `NOT_VERIFIED_IN_THIS_REPO`. |
| CL-11 | Enterprise commercial motion in the public lineup is talk to sales. Certifications are not held. | `docs/PRODUCT_LINEUP.md` | `UNSET` |
| CL-12 | Gate is not a current standalone public SKU. | `docs/PRODUCT_LINEUP.md` | `UNSET` |
| CL-13 | `vantio prove` re-renders a local file and does not add a content hash or signature. The architecture pack's limitation phrase for portable proof is local export, not an external attestation. | `docs/products/optics/PRIVACY-AND-SECURITY.md`, `docs/architecture/optics-foundation/00-PROGRAM-BOUNDARY.md` | `UNSET` |
| CL-14 | Store option C is ratified as architecture only. Gate 8 is closed. | `docs/architecture/optics-foundation/09-IMPLEMENTATION-GATES.md` | `UNSET` |
| CL-15 | The evidence-contract and record-vocabulary packages are not imported by the live CLI or SDKs at the base commit of this room. | Import search at `5064f32f1cdfcb840dfd100e2ce5c712d046550d` | `UNSET` |

## How to add a row

1. Name the source path and the commit that was read.
2. Keep the evidence tier `UNSET` until [08-PROOF-TAXONOMY.md](08-PROOF-TAXONOMY.md) is actually satisfied and a separate record says so.
3. Leave investor clearance `NOT_CLEARED` until a human promotes a redacted subset.
4. Reject the row when the support is an unsourced statistic, a customer story, or a Phantom Engine body that is not in this repository.

## Rows this ledger refuses

Customer quotes, design-partner names, fund amounts, headcount, kernel bypass results, and any claim that repository unit tests are `STRANGER_HOST_PROVED`, `PROVED_EXTERNAL`, or `CUSTOMER_VALIDATED`.
