# Vantio — Governance Platform: Tier Feature Unlock

> Same platform. Higher tiers unlock more governance control — and close residual risk.  
> **Vantio Optics** (Free) → **Vantio Gate** (Pro) → **Vantio Phantom Engine** (Enterprise)

Canonical SoT when both exist: Enterprise root [`PRODUCT_LINEUP.md`](../../PRODUCT_LINEUP.md).

---

## The governance unlock ladder

```
Tier 1 · Free / Vantio Optics ── unlocks ► Observe (Sight Loop)
                                residual ► no block; silent ungoverned paths
Tier 2 · Pro / Vantio Gate ───── unlocks ► + Enforce (rules that stick)
                                residual ► SDK omission · raw sockets · fork escape
Tier 3 · Enterprise / Phantom ─ unlocks ► + Absolute Control (Rogue Reconciliation)
                                closes   ► host evidence + bypass indicators + ledger
```

**Enterprise wedge:** correlated Observe + Enforce + Phantom Engine with **Rogue Reconciliation**. Phantom Engine is the premium lock-down on servers you own.

| Tier | Unlocks | What you see in data |
|------|---------|----------------------|
| **Free · Vantio Optics** | **Observe** · Sight Loop | `OBSERVED` (no enforce) |
| **Pro · Vantio Gate** | **+ Enforce** · rules that stick | Blocks, redactions, caps · `ALLOWED` / `BLOCKED` / `REDACTED` |
| **Enterprise · Phantom Engine** | **+ Absolute Control** · Rogue Reconciliation | Full stack + `BYPASS_INDICATOR` when layers diverge |

---

## Feature layers

### Observe · Vantio Optics (Free tier)
- Free visibility — no paid account required
- Intercepts outbound LLM calls; no code changes needed
- Captures: endpoint, response size, process ID, trace ID — no content, no prompts
- Does **not** block or redact — **observe only** ([fence](./observe-only.md))
- Workflow: **Sight Loop**
- SDK: `@vantio/agent-sdk` (Node.js), `vantio-agent-sdk` (Python)

### Enforce · Vantio Gate (Pro tier unlocks)
- Activates the policy enforcement control plane
- Unlocks: block by hostname, PII redaction, spend/size caps
- Policy lives in the Gate control plane; enforcement runs in the Optics client interceptor
- Workflow: **Rules that stick** (internal id: Policy Latch)
- Dashboard Enforce column shows what the Pro tier's governance actions prevented
- API: `GET /api/v1/config` (policy fetch), `POST /api/v1/ingest` (telemetry)

### Absolute Control · Vantio Phantom Engine (Enterprise tier unlocks)
- Premium host lock-down; closes Gate residual with correlated host evidence + Rogue Reconciliation
- eBPF TLS observe, fork inheritance, CIDR / enrolled-cgroup policy
- Host transmission with no app-layer record → BYPASS_INDICATOR
- Does not replace Pro — Enterprise runs Observe + Enforce + Absolute Control together
- Proof pack: `vantio-phantom-engine/docs/enterprise/`

---

## Tier capability matrix

| Capability | Free (Open Core) | Pro | Enterprise |
|------------|:-----------------:|:---:|:----------:|
| Observe all LLM/agent calls | ✓ | ✓ | ✓ |
| Block by hostname | — | ✓ | ✓ |
| PII redaction | — | ✓ | ✓ |
| Spend / size caps | — | ✓ | ✓ |
| Dashboard: enforcement actions | — | ✓ | ✓ |
| Host / eBPF enforcement | — | — | ✓ |
| Catch beneath the app layer | — | — | ✓ |
| Fork inheritance enforcement | — | — | ✓ |
| CIDR / k8s network policy | — | — | ✓ |

---

## Repos — one feature plane each

| Repo | Layer | Role |
|------|-------|------|
| [`vantioai/vantio-open-core`](https://github.com/vantioai/vantio-open-core) | **Vantio Optics** · Observe | Free-tier visibility; client at every tier |
| [`vantioai/vantio-pro`](https://github.com/vantioai/vantio-pro) | **Vantio Gate** · Enforce | Pro policy control plane |
| [`vantioai/vantio-phantom-engine`](https://github.com/vantioai/vantio-phantom-engine) | **Vantio Phantom Engine** · Absolute Control | Enterprise host lock-down + Rogue Reconciliation |

---

## One-line story

> **Vantio Optics** (Free) → **Vantio Gate** (Pro) → **Vantio Phantom Engine** (Enterprise) — see what agents send, apply the rules you set, lock down on servers you own.
