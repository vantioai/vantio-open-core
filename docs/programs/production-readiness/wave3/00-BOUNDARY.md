# Wave 3 Track 1 boundary

Audience: INTERNAL_RESTRICTED

Force: independent council for Founder decision 9, the Node SQLite binding.

Starting commit: `0620f10ee52d3abcea18c1c988df02f687f51b36`.

The ratified engine stays embedded SQLite with WAL and an application-owned schema. This track selects the Node binding. It does not implement it.

## In scope

- Compare repository-compatible Node bindings against the store contract.
- Record the selection, the version pin, the fallback, rollback, platforms, and the release impact.
- Leave a verdict in this directory and the decision packet under `docs/internal/optics-o7/`.

## Out of scope

- Editing `@vantio/cli` `0.3.24`, `@vantio/agent-sdk` `0.2.4`, or `vantio-agent-sdk` `3.1.0`.
- Adding an npm dependency, a native addon, or a `node:sqlite` import.
- Creating `store.sqlite`, migrating customer data, or copying legacy JSON.
- Opening Gate 8, assigning an evidence tier, or claiming a host proof.
- Publishing, tagging, announcing, issuing credentials, or spending money.
- Rewriting `docs/architecture/optics-foundation/08-ARCHITECTURE-DECISION-PACK.md`, `docs/planning/optics-o7-store/STORE-MANIFEST.json`, or `docs/planning/optics-production/PACKAGES.json`. Those files keep the sentences their tests already lock. This track's record is the selection those sentences do not yet carry.

## Verdict location

`docs/programs/production-readiness/wave3/10-COUNCIL.md`

Machine-readable copy: `docs/programs/production-readiness/wave3/O7-NODE-BINDING-DECISION.json`

Packet: `docs/internal/optics-o7/00-BINDING-DECISION.md`
