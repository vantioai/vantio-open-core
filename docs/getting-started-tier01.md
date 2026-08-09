# Getting Started with Vantio Optics
### Open Core · Free · Observe only

**Vantio Optics** is free visibility into what your agents send. Time to first event: under 60 seconds.  
Workflow: **[Sight Loop](./sight-loop.md)** (wrap → capture → inspect → residual)

---

## Step 1 — Install

```bash
npm install -g @vantio/cli
```

That's the only install step. Works on macOS, Linux, and Windows (WSL).

---

## Step 2 — Run your agent

Instead of running your agent directly, prefix it with `vantio run`:

```bash
# Before
node agent.js

# After
vantio run node agent.js
```

Nothing else changes. Your agent runs exactly the same way.

---

## Step 3 — See what's happening

The first time you run it, you'll see every outbound AI call intercepted in real time:

```
[ ∅ VANTIO ] Outbound LLM call intercepted
  host:    api.openai.com
  pid:     12345
  bytes:   237
  time:    2026-05-28T22:30:00.000Z
  → Optics observes only. Upgrade to Vantio Gate (Pro) to enforce policy.
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

## Step 4 — Connect Gate / Enterprise (optional)

Free Optics needs **no account and no API key**. Local `vantio prove` and
`vantio discover --local` work immediately after a run.

To attach **Vantio Gate** (Pro) or an Enterprise on-prem control plane:

1. Request a trial via [hello@vantio.ai](mailto:hello@vantio.ai) (or complete Stripe
   Checkout once self-serve billing is live — eng-shipped, keys not yet public).
2. You receive an API key (email / SE handoff). There is **no public self-serve
   key dashboard** today — [vantio.ai/dashboard](https://vantio.ai/dashboard)
   redirects to docs.
3. Save the key:

```bash
vantio login
```

Paste your key when prompted (or pass it directly: `vantio login vk_live_xxx`). Vantio
validates it and saves it to `~/.vantio/config.json` (chmod 600) — **no environment
variables to manage.** Every `vantio run` after this automatically picks up the saved
key:

```bash
vantio run node agent.js
```

Check your connection status anytime:

```bash
vantio whoami
# Key:    vk_live…a3f2
# Server: <your Gate control-plane URL>
# Status: connected — PRO plan
```

To disconnect: `vantio logout`.

> **Honesty note:** Remote dashboard sync and fleet `vantio discover` (without
> `--local`) require a Pro or Enterprise key pointed at a live control plane.
> Free Optics stays fully useful offline. Upgrade path:
> [vantio.ai/pricing](https://vantio.ai/pricing).

---

## Step 4b — Generate a proof artifact (Free)

After a run, you have local evidence you can share with an auditor:

```bash
vantio prove              # HTML report for the most recent run
vantio prove --list       # list all locally stored runs
vantio prove --format=md  # Markdown instead of HTML
```

The proof artifact includes: trace ID, machine/PID, timestamp, byte counts per
LLM host, action labels (OBSERVED / ALLOWED / REDACTED / BLOCKED), and summary
counts. **No prompts or completions are included** — the report is safe to share
with auditors, security teams, or compliance reviewers.

```
✓ Proof artifact written to: vantio-proof-0x1a2b3c4d.html
```

---

## Step 5 — Find your Shadow AI attack surface (Pro / Enterprise)

Once connected on a paid plan, `vantio discover` shows every AI call Vantio has seen
across your workspace — grouped by host, with a governance breakdown per host:

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

`OBSERVED` calls with no policy trace are your Shadow AI indicator — unenrolled
processes calling LLM endpoints outside Vantio's governance.

---

## Supported frameworks

Works with any framework that makes HTTP calls:

LangChain · AutoGen · CrewAI · OpenAI SDK · Anthropic SDK · AWS Bedrock · Google Vertex · Cohere · Groq · Together AI · Perplexity · any `fetch`-based agent

**Python agents:** `pip install vantio-agent-sdk` — see [vantio.ai/optics](https://vantio.ai/optics)

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
| **Free · Vantio Optics (this tier)** | Any process not started with `vantio run`; native socket calls |
| **Pro · Vantio Gate** | Raw sockets and unenrolled processes at the app layer |
| **Enterprise · Vantio Phantom Engine** | Ring-0 closes kernel-level bypass — Rogue Reconciliation when layers diverge |

Run `vantio discover --local` to see what Optics can observe on your machine. Residual risk closes with **Vantio Gate**, then **Vantio Phantom Engine** — see [observe-only.md](./observe-only.md).

> **Why honesty sells:** an audit team asking "can your agent bypass this?" gets a
> straight answer from Free: yes, intentionally, and here is the upgrade path that
> closes it. That transparency builds trust far faster than overclaiming.

---

## Common questions

**My agent uses Python, not Node.js.**
Use `pip install vantio-agent-sdk` and the `@shield` decorator. See the [Optics page](https://vantio.ai/optics) for examples. `vantio run` itself only instruments Node.js/TypeScript runtimes (`node`, `npx`, `tsx`, `ts-node`) via `NODE_OPTIONS`; other runtimes run normally without interception.

**Nothing is appearing in my terminal.**
Make sure you're using `node`, `npx`, `tsx`, or `ts-node` as the runtime — `vantio run python agent.py` runs your script normally but prints a one-line notice instead of intercepting, since Tier 1 Node interception uses a Node-specific mechanism. Use the Python SDK's `@shield` for Python agents.

**I ran `vantio login` but nothing shows up in my dashboard.**
Run `vantio whoami` and check the plan shown next to "Status: connected". If it says
FREE, that's expected — dashboard sync and `vantio discover` are Pro/Enterprise
features. Your agent's calls are still being observed locally in your terminal either
way. Upgrade at [vantio.ai/pricing](https://vantio.ai/pricing) to unlock sync.

**How do I log out / remove my saved key?**
`vantio logout` removes `~/.vantio/config.json`. You can also always override the
saved key for a single run with an explicit `VANTIO_API_KEY` environment variable,
which takes precedence over the saved config.

---

*Questions? [security@vantio.ai](mailto:security@vantio.ai) · [vantio.ai](https://vantio.ai)*
