# Expected outputs

Audience: INTERNAL_RESTRICTED

These invariants were read from `packages/vantio-cli/bin/vantio.js` and checked once on the design host on 2026-09-27. The check used `node packages/vantio-cli/bin/vantio.js`, an empty temporary `HOME`, and `VANTIO_TELEMETRY_DISABLED=1`. Working directory was the repository root. Provider packages did not resolve. `packages/vantio-cli/bin/vantio.js` is identical at the transcript commit `5064f32f1cdfcb840dfd100e2ce5c712d046550d` and at base commit `1df51d29a65a3913f1ef1f29fc00ead1335ef7a0`.

This transcript is a local design-host check. It is not customer validation, not a stranger-host proof, and not a registry check.

Fields that change every run: `trace_id`, `started_at`, `generated_at`, `ts`, and the prove-list date. The script must not require those bytes to match a previous room.

## B03 `--version`

Stdout is one line:

`0.3.24`

## B04 `status`

Stable lines when the demo home is empty, telemetry is disabled, the registry is not checked, and the seven provider packages do not resolve:

```
Vantio Optics | Free Observability for AI Agents
Free, local-first observability for supported AI-agent traffic. Prompts and completions are never stored.

Install version:             0.3.24
Registry latest:             not checked
Telemetry:                   disabled
Local data:                  0 bytes
First run since install:     yes
First run at:                none
Run logs:                    Not observed
Provider SDKs:
  openai  Unsupported
  @anthropic-ai/sdk  Unsupported
  @google/genai  Unsupported
  @google/generative-ai  Unsupported
  cohere-ai  Unsupported
  groq-sdk  Unsupported
  @mistralai/mistralai  Unsupported

Next: vantio demo
```

`Local data` stays `0 bytes` only before any run file exists. After `demo`, a later status would report a non-zero size and run logs `Successful`. The script runs status once, before demo.

## B07 `demo` human output

Stable substrings, in order:

- `Vantio Optics | Free Observability for AI Agents`
- `Prompts and completions are never stored.`
- `Demo — in-process stub. No network.`
- `method: POST /v1/chat/completions`
- `http_status: 200`
- `Optics status: Successful`
- `Application outcome: Successful`
- `duration_ms: 0`
- `trace_id: 0x` followed by 16 hexadecimal characters
- `Next: vantio prove --run=` and the same trace id

Absent from stdout and stderr: `BLOCKED`, `REDACTED`, `DRY_RUN`, `content`, a prompt body.

## `demo --json` reference

The spoken script does not run this. The shape, checked on the design host, is:

| Field | Value |
| --- | --- |
| `schema_status` | `unstable-pre-1.0` |
| `command` | `demo` |
| `network` | `none` |
| `method` | `POST` |
| `path` | `/v1/chat/completions` |
| `httpStatus` | `200` |
| `duration_ms` | `0` |
| `opticsStatus` | `SUCCESS` |
| `applicationStatus` | `SUCCESS` |
| `content` | `null` |
| `trace_id` | `0x` plus 16 hex characters, different from any other run |

## B08 run file

Path: `$DEMO_HOME/.vantio/runs/<trace_id>.json`.

Top-level keys:

`calls`, `cli_version`, `duration_ms`, `generated_at`, `plane`, `schema_version`, `started_at`, `summary`, `trace_id`, `vantio_run_log`

Call keys:

`action`, `bytes`, `hostname`, `method`, `path`, `provider`, `status`, `ts`

Stable values:

| Field | Value |
| --- | --- |
| `vantio_run_log` | `"1"` |
| `schema_version` | `2` |
| `plane` | `optics` |
| `cli_version` | `0.3.24` |
| `duration_ms` | `0` |
| `calls[0].hostname` | `optics-demo.invalid` |
| `calls[0].provider` | `openai` |
| `calls[0].method` | `POST` |
| `calls[0].path` | `/v1/chat/completions` |
| `calls[0].status` | `200` |
| `calls[0].bytes` | `0` |
| `calls[0].action` | `OBSERVED` |
| `summary.total_calls` | `1` |
| `summary.total_bytes` | `0` |
| `summary.hosts` | `["optics-demo.invalid"]` |

Absent keys on the object and on the call: `evidence_origin`, `producer`, `pid`, `content`, `prompt`, `completion`.

## B09 `prove --format=md`

Stable rows for that file:

| Field | Value |
| --- | --- |
| Host | `optics-demo.invalid` |
| Duration | `0 ms` |
| Process ID | em dash, because `pid` is absent |
| Total calls | `1` |
| Total bytes | em dash, because the total is 0 |
| Unique hosts | `1` |
| Optics status | `Successful` |
| Application outcome | `Successful` |
| HTTP | `200` |
| Bytes column | `0` |
| CLI version | `@vantio/cli v0.3.24` |

The Markdown includes the privacy sentence that prompts and completions are never stored. It does not include `SIMULATED_DEMO`, `evidence_origin`, or `simulation`.

`prove --json` on the same file sets `pid` to `null`, `duration_ms` to `0`, `opticsStatus` and `applicationStatus` to `SUCCESS`, and the single call hostname to `optics-demo.invalid`. `schema_status` is `unstable-pre-1.0`. The spoken script uses Markdown, not JSON.

`prove --list` shows the trace, call count `1`, total bytes as an em dash, and a wall-clock date. With one `demo`, the list count is 1. The design-host check ran `demo` twice and saw count 2. The room must see count 1.

## B15 discover, before the defect is planted

After one `demo`, `discover` scans 1 run log and prints host `optics-demo.invalid` with calls `1` and total bytes as an em dash, then a line of the form `1 host(s)  |  1 total call(s) observed locally`.

That sentence is expected. The operator's banner is what keeps it from being heard as customer traffic. The CLI does not filter the demo host out of this count.

## Network

`packages/vantio-cli/test/optics-cx.test.js` asserts that `demo` and default `status` perform no `connect`, `sendto`, `sendmsg`, `recvfrom`, `recvmsg`, `getaddrinfo`, or `socket` syscalls under `strace`. This design force did not re-run `strace`. The room still expects no registry line other than `not checked` and the demo sentence `No network.`
