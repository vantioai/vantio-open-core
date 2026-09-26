# Optics fields and OpenTelemetry GenAI terms

This page maps Vantio Optics display fields to OpenTelemetry GenAI semantic conventions. It is documentation only. Optics does not export OTLP, and it does not start a collector, listener, or exporter.

JSON from the CLI includes `"schema_status": "unstable-pre-1.0"`. Names and values below may change without notice.

Prompts and completions are never stored. Do not map Optics records onto `gen_ai.input.messages`, `gen_ai.output.messages`, or any other content attribute.

## Two statuses

| Optics field | Human label | Meaning | OpenTelemetry counterpart |
|---|---|---|---|
| `opticsStatus` | Optics status | Whether Optics completed observation | Status of the instrumentation span, not the model call |
| `applicationStatus` | Application outcome | What the observed application or provider call did | Status of the client span, plus `http.response.status_code` when a response exists |

`applicationStatus` is derived from the stored HTTP status code. A stored `ok` boolean is not used.

## Vocabulary

| Token | Human label | When it is used | OTel sketch |
|---|---|---|---|
| `SUCCESS` | Successful | Observation completed, or the application HTTP status is 200–399 | Span status `OK` |
| `OBSERVED` | Observed | A call was seen. Stored free-tier action labels remain `OBSERVED` | A span exists |
| `NOT_OBSERVED` | Not observed | No call or no run was recorded. Registry latest is this when `vantio status` does not query the registry | No span |
| `UNSUPPORTED` | Unsupported | A supported provider SDK cannot be resolved from the current directory | No client span for that SDK |
| `UNAVAILABLE` | Unavailable | No HTTP status (offline or no response), or a registry check that did not return a version | No `http.response.status_code`. Span status `ERROR` or unset |
| `APPLICATION_ERROR` | Application error | HTTP status 400–599 | Client span status `ERROR`. `http.response.status_code` is the stored code. `error.type` = `application_error` |
| `OPTICS_ERROR` | Optics error | Optics could not read local data, or a wrapped process ended on a signal | Instrumentation span status `ERROR`. `error.type` = `optics_error` |
| `PARTIAL` | Partial | A run contains more than one application outcome | One parent span with mixed child results. Do not collapse those children into a single HTTP code |

## Call metadata

| Optics record | OTel attribute | Note |
|---|---|---|
| `provider` | `gen_ai.provider.name` | Provider label only |
| `method` `POST` and path `/v1/chat/completions` | `gen_ai.operation.name` = `chat`, `http.request.method`, `url.path` | Path is metadata, not a prompt |
| `hostname` | `server.address` | |
| `httpStatus` | `http.response.status_code` | Present only when a numeric HTTP status was stored |
| `bytes` | none | Byte counts are not token counts. Do not invent `gen_ai.usage.input_tokens` |
| `trace_id` | none | An Optics trace id is not a W3C `trace_id` |
| `duration_ms` | span duration | The in-process demo uses a fixed duration of 0 |

## What this page does not add

- No OTLP exporter
- No listener, proxy, or daemon
- No prompt or completion capture
- No change to the paid control-plane path
