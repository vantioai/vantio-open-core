# Jaeger

Passed command, from the repo root:

```sh
sudo docker compose -p jaeger -f deploy/observability/jaeger/compose.yaml up -d
```

Image `jaegertracing/all-in-one:1.62.0`. Query is host port `16686`, gRPC `4319`, HTTP `4320`.

After the process was up, a bound queue that had been held while those ports were closed drained into Jaeger. The query API for that same trace id returned the trace. The body had the workload id from the queued event. An unbound object was not part of that queue.

A later paused container made the sender time out. Port `16686` answered `POST /v1/traces` with HTTP 200 and an HTML page. The exporter treated that status as success and did not read the HTML.
