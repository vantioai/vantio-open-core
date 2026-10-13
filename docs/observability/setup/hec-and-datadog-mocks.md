# HEC and Datadog mocks

These are local HTTP mocks behind Collector `0.136.0`. They are not Splunk and not Datadog.

Passed sequence, after the collector log says `Everything is ready`:

```sh
node deploy/observability/matrix/mock.mjs /tmp/vantio-matrix/hec.jsonl 8088
node deploy/observability/matrix/mock.mjs /tmp/vantio-matrix/datadog.jsonl 8089
sudo docker compose -f deploy/observability/fanout/compose.yaml up -d
```

A bound send to `http://127.0.0.1:4328` then appeared in both mock logs with schema `1.0.0`, `BLOCK`, `enterprise.evidence`, and no canary. The Datadog exporter's API key check against the mock failed. The key in the compose file is 32 hex zeros so the process can start. It is not a credential.

A send before the collector log says ready can be reset and leave the mocks empty.
