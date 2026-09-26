# Getting Started with Vantio Optics
### Open Core · Free · Observe only

**Time to first event: under 60 seconds.**  
Workflow: **[Sight Loop](./sight-loop.md)** (wrap → capture → inspect → residual)

---

## Step 1 — Install

```bash
npm install -g @vantio/cli
```

That's the only install step. Works on macOS, Linux, and Windows (WSL).

---

## Step 2 — Run your agent

Instead of running your Node agent directly, prefix it with `vantio run`:

```bash
# Before
node agent.js

# After
vantio run node agent.js
```

Python: install `vantio-agent-sdk` first, then `vantio run python agent.py`. Prefixing `vantio run python` does not intercept by itself.

---

## Step 3 — See what's happening

The first time you run it, you'll see every outbound AI call intercepted in real time:

```
[ ∅ VANTIO ] Outbound LLM call intercepted
  host:    api.openai.com
  pid:     12345
  bytes:   237
  time:    2026-05-28T22:30:00.000Z
  → Optics observes only. Upgrade to Vantio Phantom Engine to enforce policy.
```

A summary prints automatically when your agent finishes. You can also request it explicitly:

```bash
vantio run --summary node agent.js
```

```
[ ∅ VANTIO ] Run Summary
  LLM calls:    7
  Hosts:        api.openai.com, api.anthropic.com
  Total bytes:  94,201
  Duration:     12.4s
```

---

## Step 4 — Local commands

Free Optics needs **no account and no API key**. Local `vantio prove`,
`vantio search`, `vantio tail`, `vantio diff`, and `vantio discover --local`
work immediately after a run.

---

## Step 4b — Generate a proof artifact (Free)

After a run, you have local evidence you can share with an auditor:

```bash
vantio prove              # HTML report for the most recent run
vantio prove --list       # list all locally stored runs
vantio prove --format=md  # Markdown instead of HTML
vantio search openai      # search captured calls
vantio tail               # latest calls from the most recent run
vantio diff <a> <b>       # compare two local runs
```

The proof artifact includes: trace ID, machine/PID, timestamp, byte counts per
LLM host, action labels (OBSERVED / ALLOWED / REDACTED / BLOCKED), and summary
counts. **No prompts or completions are included** — the report is safe to share
with auditors, security teams, or compliance reviewers.

```
✓ Proof artifact written to: vantio-proof-0x1a2b3c4d.html
```

---

## Step 5 — Phantom Engine / Enterprise connected discover

Connected `vantio discover` is a Phantom Engine / Enterprise capability. It is not part of free Optics. Free Optics stays on this machine (`vantio discover --local`). The commands below are that upgrade path:

```bash
vantio discover
vantio discover --since=7d
vantio discover --host=api.openai.com
vantio discover --since=30d --json
```

```
Shadow AI Attack Surface — last 24h
--------------------------------------------------------------------------------
TARGET HOST                       CALLS    ALLOWED   REDACTED  BLOCKED   OBSERVED  SHADOW?   LAST SEEN
--------------------------------------------------------------------------------
api.openai.com                       42         38          4        0         0   no        2026-05-28 22:30:00 UTC
--------------------------------------------------------------------------------
1 host(s) shown  |  No Shadow AI indicators detected.
```

That reading belongs to Phantom Engine / Enterprise connected discover. It is not a free Optics workspace.

---

## Supported frameworks

Works with any framework that makes HTTP calls:

LangChain · AutoGen · CrewAI · OpenAI SDK · Anthropic SDK · AWS Bedrock · Google Vertex · Cohere · Groq · Together AI · Perplexity · any `fetch`-based agent

**Python agents:** `pip install vantio-agent-sdk`, then `vantio run python agent.py` or `@shield` — prefixing `vantio run python` does not intercept by itself. See [vantio.ai/optics](https://vantio.ai/optics).

---

## What Vantio never captures

- The content of your prompts
- Model completions or responses
- Any personally identifiable information

Vantio records *that* a call was made, *when*, *to which provider*, and *how many bytes* — nothing more.

---

## Free Observe is bypassable by design — and that's the point

`vantio run` intercepts LLM calls by patching `globalThis.fetch` in the Node.js
runtime (via `NODE_OPTIONS --require`). This covers the vast majority of real agents
— every OpenAI SDK call, every LangChain.js call, every Vercel AI SDK call — without
any code changes.

**It can be bypassed.** A process can:
- Call an LLM endpoint directly through a native socket without using `fetch`
- Spawn a subprocess that isn't started with `vantio run`
- Use a language runtime other than Node without installing the Python SDK

**This is intentional, not a bug.** Vantio Optics surfaces your governance gap honestly. The gap itself is what motivates upgrading:

| Tier | What's bypassable |
|------|-------------------|
| **Free · Vantio Optics (this tier)** | Any process not started with `vantio run` / `shield()`; Python without `vantio-agent-sdk`; native socket calls the interceptor does not mediate |
| **Vantio Phantom Engine** ($799/node/mo) | Raw sockets and unenrolled processes not on an enrolled Linux host |
| **Vantio Enterprise** | Same host scope; adds ledger, dual-control, and certifications |

Run `vantio discover --local` to see what Optics can observe on your machine. Residual risk closes with **Vantio Phantom Engine** — see [observe-only.md](./observe-only.md).

> **Why honesty sells:** an audit team asking "can your agent bypass this?" gets a
> straight answer from Free: yes, intentionally, and here is the upgrade path that
> closes it. That transparency builds trust far faster than overclaiming.

---

## Common questions

**My agent uses Python, not Node.js.**
Install `vantio-agent-sdk` on that interpreter, then `vantio run python agent.py` or use the `@shield` decorator. Prefixing `vantio run python` does not intercept by itself — the SDK has to be installed. `vantio run` only injects the Node interceptor (`NODE_OPTIONS --require`) for `node` / `npx` / `tsx` / `ts-node`.

**Nothing is appearing in my terminal.**
For Node, use `node`, `npx`, `tsx`, or `ts-node` under `vantio run`. For Python, install `vantio-agent-sdk` first, then `vantio run python agent.py` or `@shield`. Without the SDK, `vantio run python` prints a one-line notice and does not intercept.

---

*Questions? [security@vantio.ai](mailto:security@vantio.ai) · [vantio.ai](https://vantio.ai)*
