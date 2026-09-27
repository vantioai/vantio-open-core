# Unresolved Founder decisions

Audience: INTERNAL_RESTRICTED

Decisions EG-D1 through EG-D10 stay unresolved. The safe default is the behavior a later implementation uses while the decision is open. A default is not a silent resolution and is not a council pass.

No default in this file authorizes code, a Phantom Engine change, or execution of `07-FUTURE-FORCE.md`.

| Id | Decision | Safe default while unresolved | Consequence of leaving it open | Conflict if a later choice ignores the default without a new review |
| --- | --- | --- | --- | --- |
| EG-D1 | May a delegate redelegate? | `forbidden` | Further grants from a delegate are refused at proposal time | A redelegation bus that can mint authority the delegate does not hold breaks EG-E2-1 and doctrine invariant 9 |
| EG-D2 | How many distinct customer identities satisfy `WIDEN`? | Exactly two | No larger ceremony is designed | One identity, or the same identity twice, becomes class `REJECTED` material if it is later treated as `WIDEN` |
| EG-D3 | May Vantio witness an approval? | Optional witness on `WIDEN`, `ROOT`, and `RECOVERY`. The witness never counts toward quorum. `RECOVERY` completes with the witness absent | No required Vantio signer is introduced | A required Vantio signer on freeze, revoke, or recover breaks customer sufficiency |
| EG-D4 | Is the recovery party distinct from the root? | The customer may name a distinct customer-controlled recovery party. The root may also exercise `RECOVERY`. Vantio cannot be the recovery party | One customer-controlled path is enough | Naming Vantio as the recovery party is `REJECTED` |
| EG-D5 | Where does activation happen? | On the customer host. Phantom Engine verifies and attaches. An Enterprise store marks `APPROVED` only | No hosted "activate" button is specified | A console attach that skips the host breaks EG-SUB-1 |
| EG-D6 | Where does recoverable evidence live? | The customer-host export is sufficient to leave. A Vantio-held copy is not the recovery root. No store product is selected | Live Spanner write stays `TARGET_DESIGN` and is not chosen by this plan | A Vantio-only evidence copy breaks EG-E1-4 |
| EG-D7 | What are the numeric lifetimes for grants and exceptions? | Field required. Numbers `NOT_SET` | No duration is published as a product limit | A number chosen in code would be an invented budget |
| EG-D8 | Does company-host dogfood define the customer model? | Out of scope. The doctrine's named single-operator disable on the company host stays a Phantom Engine residual | Customer classes are not copied from that residual | Using that operator as the customer's only freeze or disable path breaks EG-SP-1 and EG-D3 |
| EG-D9 | How many identities are in the customer root set? | One customer-controlled identity, able to act while Vantio is absent | No m-of-n ceremony is selected | A root that can act only when Vantio is present breaks EG-E1-1 |
| EG-D10 | Who may narrow? | A delegate with a security grant may `NARROW` inside that grant. The root may always narrow. Widening stays `WIDEN` | Delegates are not given root acts | Letting a delegate change the owner set breaks EG-E3-5 |

## Decisions this packet refuses to open

| Topic | Position |
| --- | --- |
| Hardware root of trust, confidential computing, or a proof system | Unselected. The doctrine lists a hardware-rooted option as Roadmap and forbids "unbreakable" claims. This plan does not choose one |
| Certifications | None are held. No control in E1–E3 is a certification |
| Stable schema or a public API for grants | `schema_status` remains `unstable-pre-1.0` |
| Wiring `phantom_deny_breakglass_off` or the quarantine executor | Closed. Those executors stay unwired |
| Promoting the reference-monitor doctrine from `SCOPED` to a public claim | Closed |
| Changing Optics, package versions, or the documentation-release governance files | Closed |

## Earliest decision point

A Founder can leave every row on its default through council review of this packet. An implementation force is the earliest point that needs EG-D5 and EG-D6 confirmed, because those two choose where bytes would be written. This packet does not start that force.
