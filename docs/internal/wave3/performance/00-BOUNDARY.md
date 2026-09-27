# Wave 3 Track 8 — performance qualification boundary

Audience: INTERNAL_RESTRICTED

Producer role: measurement producer. This agent does not sit the independent council, does not self-assign a council pass, and does not move a benchmark claim stage.

Producer identity: Cursor cloud agent `bc-82b879c7-90f4-57f8-a61f-140ee17ec643`, model Grok 4.7, reasoning `xhigh`, context `500k`, fast `false`.

Producer URL: https://cursor.com/agents/bc-82b879c7-90f4-57f8-a61f-140ee17ec643

Producer classification: `W3_PERFORMANCE_QUALIFICATION_READY_FOR_COUNCIL`

That classification means this qualification packet is ready for a separate council. It is not a council verdict.

## 1. Locked input

| Item | Value |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Starting commit | `0cd36cf1d01c4db83a0a6999db0a322441f61c98` |
| Commit subject | Merge Wave 3 PE integrated runtime onto main. Source-only. Host attachment false. |
| Branch | `cursor/wave3-performance-qualification` |
| Runtime | `internal/pe-integrated-runtime` |
| Benchmark scaffold | `docs/planning/benchmark-framework/PERFORMANCE-SCAFFOLD.json` |
| Selected plane | `NONE` |

## 2. What this force does

- Qualifies the merged in-process runtime against the Wave 2 metric ids.
- Records a measurement only when the run has an instrument, a workload, a start time, a sample count, and a result value taken from that run.
- Leaves every other scaffold metric `NOT_MEASURED`, with a reason and a null result.
- Writes the control-plane register at `docs/programs/production-readiness/wave3/PERFORMANCE-REGISTER.json` and the same bytes under this directory.

## 3. What this force keeps closed

| Action | State |
| --- | --- |
| Host attachment | `NOT_PERFORMED` |
| eBPF load | Closed |
| Enrollment | Closed |
| `W3-INFRA-REQ-1` provisioning | Closed |
| Money spent | Closed |
| Credential issuance | Closed |
| Publish or announcement | Closed |
| `@vantio/cli` `0.3.24` | Unmodified |
| `@vantio/agent-sdk` `0.2.4` | Unmodified |
| `vantio-agent-sdk` `3.1.0` | Unmodified |
| Wave 2 scaffold edit | Closed |
| Claim-stage movement | Closed |
| Production SLO | Closed |
| `PROVED_EXTERNAL` | Closed |
| `CLEAN_HOST_INTERNAL_PROOF` | Closed |

## 4. Where the numbers live

`PERFORMANCE-REGISTER.json` is the register. `02-ENVIRONMENT.md` is generated from the same run. `01-METHOD.md` states the workloads. A number that is not in the register was not measured.
