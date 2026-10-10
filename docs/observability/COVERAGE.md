# Observability coverage

Section 5b is **PASS_SCOPED**, pending a Founder decision on the exclusion below. It is not an unscoped pass. `product_otlp_export_authorized` stays false. This is not a website claim.

This page records the rerun on the current bind. A row that was not closed is GAP. GAP is not a pass. The sentences are lab notes. They are not approved for a website, a registry, or a customer document.

The trust boundary is in `TRUST-BOUNDARY.md`. A co-resident caller can still bind its own object. That residual is open. No outside signature is checked before send.

## Row 5, ten minutes, then the same queue

Nine exporters, closed ports, 10 minutes. 25731 offers. Max offer time 4.792 ms. RSS delta 48533504 bytes, which is inside a 64MB bound. Each queue stayed at 8. Each drop count was 2851. Sent stayed 0. 8 + 2851 = 2859, and 2859 × 9 = 25731. Last errors were `ECONNREFUSED` or `ERR_HTTP2_STREAM_CANCEL`.

The process stayed up. Retries were held until the receiver process was actually up, because a published port accepted connections before `rsyslogd` was running and an earlier send was counted without a log line. `flush({ drain: true })` then sent the queued batches. Each exporter went from sent 0 and queued 8 to sent 8 and queued 0. The same trace id was stored 8 times in the Collector 0.136.0 file, the Collector 0.103.0 file, and the syslog file. Jaeger and Tempo query APIs returned that trace id. The webhook body contained it. That is the buffer that was held during the outage. It is not a later new event.

`resume()` on its own now schedules the next attempt. The ten-minute process called `flush({ drain: true })` after resume. The automatic resume path was unit-tested and was not the process that ran for those ten minutes.

A down receiver still does not block `offer()`. Process exit still drops an unsent queue, because the retry timer does not keep the process alive.

## What else passed on this bind

Local lab only. Not a customer deployment and not a clean-host proof.

