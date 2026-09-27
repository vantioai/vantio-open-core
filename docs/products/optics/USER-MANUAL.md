# Vantio Optics user manual

Manual version 1. Product name: **Vantio Optics**.

Optics is free, local-first observability for supported AI-agent traffic. It records that a wrapped process called a destination, when, and how large the exchange was. Prompts and completions are absent from the record.

Optics observes. Phantom Engine is the separate product that enforces. This manual stops at Optics.

The installable versions this text describes are `@vantio/cli@0.3.24` and `vantio-agent-sdk==3.0.14`. Python 3.1.0 in the source tree is unpublished. See [VERSION-METADATA.json](VERSION-METADATA.json).

## Who this is for

**First-time developer.** Install the CLI, run `vantio demo`, then prefix the agent with `vantio run`. [QUICKSTART.md](QUICKSTART.md).

**Security reviewer.** Read [PRIVACY-AND-SECURITY.md](PRIVACY-AND-SECURITY.md), [TELEMETRY.md](TELEMETRY.md), and [SUPPORTED-PATHS.md](SUPPORTED-PATHS.md) before you write a control statement. A missing row is not a block.

**Support.** Start with `vantio --version` and the Python version print in [TROUBLESHOOTING.md](TROUBLESHOOTING.md). Status tokens are in [STATUS-AND-OUTCOMES.md](STATUS-AND-OUTCOMES.md).

**Evaluator.** The capability below is the whole free product: local metadata on supported paths, plus local commands over those files. SQLite, a UI, alerting, OTLP, and a stable schema are not included. [KNOWN-LIMITATIONS.md](KNOWN-LIMITATIONS.md).

**Upgrade from v2 or from Python 3.0.x.** [UPGRADE-ROLLBACK-UNINSTALL.md](UPGRADE-ROLLBACK-UNINSTALL.md) and [PYTHON-GUIDE.md](PYTHON-GUIDE.md).

**AI assistant.** [AI-GUIDE.md](AI-GUIDE.md).

## What a run is

You start a process with `vantio run` (Node or Python) or you enter Python `shield()`. The wrapper watches supported HTTP and socket calls to in-scope hosts. At process exit it writes one JSON file.

```bash
# Example status: illustrative
npm install -g @vantio/cli@0.3.24
vantio run node agent.js
vantio prove
```

Free Optics needs no account and no API key. The CLI does not load `~/.vantio/config.json` to start a run.

The stderr line `run trace_id=0x…` is the id for that launch. The file name is that id, sanitized. Details: [RECORD-REFERENCE.md](RECORD-REFERENCE.md).

## Node and Python are not the same attach

Node: `vantio run` prepends `--require` of the interceptor for `node`, `npx`, `tsx`, and `ts-node`. The interceptor writes a log even when nothing in-scope was called, if the process reaches the exit hook.

Python: install `vantio-agent-sdk==3.0.14` on that interpreter, then `vantio run python agent.py` or call `shield()`. Without the SDK, the prefix does not intercept. Python writes a log only when at least one call was recorded.

Library lists: [SUPPORTED-PATHS.md](SUPPORTED-PATHS.md).

## Commands

| Command | Role |
| --- | --- |
| `vantio run` | Spawn a program under the wrapper. |
| `vantio demo` | Write one stub call. No network. Host `optics-demo.invalid`. |
| `vantio status` | Local version, telemetry posture, data size, whether a run exists, which provider packages resolve. |
| `vantio discover` | Group recent calls by host. This machine only. Default window 24h. |
| `vantio prove` | HTML, Markdown, or unstable JSON rendered from one run file. |
| `vantio search` | Substring scan of local run files. |
| `vantio tail` | Last calls of one run. `--follow` prints after the exit rewrite. |
| `vantio diff` | Host and byte deltas between two runs. |

```bash
# Example status: illustrative
vantio discover --local --since=7d
vantio search openai
vantio tail -n 20
vantio diff 0xabc 0xdef
vantio prove --format=md --out=report.md
```

