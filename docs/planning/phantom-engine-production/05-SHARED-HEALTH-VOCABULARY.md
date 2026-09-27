# Shared health vocabulary

Audience: INTERNAL_RESTRICTED

Producer classification: `PHANTOM_WAVE1_PACKAGING_HEALTH_PLAN_READY_FOR_COUNCIL`

Workstream 4 status: `DEFINITION_NOT_RETRIEVED`

The founder force names Workstream 4 as the source of the shared health vocabulary. No Workstream 4 document, token list, or path was in `vantio-open-core` at base `5064f32f1cdfcb840dfd100e2ce5c712d046550d`, and no completed Workstream 4 producer output was available to this force. This file binds P24 to vocabularies that already exist in git. It does not ratify a Workstream 4 catalog. Field `vocabulary_status` in `HEALTH-VOCABULARY.json` stays `PENDING_WS4`.

## 1. Layers that already have owners

### Layer A — Optics display and SDK action tokens

Owner: open-core `docs/governance/STATUS-TOKENS.json` at the planning base. Display tokens come from `packages/vantio-cli/bin/optics-cx.cjs`. Action tokens come from `packages/vantio-agent-sdk/src/index.ts`.

Display: `OBSERVED`, `NOT_OBSERVED`, `UNSUPPORTED`, `UNAVAILABLE`, `APPLICATION_ERROR`, `OPTICS_ERROR`, `PARTIAL`, `SUCCESS`.

Action: `OBSERVED`, `ALLOWED`, `REDACTED`, `BLOCKED_HOST`, `BLOCKED_SIZE`, `BLOCKED_SPEND`, `ENFORCEMENT_GAP`, `DRY_RUN_BLOCKED_HOST`, `DRY_RUN_BLOCKED_SIZE`, `DRY_RUN_BLOCKED_SPEND`.

Optics architecture `docs/architecture/optics-foundation/06-SELF-OBSERVABILITY-AND-RELIABILITY.md` adds `PRODUCT_HEALTH` diagnostic names (`hooks_installed`, `events_dropped`, and the rest of that list). Those names stay Optics records. P24 does not write them into the Phantom protection state.

### Layer B — Phantom protection states

Owner: `vantio-phantom-engine` `python/pe_protection_state.py` blob `a1b49fe6e431cdb574f0d285f7976236945519c7`.

`protected`, `observing`, `not_enrolled`, `protection_stale`, `policy_stale`, `degraded`, `quarantined`, `recovery_required`, `coverage_unknown`.

### Layer C — Independent verifier results

Owner: `docs/internal/VERIFIER_CONTRACT.md` blob `4c215cb2ebdff63a85c29094adb8dfbe2bb30dc7`.

`PASS`, `FAIL`, `NOT_APPLICABLE`, `OPTIONAL_COMPONENT_ABSENT`, `REQUIRED_DEPENDENCY_MISSING`, `NOT_TESTED`, `BLOCKED`.

### Layer D — Evidence and platform labels

From the remediation register, the test-evidence manifest, the product spec, and `vantio-enterprise` `scripts/cloud_platform_readiness.py`:

`EXECUTED_IN_THIS_REMEDIATION`, `OBSERVED_FROM_REPOSITORY_EVIDENCE`, `NOT_INDEPENDENTLY_VERIFIED`, `NOT_EXECUTED_IN_THIS_PASS`, `VERIFIED_ON_REFERENCE_HOST`, `DOCUMENTED_REQUIREMENT`, `UNVERIFIED`, `TESTED_LOCAL`, `TARGET_DESIGN`.

`compatibility_status` values in the protection-state module: `internally_proven`, `not_stranger_proven`.

### Layer E — Deployment profile

`bundled_gate`, `no_gate`, `unknown`.

## 2. Collision rules

These names share spelling across layers and keep separate fields.

| Spelling | Field that may hold it | Field that must not hold it |
| --- | --- | --- |
| `BLOCKED` | Verifier `verifier_result` when the test environment is unavailable. Ledger `ActionTaken` when a real drop was attributed | Protection `state`. Optics display vocabulary |
| `OBSERVED` | Optics display. Wire `ActionTaken` for a TLS uprobe pass-through | Protection `state`. A pass-through observation is not `protected` |
| `ALLOWED` | Phantom product label for pass-through, as the cloud checklist distinguishes it from the wire word `OBSERVED`. SDK action token when a policy allows a call | Protection `state` |
| `PARTIAL` | Optics mixed-run rollup | A Phantom coverage percentage. Coverage in this packet is a named gap, not a percentage |
| `SUCCESS` | Optics status when an observation record was stored | Protection `state` |
| `UNKNOWN` / `unknown` / `coverage_unknown` | Honest absence: freshness, deployment profile unset, or protection fallback | A synonym for `protected` |
| `CURRENT` | Not emitted. Optics freshness window is `NOT_SET` | A substitute for a heartbeat file younger than 60 seconds |

`OPTIONAL_COMPONENT_ABSENT` is not `PASS`. `internally_proven` is not `STRANGER_HOST`. `KIND_LOCAL` is not `MANAGED_CLOUD`. `TESTED_LOCAL` is not a customer-validation field.

## 3. Shared fact a later force may emit

`HEALTH-VOCABULARY.json` is the shape. One fact has one `subject`:

`ARTIFACT`, `HOST_PREREQUISITE`, `LOADER`, `COVERAGE`, `CONTROL_PLANE`, `LEDGER`.

`protection_state` is null unless `subject` is `COVERAGE` or `LOADER`. `verifier_result` is null unless the fact is a verifier run. `freshness` stays `UNKNOWN` until Workstream 4 sets a window. The DaemonSet’s 60-second file age is `heartbeat_age_limit_s` on the `LOADER` subject. It is not `freshness: CURRENT`.

Workstream 4 may add names. It may not reuse a Layer A token as a Layer B state, and it may not collapse the collision rows in section 2. If Workstream 4 publishes a catalog, a later revision of this packet replaces `PENDING_WS4` with that catalog’s commit. This revision does not invent that commit.

## 4. Open-core status-token file

This plan does not edit `docs/governance/STATUS-TOKENS.json`. Phantom protection states are private-engine names. Publishing them as Optics display tokens would mix Observe with Control.
