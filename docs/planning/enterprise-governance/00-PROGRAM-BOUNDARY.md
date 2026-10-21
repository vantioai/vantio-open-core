# Enterprise governance E1–E3 — planning boundary

Audience: INTERNAL_RESTRICTED

Producer role: planning producer only. This agent designs the packet. It does not sit the independent council, does not self-assign a council pass, and does not authorize an implementation.

Producer identity: Cursor cloud agent `bc-53037043-9d63-5b25-9945-484d22d0eaa7`, model Grok 4.7, reasoning `xhigh`, context `500k`, fast `false`.

Producer URL: https://cursor.com/agents/bc-53037043-9d63-5b25-9945-484d22d0eaa7

Producer classification: `ENTERPRISE_GOVERNANCE_E1_E3_PLAN_READY_FOR_COUNCIL`

That classification means this packet is ready for a separate council. It is not a council verdict, not an implementation authorization, and not evidence that any ownership, delegation, or approval object is built, shipped, or proved.

## 1. Locked input

| Item | Value verified at planning time |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Starting commit | `5064f32f1cdfcb840dfd100e2ce5c712d046550d` |
| Commit subject | Merge pull request #65 from `vantioai/docs/documentation-release-governance-v1` |
| `origin/main` | Same commit. Fetched before this branch was written. |
| Planning branch | `cursor/enterprise-governance-e1-e3-eaa7` |
| Writable path | `docs/planning/enterprise-governance/` only |
| Force | WS8 E1–E3, enterprise ownership, delegated authority, and approval classes |
| Force success token | `ENTERPRISE_GOVERNANCE_E1_E3_PLAN_READY_FOR_COUNCIL` |

This force is docs and planning only. The success token is the producer handoff. `06-INDEPENDENT-COUNCIL.md` stays `PENDING_INDEPENDENT_COUNCIL`.

## 2. Sources read

