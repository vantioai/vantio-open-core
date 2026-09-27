# Telemetry

Optics can send one optional usage ping to Vantio. The ping is separate from the local run log. The local run log stays on the machine. The ping is product telemetry, not customer evidence.

Two published packages implement the gate differently. Use the row for the package you installed.

| Package | When a ping is sent |
| --- | --- |
| `@vantio/cli@0.3.24` | Only when `VANTIO_TELEMETRY=1`. `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1` keeps it off, including when opt-in is set. |
| `vantio-agent-sdk==3.0.14` (PyPI) | `shield()` sends unless `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1`. The published module does not consult `VANTIO_TELEMETRY`. |
| Python 3.1.0 source in this repository | Unpublished. Same opt-in rule as the CLI: off unless `VANTIO_TELEMETRY=1`, with the same two overrides. |

`vantio status` prints the CLI posture for the current environment: `off`, `opt-in`, or `disabled`. It does not show whether a previous ping succeeded.

## CLI 0.3.24

Default is off. Nothing is sent for `vantio --help`, `vantio --version`, `vantio status`, `vantio demo`, or a run that records no call.

```bash
# Example status: illustrative
VANTIO_TELEMETRY=1 vantio run node agent.js
```

```bash
# Example status: illustrative
VANTIO_TELEMETRY_DISABLED=1 vantio run node agent.js
DO_NOT_TRACK=1 vantio run node agent.js
```

The ping fires once, after the first recorded in-scope call, because a request started inside the process exit hook does not flush. Later calls in that process do not send again.

Destination: `POST {VANTIO_INGEST_URL or https://vantio.ai}/api/v1/telemetry`.

Timeout: 3 seconds. Errors are discarded. The agent is not failed when the ping fails. The CLI captures `fetch` before it patches `globalThis.fetch`, so the ping is not recorded as an agent call.

## Published Python 3.0.14

This is the package `pip install vantio-agent-sdk` returns today.

`shield()` (decorator or `async with`) calls `send_run_telemetry_once` on entry. That function sends when `is_telemetry_disabled()` is false. In 3.0.14 that function is false unless `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1`.

To keep the published SDK from sending:

```bash
# Example status: illustrative
VANTIO_TELEMETRY_DISABLED=1 python agent.py
DO_NOT_TRACK=1 python agent.py
```

`vantio run python` uses `install_process_wrap`, which installs observation and does not call `send_run_telemetry_once`. A process started only that way does not send the Python usage ping. Entering `shield()` does.

The automatic `shield()` ping is one `run` event per process. It is sent before HTTP observations are recorded, so `callCount` is 0 and `hosts` is empty.

## Unpublished Python 3.1.0 source

The same `shield()` call site exists. The gate matches the CLI: the ping stays off unless `VANTIO_TELEMETRY=1`. `VANTIO_TELEMETRY_DISABLED=1` and `DO_NOT_TRACK=1` still force it off. This behavior is in the git tree. It is not what PyPI served on 2026-09-27.

Git also contains an unpublished 3.0.15 change that introduces this opt-in gate. PyPI latest on that check was 3.0.14. Do not assume 3.0.15 is installed.

## Payload

The sender builds a fixed allowlist. Fields outside the list are not added.

| Field | Meaning |
| --- | --- |
| `anonymousId` | Random id. Read from `~/.vantio/telemetry-id` when that file exists, otherwise created. Mode `0600` when the create succeeds. A filesystem failure uses an in-memory id for that process. The file is not under `runs/`. The JSON name `anonymousId` is the wire name. |
| `runtime` | `node` from the CLI, `python` from the SDK. |
| `runtimeVersion` | Node version string, or `platform.python_version()`. |
| `os` | `process.platform` or `sys.platform`. |
| `event` | `run` for this automatic ping. Other values are sent as `summary` if a caller passes them. |
| `hosts` | Customer LLM endpoint hostnames the event includes, at most 50 strings. CLI 0.3.24 sends the hostname of the first recorded in-scope call, as a one-element list. The Python `shield()` ping sends an empty list because it runs before observations. These are the API hostnames the agent contacted, such as `api.openai.com`. They are not prompts. |
| `callCount` | CLI: number of completed in-scope call records at send time. The first completed call reports 1. Python `shield()` ping: 0. |

Optional fields, included only when the caller sets them: `sdkVersion`, `cliVersion`, `redactedCount`, `blockedCount`, `framework`. The CLI automatic ping sets `cliVersion`. The Python automatic ping sets `sdkVersion` when import succeeds.

The request has `Content-Type: application/json`. It has no API key and no authorization header.

The ping does not include prompts, completions, request or response bodies, API keys, environment dumps, source code, local paths, or the run-log file.

## What telemetry is not

A successful ping does not prove a run log was written. A missing ping does not prove a call was blocked. `vantio status` reports posture only.

Setting `VANTIO_INGEST_URL` changes the ping's base URL when a ping is sent. On the CLI, a `VANTIO_INGEST_URL` that points at the public host does not turn on policy loading. Policy loading is outside this manual. See [PRIVACY-AND-SECURITY.md](PRIVACY-AND-SECURITY.md).
