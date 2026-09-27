# WS7 I2 — versioned semantic mapping

PRIVATE | INERT | NOT SHIPPED | ADAPTERS DISABLED | NO OTLP EXPORTER | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

Machine-readable source: `packages/optics-otel-mapping/mapping/otel-semantic-mapping.json`

`mapping_id` is `WS7-I2`. `mapping_version` is `0`. `schema_status` is `unstable-pre-1.0`. `schema_url` is null.

This page is the design. The package preview shows the same rules and still sets `emitted` to false.

## Upstream pins

Checked on 2026-09-27 against `open-telemetry/semantic-conventions` tag `v1.37.0`.

| Pin | What it is |
| --- | --- |
| `docs/gen-ai/gen-ai-spans.md` at `v1.37.0` (2025-08-25) | Attribute-name pin for GenAI spans. This release renamed `gen_ai.system` to `gen_ai.provider.name`. Content attributes are Opt-In. Stability of those GenAI attributes is Development. The client span table on that page includes `gen_ai.provider.name`, `gen_ai.operation.name`, `error.type`, `server.address`, and `server.port`. |
| `open-telemetry/semantic-conventions` `v1.42.0` (2026-06-12) | Core repository deprecated `gen_ai.*` and moved it to `open-telemetry/semantic-conventions-genai`. |
| Dedicated GenAI repository | No release tag is pinned. The README schema URL section was still TODO. This mapping does not claim that schema URL. |

`http.request.method`, `http.response.status_code`, `url.path`, and `url.scheme` are not on that GenAI span page. This mapping does not cite `docs/gen-ai/gen-ai-spans.md` for them.

| Attribute | Defining document at `v1.37.0` | Span document that cites it |
| --- | --- | --- |
| `http.request.method` | `docs/registry/attributes/http.md` | `docs/http/http-spans.md`, HTTP client and server span tables |
| `http.response.status_code` | `docs/registry/attributes/http.md` | `docs/http/http-spans.md`, HTTP client and server span tables |
| `url.scheme` | `docs/registry/attributes/url.md` | `docs/http/http-spans.md`, HTTP client span table (Opt-In) and HTTP server span table (Required) |
| `url.path` | `docs/registry/attributes/url.md` | `docs/http/http-spans.md`, HTTP server span table (Required). It is not on the HTTP client span table. |

`server.address` and `server.port` are defined in `docs/registry/attributes/server.md` and are on the GenAI client span table. `error.type` is defined in `docs/registry/attributes/error.md` and is on the GenAI client span table. Every name in this section is a candidate only. This package does not emit them.

The public sketch `docs/optics-otel-mapping.md` names `http.request.method`, `url.path`, and `http.response.status_code` as display correspondences. It does not cite the v1.37.0 GenAI span page. This design does not treat that sketch as the citation for those names. The sketch still says Optics does not export OTLP. This package does not add public OTLP support.

## Two source shapes

The mapping does not convert one shape into the other.

| Shape | Where it comes from | What a preview may consider |
| --- | --- | --- |
| `live_display` | CLI display fields in `docs/optics-otel-mapping.md` and `packages/vantio-cli/bin/optics-cx.cjs` | Field candidates only. `would_be_operational_if_i3_enabled` stays false. A live row has no evidence origin, and its `trace_id` is a process-run boundary. |
| `canonical_observation` | PKG-01 / PKG-02 observation fields | Candidates only when `evidence_origin` is `LOCAL_OBSERVATION`. Any other origin yields an empty candidate set. Missing origin is not treated as local. |

`SIMULATED_DEMO`, `TEST_FIXTURE`, `IMPORTED`, `PRODUCT_HEALTH`, and `DERIVED_DIAGNOSTIC` produce an empty candidate set. `PRODUCT_HEALTH` does not fill `gen_ai.provider.name`, `gen_ai.operation.name`, `http.request.method`, `url.path`, or `http.response.status_code`, and it does not set client span status `OK`. `DERIVED_DIAGNOSTIC` does not fill `gen_ai.provider.name`. `would_be_operational_if_i3_enabled` stays false for those origins. `emitted` stays false.

## Status dimensions

Optics keeps two statuses. OpenTelemetry span status is one dimension. This version does not collapse them.

