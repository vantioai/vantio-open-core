# Privacy model

Audience: INTERNAL_RESTRICTED

Document status: SKELETON

Future slot: `INVESTOR_UNDER_NDA`

Fill status: `NOT_FILLED`

Investor send: `NOT_CLEARED`

External publication: PROHIBITED

## Purpose

Reserve the privacy chapter. Public boundaries below are indexed so a later fill does not widen them. Private prompts and customer content stay out of this file.

## Sources to re-read

| Source | Use |
| --- | --- |
| `docs/products/optics/PRIVACY-AND-SECURITY.md` | Stored fields, absent fields, file modes, path-segment caveat, proof export |
| `docs/products/optics/TELEMETRY.md` | Version-specific telemetry |
| `docs/governance/canonical/known-limitations.md` | Public limitation sentences |
| `docs/governance/canonical/ai-guide.md` | Control-plane helpers are Phantom Engine / Enterprise, not free Optics |
| `docs/architecture/optics-foundation/02-EVIDENCE-AND-PRIVACY-CONTRACT.md` | Target allowlist. Architecture, not the shipping recorder. |

## Indexed public boundaries

These sentences are already the public manual's boundary. They are indexed here so the investor slot cannot drift. Re-read the source before sending.

| Boundary | Source |
| --- | --- |
| Optics records structural metadata. Prompts and completions are absent from the free record. | `docs/products/optics/README.md` |
| A call that never hits the interceptor is not recorded. | `docs/governance/canonical/known-limitations.md` |
| Browser paths stay outside this wrap. | `README.md` |
| Free Optics needs no account and no API key. | `README.md` |
| CLI telemetry is disabled unless `VANTIO_TELEMETRY=1`. `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1` override. | `README.md` |
| Published Python 3.0.14 `shield()` sends unless disabled. Unpublished 3.1.0 source is opt-in. Describe the package the person installed. | `docs/products/optics/KNOWN-LIMITATIONS.md` |
| Query strings are dropped. Path segments are stored and can hold secrets if the application put them there. | `docs/products/optics/PRIVACY-AND-SECURITY.md` |
| `vantio prove` re-renders a run file. It does not add a content hash or signature. | `docs/products/optics/PRIVACY-AND-SECURITY.md` |

## Control-plane redaction

`redactPII` / `redact_pii` are control-plane helpers. `docs/governance/canonical/public-exports.md` places them with Phantom Engine / Enterprise. Free Optics does not document turning body rewrite on. This skeleton does not add that procedure.

## Sections still empty

| Section | Value |
| --- | --- |
| Data-flow diagram | `NOT_FILLED` |
| Retention commitment | Absent in the shipping product. See limitations. Value for a promise: `NOT_SET` |
| Subprocessors | `NOT_FILLED` |
| Customer prompt samples | Prohibited |
| Privacy policy legal text | `NOT_FILLED`. Do not draft legal terms in this room. |

## Fill rules

- Keep examples synthetic and empty of secrets. Prefer no payload example at all.
- State the package version next to any telemetry sentence.
- Architecture allowlists are targets. Label them as architecture until Gate 8 is opened by a separate force.
