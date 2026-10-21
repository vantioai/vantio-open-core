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

Optics is the free Observe tier. [Phantom Engine](https://vantio.ai/phantom-engine) (Enforce + Control)
extends this to policy enforcement and host-level runtime protection on enrolled Linux systems. Full docs:
vantio.ai/docs.

---

## Supported runtimes

Node install is `npm install -g @vantio/cli`. If that fails with `EACCES`, the global prefix is not writable: `npm install -g @vantio/cli --prefix "$HOME/.local"` and add `$HOME/.local/bin` to `PATH`. Python also needs `pip install vantio-agent-sdk`. Where `python` is not installed, run `vantio run python3 agent.py`. Run logs are `~/.vantio/runs/` (`$VANTIO_HOME/runs` when `VANTIO_HOME` is set). A Node run writes a file even with no LLM call and prints a summary only when a supported call was recorded. A Python run writes a file only when the SDK recorded a supported call. `vantio run pnpm` and `vantio run bash` do not write one. Works on macOS, Linux, and Windows (WSL).

On Node: fetch, undici, http/https, http2, net/tls, WebSocket, and spawned curl or wget.

`vantio run` only injects the Node interceptor (`NODE_OPTIONS --require`) for `node` / `npx` / `tsx` / `ts-node`.

Python support requires vantio-agent-sdk. Follow the current Python SDK example and verify that a supported outbound event appears before relying on the coverage state. Prefixing `vantio run python` does not intercept by itself.

Browser paths stay outside this wrap.

---

## What is recorded

Optics records connection and process metadata from supported wrapped agent paths. Does not block actions or retain prompts or completions.

Vantio records *that* a call was made, *when*, *to which provider*, and *how many bytes* — nothing more.

`vantio coverage` prints the processes and connections recorded on this system, and which of those paths are on a local allowlist. `vantio destinations` flags the first time a recorded program connects to a destination that is not on that list. `vantio export` sends those events as OTLP/HTTP JSON, syslog or JSON lines, or a webhook. Optics does not stop the call. Prompts and completions are never stored.

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

Published packages such as `@vantio/cli`, `@vantio/agent-sdk`, and `vantio-agent-sdk` declare MIT in their package manifests (and in package-level LICENSE files where present). This repository does not currently publish a root LICENSE file.

Telemetry is disabled by default. Set VANTIO_TELEMETRY=1 to opt in. VANTIO_TELEMETRY_DISABLED=1 or DO_NOT_TRACK=1 override.

---

## Upgrade path to Phantom Engine and Enterprise

Free Optics needs **no account and no API key**.

Optics is the free Observe tier. [Phantom Engine](https://vantio.ai/phantom-engine) (Enforce + Control)
extends this to policy enforcement and host-level runtime protection on enrolled Linux systems.

Residual risk closes with **Vantio Phantom Engine**. Contact Vantio — see [vantio.ai/pricing](https://vantio.ai/pricing). Enterprise: Contact Vantio.
