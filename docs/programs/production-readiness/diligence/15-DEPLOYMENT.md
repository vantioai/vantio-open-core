# Deployment

Audience: INTERNAL_RESTRICTED

Document status: SKELETON

Future slot: `INVESTOR_UNDER_NDA`

Fill status: `NOT_FILLED`

Investor send: `NOT_CLEARED`

External publication: PROHIBITED

## Purpose

Reserve a deployment chapter that points at the public Optics install document. This file is not a runbook.

## Optics

| Topic | Where the public text lives | This room |
| --- | --- | --- |
| Install | `docs/products/optics/INSTALLATION.md`, `README.md` | Pointer only |
| Supported runtimes | `README.md` | macOS, Linux, and Windows (WSL), as the README states. Re-read before sending. |
| Node injection scope | `docs/governance/canonical/known-limitations.md` | `node`, `npx`, `tsx`, `ts-node` |
| Python | `docs/products/optics/PYTHON-GUIDE.md` | Describe the installed version, not unpublished source, unless the sentence is labeled unpublished. |
| Uninstall | `docs/products/optics/UPGRADE-ROLLBACK-UNINSTALL.md` | Pointer only |

Free Optics needs no account and no API key.

## Phantom Engine

Deployment, enrollment, and host operations live in the Phantom Engine repository. Status in this room: `NOT_VERIFIED_IN_THIS_REPO`.

Do not paste an operations guide here. Do not describe kernel installation, cluster enrollment, or traffic-drop behavior.

## Sections still empty

| Section | Value |
| --- | --- |
| Reference topology | `NOT_FILLED` |
| Account or tenancy model | `NOT_FILLED` |
| Customer-specific deployment | Prohibited. Use the pilot slot with values still `REDACTED`. |
| Production-cluster claim | `NOT_SET` |

## Fill rules

- An investor deployment page for Optics can quote the public install document after a fresh read.
- A sentence about enrolled hosts stays at the altitude of `docs/PRODUCT_LINEUP.md` until the Phantom Engine source of truth is re-read.
- Company operating procedures stay out.
