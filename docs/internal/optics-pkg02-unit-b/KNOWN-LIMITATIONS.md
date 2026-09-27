# PKG-02 Unit B known limitations

PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

- This unit does not activate a writer. Units D and E stay closed. `PKG02-FUTURE-CLI-UNASSIGNED` is not a release.
- The adapter is not on the `vantio run` exit path. A real CLI `0.3.24` run file stays byte-identical when this package is loaded and when a copy of that file is adapted.
- The Unit A runner still does not convert records. This package is the converter of copies. It does not rewrite the source file.
- The mapper stores invalid `sampling` as `UNSAMPLED`. The detached reading omits that key. The mapper maps `generated_at` to `ended_at`. The detached note says that is write time. The mapper fills a null span when the source omitted span. The detached reading removes that null. The mapper drops `IMPORTED` without provenance. The detached reading writes `IMPORTED` back and does not upgrade it.
- An explicit canonical `optics_status` `SUCCESS` is refused here even though the catalog allows the token when the caller sent it. This inert adapter does not store that token.
- Calls longer than 64 hit the contract copy bound `INPUT_BOUND`. The result has no envelope and no partial list of 64 events. This unit does not raise the bound.
- Node SDK `0.2.4` ingest is `UNSUPPORTED`. It is not turned into a local run log.
- Python fixture scoring uses the shared mapper. It is not Unit C and it does not publish or seal `3.1.0`.
- The frozen CLI display still reports optics `SUCCESS` for a call row. This unit does not change that display.
- No SQLite, migration, UI, daemon, exporter, alerting, release candidate, seal, or announcement.
- The Unit A isolation path check now diffs against the Unit A branch tip `299651c429b588e1e982a26ba717a1b4f1ffeac4`. The merge commit on main also contains the public manual, so a diff from that merge to the pre-Unit-A base names those manual files.
