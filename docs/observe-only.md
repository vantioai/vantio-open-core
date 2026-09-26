# Observe only — no enforce

**Vantio Optics** (Free) is the **Observe** plane. It sees LLM egress metadata; it never says **no** on its own.

This doc is the Free-tier fence: what Optics does, what it explicitly does not do, and where Phantom Engine and Enterprise sit.

---

## What Optics does (Free)

| Capability | Optics |
|------------|:------:|
| Intercept outbound LLM/agent HTTP calls (Node `vantio run`, Python `@shield`) | ✓ |
| Capture endpoint, response size, PID, trace ID, timestamp | ✓ |
| Terminal visibility + local run logs (`~/.vantio/runs/`) | ✓ |
| Proof export (`vantio prove`) | ✓ |
| Local inspect (`vantio discover --local`) | ✓ |
| Named unsupported-path inventory on this machine | ✓ |
| Privacy non-retention prove (prompt marker must not land in `~/.vantio/runs`) | ✓ |
| Node + Python SDK paths | ✓ |

**Privacy posture:**

- Does **not** capture prompts or completions by default
- Does **not** block, redact, or enforce policy alone
- Free-tier events are labelled **`OBSERVED`** — not `ALLOWED`, `BLOCKED`, or `REDACTED`
- CLI display separates **Optics status** from **Application outcome**. A provider HTTP code is the application outcome. See [Optics to OpenTelemetry](./optics-otel-mapping.md).

---

## What Optics does not do → Phantom Engine Enforce

If it can **change or block** behavior in production, it is **not** Free:

| Out of scope for Optics | Product |
|-------------------------|---------|
| Block by hostname | **Vantio Phantom Engine** (Enforce) |
| PII redaction | Phantom Engine (Enforce) |
| Spend / size caps | Phantom Engine (Enforce) |
| Dry-run → hard enforce | Phantom Engine (Enforce) |
| Policy-as-code publish / rollout | Phantom Engine (Enforce) |
| Shadow AI Discover (fleet-wide) | Phantom Engine |
| Blocking CI gates | Phantom Engine |

**Fence:** if it can say **no** in production → **Vantio Phantom Engine**.

Phantom Engine Enforce workflow: **Rules that stick** — author policy, dry-run, enforce, ledger. Applies where the agent is wired; does not close raw sockets or SDK omission on its own.

> **Note on Gate:** Gate is the internal name for the Enforce function set inside Phantom Engine. The
> `@vantio/gate-mcp` package provides a legacy/compat dry-run evaluation tool. Gate is not a
> current standalone public SKU.

---

## What Optics does not cover → Vantio Phantom Engine ($799/node/mo)

If you need protection on machines you own when a process skips the app wrap:

| Out of scope for Optics alone | Product |
|-------------------------------|---------|
| Host TLS observe on enrolled Linux | **Vantio Phantom Engine** |
| Rogue Reconciliation (host-seen, no app record) | Phantom Engine |
| Fork inheritance on enrolled hosts | Phantom Engine |
| CIDR / enrolled-cgroup egress policy | Phantom Engine |
| Append-oriented audit ledger (Enterprise) | Vantio Enterprise |

**Fence:** Phantom Engine protects Linux hosts you enroll — Observe, Enforce, and Control together, one purchase. It does not claim coverage for agents that never land on that host.

Enterprise workflow: **Rogue Reconciliation** — correlate app + host evidence when they diverge.

---

## Honest gap (by design)

Optics intercepts via Node `fetch`, `undici.fetch`, `undici.request`, `undici.stream` / `pipeline` / `dispatch` / `connect` / `upgrade`, and `http`/`https` (`vantio run`) or Python `shield()` (urllib; requests/httpx/aiohttp when installed). That covers most real agents — and **can be skipped**:

- Native sockets / curl
- Subprocesses not wrapped with `vantio run` / `@shield`
- Runtimes without instrumentation
- Browser paths

**This is not a bug.** Ungoverned paths stay silent:

```
Vantio Optics (see)  →  Vantio Phantom Engine (rules you set + machines you own)
```

Use `vantio discover --local` to inspect what Optics actually saw. The gap between that and full org coverage is named, not hidden.

---

## Quick reference

```bash
# Optics — observe only, no key required
vantio run node agent.js
vantio prove
vantio discover --local

# Phantom Engine — Linux host install (not in this repo)
# See vantio-phantom-engine
```

---

## See also

- [Sight Loop](./sight-loop.md) — the Optics workflow (wrap → capture → inspect)
- [Getting started](./getting-started-tier01.md)
- [Proof artifacts](./prove.md)
