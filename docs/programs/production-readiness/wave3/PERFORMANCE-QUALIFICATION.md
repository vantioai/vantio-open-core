# Wave 3 Track 8 — performance qualification

Audience: INTERNAL_RESTRICTED

Producer classification: `W3_PERFORMANCE_QUALIFICATION_READY_FOR_COUNCIL`

That classification means this packet is ready for a separate council. It is not a council verdict, not a production SLO, and not a claim-stage pass.

## Control-plane register

`PERFORMANCE-REGISTER.json` in this directory is the control-plane performance register.

The same bytes are stored at `docs/internal/wave3/performance/PERFORMANCE-REGISTER.json`. Tests refuse a drift between the two copies.

The Wave 2 scaffold at `docs/planning/benchmark-framework/PERFORMANCE-SCAFFOLD.json` stays `NOT_MEASURED`. A measured row in this register does not fill that scaffold and does not move a comparator cell.

## Locked input

| Item | Value |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Starting commit | `0cd36cf1d01c4db83a0a6999db0a322441f61c98` |
| Branch | `cursor/wave3-performance-qualification` |
| Producer | `bc-82b879c7-90f4-57f8-a61f-140ee17ec643` |
| Runtime | `internal/pe-integrated-runtime` |
| Selected plane | `NONE` |
| Host attachment | `NOT_PERFORMED` |

## Closed

- Host attach, eBPF load, enroll, and loader edits.
- Provisioning or spending for `W3-INFRA-REQ-1`.
- Credential issuance, publish, and announcement.
- Reopening `@vantio/cli` `0.3.24`, `@vantio/agent-sdk` `0.2.4`, and Python `vantio-agent-sdk` `3.1.0`.
- `CLEAN_HOST_INTERNAL_PROOF`, `PROVED_EXTERNAL`, and a self-assigned council pass.

Method and environment notes: `docs/internal/wave3/performance/`.
