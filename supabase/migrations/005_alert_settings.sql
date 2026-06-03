-- ============================================================
-- Vantio AI — Migration 005: Per-Tenant Alert Settings
-- Run in: Supabase Dashboard → SQL Editor (after 004_waitlist.sql)
-- Idempotent — safe to re-run.
-- ============================================================

-- ------------------------------------------------------------
-- tenants: per-tenant anomaly alert routing.
-- Each tenant gets THEIR OWN alert destinations so customer anomaly data is
-- never sent to Vantio's shared telemetry/alerts channel. These columns are
-- written through the service-role API (POST /api/v1/alerts) scoped to the
-- caller's own row, and read by the anomaly webhook (service role) and the
-- dashboard.
--   alert_slack_webhook_url — tenant's own Slack incoming webhook (nullable).
--   alert_email             — tenant's own alert email address (nullable).
--   alerts_enabled          — master on/off; defaults true so existing tenants
--                             keep alerting once they set a destination.
-- No new RLS policy is needed: the existing "tenant_self_read" SELECT policy
-- already covers tenant reads of these columns, writes go through the
-- service-role API (which bypasses RLS), and new columns inherit the table's
-- existing grants.
-- ------------------------------------------------------------
alter table tenants add column if not exists alert_slack_webhook_url text;
alter table tenants add column if not exists alert_email             text;
alter table tenants add column if not exists alerts_enabled          boolean not null default true;
