# Claim wording

Program claim: observability integration is NOT_PROVEN.

`product_otlp_export_authorized` stays false. Do not publish a destination claim from this packet. The video stays HELD.

The sentences below are the only wordings that match this lab rerun. They are not approved for a website, a registry, or a customer document.

| Level | Wording |
| --- | --- |
| Program | Observability integration is not proven. |
| Collector 0.136.0, local file exporter | On one lab host, a bound export stored schema 1.0.0, a shared trace, a block record, and a policy digest in the Collector file exporter over HTTP JSON, HTTP protobuf, and gRPC. Canaries used in that run were absent from those files. TLS and mTLS to that local Collector failed closed when the certificate did not match. This is not a production collector deployment. |
| Collector 0.103.0 | On one lab host, after the process was ready, HTTP JSON to Collector 0.103.0 stored schema 1.0.0 and a block record. |
| Jaeger 1.62.0 | On one lab host, Jaeger's query API returned that bound trace for HTTP and gRPC, including the block record, with no canary from that run in the body. |
| Tempo 2.7.1 | On one lab host, Tempo's query API returned that bound trace. Loki, Prometheus, and Grafana were not part of the run. |
| Syslog | On one lab host, rsyslog stored the bound record over TCP and UDP, with no canary from that run in the file. |
| Webhook | On one lab host, a local webhook stored the bound record, with no canary from that run in the body. |
| Splunk | Not product-verified. A local HEC mock behind the Collector received the bound record. |
| Datadog | Not product-verified. A local Datadog-exporter mock received the bound record. The mock rejected the dummy key check. |
| OpenSearch | Not proven. The Collector accepted the export and no document index showed it. |
| Forged event | An unbound object was not sent. A co-resident caller that can call the bind function is still inside the process. That is not a Phantom Engine signature. |

## Video

HELD. No line-by-line review is possible because no video, script, or caption file was found.

Looked in:

- `vantioai/vantio-app` branch `cursor/vantio-web-next-main`, `public/` (icons, logos, `llms.txt`; no video) and `content/updates/` (markdown only)
- GitHub code search for captions, vtt, srt, and mp4 under `vantioai/vantio-app`, and for higgsfield or a marketing video under `org:vantioai` (no code hits)
- This repository has no marketing video

No website text was changed.
