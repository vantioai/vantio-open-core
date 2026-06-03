# Vantio AI — Control Plane (`apps/web`)

Next.js 15 App Router application serving the Vantio AI Pro and Enterprise control plane.

## Routes

| Route | Description |
|---|---|
| `/` | Marketing homepage |
| `/architecture` | Tier 01–03 technical architecture |
| `/pricing` | Three-tier pricing page |
| `/pro` | Tier 02 — Pro ($499/mo) |
| `/enterprise` | Tier 03 — Enterprise |
| `/developers` | Tier 01 — Developer SDK / CLI |
| `/research` | Engineering dossiers |
| `/login` | Supabase magic link auth |
| `/dashboard` | Authenticated Pro anomaly event dashboard |
| `/success` | Post-checkout onboarding with API key |
| `/trust` | Compliance & governance |
| `/privacy`, `/terms` | Legal |
| `/auth/enterprise` | Enterprise contact (Calendly + form) |
| `/api/v1/ingest` | Edge route — telemetry ingestion (rate limited) |
| `/api/v1/export` | CSV export of anomaly ledger |
| `/api/stripe/create-checkout-session` | Stripe checkout session with 14-day trial |
| `/api/stripe/portal` | Stripe Customer Portal redirect |
| `/api/webhooks/stripe` | Stripe event handler (provision, downgrade, cancel) |
| `/api/contact` | Enterprise lead capture → Supabase + Slack |

## Local Development

```bash
cp ../../.env.example .env.local
# fill in values
pnpm dev
```

## Environment Variables

See `../../.env.example` for the full list.
