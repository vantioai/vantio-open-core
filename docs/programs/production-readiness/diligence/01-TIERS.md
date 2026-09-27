# Handling tiers

Audience: INTERNAL_RESTRICTED

Document status: CONTROL

External publication: PROHIBITED

Four tiers exist so a later human can label a finished artifact. This directory does not contain a finished artifact at any tier.

## PUBLIC

Facts already present in the public manual, `README.md`, or `docs/PRODUCT_LINEUP.md`.

A later promotion may quote a public fact only with the source path and the date that file was re-read. This room does not add a new public page, and it does not change canonical docs under `docs/governance/canonical/`.

## INVESTOR_UNDER_NDA

Slot for a future redacted packet that a human has cleared for a named investor under a signed agreement.

No file in this scaffold is cleared for that send. Amounts, dates, customer identities, and roadmap commitments stay `NOT_SET` until that review. The presence of a section heading is not clearance.

## INTERNAL_RESTRICTED

Default handling for this directory. Engineering, architecture, release, and evidence notes stay here. They are not investor copy and not customer copy.

## CUSTOMER_CONFIDENTIAL

Slot for a later artifact that names a customer, a workload, or a Phantom Engine customer deliverable.

This repository does not hold that body. Pilot and design-partner skeletons keep the field names and set the values to `REDACTED` or `NOT_SET`. A customer manual stays out of this path and out of public package file lists. See `docs/governance/PE-CUSTOMER-BUNDLE.json` and `docs/governance/PACKAGING-EXCLUSION.json`.

## Rules

| Rule | Meaning |
| --- | --- |
| Room audience | Every file in this directory is `INTERNAL_RESTRICTED` today. |
| Future slot | The manifest records the tier a finished document might use. The slot is not a grant. |
| Promotion | A human copies a reviewed subset to a separate artifact. Promotion does not happen by editing the audience line in place and emailing the file. |
| Downshift | When a fact's only support is internal, the investor slot stays closed for that fact. |
| Empty confidential | `CUSTOMER_CONFIDENTIAL` has a definition and no body. |
| Proof | Tier of handling and tier of evidence are different fields. `INVESTOR_UNDER_NDA` does not mean `CUSTOMER_VALIDATED`. |

## Who may fill a slot later

A founder review, against the source file named in the skeleton, on a commit recorded in the fill. This scaffold does not name a delegate and does not authorize an agent to invent the fill.
