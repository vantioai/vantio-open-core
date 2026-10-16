# T12 — Policy preview

Audience: INTERNAL

Phase: 1 design only. No feature code.

Track label: Roadmap

Written: 2026-10-16T15:48:08Z

## Question

How can an operator see the decision a policy would make, including the identity and the would-be effect, without that preview applying the policy or turning enforcement on?

## Current evidence

Two different things are already called preview or dry-run. They are not this control.

- `packages/optics-otel-mapping/src/preview.cjs` maps Optics display fields toward a canonical record shape. It does not evaluate a policy and it does not block or allow a call.
- `packages/vantio-gate-mcp` exposes `gate_evaluate` as a dry-run. The package readme says live enforcement is `vantio run` plus Phantom Engine policy, and that this MCP cannot block live traffic. `packages/vantio-cli/test/interceptor.test.js` shows `dry_run: true` lets the blocked host through and records a dry-run event.
- E3 lists counting a dry-run as host activation as a rejected act.
- `packages/pe-egress-authority/src/decision.cjs` and `tests/pe-egress/adversarial.test.cjs` record a dry-run deny as `dry_run_pass_through`. There is no `packages/pe-egress` directory.

So a preview-shaped tool exists, and it is defined as non-activating. It does not yet show T6 identity, a T10 hold, or a T11 manifest refusal. It can be mistaken for enforcement. That mistake is the gap.

## Design

Preview is a read. It takes a proposed action and the candidate policy, runs the same decision function Enforce would run, and returns a record. It does not write the active policy, does not change a hold, does not start an agent, and does not dial a broker.

The record contains:

| Field | Content |
| --- | --- |
| `decision` | `WOULD_DENY`, `WOULD_ALLOW`, or `WOULD_HOLD` |
| `reason` | A stable token |
| `agent_identity` and `owner` | From T6, or `UNVERIFIED` |
| `destination` | Host and port only |
| `effect` | The would-be class: observe, deny, hold, or credentialed dial |
| `policy_digest` | Hash of the candidate policy bytes |
| `applied` | Always `false` |

`WOULD_ALLOW` means the decision function returned allow. It does not mean the call happened.

Flags: if a request sets both preview and enforce, the request is refused and nothing is applied. If a request sets preview and also asks to arm a T10 hold or publish a T11 manifest, the request is refused.

The existing `gate_evaluate` path is the ancestor for the application-path decision. Preview adds the identity, hold, and manifest reasons. It does not add a second decision engine. Kernel enforcement stays in Phantom Engine and is not simulated by printing `WOULD_DENY` from userspace. The record includes `surface: application-path` until a later force can show a host decision from the loaded program. This phase always uses `surface: application-path`.

## Threat model

| Threat | Response |
| --- | --- |
| Preview used as the activation proof | `applied` is false and the API refuses a combined enforce flag |
| Candidate policy wider than the active one is saved by the preview handler | Preview has no write path |
| Preview output includes a prompt or a T7 secret | Same allowlist as T8. Secrets and prompts are omitted |
| Operator treats `WOULD_ALLOW` as coverage of unenrolled paths | The record names the surface. Unenrolled and kernel surfaces are absent |
| A bug returns `WOULD_ALLOW` on an evaluator exception | Exceptions become `WOULD_DENY` with reason `PREVIEW_ERROR` |

## Failure modes

Fail closed for application. Any error, missing policy, missing identity, or combined flag refuses the request and writes nothing. Reason: a broken preview must not change the host, and it must not look like an allow.

Fail open for reading the error. The operator receives `PREVIEW_ERROR` and `applied: false`. Reason: hiding the error would push the operator to apply a policy they could not see.

The live enforce path is unchanged by a preview failure. Preview does not take a lock that stalls enrolled traffic. If a later implementation shares a lock with enforce, a preview wait past a short bound is cancelled and enforce proceeds on the active policy. This design prefers no shared lock.

## Edge cases

- Candidate policy is empty. Result is `WOULD_DENY`, reason `EMPTY_POLICY`, `applied` false.
- Candidate policy sets `dry_run: true`. Preview reports `WOULD_ALLOW` only together with reason `DRY_RUN_PASS_THROUGH`, so the operator can see that the ancestor dry-run does not block. It does not report that as `WOULD_DENY`.
- Identity `UNVERIFIED` on an enforce-class action. Result is `WOULD_DENY` once T6's rule is in force. Until T6 exists, preview returns `WOULD_DENY` with reason `IDENTITY_NOT_AVAILABLE` for any action that would need an owner. It does not guess an owner.
- Two previews at once. They do not share mutable state.
- Preview of a T11 risky repo. Result is `WOULD_DENY` with reason `MANIFEST_MISMATCH` when the manifest module exists. Until T11 exists, the reason is `MANIFEST_NOT_AVAILABLE` and the decision is `WOULD_DENY` for a start action.

## Memory footprint

One preview reads the candidate policy up to a cap the implementation sets, then discards it. Over the cap, `PREVIEW_ERROR`. No policy store is appended. No memory number is claimed.

## eBPF verifier limits

No program is loaded or generated. Preview must not compile a BPF program to answer the question. A host-surface preview waits until the loaded program can be queried without a new verifier pass. That query is outside phase 1.

## Dependencies on T0–T5

| Track | Dependency |
| --- | --- |
| T0 | Preview code is company code and inherits T0 |
| T1 | Preview on a stranger host is not evidence about an enrolled host |
| T2 | The sandbox is a place to show `applied` stays false |
| T3 | The agent named in the preview comes from inventory, not from a free-typed label |
| T4 | Tool-call preview uses the same record. T4 does not apply it |
| T5 | A preview must not itself be an egress of the payload. The evaluator sees metadata |

T6, T10, and T11 supply identity, hold, and manifest reasons. T8 may export the preview record only if the customer asks, with `applied: false` and the allowlist. Export is off by default.

## Rollback

There is no applied state to undo. Rollback removes the preview command. Existing `gate_evaluate` behavior stays as it is on main. Rollback does not flip `dry_run` off and does not enable enforce.

## Proof plan

Phase 2 tests, local only:

- A candidate policy that names a blocked host returns `WOULD_DENY` and `applied: false`, and the active policy file's bytes are unchanged.
- The same request with an enforce flag returns a refusal, and the active file is unchanged.
- A fixture with `dry_run: true` returns `DRY_RUN_PASS_THROUGH` and does not return a bare allow.
- A prompt canary in the proposed action is absent from the result.
- `packages/optics-otel-mapping/src/preview.cjs` is not used as this proof.

## Risks

- The word preview is already used for OTEL field mapping. A reader merges the two.
- `WOULD_ALLOW` is copied into a status page as protected.
- Preview and enforce share a write path in a later patch.

## Approval gates

- No live policy write and no host activation in the implementation force until a separate founder decision.
- Draft PR only.

## Council

Verdict: PASS_WITH_NONBLOCKING_NOTES

Recorded from the Claude Opus review of design head `3c2c581a48ef001c3ef78df232926d6c236acb88`. Detail is in `COUNCIL-VERDICT.md`. The producer does not sit the council.
