import type { SupabaseClient } from "@supabase/supabase-js";

// Cross-tenant, ANONYMIZED benchmark aggregates over anomaly_events.
// Shared by GET /api/v1/benchmarks (SDK/CLI) and the dashboard widget so the
// logic lives in one place. No tenant identifiers are ever returned — peer
// figures are only exposed once enough distinct peers exist (k-anonymity).

export interface Benchmarks {
  your_calls_7d:      number | null;
  peer_p50_calls_7d:  number | null;
  peer_p90_calls_7d:  number | null;
  your_block_rate:    number | null;
  peer_block_rate:    number | null;
  top_hosts:          { host: string; share: number }[];
}

interface EventRow {
  tenant_identity: string;
  anomaly_metadata: { target_host?: string | null; action_taken?: string | null } | null;
}

// Minimum distinct peer tenants required before any peer figure is revealed.
const MIN_PEERS = 5;
// Cap rows scanned per benchmark computation.
const SCAN_LIMIT = 50_000;

// Engine health pings — never counted as agent calls (mirrors the dashboard).
const HEALTH_ACTIONS = new Set(["ENGINE_STARTED", "ENGINE_HEARTBEAT"]);
// Legacy violation labels treated as blocks alongside the BLOCKED_* family.
const LEGACY_BLOCKS = new Set(["BLOCKED", "SEVERED", "HARD_DROP", "POLICY_VIOLATION"]);

function isHealth(action: string): boolean {
  return HEALTH_ACTIONS.has(action);
}

function isBlock(action: string): boolean {
  return action.startsWith("BLOCKED") || LEGACY_BLOCKS.has(action);
}

function percentile(sorted: number[], p: number): number | null {
  if (sorted.length === 0) return null;
  if (sorted.length === 1) return sorted[0];
  const idx = Math.ceil((p / 100) * sorted.length) - 1;
  const clamped = Math.min(Math.max(idx, 0), sorted.length - 1);
  return sorted[clamped];
}

const EMPTY: Benchmarks = {
  your_calls_7d:     null,
  peer_p50_calls_7d: null,
  peer_p90_calls_7d: null,
  your_block_rate:   null,
  peer_block_rate:   null,
  top_hosts:         [],
};

export async function computeBenchmarks(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  supabase: SupabaseClient<any, any, any>,
  tenantEmail: string
): Promise<Benchmarks> {
  const since = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();

  const { data, error } = await supabase
    .from("anomaly_events")
    .select("tenant_identity, anomaly_metadata")
    .gte("created_at", since)
    .order("created_at", { ascending: false })
    .limit(SCAN_LIMIT);

  if (error || !data) return { ...EMPTY, your_calls_7d: 0 };

  const rows = data as EventRow[];

  // Per-tenant call/block tallies + global host histogram.
  const calls  = new Map<string, number>();
  const blocks = new Map<string, number>();
  const hostHist = new Map<string, number>();
  let totalHostHits = 0;

  for (const r of rows) {
    const action = (r.anomaly_metadata?.action_taken ?? "").toUpperCase();
    if (isHealth(action)) continue;

    const t = r.tenant_identity;
    calls.set(t, (calls.get(t) ?? 0) + 1);
    if (isBlock(action)) blocks.set(t, (blocks.get(t) ?? 0) + 1);

    const host = r.anomaly_metadata?.target_host;
    if (typeof host === "string" && host.length > 0) {
      hostHist.set(host, (hostHist.get(host) ?? 0) + 1);
      totalHostHits += 1;
    }
  }

  const yourCalls  = calls.get(tenantEmail) ?? 0;
  const yourBlocks = blocks.get(tenantEmail) ?? 0;
  const yourBlockRate =
    yourCalls > 0 ? Number((yourBlocks / yourCalls).toFixed(4)) : null;

  // Peers = every other tenant with at least one call this window.
  const peerCounts: number[] = [];
  let peerCallSum = 0;
  let peerBlockSum = 0;
  for (const [t, c] of calls) {
    if (t === tenantEmail) continue;
    peerCounts.push(c);
    peerCallSum += c;
    peerBlockSum += blocks.get(t) ?? 0;
  }

  // top_hosts are not tenant-identifying, so expose whenever any data exists.
  const topHosts =
    totalHostHits > 0
      ? Array.from(hostHist.entries())
          .sort((a, b) => b[1] - a[1])
          .slice(0, 5)
          .map(([host, n]) => ({ host, share: Number((n / totalHostHits).toFixed(4)) }))
      : [];

  // Suppress peer figures until we have enough peers to stay anonymous.
  if (peerCounts.length < MIN_PEERS) {
    return {
      your_calls_7d:     yourCalls,
      peer_p50_calls_7d: null,
      peer_p90_calls_7d: null,
      your_block_rate:   yourBlockRate,
      peer_block_rate:   null,
      top_hosts:         topHosts,
    };
  }

  const sorted = [...peerCounts].sort((a, b) => a - b);
  return {
    your_calls_7d:     yourCalls,
    peer_p50_calls_7d: percentile(sorted, 50),
    peer_p90_calls_7d: percentile(sorted, 90),
    your_block_rate:   yourBlockRate,
    peer_block_rate:   peerCallSum > 0 ? Number((peerBlockSum / peerCallSum).toFixed(4)) : null,
    top_hosts:         topHosts,
  };
}
