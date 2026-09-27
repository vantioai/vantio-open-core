# Diligence room boundary

Audience: INTERNAL_RESTRICTED

Document status: CONTROL

External publication: PROHIBITED

Producer: Cursor cloud agent `bc-c4fccba6-6357-58cd-b731-f935d88a31a9`, model Grok 4.7.

Producer URL: https://cursor.com/agents/bc-c4fccba6-6357-58cd-b731-f935d88a31a9

Base commit: `5064f32f1cdfcb840dfd100e2ce5c712d046550d` (`origin/main` at the time this branch was cut).

Writable path for this force: `docs/programs/production-readiness/diligence/` only.

## Purpose

Provide a controlled outline for a later investor diligence packet:

- category thesis
- product ladder
- architecture
- threat model and privacy model
- claim ledger
- proof taxonomy
- capabilities
- target architecture
- build status
- demo guide
- technical appendix
- release discipline
- deployment
- pilot
- design partner
- stranger-host gate
- roadmap
- differentiation
- use of funds
- hiring plan
- evidence index
- limitations
- risks

The outline names the section, the source a later author must re-read, and the value `NOT_FILLED`, `NOT_SET`, `UNSET`, or `REDACTED`. It does not supply the investor narrative.

## What this force keeps closed

- Website copy, announcements, and changes to `README.md` or `docs/governance/canonical/`
- Package version bumps, tags, npm publish, and PyPI publish
- Product code, tests, and package metadata
- A Phantom Engine customer manual, a private manual, or a customer bundle
- Credentials, customer names, customer workloads, and private prompts
- Company operating procedures, including billing, banking, and release execution steps
- Kernel bypass detail and exploit material
- Any assignment of `UNIT_PROVED`, `INTEGRATION_PROVED`, `STRANGER_HOST_PROVED`, `PROVED_EXTERNAL`, or `CUSTOMER_VALIDATED`

## Hard exclude

These bodies do not belong in this directory, including inside a skeleton "example":

| Exclude | Handling |
| --- | --- |
| Kernel bypass detail | Name the separate Phantom Engine repository. Do not describe probes, drop paths, or bypass steps. |
| Exploit material | Threat and risk skeletons name impact classes. They do not reproduce procedures. |
| Credentials | No keys, tokens, connection strings, or secret values. |
| Customer information | Pilot and design-partner fields stay `REDACTED` or `NOT_SET`. |
| Private prompts | No prompt text, completion text, or customer conversation. |
| Company operating procedures | Release and deployment skeletons point at existing docs. They do not restate how to publish, bill, or operate the company. |
| Phantom Engine customer confidential bodies | `docs/governance/PE-CUSTOMER-BUNDLE.json` records that this repository does not contain a Phantom Engine customer manual. Do not add one. Do not copy a customer bundle into this path. |

Prohibited filenames and path fragments if a later author is tempted to add them: `PRIVATE-MANUAL`, `CUSTOMER-MANUAL`, `phantom-engine/customer/`, `pe-customer/`, `customer-confidential`. The tier token `CUSTOMER_CONFIDENTIAL` is a handling label. It is not a directory name.

Retired public names listed in `docs/governance/STALE-NAMES.json` stay out of this room. Repeating them would add a new stale-name file and fail `node docs/scripts/check-docs-release.mjs`.

## Prohibited claims

A later fill must not introduce mechanisms or figures that this repository does not support. In particular, leave these unstated unless a named source file in the relevant repository is re-read and cited:

- Cryptographic proof systems, zkVMs, or rollup batches as the audit mechanism
- MicroVMs or hardware TEEs as a built isolation boundary
- A user-space or WebAssembly stand-in for host enforcement
- AST rewriting as the Optics observe mechanism
- Unsourced market, speed, cost, or CPU statistics
- Certification marks. `docs/PRODUCT_LINEUP.md` records that certifications are not held

Optics observe, in this repository, is the `NODE_OPTIONS --require` interceptor described in `README.md`, plus the Python `shield()` path. Phantom Engine is a different repository. This room does not restate that repository's build status.

## Publication

This force does not publish externally. Files may land on the default branch of `vantio-open-core` only as internal scaffold text. That git landing is not a data-room release, a website release, or an investor send.

Investor send status for every file: `NOT_CLEARED`.

## Evidence

This room assigns no proof tier. Repository tests remain repository tests. Producer completion of the scaffold is not proof.
