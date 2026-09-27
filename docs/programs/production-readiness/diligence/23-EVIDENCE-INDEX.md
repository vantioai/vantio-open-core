# Evidence index

Audience: INTERNAL_RESTRICTED

Document status: SKELETON

Future slot: `INTERNAL_RESTRICTED`

Fill status: `POINTERS_ONLY`

Investor send: `NOT_CLEARED`

External publication: PROHIBITED

## Purpose

Point at evidence classes that exist in this repository. Pointers are not tier assignments. Every evidence tier below is `UNSET`.

## Index

| ID | Class | Where to look | Tier |
| --- | --- | --- | --- |
| EV-01 | Public manual matched to recorded versions | `docs/products/optics/README.md`, `docs/products/optics/VERSION-METADATA.json` | `UNSET` |
| EV-02 | Canonical limitation sentences | `docs/governance/canonical/known-limitations.md` | `UNSET` |
| EV-03 | Documentation release checker | `docs/scripts/check-docs-release.mjs` | `UNSET` |
| EV-04 | CLI tests | `packages/vantio-cli/test/` | `UNSET` |
| EV-05 | Node SDK tests | `packages/vantio-agent-sdk` test scripts in that package | `UNSET` |
| EV-06 | Python SDK tests | `packages/vantio-agent-sdk-py/tests/` | `UNSET` |
| EV-07 | Release-governance unit tests | `scripts/release/governance.test.mjs` and the Python tests beside it | `UNSET` |
| EV-08 | Private evidence-contract corpus | `packages/optics-evidence-contract`, `tests/optics-evidence-contract/` | `UNSET`. Private. Not a live integration. |
| EV-09 | Private record-vocabulary fixtures | `packages/optics-record-vocabulary` | `UNSET`. Not imported by the live CLI or SDKs at this room's base commit. |
| EV-10 | Architecture council record | `docs/architecture/optics-foundation/10-INDEPENDENT-COUNCIL-REPORT.md` | Document result. Not an evidence tier. |
| EV-11 | Stranger-host record | [18-STRANGER-HOST-GATE.md](18-STRANGER-HOST-GATE.md) | Absent. `UNSET`. |
| EV-12 | Customer workload | [16-PILOT.md](16-PILOT.md) | Body prohibited. `UNSET`. |
| EV-13 | Phantom Engine live verification | Phantom Engine repository | `NOT_VERIFIED_IN_THIS_REPO` |

## How to attach a result later

Record the command, the commit, the host class, and the tier name from [08-PROOF-TAXONOMY.md](08-PROOF-TAXONOMY.md). Store logs that contain secrets outside this directory. Do not paste those logs here.

## What this index refuses to link

Exploit write-ups, kernel bypass notes, credential files, customer prompts, and Phantom Engine customer manuals.
