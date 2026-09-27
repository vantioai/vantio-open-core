# E1 — Ownership

Audience: INTERNAL_RESTRICTED

Status of every object in this file: `PLANNED`. Evidence tier `UNSET`. Customer validation `UNSET`. `schema_status` `unstable-pre-1.0`.

Parent boundary: `00-PROGRAM-BOUNDARY.md`. Customer-sufficiency rule: `04-SUBORDINATION-AND-CUSTOMER-SUFFICIENCY.md`.

## 1. What ownership means here

Ownership is the customer's title to authority over enrolled Linux they own. A delegate may exercise a subset for a limited time. Exercise is not title.

Phantom Engine remains the authority boundary that attaches enforcement on that host. Enterprise records title, intent, and approval. The host report is the source of what is active.

Free Optics observation stays account-free. E1 does not place local Optics logs under an Enterprise owner record.

## 2. Parties

| Party | Holds title? | Can exercise freeze, revoke, and recover alone? | Notes |
| --- | --- | --- | --- |
| Customer root | Yes | Yes, including when a separate recovery party also exists (EG-D4 default) | One or more customer-controlled identities. Vantio identities are not members of this set |
| Customer recovery party | No, unless the root has also placed that party in the root set | Yes for freeze, recover, export, and leave | Customer-controlled. Vantio cannot be this party |
| Customer delegate | No | Only inside an explicit grant, and never as the sole path for root recovery | E2 |
| Workload | No | No | A workload never receives security or recovery title because it runs on the host |
| Vantio | No | No | Optional witness under EG-D3. Vendor support and billing sit outside the authority boundary |

The minimum size of the customer root set is decision EG-D9. The safe default is one customer-controlled identity that can act while Vantio is absent. That default is not a silent choice of a multi-party ceremony.

## 3. Owned objects

### EG-E1-1 Customer authority root

The root is the customer's right to:

- name the owner set
- name or replace the recovery party
- record enroll intent and retire intent for hosts the customer owns
- issue and revoke delegations
- export evidence, hash it, roll back, and uninstall
- remove Vantio from a witness or management role without giving up the actions above

Title stays with the root when a delegate acts, when a grant expires, and when a Vantio-held copy of a record is unavailable.

A support request, a billing state, or a control-plane outage does not move title to Vantio.

### EG-E1-2 Hosts

The Linux host is the customer's. Enrollment puts that host inside the Phantom Engine boundary for as long as the customer keeps it enrolled.

Enterprise may store the customer's enroll intent or retire intent. The on-host enroll and unenroll actions remain Phantom Engine operations on that host. This repository does not ship those operations, and this plan does not add them to Optics.

Retire intent is an ownership record. A process that is still running after a retire record is the doctrine's roadmap contradiction ("Enterprise says the agent is retired, but the process is active"). E1 requires that contradiction to stay visible. It does not claim a present control that stops the process.

### EG-E1-3 Policy intent

The customer owns the declared envelope: destinations, path constraints, spend and size caps, and the named posture.

A versioned decision record names who proposed it, which approval class was satisfied, the version, and the rollback target. Those fields match the doctrine's invariant 5 target (no policy change becomes active without attributable authority and a versioned decision). Invariant 5 is Partial today. Host policy is not yet a signed versioned decision a non-dashboard verifier can check. E1 specifies the record and leaves that gap `UNSATISFIED`.

`APPROVED` on an Enterprise record and `ACTIVE` on the host are different states. Section 5 of E3 binds the display rule.

### EG-E1-4 Evidence

The customer can export evidence and leave with it. The doctrine's present customer-pack sequence is export, then hash, then rollback, then uninstall. Invariant 10, which includes verify, export, and leave, is Partial. This plan keeps that sequence as a customer-owned action.

Local append-oriented NDJSON is the verified ledger named in the product spec. The same doctrine says that local ledger is not WORM, and that a process with write access to the log can truncate it. Live Spanner write is `TARGET_DESIGN`. This plan does not select Spanner, another WORM product, or a notarization scheme (EG-D6).

