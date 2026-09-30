# @vantio/cli changelog

## 0.3.25

CANDIDATE_ONLY_NOT_FOR_PUBLICATION. This heading is source. It is not an npm release.

- CLI readers honor `VANTIO_HOME`.
- A `VANTIO_INGEST_URL` that is not http(s) is reported. With an API key, in-scope calls fail closed.
- Streaming responses record byte counts before the run log is written.
- Spawned curl and wget keep the request size in `request_bytes`. The response `bytes` field stays empty when the response size was not observed.
