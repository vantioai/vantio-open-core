-- ============================================================
-- Vantio AI — Supabase Production Schema
-- Run in: Supabase Dashboard → SQL Editor
-- ============================================================

-- Tier 2: SMB tenant registry.
-- Populated by the Stripe checkout.session.completed webhook.
create table if not exists tenants (
  id                           uuid        primary key default gen_random_uuid(),
  email                        text        not null unique,
  tier                         text        not null default 'FREE',  -- 'FREE' | 'PRO' | 'ENTERPRISE'
  stripe_subscription_id       text,
  stripe_checkout_session_id   text,
  api_key                      text unique,
  seats_used                   integer     not null default 1,
  seats_total                  integer     not null default 10,
  created_at                   timestamptz not null default now(),
  updated_at                   timestamptz not null default now()
);

-- Tier 2: Anomaly event ledger.
-- Written by /api/v1/ingest. Zero linguistic content — metadata only.
create table if not exists anomaly_events (
  id               uuid        primary key default gen_random_uuid(),
  tenant_identity  text        not null,
  trace_id         text        not null,
  anomaly_metadata jsonb       not null,   -- bytes_severed, pid, timestamp_ns, target_host, action_taken
  audit_mode       boolean     not null default false,
  created_at       timestamptz not null default now()
);

create index if not exists anomaly_events_tenant_created
  on anomaly_events (tenant_identity, created_at desc);

create index if not exists anomaly_events_trace_id
  on anomaly_events (trace_id);

-- Stripe webhook idempotency log.
-- Prevents at-least-once Stripe delivery from double-processing events.
-- The unique constraint on event_id is the deduplication mechanism.
create table if not exists stripe_processed_events (
  event_id     text        primary key,
  processed_at timestamptz not null default now()
);

-- TTL: purge events older than 30 days to keep the table small.
-- Run periodically: DELETE FROM stripe_processed_events WHERE processed_at < now() - interval '30 days';

-- Tier 3: Enterprise sales leads from /auth/enterprise contact form.
create table if not exists enterprise_leads (
  id         uuid        primary key default gen_random_uuid(),
  name       text        not null,
  email      text        not null,
  company    text        not null,
  team_size  text,
  message    text,
  created_at timestamptz not null default now()
);

-- RLS: enable on all tables.
-- The service role key (used by Next.js server components) bypasses RLS.
-- Authenticated users should only see their own rows.
alter table tenants          enable row level security;
alter table anomaly_events   enable row level security;
alter table enterprise_leads enable row level security;

-- Tenants: a user can only read their own row.
create policy "tenant_self_read" on tenants
  for select using (auth.jwt() ->> 'email' = email);

-- Anomaly events: a user can only read rows matching their email.
create policy "anomaly_events_self_read" on anomaly_events
  for select using (auth.jwt() ->> 'email' = tenant_identity);

-- Enterprise leads: internal only — no direct user access.
-- Reads go through the service role key (server-side) only.