| Destination | Rows with evidence | Rows still open |
| --- | --- | --- |
| Collector contrib 0.136.0, file exporter | 1–4 and 10 from the earlier bind rerun. 5 drain above. 6: a slow downstream returned `TIMEOUT` (offer 4.162 ms, sent 0) and a downstream HTTP 500 came back as `HTTP_500` (offer 3.419 ms, sent 0). 7 and 8 from the earlier rerun | 9 is the 0.103.0 image. A killed collector was not a clean mid-flight reset |
| Collector contrib 0.103.0, file exporter, HTTP JSON | 1 schema, 3 BLOCK and three kinds, 4 no canary hit, 5 drain above, 6 paused container `TIMEOUT` in 557 ms with sent 0, 7 below, 10 forged and unbound `UNATTESTED` and the forged marker absent from the file | 2 was not a separate correlation check beyond the shared trio. 8 TLS was not configured. 9 is this image |
| Jaeger 1.62.0 | 5 drain for HTTP and gRPC. 6: paused container `TIMEOUT` (offer 3.970 ms, flush 552.103 ms, sent 0). Query port `16686` returned HTTP 200 and an HTML page. A later send to that port was `HTTP_NOT_OTLP`, sent 0, health down. The body is read, and HTML is not delivery | 1–4 and 10 were not re-scored as a fresh trio on this run. 7, 8, 9 |
| Tempo 2.7.1 | 5 drain. 6: paused container `TIMEOUT` (offer 1.959 ms, flush 550.766 ms). Query port `3201` returned `HTTP_404` (offer 1.372 ms, flush 401.866 ms, sent 0) | 1–4 and 10 were not re-scored as a fresh trio. 7, 8, 9 |
| Loki 3.4.2 | 1 schema `1.0.0` on the labels, 2 one trace id across the three kinds, 3 `vantio_decision=BLOCK` and the policy digest, 4 no canary in the returned labels, 10 no `FORGED-WORKLOAD` in those labels | 5, 6, 7, 8, 9 |
| Prometheus v3.2.1 | Optics exports traces and logs. It does not export an Optics event count. Prometheus scraped the collector's derived span metric `traces_span_metrics_calls_total`. The series named the three span kinds and `vantio_schema_version=1.0.0`. The sample value was 0. The collector log said `normalization for label name "" resulted in empty name` | That row is not an Optics event count. Rows 2–10 of an Optics metric were not run, because there is no Optics metric |
| Grafana 11.5.2 | The datasource proxy returned the Tempo trace with schema `1.0.0` and `BLOCK` and no canary, Loki streams, and the Prometheus series above | 5–9. The UI was not clicked |
| rsyslog on Alpine, TCP 5515 | 5 drain, trace id stored 8 times. 6: paused container `TIMEOUT` (offer 1.428 ms, flush 554.073 ms, sent 0). After unpause, a new send's trace id was in the file | 1–4 and 10 were not re-scored as a fresh trio. 7, 8, 9. The syslog line does not carry the workload id |
| Local webhook | 5 drain. 6: the webhook process waited and returned 500. Offer 1.544 ms, flush ended `TIMEOUT`, health down, sent 0 | 1–4 and 10 were not re-scored here. 7, 8, 9 |
| OpenSearch 2.19.1 | 1–4 and 10 from the host-gateway send. 5: ten minutes, 2977 offers, max offer 3.765 ms, RSS delta 10792960 bytes, queue 8, dropped 2969, sent 0, then drain sent 8 and queued 0. The same trace id and `qdrain-opensearch` were in the index, with no canary hit. 6: paused OpenSearch `TIMEOUT`, offer 1.657 ms, flush 600.291 ms, sent 0. A direct post to port 9200 was `HTTP_400`, sent 0. 7 below. 9: Collector 0.103.0 stored 3 traces and 3 logs when the config used only `http.endpoint` | 8: the security plugin is disabled and port 9200 is plaintext. An https send to that port ended `EPROTO`, sent 0. TLS was not turned on. The 0.136 config key `traces_index` is rejected by Collector 0.103.0 (`invalid keys: traces_index`). Indices were yellow because the replica count is 1 on one node |
| Splunk HEC mock and Datadog mock | Unchanged from the earlier protocol check. Not the products | 5–9 and the products |

Row 7, Collector 0.103.0 HTTP JSON, after the canary check: the loop accepted 1000 events in 1340.2 ms, cpu user 1185636 µs, cpu system 24326 µs, rss delta 6524928 bytes. Total sent on that exporter was 1004, including the trio and one privacy row the allowlist kept. Dropped 0. Health healthy.

Row 7, OpenSearch through Collector 0.136.0, 1000 events: 1918.1 ms, cpu user 1158848 µs, cpu system 24234 µs, rss delta 1679360 bytes, sent 1004 including the trio and one allowlisted privacy row, dropped 0, health healthy. After that run `vantio-traces` had 1021 documents and `vantio-logs` had 1016.

The earlier Collector 0.136.0 file-exporter row 7 number still stands for that image: 1000 events, 1127.8 ms, cpu user 1101708 µs, cpu system 31550 µs, rss delta 16621568 bytes, sent 1000, dropped 0.

In-process projection, 20000 events, from the unit test on this tree: 26832.4 ms, rss delta 16666624 bytes. That is not a collector proof.

## GAP

| Item | Why |
| --- | --- |
| TLS on Jaeger, Tempo, Loki, Prometheus, Grafana, syslog, webhook, OpenSearch, and Collector 0.103.0 | Not configured. OpenSearch port 9200 is plaintext because the security plugin is disabled. An https send there ended `EPROTO` and sent 0. Collector 0.136.0 TLS and mTLS remain the earlier local result |
| Ten-minute drain for Loki, Prometheus, and Grafana | Not run. OpenSearch had its own ten-minute drain. The earlier ten-minute drain covered Collector 0.136.0, Collector 0.103.0, Jaeger, Tempo, syslog, and the webhook |
| Splunk product and Datadog product | Not used |
| Collector process killed mid-request | The container was already gone and the client saw `ECONNREFUSED`. That is not a mid-flight reset |
| A local TCP reset and a local HTTP 200 HTML body | Those were not the Jaeger, Tempo, syslog, or Collector process. Jaeger's own UI port did return HTML with status 200 |
| Response body check | A 2xx response is success. The exporter does not require the body to be OTLP |

