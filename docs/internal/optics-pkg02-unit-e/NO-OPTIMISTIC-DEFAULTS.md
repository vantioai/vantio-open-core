# PKG-02 Unit E optimistic defaults

Audience: INTERNAL_RESTRICTED

- A missing `optics_status` is stored as `UNAVAILABLE`.
- An input `opticsStatus` or `optics_status` of `SUCCESS` is stored as `UNAVAILABLE`.
- A call this writer saw is stored as `OBSERVED`, including when `application_status` is `UNAVAILABLE`.
- `application_status` `PARTIAL` is not stored. Mixed HTTP outcomes set envelope `lifecycle` `PARTIAL`.
- A missing response size omits `response_bytes`. An explicit `0` stays `0`.
- `provider` is not copied into `provider_id`.
- A comma-joined mediation string is not stored as one event token.
- `duration_ms` is omitted when the clock was not started.
- Empty `shield()` is `NOT_OBSERVED`, with an empty `events` array.
- Prohibited names, including `prompt`, drop the event. The value is not written.
- The pinned profile id on the bundle is `PKG01-UCD-16.0.0`.
