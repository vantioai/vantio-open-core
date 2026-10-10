# Observability export schema 1.0.0

Schema id: `vantio.observability.export`

Status: candidate. Not a registry release. Not a clean-host proof.

Optics observes. This schema does not enforce. A `phantom.decision` value is a record of a decision made elsewhere. Exporting it does not block or allow a call.

## Versioning

Major version 1 accepts only additive changes. A reader of major 1 ignores unknown attributes. A breaking change requires schema `2.0.0` and a deprecation window of two minor releases of this exporter, during which 1.x events are still produced and accepted.

## Fields

| Field | OTel name when it fits | Rule |
| --- | --- | --- |
| Destination host | `server.address` | DNS name only |
| Destination port | `server.port` | Integer 1–65535 |
| Process | `process.pid`, `process.executable.name` | Executable is a basename |
| Lineage | `vantio.process.lineage` | Up to 16 pid and basename pairs |
| Bytes | `vantio.bytes.request`, `vantio.bytes.response` | Counts. Null stays null |
| Timing | span start and end, `vantio.duration_ms` | Milliseconds |
| Status | `http.response.status_code`, `vantio.optics.status`, `vantio.application.status` | Codes and tokens |
| Trace context | `traceId`, `spanId` | 16-byte and 8-byte hex |
| Workload | `vantio.workload.id` | Opaque, length-capped |
| Coverage | `vantio.coverage.state` | `OBSERVED`, `NOT_OBSERVED`, `PARTIAL`, `UNSUPPORTED`, `UNKNOWN` |
| Decision | `vantio.decision` | `ALLOW` or `BLOCK` on a phantom decision record |
| Policy | `vantio.policy.digest` | `sha256:` plus 64 hex characters. Required for phantom and enterprise records |
| Schema | `vantio.schema.id`, `vantio.schema.version` | This document |

Prompts, completions, request bodies, response bodies, headers, and query strings are not fields. A path is stored only with `?` and `#` removed. Events that still contain a canary token after projection are dropped.

An event is sent only after `attestObservation` binds that object in this process. A copy, or an object that was never bound, is rejected with `UNATTESTED` and is not sent. The binding is not a Phantom Engine signature. A caller who can invoke `attestObservation` is the source for that object.

The OTLP attribute `vantio.attestation` is the label `in-process`. It is not a signature a receiver can verify.

## Transports

OTLP HTTP/JSON, OTLP HTTP/protobuf, and OTLP gRPC use the same projected event. JSON Lines, RFC 5424 syslog, and webhook use that event too. Nothing is sent unless a config file enables export. Remote plaintext is refused. TLS does not fall back to plaintext.
