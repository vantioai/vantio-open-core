# Placeholder matrix

Audience: INTERNAL_RESTRICTED

Execution: `NOT_EXECUTED`

Evidence tier on every row: `UNSET`

Normative list: `PLACEHOLDER-MATRIX.json`

The readiness verifier scans filenames under `tests/`, `.github/workflows/`, `packages/`, and `scripts/`. It fails when the scan disagrees with `repository_test_paths`. Product sentences that use the word egress are outside that filename scan. This page adds no command to `later_commands`.

## Ingress

| Field | Value |
| --- | --- |
| Id | `ingress` |
| Named suite | `ABSENT` |
| Status | `NOT_EXECUTED` |
| In `ci.yml` | false |
| In `later_commands` | false |
| Evidence tier | `UNSET` |
| Repository test paths | none |

## Egress

| Field | Value |
| --- | --- |
| Id | `egress` |
| Named suite | `ABSENT` |
| Status | `NOT_EXECUTED` |
| In `ci.yml` | false |
| In `later_commands` | false |
| Evidence tier | `UNSET` |
| Repository test paths | none |

## Host authority

| Field | Value |
| --- | --- |
| Id | `host-authority` |
| Named suite | `ABSENT` |
| Status | `NOT_EXECUTED` |
| In `ci.yml` | false |
| In `later_commands` | false |
| Evidence tier | `UNSET` |
| Repository test paths | none |

## Sequential authority

| Field | Value |
| --- | --- |
| Id | `sequential-authority` |
| Named suite | `ABSENT` |
| Status | `NOT_EXECUTED` |
| In `ci.yml` | false |
| In `later_commands` | false |
| Evidence tier | `UNSET` |
| Repository test paths | none |

## Health

| Field | Value |
| --- | --- |
| Id | `health` |
| Named suite | `NOT_THIS_GATE` |
| Status | `NOT_EXECUTED` |
| In `ci.yml` | false |
| In `later_commands` | false |
| Evidence tier | `UNSET` |
| Repository test paths | `tests/shared-health-vocabulary/catalog.test.cjs`, `tests/shared-health-vocabulary/collision.test.cjs` |

The filename hits are shared health vocabulary catalog tests. They sit outside `.github/workflows/ci.yml` and outside `later_commands`. This row leaves them unrun. A later execution authorization that wants a health probe names that probe in a copied checklist.

## Progressive enforcement

| Field | Value |
| --- | --- |
| Id | `progressive-enforcement` |
| Named suite | `ABSENT` |
| Status | `NOT_EXECUTED` |
| In `ci.yml` | false |
| In `later_commands` | false |
| Evidence tier | `UNSET` |
| Repository test paths | none |

## Adjacent tests outside this matrix

`PLACEHOLDER-MATRIX.json` lists tests added or modified between the prepared SHA and the currency SHA. Those paths stay outside `later_commands`. This page does not run them.
