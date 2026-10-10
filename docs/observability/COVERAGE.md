# Observability coverage

This page records what was run. A cell that was not run is GAP. GAP is not a pass.

Claim: observability integration is NOT_PROVEN. `product_otlp_export_authorized` is false.

The binding in `attestSourceRecord` and `attestObservation` copies one object's own data and rejects a different object. It is not a Phantom Engine signature. A co-resident caller of `attestSourceRecord`, or of `createExporter`, can bind an object of its own. A second `startFromConfig` call does not get the first claim. That residual is GAP.

## Unit evidence, repeated

Ran twice on this tree, 0 failures:

- `tests/optics-otel-i3/attestation.test.cjs` plus the i3 http, fields, delivery, and adversarial files. 28 passed, then the attestation file passed again.
- `packages/optics-export/test/export.test.cjs` 11 passed, twice.
- `packages/optics-export/test/exhaustive.test.cjs` 6 passed once on this tree.

| Check | Result |
| --- | --- |
| Enabled export of an unbound `canonical_observation` | Not sent. Result attestation `unattested`. Repeated 3 times inside the test. |
| Copy of a bound object | Not sent. |
| Bound object whose data changes | Not sent. Reason `ATTESTATION_MISMATCH`. Export uses the copy taken at bind time. |
| Caller field `signature` | Not accepted as proof. |
| Caller field `attestation` | Excluded as an unsupported proof field. Not sent. |
| Disabled adapter | Does not send, including a bound record. |
| Second `startFromConfig` | Does not send. |
| Wrong in-process token | Not sent. |
| Prompts, bodies, headers, query strings | Absent from the projection. |
| URL-encoded, base64, and split canaries in exported string fields | Refused or absent from the projection. |
| Remote plaintext | Refused by config. |
| Misconfigured TLS to a local HTTPS server | Send fails. A plaintext listener saw 0 connections. |
| 20_000 in-process projections | Finished. RSS delta stayed under 64MB. This is not a collector throughput proof. |

## Destination matrix

Rows: 1 schema, 2 trace correlation, 3 block plus policy digest, 4 privacy canaries, 5 receiver down 10 minutes with recovery, 6 slow or hostile receiver, 7 throughput, 8 TLS, 9 older collector, 10 forged event.

| Destination | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Exporter against a closed port, three OTLP protocols | GAP | GAP | GAP | GAP | see note | GAP | GAP | GAP | GAP | GAP |
| Collector contrib, this revision | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP |
| Grafana Tempo / Loki / Prometheus | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP |
| Jaeger | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP |
| OpenSearch | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP |
| Splunk product | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP |
| Splunk HEC mock | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP |
| Datadog product | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP |
| Datadog exporter mock | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP |
| syslog | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP |
| webhook | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP | GAP |

Earlier local containers are not evidence for this revision. The send path now requires a source binding those runs did not use. They are not marked pass.

Row 5 note, this revision, exit 0: three exporters (`otlp-http-json`, `otlp-http-protobuf`, `otlp-grpc`) offered to `127.0.0.1:1` for 10 minutes. 8985 offers. Each queue stayed at 8. Each drop count was 2987. 8 + 2987 = 2995, and 2995 × 3 = 8985. Sent stayed 0. Max offer time was 0.932 ms. RSS delta was 37642240 bytes. Final health was `degraded` because a full queue sets that state after the send failure. Recovery was not run: no receiver was started at the end. That cell is not a pass. Syslog, webhook, and every named product stay GAP for row 5.

Row 10 for the in-process adapter is covered by the unit file above. That is not a destination pass.

## Council

Author: Grok 4.7. OTLP review: Claude Sonnet. Gap council: GPT. Both are a different model family from the author.

The review required export of the bound copy, not a later read of the live object. That is what the tests cover. The review's remaining point stands as GAP: a co-resident caller of the bind function is treated as the source. Do not describe that as a ledger signature.
