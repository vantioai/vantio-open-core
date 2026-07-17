# Outbound webhooks (distribution stub)

Push governance signals to ops tools (Slack, n8n, Zapier, PagerDuty) without
expanding the data plane.

## Events worth forwarding

| Event | Source | Payload (metadata only) |
|-------|--------|-------------------------|
| `optics.run_completed` | Local prove / CLI | trace_id, hosts, bytes, duration |
| `gate.dry_run_blocked` | Pro ingest `DRY_RUN_*` | host, action, policy version |
| `gate.enforcement_gap` | Pro residual-risk | gap_type, host |
| `gate.blocked` | Pro live latch | host, action |

**Never** include prompts or completions.

## Pattern (today)

1. Agent runs under `vantio run` (Optics) or Gate.
2. Events land in Pro via `POST /api/v1/ingest` (existing).
3. A small worker polls `GET /api/v1/residual-risk` (or tails NDJSON) and POSTs to your webhook URL.

```bash
# Pseudocode poller
curl -sH "x-vantio-identity: $VANTIO_API_KEY" \
  "$VANTIO_API_BASE/api/v1/residual-risk" \
| jq -c '.enforcement_gaps[]' \
| while read -r row; do
    curl -sX POST "$WEBHOOK_URL" -H 'content-type: application/json' -d "$row"
  done
```

## n8n / Zapier

- Trigger: Webhook (POST)
- Filter: `action_taken` starts with `DRY_RUN_` or equals `ENFORCEMENT_GAP`
- Action: Slack / ticket / email

## Roadmap (earmarked)

Native `POST` outbound webhooks from Pro (signed, retry, secret) — see [surfaces.md](./surfaces.md) deeper platform list. Until then, use the poller pattern above.
