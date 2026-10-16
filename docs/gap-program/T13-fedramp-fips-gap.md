# T13 — FedRAMP and FIPS gap assessment

Audience: INTERNAL

Phase: 1 design only. This is a gap list. It is not an authorization package, not a control implementation, and not a validation certificate.

Track label: Roadmap

Written: 2026-10-16T15:48:08Z

## Question

What is missing before anyone could even discuss a FedRAMP boundary or a FIPS module claim, and which of those gaps are already refused by the assurance catalog?

## Current evidence

`packages/governance-assurance/src/reports.cjs` refuses ATO, FedRAMP authorization, agency acceptance, and procurement approval. Control text in that package says proof class is not raised by the audience. `vantio_fulfills_function` is false on mapping rows. The catalog's federal rows point at OMB memoranda as boundaries for the agency, not as duties Vantio has met.

No CMVP certificate number is recorded in this repository for a Vantio module. This design does not invent one. Node's crypto, the host kernel, and the distro OpenSSL are not asserted to be operating in a validated mode.

Phantom Engine's boundary in the product spec is an enrolled Linux host the customer runs. Managed-cloud Kubernetes and a live Spanner write are `TARGET_DESIGN` in that spec. A FedRAMP boundary is an agency authorization boundary. This track does not draw one.

Public pricing language stays "Contact Vantio". Commercial terms are not part of an authorization discussion in this file.

## Design

The assessment is a table of families. Each row is GAP. Family names are the usual labels only. Control sentences from NIST SP 800-53 are not copied.

| Family | Status | Gap this packet records |
| --- | --- | --- |
| Access control | GAP | E3 approval classes are `PLANNED`. No live dual control. T10 is a design |
| Audit and accountability | GAP | Local NDJSON is mutable. T8's validator is specified to return `MUTABLE_LOCAL_LEDGER`. Product OTLP is not authorized. No log store in this packet is an authorized store |
| Assessment and authorization | GAP | No package, no boundary diagram an agency could inherit, no 3PAO, no SSP. This row stays GAP on purpose |
| Configuration management | GAP | The public pin stays `e0b19d55`. This packet adds no signing root and no baseline image |
| Identification and authentication | GAP | T6 consumes customer identities and is not built. No federal issuer is configured. Mocks only, later |
| System and communications protection | GAP | FIPS gap below. No validated module claim. TLS in the 2026-10-10 drill used a local test CA |
| System and information integrity | GAP | T11 manifest checks are a design. They are not a file-integrity program under an authorization |

FIPS gap, also GAP:

- Inventory of cryptographic modules on an enrolled host is not done. Phase 2 may list module names from a lab host the program allows. The list is an inventory, not a validation.
- No certificate number, no operational-environment string, and no assertion that a module's validated mode is on.
- A customer who needs FIPS uses modules they validate on their host. Vantio does not supply that validation by shipping Node or by linking OpenSSL.
- The T7 broker and the T8 exporter, when they exist, must be able to run against the customer's module. That is a requirement statement. It is not a test result.

Out of this assessment: drawing a formal boundary, writing an SSP, contacting an agency, contacting a 3PAO, and selecting a cloud region. Those are approval gates, not phase-2 tasks.

## Threat model

| Threat | Response |
| --- | --- |
| This file is forwarded as a readiness claim | The track label is Roadmap and every row is GAP |
| A lab TLS success is described as FIPS | The 2026-10-10 drill used a local test CA. That is not a validated module |
| A pricing or hosting choice is treated as an authorization boundary | No boundary is drawn. No price is written |
| Control text is pasted in from a catalog | This file uses family names only |

## Failure modes

The assessment fails closed on claims. Missing evidence stays GAP. Reason: an empty cell is not a pass, and the assurance catalog already refuses authorization language.

There is no runtime. Nothing fails open.

## Edge cases

- A later module inventory finds a CMVP number on a distro package. The number is recorded as the distro's number, with the operational environment still unmatched, and the Vantio row stays GAP.
- An agency asks for a subset of families. The answer is still this gap list. Subsetting does not promote a row.
- Product-spec local kernel verification is offered as SC evidence. It is a different claim, on a different boundary, and it does not fill the FIPS row.

## Memory footprint

No new process. No memory claim.

## eBPF verifier limits

No new program. Verifier status is not evidence for a cryptographic module claim.

## Dependencies on T0–T5

| Track | Dependency |
| --- | --- |
| T0 | Company-stack hygiene would be part of a future configuration-management story. It is not a FedRAMP control |
| T1 | A stranger-host proof is not an authorization boundary |
| T2 | A verified sandbox is not a validated cryptographic module |
| T3 | Inventory of agents is not an account inventory for access control |
| T4 | Tool awareness does not authenticate a federal user |
| T5 | Egress drills do not select a protected transport under FIPS |

T6, T8, T10, and T11 are the designs that would later feed IA, AU, AC, and SI. They are Roadmap. They do not close these rows.

## Rollback

`git revert` of this document. No host configuration changes. Rollback of a future inventory is deleting the lab inventory file. It does not revoke a certificate, because no certificate is held.

## Proof plan

Phase 1 proof is the design checker. It requires the status column of each family row above to be exactly GAP. A later GAP word in the same row does not satisfy that column. It also rejects the literal claim phrases named in `scripts/gap-program/check-p1-design.mjs`. It does not parse an arbitrary authorization sentence, and it does not score a control as implemented.

Phase 2, only if a founder force allows a lab host: write an inventory of module names and versions, with a column `validation` set to `NOT_CLAIMED` on every row. Do not query CMVP from this program if that query is a stand-in for a claim. Reading a public certificate list is a later force.

## Risks

- Family names get expanded into copied control text.
- "Gap assessment" is shortened to "FedRAMP" on a slide.
- A test CA from the observability drill is reused as if it were a validated module.

## Approval gates

- No 3PAO, no agency, no cloud authorization package.
- No FIPS claim and no certificate number added by this program.
- Internal only. Draft PR only.

## Council

Verdict: PENDING_INDEPENDENT_REVIEW

The producer does not write the verdict.
