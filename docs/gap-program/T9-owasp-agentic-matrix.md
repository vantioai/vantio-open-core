# T9 — OWASP Agentic Top 10 matrix

Audience: INTERNAL

Phase: 1 design only. No feature code. This matrix is not a certification and not an assessment report for a customer.

Track label: Roadmap

Written: 2026-10-16T15:48:08Z

## Question

For each OWASP Agentic Top 10 item from ASI01 through ASI10, what can Optics, Gate, Phantom Engine, and Enterprise actually show today, and which cell is Verified, Lab-only, Roadmap, or Not addressed?

## How to read a cell

Verified means a repeatable proof in this tree demonstrates the control on the surface, and the proof was re-checked for this packet. No cell meets that bar.

Lab-only means a lab run showed the control and the limits of that run are named. No cell meets that bar. Scripts that exist are linked in the notes. Their existence is not a lab pass for the risk.

Roadmap means a track in this program, or a sibling T0–T5 charter, is the intended later control, and it is not built.

Not addressed means this program does not treat the risk as in scope, or no control is proposed on that surface.

Prompt scoring, answer scoring, and content moderation are out of scope. A cell that would require them is Not addressed. Constraining a destination, a tool, or an egress can still be Roadmap on Phantom Engine or Enterprise, because that is an action control.

Surfaces:

- Optics observes supported paths and does not block.
- Gate is application-path dry-run. `packages/vantio-gate-mcp/README.md` says it cannot block live traffic. A dry-run is not host activation.
- Phantom Engine is Enforce and Control on enrolled Linux only. The eBPF programs are not in this repository. This matrix does not regrade the 2026-10-06 product spec.
- Enterprise is the governance plan. E3 classes are `PLANNED`. GA-36 says planned approval is not live human oversight.

Names follow the OWASP Top 10 for Agentic Applications 2026 as published by the OWASP GenAI Security Project: ASI01 Agent Goal Hijack, ASI02 Tool Misuse and Exploitation, ASI03 Identity and Privilege Abuse, ASI04 Agentic Supply Chain Vulnerabilities, ASI05 Unexpected Code Execution, ASI06 Memory and Context Poisoning, ASI07 Insecure Inter-Agent Communication, ASI08 Cascading Failures, ASI09 Human-Agent Trust Exploitation, ASI10 Rogue Agents. This document does not copy OWASP's descriptions or mitigation text.

## Matrix

| ID | Optics | Gate | Phantom Engine | Enterprise |
| --- | --- | --- | --- | --- |
| ASI01 | Not addressed | Not addressed | Roadmap | Roadmap |
| ASI02 | Not addressed | Not addressed | Roadmap | Roadmap |
| ASI03 | Not addressed | Not addressed | Roadmap | Roadmap |
| ASI04 | Not addressed | Not addressed | Roadmap | Roadmap |
| ASI05 | Not addressed | Not addressed | Roadmap | Not addressed |
| ASI06 | Not addressed | Not addressed | Not addressed | Not addressed |
| ASI07 | Not addressed | Not addressed | Not addressed | Not addressed |
| ASI08 | Not addressed | Not addressed | Roadmap | Roadmap |
| ASI09 | Not addressed | Not addressed | Roadmap | Roadmap |
| ASI10 | Not addressed | Not addressed | Roadmap | Roadmap |

Count: Verified 0, Lab-only 0, Roadmap 16, Not addressed 24.

## Notes and scripts

### ASI01 Agent Goal Hijack

Optics and Gate do not read goals. `packages/vantio-cli/test/interceptor.test.js` shows a dry-run blocked host still reaches the target with status 200. That test is evidence the call is not stopped. It is not a goal-hijack control. Phantom Engine and Enterprise are Roadmap because T12 and T10 can later constrain the action and hold a consequential call without scoring the prompt. T4 owns tool-call awareness. None of that exists as a proof.

### ASI02 Tool Misuse and Exploitation

Same dry-run tests, plus `packages/vantio-gate-mcp/test/policy.test.js`, evaluate a decision and do not block. Gate stays Not addressed. Phantom Engine is Roadmap under T4. Enterprise is Roadmap under T10 for a consequential tool. Argument-level misuse is not tested anywhere in this tree.

