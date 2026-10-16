# Gap program Phase 1 — T6 through T14

Audience: INTERNAL

Phase: design and boundary check only. No feature code. No product behavior change.

Producer: Cursor cloud agent `bc-1969b17c-bdef-51f9-9d70-09f9fd724d12`, model Grok 4.7.

Producer URL: https://cursor.com/agents/bc-1969b17c-bdef-51f9-9d70-09f9fd724d12

Written: 2026-10-16T15:48:08Z

Base: `vantioai/vantio-open-core` `69671e97fa359b685232ec7dd4e9fb4badc7be57`

Branch: `gap/p1-p2-design`

Public pricing language stays "Contact Vantio". This packet contains no prices. It does not change the public website, the README, or any Shipped label. The public pin stays `e0b19d55`. No tag, registry, or production signing root is created.

## What this packet is

Nine design documents, one per track, plus this index, a risk register, a design-packet checker, and an evidence file the checker writes. A reviewer from a different model family reviews the final head. Until that review is recorded in `COUNCIL-VERDICT.md`, the council state is `PENDING_INDEPENDENT_REVIEW`. The producer does not sit the council.

Phantom Engine covers supported AI workloads on enrolled Linux machines only. Optics observes. Gate is the application-path dry-run inside that host product, and a dry-run is not host activation. Enterprise is governance on top of that protection. Permissions move in order: Observe, then Enforce, then Control. An AI capability does not grant a permission.

## Tracks

| Track | Document | Track label |
| --- | --- | --- |
| T6 Identity interop | `T6-identity-interop.md` | Roadmap |
| T7 Credential keep-out | `T7-credential-keep-out.md` | Roadmap |
| T8 OCSF, OTLP, SIEM, WORM validation | `T8-ocsf-otlp-siem.md` | Roadmap |
| T9 OWASP Agentic Top 10 matrix | `T9-owasp-agentic-matrix.md` | Roadmap |
| T10 Live human approval | `T10-live-human-approval.md` | Roadmap |
| T11 Coding-agent and supply-chain defense | `T11-coding-agent-supply-chain.md` | Roadmap |
| T12 Policy preview | `T12-policy-preview.md` | Roadmap |
| T13 FedRAMP and FIPS gap assessment | `T13-fedramp-fips-gap.md` | Roadmap |
| T14 EU AI Act evidence pack outline | `T14-eu-ai-act-evidence-outline.md` | Roadmap |

T9 cells use Verified, Lab-only, Roadmap, or Not addressed. This packet marks no cell Verified.

## Sibling tracks T0–T5

These forces were started in parallel on 2026-10-16 and are not in this commit. Dependencies below name the charter, not a merged artifact.

| Track | Charter seen on this run | Agent |
| --- | --- | --- |
| T0 | Own-stack hygiene, OpenClaw CVE-2026-25253 | `bc-8495549c-cbc0-56be-a0c5-f33fd7ca7161` |
| T1 | Stranger Host proof package | `bc-b514829b-b7fc-5ade-adbb-24da4a7dcbd0` |
| T2 | OpenShell strategy and verify-the-sandbox | `bc-9a8c50e6-62db-5d3b-9b1d-e2da113da297` |
| T3 | Optics agent discovery and inventory | `bc-5b9d4246-48a2-5a53-bb5e-8776f4451d9f` |
| T4 | MCP and tool-call awareness | `bc-d56585c7-15ec-5b72-a6cc-518721d23f80` |
| T5 | Side-channel and egress hardening drills | `bc-a5cc53ad-bb01-5449-84ad-87ab5e85c8ba` |

## Inherited observability packet

T8 merges with the zero-cost local OTLP and SIEM drill already recorded on `cursor/optics-observability-5bed` at `ef3a33a` (2026-10-10), draft PR 191. That branch is not merged here. `product_otlp_export_authorized` stays false. Public docs on this base still say there is no OTLP exporter.

A search of this repository, `vantio-phantom-engine` `docs/`, `vantio-enterprise` `docs/`, and `vantio-deploy` `docs/` on 2026-10-16 did not find a separate file titled as an 9 October 2026 test plan. The drill that matches the request is the 10 October 2026 packet. It used local receivers and mocks, and it recorded Zach's scoped acceptance the same day. Splunk HEC and Datadog were mocks. The Splunk product, the Datadog product, Microsoft Sentinel, OCSF, and WORM validation were not part of that packet.

## Checker

`node scripts/gap-program/check-p1-design.mjs` checks the required sections, the labels, and the claim fence, then writes `evidence/gap-program/T6-T14-P1.json`.
