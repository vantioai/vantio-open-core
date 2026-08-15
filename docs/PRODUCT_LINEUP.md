# Vantio — product lineup (Optics repo)

> Architecture first, then SKU. Peer products — not nested dolls that each close every gap below them.

**Vantio Optics** (Free) · **Vantio Gate** ($499) · **Vantio Phantom Engine** ($799/node) · **Phantom Engine Enterprise** (talk to sales → ~$2k/node)

Talk-track: Optics helps you see. Gate applies the rules you set. Phantom Engine protects the machines you own — enforce and control together, one purchase. Phantom Engine Enterprise adds governance when you need proof and process on top.

Canonical company lineup when both exist: Enterprise root `PRODUCT_LINEUP.md`. Site: [vantio.ai/pricing](https://vantio.ai/pricing).

---

## Honest gaps

| Product | Job | What is still open |
|---------|-----|--------------------|
| **Optics** (Free) | **Observe** · Sight Loop | No block; traffic that never hits the interceptor is never recorded |
| **Gate** ($499) | **Enforce** · rules that stick where the agent is wired | SDK omission, raw sockets, fork escape; oversized streams may pass unscanned |
| **Phantom Engine** ($799/node) | **Control** on Linux hosts you enroll | Privileged disable of loader; pod-network caveats; only on enrolled hosts |
| **Phantom Engine Enterprise** | Governance on that protection | Same host scope |

| Product | What you see in data |
|---------|----------------------|
| **Optics** | `OBSERVED` (no enforce) |
| **Gate** | `ALLOWED` / `BLOCKED` / `REDACTED` on the wrapped path |
| **Phantom Engine** | Host `BLOCKED` + Rogue Reconciliation when app and host diverge |

---

## Feature layers

### Observe · Vantio Optics (Free)

- Free visibility — no paid account required
- Node `vantio run`: `fetch`, `undici.fetch`, `undici.request`, `undici.stream` / `pipeline` / `dispatch`, and Node `http`/`https`. Python `shield()`: urllib; requests, httpx, and aiohttp when already installed
- Captures: endpoint, response size, process ID, trace ID — no content, no prompts
- Does **not** block or redact — **observe only** ([fence](./observe-only.md))
- Workflow: **Sight Loop**
- SDK: `@vantio/agent-sdk` (Node.js), `vantio-agent-sdk` (Python)

### Enforce · Vantio Gate ($499)

- Policy where the agent is wired — not a claim that Gate closes raw sockets or SDK omission
- When an agent crosses a line you set, Gate can refuse a destination, strip sensitive fields, or cap spend
- Policy lives in the Gate control plane; enforcement runs in the Optics client interceptor
- Workflow: **Rules that stick**
- API: `GET /api/v1/config` (policy fetch), `POST /api/v1/ingest` (telemetry)

### Control · Vantio Phantom Engine ($799/node)

- Protection on **Linux machines you own** — enforce and control together, one purchase
- Do not stack Gate cloud $499 on this quote; the enforce plane ships with the node
- Rogue Reconciliation when the host sees a transmission with no app-layer record
- Phantom Engine Enterprise adds ledger, evidence, and dual-control depth — talk to sales
- This repo does not ship Phantom Engine. See `vantio-phantom-engine`.

---

## Capability matrix

| Capability | Optics | Gate | Phantom Engine |
|------------|:------:|:----:|:--------------:|
| Observe wrapped LLM/agent calls | ✓ | ✓ | ✓ |
| Block by hostname (wrapped path) | — | ✓ | ✓ |
| PII redaction (wrapped path) | — | ✓ | ✓ |
| Spend / size caps (wrapped path) | — | ✓ | ✓ |
| Host enforcement on enrolled Linux | — | — | ✓ |
| Fork inheritance on enrolled hosts | — | — | ✓ |
| CIDR / k8s network policy (enrolled) | — | — | ✓ |

---

## Repos

| Repo | Product | Role |
|------|---------|------|
| [`vantioai/vantio-open-core`](https://github.com/vantioai/vantio-open-core) | **Vantio Optics** · Observe | Free visibility; client used with Gate |
| [`vantioai/vantio-pro`](https://github.com/vantioai/vantio-pro) | **Vantio Gate** · Enforce | Policy control plane |
| [`vantioai/vantio-phantom-engine`](https://github.com/vantioai/vantio-phantom-engine) | **Vantio Phantom Engine** · Control | Linux host protection |

---

## One-line story

> Optics helps you see. Gate applies the rules you set. Phantom Engine protects the machines you own.
