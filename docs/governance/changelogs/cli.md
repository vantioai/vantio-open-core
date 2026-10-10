# @vantio/cli changelog (documentation record)

This heading exists so a documentation release can require a changelog entry for the version already in `packages/vantio-cli/package.json`. It does not bump that version.

## 0.3.25

CANDIDATE_ONLY_NOT_FOR_PUBLICATION. Source version only. Not an npm release.

Candidate behavior, not an npm release. The customer installer pin stays on published CLI 0.3.24.

- A response size that was not measured is stored as absent. It is not written as zero, and a pre-response record does not store success.
- `http.request` and `http2` response headers fill status and measured size when they arrive. Undici dispatch does the same from response headers.
- CLI readers use `VANTIO_HOME` when it is set. Run lookup matches the file-name prefix, not a substring in the middle of another id.
- Customer lines say Observed outcome. HTTP 401, 403, 429, and 500 keep the machine token `APPLICATION_ERROR` and show the specific observed sentence.
- Provider names follow catalog hosts and known regional patterns. A hostname that merely contains a provider word is `other`.

## 0.3.24

Documentation baseline at `14249ba84ff1f3d5aa8ad7a7366172f29235c76e`. The CLI reads its version from package.json. Product behavior is unchanged by this documentation record.
