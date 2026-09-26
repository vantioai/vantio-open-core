# Future Founder Force template — Slice 1

```
NOT AUTHORIZED
DRAFT FOR FOUNDER REVIEW
DO NOT EXECUTE
```

This file is a copy-ready draft. It does not open Gate 8. It does not start A8. It does not authorize the branch, the files, or the tests below. A Founder copies it into a later force and fills the placeholders before any agent runs it.

Producer of this draft: planning agent `bc-cdec4aa3-94f6-5b72-b604-d2b7ba3bfbac`. Classification of the planning packet: `OPTICS_FOUNDATION_IMPLEMENTATION_PLAN_READY_FOR_COUNCIL`. That classification is not permission to run this template.

---

FOUNDER FORCE — OPTICS SLICE 1 EVIDENCE CONTRACT (NOT AUTHORIZED)

## Locked starting state

Repository: vantioai/vantio-open-core

Authorized starting main (exact, Founder fills this when authorizing):
`{{FOUNDER_LOCKED_STARTING_MAIN_SHA}}`

The SHA must be an ancestor-or-self check against planning commit `{{PLANNING_TIP_SHA}}` on branch `planning/optics-foundation-a8-decomposition`, or a descendant that a Founder names. The agent verifies the SHA. On mismatch, stop with `OPTICS_SLICE_1_BLOCKED_INPUT_DRIFT`.

Architecture input remains:
`docs/architecture/optics-foundation/`
at the tree that planning verified on `8a6ef881169c2bf379e04a7d1e8381532ec236b2`, unless the Founder names a newer architecture commit.

Planning spec:
`docs/planning/optics-foundation-a8/07-FIRST-SLICE-SPECIFICATION.md`

Branch to create:
`implementation/optics-slice-1-evidence-write-path`

Packages in scope:
`PKG-01` only.

## Three-phase sandbox protocol

The implementation agent follows these phases in order. A later phase does not start if an earlier phase fails.

### Phase 1 — Read-only inventory sandbox

- Read the current Node writer, Python writer, and readers named in the Slice 1 spec.
- Confirm CLI version is still `0.3.24` and Python project version is still `3.1.0` unless the Founder has named a newer floor.
- Write the inventory notes into the contract package README only after Phase 2 is allowed. Phase 1 itself changes no file.
- Stop if the live writer shapes differ materially from inventory findings 1.2 and 2.2 and from the Slice 1 spec.

### Phase 2 — Isolated contract sandbox

- Add only the files in the allowlist below.
- Validators and tests use temporary directories.
- Tests must not write `~/.vantio/runs` and must not write `store.sqlite`.
- The contract package is `private` and is not imported by `packages/vantio-cli` or by `packages/vantio-agent-sdk-py/vantio`.
- No network calls to npm, PyPI, TestPyPI, or Twine.

### Phase 3 — Evidence sandbox

- Run the Node tests, the Python tests, the conformance comparison, the privacy corpus, and the fail-open tests.
- Record commands and results in the PR body.
- Stop before merge.
- Stop before seal.
- Do not publish.

## Files allowed

Only these paths may be added:

- `packages/optics-evidence-contract/package.json` with `"private": true` and version `0.0.0-unstable-pre-1.0`
- `packages/optics-evidence-contract/README.md` marked `INTERNAL_RESTRICTED`
- `packages/optics-evidence-contract/contract/field-catalog.json`
- `packages/optics-evidence-contract/contract/denylist.json`
- `packages/optics-evidence-contract/src/validate.cjs`
- `packages/optics-evidence-contract/src/validate.py`
- `packages/optics-evidence-contract/fixtures/**`
- `packages/optics-evidence-contract/test/**`

No other path may change. In particular, do not modify:

- `packages/vantio-cli/**`
- `packages/vantio-agent-sdk-py/**`
- `packages/vantio-agent-sdk/**`
- `packages/vantio-optics-mcp/**`
- workflows, lockfiles of other packages, docs other than the contract README
- `docs/architecture/optics-foundation/**`
- `docs/planning/optics-foundation-a8/**` except if the Founder explicitly adds a result note path

