# Spec — Wrap completeness follow-on (undici.stream · pipeline · dispatch)

**Brand:** Vantio Optics · Vantio Gate  
**Workflow:** Sight Loop · Rules that stick  
**Tier fence:** P0  
**Customer surface:** CLI · vantio.ai

Stripe live checkout and a second (stranger) host stay parked. Python SDK stays **3.0.4**.

## Goal

`undici.stream`, `pipeline`, and raw `Client.dispatch` share the Optics/Gate path already used by `fetch` and `undici.request`.

`DispatcherBase.dispatch` is the chokepoint (Client / Pool / Agent inherit it). Top-level `undici.stream` / `pipeline` go through the global Agent’s `dispatch`.

## Reentrancy

Fetch and `request` already Gate, then call orig which calls `dispatch`. Use module-level `undiciWrapDepth`:

- Increment around orig fetch / request launches until those promises settle
- `dispatch` wrap: if `undiciWrapDepth > 0`, pass through

## Sync Gate

`dispatch` is sync (returns boolean). Cannot `await policyReady`. Delay until `policyReady` then run sync Gate (same idea as Node `http.request`).

**Block:** do not call orig dispatch; `queueMicrotask` handler `onConnect` → `onHeaders(403, Buffer[] pairs)` → `onData` → `onComplete`. Return `true`.

**Redact:** sync `redactBody` on string/Buffer/Uint8Array bodies only. Pipeline request bodies are often streams → host-block still works; PII redaction on streaming pipeline bodies stays residual (`ENFORCEMENT_GAP`).

## Checklist

- [x] `DispatcherBase.dispatch` wrap (not `Dispatcher.prototype.dispatch`)
- [x] Reentrancy vs fetch / request (`undiciWrapDepth`)
- [x] Tests: `undici.stream` redact + block; `Client.dispatch` block; `client.pipeline` host-block
- [ ] Publish `@vantio/cli` 0.3.6
- [ ] Public copy names `undici.stream` / `pipeline` / `dispatch`

## Out of scope

curl · raw sockets · browser · `undici.connect` / `upgrade` · HTTP/2 extras · Stripe · stranger-host
