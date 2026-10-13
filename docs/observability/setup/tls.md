# TLS

Local test CA only. These commands passed on one lab host. A wrong CA sent 0.

Jaeger 1.62.0, mTLS on OTLP HTTP `4320` and gRPC `4319`:

```sh
sudo docker run -d --name vantio-jaeger-tls \
  -p 4320:4318 -p 4319:4317 -p 16686:16686 \
  -v /tmp/vantio-matrix/certs:/certs:ro \
  jaegertracing/all-in-one:1.62.0 \
  --collector.otlp.http.tls.enabled=true \
  --collector.otlp.http.tls.cert=/certs/server.pem \
  --collector.otlp.http.tls.key=/certs/server.key \
  --collector.otlp.http.tls.client-ca=/certs/ca.pem \
  --collector.otlp.grpc.tls.enabled=true \
  --collector.otlp.grpc.tls.cert=/certs/server.pem \
  --collector.otlp.grpc.tls.key=/certs/server.key \
  --collector.otlp.grpc.tls.client-ca=/certs/ca.pem
```

Tempo 2.7.1 used `deploy/observability/tempo/tempo-tls.yaml` with the same CA. Loki 3.4.2 used `deploy/observability/grafana/loki-tls.yaml`. The webhook and the Optics event counter used a local HTTPS server that required a client certificate. Syslog used `vantio-rsyslog-tls:local` and `deploy/observability/rsyslog/rsyslog.tls.conf`. Grafana 11.5.2 used `GF_SERVER_PROTOCOL=https`. Prometheus v3.2.1 scraped and received remote write on HTTPS with client certificates. The counter was `vantio_optics_events_sent_total`.

OpenSearch 2.19.1 on port 9200 stayed plaintext. nginx 1.27 terminated TLS on port 9243 with `deploy/observability/opensearch/nginx-tls.conf` and forwarded to that port. The collector then wrote `vantio-traces-tls` and `vantio-logs-tls`.
