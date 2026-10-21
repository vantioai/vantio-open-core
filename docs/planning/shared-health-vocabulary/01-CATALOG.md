# Shared health vocabulary catalog

Audience: INTERNAL_RESTRICTED

Producer classification: `SHARED_HEALTH_VOCABULARY_READY_FOR_COUNCIL`

Schema: `0.1.0-design` (`stable_schema` false). This is a design catalog. It is not a health CLI and not a stable runtime schema.

Normative token lists and fact rules: `HEALTH-VOCABULARY.json`. Normative collision rows: `COLLISION-MATRIX.json`.

## 1. Subjects

Workstream 3 named six subjects. This catalog does not add a seventh. Optics display is a field, not a subject.

| Subject | What a fact under it is about |
| --- | --- |
| `ARTIFACT` | Package, image, chart, or other artifact provenance |
| `HOST_PREREQUISITE` | Host prerequisite or compatibility |
| `LOADER` | Node loader liveness, or a protection evaluation about the loader |
| `COVERAGE` | Protection evaluation or a named coverage gap |
| `CONTROL_PLANE` | Optional control-plane heartbeat |
| `LEDGER` | Evidence plane (local NDJSON or a Spanner claim) |

`protection_state` is set only when `subject` is `COVERAGE` or `LOADER` and `fact_kind` is `PROTECTION_EVALUATION`. `verifier_result` is set only when `fact_kind` is `VERIFIER_RUN`.

## 2. Field separation

Each name below is its own field. A fact has one `fact_kind`. That kind may set one status field. Evidence fields may sit beside a protection evaluation. They do not rewrite it.

| Field | Layer | Owner already on main |
| --- | --- | --- |
| `protection_state` | B | Phantom `python/pe_protection_state.py`, cited by the PE packet. This force: `ACCESS_GAP` |
| `verifier_result` | C | Phantom `docs/internal/VERIFIER_CONTRACT.md`, cited by the PE packet. This force: `ACCESS_GAP` |
| `optics_display` | A | `docs/governance/STATUS-TOKENS.json` display tokens, from `packages/vantio-cli/bin/optics-cx.cjs` |
| `sdk_action` | A | `docs/governance/STATUS-TOKENS.json` action tokens, from `packages/vantio-agent-sdk/src/index.ts` `VantioActionTaken` |
| `application_status` | A | Workload outcome in `docs/governance/canonical/status-tokens.md` |
| `evidence_class` | D | PE packet `HEALTH-VOCABULARY.json` |
| `platform_scope` | D | PE packet `COVERAGE-MATRIX.json` / `HEALTH-VOCABULARY.json` |
| `platform_status` | D | PE packet `HEALTH-VOCABULARY.json` |
| `deployment_profile` | E | PE packet: `bundled_gate`, `no_gate`, `unknown` |
| `compatibility_status` | D | PE vocabulary prose: `internally_proven`, `not_stranger_proven` |
| `ledger_action_taken` | Ledger | Spellings cited in Workstream 3 section 2 only: `BLOCKED`, `OBSERVED`. Enum is partial |
| `pass_through_product_label` | Product label | Spelling cited in section 2: `ALLOWED` |
| `freshness` | Freshness | Rule in section 4 of this file |
| `heartbeat_age_limit_s` | Loader liveness | DaemonSet file age `60`. Not freshness |

Optics envelope fields (`query_completeness`, `integrity_state`, `sampling_state`, `drop_state`, `completeness_reason`, `run_lifecycle`, `issue_location`, `migration_state`, `telemetry_last_result`, `product_health_name`) are owned by Optics architecture and PKG-02. They are cataloged so shared spellings stay on those fields. They are not Phantom protection states and they are not new subjects.

### Layer B — `protection_state`

`protected`, `observing`, `not_enrolled`, `protection_stale`, `policy_stale`, `degraded`, `quarantined`, `recovery_required`, `coverage_unknown`.

### Layer C — `verifier_result`

`PASS`, `FAIL`, `NOT_APPLICABLE`, `OPTIONAL_COMPONENT_ABSENT`, `REQUIRED_DEPENDENCY_MISSING`, `NOT_TESTED`, `BLOCKED`.

`OPTIONAL_COMPONENT_ABSENT` is a verifier result of its own. It is not `PASS`.

### Layer A — `optics_display`

`OBSERVED`, `NOT_OBSERVED`, `UNSUPPORTED`, `UNAVAILABLE`, `APPLICATION_ERROR`, `OPTICS_ERROR`, `PARTIAL`, `SUCCESS`.

`SUCCESS` stays in this list because `STATUS-TOKENS.json`, `optics-cx.cjs`, and PKG-02 Unit A keep it in `optics_status`. Unit F's reader refuses to render it. That reader rule does not delete the token. See `BINDINGS.md`.

