# vantio-open-core

Open-source SDK and CLI for the [Vantio](https://vantio.ai) AI agent visibility platform.

> The web application, dashboard, and API have moved to the private [`vantioai/vantio-app`](https://github.com/vantioai/vantio-app) repository.

---

## Packages

| Package | Description |
|---------|-------------|
| [`packages/vantio-agent-sdk`](./packages/vantio-agent-sdk) | Node.js agent SDK (`@vantio/agent-sdk`) |
| [`packages/vantio-cli`](./packages/vantio-cli) | CLI runner (`@vantio/cli`) |
| [`packages/vantio-agent-sdk-py`](./packages/vantio-agent-sdk-py) | Python agent SDK (`vantio-agent-sdk`) |

---

## Quick start

```bash
npm install @vantio/agent-sdk   # Node.js
pip install vantio-agent-sdk    # Python
```

### Node.js

```ts
import { shield } from "@vantio/agent-sdk";

await shield(async () => {
  await runMyLLMAgent();
});
```

### Python

```python
from vantio import shield

@shield
async def run_agent():
    await call_openai(prompt)
```

### CLI — zero code changes

```bash
npx vantio run node agent.js
npx vantio run python agent.py
npx vantio run --summary node agent.js
```

---

## What gets captured

- Which LLM endpoint was called
- Bytes in the response
- The process ID
- A trace ID that links calls across your agent's full execution

**What never gets captured:** prompts, completions, or any content from your requests.

---

## Telemetry

Anonymous, opt-out usage analytics — no prompts, completions, API keys, or emails. Opt out at any time:

```bash
export VANTIO_TELEMETRY_DISABLED=1   # or
export DO_NOT_TRACK=1
```

---

## Platform

[vantio.ai](https://vantio.ai) — free tier includes 10,000 events/month.

Dashboard: [vantio.ai/dashboard](https://vantio.ai/dashboard)
Pricing: [vantio.ai/pricing](https://vantio.ai/pricing)

---

## License

MIT
