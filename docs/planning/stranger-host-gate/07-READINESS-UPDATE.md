# Stranger-host readiness update

Audience: INTERNAL_RESTRICTED

Classification: `STRANGER_HOST_READINESS_UPDATED_READY_FOR_COUNCIL`

Council status: `PENDING_INDEPENDENT_COUNCIL`

Execution status: `NOT_AUTHORIZED`

Mode: `READINESS_UPDATE_ONLY`

Force: WAVE2 Track 16

Producer: Cursor cloud agent `bc-ad6e7ae1-4de4-5416-bc9d-a6971c7717f4`, model Grok 4.7

Repository: `vantioai/vantio-open-core`

Currency main: `89f95099d0dce463307eb75d78e7fcf2ef99feb2`

Prepared main (unchanged prep pin): `5064f32f1cdfcb840dfd100e2ce5c712d046550d`

Prep classification (unchanged): `STRANGER_HOST_PACKET_READY_AWAITING_EXECUTION_AUTH`

## Inventory

Checked on the currency SHA, with the prepared SHA as ancestor:

| Check | Result |
| --- | --- |
| `.github/workflows/ci.yml` versus the prepared SHA | Unchanged. `ci.yml is unchanged from the prepared SHA` |
| `PACKET-MANIFEST.json` `later_commands` | The prep list. This update adds no command |
| Prep authorization template | `NOT_AUTHORIZED`, placeholders unfilled |
| Refuse entrypoints | Exit 2 |
| Evidence tiers assigned | None |
| Named suites for ingress, egress, host-authority, sequential-authority, progressive-enforcement under `tests/`, `.github/workflows/`, `packages/`, and `scripts/` | No filename hit |
| Health filename hits | `tests/shared-health-vocabulary/catalog.test.cjs`, `tests/shared-health-vocabulary/collision.test.cjs` |

Tests added under `tests/` between the prepared SHA and the currency SHA, recorded in `PLACEHOLDER-MATRIX.json`, stay outside `later_commands` and outside `ci.yml`:

- `tests/optics-node-adapter/adversarial.test.cjs`
- `tests/optics-node-adapter/direct.test.cjs`
- `tests/optics-node-adapter/isolation.test.cjs`
- `tests/optics-otel-mapping/isolation.test.cjs`
- `tests/optics-otel-mapping/mapping.test.cjs`
- `tests/optics-pkg02-unit-f/adversarial.test.cjs`
- `tests/optics-pkg02-unit-f/direct.test.cjs`
- `tests/optics-pkg02-unit-f/isolation.test.cjs`
- `tests/optics-pkg02-unit-f/ordinary-client.test.cjs`
- `tests/optics-python-adapter/test_adapter.py`
- `tests/optics-python-adapter/test_isolation.py`
- `tests/shared-health-vocabulary/catalog.test.cjs`
- `tests/shared-health-vocabulary/collision.test.cjs`

`tests/optics-record-vocabulary/isolation.test.cjs` is the test file modified between those SHAs. `.github/workflows/docs-release-governance.yml` is the workflow added between those SHAs. Both stay outside the prep matrix. SH-STOP-13 still places Phantom Engine enrollment, kernel modules, and eBPF outside this packet.

## Boundary

This force updates the merged prep packet so a later council can see the currency SHA, the six placeholder families, and the execution checklist. Writable path: `docs/planning/stranger-host-gate/`.

The prep pin, `later_commands`, the unfilled Founder template, and both refuse scripts stay in force. Gate 8 stays closed. Customer hosts stay forbidden. Credentials stay `NONE`.

Local commands for this force:

```bash
node docs/planning/stranger-host-gate/scripts/verify-packet-prep.mjs
node docs/planning/stranger-host-gate/scripts/verify-readiness-update.mjs
node --test docs/planning/stranger-host-gate/scripts/readiness.test.mjs
```

Those commands read the packet. They leave `scripts/refuse-stranger-host-execution.mjs` in place. `--execute` on the readiness verifier exits 2 with `STRANGER_HOST_EXECUTION_BLOCKED_READINESS_ONLY`.

## Placeholder families

`08-PLACEHOLDER-MATRIX.md` and `PLACEHOLDER-MATRIX.json` are the sections for:

- ingress
- egress
- host-authority
- sequential-authority
- health
- progressive-enforcement

Each row is `NOT_EXECUTED`. Each evidence tier is `UNSET`. None of the rows is a `later_commands` entry. The health row records the catalog filenames the scan found and leaves those files unrun.

## Execution authorization checklist

`09-EXECUTION-AUTH-CHECKLIST.md` and `authorization/EXECUTION-AUTH-CHECKLIST.template.json` are unfilled. Future execution authorization requires every field below as a named value in a copied checklist, together with replacement of the refuse script by that later force:

| Field | Placeholder |
| --- | --- |
| Named host | `{{NAMED_HOST}}` |
| Owner/operator | `{{OWNER_OPERATOR}}` |
| Distro | `{{DISTRO}}` |
| Kernel | `{{KERNEL}}` |
| Arch | `{{ARCH}}` |
| Container/runtime profile | `{{CONTAINER_RUNTIME_PROFILE}}` |
| Confidentiality boundary | `{{CONFIDENTIALITY_BOUNDARY}}` |
| Artifact route | `{{ARTIFACT_ROUTE}}` |
| Maintenance window | `{{MAINTENANCE_WINDOW}}` |
| Rollback authority | `{{ROLLBACK_AUTHORITY}}` |
| Independent verifier | `{{INDEPENDENT_VERIFIER}}` |
| Stop conditions | `{{STOP_CONDITIONS}}` |
| Founder execution authorization | `{{FOUNDER_EXECUTION_AUTHORIZATION}}` |

In-place completion of this copy is forbidden. SH-STOP-21 is the stop. A filled field in this packet fails the readiness verifier.

## Evidence

`evidence_tiers_assigned` stays empty. This classification is the producer handoff for an independent council. It leaves `UNIT_PROVED`, `INTEGRATION_PROVED`, `STRANGER_HOST_PROVED`, `PROVED_EXTERNAL`, and `CUSTOMER_VALIDATED` unset.

## Council

`10-INDEPENDENT-COUNCIL.md` is `PENDING_INDEPENDENT_COUNCIL`. This producer records the seats as `UNSAT` and writes no verdict.