### Layer A — `sdk_action`

`OBSERVED`, `ALLOWED`, `REDACTED`, `BLOCKED_HOST`, `BLOCKED_SIZE`, `BLOCKED_SPEND`, `ENFORCEMENT_GAP`, `DRY_RUN_BLOCKED_HOST`, `DRY_RUN_BLOCKED_SIZE`, `DRY_RUN_BLOCKED_SPEND`.

Bare `BLOCKED` is not any of those SDK tokens.

### Layer A — `application_status`

`SUCCESS` for HTTP 200–399, `APPLICATION_ERROR` for HTTP 400–599, `UNAVAILABLE` otherwise. Workload `SUCCESS` stays on this field.

### Layer D and E

`evidence_class`: `EXECUTED_IN_THIS_REMEDIATION`, `OBSERVED_FROM_REPOSITORY_EVIDENCE`, `NOT_INDEPENDENTLY_VERIFIED`, `NOT_EXECUTED_IN_THIS_PASS`.

`platform_status`: `VERIFIED_ON_REFERENCE_HOST`, `DOCUMENTED_REQUIREMENT`, `UNVERIFIED`, `TESTED_LOCAL`, `TARGET_DESIGN`.

`platform_scope`: `REPOSITORY_ONLY`, `WSL2_PRIVILEGED`, `KIND_LOCAL`, `REFERENCE_HOST`, `MANAGED_CLOUD`, `STRANGER_HOST`.

`deployment_profile`: `bundled_gate`, `no_gate`, `unknown`.

`compatibility_status`: `internally_proven`, `not_stranger_proven`.

`TESTED_LOCAL` is a `platform_status`. There is no customer-validation field. `KIND_LOCAL` is not `MANAGED_CLOUD`. `internally_proven` is not `STRANGER_HOST`.

## 3. Three channels

P24 keeps three channels. A value on one channel does not fill the others. `fact_kind` is the discriminator.

| `fact_kind` | Subject | Field that may be set | Field that stays null |
| --- | --- | --- | --- |
| `LOADER_LIVENESS` | `LOADER` | `heartbeat_age_limit_s` `60` | `protection_state`, control-plane `interval_s` |
| `PROTECTION_EVALUATION` | `COVERAGE` or `LOADER` | `protection_state` | `heartbeat_age_limit_s`, `verifier_result` |
| `CONTROL_PLANE_HEARTBEAT` | `CONTROL_PLANE` | `interval_s` `NOT_COPIED` | `heartbeat_age_limit_s` |
| `VERIFIER_RUN` | any of the six | `verifier_result` | `protection_state` |
| `OPTICS_DISPLAY_READING` | any of the six | `optics_display` | `protection_state` |
| `SDK_ACTION` | any of the six | `sdk_action` | `protection_state` |
| `APPLICATION_STATUS` | any of the six | `application_status` | `optics_display` |
| `LEDGER_ACTION` | `LEDGER` | `ledger_action_taken` | `verifier_result` |
| `PASS_THROUGH_LABEL` | any of the six | `pass_through_product_label` | `protection_state` |
| `EVIDENCE_LABEL` | any of the six | evidence, scope, platform status, deployment profile, compatibility | status fields above |
| `OTHER` | any of the six | none of the status fields | all of them |

Other `fact_kind` values are not defined.

## 4. Freshness rule

Rule id: `FRESHNESS_WINDOW_NOT_SET_EMIT_UNKNOWN`.

| Piece | Value |
| --- | --- |
| Window | `NOT_SET` |
| Emitted freshness | `UNKNOWN` only |
| Reserved, not emitted | `CURRENT`, `HISTORICAL`, `STALE` |

Reason: Optics architecture `docs/architecture/optics-foundation/06-SELF-OBSERVABILITY-AND-RELIABILITY.md` section 7 leaves the freshness window number `NOT_SET` and says implementations must not invent one. Until a window exists, `CURRENT` is not emitted. Workstream 3 left freshness `UNKNOWN` until Workstream 4 set a window. This catalog sets that window to `NOT_SET`. The honest emitted value remains `UNKNOWN`.

`heartbeat_age_limit_s` is `60` on a `LOADER_LIVENESS` fact. The manifest path is `/run/vantio/heartbeat`. That age limit is the DaemonSet liveness file. It is not a freshness window and it is not `freshness` `CURRENT`.

The control-plane interval and event names stay in the `CUSTOMER_SHIPPED` operations guide. This catalog sets `interval_s` to `NOT_COPIED` and does not reuse 60 seconds for that channel. `CONFLICT-HEARTBEAT-PATH` stays unresolved: manifests probe `/run/vantio/heartbeat`; the guide's other filename was not copied.

A later catalog revision may replace `window` with a positive number of seconds. Until that revision, emitters write `UNKNOWN`.

