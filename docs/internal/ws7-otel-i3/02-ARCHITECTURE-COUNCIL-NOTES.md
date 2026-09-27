# WS7 I3 architecture council notes

Audience: INTERNAL_RESTRICTED

`PENDING_COUNCIL`

Producer classification: `OTEL_I3_ADAPTER_READY_FOR_COUNCIL_DEFAULT_DISABLED`

These notes describe the adapter that was built. They are not a council verdict. The producing agent did not self-council.

## Separate package

The approved mapping package still has no enable path. Its three adapter rows stay `NOT_PRESENT`. `exportOpticsRecords` in that package still returns `ADAPTERS_DISABLED` when a caller passes `enabled: true`.

I3 is a second private package. It calls `preview` and then applies a stricter export gate. It does not patch the mapping module. Load fails if `mapping_id`, `mapping_version`, `schema_status`, `i3_status`, `otlp_export_authorized`, `adapters_default_enabled`, or `founder_decision_12` drift from the approved document.

That split keeps the merged mapping tests intact. A later force that changes the mapping marker has to revise this package in the same review.

## Authority, then delivery

`evaluateRecords` is pure. It does not open a socket. `exportOpticsRecords` calls it before it looks at the endpoint or the transport.

For one record the authority object carries:

- mapping id `WS7-I2`, mapping version `0`, and `schema_status` `unstable-pre-1.0`
- `operational`, which is true only when the mapping preview says `would_be_operational_if_i3_enabled` and this adapter did not add a blocking field name
- allowlisted candidates, and only when `operational` is true and every candidate re-validates
- span client and instrumentation tokens from the preview, under that same condition
- application-supplied W3C trace context from the preview, re-checked as lowercase hex

Eligibility is also pure. It does not change when the exporter is down. A record is export-eligible only when all of these hold:

- authority is operational and the candidates re-validated
- client and instrumentation statuses are not both set
- `error.type` agrees with the single status that is set
- trace context is present
- `start_time_unix_nano` and `end_time_unix_nano` are decimal strings, the end is greater than the start, and neither was read from `duration_ms`

The OTLP body is built from eligibility entries. The encoder does not receive the original record.

Admission applies the queue limit. Delivery is the only phase that calls the transport. A disabled call still returns authority and eligibility, with `bytes_sent` 0 and `network` false, and it does not echo the endpoint.

## Wire shape

The body is one OTLP/HTTP JSON `ExportTraceServiceRequest`:

- one resource with an empty attribute list
- scope `vantio.optics.i3` version `0.0.0-unstable-pre-1.0`
- no `schemaUrl`
- spans named `chat` when `gen_ai.operation.name` is `chat`, otherwise `gen_ai.client`
- kind `3` (client) or kind `1` (internal) when the only status is instrumentation `ERROR`
- status code `1` for client `OK`, `2` for `ERROR`, `0` when the mapping left both statuses unset
- attributes limited to the allowlist, keys sorted, integers encoded as proto3 JSON strings

Status code `0` means the mapping did not choose a span status. It is not a success claim. Optics `SUCCESS` does not become status `OK`. Application `SUCCESS` plus an integer HTTP status 200–399 does.

If both span dimensions are set, the record is not encoded. Mapping version 0 does not collapse them.

## Endpoint, queue, retry

The endpoint comes from the call. There is no default host. The scheme must be `http` or `https`. The path must be `/` or `/v1/traces`. The posted path is `/v1/traces`. Userinfo and query or fragment are rejected and are not copied into the result. Redirects are not followed. The HTTP client sets `content-type` and `content-length` only.

The built-in client is used only when the call omits `transport`. Tests inject a transport. A transport return value other than status and the `ok` / `backpressure` flags is ignored.

Queue default is 8 and the hard maximum is 32. A larger requested limit is clamped. Extra export-eligible records are drop evidence `BACKPRESSURE_QUEUE_LIMIT` and are not encoded.

Retry default is 2, so three attempts. The hard maximum is 5 attempts. There is no sleep. HTTP 429 retries until the cap and then becomes `BACKPRESSURE_EXPORTER`. HTTP 502, 503, and 504, timeouts, and thrown transport errors retry until the cap and then become `EXPORTER_UNAVAILABLE`. Other HTTP statuses, including redirects, do not retry and become `EXPORTER_REJECTED`. `bytes_sent` is the UTF-8 size of the JSON body only after 200 or 202. Otherwise `bytes_sent` is 0 and `bytes_dropped` is that size.

A lost success response can cause another send of the same body. This is not an exactly-once claim.

## Withheld fields

Unknown safe field names are listed. Their values are not copied. Unsafe names, including names longer than 64 characters, names outside `[A-Za-z0-9_.-]`, and `__proto__`, `constructor`, and `prototype`, are counted and not echoed. If the preview would have been operational, an unsafe name withholds the record.

These name classes also withhold an otherwise operational record:

| Class | Examples | Reason |
| --- | --- | --- |
| Content | prompt, completion, message, body | `PROHIBITED_CONTENT` |
| Credential | password, secret, api_key, token, cookie, authorization, a segment `key` | `CREDENTIAL_FIELD` |
| Kernel | kernel, ebpf, uprobe, ssl_write, gnutls | `KERNEL_DETAIL_EXCLUDED` |
| Company operations | revenue, pipeline, hubspot, sdr | `COMPANY_OPS_EXCLUDED` |
| Proof claims | slsa, attestation, cluster_verified | `UNSUPPORTED_PROOF_EXCLUDED` |

Attribute values that contain a private-key banner, a cloud key marker, `sk-`, or `api_key=`, `password=`, or `secret=` are `CREDENTIAL_PATTERN_REJECTED`. The value is not returned.

Credential options on the call (`headers`, `authorization`, `apiKey`, `token`, `password`, `secret`, `credentials`) reject the send before the transport runs. The option value is not returned.

## Questions for council

1. Is a sibling package the right boundary, given the mapping document still says `i3_status` `NOT_AUTHORIZED`?
2. Is withholding a mapping-operational record that has no application-supplied trace id, or no positive caller-supplied unix-nano bounds, the right export rule?
3. Is refusing to collapse simultaneous client and instrumentation statuses correct?
4. Is OTLP/HTTP JSON, without the OpenTelemetry SDK and without protobuf, the generic adapter this force asked for?
5. Should metrics and logs stay unimplemented until a mapping version names their labels?
6. Founder decision 12 is still unresolved. Is an explicit in-process enable flag, default off, acceptable while public docs still say Optics does not export OTLP?
7. Are the extra field-name denials stricter than the mapping in a way the council wants to keep?
8. Is a bounded retry without backoff, with at-least-once resend, acceptable?
9. The endpoint is any customer `http` or `https` host. Userinfo, query, and non-trace paths are rejected. Should a later revision also refuse link-local or metadata addresses?
10. Queue default 8 and hard max 32, and 5 attempts hard max, are local bounds. Are those the bounds the council wants recorded?

## Non-goals

This package does not claim SLSA, cluster verification, production verification, or a stable schema. It does not phone a Vantio host. It does not install a fetch patch or set an OpenTelemetry stability opt-in.
