# T6 — Identity interop

Audience: INTERNAL

Phase: 1 design only. No feature code.

Track label: Roadmap

Written: 2026-10-16T15:48:08Z

## Question

How does an enrolled Linux host consume an agent identity and an owner from the customer's identity system, put both on every enforcement event, and avoid becoming an identity provider?

## Current evidence

Vantio does not issue identities. The Phantom Engine future-autonomy note, as read for the E1–E3 plan, already says Vantio consumes identity and does not become the identity provider. That sentence is a scoped note. It is not a shipped connector.

What this tree has today:

- Optics records process, destination, size, and timing on supported paths. `packages/governance-assurance` control GA-16 says that process metadata is not agent-identity infrastructure. `vantio_fulfills_function` is false on every mapping row.
- `@vantio/cli` run output has a display section titled "Run identity". That is a local run label, not an Entra, Okta, or SPIFFE subject.
- `architecture_state.md` describes a historical enterprise SAML page with an identity-provider menu. That page is not the current control plane and is not a connector.
- Enterprise approval classes in `docs/planning/enterprise-governance/03-E3-APPROVAL-CLASSES.md` are `PLANNED`. A workload identity fills neither seat of a `WIDEN` quorum.
- The NIST NCCoE concept paper of 2026-02-05 is cited by GA-06 as a concept paper. This tree has no live delegation object.

No Entra Agent ID tenant, Okta for AI Agents tenant, or SPIRE deployment is in scope for this phase. Later code uses mocks and test issuers only.

## Design

Vantio stores a reference. It does not mint a subject, a certificate, or a token.

The reference has four fields, all required on an Enforce or Control event:

| Field | Content |
| --- | --- |
| `issuer` | Customer issuer URL or SPIFFE trust domain. Mock issuers end in `.test` or `.invalid` |
| `agent_identity` | Stable subject the customer already issued for this agent |
| `owner` | Stable subject of the human or service owner the customer names. A workload subject is never stored in this field |
| `verification` | `VERIFIED` or `UNVERIFIED` |

Observe may record `verification` `UNVERIFIED` and still keep the event. Enforce and Control treat `UNVERIFIED`, a missing `owner`, or a missing `agent_identity` as a deny. The deny reason is recorded. The raw assertion, the token, and any prompt are not fields.

Sources, in the order a later implementation may add them:

1. A mock SPIFFE ID, shaped `spiffe://lab.invalid/ns/mock/sa/agent`, checked against a test trust bundle generated in the test. SPIRE is not installed.
2. A mock OIDC assertion whose issuer is `https://login.microsoftonline.test/mock-tenant` for the Entra Agent ID shape, or `https://mock.okta.test/oauth2/mock` for the Okta for AI Agents shape. The signing key is a test key created in the test process and discarded. Audience, expiry, and issuer are checked. A wrong audience or an expired assertion is `UNVERIFIED`.

The customer trust bundle is configuration the customer supplies. Vantio does not phone Microsoft or Okta from this design, and it does not embed a production root.

Binding the reference to a process uses the enrolled cgroup and the process lineage Phantom Engine already intends to watch. A child does not widen the parent's identity. `packages/pe-host-authority/src/descendant.cjs` already rejects a child widen in unit code, with `kernel_executed: false`. That unit helper is not this connector.

## Threat model

| Threat | Boundary | Design response |
| --- | --- | --- |
| Agent presents another agent's subject | Enrolled workload | Signature must match the customer bundle. Mismatch is `UNVERIFIED` and Enforce denies |
| Stolen assertion replayed after expiry | Clock on the host | Expiry is required. Missing expiry is `UNVERIFIED` |
| Owner field set to the agent itself | Event schema | Schema rejects an owner equal to the agent subject |
| Vantio minting a subject to "fill in" a gap | Product boundary | No issuer runs in Vantio. Empty identity stays `UNVERIFIED` |
| Assertion copied into the SIEM | T8 export | Export receives the four reference fields. It does not receive the raw assertion |
| Compromised company runtime treated as the trust root | T0 | Test issuers only until T0 says the company identity path is fit to consume. This track does not point mocks at a live company tenant |
| Confused deputy across hosts | T1 | Identity is meaningful on an enrolled host. A stranger host is outside this connector |

## Failure modes