## 5. Collision rules preserved from Workstream 3

These spellings stay on the fields in the first column. They do not move to the fields in the second column. `COLLISION-MATRIX.json` rows with `origin` `WS3_SECTION_2` are this table.

| Spelling | Field that may hold it | Field that must not hold it |
| --- | --- | --- |
| `BLOCKED` | `verifier_result` when the test environment is unavailable. `ledger_action_taken` when a real drop was attributed | `protection_state`. `optics_display` |
| `OBSERVED` | `optics_display`. `ledger_action_taken` for a TLS uprobe pass-through. `sdk_action` because Layer A action tokens include this spelling | `protection_state`. A pass-through observation is not `protected` |
| `ALLOWED` | `pass_through_product_label` for pass-through, distinguished from the wire word `OBSERVED`. `sdk_action` when a policy allows a call | `protection_state` |
| `PARTIAL` | `optics_display` for a mixed-run rollup | `protection_state`. A coverage percentage. Coverage in this catalog is a named gap. There is no `coverage_percent` field |
| `SUCCESS` | `optics_display` when an observation record was stored. `application_status` for HTTP 200–399 | `protection_state` |
| `UNKNOWN` / `unknown` / `coverage_unknown` | Honest absence: freshness `UNKNOWN`, deployment profile `unknown`, or protection fallback `coverage_unknown` | A synonym for `protected` |
| `CURRENT` | Not emitted. The freshness window is `NOT_SET` | A substitute for a heartbeat file younger than 60 seconds |

Also preserved, as their own rows:

- `OPTIONAL_COMPONENT_ABSENT` is not `PASS`.
- `internally_proven` is not `STRANGER_HOST`.
- `KIND_LOCAL` is not `MANAGED_CLOUD`.
- `TESTED_LOCAL` is not a customer-validation field.
- `coverage_unknown` is not `protected`.

## 6. Tightening that keeps the rows

Later rows in `COLLISION-MATRIX.json` use `origin` `WS4_TIGHTEN`, `WS3_COLLISION_RULE`, or `P24_SECTION_4`. They add a field that already uses the spelling. They do not delete a Workstream 3 `may_hold` entry and they do not merge two fields into one.

Optics cases that share a spelling and stay apart:

- Query completeness `PARTIAL` and run lifecycle `PARTIAL` are not the Optics display token `PARTIAL` and not a coverage percentage.
- Query completeness is `COMPLETE`, `PARTIAL`, `UNKNOWN`, or `UNAVAILABLE` (A4). Run lifecycle is `COMPLETE`, `PARTIAL`, `INTERRUPTED`, `ABANDONED`, or `RECOVERED`. Those two `COMPLETE` values are different fields.
- `integrity_state` `UNKNOWN`, `issue_location` `UNKNOWN`, `query_completeness` `UNKNOWN`, `sampling_state` `UNKNOWN`, and `drop_state` `UNKNOWN` are not freshness `UNKNOWN`, not `coverage_unknown`, and not deployment profile `unknown`.
- `issue_location` `COVERAGE` is not subject `COVERAGE`.
- `drop_state` `DROPS_IN_SCOPE` is not the completeness-reason token `DROPS_IN_SCOPE`.
- Unit F does not render optics `SUCCESS`. `application_status` `SUCCESS` is not copied into `optics_display`.
- `PRODUCT_HEALTH` diagnostic names (`hooks_installed`, `events_dropped`, and the rest of the A5 list) stay Optics records.

P24 named gaps stay named: an unpinned image digest, a `kind` row offered as managed cloud, a control-plane heartbeat offered as node liveness, verifier `BLOCKED` offered as ledger `BLOCKED`, and Optics `OBSERVED` offered as `protected`.

`UNVERIFIED`, `NOT_EXECUTED`, `NOT_EXECUTED_IN_THIS_PASS`, `NOT_INDEPENDENTLY_VERIFIED`, `TARGET_DESIGN`, and `STRANGER_HOST` are not rewritten to `protected`, `PASS`, or `VERIFIED_ON_REFERENCE_HOST`. `NOT_EXECUTED` is the coverage-matrix `this_force` label. It is not an `evidence_class`.

Local NDJSON is append-oriented. `WORM` is not a catalog value. Spanner live insert remains `TARGET_DESIGN`. A quarantine marker is `protection_state` `quarantined`. P24 records `dual_control_executor_wired` false. That flag is not a protection state.

## 7. What a fact looks like

`record_type` is `SHARED_HEALTH_FACT`. `freshness` on every fact this catalog allows is `UNKNOWN`. Examples and rejected shapes are in `HEALTH-VOCABULARY.json`. The tests apply `fact_rules` to those shapes. They do not load Phantom Engine and they do not open a network socket.
