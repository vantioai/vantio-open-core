# Role and responsibilities

Audience: INTERNAL_RESTRICTED

Offer exhibit: yes

## Title

| Field | Value |
| --- | --- |
| Allowed titles | Head of Product, or Head of Product Engineering |
| Titles selected per offer | One of the two. Chosen before the offer is sent. |
| Titles outside this offer | Founder. Co-founder. Technical co-founder. CTO. |
| CTO consideration line | `POSSIBLE / UNDECIDED / NOT PROMISED / NOT APPROVED / NOT AUTOMATIC` |
| Automatic CTO succession | Outside this offer |
| CTO framework | Separate document. Not attached. See `OFFER-BOUNDARY.md`. |

The two allowed titles are alternative names for this one hire. They are not two seats, and they are not a path from one title into founder or CTO.

## Founder Master Program responsibilities list

WS13 requires this package to include the responsibilities list from the Founder Master Program. Retrieval on 2026-09-27:

| Location | Result |
| --- | --- |
| `vantioai/vantio-open-core` at `5064f32f1cdfcb840dfd100e2ce5c712d046550d` | No Founder Master Program file |
| GitHub code search, `org:vantioai`, phrases "Founder Master Program", "Head of Product", "Head of Product Engineering" | No code matches |
| Linear documents | No document |
| Sibling Founder Force briefs available in this run (master control plane, WS1 Units B and C, WS2, WS3, WS3 P34, WS5, WS6, WS7, WS8, WS9, WS10, WS12) | Each brief is its own force. None contains a Head of Product responsibilities list. The master control plane names the Founder Master Program only as the source of category boundaries. |

Status: `RESPONSIBILITIES_SOURCE_ABSENT`

Copied list:

| ID | Responsibility text from the Founder Master Program |
| --- | --- |
| — | None. The cell stays empty until the Founder supplies that program text and a later change pastes it here. |

Do not interview a candidate against a list that is not in the table above. Do not fill the table from memory, from a model draft, or from a generic Head of Product description and then label the result as the Founder Master Program.

## Duties the WS13 force does state

These rows are copied from the WS13 force. They are role boundaries for the offer. They are not a substitute Founder Master Program list.

| ID | Duty | Source |
| --- | --- | --- |
| WS13-1 | Hold exactly one of the allowed titles: Head of Product, or Head of Product Engineering. | WS13 force |
| WS13-2 | Keep founder, co-founder, and technical co-founder out of the title, the offer letter, and any equity legend in that offer. | WS13 force |
| WS13-3 | Keep CTO out of the offer. The consideration line is exactly `POSSIBLE / UNDECIDED / NOT PROMISED / NOT APPROVED / NOT AUTOMATIC`. | WS13 force |
| WS13-4 | Leave automatic CTO succession out of the offer. | WS13 force |
| WS13-5 | Leave the CTO evaluation framework off the offer. It is a separate future document. | WS13 force |

## Interim operating scope

Status: `INTERIM`. `NOT_FROM_FOUNDER_MASTER_PROGRAM`.

This scope is how the company can use the hire before the missing program list is pasted. It is bounded by documents that already exist. It is not an invented product plan.

| ID | Scope | Bound |
| --- | --- | --- |
| INT-1 | Keep external product sentences aligned with `docs/governance/canonical/product-boundary.md` on the base commit above. | A sentence that adds a mechanism, a price, or a proof the canonical file does not state is withheld. |
| INT-2 | Treat Optics, Phantom Engine, and Enterprise as the three commercial categories in that canonical file. Optics is free local-first observe. Phantom Engine is Enforce + Control on enrolled Linux hosts at the price stated there. Enterprise is governance on top of that protection and is talk-to-sales. | This package does not add a fourth commercial product. |
| INT-3 | Bring a Founder checkpoint before a change to a public claim, a published price, a release, or a customer commitment. | The hire does not hold that checkpoint alone. |
| INT-4 | Leave frozen release artifacts unchanged unless a later Founder force reopens them. At this base commit, `@vantio/cli` is `0.3.24` and `vantio-agent-sdk` is `3.1.0` in tree. | This hiring package does not reopen either artifact. |

Canonical product facts used above were read from `docs/governance/canonical/product-boundary.md` and the package manifests on `5064f32f1cdfcb840dfd100e2ce5c712d046550d`. Phantom Engine customer manuals are out of scope for this package.
