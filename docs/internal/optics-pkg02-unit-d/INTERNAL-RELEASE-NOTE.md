# PKG-02 Unit D internal release note

PRIVATE | FUTURE LINE | NOT PUBLISHED | NOT SEALED | NO UNIT E | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

This note is not an announcement and not a changelog entry for publication.

`@vantio/cli` `0.4.0-pkg02-unit-d` writes canonical Optics records for new runs. `@vantio/cli` `0.3.24` does not read those files. That pairing is `UNSUPPORTED`.

The frozen display assigns optics `SUCCESS` to a call row and reads `hostname` and `status`, not `destination_host` and `http_status`. A rolled-back reader reports `UNSUPPORTED` with `schema_status` `unstable-pre-1.0` and `schema_version` `0` visible. It does not convert the file to `SUCCESS`.

Already-written canonical files stay in place when the writer is disabled. The next run, under a new trace id, uses the `0.3.24` record shape.

`@vantio/agent-sdk` `0.2.4` is not this writer. Python writer activation is not this note.
