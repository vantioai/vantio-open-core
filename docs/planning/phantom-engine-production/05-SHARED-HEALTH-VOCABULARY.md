# Shared health vocabulary

Audience: INTERNAL_RESTRICTED

Producer classification: `PHANTOM_WAVE1_PACKAGING_HEALTH_PLAN_READY_FOR_COUNCIL`

Binding classification: `PE_WS4_VOCABULARY_BINDING_READY_FOR_COUNCIL`

Workstream 4 status: `c1de02538f66df94d58aef58bf0ec8459ae797ad`

P24 reads the shared health vocabulary from `docs/planning/shared-health-vocabulary/` at commit `c1de02538f66df94d58aef58bf0ec8459ae797ad`. That commit is on main at merge `52274708e2620cbd37b0d10d67561eac642e2aee` (pull request #82). The council result cited here is `SHARED_HEALTH_VOCABULARY_COUNCIL_PASSED` (`bc-84572b17`). The merge classification is `SHARED_HEALTH_VOCABULARY_MERGED_CATALOG_ONLY`.

`HEALTH-VOCABULARY.json` sets `vocabulary_status` and `workstream_4` to that catalog commit, using `docs/planning/shared-health-vocabulary/BINDINGS.md` section 5. The previous `vocabulary_status` was `PENDING_WS4`. The previous `workstream_4` was `DEFINITION_NOT_RETRIEVED`. The commit in `vocabulary_status` means `BOUND_TO_WS4_CATALOG`. The same commit in `workstream_4` means `RETRIEVED_AND_BOUND`.

The cited catalog commit records `bound_into_pe_packet` false, and `docs/planning/shared-health-vocabulary/HEALTH-VOCABULARY.json` on this branch still records that field false. This packet is the binding in `BINDINGS.md` section 5. Vocabulary lists, `COLLISION-MATRIX.json`, and `BINDINGS.md` match that commit. This branch updates `docs/planning/shared-health-vocabulary/PLANNING-MANIFEST.json` only so its SHA-256 of `tests/shared-health-vocabulary/catalog.test.cjs` matches the binding test.

Freshness follows catalog rule `FRESHNESS_WINDOW_NOT_SET_EMIT_UNKNOWN`. The window is `NOT_SET`. The emitted freshness value is `UNKNOWN`.

At open-core base `5064f32f1cdfcb840dfd100e2ce5c712d046550d` this repository had no Workstream 4 catalog. The pointer above is that catalog. Layers A–E stay separate. Section 2 keeps its collision rows. Customer-manual bodies stay uncopied.

`00-PLANNING-BOUNDARY.md` records Workstream 4 as `DEFINITION_NOT_RETRIEVED` in the locked input verified at that planning base. `06-INDEPENDENT-COUNCIL.md` remains the wave-1 producer stub. Its checklist still names the pre-binding `vocabulary_status` `PENDING_WS4`. That stub stays the wave-1 record.

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

## 3. Shared fact

`docs/planning/shared-health-vocabulary/HEALTH-VOCABULARY.json` at `c1de02538f66df94d58aef58bf0ec8459ae797ad` is the normative shape. `docs/planning/phantom-engine-production/HEALTH-VOCABULARY.json` keeps the same subjects, protection states, verifier results, evidence classes, platform scope, platform status, and deployment profile. One fact has one `subject`:

`ARTIFACT`, `HOST_PREREQUISITE`, `LOADER`, `COVERAGE`, `CONTROL_PLANE`, `LEDGER`.

`protection_state` is set on `fact_kind` `PROTECTION_EVALUATION` when `subject` is `COVERAGE` or `LOADER`. `verifier_result` is set on `fact_kind` `VERIFIER_RUN`. `freshness` stays `UNKNOWN` under `FRESHNESS_WINDOW_NOT_SET_EMIT_UNKNOWN`. The DaemonSet’s 60-second file age is `heartbeat_age_limit_s` on the `LOADER` subject. It is not `freshness: CURRENT`.

Normative collision rows are `docs/planning/shared-health-vocabulary/COLLISION-MATRIX.json`. Section 2 of this file stays as written, with those rows unmerged. Layer B names stay out of `docs/governance/STATUS-TOKENS.json`. The catalog commit above replaces the previous `vocabulary_status` `PENDING_WS4`.

## 4. Open-core status-token file

This plan does not edit `docs/governance/STATUS-TOKENS.json`. Phantom protection states are private-engine names. Publishing them as Optics display tokens would mix Observe with Control.
