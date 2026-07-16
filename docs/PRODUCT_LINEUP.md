# Vantio Product Lineup

This is the canonical product lineup for Vantio. All READMEs, docs, and dashboard copy derive from this table.

---

## The three products

| Product | Repo | Promise |
|---------|------|---------|
| **Open Core** (Developers) | [`vantioai/vantio-open-core`](https://github.com/vantioai/vantio-open-core) | **Sees everything** — observe all agent/LLM traffic |
| **Pro** | [`vantioai/vantio-pro`](https://github.com/vantioai/vantio-pro) | **Enforces** — block, redact, caps; dashboard shows what policy stops |
| **Phantom Engine** (Enterprise kernel) | [`vantioai/vantio-phantom-engine`](https://github.com/vantioai/vantio-phantom-engine) | **Absolute control** — fewer events, inescapable kernel catch |
| **Enterprise suite** | all three together | Full stack: observe + enforce + absolute control |

---

## What each tier does

### Open Core — Sees everything
- Free developer tool; no paid account required to start observing
- `vantio run` wraps any agent process with a TLS interceptor — no code changes needed
- Captures: endpoint, response size, process ID, trace ID across the agent's full execution
- Does **not** capture prompts, completions, or any content
- Does **not** block, redact, or enforce policy on its own — that is Pro's job
- SDK: `@vantio/agent-sdk` (Node.js), `vantio-agent-sdk` (Python)

### Pro — Enforces
- Policy control plane for teams that need enforceable governance
- Owns tenant configuration (`GET /api/v1/config`) and telemetry ingest (`POST /api/v1/ingest`)
- Tells the Open Core client **what** to enforce; enforcement runs locally in the client interceptor
- Capabilities: block by hostname, PII redaction, spend/size caps
- Dashboard shows what policy stops in real time

### Phantom Engine — Absolute control
- Enterprise kernel layer; deployed as a Linux daemon or Kubernetes DaemonSet
- eBPF uprobes on TLS libraries (`SSL_write`, `gnutls_record_send`) at Ring-0
- Enforcement is inescapable: sits beneath the application layer, below any possible bypass
- Fork inheritance: child processes cannot escape trace context by spawning subprocesses
- Produces fewer events than Open Core/Pro — but every event is high-signal and decisive
- Adds the unbypassable guarantee beneath the Pro HTTP contract; does not replace it

### Enterprise suite
- All three products together
- **Observe** (Open Core) + **Enforce** (Pro) + **Absolute control** (Phantom Engine)
- Enterprise customers get the full stack: observe everything, enforce policy, catch the rest at the kernel

---

## Tier comparison

| Capability | Open Core | Pro | Enterprise |
|------------|-----------|-----|------------|
| Observe all LLM/agent calls | ✓ | ✓ | ✓ |
| Block by hostname | — | ✓ | ✓ |
| PII redaction | — | ✓ | ✓ |
| Spend / size caps | — | ✓ | ✓ |
| Dashboard: what policy stops | — | ✓ | ✓ |
| eBPF / kernel enforcement | — | — | ✓ |
| Inescapable catch (below app layer) | — | — | ✓ |
| CIDR / k8s network policies | — | — | ✓ |
| Fork inheritance enforcement | — | — | ✓ |

---

## One-line story

> **Open Core sees everything. Pro enforces it. Phantom Engine makes it inescapable.**
