# T14 — EU AI Act evidence pack outline

Audience: INTERNAL

Phase: 1 design only. An outline of a future evidence pack. Not a conformity assessment, not a classification, and not a registration.

Track label: Roadmap

Written: 2026-10-16T15:48:08Z

## Question

What would an internal evidence pack need to contain before 2 December 2027, and which of those contents are already refused or missing?

## Date and source

The European Commission AI Act Service Desk states that Article 113, as amended by Regulation (EU) 2026/1744, applies Chapter III, Sections 1, 2, and 3, except Article 6(5), from 2 December 2027 for AI systems classified as high-risk under Article 6(2) and Annex III, and from 2 August 2028 for high-risk systems under Article 6(1) and Annex I. The Service Desk FAQ states the same Annex III and Annex I dates. This outline uses 2 December 2027 as the program's target date for an evidence pack. It is one application date among several. It is not the only date in the regulation.

Source used: the public Service Desk page for Article 113 and the public FAQ, retrieved for this design on 2026-10-16. Article text is not copied. The AI Act identifier in the assurance catalog remains Regulation (EU) 2024/1689, with the catalog note that the register does not collapse multiple application dates into one effective date.

This outline does not classify any Vantio system or any customer system as high-risk, limited-risk, or prohibited. Classification stays with the customer and counsel. GA-04 already says that, including for Articles 6, 27, 43, and 49 as identifiers only.

`packages/governance-assurance/src/data/mappings.cjs` sets `vantio_fulfills_function` false and `legal_classification` to `NOT_A_LEGAL_CLASSIFICATION`. Those flags stay. This outline does not edit that package.

## Current evidence the pack could point at

| Topic the catalog already names | What exists | What the pack must say |
| --- | --- | --- |
| Technical documentation, catalog note on Art. 11 | Metadata on supported paths | This is not the legal technical file |
| Record-keeping, catalog notes on Art. 12 | Destination, process, size, and timing on supported observe paths | Not a complete log. Product OTLP is not authorized. Local ledger is mutable |
| Human oversight, catalog note on Art. 14 | T10 design. E3 is `PLANNED`. GA-36 | Planned approval is not live oversight |
| Accuracy, robustness, cybersecurity, catalog note on Art. 15 | GA-13 says runtime enforcement is unverified in this tree | This outline does not reverse that sentence |
| Data governance, catalog note on Art. 10 | Training-data duties stay with the customer and the model provider | Vantio does not hold training corpora. Conversation content is not kept |
| GPAI provider duties, catalog note on Art. 53 | Identifier only | Vantio is not claiming those duties |
| Incident reporting, catalog note on Art. 73 | No authority notification | The pack does not notify an authority |
| Transparency, catalog note on Art. 13 | Disclosure row only | Not a user-facing transparency file for a customer's system |

## Outline of the future pack

The pack, if a later force writes it, has these sections and no others until counsel adds one. Each section's phase-1 content is the gap, not the evidence.

1. Cover. Internal. Date target 2 December 2027. Statement that the pack is not a classification and not a declaration of conformity.
2. System boundary. Enrolled Linux hosts, supported observe paths, and the governance designs in this packet. Stranger hosts and unenrolled processes are outside the boundary. No cloud authorization boundary is implied.
3. Intended purpose, written by the customer. Blank in any Vantio-authored template.
4. Record-keeping description. Points at Optics limits and at T8, including `MUTABLE_LOCAL_LEDGER` and `product_otlp_export_authorized` false.
5. Human oversight description. Points at T10 and at the E3 status `PLANNED`. Includes timeout deny and the rule that the workload is not an approver.
6. Cybersecurity description. Points at the T9 matrix, with Verified count 0, and at T7 and T11 as designs.
7. Change log of the pack. Git revision, not a conformity version.
8. Explicit omissions. Prompts, credentials, prices, article quotations, a notified-body name, a registration number, and any wording that would claim fulfillment.

A template that fills section 3 with Vantio's marketing sentence is a failed pack. The customer writes the purpose.

## Threat model

| Threat | Response |
| --- | --- |
| The outline is read as a completed technical file | Every section above is a gap list |
| 2 December 2027 is treated as the only legal date | The outline names 2 August 2028 as well and refuses to collapse dates |
| A cell in T9 is attached as conformity evidence | T9 has zero Verified cells |
| The pack is sent to a market-surveillance authority or a customer counsel as Vantio's filing | Sending outside the company is an approval gate this phase does not open |
| Article text is copied in to look complete | The catalog already forbids copied clause text. This file does too |

## Failure modes

Fail closed on the claim. If a section has no evidence, the pack says the section is empty. Reason: an empty section that reads as satisfied would be a false file.

There is no product fail-open. This track does not change runtime behavior. A missing pack does not block or allow an agent.

## Edge cases

- The regulation is amended again before 2 December 2027. The outline is revised or withdrawn. The date in the cover is updated only with a new public source. It is not guessed.
- A customer system is not in Annex III. The pack is still not a classification. The customer may have nothing to file. Vantio does not decide that.
- Counsel asks for article quotations. Those quotations stay outside the repository. The pack keeps identifiers and the catalog's relationship notes.
- Another application date arrives first, including dates in 2026. This outline does not claim those dates are covered.

## Memory footprint

No process. The future pack is a document with a size cap set when it is generated. This phase produces only this outline.

## eBPF verifier limits

No program. Kernel verification status is not a cybersecurity article claim. GA-13 remains the catalog sentence.

## Dependencies on T0–T5

| Track | Dependency |
| --- | --- |
| T0 | Own-stack hygiene may later be an internal change-log input. It is not an article claim |
| T1 | The enrolled-host boundary should match the stranger-host charter. A mismatch is a pack defect |
| T2 | A sandbox result is lab evidence only if T2 produces one. None is in this commit |
| T3 | Inventory is the candidate list of agents a customer might describe. T3 has not landed |
| T4 | Tool-call records would feed record-keeping and are not implemented |
| T5 | Egress evidence would feed the cybersecurity section and is a sibling charter |

T6, T8, T9, T10, and T11 are the internal inputs sections 4 through 6 would cite. They are Roadmap.

## Rollback

`git revert` of this outline. No customer file is generated in phase 1, so there is no customer artifact to recall. A later pack is withdrawn by deleting the generated file and recording the deletion in the change log. Withdrawal is not a public statement.

## Proof plan

Phase 1 proof is the design checker. It requires the strings `2 December 2027`, `2 August 2028`, and `AI Act Service Desk` in this file, and it rejects an affirmative fulfillment sentence. It does not fetch the regulation text, and it does not change `vantio_fulfills_function` in the assurance package.

Phase 2 is still an outline review with counsel inside the company. It does not fill the template and does not notify an authority.

## Risks

- The target date is quoted without the Annex III qualifier and without 2 August 2028.
- The catalog is edited so `vantio_fulfills_function` becomes true. This track forbids that edit.
- Section 3 is drafted by Vantio as the customer's intended purpose.

## Approval gates

- Counsel inside the company before any pack is shown to a customer.
- No notification to an authority. No customer send.
- No edit to `packages/governance-assurance` in this phase.
- Draft PR only.

## Council

Verdict: PENDING_INDEPENDENT_REVIEW

The producer does not write the verdict.
