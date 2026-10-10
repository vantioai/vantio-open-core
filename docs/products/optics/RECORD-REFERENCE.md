# Record reference

Optics keeps one JSON object per trace id. The shape is `unstable-pre-1.0`. Node 0.3.24 and published Python 3.0.14 both set `schema_version` to `2` and `vantio_run_log` to `"1"`. The rest of the object is not the same. There is no SQLite database, no migration tool, and no JSON Schema file shipped as a validator.

## Where files are

| Writer | Directory |
| --- | --- |
| Node interceptor | `$VANTIO_HOME/runs` if `VANTIO_HOME` is set, otherwise `~/.vantio/runs` |
| Python SDK | Same rule: `VANTIO_HOME` or `~/.vantio`, then `runs` |
| CLI reader (`prove`, `search`, `tail`, `diff`, `discover`, `status`) | `~/.vantio/runs` only. `VANTIO_HOME` is ignored. |
| `@vantio/optics-mcp@0.1.2` | Honors `VANTIO_HOME`, otherwise `~/.vantio/runs` |

File name: the trace id, characters outside `[A-Za-z0-9_-]` replaced with `_`, truncated to 80 characters, plus `.json`. Writing the same trace id again replaces the file.

`trace_id` is the id for that `vantio run` or that Python install. It is not a W3C trace id and not a per-call span. The CLI parent uses `0x` plus 16 hex digits when `VANTIO_TRACE_ID` is unset. If the Node interceptor starts without that variable, it falls back to `randomUUID()` with no `0x` prefix. Python uses `uuid4` when the variable is missing.

## Write

Calls sit in memory for the life of the process. Python appends under a thread lock. Node relies on the single thread of the event loop and hooks `Array.push` so the telemetry gate can see the first call. Nothing writes the run file per call.

At exit (Node `process` exit, Python `atexit` / `uninstall`) the process serializes the full list once.

- Node uses `writeFileSync` with mode `0o600` and creates the directory at `0o700`.
- Python opens the file with `"w"`, then `chmod` `0o600`, and ignores chmod errors. Directory create uses `0o700`.
- Neither write uses a temporary file plus rename.
- Neither write takes a cross-process file lock. Two processes can replace the same path.
- Any write exception is discarded. The agent exit continues. A full disk drops the file silently.

Node writes on every exit hook, including zero calls. Python returns without writing when `calls` is empty or the trace id is missing.

## Read

`vantio prove`, `search`, `tail`, `diff`, and `discover` parse JSON files in the CLI runs directory.

| Result | Behavior |
| --- | --- |
| Unreadable or invalid JSON | `search`, `discover`, and `prove --list` exit 1. `status` sets runs to `OPTICS_ERROR` and continues. MCP skips the file. |
| `vantio_run_log` is not `"1"` | CLI `loadRunLog` exits 1. Listings skip it. |
| `schema_version` differs | Readers do not check it. A future file with the same marker is accepted. |

`vantio prove --from <file>` renders a JSON object from that path. It does not require `vantio_run_log` on that render path, and it does not copy the file into `runs/`.

There is no import command, no JSONL export, and no OTLP exporter. `vantio prove` is the export: HTML (default, file `vantio-proof-<id>.html` in the current directory), Markdown (`--format=md`), or `--json` with `schema_status` `unstable-pre-1.0`.

Search, tail, and diff behavior: [NODE-GUIDE.md](NODE-GUIDE.md).

## Node 0.3.24 envelope

Written by the interceptor. Field set from the exit object:

| Field | Value |
| --- | --- |
| `vantio_run_log` | `"1"` |
| `schema_version` | `2` |
| `plane` | `"optics"` |
| `data_note` | Metadata-only note. Prompts and completions are named as never stored. |
| `trace_id` | Run id |
| `pid`, `ppid` | Process ids. `ppid` null when unavailable. |
| `node_version`, `platform`, `arch` | From the Node process |
| `started_at`, `generated_at` | UTC ISO with `Z` |
| `duration_ms` | Wall clock, `Date.now` difference. Not clamped. |
| `cli_version` | CLI package version |
| `free_mode` | True when no control-plane API key is loaded |
| `calls` | Array mapped below |
| `summary` | `total_calls`, `total_bytes`, `hosts`, `providers`, `errors`, `by_host`, `by_provider`, `redacted`, `blocked`, `est_spend_usd` (`null` in free mode) |
| `residual.note` | Short metadata note |

