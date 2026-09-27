# Product health and failure truth — boundary

Audience: INTERNAL_RESTRICTED

Producer role: source composition. This agent does not sit the independent council and does not self-assign a council pass.

Producer identity: Cursor cloud agent `bc-e3b48f10-95e0-51a9-be59-03f664ad2a5b`, model Grok 4.7, reasoning `xhigh`, context `500k`, fast `false`.

Producer URL: https://cursor.com/agents/bc-e3b48f10-95e0-51a9-be59-03f664ad2a5b

Producer classification: `W3_PRODUCT_HEALTH_FAILURE_TRUTH_READY_FOR_COUNCIL`

That classification means this reading is ready for a separate council. Council status stays `PENDING_INDEPENDENT_COUNCIL`. `council_verdict` stays null. The reading composes the merged Phantom Engine runtime and the Wave 2 shared health runtime.

## 1. Locked input

| Item | Value |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Starting commit | `0cd36cf1d01c4db83a0a6999db0a322441f61c98` |
| Commit subject | Merge Wave 3 PE integrated runtime onto main. Source-only. Host attachment false. |
| Branch | `cursor/wave3-product-health-failure-truth-2a5b` |
| Force | Wave 3 Track 6, product health and failure truth |
| PE runtime classification | `W3_PE_INTEGRATED_RUNTIME_READY_FOR_COUNCIL` |
| Shared health classification | `SHARED_HEALTH_RUNTIME_READY_FOR_COUNCIL` |
| Eligible plane | `NONE` |
| Infrastructure requirement | `W3-INFRA-REQ-1` |
| Execution ceiling | `HOST_ATTACHMENT_FALSE` |

## 2. What this force implements

`composeProductHealth` and `productHealth` on `internal/pe-integrated-runtime`. The reading uses the twelve shared health states from `packages/shared-health-runtime/contract.json`. `vocabulary_states_added` is empty.

Health states stay on `OBSERVATION`. `BLOCKED_HOST`, `ENFORCE`, and `PROMOTED_MATCH` stay on `DECISION` while `host_attachment` is false. `EVIDENCE_UNAVAILABLE` and `ENFORCEMENT_UNKNOWN` remain visible. Freshness remains `UNKNOWN`. Independent verification remains `NOT_INDEPENDENTLY_VERIFIED`.

The eligible-plane packet is `docs/programs/production-readiness/wave3/BLOCKED-INFRA.json`. This reading copies `plane_id` and requirement id from that packet. It does not raise the ceiling.

## 3. What this force keeps closed

- Host attach, eBPF load, enrollment, and live loader edits.
- Stranger-host execution, customer deploy, credentials, and announcements.
- CLI `0.3.24`, Node SDK `0.2.4`, and Python `3.1.0`.
- `CLEAN_HOST_INTERNAL_PROOF` and `PROVED_EXTERNAL`.
- A new health state, including `SUCCESS`.
- A council pass. `04-PENDING-COUNCIL.md` stays `PENDING_INDEPENDENT_COUNCIL`.

## 4. Registers

`RUNTIME-REGISTER.json` and `INTEGRATION-REGISTER.json` in this directory are the product-health honesty registers. The copies under `docs/programs/production-readiness/wave3/product-health/` are the same bytes.

The merged runtime registers under `docs/internal/wave3/pe-integration/` carry the same honesty fields. Their producer classification remains `W3_PE_INTEGRATED_RUNTIME_READY_FOR_COUNCIL`.
