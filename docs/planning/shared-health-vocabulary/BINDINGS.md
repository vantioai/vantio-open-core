# Bindings

Audience: INTERNAL_RESTRICTED

Producer classification: `SHARED_HEALTH_VOCABULARY_READY_FOR_COUNCIL`

This file says how existing consumers read the Workstream 4 catalog. It does not switch those consumers over in this pull request.

## 1. P24 health and coverage

P24's plan is `docs/planning/phantom-engine-production/04-P24-HEALTH-AND-COVERAGE.md`. Its current machine vocabulary is `docs/planning/phantom-engine-production/HEALTH-VOCABULARY.json`, which still says `vocabulary_status` `PENDING_WS4`.

When a later force is authorized to revise that packet, P24 reads subjects, protection states, verifier results, evidence classes, platform scope, platform status, and deployment profile from `docs/planning/shared-health-vocabulary/HEALTH-VOCABULARY.json` at the council-accepted commit. Until that revision, P24's packet remains the `PENDING_WS4` shape.

A P24 fact uses one channel:

- Node liveness is `subject` `LOADER`, `fact_kind` `LOADER_LIVENESS`, `heartbeat_age_limit_s` `60`, path `/run/vantio/heartbeat`, `freshness` `UNKNOWN`.
- Protection state is `fact_kind` `PROTECTION_EVALUATION` on `COVERAGE` or `LOADER`.
- Control-plane heartbeat is `subject` `CONTROL_PLANE`, `fact_kind` `CONTROL_PLANE_HEARTBEAT`, `interval_s` `NOT_COPIED`.

`COVERAGE-MATRIX.json` rows already carry `evidence_class`, `platform_scope`, and `this_force` `NOT_EXECUTED`. Those cells stay on those fields. This catalog does not mark any row executed.

## 2. Optics display, Unit A, and Unit F

Layer A owner: `docs/governance/STATUS-TOKENS.json` at commit `355545a25e2daaf1040ef2d9a5aafbba27284ceb`. Display source: `packages/vantio-cli/bin/optics-cx.cjs` `VOCABULARY`. Action source: `packages/vantio-agent-sdk/src/index.ts` `VantioActionTaken`.

PKG-02 Unit A vocabulary commit `4debf8cf319a0450246da32b3eae15958b94db61`, merge `587f3b94d47ea958f91d3a99125cd55931d995f1`. Unit A keeps `SUCCESS` in the `optics_status` enum and does not use it as a stored reading. CLI `0.3.24`, Node SDK `0.2.4`, and Python `3.1.0` stay frozen. This catalog does not reopen them.

PKG-02 Unit F reader commit `2c31764c9c55f6f9c5cd0e0d1ce762ad032867e3`, merge `4b1b85ad6af41b1bb54dc4c55cde16b711ae7dd4` (pull request #81, the base of this branch). Unit F `docs/internal/optics-pkg02-unit-f/DESIGN.md` says `optics_status` and `optics_health` never render `SUCCESS`. A stored or legacy `SUCCESS` becomes `UNAVAILABLE` and sets `optimistic_default_forbidden`. Explicit `OBSERVED` stays `OBSERVED`. `application_status` `SUCCESS` stays on the application dimension.

Binding:

- `optics_display` includes `SUCCESS` because the live display vocabulary and the Unit A enum include it.
- `optics_reader_display.renders_success` is false. The reader rule does not delete `SUCCESS` from `optics_display`.
- A fact with `fact_kind` `APPLICATION_STATUS` does not also set `optics_display`.
- `PRODUCT_HEALTH` names in A5 stay Optics diagnostics. P24 does not write them into `protection_state`.
- Frozen `displayCall` in the CLI can still return optics `SUCCESS` for a call row. Unit F calls that pairing unsupported and does not change `optics-cx.cjs`. This catalog also does not change it.

Optics freshness on the A4 envelope follows the same window: `NOT_SET`, so emitted freshness is `UNKNOWN`. Unknown freshness does not set query completeness.

## 3. Verifier

`verifier_result` is the Layer C list cited from blob `4c215cb2ebdff63a85c29094adb8dfbe2bb30dc7`. This force did not read that blob (`ACCESS_GAP`).

A verifier fact uses `fact_kind` `VERIFIER_RUN` and leaves `protection_state` null. `verifier_result` `BLOCKED` is an unavailable test environment. `ledger_action_taken` `BLOCKED` is a real drop. Those two facts are not one fact. `OPTIONAL_COMPONENT_ABSENT` is not `PASS`.

## 4. Evidence labels

`evidence_class` and `platform_status` stay the split already in the PE packet. `VERIFIED_ON_REFERENCE_HOST` is a platform status. `TESTED_LOCAL` is a platform status. `EXECUTED_IN_THIS_REMEDIATION` is an evidence class.

`platform_scope` `STRANGER_HOST` may be stored as the scope of a cell. Storing it does not prove the cell. `compatibility_status` `internally_proven` is the company-host name set from the protection-state module as P24 described it. It is not `platform_scope` `STRANGER_HOST`.

`UNVERIFIED`, `NOT_EXECUTED`, `NOT_EXECUTED_IN_THIS_PASS`, and `NOT_INDEPENDENTLY_VERIFIED` are not promoted.

Ledger facts use `subject` `LEDGER`. Local NDJSON stays append-oriented. The catalog has no `WORM` value. A live Spanner commit timestamp is a different fact and stays `UNVERIFIED` / `TARGET_DESIGN` as P24 already says.

## 5. Later PE packet revision

This pull request does not edit `docs/planning/phantom-engine-production/`.

A follow-on force that is allowed to revise that packet binds it like this:

1. Set `HEALTH-VOCABULARY.json` `vocabulary_status` from `PENDING_WS4` to the full git commit of the council-accepted Workstream 4 catalog.
2. Set `workstream_4` from `DEFINITION_NOT_RETRIEVED` to that same commit.
3. Point `05-SHARED-HEALTH-VOCABULARY.md` at `docs/planning/shared-health-vocabulary/`.
4. Leave `docs/governance/STATUS-TOKENS.json` unchanged. Do not publish Layer B names as Layer A display tokens.
5. Do not delete or merge collision rows from `COLLISION-MATRIX.json`.

Until that revision lands, consumers that read only the PE packet still see `PENDING_WS4`. Consumers that read this directory see the draft catalog and `bound_into_pe_packet` false.

## 6. Files this force does not change

- `docs/planning/phantom-engine-production/**`
- `docs/governance/STATUS-TOKENS.json` and the rest of `docs/governance/`
- `packages/vantio-cli/**`, `packages/vantio-agent-sdk/**`, `packages/vantio-agent-sdk-py/**`
- `packages/optics-record-vocabulary/**`, `packages/optics-record-reader/**`, `packages/optics-node-adapter/**`
- Unit D, Unit E, O7, and I3 surfaces
