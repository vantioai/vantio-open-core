# Jaeger

Passed command:

```sh
sudo docker start vantio-jaeger
```

The container publishes query `16686`, gRPC `4319`, and HTTP `4320`. Image `jaegertracing/all-in-one:1.62.0`.

After the broker was up, a bound send to `http://127.0.0.1:4320` and to `http://127.0.0.1:4319` was readable at `http://127.0.0.1:16686/api/traces/<trace id>`. The body had schema `1.0.0`, `BLOCK`, the three event kinds, and no canary. The forged marker was absent.

One earlier HTTP attempt returned `ECONNRESET` to the client and Jaeger still stored that trace. Wait until port 4320 accepts connections.
