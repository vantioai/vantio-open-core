# Product boundary

Vantio Optics (Open Core) is free, local-first observability for AI agent egress. Optics is the free Observe tier. It does not block actions or retain prompts or completions.

Install the CLI with `npm install -g @vantio/cli` and run `vantio run node agent.js`. That command injects the Node interceptor with `NODE_OPTIONS --require` for `node`, `npx`, `tsx`, and `ts-node`.

Python support is `pip install vantio-agent-sdk`, then `@shield` or `vantio run python` after that install. Prefixing `vantio run python` does not intercept by itself.

Browser paths stay outside this wrap.

Phantom Engine is Enforce + Control on enrolled Linux hosts ($799/node/mo). Enterprise is governance on top of that protection and is talk-to-sales. Free Optics needs no account and no API key.

Telemetry is disabled by default. Set `VANTIO_TELEMETRY=1` to opt in. `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1` override that opt-in.

There is no OTLP exporter.
