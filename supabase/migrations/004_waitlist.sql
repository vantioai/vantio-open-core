-- ============================================================
-- Vantio AI — Migration 004: Tier 2 Waitlist
-- Run in: Supabase Dashboard → SQL Editor (after 003_security_hardening.sql)
-- Idempotent — safe to re-run.
-- ============================================================

-- ------------------------------------------------------------
-- waitlist: Tier 2 (Pro) interest capture while the public purchase flow is
-- disabled (waitlist-only until billing/Stripe is live). Written by
-- POST /api/v1/waitlist (no API key, no auth) through the service role key.
-- Stores ONLY the email the visitor volunteers, a coarse source label, and
-- coarse metadata — no other PII, no raw IP, no prompt content. Email is stored
-- lower-cased so the UNIQUE constraint dedupes case-insensitively.
-- ------------------------------------------------------------
create table if not exists waitlist (
  id          uuid        primary key default gen_random_uuid(),
  email       text        not null unique,
  source      text,
  metadata    jsonb       not null default '{}',
  created_at  timestamptz not null default now()
);

-- Defense in depth: also dedupe case-insensitively at the DB layer even if a
-- caller forgets to lower-case before insert.
create unique index if not exists waitlist_email_lower
  on waitlist (lower(email));

create index if not exists waitlist_created_at
  on waitlist (created_at desc);

-- ------------------------------------------------------------
-- RLS
-- ------------------------------------------------------------
-- No public/authenticated access (like usage_telemetry). Inserts and selects
-- happen through the service role key (server-side only), which bypasses RLS.
-- With RLS enabled and NO permissive policy, anon/authenticated clients get
-- zero rows and cannot insert — exactly what we want for a write-only lane.
alter table waitlist enable row level security;
