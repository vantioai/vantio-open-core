# Supported paths

Exact LLM host names are the governed list in `docs/governance/LLM-HOSTS.json`. Node `LLM_HOSTS`, Python `_LLM_HOSTS`, and Python `_CATALOG` keys are the same set. Regional Bedrock, Vertex, and Hugging Face endpoint patterns are `hostMatchesRegional` in `llm-hosts.cjs` and `_regional_provider` in the Python outcome module. They are not a second static host list.

`vantio run` injects the Node interceptor for `node`, `npx`, `tsx`, and `ts-node`. The interceptor comment records these wrapped paths:

- `globalThis.fetch`
- `undici.fetch`
- `undici.request`
- `undici.stream/pipeline/connect/upgrade`
- `http/https.request`
- `http2.connect`
- `net.Socket.connect / tls.connect`
- `globalThis.WebSocket`
- `spawn/exec of curl, wget`

Python observation runs inside `vantio-agent-sdk`. The CLI comment says the Python runtime `needs vantio-agent-sdk`. Wrapped clients named in `_http_observe.py` are `urllib.request.urlopen`, `httpx`, `aiohttp`, `urllib3`, `pycurl`, and `socket.connect`.

## Not covered

Browser paths stay outside this wrap.

Prefixing `vantio run python` does not intercept by itself.
