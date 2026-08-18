# Observe only — no enforce

**Vantio Optics** (Free · Open Core) is the **Observe** plane. It sees LLM egress metadata; it never says **no** on its own.

This doc is the Free-tier fence: what Optics does, what it explicitly does not do, and where enforcement lives.

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

**Privacy posture (product truth):**

- Does **not** capture prompts or completions by default
- Does **not** block, redact, or enforce policy alone
- Free-tier events are labelled **`OBSERVED`** — not `ALLOWED`, `BLOCKED`, or `REDACTED`

---

## What Optics does not do → Vantio Gate (Pro)

If it can **change or block** behavior in production, it is **not** Free:

| Out of scope for Optics | Tier |
|-------------------------|------|
| Block by hostname | Pro · **Vantio Gate** |
| PII redaction | Pro |
| Spend / size caps | Pro |
| Dry-run → hard enforce | Pro |
| Policy-as-code publish / rollout | Pro |
| Shadow AI Discover (fleet-wide) | Pro |
| Blocking CI gates | Pro |

**Fence:** if it can say **no** in production → **Vantio Gate**.

Pro workflow: [**Rules that stick**](https://github.com/vantioai/vantio-pro) — author policy, dry-run, enforce, ledger.

---

## What Optics does not guarantee → Vantio Phantom Engine (Enterprise)

If the org must **guarantee** control when engineers route around the interceptor:

| Out of scope for Optics (and Pro alone) | Tier |
|----------------------------------------|------|
| Host TLS observe (eBPF) | Enterprise · **Vantio Phantom Engine** |
| Rogue Reconciliation (host ∧ ¬ app record) | Enterprise |
| Fork inheritance proof | Enterprise |
| CIDR / enrolled-cgroup host egress policy | Enterprise |
| Append-oriented durable ledger | Enterprise |

**Fence:** if bypass must be **proven closed** → **Vantio Phantom Engine** (premium).

Enterprise workflow: **Rogue Reconciliation** — correlate app + host evidence, surface `BYPASS_INDICATOR`.

---

## Honest residual (by design)

Optics intercepts via in-process `fetch` patching (Node) or SDK hooks (Python). That covers most real agents — and paths that skip it leave no Optics record:

- Native sockets without `fetch`
- Subprocesses not wrapped with `vantio run` / `@shield`
- Runtimes without instrumentation

That residual is the upgrade cue:

```
Vantio Optics (see)  →  Vantio Gate (enforce)  →  Vantio Phantom Engine (host lock-down + Rogue Reconciliation)
```

Use `vantio discover --local` to inspect what Optics actually saw. The gap between that and full org coverage is residual risk — documented, not hidden.

---

## Quick reference

```bash
# Optics — observe only, no key required
vantio run node agent.js
vantio prove
vantio discover --local

# Gate — requires Pro key + vantio login (enforcement unlocked)
vantio login <pro-key>
vantio run node agent.js    # may BLOCK / REDACT when policy is enforced

# Phantom Engine — Enterprise deployment (not in this repo)
# See vantio-phantom-engine for host Control
```

---

## See also

- [Sight Loop](./sight-loop.md) — the Optics workflow (wrap → capture → inspect → residual)
- [Getting started](./getting-started-tier01.md)
- [Prove artifacts](./prove.md)