`schema_status` is absent on this file. CLI stdout JSON adds `schema_status` `unstable-pre-1.0` via `withSchema`. That marker is the command output, not the run file.

`summary.hosts` is the list of hostnames in the run. It is not the telemetry payload. Telemetry `hosts` is defined in [TELEMETRY.md](TELEMETRY.md).

### Node call object

`hostname`, `provider` (guess at write time), `method`, `path` (pathname, no query), `scheme`, `request_bytes`, `bytes`, `status`, `ok`, `content_type`, `duration_ms`, `action`, `ts`, `redactions`, `error`, `error_class`.

Missing values become null or zero in this mapper. Free-mode `action` is `OBSERVED`. Network failure sets `ok` false, `error` `network_error`, and `error_class` from the error name. The body is not a field.

The envelope has no `machine`, no span id, no session id, and no evidence-origin field.

## Published Python 3.0.14 envelope

| Field | Value |
| --- | --- |
| `vantio_run_log` | `"1"` |
| `schema_version` | `2` |
| `plane` | `"optics"` |
| `workflow` | The string `sight_loop`. Leftover storage. Not the product name. Node files do not have this field. |
| `data_note` | Metadata-only note |
| `trace_id` | Run id |
| `runtime` | `"python"` |
| `mediation` | Comma-joined mediation labels from the calls |
| `started_at`, `generated_at` | UTC timestamps from `datetime` (`+00:00` offset form) |
| `calls` | In-memory call list |
| `summary` | `total_calls`, `hosts` |
| `residual.note` | Describes the Python wrap. The sentence that mentions a Phantom Engine API key is describing a control-plane branch, not free Optics. This manual does not document that branch. |

No `schema_status`, `pid`, `ppid`, `free_mode`, envelope `duration_ms`, `by_host`, or `est_spend_usd`.

### Python 3.0.14 call object

`hostname`, `provider` (`"other"` from this tree's hooks), `action`, `mediation`, `ts`, plus extras such as `path`, `status`, `ok`, `duration_ms`, `error`, `error_class`.

## Unpublished Python 3.1.0 source

Same write path, plus file fields that 3.0.14 does not have: `schema_status` `unstable-pre-1.0`, `status_labels`, and summary fields `opticsStatus`, `applicationStatus`, `opticsLabel`, and customer summary fields. Calls gain `opticsStatus`, `applicationStatus`, `applicationOutcomeLabel`, `providerResponse`, and related lines. Source candidate 3.1.1 omits `workflow`. Older unpublished source stored the leftover string `sight_loop`. Do not treat a PyPI install as this shape.

## Schema markers

| Emitter | `vantio_run_log` | `schema_version` | `schema_status` |
| --- | --- | --- | --- |
| Node run file 0.3.24 | `"1"` | `2` | absent |
| Python run file 3.0.14 | `"1"` | `2` | absent |
| Python run file 3.1.0 source | `"1"` | `2` | `unstable-pre-1.0` |
| CLI command `--json` | depends on the command | depends | always `unstable-pre-1.0` |

`vantio demo` writes `vantio_run_log`, `schema_version` 2, `plane` `"optics"`, one call, and a small summary. It omits several Node envelope fields (`pid`, `free_mode`, `data_note`). Readers still accept it because the marker is `"1"`.

## URL storage

Hostname comes from URL parsing. Catalog checks lowercase the host. The stored call does not add a separate canonical-host field. Default ports are used for scope checks on Node (`destFromHref`) and are not a guaranteed field on the free-tier call record. Query strings are not stored. IPv6, proxies, and redirects are not folded into one destination. A redirect is a later request, recorded only if that request is in scope.

## Demo and hand-written files

`vantio demo` is an in-process stub: `POST /v1/chat/completions`, HTTP 200, host `optics-demo.invalid`, provider `openai`, bytes 0, action `OBSERVED`, duration 0, no network. The file is a normal run. There is no fixture flag.

Tests in the repository write the same kind of file. Those tests are not part of the installed CLI.

## Version skew

Node 0.3.24 and Python 3.0.14 or 3.1.0 source can share one directory. Envelopes differ. No command migrates them. No command refuses a newer `schema_version`. Rollback of the CLI is best-effort parse of whatever JSON is there.

`@vantio/agent-sdk` (Node) 0.2.4 does not write this directory.
