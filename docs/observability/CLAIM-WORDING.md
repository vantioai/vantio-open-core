# Claim wording

Program claim: observability integration is NOT_PROVEN.

`product_otlp_export_authorized` stays false. Do not publish a destination claim from this packet. The video stays HELD. The line-by-line video claim review is blocked pending the source file.

The sentences below are the only wordings that match the lab runs. They are not approved for a website, a registry, or a customer document.

| Level | Wording |
| --- | --- |
| Program | Observability integration is not proven. |
| Collector 0.136.0 | On one lab host, a bound queue held for ten minutes while the port was closed then drained into the Collector file exporter. The same trace id was in the file. Offer stayed under 5 ms. A slow downstream and an HTTP 500 from that Collector left the sender down and sent nothing. This is not a production collector deployment. |
| Collector 0.103.0 | On one lab host, after the process was ready, HTTP JSON stored schema 1.0.0, a block record, and the three event kinds. The ten-minute queue drained into that file. A paused container made the sender time out. 1000 further events were accepted in 1340.2 ms. |
| Jaeger 1.62.0 | On one lab host, the ten-minute queue drained into Jaeger over HTTP and gRPC, and the query API returned that trace. A paused Jaeger made the sender time out. The Jaeger UI port returned HTML with HTTP 200, and the exporter treated the status as success. |
| Tempo 2.7.1 | On one lab host, the ten-minute queue drained into Tempo and the query API returned that trace. A paused Tempo made the sender time out. The query port returned HTTP 404 and the sender sent nothing. |
| Loki 3.4.2 | On one lab host, Loki stored the three event kinds on one trace, including a block decision, the policy digest, and schema 1.0.0. The returned labels had no canary. |
| Prometheus | On one lab host, Prometheus scraped a collector span metric named for the three event kinds with schema 1.0.0. The sample value was 0. That is not an Optics metric endpoint and it is not an event count. |
| Grafana 11.5.2 | On one lab host, Grafana's datasource proxy returned the Tempo trace, Loki streams, and that Prometheus series. The UI was not used. |
| Syslog | On one lab host, rsyslog stored the ten-minute queue's trace id over TCP. A paused rsyslog made the sender time out. The line does not include the workload id. |
| Webhook | On one lab host, the webhook that had been down received the ten-minute queue. A webhook that waited and returned 500 made the sender time out and sent nothing. |
| OpenSearch 2.19.1 | On one lab host, OpenSearch stored schema 1.0.0, a block record, and the three event kinds in `vantio-traces` and `vantio-logs`. The documents had no canary. The indices were yellow on one node. |
| Splunk | Not product-verified. A local HEC mock behind the Collector received a bound record on an earlier run. |
| Datadog | Not product-verified. A local Datadog-exporter mock received a bound record on an earlier run. The mock rejected the dummy key check. |
| Forged event | An unbound object was not sent. A co-resident caller that can call the bind function is still inside the process. That is not a Phantom Engine signature. |

## Video

HELD. The line-by-line review is blocked pending the source file. No video, script, or caption file was found, so there is no line to mark supported or unsupported.

Looked in:

- `vantioai/vantio-app` branch `cursor/vantio-web-next-main`, `public/` (icons, logos, `llms.txt`; no video) and `content/updates/` (markdown only)
- GitHub code search for captions, vtt, srt, and mp4 under `vantioai/vantio-app`, and for higgsfield or a marketing video under `org:vantioai` (no code hits)
- This repository has no marketing video

No website text was changed.
