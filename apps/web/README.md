# Vantio AI — Control Plane (`apps/web`)

Next.js 15 App Router application serving the Vantio AI SMB and Enterprise control plane.

## Routes

| Route | Description |
|---|---|
| `/` | Marketing homepage |
| `/pricing` | Three-tier pricing page |
| `/login` | Supabase magic link auth |
| `/dashboard` | Authenticated SMB anomaly event dashboard |
| `/success` | Post-checkout onboarding with API key |
| `/trust` | Compliance & governance |
| `/auth/enterprise` | Enterprise contact (Calendly + form) |
| `/api/v1/ingest` | Edge route — telemetry ingestion (rate limited) |
| `/api/v1/export` | CSV export of anomaly ledger |
| `/api/stripe/create-checkout-session` | Stripe checkout session with 14-day trial |
| `/api/stripe/portal` | Stripe Customer Portal redirect |
| `/api/webhooks/stripe` | Stripe event handler (provision, downgrade, cancel) |
| `/api/webhooks/supabase/anomaly` | Supabase INSERT hook → Slack alert |
| `/api/contact` | Enterprise lead capture → Supabase + Slack |

## Local Development

```bash
cp ../../.env.example .env.local
# fill in values
pnpm dev
```

## Environment Variables

See `../../.env.example` for the full list.