### ASI03 Identity and Privilege Abuse

GA-16 states that process metadata on a wrapped path is not agent identity. GA-06 states there is no live delegation object. T6 is the consumer design and is Roadmap. Optics and Gate have no subject, issuer, or owner on an enforce event. `packages/vantio-cli/bin/vantio.js` prints a run-identity heading for a local run. That heading is not an owner.

### ASI04 Agentic Supply Chain Vulnerabilities

T11 is the design for plugin, hook, and skill changes and for unknown children. `packages/pe-host-authority/src/descendant.cjs` returns `kernel_executed: false` and does not block a child. `scripts/aws/lab-guests/descendant_b1.py` is a lab guest script. This packet does not run it and does not grade it. Supply-chain cells stay Roadmap on Phantom Engine and Enterprise, and Not addressed on Optics and Gate.

### ASI05 Unexpected Code Execution

The installer limitation text says path deny stays disabled. This repository does not contain the eBPF programs. The product spec's local exec tracepoint notes are not regraded here and are not an ASI05 proof. Phantom Engine is Roadmap. Enterprise does not stop code execution by a governance record, so that cell is Not addressed. Optics and Gate do not contain an execution control.

### ASI06 Memory and Context Poisoning

The program forbids keeping conversation content. Optics export work on the unmerged observability branch drops prompts from the allowlist. That is a privacy rule, not a detection of poisoned memory. All four cells are Not addressed.

### ASI07 Insecure Inter-Agent Communication

No inter-agent channel is built. T6 does not create one. All four cells are Not addressed.

### ASI08 Cascading Failures

T5 is the sibling charter for egress and side-channel drills. T10's timeout deny is the governance stop for a chain of held actions. Neither is implemented. Phantom Engine and Enterprise are Roadmap. Optics and Gate do not contain a cascade stop.

### ASI09 Human-Agent Trust Exploitation

A confident explanation is content, which this program does not score. The action control is T10: a human approval that does not trust the agent's text, with timeout deny. E3 is `PLANNED`. GA-07 and GA-36 say the same thing in the assurance catalog. Enterprise and Phantom Engine are Roadmap. Optics and Gate are Not addressed. Gate's dry-run text can be mistaken for enforcement; the Gate readme already says it cannot block live traffic, and this matrix does not treat that warning as a control.

### ASI10 Rogue Agents

Enrollment of a cgroup is the intended Phantom Engine boundary. T1 is the stranger-host charter and is not merged here. T3 is discovery. T6 binds an owner. `docs/planning/stranger-host-gate/scripts/refuse-stranger-host-execution.mjs` prints `STRANGER_HOST_EXECUTION_BLOCKED_AWAITING_AUTH` and exits 2. This packet does not call that refusal a rogue-agent proof. Optics can be skipped by not using the wrap, which the product boundary already states. Optics and Gate are Not addressed. Phantom Engine and Enterprise are Roadmap.

## NIST AI RMF

The catalog in `packages/governance-assurance/src/data/mappings.cjs` already maps GA controls to GOVERN, MAP, MEASURE, and MANAGE, with `vantio_fulfills_function` false. This table is a track crosswalk on top of that file. It does not add a claim that a function is fulfilled. Subcategory sentences are not copied. The framework version in the catalog is AI RMF 1.0, released 2023-01-26, voluntary, and the catalog notes that NIST has said 1.0 is being revised.

| Function | Tracks that would feed it later | Present state in this packet |
| --- | --- | --- |
| GOVERN | T6 owner, T10 approval, T14 outline | Design records only |
| MAP | T3 inventory, this matrix | T3 is a sibling charter, not in this commit |
| MEASURE | T8 export and the phase-2 proofs | Product OTLP is not authorized |
| MANAGE | T5, T7, T11, T12 | Designs or sibling charters |

## MITRE ATLAS

Tactic names only. Technique IDs are not pinned. This table uses the labels it has, including ML Model Access and ML Attack Staging. A later phase pins an ATLAS version before any technique row is written and before any renamed tactic is adopted. This list is a coverage sketch, not a detection claim.

