# Future Force template — Node Optics writer integration

Audience: INTERNAL_RESTRICTED

Status: `NOT AUTHORIZED`

Status: `DRAFT FOR FOUNDER REVIEW`

Status: `DO NOT EXECUTE`

This template is not a Force. It does not start work. It does not reopen `@vantio/cli` `0.3.24`. It does not edit `packages/vantio-cli/bin/` or `packages/vantio-cli/package.json` on the frozen line. It does not import `@vantio/optics-evidence-contract` into that line.

## 1. Identity placeholders

| Item | Placeholder |
| --- | --- |
| Starting commit | `PKG02-FUTURE-START-SHA-UNASSIGNED` |
| Package | `@vantio/cli` |
| Future version | `PKG02-FUTURE-CLI-UNASSIGNED` |
| Node SDK | Not the writer. `@vantio/agent-sdk` stays `0.2.4` unless a later decision selects `PKG02-FUTURE-NODE-SDK-UNASSIGNED`. |
| Contract | `@vantio/optics-evidence-contract` `0.0.0-unstable-pre-1.0`, still private, still `schema_version` `0` |
| Unicode profile | `PKG01-UCD-16.0.0` |

The starting commit is filled only when a Founder Force is actually issued. It is not this planning tip.

## 2. Allowed paths, once authorized

- A new future CLI tree at `PKG02-FUTURE-CLI-UNASSIGNED`, or a branch that does not modify the `0.3.24` sources in place.
- Inert adapter first (Unit B), then reader explanation (Unit F), then writer activation (Unit D).
- Tests that compare canonical JSON to the shared fixtures from Unit A.

Out of that future force:

- `packages/vantio-cli/` as shipped in `0.3.24`
- `packages/vantio-agent-sdk-py/`
- PKG-01 Unicode tables, detector classes, and the 220-fixture expected hashes, unless a separate contract force says otherwise
- SQLite, migrations, UI, daemon, OTLP, SIEM, alerting, npm publish, seal, release candidate
- PR #59

## 3. Required order inside the future force

1. Land the inert adapter. It reads copies. It does not replace `writeFileSync` in the frozen interceptor.
2. Prove an ordinary 0.3.24 run file is byte-identical with the adapter present and unused.
3. Prove unknown `optics_status` does not become `SUCCESS`.
4. Only then, and only on `PKG02-FUTURE-CLI-UNASSIGNED`, switch the new writer.
5. Stop before merge and before seal. An independent council reviews the activation. This template does not appoint that council.

## 4. Record delta the future force must show

Against a 0.3.24 file from the same workload, the new file must show, in a written delta and not as a claim:

- `record_type` `run_envelope` and per-call `observation_event`
- `schema_version` `0` and legacy `2` only under `compatibility.legacy_schema_version`
- `run_id` holding the value the old file called `trace_id`
- `optics_status` `OBSERVED` or `UNAVAILABLE` or `NOT_OBSERVED` or `OPTICS_ERROR`, and not a default `SUCCESS`
- `response_bytes` omitted when content-length was absent, not `0`
- `evidence_origin` `LOCAL_OBSERVATION` only with producer `node_interceptor` and the future version token
- `action` omitted or `OBSERVED`. No `ALLOWED` or `BLOCKED_*` on an Optics observation
- Prohibited keys absent: `plane`, `data_note`, `residual`, `free_mode`, `est_spend_usd`
- `issue_location` present on the observation
- Unicode diagnostic `PKG01-UCD-16.0.0`

## 5. Rollback proof

Disable the new writer. The next run uses the previous shape. The canonical file already written is still on disk, still carries its origin, and a rolled-back reader reports `UNSUPPORTED` with the schema marker visible. The workload return value is unchanged when validation fails.

## 6. Stop line

The future force stops before merge, before seal, and before publication. It does not mark a release ready. It does not announce.
