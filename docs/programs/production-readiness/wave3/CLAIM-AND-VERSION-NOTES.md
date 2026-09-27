# Wave 3 Track 1 claim and version notes

Audience: INTERNAL_RESTRICTED

Observed: 2026-09-27. Starting commit `0620f10ee52d3abcea18c1c988df02f687f51b36`.

`docs/governance/VERSION-METADATA.json` is unchanged. `docs/programs/production-readiness/CLAIM-LEDGER.json` is unchanged. That ledger is the 2026-09-27T07:44:14Z refresh snapshot. These notes are the Wave 3 Track 1 claims.

## Versions observed and left in place

| Package | Version | Manifest |
| --- | --- | --- |
| `@vantio/cli` | `0.3.24` | `packages/vantio-cli/package.json` |
| `@vantio/agent-sdk` | `0.2.4` | `packages/vantio-agent-sdk/package.json` |
| `vantio-agent-sdk` | `3.1.0` | `packages/vantio-agent-sdk-py/pyproject.toml` |
| `@vantio/optics-operational-store` | `0.0.0-unstable-pre-1.0` | `packages/optics-operational-store/package.json` |

No changelog heading is added. No tag is created. No registry publish is requested.

## Claims

| Id | Status | Claim |
| --- | --- | --- |
| `CL-W3-O7-01` | `EVIDENCE_RECORDED` | Decision 9 selects `node:sqlite@24.15.0`. The engine remains embedded SQLite with WAL. |
| `CL-W3-O7-02` | `EVIDENCE_RECORDED` | CLI `0.3.24`, Node SDK `0.2.4`, and Python SDK `3.1.0` are unmodified. |
| `CL-W3-O7-03` | `NOT_ASSERTED` | Runtime proof, stranger-host proof, external proof, Gate 8, and customer migration. |

`CL-W3-O7-01` records a document decision. The process on this commit still returns `NODE_BINDING_UNSELECTED` from Node `openStore`. Evidence tier stays `UNSET`. Gate 8 stays closed.

Machine-readable copy of the same three claims: `docs/programs/production-readiness/wave3/O7-NODE-BINDING-DECISION.json`.
