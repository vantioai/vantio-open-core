# Vantio Gate MCP

Part of **Vantio Gate** · **Policy Latch** (dry-run evaluate via Model Context Protocol).

Package: [`@vantio/gate-mcp`](../packages/vantio-gate-mcp/)

## Fence

> **Commercial/production deferred** until Stripe/banking. This package is a dry-run POC — do not market as production enforce.

- Evaluates host / size / spend decisions  
- Fetches Pro policy + residual risk (with API key)  
- **Never** blocks live traffic from inside the MCP  
- **Never** pushes unconstrained policy to production  
- **Never** exposes Absolute Control  

Live latch remains `vantio run` + Pro (when billing is live). Absolute Control remains Phantom Engine.

## Quick start

```bash
npx -y @vantio/gate-mcp
```

See [surfaces.md](./surfaces.md) for the full integration map.
