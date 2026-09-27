# PKG-02 Unit A implementation report

PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

Producer classification before council: `OPTICS_PKG02_UNIT_A_READY_FOR_COUNCIL`

This classification means the Unit A branch is ready for a separate council agent. It is not a council verdict, not a merge, and not a statement that a writer exists.

The producer did not sit the council.

## What landed

Private package `@vantio/optics-record-vocabulary` at `0.0.0-unstable-pre-1.0`. That version matches the unstable posture. It is not a bump of CLI `0.3.24`, Node SDK `0.2.4`, Python `3.1.0`, or `@vantio/optics-evidence-contract`.

The package is not in `pnpm-workspace.yaml`.

| Item | Count |
| --- | --- |
| Canonical rows retained | 120 |
| Unique canonical names | 88 |
| Names that repeat across record types | 22 (32 extra rows, not merged away) |
| Compatibility rows retained | 67 |
| Alias edges | 19 |
| Widest alias fan-out | 2 (bound 8) |
| Fixtures | 34 |
| Force scenarios covered | 26 |

Planning-row coverage: 120 `RETAINED` with no consolidation, 67 `RETAINED_AS_COMPATIBILITY` with an explicit reason. Row identity is `record_type` plus `canonical_name`.

## Checks

From the repository root:

```sh
node --test tests/optics-record-vocabulary/*.test.cjs
```

The producer run of that command reported 23 tests and 0 failures. The suite covers vocabulary parse, unique row keys, alias fan-out, cycles, ownership, enum and absent behavior, dimension separation, optimistic defaults, fixture determinism, Node/Python canonical bytes, PKG-01 field equality, source hashes, export surface, filesystem writes, frozen versions, and the Unit A path limit.

Optimistic-default proof: no fixture stores `optics_status` `SUCCESS`; missing status is `UNAVAILABLE`; legacy `bytes` 0 is null; explicit `response_bytes` 0 stays 0; inherited trace is `ASSERTED_CONTEXT`; corrupt input has `expected_canonical` null; unreadable and absent paths are not `NOT_OBSERVED`. Forcing `SUCCESS` on the HTTP 200 fixture fails evaluation.

Dimension-separation proof: the six separated dimensions have disjoint canonical fields. HTTP 200 stores workload `SUCCESS` and optics `UNAVAILABLE`. HTTP 500 stores `APPLICATION_ERROR` and `PROVIDER_INTERACTION`. `lifecycle` `PARTIAL` is not `application_status`.

PKG-01 proof: all 120 catalog fields match type, invalid disposition, privacy class, and metric, export, and proof eligibility. Enum samples match `enums.json`. Unicode profile id is `PKG01-UCD-16.0.0`. No second profile was added. Prohibited names match the PKG-01 list. Detector source is not imported.

Live-import proof: `src/` has no product `require`, no `writeFile`, no `sqlite`, and no `child_process`. Evaluation of the fixture list performs no `writeFileSync`. The public API has no convert, migrate, or write function.

## Hard-stop attestations

- No CLI, Python SDK, or Node SDK source change.
- No PKG-01 change.
- No live import.
- No record conversion of arbitrary inputs.
- No SQLite.
- No migration.
- No UI, daemon, exporter, or alerting.
- No stable schema.
- No release candidate, seal, publish, tag, or announcement.
- No Units B–F.
- Draft pull request only. Not marked ready. Not merged.
- Council is a separate agent. This producer did not run it.
