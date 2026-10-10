# OpenSearch

Local only. Container-to-container dials on this host timed out. The collector reaches OpenSearch through the published host port.

Passed command, from the repo root:

```sh
sudo docker compose -p opensearch -f deploy/observability/opensearch/compose.yaml up -d
```

OpenSearch is `opensearchproject/opensearch:2.19.1` with the security plugin disabled, `network.host` `0.0.0.0`, and `-Djava.net.preferIPv4Stack=true`. Without the IPv4 flag the process listened on IPv6 only. The collector is `otel/opentelemetry-collector-contrib:0.136.0` and its OpenSearch exporter posts to `http://host.docker.internal:9200`.

After `http://127.0.0.1:9200` answered, a bound send to `http://127.0.0.1:4518` returned health healthy and sent 3. Indices `vantio-traces` and `vantio-logs` each had 4 documents. The documents included schema `1.0.0`, `BLOCK`, `phantom.decision`, `enterprise.evidence`, and `optics.observation`. A search of those documents did not contain a canary or `FORGED-WORKLOAD`. The indices were yellow because the replica count is 1 on one node.

An earlier config used the elasticsearch exporter and `http://opensearch:9200`. The collector accepted the spans, no document index appeared, and that dial later failed with `dial tcp 172.20.0.2:9200: i/o timeout`.
