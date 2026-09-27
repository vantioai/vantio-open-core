# PKG-02 Unit F known limitations

PRIVATE | INERT | NOT SHIPPED | READ_AND_EXPLAIN | NO_WRITE_BACK | NO_LIVE_WRITER | NO_MIGRATION | NO_STABLE_SCHEMA

Audience: INTERNAL_RESTRICTED

- This unit does not activate a writer. Units D and E stay `NOT_AUTHORIZED`. `PKG02-FUTURE-CLI-UNASSIGNED` and `PKG02-FUTURE-PYTHON-UNASSIGNED` are not releases.
- The reader is not on the `vantio run` exit path and is not imported by `@vantio/cli` 0.3.24, `vantio-agent-sdk` 3.1.0, or `@vantio/agent-sdk` 0.2.4.
- An explicit catalog `optics_status` `SUCCESS` is not displayed. The inert reading shows `UNAVAILABLE`. The frozen CLI display still reports optics `SUCCESS` for a call row. This unit does not change that display.
- A demo file's envelope stays `LEGACY_UNMARKED`. `SIMULATED_DEMO` is the observation label. The reader does not promote either label to `LOCAL_OBSERVATION`.
- The ordinary-client Python file is produced by the frozen `shield()` in a temporary home. That invocation does not edit Python `3.1.0`.
- `explainCopy` refuses a path string. Only `readRunFile` opens a file, and it only reads.
- No SQLite, migration, UI, daemon, exporter, alerting, release candidate, seal, or announcement.
- This classification is not a council verdict, not a merge, and not a statement that a writer exists.
