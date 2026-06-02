-- ============================================================
-- Vantio AI — Migration 003: Security Hardening
-- Run in: Supabase Dashboard → SQL Editor (after 002_policies_and_telemetry.sql)
-- Idempotent — safe to re-run.
-- ============================================================

-- ------------------------------------------------------------
-- stripe_processed_events: enable RLS (was missing in 001).
-- This is the Stripe webhook idempotency log. It is written/read only by the
-- service role key (server-side), which bypasses RLS. Without RLS the public
-- anon key could read/insert/delete rows and tamper with idempotency dedup.
-- Like usage_telemetry, we enable RLS with NO permissive policy: anon and
-- authenticated clients get zero access; only the service role can touch it.
-- ------------------------------------------------------------
alter table stripe_processed_events enable row level security;

-- ------------------------------------------------------------
-- tenant_policies: remove the self-UPDATE policy.
-- All real policy writes go through POST /api/v1/policy using the service role
-- key (which bypasses RLS), so a direct-write grant is unnecessary. It was also
-- unsafe: a USING-only UPDATE policy (no WITH CHECK) let an authenticated user
-- repoint tenant_id / tenant_email to another tenant. Drop it; the self-READ
-- policy ("tenant_policies_self_read") is intentionally kept intact.
-- Writes remain service-role-only via the API.
-- ------------------------------------------------------------
drop policy if exists "tenant_policies_self_update" on tenant_policies;
