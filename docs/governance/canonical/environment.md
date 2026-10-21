# Environment variables

Free Optics runs with no account and no API key. Telemetry stays off unless `VANTIO_TELEMETRY=1`. `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1` keep it off.

| Variable | Role |
|---|---|
| `DO_NOT_TRACK` | Set to `1` to keep telemetry off. |
| `VANTIO_API_BASE` | Base URL for the Gate MCP control-plane client. Default `https://api.vantio.ai`. Not required for free Optics. `gate_get_policy` and `gate_residual_risk` read this from the environment. They do not take a host argument. |
| `VANTIO_API_KEY` | Control-plane key for Phantom Engine / Enterprise policy and ingest. Not required for free Optics. |
| `VANTIO_AUDIT_MODE` | Set to `1` to flag events as audit mode. |
| `VANTIO_CLOUD_INGEST` | Set to `true` or `1` before `reportAnomaly` / `report_anomaly` will send. |
| `VANTIO_EXPORT_WEBHOOK_TOKEN` | Optional bearer token for `vantio export --webhook`. The CLI does not print it. Unset sends the webhook with no authorization header. |
| `VANTIO_EXTRA_LLM_HOSTS` | Comma-separated extra hostnames added to the in-scope set. |
| `VANTIO_HOME` | Local data directory. Default `~/.vantio`. |
| `VANTIO_IDENTITY` | Older alias read by `@vantio/agent-sdk` when `VANTIO_API_KEY` is unset. |
| `VANTIO_INGEST_URL` | Control-plane base URL. Default `https://vantio.ai`. |
| `VANTIO_JSON` | Set to `1` for the unstable JSON run record. `vantio run --json` sets this. |
| `VANTIO_MCP_AWARENESS` | Node `vantio run` sets `on`. `off` or `0` does not load in-process MCP awareness. |
| `VANTIO_MCP_INJECTION` | `log` unless set to `block`. |
| `VANTIO_MCP_MODE` | `observe` unless `--mcp-enforce` or the value `enforce`. |
| `VANTIO_MCP_POLICY` | Optional path to an operator policy file. The mode still comes from `VANTIO_MCP_MODE`. |
| `VANTIO_MCP_RUG_PULL` | `log` unless set to `block`. |
| `VANTIO_SUMMARY` | Set to `1` to print the run summary. `vantio run --summary` sets this. |
| `VANTIO_TELEMETRY` | Set to `1` to opt in to the anonymous usage ping. |
| `VANTIO_TELEMETRY_DISABLED` | Set to `1` to keep the ping off even when `VANTIO_TELEMETRY=1`. |
| `VANTIO_TRACE_ID` | Trace id propagated into the wrapped process. |

`VANTIO_SOAK_LOCAL` is classified internal in the env catalog. It is a soak harness flag, not a supported customer setting. The catalog records it so a new runtime variable cannot appear without a classification.
