# Node guide

This page is `@vantio/cli@0.3.24`. The CLI in this source tree is that frozen version.

## Attach

```bash
# Example status: illustrative
vantio run node agent.js
vantio run --summary tsx agent.ts
vantio run --json node agent.js
```

`vantio run` splits its own flags from the child program at the first argument that does not start with `-`. Flags after the program name belong to the child (`vantio run node --experimental-strip-types agent.ts`).

Node runtimes are `node`, `npx`, `tsx`, and `ts-node` (and the `.exe` / `.cmd` forms the CLI recognizes). For those names the CLI prepends `--require <interceptor.cjs>` onto `NODE_OPTIONS`. Other programs are spawned with no Node interceptor.

The CLI sets `VANTIO_TRACE_ID` to the parent's value, or to `0x` plus 16 hex characters. One id covers that `vantio run` process. There is no per-call span id.

`--summary` sets `VANTIO_SUMMARY=1` for the child and prints a summary on exit. `--json` sets `VANTIO_JSON=1` and, when the child exits, prints one JSON object on the CLI's stdout with `schema_status` `unstable-pre-1.0`. A signal sets `opticsStatus` to `OPTICS_ERROR` on that stdout object. That field is not written inside the run file.

`--audit` sets `VANTIO_AUDIT_MODE=1` on the child. It is not a column in the local proof.

The child inherits the parent environment. The CLI does not inject a key or ingest URL from `~/.vantio/config.json`.

## What the interceptor patches

Inside the wrapped Node process the interceptor patches:

- `globalThis.fetch`
- `undici` `fetch`, `request`, `stream`, `pipeline`, `dispatch`, `connect`, `upgrade`, and `Client` / `Pool` / `Agent` request paths
- Node `http` / `https` `request`, `get`, and `ClientRequest`
- Node `http2.connect` and session `request`
- `net.Socket.connect` and `tls.connect` to in-scope hosts
- `globalThis.WebSocket` and undici `WebSocket` for host scope and outbound frame size (payloads are not parsed)
- bytes after `undici.upgrade` / CONNECT
- `child_process` spawn/exec of `curl`, `wget`, `httpie`, and `aria2c`, including `env` / `timeout` / `nice` prefixes, `curl -K` `url=`, `curl -F` size from stat, `wget -i` URL lists, and stdin size when stdin is a file

Browsers stay outside this wrap. A library that opens a socket from a native addon, or a child that drops `NODE_OPTIONS`, is outside the wrap. Those calls are not observed. Optics does not block them.

In-scope hosts: [SUPPORTED-PATHS.md](SUPPORTED-PATHS.md).

## Local record

On process exit the interceptor writes one JSON file. It writes that file even when `calls` is empty, so a wrapped Node process that made no in-scope call still leaves a log when the exit hook runs. `SIGKILL` skips the hook. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

Free Optics (`free_mode` true, which is the default when no control-plane API key is loaded) stores `action` `OBSERVED` for an in-scope call. The response body is not stored. Response size uses `Content-Length` when that header is present.

The Node file's envelope fields are listed in [RECORD-REFERENCE.md](RECORD-REFERENCE.md). The file sets `vantio_run_log` to `"1"` and `schema_version` to `2`. It does not set `schema_status`.

Provider labels on Node are a substring guess (`guessProvider`). A hostname that merely contains `openai` can be labeled `openai`. Python 3.0.14 does not use that guess. See [SUPPORTED-PATHS.md](SUPPORTED-PATHS.md).

## Commands that read Node logs

These commands read `~/.vantio/runs`. They also read Python logs in that directory. They do not honor `VANTIO_HOME`.

```bash
# Example status: illustrative
vantio discover --local --since=7d
vantio discover --host=api.openai.com
vantio prove --list
vantio prove --run=0x1a2b3c4d --format=md
vantio search --host=api.anthropic.com --since=7d
vantio tail --run=0x1a2b3c4d -n 20
vantio tail --all
vantio diff 0xabc 0xdef
```

`vantio tail --follow` watches the file and prints when `calls.length` grows. The writer replaces the whole file at exit, so follow stays quiet during the run and shows calls after exit. `--json` and `--follow` together are a usage error. `--all` and `--lines` together are a usage error. `-n 0` prints zero calls.

`vantio search` scans every `.json` file in the reader directory. The query is a substring, not a regular expression. Filters: `--host`, `--provider`, `--action`, `--run`, `--since=24h|7d|30d`. Default is all time, unlike `discover`, whose default is 24 hours.

`vantio diff` compares two runs: call-count delta, byte delta, hosts added, hosts removed, and hosts whose call or byte counts changed. It prefers `summary.by_host` when present. Python 3.0.14 logs omit `by_host`, so diff sums call rows.

Exit status for these commands: 0 when the command finished, including an empty result. 1 for bad arguments, or for a file that exists but cannot be read or parsed.

## Real-time lines

Intercepted calls can print to the terminal while the process runs. The run file is still the exit write. A crash before exit can leave the terminal line without a finished file.

## Node SDK

`@vantio/agent-sdk@0.2.4` does not write the run log. `vantio run` does. Do not expect `shield()` from the Node SDK, used alone, to create `~/.vantio/runs`.
