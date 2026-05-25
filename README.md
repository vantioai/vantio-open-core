# @vantio/agent-sdk

> See what your AI agents are doing. Two lines of code. Free.

```bash
npm install @vantio/agent-sdk   # Node.js
pip install vantio-agent-sdk    # Python
```

---

## The idea

AI agents make outbound calls you can't see. Vantio wraps your agent, intercepts every network call to a known LLM provider, and streams the metadata to a dashboard — without ever reading your prompts.

---

## Node.js

```ts
import { shield } from "@vantio/agent-sdk";

await shield(async () => {
  await runMyLLMAgent();
});
```

That's the integration. `shield()` propagates a trace ID through every async hop in your agent's call tree.

---

## Python

```python
from vantio import shield

@shield
async def run_agent():
    await call_openai(prompt)
```

Or as a context manager:

```python
async with shield():
    await run_agent()
```

---

## CLI — zero code changes

```bash
npx vantio run node agent.js
npx vantio run python agent.py
npx vantio run --summary node agent.js   # print call summary on exit
```

The CLI patches `globalThis.fetch` at runtime via `--require`. Your code doesn't change.

---

## What gets captured

- Which LLM endpoint was called
- Bytes in the response
- The process ID
- A trace ID that links calls across your agent's full execution

**What never gets captured:** prompts, completions, or any content from your requests.

---

## Dashboard

[vantio.ai/dashboard](https://vantio.ai/dashboard) — free tier includes 10,000 events/month.

For active blocking, compliance logs, and Slack alerts, see [vantio.ai/pricing](https://vantio.ai/pricing).

---

## License

MIT — [vantio.ai](https://vantio.ai)
