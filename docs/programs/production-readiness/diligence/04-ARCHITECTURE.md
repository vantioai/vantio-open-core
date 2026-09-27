# Architecture

Audience: INTERNAL_RESTRICTED

Document status: SKELETON

Future slot: `INVESTOR_UNDER_NDA`

Fill status: `NOT_FILLED`

Investor send: `NOT_CLEARED`

External publication: PROHIBITED

## Purpose

Describe, at investor altitude, what this repository implements today. The narrative stays `NOT_FILLED`. The bounds below are the bounds a later fill has to keep.

## Current Optics path in this repository

| Path | Where it is stated | Bound |
| --- | --- | --- |
| Node | `README.md` | `vantio run` injects the interceptor with `NODE_OPTIONS --require` for `node`, `npx`, `tsx`, and `ts-node`. |
| Python | `README.md`, `docs/governance/canonical/known-limitations.md` | `shield()` in `vantio-agent-sdk`. Prefixing `vantio run python` does not intercept by itself. |
| Record | `README.md` | Destination, process, size, and timing. Prompts and completions stay out of the free record. |
| Store today | `docs/products/optics/KNOWN-LIMITATIONS.md` | One JSON file per trace id. A database is absent. |
| Browser | `README.md` | Browser paths stay outside this wrap. |

`CONTRIBUTING.md` places this repository in user space. Kernel programs belong in the Phantom Engine repository. This file does not describe them.

## Architecture pack versus shipping code

`docs/architecture/optics-foundation/` is an internal architecture pack. Store option C is `FOUNDER_RATIFIED_ARCHITECTURE_ONLY`. Gate 8 in `docs/architecture/optics-foundation/09-IMPLEMENTATION-GATES.md` is closed. The pack is not the shipping CLI.

`packages/optics-evidence-contract` and `packages/optics-record-vocabulary` are private. At base commit `5064f32f1cdfcb840dfd100e2ce5c712d046550d`, `packages/vantio-cli`, `packages/vantio-agent-sdk`, and `packages/vantio-agent-sdk-py` do not import them.

## Sections still empty

| Section | Value |
| --- | --- |
| Diagram | `NOT_FILLED` |
| Trust boundaries for an investor page | `NOT_FILLED` |
| Phantom Engine component list | `NOT_VERIFIED_IN_THIS_REPO` |
| Failure behavior under load | Numeric budgets in the architecture pack are `NOT_SET` |

## Fill rules

- Describe the interceptor at the same altitude as `README.md`.
- Keep kernel mechanism, bypass steps, and exploit material out. See [05-THREAT-MODEL.md](05-THREAT-MODEL.md).
- A sentence about host enforcement cites the Phantom Engine repository and the public lineup. It does not import that repository's internal design into this file.
