# Spec — Wrap completeness follow-on (undici.request · Client.request)

**Brand:** Vantio Optics · Vantio Gate  
**Workflow:** Sight Loop · Rules that stick  
**Tier fence:** P0  
**Customer surface:** CLI · vantio.ai

Stripe live checkout and a second host stay parked.

## Goal

`undici.request` and `Client` / `Pool` / `Agent` `.request()` share the Optics/Gate path already used by `fetch` and `undici.fetch`.

## Checklist

- [x] Top-level `undici.request`
- [x] `Dispatcher.prototype.request` (Client / Pool / Agent)
- [x] Tests
- [ ] Publish `@vantio/cli` 0.3.5
- [ ] Public copy

## Out of scope

curl · raw sockets · browser · `undici.stream` / `pipeline` / `connect` / `upgrade` / `dispatch` · Stripe · stranger-host
