# Known limitations

This page lists what Optics does not do, and the gaps that are easy to over-read. Versions: published CLI 0.3.25 and published Python `vantio-agent-sdk` 3.1.1. `@vantio/agent-sdk` stays 0.2.4. This page does not change CLI or SDK behavior.

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
- Node provider labels are substring guesses. Python 3.1.1 fills `provider` from the host catalog when the hostname is in that map, and stores `other` when it is not.
- The same trace id overwrites one file. Prefix search can hit the wrong file.
- A crash during the single write can leave a partial file. Write errors are swallowed.
- `SIGKILL` skips the flush.
- Query strings are dropped. Path segments are stored and can hold secrets.
- Python 3.1.1 stores HTTP 400–599 with `ok` false. An HTTP status is an application outcome, not `network_error`. DNS, connection, TLS, and timeout errors stay `network_error`. A machine still running Python 3.0.14 can store `ok` true on a returned 4xx or 5xx, and urllib on that older package stored `error` `network_error` for an HTTP error status.
- Python files contain `"workflow": "sight_loop"`. That string is not current product terminology.
- The published PyPI summary and the MCP package description still contain that older phrase. This manual does not adopt it.
- `vantio prove` HTML and MCP Markdown do not show the same columns.
- `prove --from` can render JSON that Optics did not write.
- One corrupt JSON file fails `search`, `discover`, and `prove --list`, is flagged by `status`, and is skipped by MCP.
- Node and Python envelopes differ under the same `schema_version`. Nothing migrates them.

## Telemetry gap between published packages

CLI 0.3.25 is opt-in. Python 3.1.1 `shield()` sends only when `VANTIO_TELEMETRY=1`. `VANTIO_TELEMETRY_DISABLED=1` and `DO_NOT_TRACK=1` keep both off. Python 3.0.14 `shield()` sends unless one of those two disable variables is set. Describe the package the person installed. [TELEMETRY.md](TELEMETRY.md) still records the 0.3.24 and 3.0.14 rows.

The telemetry field `hosts` means customer LLM endpoint hostnames. On the CLI ping it is the first recorded call's hostname. On the Python `shield()` ping it is empty.

## Coverage of tests

Repository tests exercise CLI commands, the Node interceptor on supported clients, telemetry allowlists, and the Python observe hooks. They are unit and integration tests in this repo. They are not a customer deployment, not a stranger-host proof, and not a certificate. This manual does not claim an external proof tier.

Not covered by those tests as a product guarantee: SQLite, retention, cross-process locking, symlink confinement of `runs/`, disk-full evidence, `SIGKILL` flush, monotonic duration, automatic exclusion of demo files, or identical Node and Python envelopes.

## The installed package is the product

`packages/vantio-cli` in this tree is 0.3.25. `packages/vantio-agent-sdk-py` in this tree is 3.1.1. Those are the versions a fresh npm and PyPI install returns after this publication. `@vantio/agent-sdk` stays 0.2.4. Confirm with `npm view @vantio/cli version` and `pip index versions vantio-agent-sdk` before you describe a machine that may still have an older install. This page did not upload a package.
