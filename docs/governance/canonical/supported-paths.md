# Supported paths

Exact LLM host names are the governed list in `docs/governance/LLM-HOSTS.json`. Node `LLM_HOSTS`, Python `_LLM_HOSTS`, and Python `_CATALOG` keys are the same set. Regional Bedrock, Vertex, and Hugging Face endpoint patterns are `hostMatchesRegional` in `llm-hosts.cjs` and `_regional_provider` in the Python outcome module. They are not a second static host list.

`vantio run` injects the Node interceptor for `node`, `npx`, `tsx`, and `ts-node`. The interceptor comment records these wrapped paths. Each phrase is the whole path clause:

- `globalThis.fetch`
- `undici.fetch`
- `undici.request`
- `Client/Pool/Agent request() and dispatch()`
- `undici.stream/pipeline/connect/upgrade`
- `http/https.request|get and ClientRequest`
- `http2.connect / session.request`
- `net.Socket.connect / tls.connect`
- `globalThis.WebSocket / undici.WebSocket`
- `undici.upgrade / CONNECT tunnel writes`
- `spawn/exec of curl, wget, httpie, and aria2c`

`http/https.request|get` includes both `.request` and `.get`, and `ClientRequest` is that same clause. `session.request` is included with `http2.connect`. `undici.WebSocket` is included with `globalThis.WebSocket`. `undici.upgrade / CONNECT tunnel writes` is the tunnel-write clause, separate from `undici.stream/pipeline/connect/upgrade`.

Node spawn tool curl. Node spawn tool wget. Node spawn tool httpie. Node spawn tool aria2c. Those four tools are distinct. The source clause is `spawn/exec of curl, wget, httpie, and aria2c`.

Python observation runs inside `vantio-agent-sdk`. The CLI comment says the Python runtime `needs vantio-agent-sdk`. The `_http_observe.py` module docstring records these wrapped clients:

- `urllib.request.urlopen and OpenerDirector.open`
- `requests`
- `httpx`
- `aiohttp`
- `urllib3`
- `pycurl`
- `socket.connect / connect_ex / create_connection / ssl.SSLSocket.connect and http.client request/putrequest`
- `subprocess / os.system / asyncio curl, wget, httpie, and aria2c`

`OpenerDirector.open` is included with `urllib.request.urlopen`. `http.client request/putrequest` is included with `socket.connect`.

Python spawn tool curl. Python spawn tool wget. Python spawn tool httpie. Python spawn tool aria2c. Those four tools are distinct.

`http.client` and pycurl do not store an HTTP status on the success path. That outcome stays unavailable.

## Not covered

Browser paths stay outside this wrap.

Prefixing `vantio run python` does not intercept by itself.
