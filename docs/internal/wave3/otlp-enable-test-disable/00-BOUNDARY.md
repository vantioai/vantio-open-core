# OTLP enable-test-disable boundary

PRIVATE | DEFAULT DISABLED | NOT SHIPPED | NO PUBLIC OTLP EXPORT | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

Producer role: internal proof. This agent does not sit the independent council and does not self-assign a council pass.

Producer identity: Cursor cloud agent `bc-620ad0a8-456f-506c-b043-dd5c6351cfe5`, model Grok 4.7, reasoning `xhigh`, context `500k`, fast `false`.

Producer URL: https://cursor.com/agents/bc-620ad0a8-456f-506c-b043-dd5c6351cfe5

Producer classification: `W3_OTLP_ENABLE_TEST_DISABLE_READY_FOR_COUNCIL`

That classification means the enable-test-disable proof is ready for a separate council. It is not a council verdict, not a public OTLP support claim, and not a resolution of Founder decision 12.

## 1. Locked input

| Item | Value |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Starting commit | `0cd36cf1d01c4db83a0a6999db0a322441f61c98` |
| Commit subject | Merge Wave 3 PE integrated runtime onto main. Source-only. Host attachment false. |
| Branch | `cursor/wave3-otlp-enable-test-disable-cfe5` |
| Force | Wave 3 Track 10, OTLP enable-test-disable |

## 2. What this force implements

An internal module, `@vantio/w3-otlp-enable-test-disable` at `0.0.0-unstable-pre-1.0`, outside `pnpm-workspace.yaml`. `runEnableTestDisable` reads the live I3 and mapping rest state, enables traces only inside that call, records each attempt, and returns with the adapters disabled.

The adapter under test is the existing `@vantio/optics-otel-i3` package. Its producer classification stays `OTEL_I3_ADAPTER_READY_FOR_COUNCIL_DEFAULT_DISABLED`. Its `default_enabled` value stays false. The mapping document stays WS7-I2 version 0 with `i3_status` `NOT_AUTHORIZED`.

## 3. What this force keeps closed

- A public OTLP support claim. `public_shipped_support` stays false. `docs/optics-otel-mapping.md` still says Optics does not export OTLP.
- Founder decision 12. The field stays `unresolved`. Broader I3 product authorization stays `NOT_AUTHORIZED`.
- CLI `0.3.24`, Node SDK `0.2.4`, and Python `3.1.0`.
- Metrics, logs, protobuf, environment-variable enablement, and credential headers.
- Publish, announce, host attach, and customer deploy.
- The I3 adapter council. `council` on that package stays `PENDING_COUNCIL`.

## 4. Registers

`REST-REGISTER.json` in this directory is the at-rest honesty register. `docs/programs/production-readiness/wave3/OTLP-REST-REGISTER.json` is the same bytes. The module refuses to load when those files differ or when either file marks the adapter enabled.
