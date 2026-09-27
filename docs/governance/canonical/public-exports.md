# Public exports

Current public names are the TypeScript `export` declarations in `@vantio/agent-sdk` and `__all__` in `vantio-agent-sdk`. `fetchPolicy`, `reportAnomaly`, and their Python counterparts are Phantom Engine / Enterprise control-plane helpers. Free Optics does not require them.

## @vantio/agent-sdk

- `VantioContext` — trace id for the active `shield` frame
- `WithVantioOptions` — optional `traceId` for `shield` / `withVantio`
- `VantioEventPayload` — metadata fields accepted by `reportAnomaly`
- `VantioActionTaken` — action token union
- `VantioPolicy` — policy object returned by `fetchPolicy`
- `DEFAULT_POLICY` — permissive fail-open default
- `normalizePolicy` — coerce unknown input into a `VantioPolicy`
- `withVantio` — async trace context
- `shield` — alias of `withVantio`
- `getCurrentTraceId` — active trace id, or undefined outside `shield`
- `getCurrentContext` — active `VantioContext`, or undefined outside `shield`
- `reportAnomaly` — send metadata when cloud ingest is enabled
- `FetchPolicyOptions` — `ingestUrl`, `timeoutMs`, and `signal`
- `fetchPolicy` — load policy; on failure return a copy of `DEFAULT_POLICY`
- `RedactionResult` — rewritten text plus redaction categories
- `redactPII` — local PII replacement; the text does not leave the process

## vantio-agent-sdk (Python)

- `shield`
- `report_anomaly`
- `get_current_trace_id`
- `VantioContext`
- `fetch_policy`
- `redact_pii`
- `VantioPolicy`
- `RedactionResult`
