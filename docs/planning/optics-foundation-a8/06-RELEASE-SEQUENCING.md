# Release sequencing

Audience: INTERNAL_RESTRICTED

Sequence numbers are order constraints. They are not calendar dates and they are not effort estimates.

Nothing in this sequence is released by this planning PR. Gate 8 stays closed. CLI `@vantio/cli@0.3.24` stays frozen. Python `vantio-agent-sdk` 3.1.0 is not sealed. Python 3.0.15 is not the ship target.

## 1. Order

| Order | Unit | Packages | Customer-visible? |
| --- | --- | --- | --- |
| 1 | Slice 1 private contract | PKG-01 | No. Option B. Not loaded by CLI 0.3.24 or by Python 3.1.0 |
| 2 | Parallel library wave | PKG-02 design and fixtures, PKG-03, PKG-04, PKG-05, PKG-09 rules | No, until a writer cutover force |
| 3 | Fail-open runtime contract | PKG-12 against the interface and the health model | No by itself |
| 4 | Founder decision 9 | PKG-06 | No |
| 5 | Default store release | PKG-07 together with the selected binding and PKG-12 | Only in a future CLI and a future Python version, by a later force |
| 6 | Proof library, if not already in wave 2 | PKG-04 | A customer export command is a later force |
| 7 | Explicit legacy copy | PKG-08 | Yes, only when the customer runs it. Originals stay |
| 8 | Query | PKG-10 memory adapter can precede step 5. File-backed query follows step 5 | Command is a later CLI version |
| 9 | Retention commands | PKG-11 | Optional. Default remains unbounded |
| 10 | Coverage command | PKG-13 in-scope part only | Later CLI version |
| 11 | Trends and indicators | PKG-15 | After query. No SLO configuration |
| — | Blocked | PKG-14 waits on decision 13. PKG-16 waits on decision 3. PKG-17 waits on decision 12 | No |

Wave 2 items may finish in any internal order after order 1, subject to `02-DEPENDENCY-AND-CRITICAL-PATH.md`. Step 5 does not start before steps 1, 3, and 4.

## 2. Units that ship together

- The Node binding selected in PKG-06 and the PKG-07 schema, in the release that first writes a store file.
- PKG-12 fail-open behavior and that same default-writer release.
- Node fixture results and Python fixture results for any statement that the languages match.
- PKG-04 verifier evidence and any PKG-08 release that says migration preserved evidence.

## 3. Units that can ship alone

- The Slice 1 private package, unpublished.
- A future Python writer version, without a CLI publish.
- A future CLI version, without republishing 0.3.24.
- The proof verifier library, before migrate exists.
- A coverage command, after self-health, without a store migration.
- UI, alerting, and network export, each only after its Founder decision and each as its own release.

## 4. Frozen and unpublished floors

| Artifact | Sequence rule |
| --- | --- |
| `@vantio/cli@0.3.24` | Not patched, not republished, not retagged. The Node customer path changes only in a later version |
| `vantio-agent-sdk` 3.1.0 source | Not sealed and not given a release candidate by this plan. Writer behavior changes in a later version |
| Python 3.0.15 | Not the target and not published from the stage-2 note in this repo |
| `packages/vantio-agent-sdk` 0.2.4 | Not the Optics writer. Out of this sequence |
| Gate 8 | Closed until a separate Founder implementation force opens it |
| Registries, tags, GitHub releases | Not part of any order in this plan |

## 5. Rollback at release boundaries

Each order’s rollback is the package row in `04-MIGRATION-AND-ROLLBACK-PLAN.md`. A release that writes customer data includes the data rollback in the same notes a later force will write. This plan’s only release artifact is a draft documentation PR, which rolls back by closing the PR.

## 6. What “done” means for a release unit

A unit is done for planning when its package status is still one of the allowed planning statuses and its evidence tier is filled by a later force. This sequencing document does not mark any unit done. Producer tests do not close a unit. Independent council on the implementation tip, and the stranger-host tier where section 4 of `05-TEST-AND-EVIDENCE-STRATEGY.md` requires it, come before an external claim.
