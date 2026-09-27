# PKG-02 Unit D — no optimistic defaults

PRIVATE | FUTURE LINE | NOT PUBLISHED | NOT SEALED | NO UNIT E | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

The future writer does not store `optics_status` `SUCCESS`.

| Situation | Stored optics token |
| --- | --- |
| The wrap saw a supported call and no optics token was supplied | `OBSERVED` |
| The wrap finished and no observation was stored | `NOT_OBSERVED` |
| The supplied optics token is `SUCCESS` or unknown | `UNAVAILABLE`, with `optimistic_default_forbidden` |
| Validation fails | `OPTICS_ERROR` |

A missing `content-length` omits `response_bytes`. It is not stored as `0`. An explicit length of `0` is stored as `0`.

HTTP `500` stores `application_status` `APPLICATION_ERROR` and `issue_location` `PROVIDER_INTERACTION`. The optics token stays `OBSERVED`.

A network failure stores `failure_kind` `network`, `issue_location` `NETWORK`, and `application_status` `UNAVAILABLE`. `response_bytes` is omitted.

The frozen interceptor still prints `Optics status: Successful` on stderr. That line is `packages/vantio-cli/bin/interceptor.cjs`, which this unit does not edit. The written file does not copy that token. `displayCall` in `optics-cx.cjs` still returns `SUCCESS` for a call row. That is why CLI `0.3.24` stays `UNSUPPORTED` as a reader of the new file. The rolled-back reader reports `UNSUPPORTED` and does not adopt the display token.