## Explicit non-scope

SQLite. Any SQLite binding or dependency. WAL. A database file. A schema implementation. A migration. Legacy import. Retention. Pruning. Trends. Alerting. UI. Daemon. OTLP. SIEM. `vantio doctor`. Stable schema. Public API. Package publish. Tag. GitHub release. Credential use. Website. Announcement. Numeric performance targets. Usage or cost fields. Machine hostname. Promotion of `LEGACY_UNMARKED`. A seventh annotation origin. Freshness `CURRENT`. Hashing a secret in order to store it. Wiring the validator into the frozen CLI or into Python 3.1.0’s import path.

## Contract design

Implement `07-FIRST-SLICE-SPECIFICATION.md` sections 2, 5, 6, 7, and 8.

- Catalog and denylist are data. Validators are hand-written. No schema generator. No JSON Schema runtime.
- `schema_status` is `unstable-pre-1.0`.
- Option B: the package is not on the live writer path.

## Node and Python boundary

- `validate.cjs` and `validate.py` accept the same fixtures and emit the same disposition tokens.
- Neither file is required by `interceptor.cjs` or `_http_observe.py`.
- Display tokens stay those in `optics-cx.cjs`. Do not edit that file.
- Run-level display `PARTIAL`, lifecycle `PARTIAL`, and completeness impact stay distinct.

## Tests required

- S1-G3 Node validator tests.
- S1-G4 Python validator tests.
- S1-G5 one runner that fails if dispositions differ.
- S1-G6 privacy corpus, zero prohibited bytes in outputs or result details.
- S1-G7 fail-open: a supplied application result is unchanged.
- Legacy envelope fixtures still parse through existing readers without modifying those readers.
- The contract output is not written over the fixture.

S1-G1 and S1-G2 are review gates on the PR. S1-G8 is an independent council on the exact implementation tip. S1-G9 and S1-G10 are out of scope for this force because it does not seal or publish.

## Privacy corpus

Use the fixture table in `07-FIRST-SLICE-SPECIFICATION.md` section 5. Every row needs a fixture. A missing row fails the force. Do not add hashing as a way to retain a canary.

## Fail-open testing

Cover secret omission, event drop, internal validator failure, malformed UTF-8, and an oversized value. Assert the application result bytes and status are unchanged. Do not put an unbounded lock on a simulated request path. Do not invent a timeout number.

## Independent council

The implementation author does not self-pass. A separate Founder-authorized council reviews the exact tip. Council seats for that later force are named by the Founder at authorization. This template does not appoint them.

## Stop before merge

Open one draft PR. Do not mark it ready. Do not merge.

## Stop before seal

Do not build a release wheel or a published npm tarball for this package. Do not run a seal, a tag, or a GitHub release. Local unit tests may import the package from the repo path.

## No publication

Do not access npm, PyPI, TestPyPI, or Twine. Do not publish an announcement.

## Required return packet

- Draft PR URL
- Branch
- Exact tip SHA
- Files added
- Test commands and results
- Privacy corpus row count and failures
- Confirmation the frozen CLI and Python 3.1.0 import path do not load the package
- Confirmation no SQLite dependency and no database file
- Gate list S1-G1 through S1-G10 with only the gates this force actually ran
- Council status: pending, unless a separate council agent was authorized
- Hard stops: no seal, no registry, Gate 8 unchanged, A8 still limited to this slice’s contract library

## Allowed final classifications

Exactly one of:

- `OPTICS_SLICE_1_CONTRACT_READY_FOR_COUNCIL`
- `OPTICS_SLICE_1_BLOCKED_INPUT_DRIFT`
- `OPTICS_SLICE_1_BLOCKED_SCOPE`

`OPTICS_SLICE_1_BLOCKED_SCOPE` is for an agent that finds it cannot meet the spec without touching a forbidden path. That agent stops and reports the path. It does not take the path.

---

End of template. Not authorized. Do not execute.
