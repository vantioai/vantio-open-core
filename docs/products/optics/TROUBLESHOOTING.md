# Troubleshooting

Support answers should name the installed versions first.

```bash
# Example status: illustrative
vantio --version
python -c 'import vantio; print(vantio.__version__)'
```

Expect CLI `0.3.24`. Expect Python `3.0.14` on a PyPI install. Python `3.1.0` means this git tree, not the published package.

## No run file

| What you ran | What happened |
| --- | --- |
| `node agent.js` without `vantio run` | The interceptor was not attached. |
| `vantio run python` without `vantio-agent-sdk` on that interpreter | Warning on stderr. The agent continues. No calls are recorded. |
| Python wrap with zero in-scope calls | Python writes nothing. An empty result is expected. |
| Node wrap with zero in-scope calls | Node still writes a file with `calls: []` when the exit hook runs. |
| `VANTIO_HOME` set | Writers use `$VANTIO_HOME/runs`. `vantio search`, `prove`, `tail`, `diff`, and `discover` read `~/.vantio/runs` only. The MCP reader uses `VANTIO_HOME`. Look in the directory the writer used. |
| Process killed with `SIGKILL`, or the machine lost power | The exit hook did not run. There is no partial-recovery record. A missing file looks the same as a process that was never attached, except that a Node hook which did run writes even for zero calls. |
| Host outside the catalog | The call is ignored. Add the host only if you intend to observe it: `VANTIO_EXTRA_LLM_HOSTS`. |

`vantio tail --follow` stays quiet until exit, because the file is replaced once at the end, not appended per call.

## A call you expected is missing

Confirm the client is in [SUPPORTED-PATHS.md](SUPPORTED-PATHS.md). Then confirm the hostname. Then confirm the process was the wrapped one (`trace_id` printed on stderr at `vantio run` start: `run trace_id=…`).

Browser traffic, a second language runtime, and a subprocess that drops the wrapper will not appear. Say `NOT_OBSERVED`. Do not say the call was blocked.

## Commands exit 1 on a bad file

`vantio search`, `vantio discover`, and `vantio prove --list` exit 1 when a `.json` file in the reader directory is unreadable or is not valid JSON. One corrupt file blocks those commands. `vantio status` keeps scanning and sets run optics status to `OPTICS_ERROR`. The MCP reader skips corrupt files. The same directory does not have one error policy.

Move the bad file aside, or fix the JSON, and retry. Optics does not rebuild an empty store for you.

`loadRunLog` also exits 1 when `vantio_run_log` is not `"1"`. Readers do not check `schema_version`.

## Disk full and write errors

Run-log write errors, including a full disk, are caught and discarded. The agent still exits. No health record is stored. If a file you expected is missing after a full disk, the write was dropped.

`vantio prove` write failure exits 1 and prints the first line of the error. It does not label a half-written proof.

## Wrong run selected

The file name is the trace id with characters outside `A-Za-z0-9_-` replaced by `_`, cut at 80 characters, plus `.json`. The same trace id overwrites that file. There is no cross-process lock. Two writers with the same id replace one file.

`find` by prefix uses `filename.includes(prefix)`. A short prefix can match more than one id. Pass a longer prefix.

## Provider shows `other` on Python

Published 3.0.14 stores `provider` `"other"`. Use `hostname`. Node may show `openai` for the same host because it guesses from substrings. Both can be correct for their writers.

## `ok` is true on an HTTP error

That matches published Python 3.0.14. CLI display ignores `ok` and uses the status code. Application outcome for 400–599 is `APPLICATION_ERROR`. Unpublished 3.1.0 source stores `ok` false for those statuses. You only have that storage if you are running the unpublished tree.

## Duration looks wrong

Durations use the wall clock (`Date.now` on Node, `time.time` on Python). A step backward of the clock can store a negative Node duration. Python clamps at zero. Timestamps are UTC. Node uses a `Z` suffix. Python 3.0.14 uses an offset form from `datetime.isoformat()`. There is no sequence number when two timestamps tie. Order of timestamps is not a causality proof.

`vantio demo` duration is fixed at 0 ms.

## Telemetry surprised you

CLI: the ping is off until `VANTIO_TELEMETRY=1`.

Published Python `shield()`: the ping is on until `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1`.

`vantio run python` without entering `shield()` does not send the Python ping. Details: [TELEMETRY.md](TELEMETRY.md).

## `vantio discover` is not every process

It reads run logs on this machine for the time window (`24h` default, or `7d`, `30d`). curl typed in a terminal, a browser, and any unwrapped process are outside the list.

## Login and keys

`vantio login` is not a help command in 0.3.24. Free Optics does not ask for a key. If an old `~/.vantio/config.json` is still on disk, `vantio logout` deletes that file and does not delete `runs/`. The command is omitted from `vantio --help`.
