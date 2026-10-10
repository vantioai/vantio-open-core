# Tempo

Passed command:

```sh
sudo docker run -d --name vantio-tempo \
  -p 4347:4317 -p 4348:4318 -p 3201:3200 \
  -v "$PWD/deploy/observability/tempo/tempo.yaml:/etc/tempo.yaml:ro" \
  grafana/tempo:2.7.1 -config.file=/etc/tempo.yaml
```

A bound send to `http://127.0.0.1:4348` was readable at `http://127.0.0.1:3201/api/traces/<trace id>`. The body had schema `1.0.0`, `BLOCK`, the three kinds, service `vantio-optics`, and no canary. Tempo returns the trace id as base64.

Loki, Prometheus, and the Grafana UI were not started. There is no setup command for them.
