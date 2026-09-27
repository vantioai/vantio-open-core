# Supported paths

A path is supported when a wrapped process records it. Anything else produces no Optics row. No row means not observed. It does not mean Optics blocked the call, allowed it, or made it safe.

Phantom Engine is the product that enforces on enrolled hosts. This page does not describe Phantom Engine coverage.

## When a process is wrapped

| How you start it | What gets attached |
| --- | --- |
| `vantio run node\|npx\|tsx\|ts-node …` | Node interceptor via `NODE_OPTIONS --require` |
| `vantio run python\|python3\|py\|python3.N …` with `vantio-agent-sdk` installed | Python `sitecustomize` → `install()` |
| `shield()` in a Python 3.0.14 process | Same Python hooks for that `shield()` scope |
| Any other launch | Nothing. No record for that process. |

A child that starts without the injected `NODE_OPTIONS` or `PYTHONPATH` is a new, unwrapped process.

## Node 0.3.24 libraries

Recorded when the call's destination is in scope:

- `fetch` and undici `fetch` / `request` / `stream` / `pipeline` / `dispatch` / `connect` / `upgrade`
- Node `http` and `https`, including `ClientRequest`
- Node `http2`
- `net` and `tls` connects to in-scope hosts
- WebSocket outbound frame size (frame payloads are not parsed)
- Spawned `curl`, `wget`, `httpie`, and `aria2c`, including the argv forms listed in [NODE-GUIDE.md](NODE-GUIDE.md)

## Python 3.0.14 libraries

Recorded when the destination is in scope and the SDK is installed and wrapped:

- urllib `urlopen` and custom openers
- `requests`, `httpx` sync and async, `aiohttp`, when those packages are installed
- `urllib3` and `pycurl`, when installed
- `http.client`
- `socket.connect`, `connect_ex`, `create_connection`
- subprocess `curl`, `wget`, `httpie`, `aria2c`

Unpublished 3.1.0 source keeps this set and changes outcome fields and socket timing. It does not add a new public client family beyond what 3.0.14 already patches. See [PYTHON-GUIDE.md](PYTHON-GUIDE.md).

## Destinations that are in scope

Exact hostnames in the CLI catalog (`packages/vantio-cli/bin/llm-hosts.cjs`), kept in parallel with the Python set:

`api.openai.com`, `api.anthropic.com`, `generativelanguage.googleapis.com`, `api.cohere.ai`, `api.cohere.com`, `api.mistral.ai`, `api.groq.com`, `api.together.xyz`, `api.perplexity.ai`, `inference.ai.azure.com`, `openai.azure.com`, `api.x.ai`, `api.deepseek.com`, `api.fireworks.ai`, `openrouter.ai`, `api.cerebras.ai`, `api.voyageai.com`, `api.sambanova.ai`, `api.deepinfra.com`, `router.huggingface.co`, `api-inference.huggingface.co`, `api.replicate.com`, `ollama.com`, `integrate.api.nvidia.com`.

Also in scope:

- A DNS suffix of a listed name (`api.openai.com` matches `foo.api.openai.com`). A listed token must contain a dot, so a bare word cannot match every host.
- Regional Amazon Bedrock runtime, Mantle, and agents runtime hostnames; Google Vertex AI hostnames; Hugging Face Inference Endpoints (`*.endpoints.huggingface.cloud`). The matchers are specific patterns, not all of `amazonaws.com` or `googleapis.com`.
- Ollama on `localhost`, `127.0.0.1`, or `::1` port `11434`.
- Hosts you add with `VANTIO_EXTRA_LLM_HOSTS` (comma-separated).

`vantio status` reports whether seven Node provider packages resolve from the current working directory: `openai`, `@anthropic-ai/sdk`, `@google/genai`, `@google/generative-ai`, `cohere-ai`, `groq-sdk`, `@mistralai/mistralai`. `UNSUPPORTED` there means that package did not resolve. It does not mean the host catalog excluded the provider, and it does not mean traffic is blocked.

## Provider label

Node writes `provider` with `guessProvider`, a substring test. `api.openai.com` becomes `openai`. A hostname that contains `openai`, `anthropic`, `azure`, or the other substrings in that function is labeled the same way, including hosts that are not in the catalog if they were recorded through an extra-host or similar in-scope path. Unknown hosts become `other`. Localhost outside the Ollama port check becomes `local`.

Published Python 3.0.14 writes `provider` `"other"` for the hooks in this tree. Use `hostname` to see the destination. Unpublished 3.1.0 source can replace `"other"` from the catalog. The same hostname can therefore be `openai` in a Node 0.3.24 file and `other` in a Python 3.0.14 file.

## Paths that stay unobserved

These do not get an Optics record. Optics does not describe them as protected:

- Browser pages and browser extensions
- A process not started with `vantio run` or Python `shield()`
- `vantio run python` when `vantio-agent-sdk` is not installed on that interpreter
- Ruby, Go, Java, Rust, and other runtimes
- A Node or Python HTTP client the interceptor does not patch
- A native addon socket that never calls the patched Node APIs
- A grandchild process that does not inherit the wrapper
- A host that is outside the catalog, outside the regional patterns, and outside `VANTIO_EXTRA_LLM_HOSTS`
- Traffic after the process is killed with `SIGKILL`, before the exit hook

Redirects are recorded only when the follow-up request is itself in scope. Optics does not rewrite a proxy or an IPv6 address into a single canonical destination.

## Checking a claim of coverage

Run the agent under the wrapper, then `vantio search` or `vantio tail` for that trace id. A row with `action` `OBSERVED` is a record of that call. No row is `NOT_OBSERVED` for that call. Do not upgrade either result into an enforcement result.
