# PKG-02 Unit C boundary

PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

Unit C is the inert Python adapter. It depends on merged Unit A. It is parallel to Unit B. It is not a writer activation, not a reader release, and not a publish of Python 3.1.0.

`schema_status` is `unstable-pre-1.0`. `schema_version` on a projected record is `0` when the source carried a legacy schema version. JSON Schema is not the source of truth.

## Starting point

Locked main: `587f3b94d47ea958f91d3a99125cd55931d995f1`.

Branch: `cursor/pkg02-unit-c-inert-python-c7bb`.

## In scope

- A private Python package beside the evidence contract.
- Copy-in, projection-out adaptation.
- Scoring the Unit A fixtures on CPython 3.12.
- A byte-identity check that a 3.1.0-shaped file is unchanged after the adapter reads a parsed copy.

## Out of scope

- `packages/vantio-agent-sdk-py/vantio/` and `pyproject.toml` on the 3.1.0 line.
- `packages/vantio-cli/`.
- PKG-01 tables, Unicode data, and the evidence-contract modules.
- The Unit A vocabulary files.
- PyPI, TestPyPI, Twine, a release candidate, a seal, a tag.
- SQLite, migrations, UI, a daemon, OTLP, alerting.
- Units B, D, E, and F.
- Opening a live `~/.vantio/runs` path. A path argument is refused before any read.

Producer classification before council: `OPTICS_PKG02_UNIT_C_READY_FOR_COUNCIL`.
