# Known limitations

This page lists what Optics does not do, and the gaps that are easy to over-read. Versions: CLI 0.3.24, published Python 3.0.14, unpublished Python 3.1.0 source as labeled.

## Absent on purpose in the current products

| Item | State |
| --- | --- |
| Enforcement, blocking, redaction, spend caps | Phantom Engine. Free Optics records `OBSERVED` and does not apply those controls. |
| SQLite or any other database | Absent. One JSON file per trace id. |
| `vantio ui`, `vantio doctor`, a resident daemon | Absent. |
| Alerting | Absent. |
| OTLP export | Absent. A mapping sketch may exist elsewhere in the repository. Optics does not export OTLP. |
| Stable schema | Absent. Contract is `unstable-pre-1.0`. |
| PKG-02 and any shared record vocabulary shipped as a runtime | Future work. Not in the CLI or the published SDK. |
| Retention, prune, max size | Absent. Files stay until you delete them. |
| Cross-process file lock | Absent. In-process, Python locks its memory list only. |
| Import into `runs/` | Absent. `prove --from` renders a file and leaves it where it is. |
| Evidence origin, content hash, signature | Absent. Demo files look like other runs. |
| Per-call span id, session id, `machine` | Writers do not set them. |
| Lifecycle `INTERRUPTED` / `ABANDONED` / `RECOVERED` | Absent. |
| Monotonic clock | Durations use the wall clock. |
| Windows ACL | Not set. Unix modes `0700` / `0600` only, and only when the writer creates the path. |
| Fleet inventory | `discover` is this machine's run logs. |

Unsupported paths in [SUPPORTED-PATHS.md](SUPPORTED-PATHS.md) are unobserved. They are not protected by Optics.

## Record gaps

- Node writes a file for zero calls. Python writes only when at least one call was stored. "No file" means different things.
- CLI readers ignore `VANTIO_HOME`. Writers and the MCP reader honor it.
- Node provider labels are substring guesses. Published Python labels are `"other"`.
- The same trace id overwrites one file. Prefix search can hit the wrong file.
- A crash during the single write can leave a partial file. Write errors are swallowed.
- `SIGKILL` skips the flush.
- Query strings are dropped. Path segments are stored and can hold secrets.
- Published Python 3.0.14 can store `ok: true` on HTTP errors. Display uses the status code.
- Python files contain `"workflow": "sight_loop"`. That string is not current product terminology.
- The published PyPI summary and the MCP package description still contain that older phrase. This manual does not adopt it.
- `vantio prove` HTML and MCP Markdown do not show the same columns.
- `prove --from` can render JSON that Optics did not write.
- One corrupt JSON file fails `search`, `discover`, and `prove --list`, is flagged by `status`, and is skipped by MCP.
- Node and Python envelopes differ under the same `schema_version`. Nothing migrates them.

## Telemetry gap between published packages

CLI 0.3.24 is opt-in. Published Python 3.0.14 `shield()` sends unless disabled with `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1`. Unpublished 3.1.0 source is opt-in. Describe the package the person installed. See [TELEMETRY.md](TELEMETRY.md).

The telemetry field `hosts` means customer LLM endpoint hostnames. On the CLI ping it is the first recorded call's hostname. On the Python `shield()` ping it is empty.

## Coverage of tests

Repository tests exercise CLI commands, the Node interceptor on supported clients, telemetry allowlists, and the Python observe hooks. They are unit and integration tests in this repo. They are not a customer deployment, not a stranger-host proof, and not a certificate. This manual does not claim an external proof tier.

Not covered by those tests as a product guarantee: SQLite, retention, cross-process locking, symlink confinement of `runs/`, disk-full evidence, `SIGKILL` flush, monotonic duration, automatic exclusion of demo files, or identical Node and Python envelopes.

## Unpublished source is not the product

Reading `packages/vantio-agent-sdk-py` at this commit shows version 3.1.0. The PyPI project JSON for `vantio-agent-sdk` on 2026-09-27 reported latest version 3.0.14. This manual did not upload a package. Features that exist only in 3.1.0 source are documented as unpublished. They are not in the manual's install instructions.
