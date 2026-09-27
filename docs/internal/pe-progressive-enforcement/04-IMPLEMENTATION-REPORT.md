# Implementation report

Audience: INTERNAL_RESTRICTED

Producer classification: `PE_PROGRESSIVE_ENFORCEMENT_READY_FOR_COUNCIL`

## 1. Files

| Path | Role |
| --- | --- |
| `packages/pe-progressive-enforcement/` | Private package. Not a workspace member |
| `tests/pe-progressive-enforcement/` | Lifecycle, no-auto-enforce, and isolation tests |
| `docs/internal/pe-progressive-enforcement/` | Boundary, lifecycle, gates, limitations, this report, council slot |

## 2. Behavior the tests hold

- Every required stage is entered on the full path, then removal verification returns `REMOVED`.
- Historical replay stores shadow decisions and per-rule impact. Calling replay does not leave `PROPOSE`.
- Canary is bounded. Promotion requires a different approver and starts at `COHORT`.
- Rollout widens one step at a time and cites the previous evidence id.
- Review failure and explicit rollback restore the known-good `CANARY` snapshot and clear the active set.
- Exception expiry records `promotions: 0` and does not change stage.
- Freeze blocks promotion and promoted matches. Rollback still runs. Thaw does not change stages.
- Sixty-four observations that carry `enforce: true` stay on `OBSERVE`. `ingest` with `propose: true` and `enforce: true` stops on `PROPOSE`.
- A prompt string and a key-shaped string in an observation are absent from stored evidence.

## 3. Closed

No live package, governance status file, workspace list, or published version was edited. The council file is a pending slot.
