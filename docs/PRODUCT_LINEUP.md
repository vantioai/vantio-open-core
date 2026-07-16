# Vantio — Governance Platform: Tier Feature Unlock

> Same platform. Higher tiers unlock more governance control.
> This is the canonical tier model. All READMEs, docs, and dashboard copy derive from this file.

---

## The governance unlock ladder

Vantio is **one platform** with a layered governance architecture. Each tier unlocks the next control plane — you don't swap products, you gain more enforcement authority.

```
Tier 1 · Free / Open Core ────── unlocks ► Observe
Tier 2 · Pro ─────────────────── unlocks ► + Enforce   (includes Tier 1)
Tier 3 · Enterprise ───────────── unlocks ► + Absolute Control   (includes Tier 1 + 2)
```

Enterprise = all three feature layers active simultaneously. The Mission Control dashboard shows all three columns because all three governance layers are running — not because three products compete to claim the event.

| Tier | Unlocks | What you see in data |
|------|---------|----------------------|
| **Free · Open Core** | **Observe** — governance visibility | ALLOWED / observed events for every LLM/agent call |
| **Pro** | **+ Enforce** — block, redact, caps | Enforce column: governance actions Pro enables |
| **Enterprise** | **+ Absolute Control** — Phantom Engine kernel eBPF | Full stack: Observe + Enforce + kernel-decisive events |

---

## Feature layers

### Observe · Open Core (Free tier)
- The base governance layer — no paid account required to start
- Intercepts every outbound LLM call; no code changes needed
- Captures: endpoint, response size, process ID, trace ID — no content, no prompts
- Does **not** block or redact — those require the Enforce layer (Pro)
- SDK: `@vantio/agent-sdk` (Node.js), `vantio-agent-sdk` (Python)

### Enforce · Pro (Pro tier unlocks)
- Activates the policy enforcement control plane
- Unlocks: block by hostname, PII redaction, spend/size caps
- Policy lives in the Pro control plane; enforcement runs in the Open Core client interceptor
- Dashboard Enforce column shows what the Pro tier's governance actions prevented
- API: `GET /api/v1/config` (policy fetch), `POST /api/v1/ingest` (telemetry)

### Absolute Control · Phantom Engine (Enterprise tier unlocks)
- Kernel enforcement layer — deployed as Linux daemon or Kubernetes DaemonSet
- eBPF uprobes on TLS libraries (`SSL_write`, `gnutls_record_send`) at Ring-0
- Enforcement is inescapable: sits beneath the application layer, below any bypass
- Fork inheritance: child processes cannot escape trace context
- Adds the unbypassable kernel guarantee beneath the Pro HTTP contract
- Enterprise includes all lower tiers: Observe + Enforce + Absolute Control all active

---

## Tier capability matrix

| Capability | Free (Open Core) | Pro | Enterprise |
|------------|:-----------------:|:---:|:----------:|
| Observe all LLM/agent calls | ✓ | ✓ | ✓ |
| Block by hostname | — | ✓ | ✓ |
| PII redaction | — | ✓ | ✓ |
| Spend / size caps | — | ✓ | ✓ |
| Dashboard: enforcement actions | — | ✓ | ✓ |
| eBPF / kernel enforcement | — | — | ✓ |
| Inescapable catch (below app layer) | — | — | ✓ |
| Fork inheritance enforcement | — | — | ✓ |
| CIDR / k8s network policy | — | — | ✓ |

---

## Repos — one feature plane each

| Repo | Layer | Role |
|------|-------|------|
| [`vantioai/vantio-open-core`](https://github.com/vantioai/vantio-open-core) | **Observe** | Free-tier governance visibility; the client that runs in every tier |
| [`vantioai/vantio-pro`](https://github.com/vantioai/vantio-pro) | **Enforce** | Pro-tier policy control plane; tells Open Core what to enforce |
| [`vantioai/vantio-phantom-engine`](https://github.com/vantioai/vantio-phantom-engine) | **Absolute Control** | Enterprise-tier kernel layer; the inescapable enforcement guarantee |

---

## One-line story

> **Vantio tiers unlock governance: Observe free · Enforce with Pro · Absolute kernel control with Enterprise. No way to be more absolute.**