## Reviews

Author: Grok 4.7. OTLP review this cycle: Claude Sonnet. It found that `resume()` cleared the retry and did not start it again, and that `suspend()` did not stop later batches of an in-flight send. Both are fixed and covered by unit tests. The ten-minute drain used `flush({ drain: true })`.

## TLS on the final build

Local test CA only. A wrong CA sent 0 and did not deliver.

| Destination | TLS result |
| --- | --- |
| Jaeger 1.62.0 HTTP and gRPC | mTLS. Health healthy, sent 3, schema 1.0.0, BLOCK, no canary, forged marker absent. Wrong CA: HTTP `UNABLE_TO_VERIFY_LEAF_SIGNATURE`, gRPC `ERR_HTTP2_STREAM_CANCEL`, sent 0 |
| Tempo 2.7.1 HTTP | mTLS. Same clean trio. Wrong CA sent 0 |
| Loki 3.4.2 | mTLS on Loki. The collector forwarded logs over that TLS. Query returned schema 1.0.0 and BLOCK, no canary. A direct wrong-CA post sent 0 |
| Webhook | mTLS. Body had schema 1.0.0 and BLOCK, no canary. Wrong CA `SELF_SIGNED_CERT_IN_CHAIN`, sent 0 |
| Syslog | TLS with a client certificate. The new trace id was stored 3 times, including BLOCK. Wrong CA sent 0. The event text was not on a plaintext listener |
| Grafana 11.5.2 | HTTPS health 200. Plaintext HTTP to that port returned 400 |
| Prometheus | mTLS scrape of `vantio_optics_events_sent_total` returned 4. With scrape configs empty, remote-write over TLS returned the same counter at 6 |
| OpenSearch | The process on port 9200 stayed plaintext. The security plugin was not enabled. A local nginx required TLS and a client certificate, then forwarded to that plaintext port. `vantio-traces-tls` and `vantio-logs-tls` stored schema 1.0.0 and BLOCK, no canary. Wrong CA to port 9243 sent 0 |

Jaeger TLS throughput, 300 events: 412 ms, cpu user 393620 µs, cpu system 16234 µs, rss delta 6717440 bytes, sent 300, dropped 0.

Ten minutes on the final build, Jaeger TLS port closed, then mTLS drain: 2979 offers, max offer 5.368 ms, RSS delta 52658176 bytes. Queue 8, dropped 2971, sent 0. 8 + 2971 = 2979. Drain sent 8 and queued 0. The same trace id was in Jaeger. No canary.

## Scoped exclusion

A co-resident caller of the in-process bind is outside this claim, in the same way a hostile root is outside the product. Code in the exporting process that can call the bind can still bind an object it built. Closing that later is a Phantom Engine or Enterprise signature over `canonicalEventBytes`, checked by `checkBeforeSend` before send. The private key stays outside the process. Until that signer is the configured key, `product_otlp_export_authorized` stays false.

Also outside this scoped pass: OpenSearch's own TLS listener, the Splunk product, the Datadog product, and a hostile root or compromised kernel.

The Founder decides whether this scope is accepted. If it is not, section 5b remains NOT_PROVEN.

## Video

HELD. The v7 on-screen text was reviewed. The file was not changed.

"Prompts and completions are never stored." is supported. The export allowlist does not copy prompt or completion text.

"Works with the observability tools you already use." is not supported. It is the only line gated on this integration, and section 5b stays NOT_PROVEN. The co-resident bind is still open: Phantom Engine `main` `6aa18cab` does not sign canonical observability bytes, and the Enterprise optics seal remains a caller-supplied test key. A key in this repository would not close that. `product_otlp_export_authorized` stays false.

No website text was changed.
