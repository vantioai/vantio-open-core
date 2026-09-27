# WS4 shared health vocabulary — boundary

Audience: INTERNAL_RESTRICTED

Producer role: design and catalog only. This agent does not sit the independent council, does not self-assign a council pass, and does not authorize a probe, a load, a publish, or a deploy.

Producer identity: Cursor cloud agent `bc-17018458-81e4-592e-9017-8ea8dd4ae3c7`, model Grok 4.7.

Producer classification: `SHARED_HEALTH_VOCABULARY_READY_FOR_COUNCIL`

That classification means this catalog is ready for a separate council. It is not a council verdict, not a runtime, and not evidence that any host, loader, or ledger was proved in this force.

## 1. Locked input

| Item | Value |
| --- | --- |
| Writable repository | `vantioai/vantio-open-core` |
| Open-core base | `4b1b85ad6af41b1bb54dc4c55cde16b711ae7dd4` |
| Base subject | Merge pull request #81 from `vantioai/cursor/pkg02-unit-f-reader-compat-2409` |
| Planning branch | `cursor/ws4-shared-health-vocabulary-e3c7` |
| Writable paths | `docs/planning/shared-health-vocabulary/` and `tests/shared-health-vocabulary/` |
| PE packet left in place | `docs/planning/phantom-engine-production/` still records `vocabulary_status` `PENDING_WS4` |

## 2. Home

The catalog lives in `docs/planning/shared-health-vocabulary/`.

Layer A display and SDK action tokens stay owned by `docs/governance/STATUS-TOKENS.json`. This force does not edit that file. The shared catalog is the planning binding Workstream 3 left for Workstream 4, consumed by P24, with the same INTERNAL_RESTRICTED audience as the Phantom packaging packet. Phantom protection states stay in this planning catalog. They are not added to the Optics status-token file.

## 3. What this force does

- Publishes the Workstream 4 catalog from Layers A–E already cited on this base.
- Sets the freshness rule `FRESHNESS_WINDOW_NOT_SET_EMIT_UNKNOWN`.
- Preserves the Workstream 3 collision rows and records tighter rows that keep those layers apart.
- Records access gaps where private Phantom and enterprise blobs were not readable from this environment.
- Leaves `INDEPENDENT-COUNCIL.md` as `PENDING_INDEPENDENT_COUNCIL`.

`HEALTH-VOCABULARY.json` and `COLLISION-MATRIX.json` in this directory are the normative token lists and collision rows. The markdown explains them.

## 4. What this force keeps closed

- Live eBPF, loader, DaemonSet, kernel verifier, and probe curls.
- Stranger-host execution, customer hosts, and customer deploy.
- Unit D and Unit E writer activation, Optics store writes, and O7.
- I3 and any OpenTelemetry adapter enablement.
- CLI `0.3.24`, Node SDK `0.2.4`, and Python SDK `3.1.0` source, version, and publish changes.
- Edits to `docs/governance/STATUS-TOKENS.json`.
- Edits to `docs/planning/phantom-engine-production/`. That packet keeps `PENDING_WS4` until a later binding revision.
- npm, PyPI, GHCR, registry publish, tags, and announcements.
- Merge of this pull request. Council is a separate agent.
- Customer-manual bodies. The operations guide blob `1b973342b3bf7f6aa6cdad70de49fa6e26db0077` stays cited and uncopied.

## 5. Access gaps

Result for each unread private blob: `ACCESS_GAP`. This environment returned HTTP 404 for `vantioai/vantio-phantom-engine` and `vantioai/vantio-enterprise`. Local paths `/home/zach_vantio/vantio-phantom-engine` and `/mnt/c/Users/zach_vantio/vantio-phantom-engine` are absent.

| Gap | Cited path | Cited blob or tip |
| --- | --- | --- |
| `PE_PROTECTION_STATE_BLOB` | `python/pe_protection_state.py` | blob `a1b49fe6e431cdb574f0d285f7976236945519c7` at tip `631e435315cd780d83d3259e111893c1d0569bc3` |
| `PE_VERIFIER_CONTRACT_BLOB` | `docs/internal/VERIFIER_CONTRACT.md` | blob `4c215cb2ebdff63a85c29094adb8dfbe2bb30dc7` at the same tip |
| `PE_OPERATIONS_GUIDE` | `docs/operations-guide.md` | blob `1b973342b3bf7f6aa6cdad70de49fa6e26db0077`, class `CUSTOMER_SHIPPED` |
| `ENTERPRISE_CLOUD_PLATFORM_READINESS` | `vantio-enterprise` `scripts/cloud_platform_readiness.py` | blob `2b7e06901dcf2da2a97131709a215e794452545f` at tip `2df2d1f2d2e5a8e65c6d3021b20b94f179e485b7` |
| `LEDGER_ACTION_TAKEN_ENUM` | Phantom ledger `ActionTaken` | Open-core cites the spellings `BLOCKED` and `OBSERVED` only |
| `FOUNDER_MASTER_PROGRAM` | Not present in `vantio-open-core` | Catalog uses Layers A–E already on main |

Token lists for Layers A–E are the lists already written in open-core. This force does not invent additional protection states from an unread private body.

## 6. Evidence rule

Every coverage cell this catalog names keeps the class the Phantom packet already recorded. `UNVERIFIED`, `NOT_EXECUTED`, `NOT_EXECUTED_IN_THIS_PASS`, `NOT_INDEPENDENTLY_VERIFIED`, and `STRANGER_HOST` stay those labels. This force does not promote them.