| Stored token | Candidate |
| --- | --- |
| `application_status` `SUCCESS` and HTTP integer 200–399 | Client span status `OK` |
| `application_status` `APPLICATION_ERROR` and HTTP integer 400–599 | Client span status `ERROR`, `error.type` `application_error` |
| `optics_status` `OPTICS_ERROR` | Instrumentation span status `ERROR`, `error.type` `optics_error` |
| `optics_status` `SUCCESS` | No span status. The public sketch maps this token to instrumentation `OK`. Live display still stores it for a recorded call. PKG-02 forbids it as an optimistic default. Mapping version 0 does not copy it. |
| `UNAVAILABLE` | No span status. The public sketch said `ERROR` or unset. This version does not choose either. Null here is not the status code `UNSET`. |
| `NOT_OBSERVED`, `UNSUPPORTED`, `OBSERVED`, `PARTIAL` | No span is created to represent absence, and `PARTIAL` is not collapsed into one HTTP code. |
| Both `APPLICATION_ERROR` and `OPTICS_ERROR` | Neither span status and no `error.type`. The HTTP code, when it is an integer, stays a candidate. |

The stored `ok` boolean is ignored. A string HTTP status is not coerced. `action` `OBSERVED` is not a span status. A `calls` array is not walked.

## Provider name

`gen_ai.provider.name` is a candidate only for `canonical_observation` whose `evidence_origin` is `LOCAL_OBSERVATION`, and only when all of these hold:

- `provider_confidence` is `CATALOG` or `REGIONAL_PATTERN`
- `provider_id` is in the closed crosswalk in the mapping JSON
- the GenAI value is one of the well-known values copied from the v1.37.0 span page

Live `provider` is not promoted. Node `guessProvider` is a substring label. Python catalog resolution is a different label. The evidence contract strips `provider` and does not store that string as `provider_id`.

`google` is unmapped because it does not choose between `gcp.gemini` and `gcp.gen_ai`. `ollama` is unmapped because it is not in the v1.37.0 well-known list. Hostname text never selects the provider name. `azure_openai` maps to `azure.ai.openai` only as a stored `provider_id`, not because a host contains `azure`.

## Operation name

One rule, mapping version 0: method `POST` and path exactly `/v1/chat/completions` correspond to `gen_ai.operation.name` `chat`.

The path must be metadata: it starts with `/`, it is at most 512 characters, and it has no query, fragment, or userinfo. Any other path stays unmapped. The path is not a prompt.

## Destination

| Source | Candidate | Rule |
| --- | --- | --- |
| `destination_host` or live `hostname` | `server.address` | Lowercased DNS or IP literal. Brackets, userinfo, and a machine hostname are refused. |
| `destination_port` | `server.port` | Explicit integer 1–65535. Scheme does not invent 443 or 80. |
| `scheme` | `url.scheme` | `http`, `https`, `ws`, or `wss`. |
| `method` | `http.request.method` | Enum token other than `unknown`. Case is not rewritten. |
| `http_status` or live `httpStatus` | `http.response.status_code` | Integer 100–599 only. |

`url.full` is refused.

## Identity

| Source | Rule |
| --- | --- |
| Live `trace_id` | Never a W3C trace id, including when the characters are 32 hex digits. |
| `run_id` | Not a trace id. |
| Canonical `trace_id` | A trace-context candidate only when `trace_id_basis` is `APPLICATION_SUPPLIED`, the trace id is 32 lowercase hex and not all zeros, and the span id is 16 lowercase hex and not all zeros. An invalid parent span id drops the whole context. |
| `ASSERTED_CONTEXT` | Omitted. Architecture treats it as asserted context, not observation proof. That choice stays `NEEDS_FOUNDER_DECISION`. |
| `session_id` | Not `gen_ai.conversation.id`. |
| `process_id` | Not `process.pid` in this version. |

No candidate is emitted. There is no traceparent writer.

## Refused attributes

These targets have disposition `DO_NOT_MAP`:

- `gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.system_instructions`
- `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`
- `gen_ai.request.model`, `gen_ai.response.model`
- `gen_ai.system`
- `gen_ai.conversation.id`
- `url.full`
- `host.name`
- `process.command`, `process.command_line`

`duration_ms` is a correspondence to span duration only. It is not an attribute. A demo duration of 0 is not a measurement. `clock_quality` is not a span status.

Byte fields never become token counts. Model names are not stored, so they are not inferred from a path or a host.

A preview that sees a prohibited input name drops operational eligibility and does not copy the value into the candidate object.
