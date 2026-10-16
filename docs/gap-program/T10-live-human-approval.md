# T10 — Enterprise live human approval

Audience: INTERNAL

Phase: 1 design only. No feature code.

Track label: Roadmap

Written: 2026-10-16T15:48:08Z

## Question

How does a consequential enrolled action wait for two distinct humans, deny itself when the wait expires, and leave an audit record that contains no prompt and no credential?

## Current evidence

`docs/planning/enterprise-governance/03-E3-APPROVAL-CLASSES.md` defines classes `INSPECT`, `NARROW`, `WIDEN`, `ROOT`, `RECOVERY`, and `REJECTED`. Every class in that file is `PLANNED`. `WIDEN` requires two distinct customer identities. The same identity twice is refused. A workload identity fills neither seat. Vantio is not a satisfying party. Same-person dual control is a rejected act.

The reference-monitor doctrine, as that E3 file reports it, says dual-control kinds exist and the live executor for `phantom_deny_breakglass_off` is unwired. Two-of-two is tied there to a non-destructive test kind. A root shell on the host is outside that control. GA-07 in `packages/governance-assurance` repeats the limit: no live approval executor is bound, and break-glass is not a shipped control.

Gate dry-run is not approval and not activation. E3 lists "counting an application-path dry-run as host activation" as `REJECTED`.

Nothing in this tree holds a live action pending a human.

## Design

A hold applies to a `WIDEN` proposal and to any enrolled egress the customer policy marks `hold`. `NARROW` stays a one-person class, as E3 already says, so a customer can reduce authority without a second person.

While a hold is open:

- The enrolled action does not proceed.
- Phantom Engine, once this is implemented, treats the decision as deny until an approval record arrives. A missing decision is a deny. There is no default allow while the humans are away.
- The workload cannot approve itself. The T6 `agent_identity` is not an approver. The T6 `owner` is eligible only when that owner is a human subject on the customer side and is one of the two distinct parties. One owner is not two parties.

Dual control:

- Two different human subjects.
- Both inside the customer root envelope E3 already describes.
- The same subject presented twice denies the proposal.
- Vantio's witness, if one exists later, is not one of the two.

Timeout:

- Every hold carries `not_after`.
- A missing `not_after` is a deny at creation. The hold is not opened.
- When `not_after` passes, the decision is deny. The audit reason is `TIMEOUT_DENY`.
- The clock is the enrolled host's clock. A customer who does not trust that clock does not enable holds. This design does not add a network time authority.

Audit record, one row per decision, including timeout and deny:

| Field | Content |
| --- | --- |
| `approval_id` | Opaque id |
| `class` | E3 class |
| `parties` | The human subjects, or empty on timeout |
| `decision` | `DENY`, `TIMEOUT_DENY`, or `APPROVED` |
| `not_after` | The deadline |
| `policy_digest` | `sha256:` and 64 hex characters, the same shape as the observability candidate schema |
| `agent_identity` and `owner` | T6 reference for the workload that proposed the action |

The record does not contain prompts, completions, packet payloads, credentials, or raw assertions. `APPROVED` is not `ACTIVE`. E3 already separates those states. Host activation stays on the customer host. This design does not activate anything.

Pending holds on one host are capped by a parameter the implementation must set. Over the cap, a new hold is not opened. The decision is `DENY` and the reason is `HOLD_CAPACITY`. That is a different reason from `TIMEOUT_DENY`. The cap is a design parameter, not a measured limit. This document does not pick the number.

## Threat model

| Threat | Response |
| --- | --- |
| Agent approves its own hold | Workload subject is rejected as a party |
| One human submits both approvals | Distinct-subject check denies |
| Approver channel down | Timeout deny. The channel being down is not an allow |
| Race: action starts before the deny is written | The action is denied until the approval is `APPROVED` and the host has applied it. The window is closed by default |
| Forged approval from the workload | Approval signatures use the customer identity path from T6. An `UNVERIFIED` party is not a party |
| Audit row used to smuggle a prompt | Schema rejects non-allowlisted fields |
| Root shell disables the hold | Named residual from E3. This design does not claim a root shell is bound |
| Vantio staff as the second approver | Rejected. Vantio is not a satisfying party |

