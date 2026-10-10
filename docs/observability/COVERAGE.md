# Observability coverage

Observability integration is NOT_PROVEN. `product_otlp_export_authorized` is false.

This page records the rerun on the current bind (`attestObservation` or `attestSourceRecord`, then the in-process token). A row that was not closed on that bind is GAP. GAP is not a pass.

The trust boundary is in `TRUST-BOUNDARY.md`. A co-resident caller of the bind functions can still bind its own object. That residual is open.

## What passed on this bind

Local lab only. Not a customer deployment and not a clean-host proof.

| Destination | Rows with evidence | Rows still open |
| --- | --- | --- |
| Collector contrib 0.136.0, file exporter, HTTP JSON, HTTP protobuf, and gRPC | 1 schema, 2 shared trace, 3 BLOCK plus digest, 4 no canary in the file after the raw-field check, 7 throughput, 8 TLS and mTLS, 10 forged marker absent | 5, 6, 9 is a different image |
| Collector contrib 0.103.0, file exporter, HTTP JSON | 9: a ready collector stored schema 1.0.0 and BLOCK. A cold start in the same session returned ECONNRESET before it was ready | 1–8 and 10 were not re-scored on this image |
| Jaeger 1.62.0, HTTP and gRPC, query API | 1–4 and 10 on the query body after receivers were restored. HTTP also stored a trace on an earlier attempt whose client status was ECONNRESET | 5, 6, 7, 8, 9 |
| Tempo 2.7.1 query API | 1–4 and 10. The hex trace id is returned as base64. Loki, Prometheus, and the Grafana UI were not started | 5, 6, 7, 8, 9, and the rest of the Grafana stack |
| rsyslog on Alpine, TCP 5515 and UDP 5514 | 1–4 and 10 on a warm broker. The first TCP attempt in a cold start missed the trace | 5 buffer flush, 6, 7, 8, 9 |
| Local webhook | 1–4 and 10 | 5 buffer flush, 6 as the webhook process itself, 7, 8, 9 |
| Splunk HEC mock behind Collector 0.136.0 | 1–4 and 10 in the mock log. Protocol only. Not Splunk | 5–9, and the product |
| Datadog exporter mock behind Collector 0.136.0 | 1–4 and 10 in the mock log after the raw-field canary check. API key validation against the mock failed, which is expected. Protocol only. Not Datadog | 5–9, and the product |

Row 6, hostile peer: a local HTTP stand-in returned slowly, returned 500, and reset the socket. The sender stayed up. That stand-in was not the Collector, Jaeger, Tempo, syslog, or webhook process. Those destination rows stay GAP.

Row 5, ten minutes, eight exporters, closed ports: 22984 offers. Each queue stayed at 8. Each drop count was 2865. 8 + 2865 = 2873, and 2873 × 8 = 22984. Sent stayed 0. Max offer time was 4.016 ms. RSS delta was 84135936 bytes, which is over a 64MB bound, so memory is not a pass. The process then exited, so the queued batches were not flushed after the receivers returned. A later new send, after the receivers were started again, reached Collector, Jaeger, Tempo, syslog, and the webhook with schema, BLOCK, no canary, and the forged marker absent. That is a new send. It is not delivery of the ten-minute buffer.

Row 7, Collector HTTP JSON, 1000 events, after the canary check: 1127.8 ms, cpu user 1101708 µs, cpu system 31550 µs, rss delta 16621568 bytes, sent 1000, dropped 0, health healthy.

In-process projection, 20000 events: 26624.7 ms, rss delta 14049280 bytes. That is not a collector proof.

## GAP, no passing command

| Destination | Why |
| --- | --- |
| Grafana UI | Not started |
| Loki | Not started |
| Prometheus | Not started. This exporter does not emit a metric series |
| OpenSearch 2.19.1 | The collector accepted 3 spans and the debug exporter counted them. No OpenSearch document index received them, and the collector log had no elasticsearch error |
| Splunk product | No Splunk container. Mock only |
| Datadog product | No Datadog tenant. Mock only |
| TLS on Jaeger, Tempo, syslog, webhook, HEC, Datadog | Not configured. Collector TLS and mTLS were |
| Older Collector for every row except the one ingest above | Not run |
| Ten-minute buffer flushed into a restored receiver | Not run |

## Reviews

Author: Grok 4.7. OTLP and canary review: Claude Sonnet. The review found that uppercasing a lowercased base64 string does not restore the original text. The exporter now checks the field before it lowercases it. A mixed-case base64 host and path are rejected in unit tests, and the HEC and Datadog mock logs from the send after that check did not contain the canary.