A design in which the only recoverable copy of customer evidence is reachable solely through Vantio fails EG-E1-4.

Governance records in this packet must not store prompts, completions, raw bodies, or credentials. Identity fields are opaque customer-held identifiers. `docs/enterprise/FUTURE_AUTONOMY_NORTH_STAR.md` states a trust assumption that Vantio consumes identity and does not become the identity provider. E1 adopts that assumption as a planning constraint. It does not select a provider.

### EG-E1-5 Governance records

Delegation grants and approval records are Enterprise objects. The customer root owns them.

Vantio may keep a witness copy. The customer-held record is enough to show who holds title and which grant is in force. Loss of the witness copy does not erase title and does not disable the customer's freeze, revoke, or recover path.

### EG-E1-6 What stays outside Enterprise title

| Object | Owner of the mechanism | E1 treatment |
| --- | --- | --- |
| Kernel enforcement programs, maps, and egress drops | Phantom Engine on the customer host | Enterprise does not take title and does not load them |
| Application-path enforce inside Phantom Engine (Gate, internal name) | Phantom Engine | Dry-run in this repository stays a compatibility tool. It is not an ownership record |
| Local Optics observation | The person who ran Optics on that machine | Remains account-free |
| Billing and support consoles | Vendor operations | Outside the trusted boundary. They may degrade. They do not hold title |
| Certifications | None held | E1 does not create a certification object |

## 4. Revoke, as an ownership act

Revoke in this plan is the customer taking exercise back.

| Act | Who can do it | Effect on title |
| --- | --- | --- |
| Revoke a delegation | The customer root, or the delegator who issued that grant, inside the rules in E2 | Title stays with the root |
| Remove Vantio's witness or management role | The customer root | Title stays with the root. Vantio's copy becomes optional residue |
| Revoke a workload's permission to connect | Recorded by the customer. Disconnection on the host is a Phantom Engine consequence | The doctrine lists "identity revoked, workload still connecting" as Roadmap. The record is `PLANNED`. The disconnection is `UNSATISFIED` |

None of these acts require a Vantio approval. A Vantio-only credential that performs them is class `REJECTED` in E3.

## 5. Loss of the root

If the customer root credentials are lost, recovery of title uses the customer recovery party named before the loss. That party is customer-controlled (EG-D4).

Vantio does not unilaterally appoint a replacement root. A vendor-led replacement of the customer root is class `REJECTED`.

How the customer protects the root credentials (ceremony size, offline copies) stays with the customer. This plan sets no numeric threshold (EG-D9).

## 6. Requirement index

| Id | Statement | Status |
| --- | --- | --- |
| EG-E1-1 | Customer root holds title to customer authority. Vantio is not a member of the root set | `PLANNED` |
| EG-E1-2 | Host title stays with the customer. Enterprise stores enroll and retire intent. Phantom Engine on that host is the enroll mechanism | `PLANNED` |
| EG-E1-3 | Policy intent is a versioned customer decision. Host attachment is a separate state | `PLANNED` |
| EG-E1-4 | Export, hash, rollback, and uninstall remain customer-sufficient. The only recoverable evidence copy is not Vantio-only | `PLANNED` |
| EG-E1-5 | Grants and approvals are customer-owned records. A missing Vantio copy does not erase them | `PLANNED` |
| EG-E1-6 | Kernel enforcement, Optics observation, and billing stay outside Enterprise title | `PLANNED` |

## 7. Current hooks this ownership model does not upgrade

| Hook named in Phantom Engine sources | What this plan may say about it |
| --- | --- |
| Customer pack healthcheck, rollback, uninstall, and exit | Present as scripts in the doctrine. Not a stranger-host pass. Not E1 implemented |
| `pe_protection_state` on the host without the management console | Present as an on-host reporter. Not an ownership registry |
| Company-host disable that depends on the named company operator | Dogfood residual. Excluded from the customer root by EG-D8 |
| Append-oriented local NDJSON | Verified local ledger in the product spec. Not WORM. Not an Enterprise title system |
