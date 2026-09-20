# Vantio — product lineup (Optics repo)

> Architecture first, then SKU. Peer products — not nested dolls that each close every gap below them.

**Vantio Optics** (Free) · **Vantio Phantom Engine** ($799/node/mo) · **Vantio Enterprise** (talk to sales)

Talk-track: Optics helps you see. Phantom Engine protects the machines you own — Observe, Enforce, and Control together, one purchase. Enterprise adds governance when you need proof and process on top.

Canonical company lineup when both exist: Enterprise root `PRODUCT_LINEUP.md`. Site: [vantio.ai/pricing](https://vantio.ai/pricing).

---

## Honest gaps

| Product | Job | What is still open |
|---------|-----|--------------------|
| **Optics** (Free) | **Observe** · Sight Loop | No block; traffic that never hits the interceptor is never recorded |
| **Phantom Engine** ($799/node/mo) | **Enforce + Control** on Linux hosts you enroll | Privileged disable of loader; pod-network caveats; only on enrolled hosts |
| **Enterprise** (talk to sales) | Governance on that protection | Same host scope; certifications not held |

| Product | What you see in data |
|---------|----------------------|
| **Optics** | `OBSERVED` (no enforce) |
| **Phantom Engine** | `ALLOWED` / `BLOCKED` / `REDACTED` + Rogue Reconciliation when app and host diverge |

---

## Feature layers

### Observe · Vantio Optics (Free)

- Free visibility — no paid account required
- Node `vantio run`: `fetch`, `undici.fetch`, `undici.request`, `undici.stream` / `pipeline` / `dispatch` / `connect` / `upgrade`, and Node `http`/`https`. Python `shield()`: urllib; requests, httpx, and aiohttp when already installed
- Captures: endpoint, response size, process ID, trace ID — no content, no prompts
- Does **not** block or redact — **observe only** ([fence](./observe-only.md))
- Workflow: **Sight Loop**
- SDK: `@vantio/agent-sdk` (Node.js), `vantio-agent-sdk` (Python)

### Enforce + Control · Vantio Phantom Engine ($799/node/mo)

- Protection on **Linux machines you own** — Observe, Enforce, and Control together, one purchase
- Includes all Enforce functions: block by hostname, PII redaction, spend/size caps, policy-as-code
- Rogue Reconciliation when the host sees a transmission with no app-layer record
- Enterprise adds ledger, evidence, and dual-control depth — talk to sales
- This repo does not ship Phantom Engine. See `vantio-phantom-engine`.

> **Note on Gate:** Gate is the internal name for the Enforce function set inside Phantom Engine.
> `@vantio/gate-mcp` (in this repo) is a legacy/compat dry-run evaluation tool; Gate is not a
> current standalone public SKU.

---

## Capability matrix

| Capability | Optics | Phantom Engine | Enterprise |
|------------|:------:|:--------------:|:----------:|
| Observe wrapped LLM/agent calls | ✓ | ✓ | ✓ |
| Block by hostname (wrapped path) | — | ✓ | ✓ |
| PII redaction (wrapped path) | — | ✓ | ✓ |
| Spend / size caps (wrapped path) | — | ✓ | ✓ |
| Host enforcement on enrolled Linux | — | ✓ | ✓ |
| Fork inheritance on enrolled hosts | — | ✓ | ✓ |
| CIDR / k8s network policy (enrolled) | — | ✓ | ✓ |
| Durable ledger / dual-control | — | partial | ✓ |

---

## Repos

| Repo | Product | Role |
|------|---------|------|
| [`vantioai/vantio-open-core`](https://github.com/vantioai/vantio-open-core) | **Vantio Optics** · Observe | Free visibility; open-core client |
| [`vantioai/vantio-phantom-engine`](https://github.com/vantioai/vantio-phantom-engine) | **Vantio Phantom Engine** · Enforce + Control | Linux host protection |

---

## One-line story

> Optics helps you see. Phantom Engine protects the machines you own. Enterprise adds the governance layer.
