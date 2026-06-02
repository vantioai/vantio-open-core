-- ============================================================
-- Vantio AI — Migration 002: Policies & Telemetry
-- Run in: Supabase Dashboard → SQL Editor (after 001_initial_schema.sql)
-- ============================================================

-- ------------------------------------------------------------
-- Tier 2: Cloud-managed policy store.
-- One row per tenant. Read by GET /api/v1/config and served to the
-- customer's SDK/CLI, which performs the ACTUAL enforcement client-side
-- (PII redaction, spend caps, host/policy blocking). This table never
-- holds prompt content or PII — it only describes the rules.
-- ------------------------------------------------------------
create table if not exists tenant_policies (
  tenant_id          uuid        primary key references tenants (id) on delete cascade,
  tenant_email       text        not null,
  enforce            boolean     not null default false,
  redact_pii         boolean     not null default false,
  pii_types          text[]      not null default '{}',
  allowed_hosts      text[]      not null default '{}',
  blocked_hosts      text[]      not null default '{}',
  max_request_bytes  bigint      not null default 0,
  spend_cap_usd      numeric     not null default 0,
  updated_at         timestamptz not null default now()
);

create index if not exists tenant_policies_email
  on tenant_policies (tenant_email);

-- ------------------------------------------------------------
-- Lane 1: Anonymous usage telemetry.
-- Written by POST /api/v1/telemetry (no API key, no auth). Strictly
-- anonymous: no tenant FK, no email, no API key, no raw IP, no prompt
-- content, no PII. Only the allowlisted, aggregate counters below.
-- ------------------------------------------------------------
create table if not exists usage_telemetry (
  id              uuid        primary key default gen_random_uuid(),
  anonymous_id    text        not null,
  sdk_version     text,
  cli_version     text,
  runtime         text        not null,   -- 'node' | 'python'
  runtime_version text        not null,
  os              text        not null,
  event           text        not null,   -- 'run' | 'summary'
  hosts           text[]      not null default '{}',
  call_count      integer     not null default 0,
  redacted_count  integer     not null default 0,
  blocked_count   integer     not null default 0,
  framework       text,
  created_at      timestamptz not null default now()
);

create index if not exists usage_telemetry_created_at
  on usage_telemetry (created_at desc);

create index if not exists usage_telemetry_anonymous_id
  on usage_telemetry (anonymous_id);

-- ------------------------------------------------------------
-- Benchmark query support on anomaly_events.
-- 001 already created (tenant_identity, created_at desc). The cross-tenant
-- benchmark aggregates scan by created_at across all tenants, so add a
-- standalone created_at index for the 7-day range scan.
-- ------------------------------------------------------------
create index if not exists anomaly_events_created_at
  on anomaly_events (created_at desc);

-- ------------------------------------------------------------
-- RLS
-- ------------------------------------------------------------
alter table tenant_policies enable row level security;
alter table usage_telemetry enable row level security;

-- Tenant policies: a tenant may read only their own policy row.
create policy "tenant_policies_self_read" on tenant_policies
  for select using (auth.jwt() ->> 'email' = tenant_email);

-- Tenant policies: a tenant may update only their own policy row.
create policy "tenant_policies_self_update" on tenant_policies
  for update using (auth.jwt() ->> 'email' = tenant_email);

-- usage_telemetry: no public/authenticated access. Inserts happen through
-- the service role key (server-side only), which bypasses RLS. With RLS
-- enabled and no permissive policy, anon/authenticated clients get zero rows
-- and cannot insert — exactly what we want for an anonymous, write-only lane.
