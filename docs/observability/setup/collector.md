# Collector

Local only. The container log must say `Everything is ready` before the send. A send before that can be reset.

Passed command, from the repo root, after `chmod 0777 deploy/observability/collector/out` and empty writable `traces.json` and `logs.json`:

```sh
sudo docker compose -f deploy/observability/collector/compose.yaml up -d
```

Image: `otel/opentelemetry-collector-contrib:0.136.0`.

The rerun then sent with `attestObservation` and the in-process token to `http://127.0.0.1:4318` (JSON and protobuf) and `http://127.0.0.1:4317` (gRPC). The file exporter stored schema `1.0.0`, one trace across `optics.observation`, `phantom.decision`, and `enterprise.evidence`, `BLOCK`, and the policy digest. The files did not contain a canary. An unbound event was refused and its marker was absent.

TLS used `deploy/observability/collector/compose-tls.yaml` with a local test CA. A good CA stored the trace. A missing CA file left health down and a plaintext listener saw 0 connections. mTLS used `compose-mtls.yaml`: a wrong client certificate was reset, and the matching client certificate stored the trace.

Older image `0.103.0` (`deploy/observability/collector/compose-old.yaml`, host port 4418) stored schema `1.0.0` and `BLOCK` once it was ready.

1000 JSON events: 1127.8 ms, cpu user 1101708 µs, cpu system 31550 µs, rss delta 16621568 bytes, sent 1000, dropped 0.

A ten-minute closed-port queue then drained into this file exporter after the log said `Everything is ready`. The same trace id was in the file eight times. Sent went from 0 to 8 and the queue went from 8 to 0.

This is not a production collector deployment.
