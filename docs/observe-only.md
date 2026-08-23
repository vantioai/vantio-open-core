# Observe only — no enforce

**Vantio Optics** (Free) is the **Observe** plane. It sees LLM egress metadata; it never says **no** on its own.

This doc is the Free-tier fence: what Optics does, what it explicitly does not do, and where Gate and Phantom Engine sit.

---

## What Optics does (Free)

| Capability | Optics |
|------------|:------:|
| Intercept outbound LLM/agent HTTP calls (Node `vantio run`, Python `@shield`) | ✓ |
| Capture endpoint, response size, PID, trace ID, timestamp | ✓ |
| Terminal visibility + local run logs (`~/.vantio/runs/`) | ✓ |
| Proof export (`vantio prove`) | ✓ |
| Local inspect (`vantio discover --local`) | ✓ |
| Node + Python SDK paths | ✓ |

**Privacy posture:**

- Does **not** capture prompts or completions by default
- Does **not** block, redact, or enforce policy alone
- Free-tier events are labelled **`OBSERVED`** — not `ALLOWED`, `BLOCKED`, or `REDACTED`

---

## What Optics does not do → Vantio Gate ($499)

If it can **change or block** behavior in production, it is **not** Free:

| Out of scope for Optics | Product |
|-------------------------|---------|
| Block by hostname | **Vantio Gate** |
| PII redaction | Gate |
| Spend / size caps | Gate |
| Dry-run → hard enforce | Gate |
| Policy-as-code publish / rollout | Gate |
| Shadow AI Discover (fleet-wide) | Gate |
| Blocking CI gates | Gate |

**Fence:** if it can say **no** in production → **Vantio Gate**.

Gate workflow: **Rules that stick** — author policy, dry-run, enforce, ledger. Gate applies where the agent is wired; it does not close raw sockets or SDK omission.

---

## What Optics does not cover → Vantio Phantom Engine ($799/node)

If you need protection on machines you own when a process skips the app wrap:

| Out of scope for Optics (and Gate alone) | Product |
|------------------------------------------|---------|
| Host TLS observe on enrolled Linux | **Vantio Phantom Engine** |
| Rogue Reconciliation (host-seen, no app record) | Phantom Engine |
| Fork inheritance on enrolled hosts | Phantom Engine |
| CIDR / enrolled-cgroup egress policy | Phantom Engine |
| Append-oriented audit ledger (Enterprise) | Vantio Enterprise |

**Fence:** Phantom Engine protects Linux hosts you enroll — enforce and control together, one purchase. It does not claim coverage for agents that never land on that host.

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
Vantio Optics (see)  →  Vantio Gate (rules you set)  →  Vantio Phantom Engine (machines you own)
```

Use `vantio discover --local` to inspect what Optics actually saw. The gap between that and full org coverage is named, not hidden.

---

## Quick reference

```bash
# Optics — observe only, no key required
vantio run node agent.js
vantio prove
vantio discover --local

# Gate — requires a Gate key + vantio login
vantio login <gate-key>
vantio run node agent.js    # may BLOCK / REDACT when policy is on

# Phantom Engine — Linux host install (not in this repo)
# See vantio-phantom-engine
```

---

## See also

- [Sight Loop](./sight-loop.md) — the Optics workflow (wrap → capture → inspect)
- [Getting started](./getting-started-tier01.md)
- [Proof artifacts](./prove.md)
