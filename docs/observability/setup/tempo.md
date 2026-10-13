# Tempo

Passed command, from the repo root:

```sh
sudo docker compose -p tempo -f deploy/observability/tempo/compose.yaml up -d
```

Image `grafana/tempo:2.7.1`. HTTP is host port `4348`. The query port is `3201`.

After `/ready` returned success, a bound queue that had been held while port `4348` was closed drained into Tempo. The query API returned that same trace id. Tempo returns the trace id as base64.

A paused Tempo container made the sender time out. `POST /v1/traces` on the query port `3201` returned HTTP 404. The sender stayed down and sent 0.

Loki, Prometheus, and Grafana are a separate compose file. See `grafana.md`.
