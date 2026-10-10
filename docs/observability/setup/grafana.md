# Grafana, Loki, and Prometheus

Local only. On this host, one container could not dial another container's address. The commands below use the published host ports.

Passed command, from the repo root:

```sh
sudo docker compose -p grafana -f deploy/observability/grafana/compose.yaml up -d
```

Images: Grafana `11.5.2`, Loki `3.4.2`, Prometheus `v3.2.1`, Tempo `2.7.1`, Collector contrib `0.136.0`. Loki's ready check returned 503 until it returned 200. The send waited for 200.

A bound send to `http://127.0.0.1:4618` returned health healthy and sent 3. Loki's query API returned three kinds on one trace, including `vantio_decision=BLOCK`, the policy digest, and schema `1.0.0`. The returned labels did not contain a canary. Grafana's datasource proxy returned that Tempo trace with schema `1.0.0` and `BLOCK`, and it returned Loki streams. Prometheus's target `host.docker.internal:8889` was up. Its query API, and Grafana's proxy to that API, returned `traces_span_metrics_calls_total` for `optics.observation`, `phantom.decision`, and `enterprise.evidence` with `vantio_schema_version=1.0.0`. The sample value was 0.

The collector log also said `normalization for label name "" resulted in empty name` while building the Prometheus exporter. That series is a collector span metric. It is not an Optics metric endpoint.