| Tactic | Nearest track | Cell |
| --- | --- | --- |
| Reconnaissance | T3 discovery, if the sibling lands | Roadmap |
| Resource Development | T11 supply chain | Roadmap |
| Initial Access | T1 stranger host, T11 repo config | Roadmap |
| Command and Control | Omitted until an ATLAS version is pinned | Not addressed |
| ML Model Access | Out of scope for model evaluation. A later pin may use a different tactic title | Not addressed |
| Execution | T11 unknown children, ASI05 | Roadmap |
| Persistence | T11 hook and skill change | Roadmap |
| Privilege Escalation | T6 and the child-widen rejection | Roadmap |
| Defense Evasion | T5 sibling drills | Roadmap |
| Credential Access | T7 keep-out | Roadmap |
| Discovery | T3 | Roadmap |
| Lateral Movement | T7 and T5 egress | Roadmap |
| Collection | T8 records metadata only. Content collection is out of scope | Not addressed |
| ML Attack Staging | Model attacks are out of scope | Not addressed |
| Exfiltration | T5 and T8 claim fence | Roadmap |
| Impact | T10 timeout deny and enrolled deny | Roadmap |

## Threat model

The threat is a reader treating this matrix as a test report. The matrix is a gap list. A second threat is a Roadmap cell being copied into a website as a control. This packet does not authorize that copy.

## Failure modes

The matrix fails closed on claims. A missing proof is Roadmap or Not addressed. It is not filled with Verified because a nearby script exists. Reason: the program requires a repeatable proof for a claim, and this phase has none for these cells.

There is no runtime fail-open path. This track ships no runtime.

## Edge cases

- A script starts failing or starts passing after this commit. The cell does not move until a later force re-links it and a different-family review accepts the new label.
- OWASP renames an item. The matrix keeps the 2026 names above and records the rename in a later revision. It does not silently retitle a cell.
- A product-spec sentence says a kernel path was live-verified on WSL2 or local kind. That sentence stays in the product spec. It does not move an ASI cell to Verified or Lab-only inside this file.

## Memory footprint

The matrix is a document. No process is added. No memory budget is claimed.

## eBPF verifier limits

No new program. Verifier limits are unchanged. ASI05 and ASI10 stay Roadmap until a program in the Phantom Engine repository is tied to a proof this program accepts.

## Dependencies on T0–T5

| Track | Dependency |
| --- | --- |
| T0 | Own-stack hygiene sits under ASI04 and ATLAS Resource Development. This matrix does not grade T0 |
| T1 | Stranger-host refusal is related to ASI10 and is not a cell upgrade |
| T2 | Sandbox verification would be the lab home for several Roadmap cells. It is not a result here |
| T3 | Discovery is the MAP input for ASI03 and ASI10 |
| T4 | Tool-call awareness is the ASI02 Phantom Engine path |
| T5 | Egress and side-channel drills are the ASI08 and credential-egress path |

T6 through T8 and T10 through T12 are the controls this matrix points at. They are designs in this same packet, still Roadmap.

## Rollback

Rollback is `git revert` of this document. No host flag changes. A mistaken promotion of a cell to Verified is rolled back by restoring the cell to the value in the table above.

## Proof plan

Phase 1 proof is the design checker, which counts the cells and rejects a Verified or Lab-only mark in this file until a later force changes the checker and the council accepts the proof link.

Phase 2 does not bulk-promote cells. One cell moves only with one proof script, one evidence artifact, and a review of that head.

## Risks

- Sixteen Roadmap cells read as a commitment that the control is scheduled and staffed. They are a design pointer.
- The dry-run tests get cited as blocking tests.
- ATLAS technique IDs get invented to make the table look complete.

## Approval gates

- Internal only. Do not send this matrix to a customer or a reviewer outside the company.
- Do not edit public product docs from this track.
- A cell moves to Lab-only or Verified only in a later force with a proof. Draft PR only.

## Council

Verdict: PENDING_INDEPENDENT_REVIEW

The producer does not write the verdict.
