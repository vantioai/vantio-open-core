# PKG-02 reader compatibility entry gates — known limitations

PRIVATE | INERT | NOT SHIPPED | READ_AND_EXPLAIN | NO_WRITE_BACK | NO_LIVE_WRITER | NO_MIGRATION | NO_STABLE_SCHEMA

Audience: INTERNAL_RESTRICTED

- A passing report does not authorize Unit D or Unit E. `PKG02-FUTURE-CLI-UNASSIGNED` and `PKG02-FUTURE-PYTHON-UNASSIGNED` are not versions.
- The detached reading of a newer `schema_version` uses contract schema version `0`. That normalization is not written back. It is not a migration and it is not permission to rewrite the file in a later writer force.
- Frozen `displayCall` still returns optics `SUCCESS` for a call row. This force records that pairing as `UNSUPPORTED` and does not change `optics-cx.cjs`.
- Node SDK `0.2.4` remains a non-writer. The gate checks that an ingest-shaped payload does not become a local observation. It does not add a reader to `0.2.4`.
- Python `3.1.0` remains a non-reader. The direct test runs frozen `shield()` only to obtain a legacy file.
- The Unit F isolation test that diffs `4e50dd9775d23899e1c68e5fa0e7a59c17066ea3` to `HEAD` is already failing on this starting commit because later shared-health vocabulary files sit outside that test's allowlist. This force does not edit that test. This force's own isolation check uses `89f95099d0dce463307eb75d78e7fcf2ef99feb2`.
- No SQLite, UI, daemon, exporter, alerting, release candidate, seal, or announcement.
- `council_verdict` stays null. This classification is not a council verdict and not a merge.