## Failure modes

Fail closed. Timeout, missing deadline, capacity, unverified party, broker or channel errors, and a crashed approver process all deny the held action. Reason: the customer asked for a human, and the absence of that human is not permission.

`NARROW` does not use this fail-closed wait. A narrow that fails to parse fails closed too: the narrow is not applied. Reason: a broken narrow must not become a widen.

Observe of the attempt fails open for the event and closed for the action. The attempt is logged. The action does not run.

## Edge cases

- Two holds on the same action. The first `approval_id` wins. The second is denied as a duplicate. Neither runs the action until the winner is `APPROVED` and applied.
- Clock steps backward. `not_after` is compared to the host clock. A backward step does not reopen a `TIMEOUT_DENY`.
- Approver is the T6 owner and also the only human. Dual control still needs a second human. The owner alone is a deny for `WIDEN`.
- Policy changes while a hold is open. The hold keeps the policy digest it started with. A mismatch at apply time denies.
- `INSPECT` and export of evidence the party can already read stay one-person, per E3. This track does not put a hold on read.

## Memory footprint

Each open hold is one record of the fields above. The capacity parameter bounds memory. This design does not measure it. Audit rows append to the local ledger and are subject to the T8 mutability result: the local file is not WORM.

## eBPF verifier limits

The hold decision is a userspace record consumed by the existing enrolled decision path. Phase 1 adds no eBPF program. A later load that the verifier rejects does not attach, and the enrolled path stays deny for held actions. The loader must not skip the hold because the program failed to load.

## Dependencies on T0–T5

| Track | Dependency |
| --- | --- |
| T0 | The approval component is company code and inherits T0 hygiene |
| T1 | Holds apply on an enrolled host. A stranger host has no approval surface |
| T2 | A sandbox test of timeout deny belongs with T2's verify-the-sandbox charter |
| T3 | The inventory shows which agent opened the hold |
| T4 | A tool call marked consequential is a hold. T4 does not approve it |
| T5 | A held egress is a denied egress until approval. Side-channel drills should include a hold that must not leak the payload |

T6 supplies the human subjects and the workload identity. T12 can show the hold before it is armed. T8 exports the audit row under the allowlist.

## Rollback

Disable new holds. Open holds resolve as `TIMEOUT_DENY` at the next decision point, or immediately if rollback says to close them. Rollback does not convert an open hold into an allow. Rollback does not delete audit rows. The previous enforcement mode returns for actions that are not in the closing set. A widen that was `APPROVED` but not applied is not applied during rollback.

## Proof plan

Phase 2, mocks only:

- Two distinct mock human subjects produce `APPROVED` and still do not mark the host `ACTIVE`.
- The same subject twice yields deny.
- A workload subject as a party yields deny.
- A hold with `not_after` in the past yields `TIMEOUT_DENY` and the mock egress does not occur.
- A missing `not_after` never opens.
- The audit row contains the ids and the decision, and a prompt canary is absent.

No live customer and no production approver.

## Risks

- `APPROVED` is displayed as if the host were already enforcing the new widen.
- Timeout is implemented as "proceed" to avoid stuck agents. That implementation contradicts this design.
- The unwired `phantom_deny_breakglass_off` executor gets wired inside this track. It stays unwired. A customer break-glass is a separate founder force, as E3 already says.

## Approval gates

- Founder decision before any hold is armed on a host.
- No change to E3 class tokens in this phase.
- Draft PR only. No founder-approved label.

## Council

Verdict: PASS_WITH_NONBLOCKING_NOTES

Recorded from the Claude Opus review of design head `3c2c581a48ef001c3ef78df232926d6c236acb88`. Detail is in `COUNCIL-VERDICT.md`. The producer does not sit the council.
