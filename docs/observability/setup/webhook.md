# Webhook

Passed command: a local HTTP server on `127.0.0.1:9096` that answers 200, then a bound send with `webhook` set to `http://127.0.0.1:9096/hook`.

The POST body contained schema `1.0.0`, `BLOCK`, the three kinds, and no canary. The forged marker was absent. The OTLP side of that send was a local HTTP sink that returned 200.

No TLS listener was used for this webhook.
