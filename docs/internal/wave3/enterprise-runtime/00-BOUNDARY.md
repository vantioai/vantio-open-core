# Enterprise runtime integration boundary

Audience: INTERNAL_RESTRICTED

Producer role: source composition. This agent does not sit the independent council and does not self-assign a council pass.

Producer identity: Cursor cloud agent `bc-adac3d0c-3395-5aeb-8a09-fad025b1aa95`, model Grok 4.7, reasoning `xhigh`, context `500k`, fast `false`.

Producer URL: https://cursor.com/agents/bc-adac3d0c-3395-5aeb-8a09-fad025b1aa95

Producer classification: `W3_ENTERPRISE_RUNTIME_INTEGRATION_READY_FOR_COUNCIL`

That classification means the composition is ready for a separate council. It is not a council verdict, not live customer authority, and not host enforcement.

Wave 2 close, kept on this force: `ENTERPRISE_E1_E3_INTERNAL_MERGED_RECORD_LAYER_ONLY_NO_LIVE_CUSTOMER_AUTHORITY`

## 1. Locked input

| Item | Value |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Starting commit | `0cd36cf1d01c4db83a0a6999db0a322441f61c98` |
| Commit subject | Merge Wave 3 PE integrated runtime onto main. Source-only. Host attachment false. |
| Branch | `cursor/wave3-enterprise-runtime-integration-aa95` |
| Force | Wave 3 Track 9, Enterprise runtime integration, internal composition |

## 2. What this force implements

An internal module, `@vantio/enterprise-runtime-integration` at `0.0.0-unstable-pre-1.0`, outside `pnpm-workspace.yaml`. `createComposition` holds one customer-held Enterprise store and one Phantom Engine integrated runtime. `integrate` dispatches one Enterprise record operation or one PE `integrate` call. `compose` runs one record operation and, when that record call succeeds, one PE call, then joins the planes.

The record calls are the ones already in `internal/enterprise-governance`. The runtime calls are the ones already in `internal/pe-integrated-runtime`. This force does not edit either module.

## 3. Planes

`OBSERVATION`, `DECISION`, `APPLICATION_ENFORCEMENT`, and `HOST_ENFORCEMENT` stay distinct. An `APPROVED` record is a decision. Application enforcement stays `NOT_APPLIED`. Host enforcement stays `NOT_APPLIED` or, when a cited PE row is a gap, `GAP`. A joint call that has both a record outcome and a PE decision sets the decision status to `SEPARATED`.

`host_attachment`, `kernel_executed`, and `active_protection` stay false. `live_customer_authority` stays false. A request that asks to promote a record, attach a host, publish, announce, issue credentials, or reopen a frozen version returns `PROMOTION_REFUSED` before either child runs.

## 4. What this force keeps closed

- Live customer authority and customer deploy.
- Host attach, enroll, eBPF load, and kernel execution.
- Publishing, announcing, and credential issuance.
- Reopening CLI `0.3.24`, Node SDK `0.2.4`, or Python `3.1.0`.
- EG-E2-8, EG-E3-7, EG-E3-8, and EG-SUB-6 host residuals. The cited states stay `RECORD_LAYER_ONLY_HOST_UNSATISFIED` or `HOST_UNSATISFIED`.
- A council pass. `04-PENDING-COUNCIL.md` stays `PENDING_INDEPENDENT_COUNCIL`.

## 5. Registers

`RUNTIME-REGISTER.json`, `INTEGRATION-REGISTER.json`, and `STATUS.json` in this directory are the honesty registers. The copies under `docs/programs/production-readiness/wave3/` are the same bytes. The module refuses to load when those bytes differ or when an honesty field differs from `internal/enterprise-runtime-integration/src/boundary.cjs`.
