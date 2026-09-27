# WS7 mapping honesty during the enabled window

PRIVATE | DEFAULT DISABLED | NOT SHIPPED | NO PUBLIC OTLP EXPORT | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

The enabled window calls the existing WS7-I2 preview through `@vantio/optics-otel-i3`. This force does not edit the mapping document.

| Rule | What the harness records |
| --- | --- |
| `PRODUCT_HEALTH` does not fill GenAI or HTTP fields | Candidate keys are empty. The result text has no `gen_ai.provider.name`, `gen_ai.operation.name`, `http.request.method`, `http.response.status_code`, `url.path`, `url.scheme`, `server.address`, or `server.port`. Span client is null. `bytes_sent` is 0. |
| `optics_status` `SUCCESS` does not become span OK | Span client is null. Eligibility status code is 0. The encoded span status code is 0. |
| `application_status` `SUCCESS` without an integer HTTP status does not become span OK | Span client is null. Status code is 0. `http.response.status_code` is absent. |
| Prompts and completions are not token attributes | `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.input.messages`, and `gen_ai.output.messages` are absent. The prompt and completion strings are absent from the result. |
| Live provider and live 32-hex `trace_id` are not OTEL identity | Operational block is `LIVE_DISPLAY_IS_NOT_PROVENANCE`. Trace context is null. Span client is null. The live provider string and the live trace id are absent from the result. |

A local canonical observation with catalog confidence, `application_status` `SUCCESS`, and HTTP 200 still maps to span status OK. That is the WS7-I2 rule for paired application and HTTP evidence. The harness records that accepted attempt separately from the `SUCCESS` cases above.

`would_be_operational_if_i3_enabled` on the mapping preview stays a preview flag. The mapping package export stays `ADAPTERS_DISABLED` during the enabled window.
