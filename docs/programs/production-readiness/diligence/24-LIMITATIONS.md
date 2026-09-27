# Limitations

Audience: INTERNAL_RESTRICTED

Document status: SKELETON

Future slot: `INVESTOR_UNDER_NDA`

Fill status: `PUBLIC_LIMITS_INDEXED`

Investor send: `NOT_CLEARED`

External publication: PROHIBITED

## Purpose

Make the public limitations easy to find before any investor sentence is written. The long list lives in `docs/products/optics/KNOWN-LIMITATIONS.md`. This page indexes the sentences documentation governance already requires, plus the gaps a diligence packet has to keep visible.

## Canonical sentences

Source: `docs/governance/canonical/known-limitations.md`. Re-read before quoting.

- A call that never hits the interceptor is not recorded.
- Browser paths stay outside this wrap.
- Without `vantio-agent-sdk`, prefixing `vantio run python` does not intercept.
- `vantio run` injects the Node interceptor only for `node`, `npx`, `tsx`, and `ts-node`.
- Optics does not block actions or retain prompts or completions.
- JSON records use `schema_status` `unstable-pre-1.0`.
- There is no OTLP exporter.
- `http.client` and `pycurl` do not store an HTTP status on the success path. That outcome stays unavailable.
- Free Optics needs no account and no API key.

## Further public gaps to keep beside an investor draft

Source: `docs/products/optics/KNOWN-LIMITATIONS.md` and `docs/PRODUCT_LINEUP.md`. Summarized as topics, not as a second manual.

| Topic | State recorded in those files |
| --- | --- |
| Enforcement, blocking, redaction, spend caps | Phantom Engine. Free Optics records `OBSERVED`. |
| Database, resident daemon, alerting, OTLP export | Absent |
| Stable schema | Absent |
| Retention and prune | Absent. Files stay until deleted. |
| Evidence signature and content hash | Absent |
| Stranger-host, external, and customer proof | Not claimed by the manual |
| Python install versus source | Published package recorded as 3.0.14. Source tree 3.1.0 is unpublished. |
| Telemetry by package | CLI 0.3.24 is opt-in. Published Python 3.0.14 `shield()` sends unless disabled. |
| Path segments | Stored. A secret placed in the path is stored with the call. |
| Certifications | Not held |
| Phantom Engine host caveats | Privileged disable of the loader, pod-network caveats, enrolled hosts only. Detail beyond the lineup is `NOT_VERIFIED_IN_THIS_REPO`. |

## Sections still empty

| Section | Value |
| --- | --- |
| Investor-facing limitation narrative | `NOT_FILLED` |
| Compensating-control promises | `NOT_SET` |
| Legal disclaimer | `NOT_FILLED` |

## Fill rules

- A limitation that is true in the manual stays in the investor draft.
- Architecture targets do not erase a shipping limitation.
- Do not add exploit detail in order to illustrate a gap.
