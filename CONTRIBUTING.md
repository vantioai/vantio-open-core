# Contributing

Issues and pull requests are welcome for the public packages in this repository.

## Packages

- `packages/vantio-cli` — `@vantio/cli`, the Optics command line
- `packages/vantio-agent-sdk` — `@vantio/agent-sdk`, the Node SDK
- `packages/vantio-agent-sdk-py` — `vantio-agent-sdk`, the Python SDK
- `packages/vantio-optics-mcp` — `@vantio/optics-mcp`
- `packages/vantio-install` — Phantom Engine installer. It is not published on npm or PyPI.
- `extensions/vantio-optics` — editor extension. Publishing still runs from this repository. The Optics home is moving to [github.com/vantioai/vantio-optics](https://github.com/vantioai/vantio-optics).

## Development

CI uses Node.js 22. The CLI accepts Node.js `>=18.3.0`. The Python SDK accepts Python `>=3.10`. CI runs the Python SDK on 3.10, 3.11, and 3.12.

pnpm is the package manager. The version is the `packageManager` field in `package.json`.

```bash
pnpm install --frozen-lockfile
pnpm --filter @vantio/cli run lint
pnpm --filter @vantio/cli run test
pnpm --filter @vantio/agent-sdk run typecheck
pnpm --filter @vantio/agent-sdk run typecheck:test
pnpm --filter @vantio/agent-sdk run test
pnpm --filter @vantio/agent-sdk run build
pnpm --filter @vantio/gate-mcp test
node --test packages/vantio-mcp-awareness/test/*.test.js
```

Python SDK tests, from `packages/vantio-agent-sdk-py`:

```bash
python -m unittest discover -s tests -t .
```

Run the CLI from source:

```bash
node packages/vantio-cli/bin/vantio.js
```

## Records

Keep prompts, completions, and API keys out of Optics records and out of telemetry. Telemetry stays off unless `VANTIO_TELEMETRY=1`.

## Security

Use [SECURITY.md](SECURITY.md) for a suspected vulnerability. A public issue is the wrong place for an unfixed vulnerability.

## Conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