Enforce and Control fail closed. A missing field, a bad signature, an expired assertion, a wrong audience, or an unavailable trust bundle denies the enrolled action and records `UNVERIFIED`. Reason: an unnamed agent must not gain Enforce or Control.

Observe fails open for visibility and closed for the claim. The event is kept with `verification` `UNVERIFIED`. The product must not describe that event as an identified agent. Reason: dropping the observation would hide the workload, and labeling it verified would be a false claim.

A crash while reading the bundle is the same as an unavailable bundle: deny on Enforce and Control, record `UNVERIFIED` on Observe.

## Edge cases

- Two issuers for one process. The design keeps a single verified reference. A second issuer does not merge permissions.
- Clock skew. The later implementation picks a bounded skew and records it. This design does not pick a number of seconds as a verified limit. Exceeding the chosen bound is `UNVERIFIED`.
- SPIFFE ID with a path that points at a different namespace than the enrolled cgroup. Verification can succeed cryptographically and still be denied by an owner binding that does not match the enrollment record.
- Replayed assertion inside the expiry window. The design records the assertion hash and a `jti` when the source has one. A repeat on the same host is `UNVERIFIED` for Enforce. This is a design rule, not a built cache.
- Owner leaves the customer directory. The next verification fails closed for Enforce. Existing Observe events keep the owner subject they had. They are not rewritten.

## Memory footprint

The reference is four bounded strings plus a verification token. A later implementation caps each string at 256 bytes and caps the trust bundle the host loads. This design does not measure RSS and does not set a product memory claim. An oversize assertion is rejected and counts as `UNVERIFIED`.

## eBPF verifier limits

Phase 1 adds no eBPF program and does not change map sizes. A later phase that copies `agent_identity` and `owner` into a kernel event must keep the map value inside the verifier's accepted size. If the verifier rejects the program, the loader does not attach it and Enforce stays on the last loaded program or, if none is loaded, denies enrolled actions. The loader must not fall back to an identity-blind allow.

## Dependencies on T0–T5

| Track | Dependency |
| --- | --- |
| T0 | Company identity hygiene. Mocks stay on `.test` and `.invalid` issuers until T0 is accepted. CVE handling is T0's charter; this track does not describe that CVE |
| T1 | Enrollment is the host boundary. Identity on a stranger host is not an enrollment |
| T2 | A sandbox the customer verifies may be the place a mock assertion is evaluated. This track does not define that sandbox |
| T3 | Discovery names the process the identity is bound to. An unbound process stays `UNVERIFIED` |
| T4 | Tool-call events need the same four fields. T4 does not mint them |
| T5 | Egress drills must include an `UNVERIFIED` identity and expect a deny once Enforce is on |

## Rollback

Rollback is configuration. Remove the customer trust bundle and the host returns to identity-blind operation under the previous mode: Observe still records `UNVERIFIED`, and Enforce denies enrolled actions that require a verified identity. Rollback does not delete events already written. Rollback does not widen an allowlist. A failed rollback that leaves a half-loaded bundle is treated as an unavailable bundle.

## Proof plan

Phase 2, mocks only, not this commit:

- A fixture signed by the test key with issuer `https://login.microsoftonline.test/mock-tenant` verifies, and the event contains `agent_identity` and `owner`.
- The same fixture with a flipped signature, a wrong audience, or an expiry in the past is `UNVERIFIED`, and the enforce decision is deny.
- An Okta-shaped fixture and a SPIFFE-shaped fixture follow the same two outcomes.
- An event whose owner equals the agent subject is rejected.
- The raw token does not appear in the event bytes.
- No network call to a public identity host is made. The test asserts the destination list is empty.

## Risks

- A later engineer treats the historical SAML menu as a connector.
- A test key is copied into a lab image and mistaken for a customer root.
- Observe events with `UNVERIFIED` are shown in a console as identified agents.
- Kernel identity fields are added in a program the verifier rejects, and a fallback allows traffic.

## Approval gates

- Founder decision before any real customer issuer is configured.
- No live Entra, Okta, or SPIRE tenant in phase 2.
- No change to public docs that say how identity works.
- Draft PR only. The founder-approved label is not applied by this force.

## Council

Verdict: PENDING_INDEPENDENT_REVIEW

The producer does not write the verdict.
