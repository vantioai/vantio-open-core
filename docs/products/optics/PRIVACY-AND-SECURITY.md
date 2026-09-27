# Privacy and security

Optics stores structural metadata about supported outbound calls. The design goal is to show where an agent called, when, and how large the exchange was, without storing the conversation.

## Stored on the free path

For a recorded call, the Node 0.3.24 file can contain hostname, provider guess, method, URL path, scheme, request size, response size, HTTP status, `ok`, content-type media type, duration, action `OBSERVED`, timestamp, a redaction count (zero in free mode), and an error class name on network failure. The envelope adds trace id, pid, ppid, Node version, platform, arch, start and end times, duration, CLI version, and summary counts.

Published Python 3.0.14 stores a smaller call object: hostname, provider `"other"`, action, mediation, timestamp, and the extras that hook recorded (path, status, ok, duration, error name). The envelope has no pid. See [RECORD-REFERENCE.md](RECORD-REFERENCE.md).

Response size on Node is `Content-Length` when the header exists. A missing header leaves the size empty or zero depending on the path. Streaming byte totals in a control-plane branch are outside free Optics.

A local check on 2026-09-27 posted a prompt canary and a query token to a loopback server through `vantio run node` (CLI 0.3.24) and through `vantio run python3` with published `vantio-agent-sdk==3.0.14`. The run files contained the path and the host. They did not contain the prompt, the query token, or the response body.

## Absent from the free record

- Prompt text
- Model completions and response bodies
- A stored copy of request bodies
- Query strings (`?` and everything after). The stored path is the URL pathname
- Header maps
- API keys and `Authorization` values, unless the application placed them inside the URL path that is stored

The content-type field keeps the media type before `;`.

## Path segments

The query string is dropped. The path is not. A secret, token, or identifier placed in the path is stored with the call. Put secrets in headers or in bodies, which the free record does not keep, and treat path design as part of review.

Exception text on the unpublished 3.1.0 transport classifier is reduced to a fixed phrase. That behavior is not the published 3.0.14 package. Do not assume 3.0.14 dropped every exception string until you inspect the file.

## Redaction

Free mode does not rewrite request bodies. A `redactions` count on a Node free-mode call stays zero. Body rewrite and blocking run only when a non-public control plane and API key are loaded inside the process. That mode is not free Optics, and this manual does not document it. Optics itself does not redact and does not block.

`redact_pii` in the Python and Node SDKs is a library function for a control-plane policy. It is not the free Optics recorder. This manual does not document it.

## Files on disk

| Path | Contents | Mode when the writer creates it |
| --- | --- | --- |
| `~/.vantio/runs/<trace>.json` | Run log | File `0600`. Directory `0700` if that writer created it. |
| `~/.vantio/telemetry-id` | Random telemetry id | `0600` when creation succeeds. |
| `~/.vantio/config.json` | Leftover from older builds, if present | The current CLI does not read it for `run`. `vantio logout` deletes this file only. |
| `./vantio-proof-<id>.html` | `vantio prove` HTML default | The HTML writer does not pass mode `0600`. |

Unix modes are subject to umask and are not reapplied when the directory already exists. Python chmod errors are ignored. Windows ACLs are not set by these writers. A `~/.vantio` directory created earlier by telemetry can be wider than `0700` while a newly created `runs` directory is `0700`.

Writers do not test whether `runs` is a symbolic link before writing. `vantio status` skips symbolic links when it sums directory size.

Reviewers should treat `~/.vantio` as local operational data, readable by the user account that ran the agent.

## Demo files

`vantio demo` writes a normal run file for host `optics-demo.invalid`. Discover, search, tail, diff, and prove include it. There is no origin field that excludes fixtures. A security review of "all production calls" must filter that hostname, or any other fixture you wrote by hand.

## Proof export

`vantio prove` re-renders the run file as HTML, Markdown, or unstable JSON. It does not add a content hash, signature, or completeness manifest. `--from` reads a path you choose and renders a JSON object. That path does not have to carry `vantio_run_log`. Rendering a file does not copy it into `runs/` and does not prove Optics produced it.

The HTML table uses host, Optics status, application outcome, HTTP status, bytes, and time. It does not print a `machine` field. Current writers do not set `machine`. Older prose that expects `machine` in the report does not match CLI 0.3.24 HTML.

MCP `optics_prove` Markdown can include action, method, and path, and can print `machine` as a dash when the field is missing. CLI proof and MCP proof are not the same columns.

## Telemetry

The usage ping is a separate channel. Read [TELEMETRY.md](TELEMETRY.md) before you answer "does Optics phone home?"

Short form: CLI 0.3.24 does not send unless `VANTIO_TELEMETRY=1`. Published Python 3.0.14 `shield()` does send unless `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1`. The field `hosts` on that ping lists customer LLM endpoint hostnames, not prompts.

## Control plane

If the environment already has `VANTIO_API_KEY` and `VANTIO_INGEST_URL` pointing at a host other than the public site, the process can load policy. The public host does not receive that key for configuration. This manual does not document the policy client. Do not describe those branches as free Optics features, and do not describe unobserved traffic as enforced.
