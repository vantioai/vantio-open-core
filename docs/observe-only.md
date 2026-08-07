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

Pro workflow: [**Policy Latch**](https://github.com/vantioai/vantio-pro) — author policy, dry-run, latch enforce, ledger.

---

## What Optics does not guarantee → Vantio Phantom Engine (Enterprise)

If the org must **guarantee** control when engineers route around the interceptor:

| Out of scope for Optics (and Pro alone) | Tier |
|----------------------------------------|------|
| eBPF TLS observe at Ring-0 | Enterprise · **Vantio Phantom Engine** |
| Rogue Reconciliation (kernel ∧ ¬ app record) | Enterprise |
| Fork inheritance proof | Enterprise |
| CIDR / enrolled-cgroup kernel egress policy | Enterprise |
| Append-oriented regulator-grade ledger | Enterprise |

**Fence:** if bypass must be **proven closed** → **Vantio Phantom Engine**.

Enterprise workflow: **Rogue Reconciliation** — correlate app + kernel evidence, surface `BYPASS_INDICATOR`.

---

## Honest residual (by design)

Optics intercepts via in-process `fetch` patching (Node) or SDK hooks (Python). That covers most real agents — and **can be bypassed**:

- Native sockets without `fetch`
- Subprocesses not wrapped with `vantio run` / `@shield`
- Runtimes without instrumentation

**This is not a bug.** Silent ungoverned paths are the upgrade cue:

```
Vantio Optics (see)  →  Vantio Gate (enforce)  →  Vantio Phantom Engine (prove bypass closed)
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
vantio run node agent.js    # may BLOCK / REDACT when policy latched

# Phantom Engine — Enterprise deployment (not in this repo)
# See vantio-phantom-engine for Ring-0 plane
```

---

## See also

- [Sight Loop](./sight-loop.md) — the Optics workflow (wrap → capture → inspect → residual)
- [Getting started](./getting-started-tier01.md)
- [Prove artifacts](./prove.md)
