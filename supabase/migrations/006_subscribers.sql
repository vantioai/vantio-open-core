-- ============================================================
-- Vantio AI — Migration 006: The Brief subscribers
-- Run in: Supabase Dashboard → SQL Editor (after 005_alert_settings.sql)
-- Idempotent — safe to re-run.
-- ============================================================

-- ------------------------------------------------------------
-- subscribers: email capture for "The Brief" (the SEO blog/insights hub).
-- Written by POST /api/v1/subscribe (no API key, no auth) through the service
-- role key. Stores ONLY the email the visitor volunteers plus a coarse source
-- label — no other PII, no raw IP, no content. Email is stored lower-cased so
-- the UNIQUE constraint dedupes case-insensitively. Mirrors the waitlist table.
-- ------------------------------------------------------------
create table if not exists subscribers (
  id          uuid        primary key default gen_random_uuid(),
  email       text        not null unique,
  source      text,
  created_at  timestamptz not null default now()
);

-- Defense in depth: dedupe case-insensitively at the DB layer too.
create unique index if not exists subscribers_email_lower
  on subscribers (lower(email));

create index if not exists subscribers_created_at
  on subscribers (created_at desc);

-- ------------------------------------------------------------
-- RLS
-- ------------------------------------------------------------
-- No public/authenticated access (like waitlist/usage_telemetry). Inserts and
-- selects happen through the service role key (server-side only), which bypasses
-- RLS. With RLS enabled and NO permissive policy, anon/authenticated clients get
-- zero rows and cannot insert — exactly what we want for a write-only lane.
alter table subscribers enable row level security;
