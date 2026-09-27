# PKG-02 reader compatibility entry gates — inventory

PRIVATE | INERT | NOT SHIPPED | READ_AND_EXPLAIN | NO_WRITE_BACK | NO_LIVE_WRITER | NO_MIGRATION | NO_STABLE_SCHEMA

Audience: INTERNAL_RESTRICTED

Starting commit: `89f95099d0dce463307eb75d78e7fcf2ef99feb2` (`Merge pull request #83`).

## Frozen releases on that commit

| Surface | Version | Writer or reader today |
| --- | --- | --- |
| `@vantio/cli` | `0.3.24` | Writer of `vantio_run_log` `"1"` with legacy `schema_version` `2`. `displayCall` assigns optics `SUCCESS` to every call row. |
| `@vantio/agent-sdk` | `0.2.4` | No local run-log writer and no local run-log reader. |
| `vantio-agent-sdk` Python | `3.1.0` | Writer. Stored call `opticsStatus` is `SUCCESS`. The package does not read run logs. |

`packages/vantio-cli/bin/optics-cx.cjs` `opticsStatusForRecordedCall` returns `SUCCESS` and takes no arguments. This force leaves that function in place.

## Merged inert units already on this commit

| Unit | What is on main | Writer |
| --- | --- | --- |
| A | `packages/optics-record-vocabulary/` and the 34 conformance fixtures | None |
| B | `packages/optics-node-adapter/` calls the private contract on copies | None |
| C | `packages/optics-python-adapter/` scores the same fixtures | None |
| F | `packages/optics-record-reader/` explains a copy and re-reads the file | None |

Unit F already refuses unknown optics tokens, keeps absent, null, and unknown classes apart, preserves imported and demo labels, and leaves input bytes unchanged. It is not wired into `@vantio/cli` `0.3.24`.

## Gap this force closes

Units D and E, in `docs/planning/optics-pkg02/05-INTEGRATION-SEQUENCING.md` and `06-RELEASE-AND-ROLLBACK-BOUNDARY.md`, wait on a reader proof that legacy files, future files, unknown status, and rollback can sit together before either writer turns on. That proof was scattered across Unit F tests. It was not one fail-closed entry gate.

This force adds that gate. It does not add the writers.

## Matrix

`docs/planning/optics-pkg02/RECORD-COMPATIBILITY-MATRIX.json` stays `achievement` `NOT_SHIPPED` on every cell. This force does not edit that file. A passing gate is a reading proof. It is not a shipped compatibility cell.
