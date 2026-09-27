# PKG-02 Unit C — no writer

PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

`shield` in `vantio-agent-sdk` 3.1.0 is not replaced, wrapped, or redirected. The adapter package does not import that module.

A 3.1.0-shaped JSON file is hashed by the test, parsed, adapted, and hashed again. The file bytes match. The in-memory source still shows `opticsStatus` `SUCCESS` and the `+00:00` timestamp. The detached projection shows `UNAVAILABLE` and `Z`.

Path objects are refused with `PATH_NOT_OPENED` and `UNAVAILABLE`. The adapter does not stat them and does not create `~/.vantio/runs`.

Rollback of this unit is deletion of `packages/optics-python-adapter/`, `tests/optics-python-adapter/`, and `docs/internal/optics-pkg02-unit-c/`. Customer files are unchanged because this unit does not write them.

Python 3.0.15 is not the vehicle. Python 3.1.0 is not republished. CLI 0.3.24 is not reopened.
