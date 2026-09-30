# @vantio/cli changelog (documentation record)

This heading exists so a documentation release can require a changelog entry for the version already in `packages/vantio-cli/package.json`. It does not bump that version.

## 0.3.25

CANDIDATE_ONLY_NOT_FOR_PUBLICATION. Source version only. Not an npm release.

CLI readers honor `VANTIO_HOME`. A `VANTIO_INGEST_URL` that is not http(s) is reported, and with an API key in-scope calls fail closed. Streaming byte counts are recorded before the run log is written.

## 0.3.24

Documentation baseline at `14249ba84ff1f3d5aa8ad7a7366172f29235c76e`. The CLI reads its version from package.json. Product behavior is unchanged by this documentation record.
