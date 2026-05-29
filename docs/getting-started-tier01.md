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
  → Set VANTIO_API_KEY to route events to your dashboard.
```

Add `--summary` to get a report when your agent finishes:

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

## Step 4 — Send events to your dashboard (optional)

Sign up at [vantio.ai](https://vantio.ai), get your free API key, and add two environment variables:

```bash
export VANTIO_API_KEY=vantio_your_key_here
export VANTIO_INGEST_URL=https://vantio.ai
export VANTIO_CLOUD_INGEST=true
```

Now run your agent again. Events appear in your dashboard at [vantio.ai/dashboard](https://vantio.ai/dashboard) within seconds.

---

## Supported frameworks

Works with any framework that makes HTTP calls:

LangChain · AutoGen · CrewAI · OpenAI SDK · Anthropic SDK · AWS Bedrock · Google Vertex · Cohere · Groq · Together AI · Perplexity · any `fetch`-based agent

**Python agents:** `pip install vantio-agent-sdk` — see [vantio.ai/developers](https://vantio.ai/developers)

---

## What Vantio never captures

- The content of your prompts
- Model completions or responses
- Any personally identifiable information

Vantio records *that* a call was made, *when*, *to which provider*, and *how many bytes* — nothing more.

---

## Common questions

**My agent uses Python, not Node.js.**  
Use `pip install vantio-agent-sdk` and the `@shield` decorator. See the [Developers page](https://vantio.ai/developers) for examples.

**Nothing is appearing in my terminal.**  
Make sure you're using `node`, `npx`, `tsx`, or `ts-node` as the runtime. Python and other runtimes run normally without interception at Tier 01.

**I want events in my dashboard.**  
Set `VANTIO_API_KEY`, `VANTIO_INGEST_URL`, and `VANTIO_CLOUD_INGEST=true`. Get your key at [vantio.ai](https://vantio.ai).

---

*Questions? [security@vantio.ai](mailto:security@vantio.ai) · [vantio.ai](https://vantio.ai)*
