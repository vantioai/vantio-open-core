# Vantio Framework Integrations

**Vantio Optics** (Free · Open Core) works with any framework that sends outbound HTTP calls. The
interception mechanism (`vantio run` patching `globalThis.fetch` for Node.js, or
the Python `@shield` decorator) requires zero code changes for the common path.

This guide shows the minimal wiring for the most popular agentic frameworks.

---

## LangChain.js (Node.js / TypeScript)

LangChain.js uses the global `fetch` for all provider calls. `vantio run` patches
`fetch` automatically — no code changes needed.

```bash
# Before
node agent.js

# After — LangChain calls are intercepted automatically
vantio run node agent.js
vantio run tsx agent.ts
```

To correlate a full agent chain with a single trace ID, wrap with `shield()`:

```typescript
import { shield } from "@vantio/agent-sdk";
import { ChatOpenAI } from "@langchain/openai";
import { HumanMessage } from "@langchain/core/messages";

await shield(async () => {
  const model = new ChatOpenAI({ modelName: "gpt-4o" });
  const response = await model.invoke([new HumanMessage("Hello!")]);
  console.log(response.content);
});
```

```bash
npm install @vantio/agent-sdk
vantio run node agent.js
```

**What you see in the terminal:**

```
[ ∅ VANTIO ] run trace_id=0x1a2b3c4d5e6f7a8b

[ ∅ VANTIO ] Outbound LLM call intercepted
  host:    api.openai.com
  pid:     12345
  bytes:   4,821
  time:    2026-07-16T18:00:01.100Z
  → Optics observes only — see [observe-only.md](./observe-only.md)
```

---

## LangChain Python

LangChain Python makes HTTP calls through `httpx` or `requests` — not through a
patchable `fetch`. Use the Python `@shield` decorator to attach a trace context.
For PII scrubbing before calls reach the LLM, use `redact_pii()`.

```python
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from vantio import shield, get_current_trace_id

@shield
async def run_chain():
    model = ChatOpenAI(model="gpt-4o")
    response = await model.ainvoke([HumanMessage(content="Hello!")])
    print(f"Vantio trace: {get_current_trace_id()}")
    return response

import asyncio
asyncio.run(run_chain())
```

**With policy-driven PII redaction (Pro/Enterprise):**

```python
import os
from vantio import shield, fetch_policy, redact_pii
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

policy = fetch_policy(os.environ["VANTIO_API_KEY"])

@shield
async def run_chain(user_input: str):
    prompt = user_input
    if policy.pii_redact:
        result = redact_pii(user_input, policy.pii_types)
        prompt = result.text                    # scrubbed before LLM call

    model = ChatOpenAI(model="gpt-4o")
    return await model.ainvoke([HumanMessage(content=prompt)])
```

> **Free note:** `@shield` provides trace context and enables `report_anomaly()` for
> cloud ingest (Pro/Enterprise). On Free, it's a no-op wrapper that's safe to leave
> in place — it never blocks and never captures content.

---

## CrewAI (Python)

CrewAI orchestrates multi-agent pipelines. Wrap `crew.kickoff()` with `shield()`:

```python
from crewai import Crew, Agent, Task
from vantio import shield

researcher = Agent(role="Researcher", goal="...", backstory="...", verbose=True)
task = Task(description="Research ...", agent=researcher)
crew = Crew(agents=[researcher], tasks=[task], verbose=True)

@shield
async def run():
    result = crew.kickoff(inputs={"topic": "AI governance"})
    return result

import asyncio
asyncio.run(run())
```

**Synchronous crews** — CrewAI's `kickoff()` is synchronous; use the context manager
form to avoid `asyncio.run()` inside a sync call:

```python
import asyncio
from vantio import shield

async def main():
    async with shield() as ctx:
        print(f"Vantio trace: {ctx.trace_id}")
        result = crew.kickoff(inputs={"topic": "AI governance"})
    return result

asyncio.run(main())
```

**With PII scrubbing on crew inputs:**

```python
import os
from vantio import shield, fetch_policy, redact_pii

policy = fetch_policy(os.environ.get("VANTIO_API_KEY", ""))

async def run_crew(raw_input: str):
    topic = raw_input
    if policy.pii_redact:
        topic = redact_pii(raw_input, policy.pii_types).text

    async with shield() as ctx:
        result = crew.kickoff(inputs={"topic": topic})
    return result
```

---

## LlamaIndex (Python)

LlamaIndex uses `httpx` — same path as LangChain Python: `@shield` from `vantio-agent-sdk`.

```python
from llama_index.llms.openai import OpenAI
from vantio import shield

@shield
async def ask(q: str):
    llm = OpenAI(model="gpt-4o-mini")
    return await llm.acomplete(q)
```

See also `examples/adapters/llamaindex-py/`.

---

## Vercel AI SDK (Node.js / TypeScript)

The Vercel AI SDK (`ai` package) routes all provider calls through the global `fetch`.
`vantio run` intercepts them automatically.

```bash
# No code changes — just use vantio run
vantio run node app.js
vantio run tsx app.ts
```

```typescript
import { generateText } from "ai";
import { openai } from "@ai-sdk/openai";

const { text } = await generateText({
  model: openai("gpt-4o"),
  prompt: "Explain AI governance in one sentence.",
});

console.log(text);
```

```bash
vantio run node app.js
# [ ∅ VANTIO ] run trace_id=0x...
# [ ∅ VANTIO ] Outbound LLM call intercepted
#   host:    api.openai.com
#   ...
```

For multi-step pipelines that should share a single trace ID:

```typescript
import { shield } from "@vantio/agent-sdk";
import { generateText, streamText } from "ai";
import { openai } from "@ai-sdk/openai";

await shield(async () => {
  const planResult = await generateText({
    model: openai("gpt-4o"),
    prompt: "Make a plan.",
  });

  const { textStream } = streamText({
    model: openai("gpt-4o-mini"),
    prompt: `Execute: ${planResult.text}`,
  });

  for await (const chunk of textStream) {
    process.stdout.write(chunk);
  }
});
```

---

## AutoGen / AG2 (Python)

```python
import asyncio
from autogen import AssistantAgent, UserProxyAgent
from vantio import shield

assistant = AssistantAgent("assistant", llm_config={"model": "gpt-4o"})
user_proxy = UserProxyAgent("user_proxy", human_input_mode="NEVER")

@shield
async def run():
    await user_proxy.a_initiate_chat(assistant, message="Hello, solve a problem.")

asyncio.run(run())
```

---

## Summary

| Framework | Language | Integration method |
|-----------|----------|--------------------|
| LangChain.js | Node.js / TS | `vantio run` (zero code changes) |
| Vercel AI SDK | Node.js / TS | `vantio run` (zero code changes) |
| LangChain Python | Python | `@shield` decorator / `async with shield()` |
| CrewAI | Python | `@shield` around `crew.kickoff()` |
| AutoGen / AG2 | Python | `@shield` around the initiate call |
| Any Node.js agent | Node.js | `vantio run` (zero code changes) |
| Any Python agent | Python | `pip install vantio-agent-sdk` + `@shield` |

---

## CLI flags that work with every framework

```bash
vantio run --summary node agent.js     # print a run summary on exit
vantio run --audit   node agent.js     # flag events as VANTIO_AUDIT_MODE=1
vantio prove                           # HTML proof artifact from most recent run
vantio prove --list                    # list all local run logs
vantio discover --local                # aggregate local run history (Free, no key)
```

---

*[vantio.ai](https://vantio.ai) · [Pricing](https://vantio.ai/pricing) · [Dashboard](https://vantio.ai/dashboard)*
