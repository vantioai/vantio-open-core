# Getting Started with Vantio AI
### Tier 01 — Developer SDK

**Time to first event: under 60 seconds.**

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
  → Run `vantio login` to enforce policy and route events to your dashboard.
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

## Step 4 — Connect your dashboard (optional)

Sign up at [vantio.ai](https://vantio.ai), grab your API key from the dashboard, then run:

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
# Server: https://vantio.ai
# Status: connected — PRO plan
```

To disconnect: `vantio logout`.

> **Free plan note:** `vantio login` works with a free account too, so you can still
> use `whoami`/`logout` and remove env-var management. But dashboard sync (events
> persisting to your dashboard) and `vantio discover` (below) both require a Pro or
> Enterprise plan — the CLI tells you this honestly at login and in every run summary
> rather than silently doing nothing. Upgrade anytime at [vantio.ai/pricing](https://vantio.ai/pricing).

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

**Python agents:** `pip install vantio-agent-sdk` — see [vantio.ai/developers](https://vantio.ai/platform)

---

## What Vantio never captures

- The content of your prompts
- Model completions or responses
- Any personally identifiable information

Vantio records *that* a call was made, *when*, *to which provider*, and *how many bytes* — nothing more.

---

## Common questions

**My agent uses Python, not Node.js.**
Use `pip install vantio-agent-sdk` and the `@shield` decorator. See the [Platform page](https://vantio.ai/platform) for examples. `vantio run` itself only instruments Node.js/TypeScript runtimes (`node`, `npx`, `tsx`, `ts-node`) via `NODE_OPTIONS`; other runtimes run normally without interception.

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
