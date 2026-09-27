# Wave 3 Track 3 boundary

Audience: INTERNAL_RESTRICTED

Producer classification: `W3_PE_INTEGRATED_RUNTIME_READY_FOR_COUNCIL`

That classification means this source composition is ready for a separate council. It is not a council verdict, not host enforcement, and not external proof.

## Locked input

| Item | Value |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Starting commit | `0620f10ee52d3abcea18c1c988df02f687f51b36` |
| Branch | `cursor/wave3-pe-integrated-runtime` |
| Producer | `bc-0d910b08-2aee-5019-bce1-2872c3752880` |
| Module | `internal/pe-integrated-runtime` |

## What this track keeps closed

- Host attach, eBPF load, host enrollment, and mutation of a live Phantom Engine loader.
- Stranger-host execution and customer deploy.
- Reopening `@vantio/cli` `0.3.24`, `@vantio/agent-sdk` `0.2.4`, and Python `vantio-agent-sdk` `3.1.0`.
- Credential issue and announcements.
- `CLEAN_HOST_INTERNAL_PROOF` and `PROVED_EXTERNAL`.
- A self-assigned council pass. `council_verdict` stays null.

## Honesty registers

The same documents live here and under `docs/internal/wave3/pe-integration/`:

- `RUNTIME-REGISTER.json`
- `INTEGRATION-REGISTER.json`

Preferred execution labels are `CONTRACT_ONLY`, `EVALUATE_ONLY`, and `HOST_ATTACHMENT_FALSE`. `host_attachment` is false. `active_protection` is false. `kernel_executed` is false.

Mechanism notes are in `docs/internal/wave3/pe-integration/`.
