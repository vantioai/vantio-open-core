# Independent council

Audience: INTERNAL_RESTRICTED

Status: `PENDING_INDEPENDENT_COUNCIL`

Producer classification under review: `SHARED_HEALTH_VOCABULARY_READY_FOR_COUNCIL`

This file is the producer stub. The planning producer does not sit the council and does not write a verdict.

## 1. What a separate council reviews

| Item | Value |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Catalog directory | `docs/planning/shared-health-vocabulary/` |
| Tests | `tests/shared-health-vocabulary/` |
| Open-core base named by the producer | `4b1b85ad6af41b1bb54dc4c55cde16b711ae7dd4` |
| Producer | `bc-17018458-81e4-592e-9017-8ea8dd4ae3c7` |
| Classification the producer claims | `SHARED_HEALTH_VOCABULARY_READY_FOR_COUNCIL` |
| PE packet `vocabulary_status` after this force | `PENDING_WS4` |

## 2. Seats

| Seat | Scope | Verdict |
| --- | --- | --- |
| 1 | Layer separation and collision preservation | `UNSAT` |
| 2 | Freshness rule `FRESHNESS_WINDOW_NOT_SET_EMIT_UNKNOWN` | `UNSAT` |
| 3 | Access gaps and confidentiality | `UNSAT` |
| 4 | Bindings to P24, Optics, verifier, and evidence labels | `UNSAT` |
| 5 | Frozen surfaces and the untouched PE packet | `UNSAT` |
| 6 | No live probe and no promotion of unverified cells | `UNSAT` |

## 3. Checks the council can re-run without a live load

From the repository root:

```sh
node --test tests/shared-health-vocabulary/*.test.cjs
```

Also:

- The diff is `docs/planning/shared-health-vocabulary/` and `tests/shared-health-vocabulary/`.
- `docs/planning/phantom-engine-production/HEALTH-VOCABULARY.json` still has `vocabulary_status` `PENDING_WS4` and `workstream_4` `DEFINITION_NOT_RETRIEVED`.
- `docs/governance/STATUS-TOKENS.json` is unchanged.
- CLI `0.3.24`, Node SDK `0.2.4`, and Python SDK `3.1.0` are unchanged.
- Freshness `window` is `NOT_SET` and the only emitted freshness value is `UNKNOWN`.
- No file path contains `PRIVATE-MANUAL` or `CUSTOMER-MANUAL`.
- The operations-guide blob `1b973342b3bf7f6aa6cdad70de49fa6e26db0077` is not pasted.
- The producer classification is present and no council pass token is present.

## 4. Verdict block

| Field | Value |
| --- | --- |
| Council agent | `UNSAT` |
| Reviewed tip | `UNSAT` |
| Verdict | `PENDING_INDEPENDENT_COUNCIL` |
| Blocking findings | `UNSAT` |
