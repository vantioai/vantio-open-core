# PKG-02 Unit E boundary

Audience: INTERNAL_RESTRICTED

Unit E activates the Python Optics writer on `vantio-agent-sdk` `PKG02-FUTURE-PYTHON-UNASSIGNED`. That version is the future line. It is `3.1.0` on no tree in this change, and it is `3.0.15` on no tree in this change.

Starting commit: `dd3344dcc636136ed22df75e8df3866c993efd27`.

## In scope

- `packages/vantio-agent-sdk-py-future/`. The import name is `vantio_future`.
- Tests under `tests/optics-pkg02-unit-e/`.
- Internal notes under `docs/internal/optics-pkg02-unit-e/`.
- Claimed CPython: 3.12.

## Closed

- `packages/vantio-agent-sdk-py/` at `3.1.0`, including `vantio/` and `pyproject.toml`.
- `packages/vantio-cli/` at `0.3.24`.
- PyPI, TestPyPI, Twine, npm publish, a seal, a release candidate, a tag.
- Unit D, and any future CLI version line.
- SQLite, migrations, UI, a daemon, OTLP, SIEM, alerting, customer deploy, a stranger host.
- Announcements.
- Merge. This branch stops at `OPTICS_PKG02_UNIT_E_READY_FOR_COUNCIL`.

`activates_unit_e` is true on `MATRIX-MARKERS.json` for this unit. `activates_unit_d` is false. `registry_publish` is false. The reader-compat gate report stays `activates_unit_e: false` because that report describes the gate, which does not activate a writer.

The planning matrix file stays `achievement` `NOT_SHIPPED`. The Unit E marker uses `READY_FOR_COUNCIL` for the `future_python` writer cells only.
