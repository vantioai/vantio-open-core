/**
 * Local Optics run-log helpers (read-only).
 * Mirrors ~/.vantio/runs written by `vantio run` / interceptor.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

export function runsDir(root = process.env.VANTIO_HOME || join(homedir(), ".vantio")) {
  return join(root, "runs");
}

export function listRunLogs(dir = runsDir()) {
  let names;
  try {
    names = readdirSync(dir).filter((n) => n.endsWith(".json"));
  } catch {
    return [];
  }

  const entries = [];
  for (const name of names) {
    const path = join(dir, name);
    try {
      const raw = readFileSync(path, "utf8");
      const log = JSON.parse(raw);
      if (log?.vantio_run_log !== "1") continue;
      const st = statSync(path);
      const calls = Array.isArray(log.calls) ? log.calls : [];
      const summary = log.summary || {};
      entries.push({
        path,
        trace_id: log.trace_id || name.replace(/\.json$/, ""),
        pid: log.pid ?? null,
        machine: log.machine ?? null,
        started_at: log.started_at ?? null,
        generated_at: log.generated_at ?? null,
        duration_ms: log.duration_ms ?? null,
        total_calls: summary.total_calls ?? calls.length,
        total_bytes: summary.total_bytes ?? calls.reduce((a, c) => a + (c.bytes || 0), 0),
        hosts: Array.isArray(summary.hosts)
          ? summary.hosts
          : [...new Set(calls.map((c) => c.hostname).filter(Boolean))],
        mtime_ms: st.mtimeMs,
      });
    } catch {
      // skip corrupt
    }
  }

  entries.sort((a, b) => (b.mtime_ms || 0) - (a.mtime_ms || 0));
  return entries;
}

export function loadRun(traceOrPrefix, dir = runsDir()) {
  const entries = listRunLogs(dir);
  if (!entries.length) return { error: "no_runs", message: "No Optics run logs in ~/.vantio/runs/. Run: vantio run <agent>" };

  if (!traceOrPrefix || traceOrPrefix === "latest") {
    return { log: JSON.parse(readFileSync(entries[0].path, "utf8")), path: entries[0].path };
  }

  const needle = String(traceOrPrefix).replace(/^0x/i, "").toLowerCase();
  const matches = entries.filter((e) =>
    String(e.trace_id).toLowerCase().replace(/^0x/, "").includes(needle),
  );
  if (!matches.length) {
    return {
      error: "not_found",
      message: `No run matching '${traceOrPrefix}'. Use optics_list_runs.`,
    };
  }
  if (matches.length > 1 && matches[0].trace_id !== traceOrPrefix) {
    const exact = matches.find((m) => m.trace_id === traceOrPrefix);
    if (!exact) {
      return {
        error: "ambiguous",
        message: `'${traceOrPrefix}' matches ${matches.length} runs. Pass a longer trace_id.`,
        candidates: matches.slice(0, 8).map((m) => m.trace_id),
      };
    }
    return { log: JSON.parse(readFileSync(exact.path, "utf8")), path: exact.path };
  }
  return { log: JSON.parse(readFileSync(matches[0].path, "utf8")), path: matches[0].path };
}

export function proveMarkdown(log) {
  const calls = Array.isArray(log.calls) ? log.calls : [];
  const summary = log.summary || {};
  const totalCalls = summary.total_calls ?? calls.length;
  const totalBytes = summary.total_bytes ?? calls.reduce((a, c) => a + (c.bytes || 0), 0);
  const hosts = Array.isArray(summary.hosts)
    ? summary.hosts
    : [...new Set(calls.map((c) => c.hostname).filter(Boolean))];

  const rows = calls
    .map((c, i) => {
      const act = (c.action || "OBSERVED").toUpperCase();
      return `| ${i + 1} | ${c.hostname || "—"} | ${act} | ${c.bytes ?? "—"} | ${c.ts || "—"} |`;
    })
    .join("\n");

  return [
    "# Vantio Optics — Run Proof",
    "",
    "**Plane:** Observe (Vantio Optics) · **Workflow:** Sight Loop",
    "",
    "> No prompts or completions are captured. Traffic metadata only.",
    "",
    "## Run",
    "",
    `| Field | Value |`,
    `| --- | --- |`,
    `| Trace ID | \`${log.trace_id || "—"}\` |`,
    `| Machine | ${log.machine || "—"} |`,
    `| PID | ${log.pid ?? "—"} |`,
    `| Started | ${log.started_at || "—"} |`,
    `| Duration | ${log.duration_ms != null ? `${log.duration_ms} ms` : "—"} |`,
    `| CLI | ${log.cli_version || "—"} |`,
    "",
    "## Summary",
    "",
    `- Total calls: **${totalCalls}**`,
    `- Total bytes: **${Number(totalBytes).toLocaleString()}**`,
    `- Hosts: ${hosts.length ? hosts.map((h) => `\`${h}\``).join(", ") : "—"}`,
    "",
    "## Calls",
    "",
    "| # | Host | Action | Bytes | Timestamp |",
    "| --- | --- | --- | --- | --- |",
    rows || "| — | — | — | — | — |",
    "",
    "## Residual (honest)",
    "",
    "Optics observes only. Ungoverned paths stay silent. Upgrade to **Vantio Gate** (Policy Latch) to enforce, then **Vantio Phantom Engine** (Bypass Reconciliation) for Absolute Control.",
    "",
    "https://vantio.ai/pricing",
    "",
  ].join("\n");
}

export function discoverLocal(sinceMs = 7 * 24 * 60 * 60 * 1000, dir = runsDir()) {
  const cutoff = Date.now() - sinceMs;
  const hostMap = new Map();

  for (const entry of listRunLogs(dir)) {
    if ((entry.mtime_ms || 0) < cutoff) continue;
    let log;
    try {
      log = JSON.parse(readFileSync(entry.path, "utf8"));
    } catch {
      continue;
    }
    const calls = Array.isArray(log.calls) ? log.calls : [];
    for (const c of calls) {
      const host = c.hostname || "unknown";
      const row = hostMap.get(host) || {
        hostname: host,
        calls: 0,
        observed: 0,
        allowed: 0,
        blocked: 0,
        redacted: 0,
        bytes: 0,
        last_seen: null,
      };
      row.calls += 1;
      row.bytes += c.bytes || 0;
      const act = String(c.action || "OBSERVED").toUpperCase();
      if (act.includes("BLOCK")) row.blocked += 1;
      else if (act.includes("REDACT")) row.redacted += 1;
      else if (act.includes("ALLOW")) row.allowed += 1;
      else row.observed += 1;
      const ts = c.ts || entry.generated_at || entry.started_at;
      if (ts && (!row.last_seen || ts > row.last_seen)) row.last_seen = ts;
      hostMap.set(host, row);
    }
  }

  return [...hostMap.values()].sort((a, b) => b.calls - a.calls);
}

export const UPGRADE_PATH = {
  brand: "Vantio Optics",
  plane: "Observe",
  workflow: "Sight Loop",
  fence: "This MCP is read-only. It cannot block, redact, cap spend, or change policy.",
  next: [
    {
      tier: "Pro",
      brand: "Vantio Gate",
      workflow: "Policy Latch",
      unlocks: "Dry-run → enforce (block / redact / caps), residual-risk report",
      url: "https://vantio.ai/gate",
    },
    {
      tier: "Enterprise",
      brand: "Vantio Phantom Engine",
      workflow: "Bypass Reconciliation",
      unlocks: "Absolute Control, Ring-0 evidence, bypass indicators (patent pending)",
      url: "https://vantio.ai/enterprise",
    },
  ],
  pricing: "https://vantio.ai/pricing",
};
