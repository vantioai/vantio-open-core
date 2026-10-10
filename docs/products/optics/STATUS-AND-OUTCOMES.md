# Status and outcomes

CLI 0.3.24 prints two different ideas. Keep the tokens.

| Token | Human label in CLI 0.3.24 | Use |
| --- | --- | --- |
| `OBSERVED` | Observed | Stored `action` on a free Optics call. The call was recorded. |
| `SUCCESS` | Successful | Optics status when a call record exists, or a single application outcome for HTTP 200–399. |
| `NOT_OBSERVED` | Not observed | No call records in the rollup, or the CLI `--json` run object has not read a provider outcome. |
| `UNSUPPORTED` | Unsupported | `vantio status` when a provider package does not resolve from the current directory. |
| `UNAVAILABLE` | Unavailable | Application outcome when no usable HTTP status was stored. Also registry lookup failure. |
| `APPLICATION_ERROR` | Application error | Application outcome for HTTP 400–599. |
| `OPTICS_ERROR` | Optics error | CLI `--json` when the child dies on a signal. Also `vantio status` when local data or a run file cannot be read. |
| `PARTIAL` | Partial | Application rollup when the calls in one run do not share one application status. |
| `UNKNOWN` | (no separate CLI human label) | Keep this token if you already have it from an older file or a reviewer note. Do not relabel it as success or as a block. |

JSON values are the tokens. Human words are labels. Published CLI 0.3.24 human labels stay "Application error", "Successful", "Unavailable", "Partial", or "Not observed". Source candidate CLI 0.3.25 and Python source use the specific observed sentence ("Provider authentication failed", and similar) while the machine token for HTTP 400–599 stays `APPLICATION_ERROR`.

## How the CLI derives display fields

For each stored call, `displayCall` sets:

- `opticsStatus` = `SUCCESS` whenever the call object is being displayed. Optics status means "a record exists", not "the provider returned 200".
- `applicationStatus` from the HTTP status only. The stored `ok` boolean is ignored.
  - 200–399 → `SUCCESS`
  - 400–599 → `APPLICATION_ERROR`
  - missing or non-integer → `UNAVAILABLE`

An empty call list rolls up to `NOT_OBSERVED` for both.

If the calls in one run produce more than one application status, the rollup `applicationStatus` is `PARTIAL`. Optics status on that rollup stays `SUCCESS`.

Published Python 3.0.14 can store `ok` true on a 4xx or 5xx response when the client returns the response object (`requests`, `httpx`, `aiohttp` in the 3.0.14 source). urllib is different: a local check of the 3.0.14 wheel recorded HTTP 500 from `urlopen` with `ok` false and `error` `network_error`. Trust the HTTP status and the derived application token. The `error` string on that urllib file says `network_error` even though `status` is 500. Unpublished 3.1.0 source stores `ok` false for 400–599 and does not label that HTTP status as `network_error`. The CLI rule is the same either way: it does not read `ok`.

## Where the tokens show up

| Surface | What you get |
| --- | --- |
| Run file `action` | `OBSERVED` for free Optics. The file is not rewritten into the display tokens. |
| `vantio tail`, `search`, `prove`, `demo` | Optics status and application outcome columns or JSON fields. |
| `vantio run --json` | CLI stdout object: `opticsStatus` is `SUCCESS`, or `OPTICS_ERROR` on a signal. `applicationStatus` on that object is `NOT_OBSERVED` because the CLI parent does not copy provider outcomes into it. Read the run file for call outcomes. |
| `vantio status` | Install, telemetry posture, data directory, run scan, and provider-SDK resolve. `--json` includes `schema_status` `unstable-pre-1.0` and the vocabulary list. |
| `vantio demo` | One stub HTTP 200. Optics status Successful. Application outcome Successful. Duration 0. No network. |

## `vantio status` lines

| Line | Meaning |
| --- | --- |
| Install version | `vantio --version` from the installed package. |
| Registry latest | Filled only with `--check-registry`. Otherwise "not checked". A failed lookup is `UNAVAILABLE`. |
| Telemetry | `off`, `opt-in`, or `disabled` for the CLI environment. See [TELEMETRY.md](TELEMETRY.md). This line does not describe Python 3.0.14 `shield()` behavior. |
| Local data | Byte size of `~/.vantio`, skipping symbolic links. Unreadable data is `OPTICS_ERROR`. A missing directory is `NOT_OBSERVED`. |
| Run logs | `SUCCESS` when at least one valid run file exists and none scanned as corrupt. `OPTICS_ERROR` if any file is unreadable or invalid JSON. `NOT_OBSERVED` when the directory is missing or has no valid runs. |
| Provider SDKs | `SUCCESS` if that package resolves from the current directory, otherwise `UNSUPPORTED`. |

## What the tokens exclude

`SUCCESS` is not an allow decision. `APPLICATION_ERROR` is not an Optics block. `NOT_OBSERVED` is not proof the call was prevented. `OPTICS_ERROR` on a signal means the CLI parent saw a signal; it does not repair a missing run file.

There is no stored lifecycle of `COMPLETE`, `INTERRUPTED`, `ABANDONED`, or `RECOVERED`.

Enforcement actions (`BLOCKED_HOST`, `REDACTED`, and similar) can appear in files produced when a control-plane key was loaded. That path is not free Optics. This manual does not document how to turn it on. If you see those actions, you are outside the free observe description, and you should treat them as control-plane records rather than as Optics protection claims.
