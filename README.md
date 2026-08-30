## Vantio Optics (Open Core)
Free, local-first observability for AI agent egress. See what your agents call out to —
without ever reading the conversation.

```
npm install -g @vantio/cli
vantio run node agent.js
```

That's the integration. Optics intercepts outbound calls to known LLM providers and reports
destination, process, size, and timing — never prompts or completions.

Python: `pip install vantio-agent-sdk`, then wrap your agent with `@shield`.

Optics is Tier 1 of Vantio's architecture — Observe. [Gate](https://vantio.ai/gate) (Enforce)
and [Phantom Engine](https://vantio.ai/phantom-engine) (Control) extend this to policy
enforcement and host-level runtime protection on enrolled Linux systems. Full docs:
vantio.ai/docs.

---

## Supported runtimes

That's the only install step. Works on macOS, Linux, and Windows (WSL).

On Node: fetch, undici, http/https, http2, net/tls, WebSocket, and spawned curl or wget.

`vantio run` only injects the Node interceptor (`NODE_OPTIONS --require`) for `node` / `npx` / `tsx` / `ts-node`.

Python support requires vantio-agent-sdk. Follow the current Python SDK example and verify that a supported outbound event appears before relying on the coverage state. Prefixing `vantio run python` does not intercept by itself.

Browser paths stay outside this wrap.

---

## What is recorded

Optics records connection and process metadata from supported wrapped agent paths. Does not block actions or retain prompts or completions.

Vantio records *that* a call was made, *when*, *to which provider*, and *how many bytes* — nothing more.

---

## What is never recorded

- The content of your prompts
- Model completions or responses
- Any personally identifiable information

---

## Present coverage boundaries

`vantio run` intercepts LLM calls by patching `globalThis.fetch` in the Node.js
runtime (via `NODE_OPTIONS --require`). This covers the vast majority of real agents
— every OpenAI SDK call, every LangChain.js call, every Vercel AI SDK call — without
any code changes.

**It can be bypassed.** A process can:
- Call an LLM endpoint directly through a native socket without using `fetch`
- Spawn a subprocess that isn't started with `vantio run`
- Use a language runtime other than Node without installing the Python SDK

**This is intentional, not a bug.** Vantio Optics surfaces your governance gap honestly.

Without the SDK, `vantio run python` does not intercept. Browser paths, or processes not started with `vantio run` / `shield()`, never hit Optics — and Optics does not invent a record for them.

---

## License and telemetry

MIT License.

Anonymous, opt-out usage analytics. No prompts, completions, API keys, or emails. Opt out at any time:

```
export VANTIO_TELEMETRY_DISABLED=1   # or
export DO_NOT_TRACK=1
```

---

## Upgrade path to Gate and Phantom Engine

Free Optics needs **no account and no API key**. `vantio login` is optional and later, for dashboard sync only, never a required step before running.

Optics is Tier 1 of Vantio's architecture — Observe. [Gate](https://vantio.ai/gate) (Enforce)
and [Phantom Engine](https://vantio.ai/phantom-engine) (Control) extend this to policy
enforcement and host-level runtime protection on enrolled Linux systems.

Residual risk closes with **Vantio Gate**, then **Vantio Phantom Engine** — see [vantio.ai/pricing](https://vantio.ai/pricing).
