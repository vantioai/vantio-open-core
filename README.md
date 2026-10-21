# Vantio

Linux security for AI.

This repository contains Vantio Optics, the Phantom Engine installer, and the Python SDK.

## Vantio Optics (Open Core)

Free, local-first observability for AI egress. Optics is the free Observe tier. It records the destination, the process, the size, and the timing of a supported outbound call. Does not block actions or retain prompts or completions.

The Optics home is moving to [github.com/vantioai/vantio-optics](https://github.com/vantioai/vantio-optics). Publishing still runs from this repository. The editor extension stays at [extensions/vantio-optics](extensions/vantio-optics). Commands and local install notes are in [extensions/vantio-optics/README.md](extensions/vantio-optics/README.md).

### Install

These are the versions npm and PyPI served on 2026-10-21. Manifests in this git tree can be newer than the registry.

| Package | Registry | Version |
| --- | --- | --- |
| `@vantio/cli` | npm | 0.3.24 |
| `@vantio/agent-sdk` | npm | 0.2.4 |
| `vantio-agent-sdk` | PyPI | 3.1.1 |
| `@vantio/optics-mcp` | npm | 0.1.2 |
| `@vantio/gate-mcp` | npm | 0.1.0 |

`@vantio/gate-mcp` is a compatibility package for an older integration.

Optics CLI, on macOS, Linux, and Windows (WSL):

```bash
npm install -g @vantio/cli@0.3.24
vantio run node agent.js
```

`vantio run` injects the Node interceptor with `NODE_OPTIONS --require` for `node`, `npx`, `tsx`, and `ts-node`. On Node it covers fetch, undici, http/https, http2, net/tls, WebSocket, and spawned curl or wget.

Python SDK:

```bash
pip install vantio-agent-sdk==3.1.1
```

Wrap a Python callable with `@shield`. Prefixing `vantio run python` does not intercept by itself.

Node SDK:

```bash
npm install @vantio/agent-sdk@0.2.4
```

The Node SDK exposes `shield()`. Outbound Node coverage comes from `vantio run`.

Optics MCP:

```bash
npm install @vantio/optics-mcp@0.1.2
```

Free Optics needs no account and no API key.

Browser paths stay outside this wrap.

A process can miss the wrapper when it opens a socket the Node interceptor does not see, starts a subprocess outside `vantio run`, or uses a runtime other than Node without the Python SDK. Optics records the paths it wrapped.

`vantio coverage` prints the processes and connections recorded on this system, and which of those paths are on a local allowlist. `vantio destinations` flags the first time a recorded program connects to a destination that is not on that list. `vantio export` sends those events as OTLP/HTTP JSON, syslog or JSON lines, or a webhook. Optics does not stop the call.

Telemetry is disabled by default. Set `VANTIO_TELEMETRY=1` to opt in. `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1` override that opt-in.

## Phantom Engine installer

Phantom Engine is enforcement and control for enrolled Linux systems. Contact Vantio. The product page is [vantio.ai/phantom-engine](https://vantio.ai/phantom-engine).

The installer source is [packages/vantio-install](packages/vantio-install). `vantio-install` is not on npm or PyPI. Operator install uses the sealed wheel described in [packages/vantio-install/docs/QUICKSTART.md](packages/vantio-install/docs/QUICKSTART.md). The commands are `vantio-install` and `vantio-verify`. That install does not replace `@vantio/cli`. The installer notes in that package target Ubuntu 24.04 LTS on x86_64.

## Documentation

- Site: [vantio.ai](https://vantio.ai)
- Docs: [vantio.ai/docs](https://vantio.ai/docs)
- Optics: [vantio.ai/optics](https://vantio.ai/optics)
- Phantom Engine: [vantio.ai/phantom-engine](https://vantio.ai/phantom-engine)
- CLI: [packages/vantio-cli/README.md](packages/vantio-cli/README.md)
- Python SDK: [packages/vantio-agent-sdk-py/README.md](packages/vantio-agent-sdk-py/README.md)
- Editor extension: [extensions/vantio-optics/README.md](extensions/vantio-optics/README.md)

## License

`@vantio/cli`, `@vantio/agent-sdk`, and `vantio-agent-sdk` declare MIT. License files for the CLI and the Python SDK are [packages/vantio-cli/LICENSE](packages/vantio-cli/LICENSE) and [packages/vantio-agent-sdk-py/LICENSE](packages/vantio-agent-sdk-py/LICENSE). The Node SDK declares MIT in [packages/vantio-agent-sdk/package.json](packages/vantio-agent-sdk/package.json). There is no root `LICENSE` file. The MIT grant covers the published packages named here.

## Security

Report a suspected vulnerability to security@vantio.ai. The process is [SECURITY.md](SECURITY.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
