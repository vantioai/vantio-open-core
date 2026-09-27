# Integrated runtime boundary

Audience: INTERNAL_RESTRICTED

Producer role: source composition. This agent does not sit the independent council and does not self-assign a council pass.

Producer identity: Cursor cloud agent `bc-0d910b08-2aee-5019-bce1-2872c3752880`, model Grok 4.7, reasoning `xhigh`, context `500k`, fast `false`.

Producer URL: https://cursor.com/agents/bc-0d910b08-2aee-5019-bce1-2872c3752880

Producer classification: `W3_PE_INTEGRATED_RUNTIME_READY_FOR_COUNCIL`

That classification means the composition is ready for a separate council. It is not a council verdict, not a customer deploy, and not host enforcement.

## 1. Locked input

| Item | Value |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Starting commit | `0620f10ee52d3abcea18c1c988df02f687f51b36` |
| Commit subject | Merge Enterprise E1-E3 onto main. Source-only. Internal. Record layer only. |
| Branch | `cursor/wave3-pe-integrated-runtime` |
| Force | Wave 3 Track 3, Phantom Engine integrated runtime, source composition |

## 2. What this force implements

An internal module, `@vantio/pe-integrated-runtime` at `0.0.0-unstable-pre-1.0`, outside `pnpm-workspace.yaml`. `createRuntime` holds one ingress session, one progressive engine, an in-memory policy-version list, and an evidence list. `integrate` dispatches one supplied case into a merged Wave 2 evaluator and projects the result onto eight planes.

The evaluators called are the ones already in this tree:

- `packages/shared-health-runtime`
- `packages/pe-ingress-authority`
- `packages/pe-egress-authority`
- `packages/pe-host-authority` pure `evaluate` only
- `packages/pe-sequential-authority`
- `packages/pe-progressive-enforcement`

Host proof entry points `prove`, `collectHostFacts`, and `proveLiveChild` are not called. The composition does not spawn a process, open a socket, or write a host policy.

## 3. What this force keeps closed

- Host attach, eBPF load, enrollment, and live loader edits.
- Stranger-host execution, customer deploy, credentials, and announcements.
- CLI `0.3.24`, Node SDK `0.2.4`, and Python `3.1.0`.
- `CLEAN_HOST_INTERNAL_PROOF` and `PROVED_EXTERNAL`.
- A council pass. `04-PENDING-COUNCIL.md` stays `PENDING_INDEPENDENT_COUNCIL`.

## 4. Registers

`RUNTIME-REGISTER.json` and `INTEGRATION-REGISTER.json` in this directory are the honesty registers. The copies under `docs/programs/production-readiness/wave3/` are the same bytes. Tests refuse a drift between the two copies, and the module refuses to load a register whose honesty fields differ from the posture in `internal/pe-integrated-runtime/src/boundary.cjs`.
