# Q13 — MCP awareness on the `vantio run` path

UTC: 2026-10-16

Founder approval: load `@vantio/mcp-awareness` from Node `vantio run` after the library commit `d21bdb08580988429cd3455fcabcf76b098d1c87`.

This page is the Q13 behavior. The design packet's earlier sentence that the library is not on the default path describes that library commit. `packages/vantio-cli/bin/interceptor.cjs` is unchanged. The public tools of `@vantio/gate-mcp` are unchanged.

## What `vantio run` does

For `node`, `npx`, `tsx`, and `ts-node`, `vantio run` adds `--import` of `packages/vantio-cli/bin/mcp-awareness-register.js` beside the existing interceptor `--require`.

| Control | Default | Effect |
| --- | --- | --- |
| `VANTIO_MCP_AWARENESS` | `on` | `off` or `0` does not add the import |
| `VANTIO_MCP_MODE` | `observe` | `enforce`, or `--mcp-enforce`, withholds inside this process |
| `VANTIO_MCP_INJECTION` | `log` | `block` is the only other accepted value |
| `VANTIO_MCP_RUG_PULL` | `log` | `block` is the only other accepted value |
| `VANTIO_MCP_POLICY` | absent | Optional operator policy file. Mode still comes from the environment |

`--mcp-enforce` does not win over `VANTIO_MCP_AWARENESS=off`. A mode other than `enforce` stays observe. A value other than `block` stays log.

Python `vantio run` does not load this library.

## No proxy hop

The register does not listen, does not call `net.connect`, and does not spawn a process of its own.

Observe copies bytes the workload already holds:

- A stdio `write` is copied, then the original `write` runs with the original chunk.
- `tapReadable` runs only after the workload has already added a `data` listener.
- A fetch body that is already a string or byte buffer is inspected, then the original `fetch` is called. The response clone is read after the caller has been given the response.

Enforce is the opt-in that can withhold:

- Piped stdio uses `createStdioPairGate` in this process. A non-MCP line is forwarded. A blocked JSON-RPC frame is not written to the child. The fixed error `vantio_mcp_policy_block` is written on the workload's readable and does not include payload bytes.
- A buffered HTTP request whose first 256 bytes are a JSON-RPC object is withheld before `fetch` when the decision is `BLOCK` or `GAP`. The caller receives that same fixed error. A stream or `Request` body is not read and is not withheld.
- `stdio: "inherit"` has no pipe to gate. It is logged only when observe can see a copy.

## No content storage

Records are the library's `vantio.mcp_observation.v1` objects. Argument values, tool-result text, and string ids are not fields. The register drops `ignored_non_json` and empty lines. It appends JSON lines to `~/.vantio/mcp-observations.jsonl` and stops at 1 MiB. `VANTIO_HOME` overrides the directory.

`server_id` is the child command's basename, or the fetch hostname. It is not read from the JSON-RPC message.

## Labels

| Result | Label |
| --- | --- |
| Observe forwards a stdio tool call, enforce withholds it, HTTP observe sends the request, HTTP enforce does not, and the canary is absent from the log and from stderr. Tests: `packages/vantio-cli/test/mcp-awareness-run.test.js` | Verified |
| Phantom Engine host copy and host enforce | Roadmap |
| A packed `@vantio/cli` tarball that does not contain this private package. The import fails closed to "do not change the workload" | Roadmap |
| Python `vantio run`, `spawnSync`, `fork`, and a stream HTTP body | Roadmap |

No result here is called unbreakable. No result is called audited.

## Rollback

Set `VANTIO_MCP_AWARENESS=off`. The register is not imported. In-memory sessions leave with the process. There is no on-disk conversation store to migrate.