Phantom Engine sources were read from GitHub at commit `631e435315cd780d83d3259e111893c1d0569bc3` (merge of phantom-engine PR #8, 2026-09-20). This planning tree does not vendor those files. Blob hashes are the bytes read:

| Repo | Path | Blob SHA-256 recorded by Git | Role in this plan |
| --- | --- | --- | --- |
| `vantioai/vantio-phantom-engine` | `docs/product-spec.md` | `f12c0caf7413dc061d705c8fc78ce7d2bcdc525d` | Commercial model and verification labels, dated 2026-09-20 |
| `vantioai/vantio-phantom-engine` | `docs/PRODUCT_LINEUP.md` | `db10eff96899703a6711aefec4281e5517b8784a` | Jobs: Observe, Enforce + Control, Govern |
| `vantioai/vantio-phantom-engine` | `docs/enterprise/REFERENCE_MONITOR.md` | `57b0d613267a9ea57b2f94897b5c839727bc5e1f` | Authority-boundary doctrine, dated 2026-08-26, status `SCOPED` |
| `vantioai/vantio-phantom-engine` | `docs/P0_CUSTOMER_PROTECTION_STATE.md` | `04916238c295df03e549d02d5d3419e2ff5bd574` | Customer-verifiable protection state; quarantine executor unwired |
| `vantioai/vantio-phantom-engine` | `docs/enterprise/FUTURE_AUTONOMY_NORTH_STAR.md` | `797391414c4f4662d398765895010fb1120a5f53` | Scoped sibling note. Trust-assumption cell: Vantio consumes identity and does not become the identity provider |

`docs/specs/DUAL_CONTROL.md` is cited by the reference-monitor doctrine at a path that is not inside the phantom-engine tree returned for that commit. This plan does not describe the contents of that missing file. Dual-control statements below are only the statements the reference-monitor file itself makes.

Open-core sources are this starting commit:

| Path | Use |
| --- | --- |
| `docs/governance/canonical/product-boundary.md` | Current public boundary: Optics observes; Phantom Engine is Enforce + Control on enrolled Linux; Enterprise is governance on top, talk to sales |
| `docs/PRODUCT_LINEUP.md` | Same three products. Enterprise job is governance on that protection. Certifications are not held. Durable ledger / dual-control is marked partial on Phantom Engine and checked on Enterprise |
| `docs/observe-only.md` | Optics fence. Enforcement stays Phantom Engine |
| `docs/governance/VERSION-METADATA.json` | Frozen package versions this plan leaves untouched |

A capability matrix cell is a lineup statement. It is not an implementation record for E1, E2, or E3.

## 3. Product facts this plan uses

| Fact | Source | Planning consequence |
| --- | --- | --- |
| Three products: Optics (free Observe), Phantom Engine ($799 per enrolled node per month, Observe + Enforce + Control), Enterprise (governance add-on, talk to sales) | Phantom Engine `docs/product-spec.md` canonical model, 2026-09-20; open-core product boundary | No fourth product. Gate is the internal application-path enforcement component inside Phantom Engine, not a separate invoice |
| Enterprise status in the product-spec cross-product table | `Internal dogfood` | This plan does not reclassify Enterprise as shipped |
| Phantom Engine verification label | Live-verified on a privileged Linux host and a local `kind` cluster. Managed-cloud Kubernetes (GKE, EKS, AKS) and a live Spanner write are `TARGET_DESIGN` | This plan does not call `kind` a production-cluster proof and does not select Spanner as the evidence store |
| Authority boundary | Reference-monitor doctrine: Control means enrolled Linux the customer owns. The doctrine file is `SCOPED`. It is not Present, not Shipped, and not a public claim. Certifications held: none | Enterprise governs inside that boundary. It does not replace it |
| Three authority domains | Workload, Security, and Recovery. Classified Partial in the doctrine. Split control (propose, approve, Phantom Engine verifies both, customer-owned channel activates) is Roadmap | E1 owns the domains. E2 grants inside them. E3 approves proposals. Activation stays on the customer host |
| Invariant 10 | "No customer loses the independent ability to freeze, verify, recover, export, or leave." Status Partial. Named residual: independent freeze is not a customer-owned one-shot. Weakening by making freeze or leave require Vantio is a force-approval event in that doctrine | E1–E3 keep freeze, revoke, and recover exercisable by a customer-controlled party while Vantio is absent |
| Child and cross-agent delegation | Invariant 2 is Partial. Invariant 9 is Roadmap. No first-class child-agent delegation object | E2 defines the grant. It does not claim the object exists in Phantom Engine |
| Recovery ceiling | Customer-pack modes named in the doctrine: `last-known`, `observe-only`, `stay-quarantined`. Invariant 8 is Partial. Prove row RM-08 is skip, residual `recovery_restoring_authority_ceiling_not_present` | E3 adopts those three modes and the ceiling. It adds no wider restore mode |
| Dual control, as stated in the doctrine file | Kinds exist, including `phantom_deny_breakglass_off`, whose live executor is unwired. Two-of-two is described as proved only for a non-destructive test kind. A root shell is outside that control | E3 does not treat those hooks as shipped approval classes and does not wire the executor |
| Company host | The doctrine says company-operated hosts still need the named company operator to disable protection | That residual stays out of the customer model. See decision EG-D8 |
| Open-core packages | `@vantio/cli` `0.3.24`, `@vantio/agent-sdk` `0.2.4`, `vantio-agent-sdk` `3.1.0`, `@vantio/optics-mcp` `0.1.2`, `@vantio/gate-mcp` `0.1.0` | Frozen. This plan does not patch them |
| Free Optics | No account and no API key | E1 does not attach an account requirement to local Optics observation |

The reference-monitor file and its sibling future-autonomy note are different scoped sentences. This plan uses the authority-boundary fences and invariant 10. It does not promote either sentence to a current product label.

The product-spec summary table says Phantom Engine blocks traffic and uses the word "unbypassable" at the kernel. The same spec's scope boundary requires Linux, kernel 5.8 or newer, BTF, and root or `CAP_BPF`, and it says the product is not a SaaS product. The reference-monitor doctrine and the open-core lineup both keep privileged disable of the loader as a named residual, limited to enrolled hosts. This plan follows the residual. It does not adopt "unbypassable" as a governance guarantee.

## 4. What this force does

- Defines E1 ownership: who holds customer authority, host intent, policy intent, evidence, and governance records.
- Defines E2 delegated authority: grants that stay inside the delegator's envelope and expire.
- Defines E3 approval classes: which customer parties must agree before a proposal may be offered to Phantom Engine.
- Records the subordination rule and the customer-sufficiency rule, with tests specified and marked unsatisfied.
- Leaves Founder decisions EG-D1 through EG-D10 unresolved, each with a safe default.
- Leaves `06-INDEPENDENT-COUNCIL.md` pending.
- Marks `07-FUTURE-FORCE.md` `NOT AUTHORIZED`.

## 5. What this force keeps closed

- Product code, package versions, workflows, tags, GitHub releases, npm, and PyPI.
- Phantom Engine source, eBPF programs, loaders, enroll flags, quarantine executors, and dual-control executors.
- Any customer control plane, billing change, or website copy.
- A stable schema. Every planning object in this packet is `schema_status` `unstable-pre-1.0`.
- Selection of an identity provider, a hardware root, a WORM product, a notarization scheme, or a proof system.
- Certifications. None are held.
- Public claims that a reference monitor, independent verifier, or stranger-host standard has passed.
- An implementation pull request in `vantio-phantom-engine` or in this repository's packages.

`07-FUTURE-FORCE.md` is a draft for a later Founder. Running it is outside this force.

## 6. Subordination

Enterprise is the governance add-on on Phantom Engine protection. The authority boundary stays Phantom Engine on enrolled Linux the customer owns.

An Enterprise record can name an owner, a grant, and an approval. Phantom Engine on the customer host is the component that attaches, refuses, or continues last-known enforcement. An approval marked in a vendor console is a proposal until the host reports a matching active version.

Detail and requirement ids: `04-SUBORDINATION-AND-CUSTOMER-SUFFICIENCY.md`.

## 7. Customer sufficiency

Freeze, revoke, and recover of customer authority each have a customer-controlled party that can complete the action while Vantio contributes no credential, no approval, and no hosted service.

Vantio may be an optional witness where decision EG-D3's default allows it. Vantio is not a sufficient party for those three actions. A design in which Vantio is the only party that can freeze, revoke, or recover customer authority is approval class `REJECTED`.

Detail: `04-SUBORDINATION-AND-CUSTOMER-SUFFICIENCY.md`.

## 8. Status vocabulary

| Token | Meaning in this packet |
| --- | --- |
| `PLANNED` | Specified here. No object is implemented by this force |
| `UNSATISFIED` | A test or property this plan requires, and that current sources do not show as passed |
| `UNSET` | Evidence tier and customer validation. This packet assigns neither |
| `NOT_SET` | A numeric bound a Founder has not chosen |
| `PENDING_INDEPENDENT_COUNCIL` | Council file state. The producer does not fill verdicts |
| `NOT AUTHORIZED` | The future-force template |

Doctrine labels quoted from Phantom Engine (`Present`, `Partial`, `Roadmap`, `SCOPED`, `TARGET_DESIGN`) keep that file's meaning. This plan does not promote them.

## 9. Hard-stop attestation

| Stop | Attestation |
| --- | --- |
| Writable path | Markdown and JSON under `docs/planning/enterprise-governance/` only |
| Product code | None |
| Package versions | Unchanged |
| Phantom Engine repo | Read. Not modified |
| Executors | None wired |
| Schema implementation | None. `schema_status` is `unstable-pre-1.0` |
| Evidence tier | `UNSET` on every requirement |
| Customer validation | `UNSET` on every requirement |
| Certifications | None claimed |
| Council | Pending. This producer does not pass it |
| Future force | `NOT AUTHORIZED` |