`--json` on these commands adds `"schema_status": "unstable-pre-1.0"`. The shape may change. The Node run file itself does not carry `schema_status`.

Exit status 0 means the command finished, including an empty result. Exit status 1 means bad arguments or a file that could not be read or parsed.

`vantio logout` is hidden from help. It deletes `~/.vantio/config.json` only.

## How to read an outcome

The stored action on a free run is `OBSERVED`.

The CLI then shows two display fields:

- **Optics status** `SUCCESS` / "Successful" means the record exists.
- **Application outcome** comes from the HTTP status: `SUCCESS` for 200–399, `APPLICATION_ERROR` for 400–599, `UNAVAILABLE` when no status was stored, `PARTIAL` when one run mixes those, `NOT_OBSERVED` when there are no calls.

The stored `ok` flag is not used for that display. Published Python 3.0.14 can store `ok` true on an error status. Use the HTTP status.

`NOT_OBSERVED` means there is no record. It does not mean the call was stopped.

Full table: [STATUS-AND-OUTCOMES.md](STATUS-AND-OUTCOMES.md).

## Privacy

The record keeps destination metadata. It does not keep prompts, completions, or request bodies on the free path. Query strings are dropped. A secret placed in the URL path is stored, because the path is kept. File modes and the telemetry ping are in [PRIVACY-AND-SECURITY.md](PRIVACY-AND-SECURITY.md) and [TELEMETRY.md](TELEMETRY.md).

If you describe the telemetry field `hosts`, say what it is: customer LLM endpoint hostnames (at most 50). The CLI ping sends the hostname of the first recorded call. The Python `shield()` ping sends an empty list because it is sent before any observation.

CLI 0.3.24 does not send the ping unless `VANTIO_TELEMETRY=1`. Published Python 3.0.14 `shield()` sends it unless `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1`. Those are different gates. Do not collapse them.

## Local proof

`vantio prove` reads a run log and writes a report. The report is the same evidence, rendered. It has no signature and no content hash. Default HTML is `vantio-proof-<id>.html` in the current directory. `--from` can render a JSON file you supply, including one Optics did not write.

`vantio demo` creates a real file in `runs/` with no origin marker. Filter `optics-demo.invalid` when you want production calls only.

## Read-only MCP

`@vantio/optics-mcp@0.1.2` lists and renders local logs over the Model Context Protocol. It does not block or redact. Its tools are `optics_list_runs`, `optics_get_run`, `optics_prove`, `optics_discover_local`, `optics_explain`, and `optics_upgrade_path`. The last tool points at Phantom Engine. This manual does not document Phantom Engine.

The MCP reader follows `VANTIO_HOME`. The CLI reader does not.

## Limits that belong in every evaluation

- Only wrapped processes and in-scope hosts produce rows.
- No database, no UI, no alerts, no OTLP exporter, no stable schema.
- No retention command. Disk grows until you delete files.
- No cross-process lock. The same trace id overwrites one file.
- Write failures are silent.
- Node and Python files differ.
- The string `sight_loop` inside a Python file is leftover storage, not the product name.

[KNOWN-LIMITATIONS.md](KNOWN-LIMITATIONS.md) is the full list.

## Where to go next

| Question | Page |
| --- | --- |
| Install pins | [INSTALLATION.md](INSTALLATION.md) |
| Node flags and commands | [NODE-GUIDE.md](NODE-GUIDE.md) |
| Python 3.0.14 versus unpublished 3.1.0 | [PYTHON-GUIDE.md](PYTHON-GUIDE.md) |
| Field-by-field file layout | [RECORD-REFERENCE.md](RECORD-REFERENCE.md) |
| Remove data | [UPGRADE-ROLLBACK-UNINSTALL.md](UPGRADE-ROLLBACK-UNINSTALL.md) |
| Package history | [CHANGELOG-GUIDE.md](CHANGELOG-GUIDE.md) |
