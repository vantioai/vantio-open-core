# Track 0 boundary — Wave 2 authority reconciliation

Audience: INTERNAL_RESTRICTED

Producer: Cursor cloud agent `bc-dc0c9f02-6053-5065-b948-8034e493f0e1`, model Grok 4.7. This agent records the superseding authority. It does not sit the independent council and it does not assign a council pass.

Classification: `WAVE2_AUTHORITY_RECONCILED_READY_FOR_COUNCIL`

That classification means the reconciliation is ready for a separate council. It is not a council verdict, not a merge, and not permission to execute stranger-host, announce, or publish.

## Locked input

| Item | Value |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Base commit | `89f95099d0dce463307eb75d78e7fcf2ef99feb2` |
| Base subject | Merge pull request #83 from `vantioai/cursor/pe-ws4-vocabulary-binding-f9f5` |
| Authority date | 2026-09-27 |
| Entry | `docs/programs/production-readiness/authority/WAVE2-AUTHORITY.json` |

## Writable paths

- `docs/programs/production-readiness/MASTER-MANIFEST.json` — additive `superseding_authority` pointer only
- `docs/programs/production-readiness/WORKSTREAM-REGISTRY.json` — same pointer
- `docs/programs/production-readiness/DECISION-REGISTER.json` — same pointer
- `docs/programs/production-readiness/RELEASE-REGISTER.json` — same pointer
- `docs/programs/production-readiness/authority/`
- `tests/wave2-authority/`

Every other path stays as it is on the base commit. Historical fields inside the four registers stay as the 2026-09-27T07:44:14Z refresh. The pointer is the only added key.

## What this force does

- Records one superseding authority entry for the Founder Wave 2 authorization dated 2026-09-27.
- Points each of the four registers at that entry with the same object.
- States the reading rule: on a conflict, the entry is the current authority, and the earlier field remains the refresh observation.
- Records WS11 R1–R18 as the one-line labels from the Track 14 founder brief.
- Keeps stranger-host execution blocked pending a named host and a named operator.
- Keeps announcements on HOLD.
- Records Wave 1 closed as the executable design foundation at the base commit.

## What stays closed in this force

| Stop | State |
| --- | --- |
| Customer deploy | Closed |
| Stranger-host execution | Blocked pending named host and named operator |
| Announcements | HOLD |
| Credential create or rotate | Closed |
| Money movement | Closed |
| Reopen `@vantio/cli` 0.3.24 | Closed |
| Mutate sealed or published Python 3.1.0 bytes | Closed |
| Merge Phantom Engine customer-confidential material to public main | Closed |
| Formal SLSA level, certification, proved reproducibility, or hardware-backed provenance | Unclaimed |
| Promotion of internal proof to external proof | Closed |
| Merge of this pull request | Closed until a later merge force |

## Checks

```
node --test tests/wave2-authority/*.test.cjs
node --test docs/scripts/check-docs-release.test.mjs
```

The authority tests pass on this branch. The documentation release check already fails on the accepted main: `legacy-stale-name-inventory-frozen` reports `tests/shared-health-vocabulary/collision.test.cjs`. That file names a retired product string inside an assertion that catalog text excludes it. This force does not edit that test or the frozen inventory.

## Document order

1. `00-INVENTORY.md`
2. `01-BOUNDARY.md`
3. `02-ARCHITECTURE-COUNCIL-NOTES.md`
4. `WAVE2-AUTHORITY.json`
