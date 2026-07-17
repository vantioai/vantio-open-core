# Vantio Gate MCP

Part of **Vantio Gate** · **Policy Latch** (dry-run evaluate via Model Context Protocol).

Package: [`@vantio/gate-mcp`](../packages/vantio-gate-mcp/)

## Fence

- Evaluates host / size / spend decisions  
- Fetches Pro policy + residual risk (with API key)  
- **Never** blocks live traffic from inside the MCP  
- **Never** pushes unconstrained policy to production  
- **Never** exposes Absolute Control  

Live latch remains `vantio run` + Pro. Absolute Control remains Phantom Engine.

## Quick start

```bash
npx -y @vantio/gate-mcp
```

See [surfaces.md](./surfaces.md) for the full integration map.
